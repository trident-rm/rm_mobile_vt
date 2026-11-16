#!/usr/bin/env python3
"""Aggregate multiple L2 benchmark runs into pooled per-frame statistics.

Each run keeps its own CLOCK_MONOTONIC domain.  Warm-up is applied per run;
latency values are pooled only after that filtering.  FPS is reported per run
and summarized, never by mixing timestamps from different runs.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import l2_report as lr  # noqa: E402


def read_sys_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                rows.append(
                    {
                        "t_mono": float(row["t_mono"]),
                        "cpu_busy_pct": float(row["cpu_busy_pct"]),
                        "cpu_iowait_pct": float(row["cpu_iowait_pct"]),
                        "load1": float(row["load1"]),
                        "wk_utime_ms": int(row["wk_utime_ms"]),
                        "wk_stime_ms": int(row["wk_stime_ms"]),
                        "mem_avail_kb": int(row["mem_avail_kb"]),
                        "temp_mc": int(row["temp_mc"]),
                    }
                )
            except (KeyError, ValueError):
                continue
    return rows


def summarize(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "min": round(ordered[0], 3),
        "median": round(statistics.median(ordered), 3),
        "max": round(ordered[-1], 3),
        "mean": round(statistics.fmean(ordered), 3),
    }


def discover_groups(root: Path) -> dict[tuple[str, str], list[Path]]:
    groups: dict[tuple[str, str], list[Path]] = {}
    hold_match = re.search(r"hold(?P<hold>\d+)", root.name)
    direct_hold = hold_match.group("hold") if hold_match else "2"
    direct_runs: dict[tuple[str, str], list[Path]] = defaultdict(list)
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        run_match = re.fullmatch(r"mode_(?P<mode>[A-Za-z0-9]+)_r(?P<rep>\d+)", child.name)
        if run_match:
            direct_runs[(run_match.group("mode"), direct_hold)].append(child)
            continue
        group_match = re.fullmatch(
            r"mode_(?P<mode>[A-Za-z0-9]+)_hold(?P<hold>\d+)", child.name
        )
        if not group_match:
            continue
        mode = group_match.group("mode")
        hold = group_match.group("hold")
        runs = sorted(p for p in child.glob(f"mode_{mode}_r*") if p.is_dir())
        if runs:
            groups[(mode, hold)] = runs
    for key, runs in direct_runs.items():
        groups.setdefault(key, []).extend(runs)
        groups[key].sort()
    return groups


def analyze_run(run: Path, warmup_s: float) -> dict:
    present_rows, flip_rows = lr.read_trace(run / "trace.csv")
    py_rows = lr.read_python_au(run / "latency_python.csv")
    worker = lr.read_worker_log(run / "worker.log")
    replay = lr.read_replay_log(run / "replay.log")
    worker["process_rc"] = lr.read_rc(run / "worker.rc")
    replay["process_rc"] = lr.read_rc(run / "replay.rc")
    dmesg = lr.dmesg_delta(
        lr.dmesg_counts(run / "dmesg_before.txt"),
        lr.dmesg_counts(run / "dmesg_after.txt"),
    )
    sys_stats = lr.read_sys(run / "sys.csv")
    sys_rows = read_sys_rows(run / "sys.csv")

    present_by_seq = {int(r["seq"]): r for r in present_rows if r.get("seq") is not None}
    flip_by_seq = {int(r["seq"]): r for r in flip_rows if r.get("seq") is not None}
    present_times = sorted(
        int(r["t_kms_submit_end_ns"]) for r in present_rows
        if r.get("t_kms_submit_end_ns") is not None and r["t_kms_submit_end_ns"] > 0
    )
    t0 = present_times[0] if present_times else 0
    cutoff = t0 + int(warmup_s * 1e9)

    metrics: dict[str, list[float]] = defaultdict(list)
    eligible_present: list[dict] = []
    matched_flips: list[dict] = []
    flip_missing = 0
    flip_mismatch = 0
    flip_pending = 0
    dma_sync_unsupported = 0
    skipped_total = 0
    max_seq_gap = 0
    max_au_queue = 0
    max_input_inflight = 0
    max_backlog = 0

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
            ("pipeline_send_to_worker_recv_ms", lr.delta_ms(worker_recv, pipeline_send)),
            ("worker_recv_to_enqueue_ms", lr.delta_ms(enqueue, worker_recv)),
            ("worker_recv_to_dequeue_ms", lr.delta_ms(dequeue, worker_recv)),
            ("enqueue_to_dequeue_ms", lr.delta_ms(dequeue, enqueue)),
            ("pipeline_send_to_dequeue_ms", lr.delta_ms(dequeue, pipeline_send)),
            ("dequeue_to_sync_start_ms", lr.delta_ms(sync_begin_start, dequeue)),
            ("dmabuf_sync_begin_ms", lr.delta_ms(sync_begin_end, sync_begin_start)),
            ("copy_ms", lr.delta_ms(copy_end, copy_start)),
            ("rotation_ms", lr.delta_ms(rotation_end, rotation_start)),
            ("fused_transform_ms", lr.delta_ms(rotation_end, fused_start)),
            ("fused_transform_plus_sync_ms", lr.delta_ms(rotation_end, fused_plus_sync_start)),
            ("dmabuf_sync_end_ms", lr.delta_ms(sync_end_end, sync_end_start)),
            ("dequeue_to_submit_ms", lr.delta_ms(submit_start, dequeue)),
            ("pipeline_send_to_submit_ms", lr.delta_ms(submit_start, pipeline_send)),
            ("kms_submit_ms", lr.delta_ms(submit_end, submit_start)),
            ("submit_to_flip_ms", lr.delta_ms(flip_event, submit_end)),
            ("submit_start_to_flip_ms", lr.delta_ms(flip_event, submit_start)),
            ("pipeline_send_to_flip_ms", lr.delta_ms(flip_event, pipeline_send)),
            ("flip_event_tv_delta_ms", lr.delta_ms(flip_event, flip_tv)),
            ("submit_end_to_flip_tv_ms", lr.delta_ms(flip_tv, submit_end)),
            ("submit_start_to_flip_tv_ms", lr.delta_ms(flip_tv, submit_start)),
            ("pipeline_send_to_flip_tv_ms", lr.delta_ms(flip_tv, pipeline_send)),
            ("au_queue_depth", p.get("au_queue_depth")),
            ("input_inflight", p.get("input_inflight")),
            ("backlog", p.get("backlog")),
        ):
            if value is not None:
                metrics[key].append(float(value))

        py = py_rows.get(seq)
        if py:
            for key, value in (
                ("au_assembly_ms", lr.delta_ms(py["au_complete_ns"], py["usb_receive_ns"])),
                ("au_complete_to_enqueue_ms", lr.delta_ms(enqueue, py["au_complete_ns"])),
                ("au_complete_to_flip_ms", lr.delta_ms(flip_event, py["au_complete_ns"])),
                ("usb_receive_to_flip_ms", lr.delta_ms(flip_event, py["usb_receive_ns"])),
                ("au_complete_to_flip_tv_ms", lr.delta_ms(flip_tv, py["au_complete_ns"])),
                ("usb_receive_to_flip_tv_ms", lr.delta_ms(flip_tv, py["usb_receive_ns"])),
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

    return {
        "run": run.name,
        "warmup_s": warmup_s,
        "eligible_present": len(eligible_present),
        "matched_flips": len(matched_flips),
        "flip_missing_or_mismatch": flip_missing,
        "flip_mismatch": flip_mismatch,
        "flip_pending_at_end": flip_pending,
        "dma_sync_unsupported_present_rows": dma_sync_unsupported,
        "dropped_or_replaced_frames": skipped_total,
        "max_seq_gaps": max_seq_gap,
        "queue": {
            "max_au_queue_depth": max_au_queue,
            "max_input_inflight": max_input_inflight,
            "max_replaced_backlog": max_backlog,
        },
        "fps": {
            "source_replay": replay.get("source_fps"),
            "source_au_median": lr.median_interval_fps(source_times),
            "decoded_worker": worker.get("decoded_fps"),
            "decoded_present": lr.span_fps(decoded_times),
            "submitted": lr.span_fps(submitted_times),
            "completed_flip_event_read": lr.span_fps(flip_times),
            "completed_flip_tv": lr.span_fps(flip_tv_times),
        },
        "metrics": dict(metrics),
        "worker": worker,
        "replay": replay,
        "dmesg": dmesg,
        "system": sys_stats,
        "system_rows": sys_rows,
    }


def aggregate_group(runs: list[Path], warmup_s: float, mode: str) -> dict:
    analyses = [analyze_run(run, warmup_s) for run in runs]
    pooled_metrics: dict[str, list[float]] = defaultdict(list)
    for analysis in analyses:
        for key, values in analysis["metrics"].items():
            pooled_metrics[key].extend(values)

    fps_keys = (
        "source_replay", "source_au_median", "decoded_worker", "decoded_present",
        "submitted", "completed_flip_event_read", "completed_flip_tv",
    )
    fps_summary = {
        key: summarize([
            float(analysis["fps"][key]) for analysis in analyses
            if analysis["fps"].get(key) is not None
        ])
        for key in fps_keys
    }

    worker_sessions = [int(a["worker"].get("decoded_sessions") or 0) for a in analyses]
    worker_fps = [float(a["worker"]["decoded_fps"]) for a in analyses if a["worker"].get("decoded_fps") is not None]
    replay_fps = [float(a["replay"]["source_fps"]) for a in analyses if a["replay"].get("source_fps") is not None]
    flip_fps = [float(a["fps"]["completed_flip_tv"]) for a in analyses if a["fps"].get("completed_flip_tv") is not None]

    cpu_busy = [r["cpu_busy_pct"] for a in analyses for r in a["system_rows"]]
    cpu_iowait = [r["cpu_iowait_pct"] for a in analyses for r in a["system_rows"]]
    temps = [r["temp_mc"] for a in analyses for r in a["system_rows"] if r["temp_mc"] >= 0]
    mem_avail = [r["mem_avail_kb"] for a in analyses for r in a["system_rows"] if r["mem_avail_kb"] >= 0]

    worker_cpu_pct: list[float] = []
    for analysis in analyses:
        rows = analysis["system_rows"]
        ticks = [r["wk_utime_ms"] + r["wk_stime_ms"] for r in rows if r["wk_utime_ms"] >= 0 and r["wk_stime_ms"] >= 0]
        if len(ticks) >= 2 and len(rows) >= 2:
            span_ms = (rows[-1]["t_mono"] - rows[0]["t_mono"]) * 1000.0
            delta_ms = max(ticks) - min(ticks)
            if span_ms > 0 and delta_ms > 0:
                worker_cpu_pct.append(100.0 * delta_ms / span_ms)

    irq_deltas = {
        key: [int(a["system"].get(key) or 0) for a in analyses]
        for key in ("irq_vdec_delta", "irq_esparser_delta", "irq_xhci_delta")
    }

    frame_mb = 1920 * 1080 * 1.5 / 1e6
    passes = 4 if mode == "A" else 2
    flip_fps_mean = statistics.fmean(flip_fps) if flip_fps else 0.0
    bandwidth = {
        "frame_nv12_mb": round(frame_mb, 4),
        "logical_cpu_nv12_passes_per_frame": passes,
        "source_read_mb_s": round(frame_mb * flip_fps_mean, 2),
        "scratch_write_mb_s": round(frame_mb * flip_fps_mean, 2),
        "logical_cpu_nv12_mb_s": round(frame_mb * flip_fps_mean * passes, 2),
        "note": "Derived logical NV12 traffic from completed-flip FPS; not a DRAM-controller measurement.",
    }

    return {
        "runs": [a["run"] for a in analyses],
        "run_count": len(analyses),
        "per_run": analyses,
        "pooled_latency_ms": {key: lr.quantiles(values) for key, values in sorted(pooled_metrics.items())},
        "fps_summary": fps_summary,
        "worker": {
            "decoded_frames_sum": sum(int(a["worker"].get("decoded_frames") or 0) for a in analyses),
            "decoded_corrupt_sum": sum(int(a["worker"].get("decoded_corrupt") or 0) for a in analyses),
            "decoded_oversize_sum": sum(int(a["worker"].get("decoded_oversize") or 0) for a in analyses),
            "decoded_sessions_max": max(worker_sessions) if worker_sessions else 0,
            "decoded_sessions_sum": sum(worker_sessions),
            "status_0xf_sum": sum(int(a["worker"].get("status_0xf_count") or 0) for a in analyses),
            "abort_sum": sum(int(a["worker"].get("abort_count") or 0) for a in analyses),
            "flip_unmatched_sum": sum(int(a["worker"].get("worker_flip_unmatched") or 0) for a in analyses),
            "flip_mismatch_sum": sum(int(a["worker"].get("worker_flip_mismatch") or 0) for a in analyses),
            "flip_timeout_sum": sum(int(a["worker"].get("flip_timeout_count") or 0) for a in analyses),
            "atomic_fallback_sum": sum(int(a["worker"].get("atomic_fallback_count") or 0) for a in analyses),
            "dma_sync_unsupported_sum": sum(int(a["worker"].get("dma_sync_unsupported_count") or 0) for a in analyses),
            "decoded_fps": summarize(worker_fps),
            "process_rc_values": sorted({a["worker"].get("process_rc") for a in analyses}, key=lambda x: (x is None, x)),
        },
        "replay": {
            "sent_sum": sum(int(a["replay"].get("sent") or 0) for a in analyses),
            "dropped_sum": sum(int(a["replay"].get("dropped") or 0) for a in analyses),
            "recoveries_sum": sum(int(a["replay"].get("recoveries") or 0) for a in analyses),
            "source_fps": summarize(replay_fps),
            "process_rc_values": sorted({a["replay"].get("process_rc") for a in analyses}, key=lambda x: (x is None, x)),
        },
        "queue_max": {
            "max_au_queue_depth": max((a["queue"]["max_au_queue_depth"] for a in analyses), default=0),
            "max_input_inflight": max((a["queue"]["max_input_inflight"] for a in analyses), default=0),
            "max_replaced_backlog": max((a["queue"]["max_replaced_backlog"] for a in analyses), default=0),
        },
        "dmesg_sum": {
            key: sum(int(a["dmesg"].get(key) or 0) for a in analyses)
            for key in ("status_0xf", "aborting_session", "hevc_lcu_check", "source_change", "pollerr", "eio", "no_dst_buffer")
        },
        "system": {
            "cpu_busy_pct": lr.quantiles(cpu_busy),
            "cpu_iowait_pct": lr.quantiles(cpu_iowait),
            "temp_mc": lr.quantiles(temps),
            "mem_avail_kb": lr.quantiles(mem_avail),
            "worker_cpu_pct": summarize(worker_cpu_pct),
            "irq_deltas": {key: {"sum": sum(vals), "max": max(vals) if vals else 0} for key, vals in irq_deltas.items()},
        },
        "completed_flip_fps_mean": round(flip_fps_mean, 2),
        "logical_bandwidth": bandwidth,
        "fused_transform_p95_ms": lr.quantiles(pooled_metrics.get("fused_transform_ms", [])).get("p95"),
        "fused_transform_target_p95_ms": 12.0,
        "fused_transform_target_met": (
            lr.quantiles(pooled_metrics.get("fused_transform_ms", [])).get("p95", 9999.0) < 12.0
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--warmup-s", type=float, default=5.0)
    ap.add_argument("--json-out", default="")
    args = ap.parse_args()

    root = Path(args.root)
    groups = discover_groups(root)
    if not groups:
        print(f"no benchmark groups under {root}", file=sys.stderr)
        return 2

    output = {"root": str(root), "warmup_s": args.warmup_s, "groups": {}}
    for (mode, hold), runs in sorted(groups.items()):
        key = f"{mode}_hold{hold}"
        group = aggregate_group(runs, args.warmup_s, mode)
        output["groups"][key] = group
        lat = group["pooled_latency_ms"]
        fused = lat.get("fused_transform_ms", {})
        upstream = lat.get("pipeline_send_to_worker_recv_ms", {})
        enqueue = lat.get("enqueue_to_dequeue_ms", {})
        print(
            f"{key}: runs={group['run_count']} "
            f"flip_fps_mean={group['completed_flip_fps_mean']:.2f} "
            f"fused_p50={fused.get('p50')} fused_p95={fused.get('p95')} "
            f"replay_to_worker_p50={upstream.get('p50')} "
            f"enqueue_to_dequeue_p50={enqueue.get('p50')} "
            f"corrupt={group['worker']['decoded_corrupt_sum']} "
            f"0xf={group['worker']['status_0xf_sum']} "
            f"sessions_max={group['worker']['decoded_sessions_max']} "
            f"flip_unmatched={group['worker']['flip_unmatched_sum']}"
        )

    out = Path(args.json_out) if args.json_out else root / "l2_aggregate.json"
    out.write_text(json.dumps(output, indent=2) + "\n")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
