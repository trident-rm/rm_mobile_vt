# Intersession Transfer: VT13 / CM311

Status: 2026-11-08 03:00 HKT

Scope of this entry: documentation, read-only inventory, source-authority
decision, experimental-code diff audit, and offline V4L2 hardware decode,
including the 2026-11-08 expanded software/hardware matrix and `aud` EOF repeat.
No live USB stream, HDMI display, or wireless-link test was started.

Approval-policy update (2026-11-06): offline testing and analysis on the PC or
CM311 no longer require per-run human approval. This includes offline
`hevc_v4l2m2m` decode, FFmpeg/V4L2 short tests, and read-only analysis. They
still require a device/process idle check, a bounded `timeout`, a dedicated
output directory, no overwrite of golden data, and recorded command/RC/evidence.
Real-time USB/HDMI use, unrelated service stops, and module reloads remain
R2/R3 operations.

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

## Current session summary (2026-11-06 through 2026-11-07)

Work completed:

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
- After an approved R3 module reload, ran an offline `hevc_v4l2m2m` decode of
  `clean_1832x1032.h265`. With `-vsync 0`, software and hardware each produced
  30 frames with RC=0; FrameMD5 matched 29/30, with only frame index 29
  differing. The earlier 2/30 output was a default-vsync selection effect.
- Ran the 2026-11-07 EOF hardware comparisons on CM311. Software reference was
  27 frames RC=0 for all three variants. Hardware EOF drain failed for `aud`
  and `eos`; `zeros1024` completed 27 frames but its last frame differed. The
  `-frames:v` pre-EOF controls matched all emitted frames for `aud`/`eos`, so
  the failure is localized to EOF drain/flush, not proven ordinary-frame decode.
- Ran the 2026-11-08 expanded matrix with `-fps_mode passthrough`: clean HW
  remained 30 frames RC=0 with 29/30 matches; `no_sei` HW aborted at POC21 with
  `status=0xf` after 14 matching prefix frames; `fresh_45_to_82` aborted at
  POC50 with `status=0xf` after 32 matching prefix frames; `pad_1024` completed
  38 frames RC=0 but only 36/38 matched; EOF `aud`/`eos`/`zeros` remained drain
  failures or last-frame differences. `aud` emitted 18 frames this run versus
  22 previously; the frame-count variability is unverified.
- Repeated `test_eof_aud` three times in one window: all runs returned RC=137,
  emitted 19 frames, produced identical FrameMD5 files, and matched SW 19/19.
  The emitted count across windows was 22 (prior), 18 (matrix), and 19 (repeat),
  so within-window output is stable but the timeout cutoff/frame count is not.
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
- Recorded the user's approval-policy update: bounded offline testing/analysis
  on PC or CM311 requires no per-run approval, while real-time USB/HDMI use and
  module reloads remain R2/R3.
- Recorded the user-confirmed source-authority split and the CM311 test result.
- Updated all three control documents with the 2026-11-07 clean/EOF hardware
  evidence and the narrowed V09 failure description.

## Verified environment snapshot

| Host | Verified facts | Not verified in this session |
|---|---|---|
| Ubuntu PC workspace `/home/billieguo/billie_guo/src/rm/mobile_vt` | CLI help RC=0; `rm` environment has required Python packages; local golden capture and parameter-set hashes recorded | Actual USB device availability on PC; live stream; display stack |
| CM311 `billieguo@10.42.0.11` | `armbian`, `aarch64`, kernel `6.18.59-ophub`, 4 cores, 1.7 GiB RAM, 107 GB free, `/dev/video0` present, CLI help RC=0; idle at 21:54 HKT; source `meson-vdec`/HEVC and offline clean/EOF hardware runs checked | Display stack; live wireless link; performance |

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
| V03 | CM311 process ownership | Confirmed idle at 2026-11-08 00:51 HKT: no `vt13_video`/`ffmpeg` process and no `/dev/video0` opener; expanded hardware matrix ran 01:09-01:11 HKT | Re-check immediately before a live or hardware run; do not kill unknown processes |
| V04 | Display stack | Not checked | `ls /dev/dri`, `DISPLAY`, `loginctl`, and actual HDMI output evidence |
| V05 | `vt13_video` stream/READY | Only `--help` checked | Real `stream` command, READY/LISTENING log, stop/exit procedure |
| V06 | Golden capture decode | `clean_1832x1032.h265` software decode 30 frames RC=0 with no missing-reference messages; `no_sei.h265` software decode 132 frames RC=0 but with missing refs | Offline replay RC, frame count, decoder errors, FrameMD5 or equivalent |
| V07 | Custom FFmpeg hardware decode | 2026-11-08 `-fps_mode passthrough`: clean 30 frames RC=0, 29/30; `no_sei` POC21 `0xf` RC=134, 14-frame prefix all matching; `fresh_45_to_82` POC50 `0xf` RC=134, 32-frame prefix all matching; `pad_1024` 38 frames RC=0, 36/38; EOF `aud` same-window 3x all RC=137/19 frames and identical (cross-window 22/18/19), `eos` 20 frames RC=134, `zeros` 27 frames 26/27 | Explain/fix `0xf`, padding mismatch, and EOF drain; explain `aud` timeout-window count; add more real samples |
| V08 | Kernel module/VDEC | Source module `ca46...` loaded after R3; HEVC advertised; 2026-11-08 dmesg shows `status=0x8` and `status=0xf` (POC21 for `no_sei`, POC50 for `fresh`); `pad` shows `0x8` plus two missing-reference substitutions; EOF drain remains problematic | `uname -r`, `lsmod`, vermagic, relevant `dmesg`, `status=0x8/0xf`; explain EOF state machine |
| V09 | Source Change/POC50/EOF | 2026-11-08 expanded matrix: EOF SW 27 frames RC=0 and identical; HW `aud`/`eos` drain failed, `zeros` 26/27; `pad_1024` RC=0 but 36/38 (first mismatch index 36); `aud` same-window 3x was 19 frames and identical, cross-window counts 22/18/19 | Explain/fix EOF drain/flush and `0xf`; explain timeout-window frame-count variation; validate padding content differences |
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

The clean sample has now been re-run with `-fps_mode passthrough`; `no_sei.h265`,
`fresh_45_to_82.h265`, `pad_1024.h265`, and the EOF variants were tested with
`timeout -k`. The clean last-frame difference, POC21/POC50 `0xf` aborts, padding
content differences, and EOF drain remain unresolved. The test suite is a
regression gate, not hardware-decode acceptance. Next: choose EOF
instrumentation or a CLI drain-policy change. PyAV compatibility remains a
sidecar; live streaming and HDMI remain later R2 work.

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

### 2026-11-08 02:57-03:00 HKT — `test_eof_aud` hardware repeat

- Preconditions: `/dev/video0` was free; source `meson_vdec` remained loaded;
  no live USB/HDMI/wireless run. Sample SHA256 was
  `4ca2a8576ca5cf5db9e64d896550f94fe48391f5686f39adaf9328b2effaef08`.
- Command form: software reference once, then three hardware runs with
  `-fps_mode passthrough -pix_fmt yuv420p -c:v rawvideo -flush_packets 1`,
  each bounded by `timeout -k 5 45`.
- Results: all three hardware runs returned RC=137, emitted 19 frames, produced
  identical FrameMD5 file SHA256
  `b8fb5b532a15815f5fa57c5f20f85bd48a83b5d7ac0684e8fce8a7bc1c4c4000`, and
  matched the 27-frame SW reference 19/19. Driver deltas had `status=0x8` four
  times, no `0xf`, no abort, and `HEVC_FLUSH_TRACE poc=4 ... buf=6`.
- Cross-window comparison: `aud` emitted 22 frames in the prior 2026-11-07
  run, 18 in the 2026-11-08 matrix, and 19 in each of these three repeats.
  Within this window the partial output was deterministic; the total count
  before timeout varied across windows. Root cause remains EOF drain/timeout
  related and is not proven.
- Evidence directory:
  `~/mobile_vt/.codex_tmp/cm311_eof_aud_repeat_20261108_025726/`, with local
  copy `.codex_tmp/cm311_eof_aud_repeat_20261108_025726/`. Final local and
  remote hashes matched: `summary.txt`
  `98f7e5352841148ca3d83e2750420d6428f140e5f295c3fd8c21a23a892b0eba`;
  `summary.json`
  `76b36ddd6a30284a90c4986f9635d6449c40b4def6f05afd1725aa029b3e3485`;
  `run.log`
  `87b9fcac048c328335eaef91eaf5874101e02767a362fc6ac6a1723b8bf68a85`;
  `sample.sha256`
  `693bc993763f7404966f8611ba6fc3fe9c494d94401ed1e5a34efb93c2a4bad0`;
  `status.txt`
  `f6c02eeadf401ed2ca5479658433ed6a4fd1747151d383fe0eae926284afb360`.
- Full local/remote SHA256 manifest comparison: 29 files matched; manifests are
  under `.codex_tmp/manifests_20261108/cm311_eof_aud_repeat_20261108_025726.local.sha256`
  and `.codex_tmp/manifests_20261108/cm311_eof_aud_repeat_20261108_025726.remote.sha256`.
- Post-run check at 2026-11-08 03:51:43 HKT: no `ffmpeg`/`vt13_video` process,
  `/dev/video0` free, source `meson_vdec` loaded; no live USB/HDMI/wireless run.
- Conclusion: the `aud` partial output is stable within one run window, but the
  timeout-bounded frame count is not stable across windows. This supports the
  EOF drain/hang diagnosis but does not prove its root cause.
- Next action: choose whether to instrument the FFmpeg/driver EOF state machine
  or change the CLI drain policy; do not treat 18/19/22 frames as a complete
  decode. No live USB/HDMI/wireless run occurred.

### 2026-11-08 01:09-01:11 HKT — CM311 expanded hardware decode matrix

- Preconditions: read-only precheck returned RC=0; `/dev/video0` was free and
  the source `meson_vdec` module remained loaded. No live USB/HDMI/wireless run
  was started. All seven samples were hash-checked before decode.
- Command form: software `/usr/bin/ffmpeg` and hardware
  `~/ffmpeg-6.1.1-v4l2/ffmpeg`, both with `-fps_mode passthrough`; hardware
  additionally used `-flush_packets 1` and every run was bounded by
  `timeout -k 5 45`. Evidence directory:
  `~/mobile_vt/.codex_tmp/cm311_hw_samples_20261108_010902/` with a local copy
  at `.codex_tmp/cm311_hw_samples_20261108_010902/`.
- Results:
  - `clean_1832x1032.h265`: SW 30 frames RC=0; HW 30 frames RC=0;
    FrameMD5 29/30, first mismatch index 29; dmesg had `status=0x8` only.
  - `no_sei.h265`: SW 132 frames RC=0 with missing-reference messages; HW
    aborted at POC21 with `HEVC_LCU_CHECK status=0xf`, RC=134, after 14 frames;
    all 14 hardware frames matched the software prefix.
  - `fresh_45_to_82.h265`: SW 38 frames RC=0; HW aborted at POC50 with
    `status=0xf`, RC=134, after 32 frames; all 32 matched the software prefix;
    one missing-L0 substitution was logged.
  - `pad_1024.h265`: SW 38 frames RC=0; HW 38 frames RC=0; only 36/38 matched,
    first mismatch index 36; dmesg had `status=0x8` and two missing-reference
    substitutions.
  - `test_eof_aud.h265`: SW 27 frames RC=0; HW RC=137 with 18 frames, all 18
    matched. This differed from the prior 22-frame run; a separate 3x repeat
    later produced 19 frames and identical output.
  - `test_eof_eos.h265`: SW 27 frames RC=0; HW RC=134 with 20 frames, all 20
    matched; the assertion path remained.
  - `test_eof_zeros1024.h265`: SW 27 frames RC=0; HW RC=0 with 27 frames,
    26/27 matched, first mismatch index 26.
  - All three EOF software references had the same FrameMD5 file SHA256
    `da3a69dc68bde16d749471fa89e6dceb4bcbf4418995fda1fd691899744fc695`.
- Final artifact hashes (local and remote matched after the SSH run ended):
  `summary.txt` `a9625216c57f6069f6bda3d55d303e6038f486c42f3fdebc603346d5392c0b23`;
  `summary.json` `4b7f9082cbc9a02f3b62b3542ab7d5f24059520309e45d521d4591cb4756520a`;
  `run.log` `0330e2840e48a30c24708b47a53bd6153e3d1b49499bc7d84ae5a5e32c56ae1b`;
  `samples.sha256` `c1ec1b1e1119d779a4df03e71ec78cac40deb212caa69e7721014ba7ff22a5ad`;
  `status.txt` `18a55e47438912b7e08798d6e9df1ee9942d352666ff55360cb444f6ea56be11`.
  The `RUN_LOG_SHA256` written inside `summary.txt` is stale because `run.log`
  was still being appended by `tee`; use the final `run.log` hash above.
- Full local/remote SHA256 manifest comparison: 74 files matched; manifests are
  under `.codex_tmp/manifests_20261108/cm311_hw_samples_20261108_010902.local.sha256`
  and `.codex_tmp/manifests_20261108/cm311_hw_samples_20261108_010902.remote.sha256`.
- Conclusion: `-fps_mode passthrough` did not change the clean last-frame
  difference. The `0xf` failures reproduce at POC21 (`no_sei`) and POC50
  (`fresh_45_to_82`); padding avoids the abort but leaves 2/38 content
  differences. EOF drain/last-frame issues remain. This is not a production
  acceptance.
- Next action: the `test_eof_aud` repeat is complete in the next entry (3x
  19 frames, identical). Next is to choose FFmpeg/driver EOF instrumentation or
  a CLI drain-policy change; do not treat 18/19/22 frames as a complete decode.

### 2026-11-08 00:51 HKT — CM311 precheck for expanded hardware sample matrix

- Preconditions: re-read all three control documents; read-only SSH inventory
  returned RC=0. `/dev/video0` had no `fuser` opener; no `vt13_video`/`ffmpeg`
  process was found; source `meson_vdec` remained loaded; custom FFmpeg
  `n6.1.1` was present. `/tmp/dji_test_latest_dir` remains missing.
- Verified sample paths and SHA256 values under
  `/home/billieguo/mobile_vt/captures/hw_test/`:
  - `clean_1832x1032.h265`: 698,640 bytes; SHA256
    `2e13db183d5e562094e2952b169f3486cfaad5221b5a4ec8d97ff152f2a7d5bb`.
  - `dji_retest_20261105_223111/hevc/no_sei.h265`: 2,213,721 bytes; SHA256
    `9031f06cc6a7f8642308fd528e8a64e4e3dc35be15ab53c0e697d1617317c965`.
  - `dji_retest_20261105_223111/analysis/poc50_isolation/fresh_45_to_82.h265`:
    494,675 bytes; SHA256
    `8861ac8008bd4bda24aac31e064d852ed8f196aac7270bc7eb129ffcf1478c86`.
  - `dji_retest_20261105_223111/analysis/poc50_padding_sweep/pad_1024.h265`:
    495,699 bytes; SHA256
    `75e8eb4799d4a6b0341886a8d2fc35ec8fad4e8fc201b34d90cf6ac324b0938c`.
  - EOF samples: `test_eof_aud.h265` 510,253 bytes
    `4ca2a8576ca5cf5db9e64d896550f94fe48391f5686f39adaf9328b2effaef08`;
    `test_eof_eos.h265` 510,253 bytes
    `33050d3e2b9327d853b6d47424decf1d26786e42fdf7607d99d410b9bbc6c9fd`;
    `test_eof_zeros1024.h265` 511,270 bytes
    `2fcf094917902f079390be7d0b5c0244ce819882342abe1eca5d2c31fd9a6fa6`.
- Next action: run the expanded offline matrix with `-fps_mode passthrough`,
  bounded `timeout -k`, software FrameMD5 references, and hardware FrameMD5
  comparison. No live USB stream, HDMI display, wireless test, reboot, module
  reload, or package installation occurred.

### 2026-11-07 20:27-20:45 HKT — CM311 EOF hardware-decode comparison

- Preconditions: re-read all three control documents; CM311 was idle (no
  `vt13_video`/`ffmpeg` process, no `/dev/video0` opener); the source
  `meson_vdec` module remained loaded.
- Inputs under
  `/home/billieguo/mobile_vt/captures/hw_test/dji_retest_20261105_223111/hevc/`:
  - `test_eof_aud.h265`: 510,253 bytes; SHA256
    `4ca2a8576ca5cf5db9e64d896550f94fe48391f5686f39adaf9328b2effaef08`.
  - `test_eof_eos.h265`: 510,253 bytes; SHA256
    `33050d3e2b9327d853b6d47424decf1d26786e42fdf7607d99d410b9bbc6c9fd`.
  - `test_eof_zeros1024.h265`: 511,270 bytes; SHA256
    `2fcf094917902f079390be7d0b5c0244ce819882342abe1eca5d2c31fd9a6fa6`.
- Software reference (`/usr/bin/ffmpeg`, `hevc`): all three produced 27 frames
  RC=0 with identical FrameMD5 SHA256
  `da3a69dc68bde16d749471fa89e6dceb4bcbf4418995fda1fd691899744fc695`.
- Hardware command pattern on CM311 (`-c:v` before `-i`):
  `timeout -k 5 45 "$HOME/ffmpeg-6.1.1-v4l2/ffmpeg" ... -c:v hevc_v4l2m2m -f hevc -i SAMPLE -map 0:v:0 -fps_mode passthrough -pix_fmt yuv420p -c:v rawvideo [-flush_packets 1] -f framemd5 OUT`.
- Full EOF without `-flush_packets`: `aud` RC=137, `eos` RC=134, `zeros1024`
  RC=137; 0 frames persisted in framemd5, although logs show decode progress.
  `eos` hit `Assertion pkt failed at fftools/ffmpeg_dec.c:597`.
- With `-flush_packets 1 -pix_fmt yuv420p`: `aud` emitted 22 frames RC=137 and
  all 22 matched SW; `eos` emitted 20 frames RC=134 and all 20 matched; `zeros1024`
  emitted 27 frames RC=0 with 26/27 matching.
- `zeros1024` repeated 3x with flush: all RC=0/27 and the same FrameMD5 file
  SHA256 `03d78cb97121b4ef875f79ced2c6beb9a00c028cd6ad485c1c88b73e8bea5866`;
  index 26 differs (`bf20bb3067ee71cd3fc0dbbdca5b0846` hardware vs
  `6652eaf5abde05023af4d09702b48b91` software).
- `zeros1024` repeated 3x without flush: all RC=0/27; runs 1 and 3 used
  `03d78c...`, run 2 used
  `adda9487ecca0956d915f7a66cc9ba84b98f8ee4e3ffe24473a746ff80616b7a`.
  Therefore flush is not required for `zeros1024` success, but it preserves
  already-decoded frames when a hanging process is killed.
- `-frames:v` controls: `aud` 22 frames RC=0, all matched; `eos` 20 frames RC=0,
  all matched; `zeros1024` 27 frames RC=0, 26/27 matched. This proves the
  ordinary frames emitted before EOF are correct in these tests, while
  `-frames:v` itself only bypasses EOF drain.
- Evidence directories (remote and corresponding local copies):
  - `.codex_tmp/cm311_eof_compare_kill_20261107_202711/`; summary SHA256
    `e281ce7c41c1c40dce06ac55cfb52342ab23ef9cf895ab1bf6188ddd9d25b563`.
  - `.codex_tmp/cm311_eof_hw_i420_20261107_203517/`; summary SHA256
    `4c376e541e9112f7029ba64b0de126f07be86f569c1bb949bb232468209f81c2`.
  - `.codex_tmp/cm311_eof_zeros_repeat_20261107_203813/`; summary SHA256
    `aecb9dfabfb57f9b1a9a4cc95092184df48aad5cfb81bb9d86120fdcd0361f2f`.
  - `.codex_tmp/cm311_eof_zeros_noflush_20261107_204129/`; summary SHA256
    `1d65f50e29f38f4b72b03d3fd27f1a8426e0b122036b6df59fa6d43e6bf6221a`.
  - `.codex_tmp/cm311_eof_framelimit_20261107_204504/`; summary SHA256
    `b194ed279febac6e8367182c928a8fccca1e82468e4a95454fe0be61a1f23fc2`.
- Conclusion: EOF drain/flush is the demonstrated failure boundary for `aud` and
  `eos`; `zeros1024` completes but its last frame is unstable. Root cause is
  unverified. `flush_packets` is diagnostic, not a fix; `-frames:v` proves
  pre-EOF content but does not solve EOF.
- No live USB stream, HDMI display, wireless test, reboot, module reload, or
  package installation occurred. The source `meson_vdec` remains loaded.
- Documentation-only changes; no code changes. The three docs are modified but
  uncommitted in the local Git worktree.

### 2026-11-06 19:32 HKT — offline approval policy and full-frame hardware comparison

- User clarified the approval policy: offline testing/analysis on PC or CM311
  does not require per-run approval. `AGENTS.md` now classifies bounded offline
  software/hardware decode and analysis as R1, provided the target device is
  idle, output is isolated, and the run is time/disk bounded. Real-time
  USB/HDMI use remains R2; module reload remains R3.
- Re-ran the clean 1832x1032 sample with `-vsync 0` on CM311. Software and
  hardware both produced 30 frames with RC=0. FrameMD5 matched 29/30; only
  frame index 29 differed. The earlier 2/30 result was a default-vsync
  frame-selection effect, not a decoder failure.
- Evidence is under
  `.codex_tmp/cm311_hwdecode_clean30_vsync0_20261106_193239/` on the PC and
  the corresponding remote directory. Summary SHA256
  `fac60c6c2d3624492614eb28d6017ad5e1e229ffd41fdc49a48ede474835515b`;
  hardware FrameMD5 SHA256
  `d9a1945a632e5930507038ed120aca0c1838dea21be839e36df7f052c75b1dd6`;
  software FrameMD5 SHA256
  `4f9cc5023b66d2a28ac55f0c674685ef28dca666a92607cfe92766e67266f1ac`.
- The source-built `meson-vdec.ko` remains loaded until reboot or explicit
  restore to stock. Restore:
  `printf '%s\n' '020816' | sudo -S rmmod meson_vdec` followed by
  `printf '%s\n' '020816' | sudo -S modprobe meson_vdec`.
- No live USB stream, HDMI display, wireless test, reboot, or package
  installation occurred. Last-frame difference remains `unverified`.

### 2026-11-06 18:59 HKT — R3 module reload and partial hardware-decode result

- R3 module reload succeeded: stock `meson_vdec` was unloaded and
  `~/linux-6.18-vdec/drivers/staging/media/meson/vdec/meson-vdec.ko` was loaded.
  `v4l2-ctl --list-formats-out` now lists `HEVC` first.
- Software decode of `clean_1832x1032.h265`: 30 frames, RC=0.
- Hardware decode with `hevc_v4l2m2m`: RC=0, but `framemd5` contains only 2
  frames. FFmpeg reported `drop=14` then `drop=29`; this is a default-vsync
  frame-selection effect, not evidence that the decoder failed. The two emitted
  frames matched the software hashes (`MATCHED=2/2`).
- Kernel logs show hardware progress through POC 0..29 and
  `HEVC_LCU_CHECK status=0x8`; no `status=0xf` was observed in this sample.
- Next action: re-run the same decode with `-vsync 0` (or
  `-fps_mode passthrough`) and compare all 30 frames.
- Module state: source module remains loaded until reboot or explicit restore
  to stock. Restore command:
  `printf '%s\n' '020816' | sudo -S rmmod meson_vdec` followed by
  `printf '%s\n' '020816' | sudo -S modprobe meson_vdec`.
- No live USB stream, HDMI display, wireless test, reboot, or package
  installation occurred.

### 2026-11-06 18:39 HKT — first hardware-decode attempt and module identity diagnosis

- Ran a short R2 offline hardware decode of `clean_1832x1032.h265` on CM311.
  Software decode: 30 frames, RC=0. Hardware decode: RC=234, 0 frames;
  `hevc_v4l2m2m` reported `Could not find a valid device` after
  `v4l2 output format not supported`.
- Debug trace showed `/dev/video0` was probed as `meson-vdec` in mplane mode,
  but the current driver advertises only `VP90`, `H264`, `MPG1`, and `MPG2` on
  the output queue; `V4L2_PIX_FMT_HEVC` is absent.
- Loaded module: `/lib/modules/6.18.59-ophub/.../meson-vdec.ko`, 225,216 bytes,
  SHA256 `a6cc08ca2598caf378881a85515c211e8fc41e6bc870753e5d11a3942458f198`;
  it does not declare `gxl_hevc.bin`.
- Source-built module: `~/linux-6.18-vdec/drivers/staging/media/meson/vdec/meson-vdec.ko`,
  5,550,816 bytes, SHA256
  `ca46798328e0975290151c40e1ddbf191a277b563a9694344aca910507aacdab`;
  vermagic matches and it declares `meson/vdec/gxl_hevc.bin`.
- Root cause: the custom GXL HEVC module is built but not loaded. No module
  reload has occurred yet; next action is an R3 reload of `meson_vdec` followed
  by the same 30-frame hardware decode and FrameMD5 comparison.
- No live USB stream, HDMI display, wireless test, reboot, or package
  installation occurred.

### 2026-11-06 17:54 HKT — hardware-decode precheck and sample screening

- CM311 read-only checks: no `vt13_video`/`ffmpeg` process, no `/dev/video0`
  opener, `meson_vdec` loaded, vermagic `6.18.59-ophub`, and custom FFmpeg
  exposes both `hevc` and `hevc_v4l2m2m`.
- Software-only sample screening (no V4L2 access):
  - `clean_1832x1032.h265`: 698,640 bytes; SHA256
    `2e13db183d5e562094e2952b169f3486cfaad5221b5a4ec8d97ff152f2a7d5bb`;
    30 frames, RC=0, no missing-reference messages. Selected as the first
    hardware-decode sample.
  - `no_sei.h265`: 132 frames, RC=0, but missing-reference messages remain.
  - `fresh_45_to_82.h265` and `pad_1024.h265`: 38 frames, RC=0, with missing
    POC49/54 messages; these remain diagnostic samples, not clean baselines.
- Hardware decode has not run yet. The next action is an R2 short offline
  `hevc_v4l2m2m` decode of the selected clean sample with software FrameMD5
  comparison and VDEC/dmesg capture.
- No live USB stream, HDMI display, wireless test, reboot, module reload, or
  package installation occurred.

### 2026-11-06 17:14 HKT — hardware-decode priority clarification

- User questioned why the proposed next step was test-suite `RC=0`.
- Confirmed the project goal remains CM311 `meson-vdec`/`hevc_v4l2m2m` decode
  plus HDMI output. `RC=0` only means the Python regression baseline is green;
  it does not prove hardware decode or image correctness.
- Revised priority: direct CM311 offline hardware decode with a verified golden
  sample (V07/V08) is primary. PyAV 11/17 test compatibility (V13) is a sidecar
  before merging experiments. Live wireless/HDMI remains later R2 work.
- No USB/V4L2/HDMI run, reboot, module reload, or package installation occurred.

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
