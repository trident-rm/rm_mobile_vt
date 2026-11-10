#!/bin/bash
# CM311 live launcher: run-4 pipeline plus the DUML control plane and the
# optional output-stall watchdog. The video path is unchanged.
#
# Env knobs:
#   DJI_RUN_DIR            (required) output directory
#   DJI_SMOKE_SECONDS      default 90
#   DJI_PARAMS_FILE        parameter-set priming file
#   DJI_CONTROL_ENABLED    default true
#   DJI_CONTROL_PORT       default null (auto-detect ttyACM0/interface 2)
#   DJI_PAIRING_POLL_S     default 1.0 (0 disables)
#   DJI_STALL_RESTART_S    default 5.0 (0 disables the watchdog)
#   DJI_DISPLAY            default ffplay
set -uo pipefail
: "${DJI_RUN_DIR:?DJI_RUN_DIR must be set}"
mkdir -p "$DJI_RUN_DIR"
cd "$HOME/mobile_vt" || exit 1
PY="$HOME/mobile_vt/.venv-v4l2/bin/python"
test -x "$PY" || { echo "ERROR: venv python missing"; exit 1; }
SECONDS_LIMIT="${DJI_SMOKE_SECONDS:-90}"
PARAMS_ARGS=()
if [ -n "${DJI_PARAMS_FILE:-}" ]; then
  test -f "$DJI_PARAMS_FILE" || { echo "ERROR: DJI_PARAMS_FILE not found: $DJI_PARAMS_FILE"; exit 1; }
  PARAMS_ARGS+=(--parameter-sets-file "$DJI_PARAMS_FILE")
fi
cat > "$DJI_RUN_DIR/smoke.yaml" <<YAML
recovery:
  kernel_abort_watch: ${DJI_KERNEL_ABORT_WATCH:-true}
control:
  enabled: ${DJI_CONTROL_ENABLED:-true}
  port: ${DJI_CONTROL_PORT:-null}
  iframe_on_connect: ${DJI_IFRAME_ON_CONNECT:-true}
  iframe_on_recovery: ${DJI_IFRAME_ON_RECOVERY:-true}
  iframe_retry_s: 2.0
  min_iframe_interval_s: 0.5
  pairing_poll_s: ${DJI_PAIRING_POLL_S:-1.0}
decoder:
  codec: hevc_v4l2m2m
  backend: ${DJI_BACKEND:-ffmpeg-pipe}
  ffmpeg_path: ${DJI_FFMPEG_PATH:-$HOME/ffmpeg-6.1.1-v4l2/ffmpeg}
  ffmpeg_codec: ${DJI_FFMPEG_CODEC:-hevc_v4l2m2m}
  convert_bgr: ${DJI_CONVERT_BGR:-true}
  display: ${DJI_DISPLAY:-ffplay}
  display_width: 1024
  display_height: 576
  stall_restart_s: ${DJI_STALL_RESTART_S:-5.0}
output:
  preview: false
  log_level: INFO
YAML
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
echo "launcher: codec=${DJI_FFMPEG_CODEC:-hevc_v4l2m2m} control=${DJI_CONTROL_ENABLED:-true} port=${DJI_CONTROL_PORT:-auto} pairing=${DJI_PAIRING_POLL_S:-1.0}s stall_restart=${DJI_STALL_RESTART_S:-5.0}s"
"$PY" -m vt13_video stream --config "$DJI_RUN_DIR/smoke.yaml" --headless \
  --seconds "$SECONDS_LIMIT" --record "$DJI_RUN_DIR/raw_ep81.bin" --json-stats \
  "${PARAMS_ARGS[@]}" --save-parameter-sets "$DJI_RUN_DIR/params_latest.h265" \
  > "$DJI_RUN_DIR/capture.log" 2>&1 &
STREAM_PID=$!
echo "$STREAM_PID" > "$DJI_RUN_DIR/stream.pid"
for _ in $(seq 1 40); do
  if grep -q "USB source open" "$DJI_RUN_DIR/capture.log" 2>/dev/null; then
    grep -m1 "control link" "$DJI_RUN_DIR/capture.log" || true
    echo "READY: USB source open — wireless may be enabled now"
    rc=0
    wait "$STREAM_PID" || rc=$?
    echo "STREAM_EXIT_RC=$rc"
    exit "$rc"
  fi
  if ! kill -0 "$STREAM_PID" 2>/dev/null; then
    echo "ERROR: stream exited before READY"
    tail -30 "$DJI_RUN_DIR/capture.log"
    exit 1
  fi
  sleep 0.5
done
echo "ERROR: READY timeout (20s)"
tail -30 "$DJI_RUN_DIR/capture.log"
kill "$STREAM_PID" 2>/dev/null
exit 1
