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
            "wk_utime_ms", "wk_stime_ms", "wk_threads",
            "mem_avail_kb", "temp_mc",
            "irq_vdec", "irq_esparser", "irq_xhci",
        ]
    )
    prev = cpu_totals()
    prev_py = proc_ticks(args.pid)
    prev_wk = proc_ticks(args.worker_pid) if args.worker_pid else (-1, -1, -1)
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
            wk = proc_ticks(args.worker_pid) if args.worker_pid else (-1, -1, -1)
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
                    -1 if wk[0] < 0 else wk[0] * 1000 // CLK,
                    -1 if wk[1] < 0 else wk[1] * 1000 // CLK,
                    wk[2],
                    mem_available_kb(),
                    temp_mc(),
                    *irq,
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
