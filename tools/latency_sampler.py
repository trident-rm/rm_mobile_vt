#!/usr/bin/env python3
"""Low-overhead 1 Hz /proc sampler for the L1 live latency run (read-only)."""
from __future__ import annotations

import argparse
import csv
import os
import time
from pathlib import Path

CLK = os.sysconf("SC_CLK_TCK")


def cpu_totals() -> list[int]:
    parts = Path("/proc/stat").read_text().splitlines()[0].split()[1:]
    return [int(p) for p in parts]


def proc_ticks(pid: int) -> tuple[int, int, int]:
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()
        return int(fields[11]), int(fields[12]), int(fields[17])
    except (OSError, IndexError, ValueError):
        return (-1, -1, -1)


def proc_rss_kb(pid: int) -> int:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except (OSError, IndexError, ValueError):
        pass
    return -1


def resolve_worker_pid(pid: int) -> int:
    """The benchmark wraps the worker in timeout(1); sample its child."""
    try:
        children = Path(f"/proc/{pid}/task/{pid}/children").read_text().split()
        if children:
            return int(children[0])
    except (OSError, ValueError):
        pass
    return pid


def irq_counts() -> tuple[int, int, int]:
    totals = [0, 0, 0]
    try:
        for line in Path("/proc/interrupts").read_text().splitlines():
            if "vdec-mbox" in line:
                totals[0] += sum(int(x) for x in line.split()[1:] if x.isdigit())
            elif "esparserirq" in line:
                totals[1] += sum(int(x) for x in line.split()[1:] if x.isdigit())
            elif "xhci-hcd" in line:
                totals[2] += sum(int(x) for x in line.split()[1:] if x.isdigit())
    except OSError:
        pass
    return tuple(totals)


def mem_available_kb() -> int:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1])
    return -1


def temp_mc() -> int:
    try:
        return int(Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip())
    except (OSError, ValueError):
        return -1


def cpu_freq_khz(path: str) -> int:
    try:
        return int(Path(path).read_text().strip())
    except (OSError, ValueError):
        return -1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, required=True, help="pipeline python pid")
    ap.add_argument("--worker-pid", type=int, default=0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--interval", type=float, default=1.0)
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fh = out.open("w", newline="")
    writer = csv.writer(fh)
    writer.writerow(
        [
            "t_mono", "cpu_busy_pct", "cpu_iowait_pct", "load1",
            "py_utime_ms", "py_stime_ms", "py_threads",
            "py_rss_kb", "wk_utime_ms", "wk_stime_ms", "wk_threads", "wk_rss_kb",
            "mem_avail_kb", "temp_mc",
            "irq_vdec", "irq_esparser", "irq_xhci",
            "cpu_freq_khz", "cpu_max_freq_khz",
        ]
    )
    prev = cpu_totals()
    t0 = time.monotonic()
    try:
        while True:
            time.sleep(args.interval)
            cur = cpu_totals()
            delta = [max(0, c - p) for c, p in zip(cur, prev)]
            total = sum(delta) or 1
            busy = 100.0 * (total - delta[3] - delta[4]) / total
            iowait = 100.0 * delta[4] / total
            prev = cur
            py = proc_ticks(args.pid)
            wk = proc_ticks(resolve_worker_pid(args.worker_pid)) if args.worker_pid else (-1, -1, -1)
            irq = irq_counts()
            load1 = float(Path("/proc/loadavg").read_text().split()[0])
            writer.writerow(
                [
                    round(time.monotonic() - t0, 3),
                    round(busy, 1),
                    round(iowait, 1),
                    load1,
                    -1 if py[0] < 0 else py[0] * 1000 // CLK,
                    -1 if py[1] < 0 else py[1] * 1000 // CLK,
                    py[2],
                    proc_rss_kb(args.pid),
                    -1 if wk[0] < 0 else wk[0] * 1000 // CLK,
                    -1 if wk[1] < 0 else wk[1] * 1000 // CLK,
                    wk[2],
                    proc_rss_kb(resolve_worker_pid(args.worker_pid)) if args.worker_pid else -1,
                    mem_available_kb(),
                    temp_mc(),
                    *irq,
                    cpu_freq_khz("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"),
                    cpu_freq_khz("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq"),
                ]
            )
            fh.flush()
    except KeyboardInterrupt:
        pass
    finally:
        fh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
