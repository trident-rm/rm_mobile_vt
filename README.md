# VT13 USB HEVC Receiver

A read-only Linux receiver for the VT13 USB video endpoint (`2ca3:1020`). It
reads raw HEVC Annex-B data from Bulk IN `0x81`, assembles access units, waits
for a decodable random-access point, and exposes decoded frames as
OpenCV-compatible BGR `numpy.ndarray` images.

The verified production target is a CM311-1S running the native P128 worker and
a KMS kiosk. The PyAV software path remains available for development,
diagnostics, and offline replay.

## Features

- Live USB capture from VT13, plus offline replay of recorded captures.
- Annex-B parsing, access-unit assembly, parameter-set caching, and IRAP gating.
- Bounded recovery for USB stalls, endpoint halts, and disconnects.
- Optional DUML control-channel I-frame requests.
- Raw recording with timestamp and event sidecars.
- Native C worker for CM311 hardware decode and KMS presentation.
- Python API and CLI for development, replay, and diagnostics.

## Hardware BOM

The following bill of materials describes the verified deployment. A Linux PC
can run the software path without the CM311, but live USB access still requires
the VT13 receiver.

| Component | Qty | Notes |
|---|---:|---|
| CM311-1S TV box | 1 | Amlogic S905L3B, four cores, about 1.7 GiB RAM, internal eMMC; verified Armbian target. |
| DJI VT13 USB receiver | 1 | USB ID `2ca3:1020`; video endpoint Bulk IN `0x81`; optional CDC control interfaces. |
| DJI C5 / VT03 wireless camera and transmitter | 1 | Observed HEVC source; the receiver does not control the wireless link. |
| HDMI display and cable | 1 | 1080p60-capable display for the CM311 kiosk or local preview. |
| USB-A cable for VT13 | 1 | Connect the receiver to the CM311 or development PC. |
| CM311-1S DC power adapter | 1 | Use the supplied adapter; verify voltage/current on its label. |
| Ubuntu PC | 1 | Development, testing, deployment, and offline analysis host. |
| Network connection | 1 | SSH between the Ubuntu PC and CM311; the CM311 address is DHCP-assigned. |
| USB boot/recovery drive | Optional | Recommended fallback for the CM311 eMMC deployment. |
| USB-UART adapter | Optional | Serial console for recovery when SSH or HDMI is unavailable. |
| Keyboard and mouse | Optional | Direct CM311 access for recovery and HDMI checks. |

## Architecture

```text
VT03/C5 camera -> wireless link -> VT13 USB receiver
    -> USB Bulk IN 0x81 -> Annex-B parser -> access-unit assembler
    -> PyAV HEVC decoder or native CM311 worker -> BGR frame / KMS display
```

| Module | Responsibility |
|---|---|
| `vt13_video/nal.py` | Annex-B parsing, AU assembly, parameter-set cache, IRAP detection |
| `vt13_video/device.py` | USB discovery, endpoint validation, permission diagnostics |
| `vt13_video/sources.py` | Live USB source and offline capture replay |
| `vt13_video/recovery.py` | Backoff, jitter, healthy-read tracking, reset policy |
| `vt13_video/control.py` | Optional DUML v1 control channel and I-frame requests |
| `vt13_video/decoder.py` | PyAV HEVC decoding, keyframe gating, decoder reset, bounded queue |
| `vt13_video/pipeline.py` | Read/decode loop, recovery, control hooks, recording, statistics |
| `vt13_video/cli.py` | `devices`, `inspect`, `stream`, `replay`, `doctor`, and `config` commands |
| `tools/d3_probe.c` | Canonical native P128 worker source |
| `tools/d3_probe_instrumented.c` | Diagnostic native worker variant |

## Repository layout

```text
vt13_video/        Python package and CLI
tools/             Native worker, replay, benchmark, and analysis tools
config/            Example, kiosk, P128, and fallback configurations
deploy/            systemd, udev, eMMC, and provenance references
udev/              USB permission rule
tests/             Regression suite
examples/          Python API example
live_runs/         Compact tracked validation evidence
captures/          Golden capture and local-only captures
archive/           Historical plans and development notes
docs/              Concise operational and handoff documents
```

## Requirements

### Development host

- Linux with USB sysfs and usbfs (`/dev/bus/usb`).
- Python 3.10 or newer.
- `libusb-1.0` and `ffmpeg` available to PyUSB/PyAV.
- PyUSB, PyAV, NumPy, OpenCV, and PyYAML.
- A display server only if you want the OpenCV preview window.

### CM311 target

- CM311-1S or compatible Amlogic S905L3B board with Armbian aarch64.
- Kernel `6.18.59-ophub` in the verified deployment.
- Custom `meson-vdec` (ca46) and `gxl_hevc.bin` for the native hardware path.
- `gcc` for the native worker; the worker itself depends only on libc.
- systemd for the `vt13-kiosk.service` kiosk deployment.

## Installation

On Ubuntu, install the system dependencies:

```bash
sudo apt-get install -y libusb-1.0-0 ffmpeg
```

Create a virtual environment and install the Python package from the repository
root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Alternatively, install the runtime dependencies directly:

```bash
python -m pip install -r requirements.txt
```

## USB permissions

Install the supplied udev rule, reload rules, and reconnect the receiver:

```bash
sudo cp udev/99-vt13-video.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

The rule grants the active local desktop session access through `uaccess` and
also uses `GROUP="plugdev"` for headless use. `uaccess` may not apply over SSH;
ensure your SSH user is in `plugdev` or replace the rule with an owner/group
rule for your service account.

## Development quickstart

From the repository root, after completing Installation. USB permissions are
only needed for the live USB steps below.

Start with an offline check so that USB permissions and hardware are not
required:

```bash
python -m vt13_video replay \
  --file captures/cold_start/bulk_if0_ep81.bin \
  --headless \
  --save-first /tmp/vt13_first.png \
  --json-stats
```

Run the regression suite:

```bash
python -m unittest discover -s tests -t . -v
```

Check the live hardware path:

```bash
python -m vt13_video doctor
python -m vt13_video devices --json
python -m vt13_video inspect
```

Start a live preview:

```bash
python -m vt13_video stream \
  --config config/vt13_video.yaml \
  --save-first /tmp/vt13_live_first.png
```

For a headless live run, record the stream and write JSON statistics:

```bash
mkdir -p live_runs
python -m vt13_video stream \
  --config config/vt13_video.yaml \
  --headless --seconds 30 \
  --record live_runs/dev_run.bin \
  --json-stats
```

Live USB order matters: start the receiver first, then enable the VT03/C5
transmitter. Wait for complete parameter sets and a fresh IRAP before expecting
decoded frames. If no display server is available, use `--headless` and
`--save-first`.

## Usage

### CLI

```text
vt13-video devices   list matching VT13/C5 USB devices
vt13-video inspect   inspect USB descriptors and endpoints
vt13-video doctor    check dependencies, device, and usbfs access
vt13-video replay    decode a raw capture offline
vt13-video stream    capture and decode live USB video
vt13-video config    show or write configuration
```

Use `python -m vt13_video <command> --help` for all options.

### Offline replay

```bash
python -m vt13_video replay \
  --file captures/cold_start/bulk_if0_ep81.bin \
  --headless \
  --json-stats
```

If a capture lacks parameter sets, prime the cache from a known-good Annex-B
file:

```bash
python -m vt13_video replay \
  --file /tmp/capture_without_params.h265 \
  --parameter-sets-file captures/cold_start/bulk_if0_ep81.bin \
  --headless \
  --json-stats
```

### Python API

```python
from vt13_video import VT13Stream, load_config

config = load_config("config/vt13_video.yaml")
config.output.preview = False

with VT13Stream(config) as stream:
    frame = stream.read_frame(timeout=1.0)
    if frame is not None:
        image = frame.image  # uint8 BGR numpy.ndarray
```

`FileSource(path)` can be passed to `VT13Stream` for offline replay. See
`examples/frame_consumer.py` for a complete example.

### Recording and diagnostics

`--record` writes raw bytes and two sidecars:

- `<stem>.times.tsv`: `elapsed_s`, `chunk_length`, `wall_time_utc`
- `<stem>.events.tsv`: `elapsed_s`, `event`, `detail`, `wall_time_utc`

The sidecars preserve timing and failure evidence without keeping large raw
`.bin` files in Git. `--json-stats` prints link, USB, decode, and recovery
counters. See `live_runs/README.md` for the tracked evidence set.

## Native CM311 worker

The canonical production worker source is `tools/d3_probe.c`; the diagnostic
variant is `tools/d3_probe_instrumented.c`. Keep both.

Build on CM311:

```bash
make exact        # build/d3/d3_probe_p128_exact, production
make instrumented # build/d3/d3_probe_p128_instrumented, diagnostics
```

The exact worker is unstripped and records the source basename. Build it from a
source named `d3_probe.c`; `make exact` handles this. The verified exact binary
SHA256 is:

```text
663f75e09e021b3877ee9da70c543b00fa82742c5f108af4ad6a1e69466285dc
```

The local repository plus `Makefile` and C sources are sufficient to rebuild the
ARM worker; a local ARM binary cache is not required. See
`deploy/P128_BUILD_PROVENANCE.md` for the full recipe and hashes.

The production client is `vt13_video/worker_client.py`;
`vt13_video/worker_client_instrumented.py` is the diagnostic variant.

## Configuration

- `config/vt13_video.yaml` — development defaults.
- `config/vt13_video.kiosk.yaml` — verified CM311 kiosk configuration.
- `config/vt13_video.kiosk.a.yaml` — tested A-worker fallback.
- `config/vt13_video.kiosk.p128.yaml` — P128 reference configuration.

All keys are validated and unknown keys are rejected. Relative paths such as
`record`, `save_first`, `parameter_sets_file`, and `save_parameter_sets` are
resolved against the YAML file's directory.

Important defaults:

- `read.read_size: 2048` — larger reads were associated with frequent EIO on
  the VT13 endpoint; do not increase it without testing.
- `recovery.clear_halt_on_error: true` — clears a halted Bulk IN endpoint after
  recoverable USB errors.
- `decoder.emit_corrupt_frames: false` — corrupt frames are suppressed from the
  frame queue by default.
- `control.enabled` — optional DUML I-frame requests; not required for offline
  replay.

Generate a fresh default file with:

```bash
python -m vt13_video config --write-default config/vt13_video.yaml
```

## Testing

```bash
python -m unittest discover -s tests -t . -v
```

Current local result in this environment: **92 tests, 54 passed, 38 skipped**.
Skipped tests require PyAV, USB hardware, or an environment-specific setup. The suite covers parser
boundaries, AU grouping, parameter-set bootstrap, readiness, replay, recovery,
recording timestamps, YAML validation, USB discovery, and CLI smoke paths.

## Troubleshooting

- `doctor` exits nonzero or the device is missing: check `lsusb -d 2ca3:1020`,
  the udev rule, and `plugdev` membership.
- USB access works locally but not over SSH: `uaccess` is seat-specific; use the
  group rule or add the service account to `plugdev`.
- USB bytes arrive but no frames decode: wait for complete parameter sets and a
  fresh IRAP; power-cycle or relink the VT03/C5 transmitter if needed.
- Preview is blank: run with `--headless --save-first` to verify capture and
  decode independently.
- CM311 manual run fails because the device is busy: `vt13-kiosk.service` owns
  USB/V4L2/DRM while active; stop it only with approval before running manually.
- Frequent EIO or kernel `0xf` aborts: keep `read.read_size: 2048`, preserve the
  journal and capture, and consult `archive/DEVELOPMENT_FLOW_AND_LATENCY.md`.

## Known limitations

- Decoding cannot start from arbitrary P-frames without complete parameter sets
  and a fresh IRAP. Cached parameter sets do not reconstruct missing references.
- The observed stream changes resolution after startup; callers must not assume
  a fixed frame size.
- VT03/C5 does not emit a periodic IRAP in the observed stream. A USB reset does
  not create one; relink or power-cycle the transmitter if recovery stalls.
- `status_drain` and `decoder.stall_restart_s` remain experimental.
- OpenCV preview requires a display server; use `--headless` on headless hosts.
- The CM311 production path depends on the verified ca46 `meson-vdec` module and
  KMS configuration; a generic kernel may use the PyAV software path instead.

## Documentation

- [Agent implementation protocol](AGENTS.md) — safety, approvals, workflow, and
  verification rules.
- [Remote machine usage](docs/REMOTE_MACHINE_USAGE.md) — CM311 access, build,
  deployment, and diagnostics.
- [Development handoff](docs/INTERSESSION_TRANSFER.md) — current baseline and
  open validation.
- [Development flow and latency](archive/DEVELOPMENT_FLOW_AND_LATENCY.md) —
  historical debugging and performance analysis.
- [Archived plans](archive/plans/) — execution and optimization plans.
- [P128 build provenance](deploy/P128_BUILD_PROVENANCE.md) — exact and
  instrumented worker hashes and recipe.
- [CM311 payload manifest](deploy/PAYLOAD_MANIFEST.md) — eMMC deployment
  reference.
- [Live-run evidence index](live_runs/README.md) — tracked validation evidence.

## Related projects

- [rm-receiver](https://github.com/trident-rm/rm-receiver) — reverse-engineered
  receiver implementation derived from the official client; useful for protocol
  and control-behavior comparison.
