# Intersession Transfer: VT13 / CM311

Status: 2026-11-06 16:46 HKT

Scope of this entry: documentation, read-only inventory, source-authority
decision, and experimental-code diff audit. No live USB stream, V4L2 decode,
HDMI display, or wireless-link test was started.

## Purpose and maintenance contract

This is the third project-control document. Read it together with `AGENTS.md`
and `docs/REMOTE_MACHINE_USAGE.md` at the start of every session. At the end of
every session and after every verifiable step, update this file with:

- host(s), exact commands, exit codes, and time window
- files changed and Git commit/diff state
- evidence paths and whether they are local or remote
- `verified`, `experimental workaround`, or `unverified` status
- validation-needed items and the evidence that would close them
- human approvals and the next single action

Do not delete older entries. Add a dated entry and update the current
validation-needed table. Do not claim that local and remote code/data are
consistent without a Git commit/diff comparison or an explicit SHA256 manifest.

All temporary copies and analysis artifacts belong under `.codex_tmp/<step>/`
inside this repository. Record the path in this file; `.codex_tmp/` is ignored by
Git and must not overwrite original captures or golden data.

## Current session summary (2026-11-06)

Read-only work completed:

- Read `AGENTS.md` and `docs/REMOTE_MACHINE_USAGE.md`.
- Confirmed the local CLI surface with `python3 -m vt13_video --help` and each
  subcommand's `--help`; all returned RC=0.
- Confirmed the local base Python is not sufficient for decode:
  `/home/billieguo/miniconda3/bin/python3` is 3.13.5 and lacks `av`.
- Confirmed the intended local runtime:
  `/home/billieguo/miniconda3/envs/rm/bin/python` is 3.10.20 with `av` 17.1.0,
  `pyusb` 1.3.1, `cv2` 5.0.0, `numpy` 2.2.6, and `yaml` 6.0.3.
- Performed a read-only CM311 inventory over SSH to `billieguo@10.42.0.11`.
  The sandbox initially blocked the connection with `socket: Operation not
  permitted`; the same command succeeded with network escalation.
- Confirmed CM311 identity: `armbian`, kernel `6.18.59-ophub`, `aarch64`,
  Armbian OS 26.11.0 / Ubuntu 24.04 Noble, 4 CPU cores, 1.7 GiB RAM.
- Confirmed CM311 paths exist: `~/mobile_vt`, `~/linux-6.18-vdec`, and
  `~/ffmpeg-6.1.1-v4l2`.
- Confirmed CM311 commands exist: `python3`, `ffmpeg`, `ffprobe`, `v4l2-ctl`,
  `tmux`, `rsync`, `git`, and `sha256sum`.
- Confirmed `/dev/video0` exists; this is not proof that it is free or working.
- Confirmed CM311 `python3 -m vt13_video --help` returns RC=0 from
  `~/mobile_vt`; no `stream` run was started.
- Confirmed `/tmp/dji_test_latest_dir` is currently missing on CM311.
- Confirmed the local and remote golden capture and parameter-set files have
  matching sizes and SHA256 values (see the data manifest below).
- Compared source/config/test SHA256 manifests and found that the trees are
  **not identical**: 24 local entries versus 27 remote entries. The remote tree
  has `config/vt13_video.no_status.yaml`, `config/vt13_video.yuvtest.yaml`, and
  `vt13_video/async_usb.py`; `README.md`, `vt13_video/decoder.py`, and
  `vt13_video/pipeline.py` differ. The remaining compared files matched.
- Confirmed the custom CM311 FFmpeg executable reports `ffmpeg version n6.1.1`
  with the expected `hevc_v4l2m2m` build configuration.
- Re-read all three project-control documents before this step.
- Fetched the remote-only/differing experimental files into the repository-local
  temporary directory `.codex_tmp/cm311_latest_20261106/` for read-only diffing.
- User confirmed the authority split: CM311 holds the latest experimental code;
  the Ubuntu PC copy is the workable software-decode baseline.
- Ran the CM311 offline test suite: 50 tests in 63.185 s, 49 passed, 1 error,
  RC=1. The error is a PyAV API-name mismatch: CM311 has PyAV 11.0.0 with
  `Flags.OUTPUT_CORRUPT`, while the test accesses lowercase `output_corrupt`.
- Characterized the experimental divergence: remote-only `async_usb.py`, PyAV
  thread experiment in `decoder.py`, async USB and low-latency catch-up paths in
  `pipeline.py`, plus two extra test configs. The PC `README.md` has a newer
  documentation link than the CM311 copy, so file-level freshness is mixed.
- No package was installed, no service was restarted, and CM311 was not
  rebooted by this session.

Documentation and repository changes made in this session:

- Updated `AGENTS.md` with the mandatory local/cross-machine consistency rule,
  the three-document maintenance contract, and a validation-needed table.
- Updated `docs/REMOTE_MACHINE_USAGE.md` with the current read-only snapshot,
  missing latest-capture pointer, source-tree modification snapshot, validation
  checklist, and consistency-check procedure.
- Added this intersession transfer file.
- Initialized the local project directory as a Git repository and created the
  initial baseline commit `a5909bd`. Verify with `git log -1 --oneline` and
  `git status --short --branch`; large raw captures and live-run binaries are
  intentionally excluded by `.gitignore`.
- Added the mandatory per-step three-document update rule and the rule that all
  temporary files/data must live under the project-local `.codex_tmp/` tree.
- Recorded the user-confirmed source-authority split and the CM311 test result.

## Verified environment snapshot

| Host | Verified facts | Not verified in this session |
|---|---|---|
| Ubuntu PC workspace `/home/billieguo/billie_guo/src/rm/mobile_vt` | CLI help RC=0; `rm` environment has required Python packages; local golden capture and parameter-set hashes recorded | Actual USB device availability on PC; live stream; display stack |
| CM311 `billieguo@10.42.0.11` | `armbian`, `aarch64`, kernel `6.18.59-ophub`, 4 cores, 1.7 GiB RAM, 107 GB free, `/dev/video0` present, CLI help RC=0 | Current process ownership; V4L2/decoder health; display stack; live wireless link; performance |

## Cross-machine consistency ledger

| Item | Local state | CM311 state | Result |
|---|---|---|---|
| `captures/cold_start/bulk_if0_ep81.bin` | 2,431,249 bytes; SHA256 `d4cec190f35eac9b32944aff0b32ca501d54e451c1e7e0c800ab10cbdd5aa698` | Same size and SHA256 | MATCH |
| `live_runs/vt13_params.h265` | 102 bytes; SHA256 `f9f019a14e2fc2990863221cca5bd1187cf3898dceb38277ba2b86194f94887f` | Same size and SHA256 | MATCH |
| Project source tree | Workable software-decode baseline; local Git baseline; 24 source/config/test entries hashed; 50/50 local tests pass | Latest experimental code; `.git` invalid; 27 source/config/test entries hashed; remote-only `async_usb.py` and two config files; `README.md`, `decoder.py`, `pipeline.py` differ; remote tests 49/50 due PyAV API mismatch | DIVERGENT BY DESIGN; MERGE PENDING |
| Kernel source tree | Not present in this workspace | HEAD `0e80ef956`; modified `codec_hevc.c`, `vdec_platform.c`; untracked backups | REMOTE-ONLY SNAPSHOT |
| FFmpeg source tree | Not present in this workspace | HEAD `e38092e`; modified `v4l2_buffers.c`, `v4l2_m2m.c`, `v4l2_m2m_dec.c` | REMOTE-ONLY SNAPSHOT |
| Project docs | Updated locally this session | Older remote copies not re-read/synced | EXPECTED DIVERGENCE UNTIL SYNC |
| `/tmp/dji_test_latest_dir` | Not applicable | Missing | UNRESOLVED |

## Current validation-needed checklist

| ID | Item | Current status | Evidence required to close |
|---|---|---|---|
| V01 | Local/remote source consistency | Authority documented: CM311 is latest experimental, PC is workable software-decode baseline; trees remain divergent (24 vs 27 entries); remote tests 49/50 due PyAV API mismatch | Per-file merge/review; Git commit/diff or full SHA256 manifest; test both sides |
| V02 | Latest capture pointer | Missing on CM311 | `test -f /tmp/dji_test_latest_dir`, `cat`, and a verified capture root |
| V03 | CM311 process ownership | Not enumerated by this session | `ps`/`pgrep` plus `fuser`/`lsof` for `/dev/video0`; do not kill unknown processes |
| V04 | Display stack | Not checked | `ls /dev/dri`, `DISPLAY`, `loginctl`, and actual HDMI output evidence |
| V05 | `vt13_video` stream/READY | Only `--help` checked | Real `stream` command, READY/LISTENING log, stop/exit procedure |
| V06 | Golden capture decode | Hashes match; decode not re-run | Offline replay RC, frame count, decoder errors, FrameMD5 or equivalent |
| V07 | Custom FFmpeg hardware decode | Binary/version verified | `hevc_v4l2m2m` decode run, RC, frame count, software/hardware comparison |
| V08 | Kernel module/VDEC | Not checked | `uname -r`, `lsmod`, vermagic, relevant `dmesg`, `status=0x8/0xf` |
| V09 | Source Change/POC50/EOF | Historical results only | Controlled offline test and a short CM311 target-board test |
| V10 | Live wireless end-to-end | Not started | `AGENTS.md` §6 handoff: READY first, then human opens wireless link |
| V11 | Performance/latency targets | 30–50 FPS and ~1024×576 remain unconfirmed | User acceptance criteria plus CM311 CPU/RSS/temperature/latency evidence |
| V12 | Cross-machine sync | Golden and parameter-set data match; source/docs not yet synced | Post-copy SHA256 verification and an updated ledger |
| V13 | Remote test/PyAV compatibility | 49/50 pass; PyAV 11.0.0 exposes `OUTPUT_CORRUPT`, while the test expects lowercase `output_corrupt` | Fix the compatibility test or pin PyAV; rerun all tests and record RC |

## Data manifest

| Path | Host | Size | SHA256 | Status |
|---|---|---|---|---|
| `captures/cold_start/bulk_if0_ep81.bin` | Ubuntu PC | 2,431,249 | `d4cec190f35eac9b32944aff0b32ca501d54e451c1e7e0c800ab10cbdd5aa698` | MATCH with CM311 |
| `/home/billieguo/mobile_vt/captures/cold_start/bulk_if0_ep81.bin` | CM311 | 2,431,249 | `d4cec190f35eac9b32944aff0b32ca501d54e451c1e7e0c800ab10cbdd5aa698` | MATCH with PC |
| `live_runs/vt13_params.h265` | Ubuntu PC | 102 | `f9f019a14e2fc2990863221cca5bd1187cf3898dceb38277ba2b86194f94887f` | MATCH with CM311 |
| `/home/billieguo/mobile_vt/live_runs/vt13_params.h265` | CM311 | 102 | `f9f019a14e2fc2990863221cca5bd1187cf3898dceb38277ba2b86194f94887f` | MATCH with PC |

Timestamps differ between hosts; size and SHA256 are the authoritative
content-consistency evidence. Other large captures and live-run binaries have
not yet been entered into this manifest.

Source/config/test manifest comparison (2026-11-06 16:21 HKT): 24 local entries
versus 27 remote entries; the exact divergence is recorded in
`docs/REMOTE_MACHINE_USAGE.md` under “Source hash comparison”. The authority
split is now documented, but the trees are still divergent; merge per file and
do not copy either tree wholesale.

### CM311 experimental source snapshot (repository-local temp copy)

Copied to `.codex_tmp/cm311_latest_20261106/` for read-only comparison; this
directory is not committed to Git.

| File | Size | SHA256 |
|---|---|---|
| `vt13_video/async_usb.py` | 6,146 | `d5b52faab84d8161fee0aa9b679d23e63a3888b74ce7f1991bc4f80c8023f32e` |
| `vt13_video/decoder.py` | 9,053 | `0a63d8962752b9b5efbc54af01de4548ecac0523eaacfa4c28a33ba7e31ce527` |
| `vt13_video/pipeline.py` | 34,065 | `85e57ea8aa5faf5224e1901a7175966096672af37d7efe790b8f80e1393d315c` |
| `README.md` | 16,874 | `14deff0bd8e95bbc2b75c9ef8c61dc587fd9f35171365d0347ba715225700533` |
| `config/vt13_video.no_status.yaml` | 2,040 | `913c8af02e087555aaee295c56a7b46a4b9229528166c109c761ca611454e230` |
| `config/vt13_video.yuvtest.yaml` | 2,039 | `fb2c1738ad0be9fe2486c803e37a90e545a8532207bf342ed8adff809ade27bf` |

## Next-session start checklist

On the Ubuntu PC:

```bash
cd /home/billieguo/billie_guo/src/rm/mobile_vt
git status --short --branch
git log -1 --oneline
/home/billieguo/miniconda3/envs/rm/bin/python -m vt13_video --help
```

On CM311 (read-only; SSH may require network escalation):

```bash
hostname
uname -a
uname -m
test -f /tmp/dji_test_latest_dir && cat /tmp/dji_test_latest_dir || echo 'MISSING: /tmp/dji_test_latest_dir'
ls -l /dev/video0
cd "$HOME/mobile_vt"
python3 -m vt13_video --help
git status --short 2>&1 || true
```

Do not start a live stream until the process-ownership and display-stack checks
are complete. A live run is R2 and requires approval; the wireless transmitter
is opened by a human only after the receiver reports READY.

For any fetched copy or analysis artifact, create a step-specific directory under
`.codex_tmp/` in this repository and record it in the change log.

## Human decisions still needed

- Confirm the actual HDMI display stack and target output path.
- Confirm minimum FPS, maximum latency, quality/error-concealment tolerance, and
  required test duration.
- Confirm which CM311 processes may be stopped and whether USB/V4L2/HDMI may be
  exclusively used for a test window.
- Confirm the wireless-link open/close procedure and whether the link can
  request a fresh IDR.
- Confirm the per-file merge direction: which CM311 experiments should be
  ported into the PC software-decode baseline, and whether to initialize
  `~/mobile_vt` as a Git repository on CM311.

## Change log

### 2026-11-06 16:46 HKT — source authority and experimental diff audit

- Re-read all three project-control documents before acting.
- User confirmed CM311 `~/mobile_vt` is the latest experimental source tree and
  the Ubuntu PC tree is the workable software-decode baseline.
- Copied remote-only/differing files to `.codex_tmp/cm311_latest_20261106/` and
  recorded sizes/SHA256.
- Characterized CM311 experiments: async USB prefetcher, PyAV thread controls,
  low-latency stale-AU catch-up, and two extra configs.
- CM311 offline tests: 50 run, 49 passed, 1 error, RC=1; failure is PyAV 11.0.0
  `OUTPUT_CORRUPT` versus test lowercase `output_corrupt`, not a proven decoder
  logic failure.
- Added mandatory per-step three-document updates and project-local `.codex_tmp/`
  temporary-data rules.
- No live USB/V4L2/HDMI run, wireless test, reboot, module reload, or package
  installation occurred.

### 2026-11-06 15:52 HKT — documentation and read-only inventory

- Read both existing project-control documents.
- Verified local CLI, Python environments, and remote R0 environment.
- Recorded matching golden/parameter-set SHA256 values across hosts.
- Recorded source/config/test SHA256 divergence (24 local vs 27 remote entries;
  remote-only `async_usb.py` and two config files; three differing files).
- Recorded missing `/tmp/dji_test_latest_dir` and invalid remote Git metadata.
- Added the local Git baseline and `.gitignore` exclusions for large raw data and
  generated artifacts.
- No USB/V4L2/HDMI live run, wireless test, reboot, module reload, or package
  installation occurred.
