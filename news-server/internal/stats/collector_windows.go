package stats

import (
	"fmt"
	"os/exec"
	"runtime"
	"strconv"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

var (
	kernel32                 = syscall.NewLazyDLL("kernel32.dll")
	psapi                    = syscall.NewLazyDLL("psapi.dll")
	iphlpapi                 = syscall.NewLazyDLL("iphlpapi.dll")
	procGetTickCount64       = kernel32.NewProc("GetTickCount64")
	procGetSystemTimes       = kernel32.NewProc("GetSystemTimes")
	procGlobalMemoryStatusEx = kernel32.NewProc("GlobalMemoryStatusEx")
	procGetDiskFreeSpaceExW  = kernel32.NewProc("GetDiskFreeSpaceExW")
	procEnumProcesses        = psapi.NewProc("EnumProcesses")
	procGetIfTable           = iphlpapi.NewProc("GetIfTable")
)

// --- uptime ---

func readUptime() float64 {
	r, _, _ := procGetTickCount64.Call()
	ms := uint64(r)
	return float64(ms) / 1000.0
}

// --- CPU ---

func readSystemTimes() (idle, kernel, user uint64) {
	var idleFt, kernelFt, userFt syscall.Filetime
	procGetSystemTimes.Call(
		uintptr(unsafe.Pointer(&idleFt)),
		uintptr(unsafe.Pointer(&kernelFt)),
		uintptr(unsafe.Pointer(&userFt)),
	)
	idle = uint64(idleFt.HighDateTime)<<32 | uint64(idleFt.LowDateTime)
	kernel = uint64(kernelFt.HighDateTime)<<32 | uint64(kernelFt.LowDateTime)
	user = uint64(userFt.HighDateTime)<<32 | uint64(userFt.LowDateTime)
	return
}

func collectCPU() CPUStats {
	s := CPUStats{
		Cores: runtime.NumCPU(),
	}

	// Get CPU model from wmic
	out, err := exec.Command("wmic", "cpu", "get", "Name", "/value").Output()
	if err == nil {
		for _, line := range strings.Split(string(out), "\n") {
			line = strings.TrimSpace(line)
			if strings.HasPrefix(line, "Name=") {
				s.Model = strings.TrimPrefix(line, "Name=")
				break
			}
		}
	}

	// Two-sample CPU usage
	idle1, kernel1, user1 := readSystemTimes()
	time.Sleep(200 * time.Millisecond)
	idle2, kernel2, user2 := readSystemTimes()

	idleDelta := idle2 - idle1
	kernelDelta := kernel2 - kernel1
	userDelta := user2 - user1
	totalDelta := kernelDelta + userDelta
	if totalDelta > 0 {
		s.UsagePercent = round2(float64(totalDelta-idleDelta) / float64(totalDelta) * 100)
	}

	return s
}

// --- Memory ---

type memoryStatusEx struct {
	dwLength                uint32
	dwMemoryLoad            uint32
	ullTotalPhys            uint64
	ullAvailPhys            uint64
	ullTotalPageFile        uint64
	ullAvailPageFile        uint64
	ullTotalVirtual         uint64
	ullAvailVirtual         uint64
	ullAvailExtendedVirtual uint64
}

func collectMemory() MemoryStats {
	m := MemoryStats{}

	var ms memoryStatusEx
	ms.dwLength = uint32(unsafe.Sizeof(ms))
	r, _, _ := procGlobalMemoryStatusEx.Call(uintptr(unsafe.Pointer(&ms)))
	if r == 0 {
		return m
	}

	used := ms.ullTotalPhys - ms.ullAvailPhys
	m.Total = formatBytes(ms.ullTotalPhys)
	m.Used = formatBytes(used)
	if ms.ullTotalPhys > 0 {
		m.UsagePercent = round2(float64(used) / float64(ms.ullTotalPhys) * 100)
	}
	return m
}

// --- Disk ---

func collectDisk() DiskStats {
	d := DiskStats{}

	root, _ := syscall.UTF16PtrFromString("C:\\")
	var freeBytesAvailable, totalBytes, totalFreeBytes uint64

	r, _, _ := procGetDiskFreeSpaceExW.Call(
		uintptr(unsafe.Pointer(root)),
		uintptr(unsafe.Pointer(&freeBytesAvailable)),
		uintptr(unsafe.Pointer(&totalBytes)),
		uintptr(unsafe.Pointer(&totalFreeBytes)),
	)
	if r == 0 {
		return d
	}

	used := totalBytes - totalFreeBytes
	d.Total = formatBytes(totalBytes)
	d.Used = formatBytes(used)
	if totalBytes > 0 {
		d.UsagePercent = round2(float64(used) / float64(totalBytes) * 100)
	}
	return d
}

// --- Network ---

type mibIfRow struct {
	wszName           [512]uint16
	dwIndex           uint32
	dwType            uint32
	dwMtu             uint32
	dwSpeed           uint32
	dwPhysAddrLen     uint32
	bPhysAddr         [8]byte
	dwAdminStatus     uint32
	dwOperStatus      uint32
	dwLastChange      uint32
	dwInOctets        uint32
	dwInUcastPkts     uint32
	dwInNUcastPkts    uint32
	dwInDiscards      uint32
	dwInErrors        uint32
	dwInUnknownProtos uint32
	dwOutOctets       uint32
	dwOutUcastPkts    uint32
	dwOutNUcastPkts   uint32
	dwOutDiscards     uint32
	dwOutErrors       uint32
	dwOutQLen         uint32
	dwDescrLen        uint32
	bDescr            [256]byte
}

func collectNetwork() NetworkStats {
	n := NetworkStats{}

	// First call to get required buffer size
	var size uint32
	procGetIfTable.Call(0, uintptr(unsafe.Pointer(&size)), 0)
	if size == 0 {
		return n
	}

	buf := make([]byte, size)
	r, _, _ := procGetIfTable.Call(
		uintptr(unsafe.Pointer(&buf[0])),
		uintptr(unsafe.Pointer(&size)),
		0,
	)
	if r != 0 {
		return n
	}

	// First 4 bytes = number of entries
	numEntries := *(*uint32)(unsafe.Pointer(&buf[0]))
	rowSize := unsafe.Sizeof(mibIfRow{})

	var totalRX, totalTX uint64
	for i := uint32(0); i < numEntries; i++ {
		offset := 4 + uintptr(i)*rowSize
		if offset+rowSize > uintptr(len(buf)) {
			break
		}
		row := (*mibIfRow)(unsafe.Pointer(&buf[offset]))
		// Skip loopback (type 24)
		if row.dwType == 24 {
			continue
		}
		totalRX += uint64(row.dwInOctets)
		totalTX += uint64(row.dwOutOctets)
	}

	n.RX = formatBytes(totalRX)
	n.TX = formatBytes(totalTX)
	return n
}

// --- Processes ---

func countProcesses() int {
	pids := make([]uint32, 4096)
	var bytesReturned uint32
	r, _, _ := procEnumProcesses.Call(
		uintptr(unsafe.Pointer(&pids[0])),
		uintptr(len(pids)*4),
		uintptr(unsafe.Pointer(&bytesReturned)),
	)
	if r == 0 {
		return 0
	}
	return int(bytesReturned / 4)
}

// --- Load Average ---

func readLoadAvg() string {
	// Windows does not have load average; approximate with CPU queue length
	out, err := exec.Command("wmic", "cpu", "get", "LoadPercentage", "/value").Output()
	if err != nil {
		return "N/A"
	}
	for _, line := range strings.Split(string(out), "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "LoadPercentage=") {
			val := strings.TrimPrefix(line, "LoadPercentage=")
			if v, err := strconv.ParseFloat(val, 64); err == nil {
				pct := fmt.Sprintf("%.1f%%", v)
				return pct
			}
		}
	}
	return "N/A"
}
