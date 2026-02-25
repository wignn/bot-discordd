package stats

import (
	"bufio"
	"os"
	"runtime"
	"strconv"
	"strings"
	"time"
)

func readUptime() float64 {
	data, err := os.ReadFile("/proc/uptime")
	if err != nil {
		return 0
	}
	fields := strings.Fields(string(data))
	if len(fields) == 0 {
		return 0
	}
	v, _ := strconv.ParseFloat(fields[0], 64)
	return v
}

type cpuTimes struct {
	idle  uint64
	total uint64
}

func readCPUTimes() cpuTimes {
	f, err := os.Open("/proc/stat")
	if err != nil {
		return cpuTimes{}
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "cpu ") {
			return parseCPULine(line)
		}
	}
	return cpuTimes{}
}

func parseCPULine(line string) cpuTimes {
	fields := strings.Fields(line)
	if len(fields) < 5 {
		return cpuTimes{}
	}
	var vals []uint64
	for _, f := range fields[1:] {
		v, _ := strconv.ParseUint(f, 10, 64)
		vals = append(vals, v)
	}
	var total uint64
	for _, v := range vals {
		total += v
	}
	idle := vals[3]
	return cpuTimes{idle: idle, total: total}
}

func collectCPU() CPUStats {
	s := CPUStats{
		Cores: runtime.NumCPU(),
	}

	if f, err := os.Open("/proc/cpuinfo"); err == nil {
		scanner := bufio.NewScanner(f)
		for scanner.Scan() {
			line := scanner.Text()
			if strings.HasPrefix(line, "model name") {
				parts := strings.SplitN(line, ":", 2)
				if len(parts) == 2 {
					s.Model = strings.TrimSpace(parts[1])
					break
				}
			}
		}
		f.Close()
	}

	t1 := readCPUTimes()
	time.Sleep(200 * time.Millisecond)
	t2 := readCPUTimes()

	totalDelta := t2.total - t1.total
	idleDelta := t2.idle - t1.idle
	if totalDelta > 0 {
		s.UsagePercent = round2(float64(totalDelta-idleDelta) / float64(totalDelta) * 100)
	}

	return s
}

func collectMemory() MemoryStats {
	m := MemoryStats{}
	f, err := os.Open("/proc/meminfo")
	if err != nil {
		return m
	}
	defer f.Close()

	info := make(map[string]uint64)
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		parts := strings.SplitN(line, ":", 2)
		if len(parts) != 2 {
			continue
		}
		key := strings.TrimSpace(parts[0])
		valStr := strings.TrimSpace(parts[1])
		valStr = strings.TrimSuffix(valStr, " kB")
		v, _ := strconv.ParseUint(strings.TrimSpace(valStr), 10, 64)
		info[key] = v
	}

	totalKB := info["MemTotal"]
	availKB := info["MemAvailable"]
	usedKB := totalKB - availKB

	m.Total = formatBytes(totalKB * 1024)
	m.Used = formatBytes(usedKB * 1024)
	if totalKB > 0 {
		m.UsagePercent = round2(float64(usedKB) / float64(totalKB) * 100)
	}
	return m
}

func collectNetwork() NetworkStats {
	n := NetworkStats{}
	f, err := os.Open("/proc/net/dev")
	if err != nil {
		return n
	}
	defer f.Close()

	var totalRX, totalTX uint64
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		if !strings.Contains(line, ":") {
			continue
		}
		parts := strings.SplitN(line, ":", 2)
		if len(parts) != 2 {
			continue
		}
		iface := strings.TrimSpace(parts[0])
		if iface == "lo" {
			continue
		}
		fields := strings.Fields(parts[1])
		if len(fields) < 10 {
			continue
		}
		rx, _ := strconv.ParseUint(fields[0], 10, 64)
		tx, _ := strconv.ParseUint(fields[8], 10, 64)
		totalRX += rx
		totalTX += tx
	}

	n.RX = formatBytes(totalRX)
	n.TX = formatBytes(totalTX)
	return n
}

func countProcesses() int {
	entries, err := os.ReadDir("/proc")
	if err != nil {
		return 0
	}
	count := 0
	for _, e := range entries {
		if e.IsDir() {
			if _, err := strconv.Atoi(e.Name()); err == nil {
				count++
			}
		}
	}
	return count
}

func readLoadAvg() string {
	data, err := os.ReadFile("/proc/loadavg")
	if err != nil {
		return "0 0 0"
	}
	fields := strings.Fields(string(data))
	if len(fields) >= 3 {
		return fields[0] + " " + fields[1] + " " + fields[2]
	}
	return "0 0 0"
}
