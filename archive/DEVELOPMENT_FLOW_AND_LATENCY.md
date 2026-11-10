# VT13 Receiver: Development Flow, Debugging, Tuning, and Latency

Status: 2026-10-31

This document records how the VT13 USB HEVC receiver was developed, which
failure modes were encountered, how they were handled, and what to check when
debugging or tuning latency. It complements `README.md` and the Chinese project
log (`VT13_USB视频逆向项目进度与后续计划.md`).

## 1. Executive summary

- The receiver is read-only. It never sends vendor-specific OUT/control
  requests. Recovery is limited to endpoint halt clearing, optional USB reset,
  and reopening the device.
- USB byte flow is not the same as decodable video. A usable start requires
  complete VPS/SPS/PPS, an IRAP in the current acquisition epoch, and a decoder
  that has accepted that IRAP.
- The VT13 stream does not provide a periodic IRAP. After a link loss or
  discontinuity, a fresh IRAP must come from VT03. No verified receiver-side
  command can request one.
- Parameter sets are stable and can be saved/reused for bootstrap, but they do
  not replace a fresh IRAP or missing reference frames.
- The measured receiver-side processing cost is small compared with the frame
  interval. On an offline replay of `live_run11`, parser/assembler work was
  about 1.4% of core processing time; PyAV/FFmpeg decode plus BGR conversion was
  about 98.6%. Receiver-side `Frame.latency_s` was p50 13.5 ms, p90 17.0 ms,
  p99 21.8 ms in that replay.
- A C++ or Rust rewrite is not the first fix for a latency complaint. It would
  not remove encoder, wireless-link, USB, IRAP-readiness, display/compositor, or
  queue-backlog delay. First measure where the latency is, then tune queue and
  display behavior; consider native/hardware decoding only if profiling shows a
  real receiver-side bottleneck.

## 2. System model and constraints

```text
VT03 camera -> wireless encoder/link -> VT13 receiver
    -> USB Bulk IN 0x81
    -> incremental Annex-B parser
    -> access-unit assembler
    -> keyframe-gated PyAV HEVC decoder
    -> BGR frame queue
    -> preview / application / recording
```

Observed constraints:

- Device ID: `2ca3:1020`, video endpoint `0x81` on interface 0, structured
  status endpoint `0x82` on interface 1.
- The status drain is read-only and experimental. It has not been proven
  necessary for video stability.
- The stream starts at 1832x1032 and later reaches 1920x1080. Do not assume a
  fixed resolution.
- The stream contains VPS/SPS/PPS and IRAPs, but not on a reliable periodic
  schedule.
- A halted Bulk IN endpoint may surface as `EIO` (`errno=5`, libusb backend
  `-1`) rather than a conventional stall error.
- Read sizes of 4 KiB and above caused substantially more USB errors in the
  probes. The default is therefore 2 KiB, accepting extra syscall/read cadence
  in exchange for transport stability.

## 3. Development flow

### Stage 1: device discovery and capture

1. Used sysfs and PyUSB to identify interfaces, endpoints, permissions, and the
   active configuration.
2. Captured idle, linked, and cold-start sessions, including raw bytes, read
   timestamps, and event traces.
3. Confirmed that `0x81` carries Annex-B HEVC and that `0x82` is a structured
   status/message endpoint.
4. Established the first golden capture:
   `captures/cold_start/bulk_if0_ep81.bin`.

### Stage 2: transport stability

1. Started with direct Bulk IN reads.
2. Observed stalls, timeouts, disconnects, and `EIO` from the endpoint.
3. Added backoff, jitter, healthy-read tracking, endpoint halt clearing, and
   optional device reset.
4. Distinguished recovery classes:
   - `io`: clear the halt and preserve parser/assembler/decoder state when the
     halt clear succeeds.
   - `pipe` / `stall`: clear the halt but reset stream state and wait for a new
     IRAP.
   - `disconnected`: mark a discontinuity and reopen the device.
5. Ran read-size probes and chose 2048 bytes as the stable default.

### Stage 3: bitstream parsing and access-unit assembly

1. Built an incremental Annex-B parser so NAL units can span arbitrary USB read
   boundaries.
2. Built an access-unit assembler using AUD boundaries and the first-slice flag.
3. Kept VPS/SPS/PPS and prefix SEI attached to the following picture rather
   than the previous one.
4. Added parameter-set caching and IRAP detection.

### Stage 4: decoding and recovery behavior

1. Used PyAV/FFmpeg for HEVC decode and BGR conversion.
2. Added keyframe gating: decoding starts only from an IRAP with usable
   parameter sets.
3. Enabled FFmpeg's corrupt-frame output so recoverable USB damage does not
   silently suppress the rest of the stream, then suppressed corrupt frames from
   the application queue by default.
4. Added decoder reset after consecutive errors, followed by a wait for a new
   IRAP.

### Stage 5: readiness and parameter-set handling

1. `live_run11` showed 7.78 MiB of video bytes with zero decoded frames before
   VT03 was power-cycled. This proved that byte flow alone is not readiness.
2. Added current-epoch `link` fields:
   `usb_open`, `data_flowing`, `parameter_sets_complete`, `irap_seen`,
   `keyframe_started`, and `streaming`.
3. Added a 10 s warning for a data epoch that is flowing but has not started
   decoding. The warning names the missing prerequisite and resets its timer
   after reconnect/discontinuity.
4. Added atomic parameter-set saving and preloading. The observed sets are
   stable variants, not random per power-on.

### Stage 6: operational polish

1. Added periodic status, JSON snapshots, raw recording, `.times.tsv`, and
   `.events.tsv` diagnostics.
2. Throttled repeated same-kind recovery logs while keeping every event in the
   event trace and preserving disconnect / failed-clear-halt warnings.
3. Added offline replay and golden tests.
4. Added tests for parser boundaries, AU assembly, parameter bootstrap, link
   readiness, recovery behavior, warning timing, log throttling, configuration,
   device discovery, and CLI paths.

### Current verification baseline

- **48 unittest cases pass.**
- Golden capture: 105 frames, 0 decoder errors, 121 access units.
- `live_run11` offline replay: 974 frames at 1920x1080, 0 decode errors, 0
  decoder resets, 0 corrupt frames.
- `live_run09` live session: 145.968 s, 5,537 frames, 60.59 FPS, 1920x1080,
  0 decoder errors/corrupt frames/dropped frames after the initial reconnect.
- `live_run10` live session: 130.6 s, 6,342 clean frames, 60.6 FPS; 47 in-place
  stall recoveries and 407 suppressed corrupt frames in the early segment.

## 4. Problems and how they were handled

| Symptom | Root cause / finding | Solution | Verification / caveat |
|---|---|---|---|
| Device missing or permission denied | usbfs permissions / udev / active seat | sysfs + PyUSB discovery, `doctor`, udev rule, actionable errors | `doctor` and device tests |
| USB read stalls or returns EIO | VT13 may halt the Bulk IN endpoint and report `errno=5` | Clear endpoint halt; preserve state for `io`; reset stream state for `pipe`/`stall` | Live recoveries; 47 stalls in `live_run10` |
| Large reads increase USB errors | 4 KiB+ reads were unstable in probes | Use 2 KiB default; expose `--read-size` for controlled experiments | Empirical mitigation, not a proven root cause |
| NAL unit split across reads | Bulk reads do not align with NAL boundaries | Incremental Annex-B parser with carry buffer | Arbitrary-chunk parser test |
| Access units grouped incorrectly | Parameter sets/AUD/first-slice boundaries | Dedicated AU assembler with pending-prefix handling | AU assembly tests |
| Decoder cannot start | Missing VPS/SPS/PPS or no IRAP | Keyframe gate, parameter cache/bootstrap, explicit readiness state | Stripped-stream and golden-replay tests |
| USB bytes arrive but picture stays blank | No fresh IRAP / no reference chain | Detect readiness and wait; power-cycle/reconnect VT03 | `live_run11` readiness case |
| Parameter sets lost or changed | Resolution/variant changes | Cache latest complete group; atomic save; capture both variants if needed | Saved 102-byte file for 1920x1080 |
| Corrupt frames after USB damage | Missing references and decoder error concealment | Allow corrupt output, suppress by default, reset after repeated errors | `live_run10` corrupt-frame analysis |
| Reconnect loop / false warning | Warning timer used total session time | Use current data-epoch timer; reset on open/close/discontinuity/decoder reset | New regression tests |
| Recovery log spam | Repeated successful halt clears logged at WARNING | Log at most once per 5 s per kind; summarize suppressed details | Stats and event trace remain complete |
| Resolution change | Stream starts at 1832x1032 then moves to 1920x1080 | Report per-frame width/height; do not hard-code one size | Golden replay and live runs |
| Preview lag | Queue depth, display/compositor, or transport delay | Measure receiver latency; use `latest_frame` or queue size 1-2 for control loops | See latency section |

## 5. Debugging playbook

Run these in order when something looks wrong.

### 5.1 Environment and device

```bash
python -m vt13_video doctor
python -m vt13_video devices --json
```

Check:

- `/dev/bus/usb` exists and is accessible.
- The device is `2ca3:1020`.
- Interface 0 exposes endpoint `0x81`.
- Interface 1 exposes `0x82` if status drain is enabled.
- No other process is claiming the video interface.

### 5.2 Capture a reproducible live run

```bash
python -m vt13_video stream \
  --config config/vt13_video.yaml \
  --headless --seconds 30 \
  --record live_runs/debug_run.bin \
  --save-parameter-sets live_runs/vt13_params.h265 \
  --json-stats
```

The `.times.tsv` and `.events.tsv` sidecars are as important as the raw bytes.
Record every experiment you intend to analyze; an unrecorded run cannot be
replayed later.

### 5.3 Check readiness before blaming the decoder

Look at the periodic status suffix:

```text
usb=up, data=yes, params=yes, irap=no, keyframe=no
```

Meaning:

- `data=yes`: USB bytes are arriving.
- `params=yes`: complete VPS/SPS/PPS are cached.
- `irap=yes`: an IRAP has been seen in the current epoch.
- `keyframe=yes`: the decoder has started from a usable IRAP.

If `params=no` or `irap=no`, do not tune the decoder first. Power-cycle or
reconnect VT03 so it emits a fresh random-access point. There is no verified
receiver command that requests one.

### 5.4 Separate live transport from decoding

Replay the recorded raw bytes:

```bash
python -m vt13_video replay \
  --file live_runs/debug_run.bin \
  --headless --json-stats
```

- Clean replay means the parser/decoder logic handled the captured bytes.
- Replay errors or resets mean the capture contains a real bitstream problem.
- Live-only failures point to USB/link/recovery behavior, not the decoder.

### 5.5 Inspect recovery events

Use `live_runs/debug_run.events.tsv` to correlate:

- `usb_error`: kind, errno, backend code, last reads/bytes, time since data.
- `clear_halt`: whether endpoint recovery succeeded.
- `discontinuity`: stream state was reset and a fresh IRAP is required.
- `read_gap`: a large gap without a forced reset.
- `preroll`: bytes consumed immediately after open were parsed instead of
  discarded, preserving a possible fresh IRAP.
- `parameter_sets_saved`: saved parameter-set path.
- `decoder_reset`: decoder rejected the current reference chain.

If `clear_halt` succeeds for `io`, the decoder state is intentionally preserved.
If it succeeds for `pipe`/`stall`, stream state is reset. Do not assume those two
paths are equivalent.

### 5.6 Measure latency without the preview

Start headless and consume frames with a low-latency queue:

```bash
python examples/frame_consumer.py \
  --config config/vt13_video.yaml \
  --seconds 30
```

`frame_consumer.py` prints `frame.latency_s`. That value measures the interval
from the first NAL of an access unit being received to the decoded BGR frame
being available. It does **not** include camera capture, VT03 encoding,
wireless transport, USB device buffering, display compositing, or application
processing after the frame is handed over.

For a stricter receiver-side measurement, set `decoder.queue_size` to 1-2 and
consume with `latest_frame` when only the newest image matters.

### 5.7 Reduce noise while measuring

For a latency experiment, disable or isolate:

- preview (`--headless`) and window scaling;
- raw recording (disk I/O);
- `device.status_drain` (experimental second USB reader thread);
- verbose recovery logging (`--log-level INFO` or `WARNING`);
- terminal printing for every frame; redirect output or aggregate statistics.

The `QFontDatabase: Cannot find font directory ...` messages from OpenCV/Qt are
packaging warnings and do not indicate a pipeline failure.

## 6. Tuning guide

| Setting | Default | Effect | Guidance |
|---|---|---|---|
| `read.read_size` | 2048 | USB transfer size and read cadence | Keep 2 KiB for stability; test 512/1024 only in a controlled probe |
| `read.timeout_ms` | 250 | Per-read timeout | Increase only for slow/diagnostic runs; large values delay recovery |
| `read.stall_timeout_s` | 3.0 | No-data threshold before stall recovery | Lower for faster recovery, higher to tolerate transient gaps |
| `read.drain_reads` | 2 | Consume and parse pre-roll bytes after open | Preserves a fresh parameter set/IRAP in the first post-reconnect reads; 0 disables |
| `recovery.clear_halt_on_error` | true | Clears endpoint halt for `pipe`/`stall`/`io` | Keep enabled for observed VT13 EIO behavior |
| `recovery.reset_after_failures` | 0 | USB device reset threshold | Keep 0 unless reset is specifically being tested; reset did not reliably restart the stream |
| `recovery.gap_threshold_s` | 0.5 | Records large read gaps | Diagnostic only; do not force reset unless replay proves it helps |
| `recovery.reset_on_gap` | false | Resets stream state on a read gap | Off by default; golden captures contain valid long gaps |
| `decoder.require_keyframe` | true | Starts decoding only at IRAP | Keep enabled; decoding mid-GOP without references is not reliable |
| `decoder.allow_corrupt_frames` | true | Lets FFmpeg emit concealed frames | Keep enabled so recoverable USB damage does not silently stall output |
| `decoder.emit_corrupt_frames` | false | Puts corrupt frames into the queue | Keep false for normal use; enable only for diagnostics |
| `decoder.parameter_sets_file` | null | Preloads VPS/SPS/PPS | Use saved stable sets for bootstrap; still wait for a fresh IRAP |
| `decoder.save_parameter_sets` | null | Atomically saves complete sets | Useful for preloading; capture both resolution variants if needed |
| `decoder.max_consecutive_errors` | 3 | Decoder reset threshold | Lower for stricter recovery, higher only if the stream is known noisy |
| `decoder.queue_size` | 8 | Consumer backlog bound | Use 1-2 for low-latency control loops; larger for recording/offline |
| `decoder.drop_oldest` | true | Keeps newest frames when full | Keep true for live/control; false for replay where every frame matters |
| `output.preview_width` | 1000 | GUI scaling work | Lower or use headless when measuring latency |
| `output.stats_interval_s` | 1.0 | Status print frequency | Increase during latency tests to reduce terminal overhead |
| `output.log_level` | INFO | Log volume | Use WARNING/ERROR for timing runs |
| `device.status_drain` | true | Experimental `0x82` drain | Disable to isolate its CPU/thread impact; not proven required for video |

Important queue semantics:

- `read_frame()` returns the oldest queued frame (FIFO).
- `latest_frame` returns the newest frame, regardless of queue backlog.
- With `queue_size=8` and a consumer slower than the producer, the steady-state
  backlog can add roughly 8 frame intervals. At 60 FPS that is about 133 ms.
- The CLI preview currently consumes through `read_frame()`. If preview latency
  matters, reduce queue size or use `latest_frame` in the consumer.

## 7. Latency analysis

### 7.1 Four different latencies

1. **Startup/readiness latency**: time from opening USB to the first decoded
   frame. Dominated by parameter-set availability, IRAP arrival, and
   reconnect/power-cycle behavior.
2. **Transport latency**: camera capture + VT03 encode + wireless transport +
   VT13 buffering + USB/kernel delivery. This is not measured by the receiver's
   `Frame.latency_s`.
3. **Receiver processing latency**: Annex-B parsing, AU assembly, HEVC decode,
   BGR conversion, queue insertion. `Frame.latency_s` measures this plus decoder
   buffering, starting from the first NAL of the AU.
4. **Display/consumer latency**: queue backlog, OpenCV/Qt rendering, window
   scaling, compositor/vsync, and application processing.

Do not use one number to explain all four. A blank screen for 100 s is readiness
latency, not Python decode latency. A 130 ms steady-state preview delay can be a
queue/display issue even when decode is fast.

### 7.2 Measured receiver-side baseline

Offline replay of `live_runs/live_run11.bin` with the full pipeline and a
concurrent consumer:

- 974 frames in 7.335 s of replay wall time (132.8 FPS).
- `Frame.latency_s`: p50 13.5 ms, p90 17.0 ms, p99 21.8 ms, max 72.9 ms.
- 0 decode errors, 0 decoder resets, 0 corrupt frames, 0 dropped frames.

Core-processing breakdown on the same capture (29,781,978 bytes):

- Annex-B parse + AU assembly: 0.097 s (~293.9 MiB/s), about **1.4%** of core
  processing.
- PyAV/FFmpeg decode + BGR conversion: 7.027 s, about **98.6%** of core
  processing, roughly 138 FPS.

At a 60 FPS live rate, the frame interval is 16.7 ms. The measured average
decode+convert cost is roughly 7.2 ms/frame, leaving headroom in the receiver.
The p99 receiver-side latency of 21.8 ms is an occasional offline jitter figure,
not a full end-to-end live latency.

For scale, `live_run09` performed 82,184 USB reads over 145.968 s, about 563
reads/s at 2 KiB per read. That is a read cadence of roughly 1.8 ms per chunk;
the read size is not a plausible explanation for a large visual delay.

The latest unrecorded live log first reached a decodable start only after about
108 s, following parameter-set/IRAP availability and reconnects. That delay is
readiness/link behavior, not Python processing speed.

### 7.3 Likely latency contributors, in order of investigation

1. **Readiness / link acquisition**: if no frames are present, check `params`,
   `irap`, and `keyframe`; power-cycle VT03 if needed.
2. **Transport / encoder / wireless**: if frames are flowing but end-to-end
   latency is large, measure against an external timestamp. The receiver cannot
   remove delay already introduced before USB.
3. **Consumer queue backlog**: inspect `queue.size` and `queue.dropped`; use
   `latest_frame` or a queue size of 1-2 for low-latency control.
4. **Display/compositor**: compare headless consumer latency with preview
   latency; test without window scaling and without Qt.
5. **Receiver CPU/decoder**: compare live FPS with offline replay FPS and watch
   CPU saturation. If replay is much faster than live and latency is still high,
   the bottleneck is not the Python decode loop.
6. **Diagnostics overhead**: recording, status drain, per-frame printing, and
   verbose logging can add CPU/I/O contention during measurements.

### 7.4 Measurement recipe

1. Record a live run with raw bytes, `.times.tsv`, and `.events.tsv`.
2. Replay it headless; confirm frame count, errors, resets, and corrupt frames.
3. Measure `frame.latency_s` distribution with a queue size of 1-2 and a consumer
   that does not print every frame.
4. Compare headless, preview, recording, and status-drain variants.
5. For true end-to-end latency, use an external timestamp source visible in the
   camera image (for example, a millisecond clock or a controlled LED) and
   photograph/measure the display. `Frame.latency_s` alone is not end-to-end.
6. Check CPU utilization and scheduling while streaming. If live FPS is near 60
   and replay FPS is far above 60, CPU/decoder is unlikely to be the primary
   latency cause.

## 8. Will C++ or Rust solve the latency?

**Not by itself, and usually not first.**

The measured evidence says:

- The heavy decode and BGR conversion are already performed by native
  FFmpeg/PyAV code. That accounted for about 98.6% of core processing time.
- The Python Annex-B parser and AU assembler accounted for about 1.4% of core
  processing time. Rewriting just that layer has a small upper bound on the
  achievable saving.
- The measured receiver-side p50 was 13.5 ms and p90 17.0 ms offline, so the
  typical case fits within the 16.7 ms frame interval at 60 FPS; p99 was
  21.8 ms, showing occasional jitter beyond one frame interval.
- Large visible delays are more likely to come from readiness/IRAP waiting,
  wireless/encoder/USB transport, queue backlog, or display compositing.

A native rewrite can still be justified for other reasons:

- multi-stream or high-resolution workloads where CPU or memory copies matter;
- deterministic scheduling and tighter jitter control;
- hardware decode / zero-copy GPU integration;
- embedded deployment with limited Python runtime or memory;
- avoiding Python/FFI/queue overhead after profiling proves it is material.

Those gains come from architecture choices (hardware decode, zero-copy, direct
FFmpeg/GStreamer integration, real-time scheduling), not from the language label
alone. A C++ or Rust implementation still needs the same USB recovery, Annex-B
parsing, keyframe gating, parameter-set handling, and queue policy. It also
still cannot request an IRAP from VT03 or remove delay already present in the
wireless link.

Recommended order:

1. Measure receiver-side and end-to-end latency.
2. Reduce queue backlog and display overhead.
3. Test headless vs preview and status-drain on/off.
4. Profile CPU and decode; consider hardware decode/GStreamer.
5. Rewrite in C++/Rust only if profiling shows a receiver-side bottleneck that
   cannot be removed within the Python/native-library architecture.

## 9. Invariants and debugging reminders

- `data=yes` means bytes are arriving, not that video is decodable.
- A fresh IRAP is required after a discontinuity. Parameter sets alone cannot
  reconstruct the reference chain.
- USB replug only re-enumerates VT13; it does not reset the VT03 encoder. If no
  fresh IRAP arrives, power-cycle VT03.
- VT03 does not emit a periodic IRAP in the observed stream; power-cycle or
  reconnect when startup stalls.
- The receiver cannot request or emit an IRAP with any verified command.
- `clear_halt` after `io` preserves decoder state; `pipe`/`stall` recovery marks
  a discontinuity.
- Use 2 KiB reads for stability unless a controlled probe proves otherwise.
- Record raw bytes plus times/events for every live experiment.
- Replay offline before changing decoder logic; it separates transport failures
  from bitstream/decoder failures.
- Do not tune using corrupt frames unless `emit_corrupt_frames=true` is an
  intentional diagnostic choice.
- Do not hard-code 1920x1080; the stream can begin at 1832x1032.
- `read_frame()` is FIFO; `latest_frame` is newest. Queue depth directly affects
  latency when the consumer is slower than the producer.
- `Frame.latency_s` is receiver-side only; use an external timestamp for true
  end-to-end latency.
- Console log throttling does not lose data: `.events.tsv` and statistics still
  record every error.
- The OpenCV/Qt font-directory warnings are packaging noise, not stream errors.
