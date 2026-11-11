#!/bin/bash
# L1 live latency run (RC1 worker backend + instrumentation).
# Requires prior R2 approval. Human sequence: start this script, wait for
# READY, then enable the wireless video link. No recording is written to disk.
#
# Env:
#   DJI_RUN_DIR       (required) output directory
#   DJI_LAT_SECONDS   measurement window after READY (default 180)
#   VT13_ASYNC_USB    forced to 0 (never enable the async reader)
set -uo pipefail
: "${DJI_RUN_DIR:?DJI_RUN_DIR must be set}"
DURATION="${DJI_LAT_SECONDS:-180}"
mkdir -p "$DJI_RUN_DIR"
cd "$HOME/mobile_vt" || exit 1
PY="$HOME/mobile_vt/.venv-v4l2/bin/python"
test -x "$PY" || { echo "ERROR: venv python missing"; exit 1; }
test -x "$HOME/mobile_vt/build/d3/d3_probe" || { echo "ERROR: d3_probe missing"; exit 1; }

SHM="/dev/shm/vt13_l1_$$"
PY_CSV="${SHM}.latency_python.csv"
WK_CSV="${SHM}.latency_worker.csv"
SYS_CSV="${SHM}.sys.csv"
LOG="$DJI_RUN_DIR/stream.log"
export VT13_LAT_CSV="$PY_CSV"
export VT13_WORKER_LAT_CSV="$WK_CSV"
export VT13_ASYNC_USB=0

echo "config=$HOME/mobile_vt/config/vt13_video.kiosk.yaml duration=${DURATION}s"
"$PY" -m vt13_video stream --config "$HOME/mobile_vt/config/vt13_video.kiosk.yaml" \
  --headless --seconds "$((DURATION + 2))" --json-stats > "$LOG" 2>&1 &
STREAM_PID=$!
echo "$STREAM_PID" > "$DJI_RUN_DIR/stream.pid"

ready=0
for _ in $(seq 1 40); do
  if grep -q "USB source open" "$LOG" 2>/dev/null; then ready=1; break; fi
  if ! kill -0 "$STREAM_PID" 2>/dev/null; then
    echo "ERROR: stream exited before READY"; tail -30 "$LOG"; exit 1
  fi
  sleep 0.5
done
if [ "$ready" -ne 1 ]; then
  echo "ERROR: READY timeout (20s)"; tail -30 "$LOG"
  kill -INT "$STREAM_PID" 2>/dev/null; exit 1
fi
WORKER_PID="$(pgrep -f 'd3_probe --socket' | head -1 || true)"
echo "READY: USB source open (worker_pid=${WORKER_PID:-none}) — enable the wireless link now"
"$PY" "$HOME/mobile_vt/tools/latency_sampler.py" \
  --pid "$STREAM_PID" --worker-pid "${WORKER_PID:-0}" --out "$SYS_CSV" &
SAMPLER_PID=$!
sleep "$DURATION"
kill -INT "$STREAM_PID" 2>/dev/null
for _ in $(seq 1 100); do
  kill -0 "$STREAM_PID" 2>/dev/null || break
  sleep 0.1
done
kill -TERM "$STREAM_PID" 2>/dev/null
wait "$STREAM_PID"; RC=$?
kill "$SAMPLER_PID" 2>/dev/null
wait "$SAMPLER_PID" 2>/dev/null
cp -f "$PY_CSV" "$DJI_RUN_DIR/latency_python.csv" 2>/dev/null
cp -f "$WK_CSV" "$DJI_RUN_DIR/latency_worker.csv" 2>/dev/null
cp -f "$SYS_CSV" "$DJI_RUN_DIR/sys.csv" 2>/dev/null
rm -f "$PY_CSV" "$WK_CSV" "$SYS_CSV"
echo "STREAM_EXIT_RC=$RC"
echo "RUN_DIR=$DJI_RUN_DIR"
grep -E "IRAP received|DECODED frames|kernel VDEC abort" "$LOG" | tail -20
exit "$RC"
