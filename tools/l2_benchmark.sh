#!/bin/bash
# Offline L2 A/B/C benchmark: d3_replay -> d3_probe -> KMS, with per-frame trace.
# The caller must stop the production kiosk first (DRM master is exclusive).
set -euo pipefail

RUN_DIR=""
WORKER=""
SOURCE=""
DURATION=60
REPEATS=3
MODES="A B C"
SOURCE_HOLD=2
WARMUP=5
DUMP_ROT=0
DUMP_SOURCE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --run-dir) RUN_DIR="$2"; shift 2 ;;
    --worker) WORKER="$2"; shift 2 ;;
    --source) SOURCE="$2"; shift 2 ;;
    --duration) DURATION="$2"; shift 2 ;;
    --repeats) REPEATS="$2"; shift 2 ;;
    --modes) MODES="$2"; shift 2 ;;
    --source-hold) SOURCE_HOLD="$2"; shift 2 ;;
    --warmup) WARMUP="$2"; shift 2 ;;
    --dump-rot-frames) DUMP_ROT="$2"; shift 2 ;;
    --dump-source-frames) DUMP_SOURCE="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

[ -n "$RUN_DIR" ] && [ -n "$WORKER" ] && [ -n "$SOURCE" ] || {
  echo "usage: $0 --run-dir DIR --worker PATH --source PATH [--duration 60] [--repeats 3] [--modes 'A B C'] [--source-hold 2] [--dump-rot-frames N] [--dump-source-frames N]" >&2
  exit 2
}
[ -x "$WORKER" ] || { echo "worker not executable: $WORKER" >&2; exit 2; }
[ -f "$SOURCE" ] || { echo "source missing: $SOURCE" >&2; exit 2; }

mkdir -p "$RUN_DIR"
FRAMES=$((DURATION * 60))
ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python3}"

for mode in $MODES; do
  for rep in $(seq 1 "$REPEATS"); do
    run="$RUN_DIR/mode_${mode}_r${rep}"
    mkdir -p "$run"
    # Keep the AF_UNIX path short: the project evidence path can exceed 108 bytes.
    sock="/tmp/l2_${mode}_${rep}_$$.sock"
    rm -f "$sock"
    echo "=== mode=$mode repeat=$rep frames=$FRAMES source_hold=$SOURCE_HOLD ==="

    if command -v dmesg >/dev/null 2>&1; then
      dmesg --ctime > "$run/dmesg_before.txt" 2>&1 || dmesg > "$run/dmesg_before.txt" 2>&1 || true
    fi

    "$PY" "$ROOT/d3_replay.py" --file "$SOURCE" --socket "$sock" \
      --rate 60 --frames "$FRAMES" --stall-ms 200 --eos-wait 10 \
      > "$run/replay.log" 2>&1 &
    replay_pid=$!

    for _ in $(seq 1 100); do
      grep -q LISTENING "$run/replay.log" 2>/dev/null && break
      kill -0 "$replay_pid" 2>/dev/null || break
      sleep 0.1
    done
    grep -q LISTENING "$run/replay.log" 2>/dev/null || {
      echo "replay did not listen"; cat "$run/replay.log"; exit 1;
    }

    rot_args=()
    if [ "$DUMP_ROT" -gt 0 ]; then
      mkdir -p "$run/rot"
      rot_args+=(--dump-rot "$run/rot" --dump-rot-frames "$DUMP_ROT")
    fi

    source_args=()
    if [ "$DUMP_SOURCE" -gt 0 ]; then
      mkdir -p "$run/source"
      source_args+=(--dump "$run/source" --dump-frames "$DUMP_SOURCE")
    fi

    timeout -k 5 $((DURATION + 30)) "$WORKER" \
      --socket "$sock" --frames 0 --hide-primary --start-gate 0 \
      --mode 1920x1080@60 --video 1920x1080 --cap-bufs 17 \
      --rotation 180 --rotation-mode "$mode" --source-hold "$SOURCE_HOLD" \
      --dmabuf-sync 1 --trace-csv "$run/trace.csv" --lat-csv "$run/latency_worker.csv" \
      "${rot_args[@]}" "${source_args[@]}" \
      > "$run/worker.log" 2>&1 &
    worker_pid=$!

    "$PY" "$ROOT/latency_sampler.py" --pid 0 --worker-pid "$worker_pid" \
      --out "$run/sys.csv" > "$run/sampler.log" 2>&1 &
    sampler_pid=$!

    set +e
    wait "$worker_pid"; worker_rc=$?
    set -e
    kill "$sampler_pid" 2>/dev/null || true
    wait "$sampler_pid" 2>/dev/null || true
    wait "$replay_pid"; replay_rc=$?
    echo "worker_rc=$worker_rc replay_rc=$replay_rc"
    echo "$worker_rc" > "$run/worker.rc"
    echo "$replay_rc" > "$run/replay.rc"

    if command -v dmesg >/dev/null 2>&1; then
      dmesg --ctime > "$run/dmesg_after.txt" 2>&1 || dmesg > "$run/dmesg_after.txt" 2>&1 || true
    fi

    "$PY" "$ROOT/l2_report.py" --run-dir "$run" --warmup-s "$WARMUP" \
      > "$run/report.log" 2>&1 || true
    sha256sum "$SOURCE" "$WORKER" > "$run/input_hashes.txt"
  done
done

echo "DONE $RUN_DIR"
