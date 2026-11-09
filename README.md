# VT13 USB HEVC Receiver

Read-only Linux receiver for the VT13 (`2ca3:1020`) USB video endpoint. The
pipeline reads raw HEVC Annex-B data from Bulk IN `0x81`, assembles access
units, waits for a decodable random-access point, and exposes decoded frames as
OpenCV-compatible BGR `numpy.ndarray` images.

```text
VT03 camera -> wireless link -> VT13 -> USB Bulk IN 0x81
    -> Annex-B parser -> access-unit assembler -> PyAV HEVC decoder -> BGR frame
```

## Status

- Offline golden replay is verified: `captures/cold_start/bulk_if0_ep81.bin`
  decodes 105 frames with zero decoder errors.
- Live USB streaming is verified: a 145.968 s headless session decoded 5,537
  frames at 60.59 FPS and 1920x1080, with zero decoder errors, corrupt frames,
  or dropped frames. The 43 USB recoveries occurred before the first frame
  while VT03 was intentionally disconnected; there were no USB errors after
  reconnect. Offline replay produced the same 5,537 clean frames.
- A second live session (`live_run10`) decoded 6,342 clean frames at 60.6 FPS
  over 130.6 s. It had 47 in-place USB recoveries during one early 11.6 s link
  interruption (9.832-21.386 s) and no USB errors afterward. The 407
  decoder-marked corrupt frames were suppressed and confined to the early
  segment; a late full-resolution frame was clean.
- `live_run11` reproduced the readiness edge directly: 7.78 MiB of video bytes
  arrived with 0 decoded frames before VT03 was power-cycled a second time.
  After the fresh parameter sets and IRAP, the live session decoded 970 frames;
  offline replay decoded 974 frames with 0 errors. USB byte flow alone is
  therefore not treated as video readiness.
- The first frame in both the golden replay and the live run is 1832x1032;
  later frames reach 1920x1080, so callers must not assume one fixed resolution.
- The default `read.read_size` is 2048 bytes. In 30 s probes, 512 B through
  2 KiB produced 0-2 USB errors, while 4 KiB produced 19-29 errors and 16 KiB
  produced 38 errors. This is an empirical transport mitigation, not a proven
  root-cause fix for EIO.
- PyAV is configured to produce frames marked corrupt so USB damage does not
  silently stall decoding, but those frames are suppressed from the frame queue
  by default. Set `decoder.emit_corrupt_frames=true` only for diagnostics.
- `device.status_drain` performs a read-only drain of `0x82`. It is enabled in
  the example configuration but remains experimental and optional; testing did
  not establish that it is required for video stability.
- The pipeline never issues vendor-specific USB OUT transfers. It can optionally
  write DUML control frames to the CDC port (`control.enabled`) to request an
  I-frame and poll pairing status; the video endpoint is unaffected. Recovery is
  still limited to clearing a stalled endpoint and optional USB device reset.

## Architecture

| Module | Responsibility |
|---|---|
| `vt13_video/nal.py` | Incremental Annex-B parsing, AU assembly, parameter-set cache, IRAP detection |
| `vt13_video/device.py` | sysfs and PyUSB discovery, endpoint validation, actionable permission errors |
| `vt13_video/sources.py` | Read-only USB source and offline capture replay |
| `vt13_video/recovery.py` | Backoff, jitter, healthy-read tracking, reset policy |
| `vt13_video/control.py` | Optional DUML v1 control channel: I-frame requests, pairing poll, downlink decode |
| `vt13_video/decoder.py` | PyAV HEVC decoding, keyframe gating, decoder reset, bounded frame queue |
| `vt13_video/pipeline.py` | Background read/decode loop, recovery, control hooks, stall watchdog, recording, state and statistics |
| `vt13_video/cli.py` | `devices`, `inspect`, `stream`, `replay`, `doctor`, and `config` commands |

## Further documentation

- [Development flow, debugging, tuning, and latency](docs/DEVELOPMENT_FLOW_AND_LATENCY.md)
  explains how the receiver was built, the failure modes and fixes, the debug
  playbook, tuning defaults, measured receiver-side latency, and when a
  C++/Rust rewrite is or is not justified.
- [Remote machine usage reference](docs/REMOTE_MACHINE_USAGE.md)
  covers SSH access, PTY and sudo behavior, system details, tool paths, and
  common HEVC decode/debug commands for the `10.42.0.11` Armbian test machine.

## Requirements

- Linux with USB sysfs and usbfs (`/dev/bus/usb`)
- Python 3.10 or newer
- `libusb-1.0` and `ffmpeg` available to PyAV/libusb
- PyUSB, PyAV, NumPy, OpenCV, and PyYAML (see `requirements.txt`)

On Ubuntu, system packages can be installed with:

```bash
sudo apt install libusb-1.0-0 ffmpeg
```

Install the Python package from this directory:

```bash
python -m pip install -e .
```

Or install the runtime dependencies directly:

```bash
python -m pip install -r requirements.txt
```

The project has been tested with the Conda `rm` environment at
`/home/billieguo/miniconda3/envs/rm/bin/python`.

## USB permissions

Install the supplied udev rule, reload rules, and reconnect the receiver:

```bash
sudo cp udev/99-vt13-video.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

The rule uses `TAG+="uaccess"` so the active desktop session can access the
device without running as root. For headless services, use an appropriate
group/mode rule or a dedicated service account with access to `/dev/bus/usb`.
`uaccess` only applies to active local seats; it may not grant access over SSH.
For SSH/headless access, replace the rule with an owner/group rule, for example:

```udev
SUBSYSTEM=="usb", ATTR{idVendor}=="2ca3", ATTR{idProduct}=="1020", OWNER="youruser", GROUP="yourgroup", MODE="0660"
```

Check the environment before a live run:

```bash
python -m vt13_video doctor
python -m vt13_video devices --json
```

`doctor` exits nonzero when the matching device node or usbfs is unavailable.

## Configuration

The example configuration is `config/vt13_video.yaml`. All keys are validated,
unknown keys are rejected, and relative paths such as `record`, `save_first`,
`parameter_sets_file`, and `save_parameter_sets` are resolved against the YAML
file's directory rather than the current working directory.

Generate a fresh default file with:

```bash
python -m vt13_video config --write-default config/vt13_video.yaml
```

Important recovery settings:

- `read.read_size`: default `2048`. Larger reads were associated with frequent
  EIO on the VT13 endpoint; 2 KiB was stable in the sustained live run.
- `clear_halt_on_error`: clear a stalled endpoint after `pipe`/`stall`/`io`
  errors. The VT13 has been observed to report a halted Bulk IN endpoint as
  `EIO` (`errno=5`); clearing the halt restores reads.
- `reset_after_failures`: optional device reset threshold; `0` disables reset.
- `read.drain_reads`: number of chunks consumed immediately after opening the
  USB endpoint. These pre-roll bytes are parsed rather than discarded, so a
  fresh parameter set or IRAP in the first post-reconnect reads is preserved.
  Set it to `0` to disable the pre-roll read.
- `gap_threshold_s` / `reset_on_gap`: read-gap diagnostics. Forced resync is off
  by default because the verified golden capture contains long read gaps but
  remains decodable.
- `decoder.allow_corrupt_frames` / `emit_corrupt_frames`: allow PyAV to produce
  damaged frames, but keep them out of the frame queue by default.
- `decoder.save_parameter_sets`: optional Annex-B output path. Each complete
  VPS/SPS/PPS group is written atomically and unchanged groups are not rewritten.
  The observed parameter sets are not random per power-on: the captures contain
  two stable VPS/SPS variants mapping to 1832x1032 and 1920x1080, with one shared
  PPS. The saver keeps the latest complete group, so it follows a resolution
  change; capture each mode separately if both variants must be pre-saved.
- `device.status_drain`: experimental read-only drain of the `0x82` structured
  message endpoint; optional and not demonstrated to be required.

## Commands

Live streaming with preview and a saved first frame:

```bash
python -m vt13_video stream \
  --config config/vt13_video.yaml \
  --save-first /tmp/vt13_live_first.png \
  --save-parameter-sets live_runs/vt13_params.h265
```

The saved file contains the latest complete VPS/SPS/PPS group and can later be
passed back with `--parameter-sets-file`. It is a bootstrap aid only: parameter
sets do not create an IRAP or reconstruct missing reference frames.

Headless live streaming for 30 seconds with raw recording:

```bash
mkdir -p live_runs
python -m vt13_video stream \
  --config config/vt13_video.yaml \
  --headless --seconds 30 \
  --record live_runs/live_run01.bin \
  --json-stats
```

Replay the verified capture:

```bash
python -m vt13_video replay \
  --file captures/cold_start/bulk_if0_ep81.bin \
  --headless --save-first /tmp/vt13_first.png \
  --json-stats
```

If a capture has no parameter sets, prime the cache from a known-good Annex-B
file. Cached parameter sets can bootstrap decoding, but they cannot reconstruct
missing reference frames:

```bash
python -m vt13_video replay \
  --file /tmp/cold_start_noparams.h265 \
  --parameter-sets-file captures/cold_start/bulk_if0_ep81.bin \
  --headless --json-stats
```

Run the frame-consumer example against live USB or a capture:

```bash
python examples/frame_consumer.py --config config/vt13_video.yaml --seconds 10
python examples/frame_consumer.py --file captures/cold_start/bulk_if0_ep81.bin --seconds 10
```

`stream` and `replay` return a nonzero exit code when decoder errors occur or
no frames are decoded.

## Preview troubleshooting

- Preview mode opens an OpenCV window titled `VT13 USB HEVC`. It stays blank
  while the pipeline reports `waiting_keyframe`.
- Periodic status now includes link readiness, for example
  `usb=up, data=yes, params=yes, irap=no, keyframe=no`. Decoding starts only
  after `params=yes`, `irap=yes`, and `keyframe=yes`. `data=yes` only means USB
  bytes are arriving; it does not prove the wireless video link is decodable.
- VT13 does not emit a periodic IRAP in the observed stream. Start the stream,
  then disconnect and reconnect VT03 (or power-cycle the wireless link) so a
  fresh VPS/SPS/PPS + IRAP can arrive. The window fills after the first frame.
- The official client asks the transmitter for an I-frame over the CDC control
  port (DUML `1/1 -> 14/0`, frame
  `55 17 04 38 aa 0e 00 00 40 01 01 00 00 00 00 00 24 00 00 00 24 8f 06`).
  This pipeline can send the same request with `control.enabled=true`, retries
  it while waiting for a keyframe, and sends it after a discontinuity. The
  request is protocol-verified against the official client, but its effect on
  the transmitter is not yet verified on hardware. A USB reset alone still does
  not restart the stream or create an IRAP.
- If the current data epoch continues for 10 s without a decodable start, the
  pipeline logs a warning with the current parameter-set and IRAP state. The
  hint asks for fresh VPS/SPS/PPS + IRAP when parameter sets are missing, or
  only a fresh IRAP when parameter sets are already complete. The timer restarts
  after a reconnect or discontinuity.
- Ctrl+C prints `Interrupted.` and stops the stream. If a GUI call wedges the
  process, terminate it from another terminal:

```bash
pgrep -af 'python -m vt13_video stream'
kill -TERM <PID>
kill -KILL <PID>  # only if SIGTERM does not exit
```

## Recording and diagnostics

When `output.record` (or `--record`) is set, raw bytes are written to the
requested file and two sidecars are created:

- `<stem>.times.tsv`: `elapsed_s`, `chunk_length`, `wall_time_utc`
- `<stem>.events.tsv`: `elapsed_s`, `event`, `detail`, `wall_time_utc`

`elapsed_s` is monotonic time since the pipeline started. `wall_time_utc` is an
ISO 8601 UTC timestamp with millisecond precision, so USB events can be aligned
with kernel logs such as `dmesg -T` after normalizing the time zone. Error event
details include the error kind/message, `errno`, libusb backend code, successful
read/byte counts, and time since the last data.

JSON statistics include `usb.empty_reads`, `decode.corrupt_frames`, and optional
`usb.status_drain` state plus `last_error_kind`,
`last_error_errno`, `last_error_backend_code`, `last_error_reads`,
`last_error_bytes`, and `last_error_since_data_s` for the most recent USB error.
The `link` object reports `usb_open`, `data_flowing`,
`parameter_sets_complete`, `irap_seen`, `keyframe_started`, and `streaming`.
`irap_seen` and `keyframe_started` describe the current acquisition epoch and
reset after a discontinuity. `parameter_sets` reports completeness, sizes,
`saved`, and `saved_path`.
The recording path and its parent directory must be writable; an unusable path
causes the command to exit with an actionable error before opening USB.

## Python API

```python
from vt13_video import VT13Stream, load_config

config = load_config("config/vt13_video.yaml")
config.output.preview = False

with VT13Stream(config) as stream:
    frame = stream.read_frame(timeout=1.0)  # Frame | None
    if frame is not None:
        bgr = frame.image  # numpy.ndarray, uint8, BGR

    latest = stream.latest_frame  # newest frame, even if the queue was drained
```

For offline replay, pass `FileSource(path)` as the `source` argument to
`VT13Stream`. `read_frame()` consumes from a bounded queue; `latest_frame` is
intended for consumers that only need the freshest image.

## Recovery semantics

- USB read timeouts increment counters. A timeout becomes a stall only after
  `read.stall_timeout_s` without data.
- Zero-length reads increment `usb.empty_reads`; sustained no-data beyond
  `read.stall_timeout_s` also triggers stall recovery.
- Read failures trigger exponential backoff with jitter. `pipe`/`stall`/`io`
  errors can optionally clear the endpoint halt before reopening.
- If clearing a halt succeeds after an `io` error, the pipeline preserves the
  parser, AU assembler, and decoder state and continues on the existing USB
  handle. This is the recovery path observed for VT13's EIO/halted endpoint.
- If clearing a halt succeeds after a `pipe` or `stall` error, the pipeline
  continues on the existing handle but marks a discontinuity and resets the
  parser, AU assembler, and decoder before waiting for a fresh IRAP.
- For those error kinds it closes and reopens when the halt clear fails or a
  configured device reset is attempted; other error kinds reopen directly.
- A successful `open()` does **not** clear the failure streak. Recovery requires
  sustained healthy reads (`healthy_reads` or `healthy_seconds`).
- Repeated failures of the same kind are logged at most once per 5 s, with a
  summary of suppressed details when reporting resumes or the stream recovers.
  Counters and `.events.tsv` still record every failure; disconnects and failed
  halt clears are always logged.
- On a discontinuity, the parser, AU assembler, and decoder are reset. The
  parameter-set cache is retained, and decoding restarts only at a fresh IRAP
  with complete parameter sets.
- Bytes consumed immediately after USB open are parsed, not discarded. This
  preserves a fresh IRAP that arrives during re-enumeration.
- The current-epoch `link.irap_seen` and `link.keyframe_started` flags reset on
  discontinuity. Lifetime counts remain available under `stream`.
- State reporting distinguishes `waiting_keyframe`,
  `waiting_parameter_sets`, `streaming`, `recovering`, and terminal states.

## Tests

Run the regression suite with unittest:

```bash
python -m unittest discover -s tests -t . -v
```

The suite currently has 50 tests and covers arbitrary parser chunk boundaries,
AU grouping, parameter-set bootstrap and atomic saving, link readiness state,
current-epoch readiness warning timing and wording, post-open pre-roll parsing,
golden and stripped-stream replay, recovery/backoff/reset behavior, recovery-log
throttling, empty-read stalls, corrupt-frame suppression, diagnostic metadata,
recording timestamps, YAML validation, sysfs discovery, and CLI smoke paths.

## Known limitations

- A stream with no VPS/SPS/PPS or no IRAP cannot start decoding from arbitrary
  P-frames. Cached parameter sets alone do not create missing reference frames.
- The verified golden stream changes resolution after the initial frames; the
  pipeline reports the actual frame dimensions instead of enforcing one size.
- The camera does not emit a periodic IRAP in the observed stream. A standard
  USB device reset did not restart the video stream or create a new IRAP in
  testing. The DUML I-frame request (`control.enabled=true`) is the candidate
  recovery primitive but its live effect is unverified; power-cycle or relink
  VT03 if the request is not honored.
- Replugging the VT13 USB cable only re-enumerates the receiver. It does not
  reset the VT03 encoder, which may resume mid-GOP without an IRAP. If the link
  remains in `waiting_keyframe` after reconnection, power-cycle VT03.
- Saved parameter sets can bootstrap parsing and decoding, but they are not a
  substitute for a fresh IRAP or for the reference picture chain.
- Reads of 4 KiB and larger were associated with frequent EIO. The 2 KiB default
  mitigates this transport behavior, but its root cause is still unknown.
- `status_drain` remains experimental; no test has shown it is necessary.
- `decoder.stall_restart_s` (default 0, disabled) resets the decoder when VCL
  access units keep arriving but no frames are produced for N seconds. It is
  meant for a silent `0xf` session death, where the ffmpeg process stays alive
  but stops yielding pictures; pair it with `control.enabled=true` so the reset
  is followed by an I-frame request. The ffplay window stays open across these
  resets; only the picture freezes for the watchdog interval. Experimental.
- A preview window can remain blank until VT03 is relinked and a fresh IRAP is
  received; use `--headless` plus `--save-first` to verify capture independently.
- Sustained streaming has been verified in two sessions (145.968 s and 130.6 s),
  including one early link interruption and in-place recovery. Repeat runs
  across different RF conditions and repeated reconnects are still warranted.
- OpenCV preview requires a display server; use `--headless` on headless hosts.
