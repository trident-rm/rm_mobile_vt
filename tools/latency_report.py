#!/usr/bin/env python3
"""Join the Python AU log with the C worker's latency CSV (L1 measurement).

Both sides stamp CLOCK_MONOTONIC on the same host and share the AU `seq`, so
`present_ns - completed_ns` is the internal AU-complete-to-scanout latency.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

FRAME_MS = 1000.0 / 60.0


def quantiles(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    ordered = sorted(values)

    def pick(q: float) -> float:
        idx = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
        return round(ordered[idx], 2)

    return {
        "n": len(ordered),
        "min": round(ordered[0], 2),
        "p50": pick(0.50),
        "p95": pick(0.95),
        "p99": pick(0.99),
        "max": round(ordered[-1], 2),
        "mean": round(statistics.fmean(ordered), 2),
    }


def read_py_au(path: Path) -> dict[int, dict]:
    aus: dict[int, dict] = {}
    if not path.exists():
        return aus
    with path.open() as fh:
        for row in csv.reader(fh, delimiter="\t"):
            if not row or row[0] != "au":
                continue
            seq = int(row[1])
            aus[seq] = {
                "send_ns": int(row[2]),
                "completed_ns": int(row[3]),
                "flags": int(row[4]),
                "bytes": int(row[5]),
            }
    return aus


def read_worker(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open() as fh:
        for row in csv.DictReader(fh):
            try:
                rows.append(
                    {
                        "frame": int(row["frame"]),
                        "seq": int(row["seq"]),
                        "present_ns": int(row["present_mono_ns"]),
                        "age_ms": float(row["age_ms"]),
                        "decode_ms": float(row["decode_ms"]),
                        "wait_ms": float(row["wait_ms"]),
                        "backlog": int(row["backlog"]),
                        "session": int(row["session"]),
                    }
                )
            except (KeyError, ValueError):
                continue
    return rows


def parse_worker_log(path: Path) -> list[dict]:
    events: list[dict] = []
    if not path.exists():
        return events
    patterns = (
        re.compile(r"RECOVER first_frame t=(?P<t>[\d.]+) dt=(?P<dt>[\d.]+)(?: VISIBLE_GAP gap_ms=(?P<gap>[\d.]+))?"),
        re.compile(r"t=(?P<t>[\d.]+) session (?P<session>\d+) rebuilt after error; frames=(?P<frames>\d+)"),
        re.compile(r"RECOVER begin t=(?P<t>[\d.]+) \((?P<why>[^)]*)\) since_last_present_ms=(?P<since>-?[\d.]+)"),
    )
    for line in path.read_text(errors="replace").splitlines():
        for pat in patterns:
            m = pat.search(line)
            if m:
                events.append({"kind": line.split("(")[0][:40].strip(), **m.groupdict()})
                break
    return events


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--py-csv", default="latency_python.csv")
    ap.add_argument("--worker-csv", default="latency_worker.csv")
    ap.add_argument("--worker-log", default="stream.log")
    args = ap.parse_args()

    run = Path(args.run_dir)
    aus = read_py_au(run / args.py_csv)
    frames = read_worker(run / args.worker_csv)
    events = parse_worker_log(run / args.worker_log)

    internal_ms: list[float] = []
    send_ms: list[float] = []
    decode_ms: list[float] = []
    wait_ms: list[float] = []
    missing = 0
    for f in frames:
        send_ms.append(f["age_ms"])
        decode_ms.append(f["decode_ms"])
        wait_ms.append(f["wait_ms"])
        au = aus.get(f["seq"])
        if au is None:
            missing += 1
            continue
        internal_ms.append((f["present_ns"] - au["completed_ns"]) / 1e6)
        send_ms[-1] = (f["present_ns"] - au["send_ns"]) / 1e6

    buckets: dict[int, dict] = defaultdict(lambda: {"frames": 0, "ages": []})
    for f in frames:
        b = buckets[f["present_ns"] // 1_000_000_000]
        b["frames"] += 1
        if f["age_ms"] >= 0:
            b["ages"].append(f["age_ms"])
    t0 = min(buckets) if buckets else 0
    metrics_path = run / "metrics_1s.csv"
    with metrics_path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["second", "presented", "fps", "age_p50_ms", "age_p95_ms", "age_max_ms"])
        for sec in sorted(buckets):
            b = buckets[sec]
            ages = b["ages"]
            w.writerow(
                [
                    sec - t0,
                    b["frames"],
                    round(b["frames"], 2),
                    round(statistics.median(ages), 2) if ages else "",
                    round(sorted(ages)[int(0.95 * (len(ages) - 1))], 2) if ages else "",
                    round(max(ages), 2) if ages else "",
                ]
            )

    gaps = []
    ordered = sorted(f["present_ns"] for f in frames)
    for prev, cur in zip(ordered, ordered[1:]):
        gap = (cur - prev) / 1e6
        if gap > 2 * FRAME_MS:
            gaps.append({"start_ns": prev, "gap_ms": round(gap, 2)})
    with (run / "freeze_and_recovery.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["kind", "time", "value", "detail"])
        for g in gaps:
            w.writerow(["present_gap_ms", g["start_ns"], g["gap_ms"], ">2 frame periods"])
        for ev in events:
            w.writerow(["worker_event", ev.get("t", ""), ev.get("dt", ev.get("gap", "")), ev])

    result = {
        "frames_presented": len(frames),
        "au_rows": len(aus),
        "au_frames_without_python_row": missing,
        "session_rebuilds": len({f["session"] for f in frames}) - 1 if frames else 0,
        "internal_complete_to_present_ms": quantiles(internal_ms),
        "send_to_present_ms": quantiles(send_ms),
        "worker_decode_ms": quantiles(decode_ms),
        "worker_present_wait_ms": quantiles(wait_ms),
        "present_gap_over_2_frames": len(gaps),
        "visible_gaps_ms": [
            round(float(e["gap"]), 2) for e in events if e.get("gap") not in (None, "")
        ],
        "present_wait_gt_half_frame_frac": (
            round(sum(1 for v in wait_ms if v > FRAME_MS / 2) / len(wait_ms), 3)
            if wait_ms
            else None
        ),
    }
    (run / "latency_quantiles.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
