# Remote Machine Usage Reference

Status: 2026-11-06 16:46 HKT (read-only inventory and source-authority audit; live USB/decode/display not revalidated)

This document describes how to access and operate the Armbian test machine used
for VT13/HEVC capture and decoder experiments. It is intended as an operational
checklist for later use.

This is a snapshot, not proof that the device is currently idle or that USB,
V4L2, decoding, or HDMI output is working. Re-run the read-only checks before a
live session. The three project-control documents are `AGENTS.md`, this file,
and `docs/INTERSESSION_TRANSFER.md`; update the transfer file at the end of every
session.

## Connection details

- SSH host: `10.42.0.11`
- SSH port: `22`
- User: `billieguo`
- Password: `020816`
- Sudo password: same as the SSH password

> The password is recorded here for convenience. If this repository is shared,
> move it to an environment variable or install an SSH key.

> From the Codex workspace sandbox, SSH may fail with `socket: Operation not
> permitted`. Rerun the same read-only command with network escalation; do not
> assume the host is down.

## Interactive access

```bash
ssh billieguo@10.42.0.11
```

Interactive SSH allocates a PTY. `sudo` can prompt for the password normally:

```bash
sudo dmesg
```

This is the preferred way for manual debugging.

## Automated or non-interactive access

`ssh -T` does not allocate a remote TTY. Plain `sudo` then fails with:

```text
sudo: a terminal is required to read the password
sudo: a password is required
```

Use one of these patterns instead.

### Force a PTY

```bash
ssh -tt billieguo@10.42.0.11
```

Or, for a single command:

```bash
ssh -tt billieguo@10.42.0.11 'sudo dmesg'
```

### Feed the sudo password on stdin

```bash
printf '%s\n' '020816' | ssh -T billieguo@10.42.0.11 'sudo -S dmesg'
```

The password is consumed by remote `sudo`, so avoid this pattern when the
remote command also needs stdin.

### Local askpass helper

`sshpass` is not installed on the local workstation. For automated SSH from
Codex or a script, use OpenSSH's `SSH_ASKPASS` support:

```bash
ASKPASS=/tmp/ssh-askpass-codex
printf '%s\n' '#!/bin/sh' 'printf "%s\n" "$SSH_PASSWORD"' > "$ASKPASS"
chmod 700 "$ASKPASS"

SSH_PASSWORD='020816' \
SSH_ASKPASS="$ASKPASS" \
SSH_ASKPASS_REQUIRE=force \
DISPLAY=:0 \
ssh -T billieguo@10.42.0.11 'hostname'
```

For a persistent PTY-backed session, start SSH with `-tt` (or use a PTY in the
calling tool), keep the session open, and send commands to it. This preserves
the working directory and environment between commands.

## System profile

Read-only inventory snapshot on 2026-11-06 15:52 HKT:

- Hostname: `armbian`
- Board: `Aml.S905l3b` (previous record; not rechecked in this inventory)
- OS: Armbian OS 26.11.0 based on Ubuntu 24.04 LTS (Noble), `aarch64`
- Kernel: `6.18.59-ophub`
- CPU: 4 cores
- Memory: 1.7 GiB total; 417 MiB used; 1.3 GiB available
- Swap: 1.0 GiB total; 0 B used; 1.0 GiB free
- Root filesystem: `/dev/sda2`, 115 GB total, 8.2 GB used, 107 GB available
- `/tmp`: 894 MiB tmpfs, 12 KiB used
- Uptime: 29 minutes; 2 users; load average 0.17, 0.14, 0.19
- Commands present: `python3`, `ffmpeg`, `ffprobe`, `v4l2-ctl`, `tmux`, `rsync`, `git`, `sha256sum`
- Video node: `/dev/video0` exists, mode `crw-rw----+ root video`; presence does not prove it is free or functional

## Important paths

- `~/mobile_vt` — working tree for capture, analysis, and decoder experiments.
  The directory exists and `python3 -m vt13_video --help` exits 0. Its `.git`
  directory exists, but `git status` currently fails with `fatal: not a git
  repository`; do not treat it as a valid Git baseline yet. A 2026-11-06
  source/config/test SHA256 comparison found 24 local entries versus 27 remote
  entries; see the source hash comparison below.
- `/tmp/dji_test_latest_dir` — **missing** on 2026-11-06 15:52 HKT. Do not
  assume a latest capture exists; use an explicit capture root or re-create the
  pointer with approval.
- `~/mobile_vt/captures/cold_start/bulk_if0_ep81.bin` — exists on CM311,
  2,431,249 bytes, SHA256
  `d4cec190f35eac9b32944aff0b32ca501d54e451c1e7e0c800ab10cbdd5aa698`.
  This matches the local copy checked on 2026-11-06.
- `~/mobile_vt/live_runs/vt13_params.h265` — exists on CM311, 102 bytes,
  SHA256 `f9f019a14e2fc2990863221cca5bd1187cf3898dceb38277ba2b86194f94887f`.
  The local copy has the same size and SHA256.
- `$OUT/analysis/poc50_isolation` — POC isolation artifacts under the capture
  root named by `/tmp/dji_test_latest_dir`; currently unresolved because the
  pointer is missing.
- `/usr/bin/ffmpeg` — system FFmpeg 6.1.1-3ubuntu5.
- `~/ffmpeg-6.1.1-v4l2/ffmpeg` — custom FFmpeg; verified executable on
  2026-11-06 as `ffmpeg version n6.1.1`. Its configuration includes
  `--enable-decoder=hevc_v4l2m2m --enable-demuxer=hevc --enable-parser=hevc
  --enable-muxer=null --enable-debug=2`. This verifies binary identity, not
  decode correctness.
- `~/ffmpeg-6.1.1-v4l2/install` — install prefix for the custom build.

## Source authority (user-confirmed 2026-11-06)

- **CM311 `~/mobile_vt`** is the latest experimental source tree because most
  decoder and latency experiments were performed there. “Latest” does not mean
  production-ready, and it does not mean every individual file is newer than
  the PC copy.
- **Ubuntu PC `mobile_vt`** is the workable software-decode baseline. It has the
  local 50-test regression baseline and the reproducible software-decode path.
- Do not overwrite either tree wholesale. Merge per file, preserve the PC
  software-decode baseline, treat CM311 as the latest experiment reference, and
  verify both sides with tests and SHA256/commit evidence.

## Current source-tree modification snapshot

Read-only Git status on 2026-11-06:

- `~/linux-6.18-vdec`: HEAD `0e80ef956`; modified
  `drivers/staging/media/meson/vdec/codec_hevc.c` and
  `drivers/staging/media/meson/vdec/vdec_platform.c`; many untracked `.bak` and
  `.before-*` files. Do not treat the whole modified file as a release fix.
- `~/ffmpeg-6.1.1-v4l2`: HEAD `e38092e`; modified
  `libavcodec/v4l2_buffers.c`, `libavcodec/v4l2_m2m.c`, and
  `libavcodec/v4l2_m2m_dec.c`. These include refcount/Copy-Out/diagnostic work;
  correctness and CPU cost still need validation.

### Source hash comparison (read-only, 2026-11-06)

A SHA256 comparison of `vt13_video`, `tests`, `config`, `examples`, `udev`,
`pyproject.toml`, `requirements.txt`, and `README.md` found:

- 24 local entries versus 27 remote entries.
- Remote-only files: `config/vt13_video.no_status.yaml`,
  `config/vt13_video.yuvtest.yaml`, and `vt13_video/async_usb.py`.
- Differing files: `README.md`, `vt13_video/decoder.py`, and
  `vt13_video/pipeline.py`.
- Remaining compared files matched.

Conclusion: the local and remote source trees are **not currently identical**.
The authority decision is now recorded above; merge per file rather than copying
either tree wholesale.

### Observed experimental divergence (read-only, 2026-11-06)

- `vt13_video/async_usb.py` is remote-only. It is a bounded experimental USB
  prefetcher controlled by `VT13_ASYNC_USB` and `VT13_ASYNC_CHUNKS`; the default
  16,384-chunk queue is about 32 MiB at 2,048 bytes/chunk. It is described in
  the file as a diagnostic, not a real-time guarantee.
- `vt13_video/decoder.py` adds a PyAV thread experiment controlled by
  `VT13_AV_THREADS` and `VT13_AV_THREAD_TYPE`.
- `vt13_video/pipeline.py` adds the async-source wrapper and a low-latency
  stale-AU catch-up path controlled by `VT13_LOW_LATENCY_MS`; when active it
  resets decoding and waits for a fresh IRAP.
- `config/vt13_video.no_status.yaml` sets `status_drain: false`.
- `config/vt13_video.yuvtest.yaml` sets `output_format: gray` and
  `preview: false`.
- `README.md`: the PC copy contains the remote-machine documentation link; the
  CM311 copy does not. File-level freshness differs, so do not infer authority
  from one directory timestamp.

### Remote offline test snapshot (2026-11-06 16:46 HKT)

Command on CM311: `python3 -m unittest discover -s tests -t . -v`.

- Result: 50 tests run in 63.185 s; 49 passed, 1 error; process RC=1.
- Error: `test_allow_corrupt_frames_controls_pyav_output_flag` accesses
  `av.codec.context.Flags.output_corrupt`, but the installed PyAV `11.0.0`
  exposes only `Flags.OUTPUT_CORRUPT`.
- Local `rm` environment uses PyAV `17.1.0`, where the lowercase name exists.
  Treat this as a test/PyAV-version compatibility issue, not proof that the
  experimental decoder is broken. The decoder itself uses
  `getattr(..., "output_corrupt", 1 << 3)`, which is compatible with both names.

## Validation Needed

The following are not proven by the read-only inventory. Check them before any
live run, driver change, or FFmpeg experiment.

| Item | Status on 2026-11-06 | Evidence needed |
|---|---|---|
| Latest capture pointer | Missing | `test -f /tmp/dji_test_latest_dir`; explicit capture root; do not guess |
| Idle/ownership | Not enumerated by this session | `ps`, `pgrep`, `fuser`/`lsof` for `/dev/video0`; do not kill |
| Display stack | Not checked | `ls /dev/dri`, `DISPLAY`, `loginctl`, physical HDMI output |
| `vt13_video` stream/READY | Only `--help` checked | Real `stream` command, READY/LISTENING log, exit method |
| `/dev/video0` function | Node exists only | `v4l2-ctl --all`; meson-vdec binding; no conflicting opener |
| Custom FFmpeg decode | Binary/version verified | `-decoders` check; actual `hevc_v4l2m2m` decode; frame comparison |
| Kernel module/VDEC | Not checked | `uname -r`, `lsmod`, module vermagic, `dmesg`, `status=0x8/0xf` |
| Source Change/POC50/EOF | Historical only | Controlled offline and target-board short tests |
| Live wireless end-to-end | Not started | AGENTS.md §6 handoff; READY before human opens link |
| Performance/latency targets | User targets unconfirmed | User acceptance plus CM311 CPU/RSS/temperature/latency evidence |
| Local/remote source consistency | **Authority documented; trees still divergent**: CM311 is latest experimental, PC is workable software-decode baseline; 24 local vs 27 remote entries; remote-only `async_usb.py` and two config files; `README.md`, `decoder.py`, `pipeline.py` differ | Per-file merge/review; Git commit/diff or full SHA256 manifest; test both sides |
| Remote test/PyAV compatibility | 49/50 pass; PyAV 11.0.0 exposes `OUTPUT_CORRUPT`, while the test expects lowercase `output_corrupt` | Fix the compatibility test or pin PyAV; rerun all tests and record RC |

## Code and data consistency checks

Before copying files between the Ubuntu PC and CM311, or before claiming that a
remote run uses the local source/data:

1. Record the source and destination hosts, absolute paths, Git commit,
   `git status --short`, and relevant `git diff` on both sides.
2. Record file size, mtime, and SHA256 for each transferred file.
3. Preview with `rsync -avhn` before a real copy; never overwrite a golden
   capture or a running binary without approval.
4. After copying, recompute SHA256 and size on the destination and compare.
5. For binaries, also compare architecture and linkage (`file`, `readelf -h`,
   `ldd`) as applicable.
6. Write the result, including expected divergence, into
   `docs/INTERSESSION_TRANSFER.md`.

Use a repository-local temporary directory such as `.codex_tmp/<step>/` for
fetched copies, manifests, and diff artifacts. Avoid leaving project data in
`/tmp` unless the project directory is not writable or a tool requires it.

If either tree lacks valid Git metadata, use an explicit SHA256 manifest for the
source files instead of assuming that matching directory names mean matching
code.

## Common operations

### Inspect the machine

```bash
hostname
cat /etc/os-release
uname -a
nproc
free -h
df -h /
uptime
```

### Inspect the latest capture

```bash
if [ -f /tmp/dji_test_latest_dir ]; then
  OUT=$(cat /tmp/dji_test_latest_dir)
  DIR="$OUT/analysis/poc50_isolation"
  ls -l "$DIR"
else
  echo "MISSING: /tmp/dji_test_latest_dir; choose an explicit capture root"
fi
```

### Software HEVC decode

```bash
/usr/bin/ffmpeg \
  -hide_banner -nostdin \
  -loglevel warning \
  -threads 1 -c:v hevc \
  -f hevc -i "$DIR/fresh_45_to_82.h265" \
  -f null -
```

### Hardware HEVC decode

```bash
ulimit -c 0
timeout -s TERM -k 2s 15s "$HOME/ffmpeg-6.1.1-v4l2/ffmpeg" \
  -hide_banner -nostdin \
  -loglevel info -stats \
  -c:v hevc_v4l2m2m \
  -f hevc -i "$DIR/fresh_45_to_82.h265" \
  -f null -
```

### Trace slice headers

```bash
/usr/bin/ffmpeg \
  -hide_banner -nostdin \
  -loglevel trace \
  -f hevc -i "$DIR/poc50_to36.h265" \
  -map 0:v:0 -c:v copy \
  -bsf:v trace_headers \
  -f null - \
  2> "$DIR/poc50_to36.trace"

grep 'slice_pic_order_cnt_lsb' "$DIR/poc50_to36.trace" | tail -4
```

### Kernel decoder logs

Interactive SSH:

```bash
sudo dmesg | grep -Ei \
  'Missing L[01] reference|HEVC_LCU_CHECK status=0xf|HEVC_DBG unexpected|Aborting'
```

Follow live:

```bash
sudo dmesg -w
```

Non-interactive equivalent:

```bash
printf '%s\n' '020816' | ssh -T billieguo@10.42.0.11 \
  'sudo -S dmesg | grep -Ei "Missing L[01] reference|HEVC_LCU_CHECK status=0xf|HEVC_DBG unexpected|Aborting"'
```

## HEVC POC isolation workflow

The following script patches the POC LSB of the last two TRAIL_R NAL units
(assumed POC50 and POC55) and writes two variants under the latest capture's
`analysis/poc50_isolation` directory.

```bash
cd ~/mobile_vt
OUT=$(cat /tmp/dji_test_latest_dir)
export OUT

python3 - <<'PY'
from pathlib import Path
import os, re

root = Path(os.environ["OUT"])
folder = root / "analysis/poc50_isolation"
src = folder / "fresh_45_to_82.h265"

original = src.read_bytes()

def read_bits(data, byte_offset, bit_offset, nbits):
    result = 0
    for i in range(nbits):
        pos = bit_offset + i
        b = data[byte_offset + pos // 8]
        bit = (b >> (7 - pos % 8)) & 1
        result = (result << 1) | bit
    return result

def write_bits(data, byte_offset, bit_offset, nbits, value):
    for i in range(nbits):
        pos = bit_offset + i
        idx = byte_offset + pos // 8
        mask = 1 << (7 - pos % 8)
        bit = (value >> (nbits - 1 - i)) & 1
        if bit:
            data[idx] |= mask
        else:
            data[idx] &= ~mask

nals = []
for m in re.finditer(b"\x00\x00\x00\x01|\x00\x00\x01", original):
    pos = m.end()
    if pos + 4 > len(original):
        continue
    typ = (original[pos] >> 1) & 63
    if typ == 1:
        nals.append(pos)

assert len(nals) >= 2
targets = nals[-2:]

assert read_bits(original, targets[0], 21, 8) == 50
assert read_bits(original, targets[1], 21, 8) == 55

variants = {
    "poc50_to36": [(0, 36)],
    "poc50_to36_poc55_to37": [(0, 36), (1, 37)],
}

for name, patches in variants.items():
    data = bytearray(original)
    for idx, new_poc in patches:
        old_poc = read_bits(data, targets[idx], 21, 8)
        write_bits(data, targets[idx], 21, 8, new_poc)
        assert read_bits(data, targets[idx], 21, 8) == new_poc
        print(name, old_poc, "->", new_poc)

    dst = folder / f"{name}.h265"
    dst.write_bytes(data)
    assert len(data) == len(original)
    print("Created:", dst)
PY
```

Then run the trace, software, and hardware decode checks from the sections
above. The hardware decoder is expected to abort with `HW_RC=134` and emit
`HEVC_LCU_CHECK status=0xf` / `HEVC_DBG unexpected` / `Aborting decoding
session` messages when the reference chain is inconsistent.

## Troubleshooting

- `Permission denied (publickey,password)` — use the correct username and
  password, or configure an SSH key.
- `sudo: a terminal is required` — use interactive SSH, `ssh -tt`, or
  `sudo -S` with the password on stdin.
- `Could not find ref with POC ...` — software decoder detected a missing
  reference; inspect the POC trace and the kernel log.
- `HW_RC=134` — the hardware decoder aborted. Check `sudo dmesg` for the
  `meson-vdec` messages.
- `/tmp/dji_test_latest_dir` missing or stale — confirm that a new capture was
  completed and that the file was updated.
