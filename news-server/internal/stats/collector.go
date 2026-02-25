package stats

import (
	"fmt"
	"os"
	"runtime"
	"time"
)

type CPUStats struct {
	Model        string  `json:"model"`
	Cores        int     `json:"cores"`
	UsagePercent float64 `json:"usagePercent"`
}

type MemoryStats struct {
	Total        string  `json:"total"`
	Used         string  `json:"used"`
	UsagePercent float64 `json:"usagePercent"`
}

type DiskStats struct {
	Total        string  `json:"total"`
	Used         string  `json:"used"`
	UsagePercent float64 `json:"usagePercent"`
}

type NetworkStats struct {
	RX string `json:"rx"`
	TX string `json:"tx"`
}

type StatsPayload struct {
	Hostname      string       `json:"hostname"`
	Uptime        string       `json:"uptime"`
	UptimeSeconds float64      `json:"uptimeSeconds"`
	CPU           CPUStats     `json:"cpu"`
	Memory        MemoryStats  `json:"memory"`
	Disk          DiskStats    `json:"disk"`
	Network       NetworkStats `json:"network"`
	OS            string       `json:"os"`
	Processes     int          `json:"processes"`
	LoadAverage   string       `json:"loadAverage"`
	Status        string       `json:"status"`
	LastUpdated   string       `json:"lastUpdated"`
}

func Collect() StatsPayload {
	p := StatsPayload{
		OS:          runtime.GOOS,
		Status:      "online",
		LastUpdated: time.Now().UTC().Format(time.RFC3339),
	}

	p.Hostname, _ = os.Hostname()
	p.UptimeSeconds = readUptime()
	p.Uptime = formatDuration(p.UptimeSeconds)
	p.CPU = collectCPU()
	p.Memory = collectMemory()
	p.Disk = collectDisk()
	p.Network = collectNetwork()
	p.Processes = countProcesses()
	p.LoadAverage = readLoadAvg()

	return p
}

func formatDuration(secs float64) string {
	d := time.Duration(secs) * time.Second
	days := int(d.Hours()) / 24
	hours := int(d.Hours()) % 24
	mins := int(d.Minutes()) % 60
	if days > 0 {
		return fmt.Sprintf("%dd %dh %dm", days, hours, mins)
	}
	return fmt.Sprintf("%dh %dm", hours, mins)
}

func formatBytes(b uint64) string {
	const (
		KB = 1024
		MB = KB * 1024
		GB = MB * 1024
		TB = GB * 1024
	)
	switch {
	case b >= TB:
		return fmt.Sprintf("%.2f TB", float64(b)/float64(TB))
	case b >= GB:
		return fmt.Sprintf("%.2f GB", float64(b)/float64(GB))
	case b >= MB:
		return fmt.Sprintf("%.2f MB", float64(b)/float64(MB))
	case b >= KB:
		return fmt.Sprintf("%.2f KB", float64(b)/float64(KB))
	default:
		return fmt.Sprintf("%d B", b)
	}
}

func round2(v float64) float64 {
	return float64(int(v*100)) / 100
}
