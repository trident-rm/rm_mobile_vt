# Remote Machine Usage Reference

Status: 2026-11-08 03:00 HKT (source meson_vdec loaded; HEVC advertised; clean 30-frame hardware decode 29/30 FrameMD5 match; expanded sample matrix completed; `aud` EOF repeat stable within one window at 19 frames; POC21/POC50 `0xf`, padding content differences, and EOF drain failures documented; offline tests/analysis no longer require approval)

This document describes how to access and operate the Armbian test machine used
for VT13/HEVC capture and decoder experiments. It is intended as an operational
checklist for later use.

This is a snapshot, not proof that the device is currently idle or that USB,
V4L2, decoding, or HDMI output is working. Re-run the read-only checks before a
live session. The three project-control documents are `AGENTS.md`, this file,
and `docs/INTERSESSION_TRANSFER.md`; update the transfer file at the end of every
session.

Approval policy (user decision 2026-11-06): offline testing and analysis on the
Ubuntu PC or CM311 do **not** require per-run human approval. This includes
offline `hevc_v4l2m2m` decode, FFmpeg/V4L2 short tests, and read-only analysis.
Before running one, confirm the target device/process is not occupied, use a
bounded `timeout`, write to a step-specific or run-specific directory, do not
overwrite golden data, and record the command, RC, and evidence. Starting a
real-time USB receiver/HDMI display, stopping unrelated services, or reloading a
kernel module still follows the R2/R3 rules in `AGENTS.md`.

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
- Hardware-decode precheck 17:54 HKT: `/dev/video0` had no opener from `fuser`, `pgrep`, or `lsof`; `meson_vdec` was loaded with vermagic `6.18.59-ophub`; custom FFmpeg exposed both `hevc` and `hevc_v4l2m2m`; no live stream was started
- R3 module reload 18:50 HKT: stock `meson_vdec` was unloaded and the source-built module was loaded. `v4l2-ctl --list-formats-out` now lists `HEVC` first. The module remains loaded until reboot or manual restore to stock.
- Offline hardware-decode verification 19:32 HKT: with `-vsync 0`, software and hardware each produced 30 frames with RC=0. FrameMD5 matched for 29/30 frames; the only mismatch is frame index 29 (software `133559bb...`, hardware `1517d50f...`). This is an unresolved last-frame/EOF difference, not proof of complete decode correctness. The sample did not exhibit `status=0xf`.
- 2026-11-07 EOF hardware tests 20:27-20:45 HKT: software decode of `test_eof_aud.h265`, `test_eof_eos.h265`, and `test_eof_zeros1024.h265` each produced 27 frames RC=0 with identical SW FrameMD5 SHA256 `da3a69dc68bde16d749471fa89e6dceb4bcbf4418995fda1fd691899744fc695`.
- Full-EOF hardware under `timeout -k 5 45` gave `aud` and `zeros` RC=137, `eos` RC=134, and 0 persisted frames when output was not flushed. With `-flush_packets 1 -pix_fmt yuv420p`, `aud` emitted 22 frames (all matching SW), `eos` 20 (all matching), and `zeros1024` 27 (26/27 matching). `zeros1024` repeated 3x RC=0/27 with identical FrameMD5 SHA256 `03d78cb97121b4ef875f79ced2c6beb9a00c028cd6ad485c1c88b73e8bea5866`, but the last frame differs from SW (`bf20bb...` vs `6652eaf...`). `-frames:v` stopped `aud` at 22 and `eos` at 20, both fully matching; `zeros1024` remained 26/27. Root cause is unverified.

- 2026-11-08 00:51 HKT precheck: CM311 idle (`/dev/video0` had no `fuser` opener; no `vt13_video`/`ffmpeg` process); source `meson_vdec` remains loaded; custom FFmpeg `n6.1.1` present; `/tmp/dji_test_latest_dir` still missing. All seven target sample files exist and their SHA256 values match the recorded baseline. Expanded hardware matrix not yet run.

- 2026-11-08 01:09-01:11 HKT expanded hardware matrix: all runs used `-fps_mode passthrough`; hardware used `-flush_packets 1` and `timeout -k 5 45`. `clean` SW/HW 30 frames RC=0 with 29/30 FrameMD5 match (index 29 differs). `no_sei` SW 132 frames RC=0; HW aborted at POC21 with `status=0xf` RC=134 after 14 frames, all matching the SW prefix. `fresh_45_to_82` SW 38 frames RC=0; HW aborted at POC50 with `status=0xf` RC=134 after 32 frames, all matching the SW prefix. `pad_1024` HW 38 frames RC=0 but only 36/38 matched (first mismatch index 36); driver logs showed `status=0x8` and two missing-reference substitutions. EOF: `aud` RC=137 with 18 matching frames (later 3x repeat: 19 frames, identical; cross-window 22/18/19), `eos` RC=134 with 20 matching frames, `zeros1024` RC=0 with 27 frames and 26/27 matching. All three EOF SW references remained identical.

- 2026-11-08 02:57-03:00 HKT `test_eof_aud` repeat: 3 hardware runs all RC=137, 19 frames, identical FrameMD5 SHA256 `b8fb5b532a15815f5fa57c5f20f85bd48a83b5d7ac0684e8fce8a7bc1c4c4000`, and 19/19 matched SW. Across windows the emitted count was 22 (prior), 18 (matrix), 19 (repeat); within-window output was stable, but the timeout cutoff/frame count varies. Evidence: `~/mobile_vt/.codex_tmp/cm311_eof_aud_repeat_20261108_025726/`; local copy under the same relative path. Final hashes: `summary.txt` `98f7e5352841148ca3d83e2750420d6428f140e5f295c3fd8c21a23a892b0eba`, `summary.json` `76b36ddd6a30284a90c4986f9635d6449c40b4def6f05afd1725aa029b3e3485`, `run.log` `87b9fcac048c328335eaef91eaf5874101e02767a362fc6ac6a1723b8bf68a85`, `sample.sha256` `693bc993763f7404966f8611ba6fc3fe9c494d94401ed1e5a34efb93c2a4bad0`, `status.txt` `f6c02eeadf401ed2ca5479658433ed6a4fd1747151d383fe0eae926284afb360`.

- 2026-11-08 03:51 HKT post-run check: no `ffmpeg`/`vt13_video` process, `/dev/video0` free, source `meson_vdec` loaded; no live USB/HDMI/wireless run.

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
- `~/mobile_vt/captures/hw_test/clean_1832x1032.h265` — 698,640 bytes, SHA256
  `2e13db183d5e562094e2952b169f3486cfaad5221b5a4ec8d97ff152f2a7d5bb`.
  Software decode produced 30 frames with RC=0 and no missing-reference
  messages. Hardware decode with `-vsync 0` and the 2026-11-08
  `-fps_mode passthrough` re-run both produced 30 frames RC=0 and 29/30
  FrameMD5 matches; only frame index 29 differs. The last-frame difference
  remains unresolved.
- `/lib/modules/6.18.59-ophub/kernel/drivers/staging/media/meson/vdec/meson-vdec.ko`
  — stock module, not currently loaded, 225,216 bytes, SHA256
  `a6cc08ca2598caf378881a85515c211e8fc41e6bc870753e5d11a3942458f198`.
  It does not declare `meson/vdec/gxl_hevc.bin`.
- `~/linux-6.18-vdec/drivers/staging/media/meson/vdec/meson-vdec.ko` — source-built
  custom module, 5,550,816 bytes, SHA256
  `ca46798328e0975290151c40e1ddbf191a277b563a9694344aca910507aacdab`.
  Vermagic matches `6.18.59-ophub`; it declares `meson/vdec/gxl_hevc.bin`.
  It is currently loaded after the approved R3 reload; restore stock explicitly
  if needed.
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
- `~/mobile_vt/.codex_tmp/cm311_eof_compare_kill_20261107_202711/` — full-EOF
  comparison evidence; summary SHA256
  `e281ce7c41c1c40dce06ac55cfb52342ab23ef9cf895ab1bf6188ddd9d25b563`.
- `~/mobile_vt/.codex_tmp/cm311_eof_hw_i420_20261107_203517/` — preserved
  partial output with `-flush_packets 1 -pix_fmt yuv420p`; summary SHA256
  `4c376e541e9112f7029ba64b0de126f07be86f569c1bb949bb232468209f81c2`.
- `~/mobile_vt/.codex_tmp/cm311_eof_zeros_repeat_20261107_203813/` — three
  repeated `zeros1024` hardware runs with flush; summary SHA256
  `aecb9dfabfb57f9b1a9a4cc95092184df48aad5cfb81bb9d86120fdcd0361f2f`.
- `~/mobile_vt/.codex_tmp/cm311_eof_zeros_noflush_20261107_204129/` — three
  repeated `zeros1024` runs without flush; summary SHA256
  `1d65f50e29f38f4b72b03d3fd27f1a8426e0b122036b6df59fa6d43e6bf6221a`.
- `~/mobile_vt/.codex_tmp/cm311_eof_framelimit_20261107_204504/` — pre-EOF
  `-frames:v` comparison; summary SHA256
  `b194ed279febac6e8367182c928a8fccca1e82468e4a95454fe0be61a1f23fc2`.
- `~/mobile_vt/.codex_tmp/cm311_hw_samples_20261108_010902/` — expanded
  software/hardware matrix. Final local and remote SHA256 values matched for
  `summary.txt` `a9625216c57f6069f6bda3d55d303e6038f486c42f3fdebc603346d5392c0b23`,
  `summary.json` `4b7f9082cbc9a02f3b62b3542ab7d5f24059520309e45d521d4591cb4756520a`,
  `run.log` `0330e2840e48a30c24708b47a53bd6153e3d1b49499bc7d84ae5a5e32c56ae1b`,
  `samples.sha256` `c1ec1b1e1119d779a4df03e71ec78cac40deb212caa69e7721014ba7ff22a5ad`,
  and `status.txt` `18a55e47438912b7e08798d6e9df1ee9942d352666ff55360cb444f6ea56be11`.
  A local copy is under the same relative path in this repository.
  Full local/remote manifest comparison: 74 files matched; manifests are under
  `.codex_tmp/manifests_20261108/cm311_hw_samples_20261108_010902.*.sha256`.
- `~/mobile_vt/.codex_tmp/cm311_eof_aud_repeat_20261108_025726/` — `aud` EOF
  repeat evidence; local and remote final hashes matched. See the run summary
  for the 3x RC/frame/FrameMD5 results and the final artifact hashes. Full
  local/remote manifest comparison: 29 files matched; manifests are under
  `.codex_tmp/manifests_20261108/cm311_eof_aud_repeat_20261108_025726.*.sha256`.

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
| Idle/ownership | Confirmed idle at 2026-11-08 00:51 HKT: no `vt13_video`/`ffmpeg` process and no `/dev/video0` opener; source `meson_vdec` remains loaded; expanded hardware matrix ran 01:09-01:11 HKT | Re-check immediately before a live or hardware run; do not kill |
| Display stack | Not checked | `ls /dev/dri`, `DISPLAY`, `loginctl`, physical HDMI output |
| `vt13_video` stream/READY | Only `--help` checked | Real `stream` command, READY/LISTENING log, exit method |
| `/dev/video0` function | Source `meson-vdec` loaded; V4L2 output formats include `HEVC`; clean and EOF offline hardware runs executed | `v4l2-ctl --all`; meson-vdec binding; no conflicting opener |
| Custom FFmpeg decode | 2026-11-08 `-fps_mode passthrough`: clean 30 frames RC=0, 29/30; `no_sei` POC21 `0xf` RC=134, 14-frame prefix all matching; `fresh_45_to_82` POC50 `0xf` RC=134, 32-frame prefix all matching; `pad_1024` 38 frames RC=0, 36/38; EOF `aud` 3x repeat all RC=137/19 frames and identical (cross-window counts 22/18/19), `eos` 20 frames RC=134, `zeros` 27 frames 26/27 | Explain/fix `0xf`, padding mismatch, and EOF drain; explain `aud` cross-window timeout count; add more real samples |
| Kernel module/VDEC | R3 loaded source module (`ca46...`) with matching vermagic; HEVC advertised; 2026-11-08 dmesg shows `status=0x8` and `status=0xf` (POC21 for `no_sei`, POC50 for `fresh`); `pad` shows only `0x8` plus two missing-reference substitutions | `uname -r`, `lsmod`, module vermagic, `dmesg`, `status=0x8/0xf`; explain EOF state machine |
| Source Change/POC50/EOF | 2026-11-08 expanded matrix: EOF SW 27 frames remains identical; HW `aud`/`eos` drain failed, `zeros` 26/27; `pad_1024` RC=0 but 36/38 (first mismatch index 36); `aud` same-window 3x was 19 frames and identical, but cross-window counts were 22/18/19 | Explain/fix EOF drain/flush and `0xf`; explain timeout-window frame-count variation; validate padding content differences |
| Live wireless end-to-end | Not started | AGENTS.md §6 handoff; READY before human opens link |
| Performance/latency targets | User targets unconfirmed | User acceptance plus CM311 CPU/RSS/temperature/latency evidence |
| Local/remote source consistency | **Authority documented; trees still divergent**: CM311 is latest experimental, PC is workable software-decode baseline; 24 local vs 27 remote entries; remote-only `async_usb.py` and two config files; `README.md`, `decoder.py`, `pipeline.py` differ | Per-file merge/review; Git commit/diff or full SHA256 manifest; test both sides |
| Remote test/PyAV compatibility | 49/50 pass; PyAV 11.0.0 exposes `OUTPUT_CORRUPT`, while the test expects lowercase `output_corrupt` | Fix the compatibility test or pin PyAV; rerun all tests and record RC |

A green Python test suite (`RC=0`) is a regression gate, not proof of hardware
decode. The primary acceptance evidence remains an actual CM311
`hevc_v4l2m2m` decode with frame comparison (V07/V08). The 2026-11-07 EOF tests
localize a real failure/difference to EOF drain/flush; they do not close V09.

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
timeout -k 5 45 "$HOME/ffmpeg-6.1.1-v4l2/ffmpeg" \
  -hide_banner -nostdin \
  -loglevel info -stats \
  -c:v hevc_v4l2m2m \
  -f hevc -i "$DIR/fresh_45_to_82.h265" \
  -f null -
```

`-c:v hevc_v4l2m2m` must appear before `-i`. Placing it after the input makes
FFmpeg interpret it as an output encoder. For FrameMD5 comparison, use the
following bounded command; `-flush_packets 1` preserves frames already decoded
when a hang is killed, but it is a diagnostic aid, not an EOF fix:

```bash
SAMPLE="$DIR/test_eof_aud.h265"
OUT="$RUN_DIR/test_eof_aud.hw.framemd5"
ulimit -c 0
timeout -k 5 45 "$HOME/ffmpeg-6.1.1-v4l2/ffmpeg" \
  -hide_banner -nostdin -loglevel info \
  -c:v hevc_v4l2m2m -f hevc -i "$SAMPLE" \
  -map 0:v:0 -fps_mode passthrough -pix_fmt yuv420p \
  -c:v rawvideo -flush_packets 1 -f framemd5 "$OUT"
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
- `HW_RC=137` — the hard timeout killed the hardware process, commonly while it
  is stuck in EOF drain. Use `timeout -k`; inspect the tail of the log and
  dmesg. An empty `framemd5` can mean buffered output was lost, not necessarily
  that no frame was decoded.
- `HW_RC=134` — the hardware decoder aborted. Check `sudo dmesg` for the
  `meson-vdec` messages; EOF samples can hit
  `Assertion pkt failed at fftools/ffmpeg_dec.c:597`.
- `-frames:v` stops before EOF drain and can make a hanging sample exit 0; do
  not treat that as proof that EOF handling is fixed.
- `/tmp/dji_test_latest_dir` missing or stale — confirm that a new capture was
  completed and that the file was updated.
