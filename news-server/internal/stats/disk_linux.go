package stats

import "syscall"

func collectDisk() DiskStats {
	d := DiskStats{}
	var stat syscall.Statfs_t
	if err := syscall.Statfs("/", &stat); err != nil {
		return d
	}
	total := stat.Blocks * uint64(stat.Bsize)
	free := stat.Bfree * uint64(stat.Bsize)
	used := total - free

	d.Total = formatBytes(total)
	d.Used = formatBytes(used)
	if total > 0 {
		d.UsagePercent = round2(float64(used) / float64(total) * 100)
	}
	return d
}
