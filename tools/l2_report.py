#!/usr/bin/env python3
"""Join L2 per-frame traces and report validated latency/FPS metrics.

The worker trace contains CLOCK_MONOTONIC nanosecond timestamps.  The Python
AU log contains the same-host pipeline timestamps; no wireless sender timestamp
exists in the current USB/AU protocol.  `sender_ns` is therefore -1.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

INT_FIELDS = {
    "frame", "seq", "session", "au_flags", "au_bytes", "rot_mode",
    "source_fb", "presented_fb", "au_queue_depth", "input_inflight",
    "backlog", "seq_gaps", "t_pipeline_send_ns", "t_worker_recv_ns",
    "t_decoder_enqueue_ns", "t_decoder_dequeue_ns",
    "t_dmabuf_sync_begin_start_ns", "t_dmabuf_sync_begin_end_ns",
    "t_dmabuf_sync_end_start_ns", "t_dmabuf_sync_end_end_ns",
    "t_copy_start_ns", "t_copy_end_ns", "t_rotation_start_ns",
    "t_rotation_end_ns", "t_kms_submit_start_ns", "t_kms_submit_end_ns",
    "t_kms_flip_event_ns", "kms_flip_sequence", "kms_flip_tv_ns",
    "t_flip_slot_wait_start_ns", "t_flip_slot_wait_end_ns",
    "t_kms_prepare_start_ns", "t_kms_prepare_end_ns",
    "t_kms_commit_start_ns", "t_kms_commit_end_ns",
    "kms_commit_rc", "kms_ebusy", "pending_flip_depth",
    "dma_sync_supported", "flip_pending", "flip_matched",
}


def quantiles(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    ordered = sorted(values)

    def pick(q: float) -> float:
        idx = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
        return round(ordered[idx], 3)

    return {
        "n": len(ordered),
        "min": round(ordered[0], 3),
        "p50": pick(0.50),
        "p95": pick(0.95),
        "p99": pick(0.99),
        "max": round(ordered[-1], 3),
        "mean": round(statistics.fmean(ordered), 3),
    }


def read_trace(path: Path) -> tuple[list[dict], list[dict]]:
    present: list[dict] = []
    flip: list[dict] = []
    if not path.exists():
        return present, flip
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            kind = row.get("kind")
            if kind not in {"present", "flip"}:
                continue
            parsed: dict = {"kind": kind}
            for key, value in row.items():
                if key == "kind":
                    continue
                try:
                    parsed[key] = int(value) if key in INT_FIELDS else float(value)
                except (TypeError, ValueError):
                    parsed[key] = None
            (present if kind == "present" else flip).append(parsed)
    return present, flip


def read_python_au(path: Path) -> dict[int, dict]:
    rows: dict[int, dict] = {}
    if not path.exists():
        return rows
    with path.open(newline="") as fh:
        for row in csv.reader(fh, delimiter="\t"):
            if not row or row[0] != "au":
                continue
            try:
                seq = int(row[1])
                rows[seq] = {
                    "pipeline_enqueue_ns": int(row[2]),
                    "au_complete_ns": int(row[3]),
                    "flags": int(row[4]),
                    "bytes": int(row[5]),
                    "usb_receive_ns": int(row[6]) if len(row) > 6 else -1,
                    "au_start_ns": int(row[7]) if len(row) > 7 else -1,
                    "sender_ns": int(row[8]) if len(row) > 8 else -1,
                }
            except (IndexError, ValueError):
                continue
    return rows


def read_sys(path: Path) -> dict:
    if not path.exists():
        return {}
    rows: list[dict] = []
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                rows.append(
                    {
                        "t_mono": float(row["t_mono"]),
                        "cpu_busy_pct": float(row["cpu_busy_pct"]),
                        "cpu_iowait_pct": float(row["cpu_iowait_pct"]),
                        "load1": float(row["load1"]),
                        "py_rss_kb": int(row.get("py_rss_kb") or -1),
                        "wk_utime_ms": int(row["wk_utime_ms"]),
                        "wk_stime_ms": int(row["wk_stime_ms"]),
                        "wk_threads": int(row["wk_threads"]),
                        "wk_rss_kb": int(row.get("wk_rss_kb") or -1),
                        "mem_avail_kb": int(row["mem_avail_kb"]),
                        "temp_mc": int(row["temp_mc"]),
                        "irq_vdec": int(row["irq_vdec"]),
                        "irq_esparser": int(row["irq_esparser"]),
                        "irq_xhci": int(row["irq_xhci"]),
                        "cpu_freq_khz": int(row.get("cpu_freq_khz") or -1),
                        "cpu_max_freq_khz": int(row.get("cpu_max_freq_khz") or -1),
                    }
                )
            except (KeyError, ValueError):
                continue
    if not rows:
        return {}

    def col(name: str) -> list[float]:
        return [float(r[name]) for r in rows if r.get(name) is not None]

    worker_cpu = [
        r["wk_utime_ms"] + r["wk_stime_ms"]
        for r in rows
        if r["wk_utime_ms"] >= 0 and r["wk_stime_ms"] >= 0
    ]
    span_s = max(0.0, rows[-1]["t_mono"] - rows[0]["t_mono"])
    cpu_span_ms = (max(worker_cpu) - min(worker_cpu)) if len(worker_cpu) >= 2 else 0
    freq_rows = [r for r in rows if r["cpu_freq_khz"] > 0 and r["cpu_max_freq_khz"] > 0]
    throttled = [r for r in freq_rows if r["cpu_freq_khz"] < r["cpu_max_freq_khz"]]
    return {
        "samples": len(rows),
        "span_s": round(span_s, 3),
        "cpu_busy_pct": quantiles(col("cpu_busy_pct")),
        "cpu_iowait_pct": quantiles(col("cpu_iowait_pct")),
        "load1": quantiles(col("load1")),
        "worker_cpu_ms_delta_max": cpu_span_ms,
        "worker_cpu_pct_avg": round(100.0 * cpu_span_ms / (span_s * 1000.0), 2)
        if span_s > 0 else None,
        "py_rss_kb": quantiles([float(r["py_rss_kb"]) for r in rows if r["py_rss_kb"] > 0]),
        "worker_rss_kb": quantiles([float(r["wk_rss_kb"]) for r in rows if r["wk_rss_kb"] > 0]),
        "mem_avail_kb_min": min((r["mem_avail_kb"] for r in rows), default=-1),
        "temp_mc_max": max((r["temp_mc"] for r in rows), default=-1),
        "irq_vdec_delta": max((r["irq_vdec"] for r in rows), default=-1)
        - min((r["irq_vdec"] for r in rows), default=-1),
        "irq_esparser_delta": max((r["irq_esparser"] for r in rows), default=-1)
        - min((r["irq_esparser"] for r in rows), default=-1),
        "irq_xhci_delta": max((r["irq_xhci"] for r in rows), default=-1)
        - min((r["irq_xhci"] for r in rows), default=-1),
        "cpu_freq_khz": quantiles([float(r["cpu_freq_khz"]) for r in freq_rows]),
        "cpu_max_freq_khz": max((r["cpu_max_freq_khz"] for r in freq_rows), default=-1),
        "cpu_below_max_samples": len(throttled),
    }


def read_worker_log(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(errors="replace")
    stats: dict = {}
    ebusy_total = 0
    ebusy_max = 0
    pending_max = 0
    timing_lines = 0
    for line in text.splitlines():
        m = re.search(
            r"aus_frames=(\d+) corrupt=(\d+) oversize=(\d+) eos=(\d+) "
            r"sessions=(\d+) ([0-9.]+) fps",
            line,
        )
        if m:
            stats.update(
                aus_frames=int(m.group(1)),
                corrupt_frames=int(m.group(2)),
                oversize=int(m.group(3)),
                eos=int(m.group(4)),
                sessions=int(m.group(5)),
                worker_reported_fps=float(m.group(6)),
            )
        m = re.search(
            r"DECODED frames=(\d+) corrupt=(\d+) oversize=(\d+) "
            r"sessions=(\d+) seq_gaps=(\d+) gated=(\d+) "
            r"wall=([0-9.]+)s fps=([0-9.]+)",
            line,
        )
        if m:
            stats.update(
                decoded_frames=int(m.group(1)),
                decoded_corrupt=int(m.group(2)),
                decoded_oversize=int(m.group(3)),
                decoded_sessions=int(m.group(4)),
                decoded_seq_gaps=int(m.group(5)),
                decoded_gated=int(m.group(6)),
                decoded_wall_s=float(m.group(7)),
                decoded_fps=float(m.group(8)),
            )
        m = re.search(
            r"worker_timing .*?trace_present=(\d+) trace_flip=(\d+) "
            r"flip_unmatched=(\d+) flip_mismatch=(\d+) dmabuf_sync=(-?\d+)",
            line,
        )
        if m:
            stats.update(
                worker_trace_present=int(m.group(1)),
                worker_trace_flip=int(m.group(2)),
                worker_flip_unmatched=int(m.group(3)),
                worker_flip_mismatch=int(m.group(4)),
                worker_dmabuf_sync=int(m.group(5)),
            )
        m = re.search(
            r"kms_prepare_avg_ms=([0-9.]+) kms_commit_avg_ms=([0-9.]+) "
            r"kms_ebusy=(\d+) pending_max=(\d+)",
            line,
        )
        if m:
            timing_lines += 1
            ebusy = int(m.group(3))
            pending = int(m.group(4))
            ebusy_total += ebusy
            ebusy_max = max(ebusy_max, ebusy)
            pending_max = max(pending_max, pending)
            stats.update(
                kms_prepare_avg_ms=float(m.group(1)),
                kms_commit_avg_ms=float(m.group(2)),
                kms_ebusy_count=ebusy_total,
                kms_ebusy_per_second_max=ebusy_max,
                pending_flip_max=pending_max,
            )
        m = re.search(r"STOPPING rc=(-?\d+)", line)
        if m:
            stats["worker_stop_rc"] = int(m.group(1))
    stats["status_0xf_count"] = text.count("status=0xf")
    stats["abort_count"] = text.count("Aborting decoding session")
    stats["flip_timeout_count"] = text.count("DRM flip wait timeout")
    stats["atomic_fallback_count"] = text.count("falling back to legacy SETPLANE")
    stats["dma_sync_unsupported_count"] = text.count("DMA_BUF_IOCTL_SYNC unsupported")
    stats["worker_timing_lines"] = timing_lines
    return stats


def read_replay_log(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(errors="replace")
    stats: dict = {}
    m = re.search(r"file=.*? aus=(\d+) rate=([0-9.]+)", text)
    if m:
        stats["source_aus"] = int(m.group(1))
        stats["requested_rate"] = float(m.group(2))
    m = re.search(
        r"SENT=(\d+) DROPPED=(\d+) RECOVERIES=(\d+) BYTES=(\d+) "
        r"WALL=([0-9.]+)s FPS=([0-9.]+)",
        text,
    )
    if m:
        stats.update(
            sent=int(m.group(1)),
            dropped=int(m.group(2)),
            recoveries=int(m.group(3)),
            bytes_sent=int(m.group(4)),
            wall_s=float(m.group(5)),
            source_fps=float(m.group(6)),
        )
    return stats


def read_rc(path: Path) -> int | None:
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def dmesg_counts(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(errors="replace")
    patterns = {
        "status_0xf": "status=0xf",
        "aborting_session": "Aborting decoding session",
        "hevc_lcu_check": "HEVC_LCU_CHECK",
        "source_change": "SOURCE_CHANGE",
        "pollerr": "POLLERR",
        "eio": "EIO",
        "no_dst_buffer": "No dst buffer",
    }
    return {key: text.count(pattern) for key, pattern in patterns.items()}


def dmesg_delta(before: dict, after: dict) -> dict:
    if not after:
        return {}
    out: dict = {}
    wrapped = False
    for key, value in after.items():
        delta = value - before.get(key, 0)
        if delta < 0:
            wrapped = True
            delta = 0
        out[key] = delta
    out["ring_buffer_wrapped_or_rotated"] = wrapped
    return out


def delta_ms(later: int | None, earlier: int | None) -> float | None:
    if later is None or earlier is None or later < 0 or earlier < 0:
        return None
    return (later - earlier) / 1e6


def span_fps(times: list[int]) -> float | None:
    if len(times) < 2:
        return None
    ordered = sorted(times)
    span_s = (ordered[-1] - ordered[0]) / 1e9
    return round((len(ordered) - 1) / span_s, 2) if span_s > 0 else None


def median_interval_fps(times: list[int]) -> float | None:
    if len(times) < 2:
        return None
    ordered = sorted(times)
    gaps = [b - a for a, b in zip(ordered, ordered[1:]) if b > a]
    if not gaps:
        return None
    return round(1e9 / statistics.median(gaps), 2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--trace", default="trace.csv")
    ap.add_argument("--py-csv", default="latency_python.csv")
    ap.add_argument("--sys-csv", default="sys.csv")
    ap.add_argument("--worker-log", default="worker.log")
    ap.add_argument("--replay-log", default="replay.log")
    ap.add_argument("--worker-rc", default="worker.rc")
    ap.add_argument("--replay-rc", default="replay.rc")
    ap.add_argument("--dmesg-before", default="dmesg_before.txt")
    ap.add_argument("--dmesg-after", default="dmesg_after.txt")
    ap.add_argument("--warmup-s", type=float, default=5.0)
    ap.add_argument("--json-out", default="l2_summary.json")
    args = ap.parse_args()

    run = Path(args.run_dir)
    present_rows, flip_rows = read_trace(run / args.trace)
    py_rows = read_python_au(run / args.py_csv)
    sys_stats = read_sys(run / args.sys_csv)
    worker_stats = read_worker_log(run / args.worker_log)
    replay_stats = read_replay_log(run / args.replay_log)
    worker_stats["process_rc"] = read_rc(run / args.worker_rc)
    replay_stats["process_rc"] = read_rc(run / args.replay_rc)
    dmesg = dmesg_delta(
        dmesg_counts(run / args.dmesg_before),
        dmesg_counts(run / args.dmesg_after),
    )

    present_by_seq = {int(r["seq"]): r for r in present_rows if r.get("seq") is not None}
    flip_by_seq = {int(r["seq"]): r for r in flip_rows if r.get("seq") is not None}
    present_times = sorted(
        int(r["t_kms_submit_end_ns"]) for r in present_rows
        if r.get("t_kms_submit_end_ns") is not None and r["t_kms_submit_end_ns"] > 0
    )
    t0 = present_times[0] if present_times else 0
    cutoff = t0 + int(args.warmup_s * 1e9)

    metrics: dict[str, list[float]] = defaultdict(list)
    eligible_present: list[dict] = []
    matched_flips: list[dict] = []
    skipped_total = 0
    max_seq_gap = 0
    max_au_queue = 0
    max_input_inflight = 0
    max_backlog = 0
    dma_sync_unsupported = 0
    flip_mismatch = 0
    flip_missing = 0
    flip_pending = 0
    kms_ebusy_present_rows = 0
    max_pending_flip_depth = 0

    for seq, p in sorted(present_by_seq.items(), key=lambda kv: kv[1].get("t_kms_submit_end_ns") or 0):
        submit_end = p.get("t_kms_submit_end_ns")
        if submit_end is None or submit_end < cutoff:
            continue
        eligible_present.append(p)
        skipped_total += max(0, int(p.get("backlog") or 0))
        max_seq_gap = max(max_seq_gap, int(p.get("seq_gaps") or 0))
        max_au_queue = max(max_au_queue, int(p.get("au_queue_depth") or 0))
        max_input_inflight = max(max_input_inflight, int(p.get("input_inflight") or 0))
        max_backlog = max(max_backlog, int(p.get("backlog") or 0))
        max_pending_flip_depth = max(max_pending_flip_depth, int(p.get("pending_flip_depth") or 0))
        kms_ebusy_present_rows += 1 if p.get("kms_ebusy") else 0
        if p.get("dma_sync_supported") == 0:
            dma_sync_unsupported += 1

        f = flip_by_seq.get(seq)
        if f is None or not f.get("flip_matched"):
            flip_missing += 1
            if p.get("flip_pending"):
                flip_pending += 1
            if f is not None:
                flip_mismatch += 1
            continue
        matched_flips.append(f)

        dequeue = p.get("t_decoder_dequeue_ns")
        submit_start = p.get("t_kms_submit_start_ns")
        submit_end = p.get("t_kms_submit_end_ns")
        flip_event = f.get("t_kms_flip_event_ns")
        flip_tv = f.get("kms_flip_tv_ns")
        enqueue = p.get("t_decoder_enqueue_ns")
        worker_recv = p.get("t_worker_recv_ns")
        pipeline_send = p.get("t_pipeline_send_ns")
        sync_begin_start = p.get("t_dmabuf_sync_begin_start_ns")
        sync_begin_end = p.get("t_dmabuf_sync_begin_end_ns")
        sync_end_start = p.get("t_dmabuf_sync_end_start_ns")
        sync_end_end = p.get("t_dmabuf_sync_end_end_ns")
        copy_start = p.get("t_copy_start_ns")
        copy_end = p.get("t_copy_end_ns")
        rotation_start = p.get("t_rotation_start_ns")
        rotation_end = p.get("t_rotation_end_ns")
        fused_start = copy_start if copy_start and copy_start > 0 else sync_begin_end
        fused_plus_sync_start = sync_begin_start if sync_begin_start and sync_begin_start > 0 else fused_start

        for key, value in (
            ("pipeline_send_to_worker_recv_ms", delta_ms(worker_recv, pipeline_send)),
            ("worker_recv_to_enqueue_ms", delta_ms(enqueue, worker_recv)),
            ("worker_recv_to_dequeue_ms", delta_ms(dequeue, worker_recv)),
            ("enqueue_to_dequeue_ms", delta_ms(dequeue, enqueue)),
            ("pipeline_send_to_dequeue_ms", delta_ms(dequeue, pipeline_send)),
            ("dequeue_to_sync_start_ms", delta_ms(sync_begin_start, dequeue)),
            ("dmabuf_sync_begin_ms", delta_ms(sync_begin_end, sync_begin_start)),
            ("copy_ms", delta_ms(copy_end, copy_start)),
            ("rotation_ms", delta_ms(rotation_end, rotation_start)),
            ("dmabuf_sync_end_ms", delta_ms(sync_end_end, sync_end_start)),
            ("dequeue_to_submit_ms", delta_ms(submit_start, dequeue)),
            ("pipeline_send_to_submit_ms", delta_ms(submit_start, pipeline_send)),
            ("kms_submit_ms", delta_ms(submit_end, submit_start)),
            ("submit_to_flip_ms", delta_ms(flip_event, submit_end)),
            ("submit_start_to_flip_ms", delta_ms(flip_event, submit_start)),
            ("pipeline_send_to_flip_ms", delta_ms(flip_event, pipeline_send)),
            ("flip_event_tv_delta_ms", delta_ms(flip_event, f.get("kms_flip_tv_ns"))),
            ("submit_end_to_flip_tv_ms", delta_ms(flip_tv, submit_end)),
            ("submit_start_to_flip_tv_ms", delta_ms(flip_tv, submit_start)),
            ("pipeline_send_to_flip_tv_ms", delta_ms(flip_tv, pipeline_send)),
            ("fused_transform_ms", delta_ms(rotation_end, fused_start)),
            ("fused_transform_plus_sync_ms", delta_ms(rotation_end, fused_plus_sync_start)),
            ("flip_slot_wait_ms", delta_ms(p.get("t_flip_slot_wait_end_ns"), p.get("t_flip_slot_wait_start_ns"))),
            ("kms_prepare_ms", delta_ms(p.get("t_kms_prepare_end_ns"), p.get("t_kms_prepare_start_ns"))),
            ("kms_commit_ms", delta_ms(p.get("t_kms_commit_end_ns"), p.get("t_kms_commit_start_ns"))),
        ):
            if value is not None:
                metrics[key].append(value)

        py = py_rows.get(seq)
        if py:
            for key, value in (
                ("au_assembly_ms", delta_ms(py["au_complete_ns"], py["usb_receive_ns"])),
                ("au_complete_to_enqueue_ms", delta_ms(enqueue, py["au_complete_ns"])),
                ("au_complete_to_flip_ms", delta_ms(flip_event, py["au_complete_ns"])),
                ("usb_receive_to_flip_ms", delta_ms(flip_event, py["usb_receive_ns"])),
                ("au_complete_to_flip_tv_ms", delta_ms(flip_tv, py["au_complete_ns"])),
                ("usb_receive_to_flip_tv_ms", delta_ms(flip_tv, py["usb_receive_ns"])),
            ):
                if value is not None:
                    metrics[key].append(value)

    source_times = sorted(
        int(r["t_pipeline_send_ns"]) for r in eligible_present
        if r.get("t_pipeline_send_ns") is not None and r["t_pipeline_send_ns"] > 0
    )
    decoded_times = sorted(
        int(r["t_decoder_dequeue_ns"]) for r in eligible_present
        if r.get("t_decoder_dequeue_ns") is not None and r["t_decoder_dequeue_ns"] > 0
    )
    submitted_times = sorted(
        int(r["t_kms_submit_end_ns"]) for r in eligible_present
        if r.get("t_kms_submit_end_ns") is not None and r["t_kms_submit_end_ns"] > 0
    )
    flip_times = sorted(
        int(r["t_kms_flip_event_ns"]) for r in matched_flips
        if r.get("t_kms_flip_event_ns") is not None and r["t_kms_flip_event_ns"] > 0
    )
    flip_tv_times = sorted(
        int(r["kms_flip_tv_ns"]) for r in matched_flips
        if r.get("kms_flip_tv_ns") is not None and r["kms_flip_tv_ns"] > 0
    )

    result = {
        "trace_rows": {"present": len(present_rows), "flip": len(flip_rows)},
        "warmup_s": args.warmup_s,
        "eligible_present": len(eligible_present),
        "matched_flips": len(matched_flips),
        "flip_missing_or_mismatch": flip_missing,
        "flip_mismatch": flip_mismatch,
        "flip_pending_at_end": flip_pending,
        "kms_ebusy_present_rows": kms_ebusy_present_rows,
        "max_pending_flip_depth": max_pending_flip_depth,
        "dma_sync_unsupported_present_rows": dma_sync_unsupported,
        "dropped_or_replaced_frames": skipped_total,
        "max_seq_gaps": max_seq_gap,
        "queue": {
            "max_au_queue_depth": max_au_queue,
            "max_input_inflight": max_input_inflight,
            "max_replaced_backlog": max_backlog,
        },
        "fps": {
            "source_replay": replay_stats.get("source_fps"),
            "source_au_median": median_interval_fps(source_times),
            "decoded_worker": worker_stats.get("decoded_fps"),
            "decoded_present": span_fps(decoded_times),
            "submitted": span_fps(submitted_times),
            "completed_flip_event_read": span_fps(flip_times),
            "completed_flip_tv": span_fps(flip_tv_times),
        },
        "latency_ms": {key: quantiles(values) for key, values in sorted(metrics.items())},
        "clock_domain": {
            "pipeline_au_timestamp": "CLOCK_MONOTONIC on the same CM311 host (Python time.monotonic_ns)",
            "worker_timestamps": "CLOCK_MONOTONIC (C clock_gettime(CLOCK_MONOTONIC))",
            "kms_event_tv": "DRM event tv_sec/tv_usec; compare with flip_event_tv_delta_ms",
            "sender_au_timestamp": "unavailable in the current USB/AU protocol; Python log writes -1",
        },
        "worker": worker_stats,
        "replay": replay_stats,
        "dmesg": dmesg,
        "system": sys_stats,
    }
    out = run / args.json_out
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
