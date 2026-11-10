# Remote Machine Usage Reference

Status: 2026-11-10 02:55 HKT (**root cause corrected**: moving the receiver to a
USB2 extension re-enumerated it 005→006 but did NOT change the failure — 3×60 s
gave 31/32/34 aborts and 243/278/182 frames, same as before. A capture-only run
with the same receiver/USB path but no decoding delivered a clean stream:
76.2 MB/60 s = 10.2 Mbps, 60.3 AU/s, max gap 0.17 s, only 2/451 GOPs with POC
gaps. The pipeline's clean 1080p replay tops out at 38.5 fps < 60 fps source, so
it sustains a backlog (async queue 15k/16k), the receiver overflows, the stream
is damaged and `0xf` follows. Best live result: async + control disabled =
778 frames/61 s (12.7 fps), 10 aborts, 0 green drops. Opt-in blocks are deployed and default-off: `VT13_SHED_TO_IRAP` in
`pipeline.py` `9d0013c2` and `VT13_DISPLAY_FPS` in `ffmpeg_pipe.py` `edb960c2`
(backups `~/.codex_tmp/backup_shed_20261109/`, `backup_dispcap_20261109/`).
Best tested combo: small async queue (2000 chunks ≈2.5 s) + 50% GOP shed +
display cap 25 + no-copy + control off = 552/529 frames per 60 s (9.2/8.7 fps),
15/17 aborts, ~3 MiB backlog. Note: the
pipeline's recorded raw is only the bytes delivered to the parser; with an async
backlog it is not the full USB stream. User visual check: the default config
still updates every few seconds (~5 s lag), while async ON barely updates because
the ~25 MiB (~20 s) backlog makes decoded frames stale — async is a diagnostic
only, not a viewing path. Next: raise pipeline throughput above
60 fps or close the shed-to-IRAP loop; RF is no longer the priority.)
Earlier: P1-1 clean startup 0.26–0.32 s for one frame; reopen right after an
injected `0xf` takes 0.277–0.305 s; 300-frame rawvideo Copy-Out 38.7 fps vs
no-copy 89.9 fps. P0-3: B1 raw capture damaged at byte level (18 oversized fake
parameter-set NALs, 74/295 GOPs with POC gaps) — that attribution is now
superseded by the capture-only result above. P0-1 A/B/A: ON 31/32 aborts and
267/216 frames vs OFF 33 aborts and 225 frames, all 60 s → requested IDR is not
the `0xf` trigger. P0-0 snapshot: CM311 idle, `/dev/video0` free, `meson_vdec`
refcnt 0, receiver `2ca3:1020` enumerated, Xorg `:0` reachable. Deployed: config
`f47c7d9b...`, pipeline `9d0013c2...`, ffmpeg_pipe `b6672def...` (pipeline `9ada66df` with opt-in
`VT13_DAMAGE_GATE`, default off), launcher
`c0e35756...`, release FFmpeg `1ed2b711...`. Details in
`docs/INTERSESSION_TRANSFER.md` 23:02 entry. Earlier: duplicate ffplay window on
resolution change fixed: run 17 started 1832 then 1080 without closing the old
window; run 18
after the fix has one start/one close and no residual process. ffmpeg_pipe
`871af9b2...`. Earlier: no-request control run 17: 1 request, 30 aborts,
31 IRAPs, 273 frames/60 s — the requested IDRs are NOT the trigger; the
source sends IRAPs about every 2 s and each GOP still dies. Root is the
damaged 1080p stream/link + firmware abort. Next: RF/link, 1832 mode, P0.
Earlier: partial-green filter deployed: run 15 dropped
23 full-green + 13 partial-green frames, so bottom-half green flashes are
filtered; 195 frames, 33 aborts, 1582 POLLERR, 0 watchdog. The 0xf/POLLERR
freeze remains. ffmpeg_pipe `2d99b0a0...`. Earlier: release Copy-Out live A/B
run 14: 258 frames,
31 aborts, 1507 POLLERR, 0 watchdog; Copy-Out active (no env), recovers but
the 0xf cadence still limits the picture. Release Copy-Out is a cleaner live
candidate via `DJI_FFMPEG_PATH`. Earlier: release patched FFmpeg built:
Copy-Out mode
45 fps, `FFMPEG_V4L2_NO_COPY=1` mode 249 fps offline. Live run 13 with
no-copy: 219 frames/60 s, 34 aborts, 1503 POLLERR — no-copy cannot recover
from `0xf`; Copy-Out is required live. The 210 fps is real but offline-only;
the live limiter is the `0xf` cadence per requested IDR. Binary
`~/ffmpeg-6.1.1-release/ffmpeg` SHA256 `1ed2b711...`. Earlier: 210 fps
explained: the Nov 5 log is real; the
custom `--enable-debug=2` FFmpeg caps at 45 fps, while `/usr/bin/ffmpeg`
release reaches 221 fps on the same file. The system release binary cannot
recover from the kernel 0xf (`output POLLERR`/EIO), so it is offline-only.
A release build of the patched FFmpeg is running in
`~/ffmpeg-6.1.1-release` (PID 104978). Earlier: run 11 added
`recovery.kernel_abort_watch`:
journalctl detects `0xf` and resets + requests in 116 ms median, 0 watchdog
waits; abort rate rose to 33/min, so requested IDRs/link damage dominate.
Clean 1080p hardware decode to raw measured 38.7 fps; >200 fps not reproduced.
Deployed: config `f47c7d9b...`, pipeline `c700b8cd...`, launcher `673dd0f8...`.
Earlier: runs 5–10 done. I-frame request hardware-verified
(37–162 ms; 0.2 s startup). Display filters keep the ffplay window open and
suppress green/grey/corrupt frames. Software decode is NOT viable (~3 cores,
USB backpressure, grey concealment). Remaining: 14–29 `0xf` aborts per run at
1920×1080; 1832×1032 was stable. Deployed: config `93b3d6b5...`, pipeline
`a14b3aa2...`, ffmpeg_pipe `8e6c4411...`, launcher `ae7f3f42...`. Earlier:
NV12 display sink INTEGRATED and DEPLOYED: `decoder.display: ffplay` taps NV12 before cv2 in the ffmpeg-pipe reader thread; verified on CM311 — segB replay 491 frames / 21.55 fps / 0 errors with HDMI window active (user confirmed dynamic video on the earlier BGR test; smoothness confirmation pending); display stack: Xorg :0/tty7 + meson-drm HDMI 1024x600, ffplay SDL NV12 overlay; hash-chain deployment with remote pre-backup; suite 57 tests only known V13; no commit; next: live run 4 when user confirms RF setup)

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

## Current device snapshot (2026-11-10 11:12 HKT, B0 read-only)

- Identity: `armbian`, `aarch64`, `6.18.59-ophub`, 4 cores, 1.7 GiB RAM,
  101 GB free on `/dev/sda2`, uptime 3 d 19 h 49 m, load 0.16,
  boot_id `779b73da-3760-4b6b-9c6f-f76fc0525322`.
- Kernel cmdline: `video=HDMI-A-1:1920x1080@60e console=ttyAML0,115200n8
  console=tty0 consoleblank=0`. HDMI-A-1 connected + enabled + dpms On;
  Composite-1 disabled; fb0 `mesondrmfb` `virtual_size=1920,2160`.
- **No Xorg, LightDM `inactive`, default `multi-user.target`, DRM master free.**
  This supersedes the 2026-11-09 note that Xorg `:0` held the master.
- `/dev/video0` = `meson-video-decoder`, no opener, `meson_vdec` refcnt 0;
  CAPTURE only `NM12`; `ENUM_FRAMESIZES` returns nothing; `G_PARM` EINVAL.
- Build: `gcc`/`make`/`pkg-config`, `/usr/include/drm/{drm.h,drm_mode.h}` and
  `/usr/include/linux/videodev2.h` present; **no libdrm-dev / pkg-config libdrm**;
  `modetest` missing. Raw-ioctl C builds work; no libdrm link needed.
- USB: `2ca3:1020` on Bus 001 Port 001 (If0/If1 vendor no-driver, If2-5 cdc_acm);
  SG Flash rootfs on Port 002 → same xhci.
- Remote tree is **not** a Git repository. Deployed hashes now:
  `config.py` `25004fb8...`, `ffmpeg_pipe.py` `67a40898...`,
  `pipeline.py` `4f129217...`, `control.py` `cc0cbcdc...`,
  `decoder.py` `0a63d896...` (experimental). `tools/kms_render.c` is absent
  remotely; the only copy is `.codex_tmp/kiosk_20261110/kms_render.c`
  (`7d26005b...`, identical to local `tools/kms_render.c`), binary
  `fbb208d7...`. FFmpeg: `/usr/bin/ffmpeg` `dbb8cc21...`, release
  `1ed2b711...`, debug `2a204518...`, shared `622cd084...`.
- Local mirror of the five deployed sources + renderer binary:
  `.codex_tmp/b0_inventory_20261110/remote/` (SHA256 verified). No remote tar
  snapshot was taken (write operation, not yet approved).
- D3-0 probe (`tools/d3_probe.c`, `7d4eaab4...`) **ran on the board** (R2 approved):
  `build/d3/d3_probe` `1c196647...`. T1 1832x1032 (20 capture buffers) and T2
  1920x1080 (`--cap-bufs 17`, IRAP-cut sample) both decoded one frame, held the
  overlay 10 s, and exited RC=0. Hardware dumps are **byte-identical** to software
  decode (`00221868...` and `35b75b16...`). Post-run: overlay `crtc=0 fb=0`,
  primary `crtc=45 fb=47`, `video0` free, `refcnt=0`, no master holder; the two
  passing runs logged no `0xf` and no abort. HDMI visual confirmation pending.
  Evidence `~/.codex_tmp/d3_0_20261110_112758/`, report `.codex_tmp/docs_backup_20261110_d3/D3-0_report.md`.
- **D3a (file) passed** with `tools/d3_probe.c` `5ba4af69...` (board
  `126acd1c...`): decode-only 240 frames / 0.884 s = **271.6 fps**; present mode
  with `--hide-primary` 240 frames / 3.992 s = **60.12 fps** (vblank-limited at
  60 Hz), 0 corrupt, 0 `0xf`, 0 abort. Note `status=0x8` appears ~0.95/frame
  (`over=0`, non-fatal); only frame 0 was checked bit-exact against software.
  Feeding must be **AU-level** (NAL-level stalls after 2 frames), and 17 capture
  buffers (DPB 16 + 1) are sufficient; 20 can fail under CMA fragmentation.
  Report `.codex_tmp/docs_backup_20261110_d3/D3a_report.md`.
- **Kiosk display fix (2026-11-10 13:45)**: `kms_render` now accepts
  `--hide-primary` (source `fbd8c439...`, binary `a071cfed...`; old binary
  `fbb208d7...` backed up under `~/.codex_tmp/backup_kms_hideprimary_20261110_1200/`).
  `vt13_video/ffmpeg_pipe.py` passes it for `display=kms`
  (`67a40898...` -> `0936da17...`, backup in the same directory, `py_compile`
  RC=0). Verified with lavfi 90 frames and software-decoded real content
  120/240 frames (24 fps), clean exit, console restored. Note: a preceding
  stuck ffmpeg (`-frames:v 600` > ~430-frame file, EOF drain) held
  `/dev/video0`, so the renderer received 0 frames and showed a green
  uninitialized dumb buffer; `-f rawvideo` pipes are also unreliable. Live
  verification still pending.
  **Live verified 2026-11-10 13:45** (run `d3_live_20261110_134503`): 45 s,
  `display=kms` + `--hide-primary`, 570 frames = 12.7 fps, 10 `kernel_0xf`
  resets, 144 GOP-shed drops, 5 display drops, async backlog 3.1-3.7 MiB
  (~3 s). User confirms the live VT picture is visible, but lagging and
  flashing (resets + single dumb-buffer tearing). Python/nut path is still
  12-17 fps vs the 60 fps source; D3b C worker is the real fix.
- **D3b stage 1 passed (2026-11-10 13:57)**: `tools/d3_replay.py` (AU server,
  SOCK_SEQPACKET, 24-byte header, 60 AU/s) -> `d3_probe --socket` C worker
  (reuses the D3a V4L2/KMS path). 300 AU / 5.001 s = 60.00 AU/s, 0 sender
  drops; worker decoded 299 frames at 60.2-60.6 fps steady, 0 corrupt, 0 `0xf`,
  0 abort; clean exit. Build: source `c5db1467...`, board binary `5a23fa8b...`,
  replay `dfbbe424...`. Report `.codex_tmp/docs_backup_20261110_d3/D3b_report.md`. Next: opt-in pipeline
  integration and live test.
- **D3b pipeline integration (live, 2026-11-10 14:06)**: opt-in
  `decoder.backend=worker` deployed (`worker_client.py` `7929f009...`,
  `config.py` `1a6160d1...`, `pipeline.py` `75071b00...`, launcher
  `e5f73157...`; backup `~/.codex_tmp/backup_worker_backend_20261110_1400/`).
  With async USB it reads 2287 AU / 40 s ~ 57 AU/s and each worker session
  decodes at 60.3-60.5 fps, but the live input produced 30 `0xf`, 17 aborts,
  64 missing-ref in 40 s, killing each session after ~1 s. Clean exit, no
  leftover worker. Remaining limiter is upstream input damage
  (~0.75 `0xf`/s); next is in-worker recovery (D3c) plus link/RF checks.
- **D3c-lite in-worker recovery (2026-11-10 14:13)**: the worker now rebuilds its
  V4L2 session in-process on `POLLERR`/EIO (keeps socket and DRM; waits for the
  next IRAP; source `756b3e02...`, board `9ad1fb16...`, client `93a7087a...`).
  Live 45 s: 34 sessions, **2018 frames = 44.78 fps**, 0 corrupt, 0 oversize,
  `STREAM_EXIT_RC=0`, clean exit. Freeze per event dropped from ~1 s to
  ~0.1-0.2 s. Remaining limiter is still upstream damage (~0.75 `0xf`/s).
- **Key A/B (2026-11-10 14:21)**: capture-only 60 s is clean — 79.34 MB / 10.6 Mbps,
  max gap 0.01 s, 0 gaps >=100 ms, 3616 AU = 60.3 AU/s, 452 IRAPs all carrying
  VPS/SPS/PPS, no oversized PS. Decode without display: 2288 frames / 40 s =
  57.06 fps, 8 sessions, 12 `0xf`; decode with KMS display: 44.78 fps, 34
  sessions, 34 `0xf`. So the `0xf` damage is **host-induced** (KMS scanout adds
  the largest share; VDEC/USB coexistence adds the rest), not RF/upstream.
- **Decisive A/B (2026-11-10 14:28)**: same worker+display config with
  `VT13_ASYNC_USB=1 -> 0` gave **2330 frames / 40.1 s = 58.06 fps**, only
  5 sessions, 0 corrupt, and 6 `0xf` / 4 aborts (vs 44.8 fps / 34 sessions /
  34 `0xf` with async). The Python async reader thread (GIL/scheduling) is the
  dominant damage source; single-threaded read->parse->send is clean. Recommended
  live config: `DJI_BACKEND=worker`, async OFF (default), control on.
- **Best live run (2026-11-10 14:36)**: worker + async OFF + control on, 45 s:
  **2671 frames / 45.106 s = 59.22 fps**, **sessions=1**, 0 corrupt, 0 errors,
  0 resets, **0 `0xf` / 0 aborts**, clean exit. The worker now keeps the
  last scanned-out fb alive across a rebuild (`held`) so the screen does not
  flash. Build `c4203cb6...` -> board `87da0d9e...`. Note run-to-run variance
  (0-78 `0xf`) remains.
- **User accepted the current live baseline (2026-11-10 14:39)**: 60 s run =
  3487 frames / 60.066 s = 58.05 fps, 6 sessions, 0 corrupt; 10 `0xf`/5 aborts.
  Recommended config: `DJI_BACKEND=worker`, `VT13_ASYNC_USB=0`, control on,
  kernel watch on, `DJI_STALL_RESTART_S=0`. Deferred optimizations: rebuild
  flash, ~0.1-0.2 s rebuild pause, faster reinit, IRAP wait, residual `0xf`
  jitter, 10-min soak.
- **10-minute soak passed (2026-11-10 14:54)**: worker backend, async OFF,
  control on, no recording. 35226 frames / 600.112 s = 58.70 fps, 45 sessions,
  0 corrupt, 0 errors, 0 dropped AUs, `PIPELINE_RC=0`; dmesg 20 `0xf` /
  10 aborts; memory 376 -> 365 MiB (no growth); temperature 59 -> 66 C;
  clean exit. Evidence `captures/manual_live/soak_20261110_144438/`.
- **Deployed baseline synced back to the local repo (2026-11-10 15:05)**:
  `config.py 1a6160d1`, `pipeline.py 75071b00`, `ffmpeg_pipe.py 0936da17`,
  `async_usb.py d5b52faa`, launcher `e5f73157`, `control.py cc0cbcdc`;
  `decoder.py` = deployed `0a63d896` + local codec identity logging
  (`5c7460f0`). Tests 43 passed / 38 skipped. From now on the local repo is
  the source of truth; deployment edits must be flowed back and committed.
- **Recovery optimization + TTFV (2026-11-10 15:29)**: worker reuses the same
  V4L2 fd (STREAMOFF -> S_FMT/REQBUFS, reopen only on failure) and sends `R`
  over the AU socket on POLLERR/EIO so the pipeline requests an I-frame
  immediately. TTFV breakdown: reopen 181 ms, IRAP wait 28 ms, buffer export
  35 ms, first frame 18 ms = **260-265 ms** (was 282 ms); the 200 ms target is
  not met and the 181 ms is driver-side reconfiguration. Throughput 57-58 fps,
  0 corrupt. Next options: soft recovery without REQBUFS, pre-opened spare fd,
  or accept.
  Note: CMA free is only ~106-115 MB; requesting 20 x 1080p buffers can yield 12
  and `STREAMON` EINVAL — use `--cap-bufs 17`. Backup
  `~/.codex_tmp/backup_d3_20261110_112758/deployed.tar` (`0ed6e107...`).

## Current device snapshot (2026-11-09 22:40 HKT, read-only)

- Identity: `armbian`, `aarch64`, kernel `6.18.59-ophub`, 4 cores, 1.7 GiB RAM,
  103 GB free on `/`, uptime 3 d 7 h, load 0.22.
- Video/decoder: `/dev/video0` has no opener; `meson_vdec` loaded, refcnt 0;
  `/dev/dri/{card0,card1,renderD128}` present; Xorg `:0`/tty7 reachable
  (`xdpyinfo` RC=0).
- USB: `2ca3:1020 DJI C5` enumerated on bus 1; `/dev/ttyACM0` (control) and
  `/dev/ttyACM1` exist. The VT link was already on during this snapshot.
- No `vt13_video`/`ffmpeg`/`ffplay` process was running.
- Remote working tree is **not** a Git repository; deployed-file hashes are the
  only consistency evidence. Current hashes: `config.py` `f47c7d9b...`,
  `pipeline.py` `c700b8cd...`, `ffmpeg_pipe.py` `871af9b2...`,
  `control.py` `cc0cbcdc...`, `decoder.py` `0a63d896...` (experimental),
  `.codex_runs/live_capture_run5.sh` `c0e35756...`,
  `~/ffmpeg-6.1.1-release/ffmpeg` `1ed2b711...`,
  `~/ffmpeg-6.1.1-v4l2/ffmpeg` `2a204518...`; venv PyAV 11.0.0.
- Live launcher config used by runs 15/17/18: `kernel_abort_watch=true`,
  `iframe_on_connect=true`, `stall_restart_s` 0 or 2, release Copy-Out FFmpeg,
  `convert_bgr=false`, `display=ffplay`, 1024×576 window, 1920×1080 source.

## USB rootfs topology (2026-11-10 00:06 HKT, U0 read-only)

- `/dev/sda2` (ext4) is the root filesystem on a **USB SG Flash**; `/dev/sda1`
  (vfat) is `/boot`. `TRAN=usb`, udev path
  `platform-xhci-hcd.2.auto-usb-0:2:1.0-scsi-0:0:0:0`.
- The DJI receiver `2ca3:1020` and the SG Flash are both on Bus 001,
  `xhci-hcd/2p` 480M (Port 001 and Port 002) → **same USB 2.0 host controller**.
- Swap is `zram0` (1 GB, RAM-backed); `/tmp` and `/dev/shm` are tmpfs
  (`/dev/shm` 894 MB). Root mount options: `noatime,nodiratime,commit=600,data=writeback`.
- No USB/UAS/reset/I-O/ext4 errors in the current boot journal; idle `wa=0`.
- Evidence: `.codex_tmp/u0_usb_rootfs_20261110/readonly.txt`. For future live
  tests, put recordings under `/dev/shm` to remove rootfs write-back from the
  shared-controller path (no system change needed).

## Kiosk state (2026-11-10 01:30 HKT)

- `lightdm` stopped; enable symlink removed (unit static); default target
  `multi-user.target`. HDMI shows the text console when no renderer runs; SSH
  is unaffected.
- Restore desktop: `sudo systemctl start lightdm` (and `chvt 7` if needed).
- KMS renderer: `tools/kms_render.c` (binary
  `~/.codex_tmp/kiosk_20261110/kms_render`, SHA256 `d3dc2d6e...`), invoked by
  the pipeline with `decoder.display: kms` (config `25004fb8`,
  ffmpeg_pipe `67a40898`).
- Live KMS result: 659 frames/60.9 s = 10.8 fps, 15 `0xf`, AU 48.5/s with
  display cap 25 + 50% GOP shed; regression KMS3: 625 frames/10.4 fps/14.
  ffplay same config: 529 frames/8.7 fps/17.

## Audit deliverables (archived 2026-11-10; backup under `.codex_tmp/docs_backup_20261110/`)

- U4-lite: recording to `/dev/shm` vs rootfs gave 541/14 vs 529/17 — no
  storage-interference evidence; U4 A/B not needed.
- `.codex_tmp/docs_backup_20261110/pipeline_bottleneck_analysis.md` — full-chain capacity/loss analysis
  (reset cycle dominant; consumer 50.7 vs 60.3 AU/s; 41% fed-AU→frame).
- `.codex_tmp/docs_backup_20261110/plan_review_20261110.md` — review of both plans against the
  2026-11-09/10 evidence (stage status, corrections, revised order).
- `.codex_tmp/docs_backup_20261110/dma_optimization_plan.md` — K2c: copy inventory + D1/D3 plan
  (ffmpeg->kms direct; custom V4L2 dmabuf->KMS zero-copy).
- `.codex_tmp/docs_backup_20261110/p2_2_display_feasibility.md` — P2-2: NV12 KMS overlay + hardware
  scaling feasibility, EXPBUF/DRM-master open issues, PoC plan. EXPBUF,
  PRIME_FD_TO_HANDLE and ADDFB2 runtime-verified (NV12 fb created); only the
  plane commit still needs DRM master (Xorg holds it).
- `.codex_tmp/docs_backup_20261110/0xf_layer_matrix.md` — U3: `0xf` layer classification and actionable
  fix layers (input damage first; padding is diagnostic only).
- `.codex_tmp/docs_backup_20261110/ffmpeg_lifecycle_comparison.md` — U2: FFmpeg V4L2 M2M lifecycle,
  refcount symmetry and Copy-Out comparison (audit only).
- `.codex_tmp/docs_backup_20261110/upstream_patch_matrix.md` — U1: upstream meson-vdec v7 19-patch
  status matrix against the local 6.18.59-ophub tree (audit only; no candidate
  approved for deployment).

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

## Agent non-interactive access status (2026-11-09: askpass authorized and used)

**2026-11-09 ~13:29 HKT: the user explicitly authorized the askpass pattern
below for this test window** ("why we need ssh-copy-id, cannot we use
askpass"). The agent extracted the password from this file into `SSH_PASSWORD`
at runtime (never echoed in commands or output), used a credential-free helper
at `.codex_tmp/v16_cm311_prep_20261109_122603/ssh-askpass.sh`, and reached
CM311 with RC=0. This authorization is window-limited; future sessions must
re-confirm before using the recorded password. Key auth is still not installed
(`BatchMode=yes` probes at 12:03/12:20/12:26 were RC=255); `ssh-copy-id` plus
password rotation remain the recommended hygiene fix.

Earlier re-probes at 2026-11-09 12:20 and 12:26 HKT: the same `BatchMode=yes`
command still returned RC=255 `Permission denied (publickey,password)`. A
read-only V16 pre-test script is prepared at
`.codex_tmp/v16_cm311_prep_20261109_122603/cm311_readonly_check.sh` (run on
CM311; checks PyAV `hevc_v4l2m2m` availability, idle state, module, USB
receiver, and remote source hashes). It was executed successfully via askpass
(output: `cm311_readonly_output.txt` in the same directory).

Verified from the Ubuntu PC:

- `ssh`, `scp`, `rsync`, `ssh-copy-id`, `ssh-agent`, `ssh-add` are installed.
  `sshpass` is **not** installed.
- `~/.ssh/config` defines `220.241.224.120` (`bguo`), `192.168.50.142` (`guest`),
  `10.192.1.3` (`guest`), and `github.com`. CM311 `10.42.0.11` has **no** Host
  block, so it is addressed directly as `billieguo@10.42.0.11`.
- The loaded agent identity and `~/.ssh/id_ed25519` are the same ED25519 key,
  fingerprint `SHA256:+EPYDiNosoF8tOu7qDJmQ74L9GXw++Fa/O4zcZBLUz4`.
- `ssh -T -o BatchMode=yes -o ConnectTimeout=8 billieguo@10.42.0.11 'hostname'`
  returned **RC=255**, `Permission denied (publickey,password)`. `ssh -v` shows
  the TCP connection and SSH handshake succeeded and the key was offered and
  rejected. The host is up; the public key is simply not authorized there.

Consequence: an agent shell cannot answer an interactive password prompt, so
agent-driven CM311 work is blocked until key auth is installed. The askpass
pattern below still works for a human-supplied credential, but agents must not
use the password recorded in this file (see `AGENTS.md` §5).

One-time fix, run by a human on the **Ubuntu PC** (precondition: CM311 reachable
on the LAN; you will be asked for the CM311 account password once):

```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub billieguo@10.42.0.11
```

Expected: `Number of key(s) added: 1`. Verify non-interactive access:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=8 billieguo@10.42.0.11 'hostname; uname -r'
```

Expected: `armbian`, `6.18.59-ophub`, RC=0. No remote service is restarted and no
existing `authorized_keys` entry is removed by `ssh-copy-id`; it appends.

Security note: this document stores the account and sudo password in plaintext
and is tracked in Git, so the credential is present in repo history. Rotate it
and move it out of the repository (environment variable, secret store, or key
auth only) before sharing this repo. Tracked as V17 in
`docs/INTERSESSION_TRANSFER.md`.

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

- 2026-11-08 19:54 HKT R0 precheck for the first live smoke test: CM311 identity is `armbian`/`aarch64`/`6.18.59-ophub`; no `vt13_video`/`ffmpeg` process and no `/dev/video0` opener. `/dev/dri` contains `card0`, `card1`, and `renderD128`; `DISPLAY` and `WAYLAND_DISPLAY` are empty over SSH; `loginctl` shows an active `seat0`/`tty7` session, but physical HDMI output is not verified. `python3 -m vt13_video --help` and `python3 -m vt13_video stream --help` both returned RC=0 and confirmed `--headless`, `--seconds`, `--record`, and `--json-stats`. `python3 -m vt13_video doctor` returned RC=1: no matching `2ca3:1020` device; `lsusb` currently shows only the root hub and `23a9:ef18` SG Flash. The USB receiver must be connected/enumerated before live capture can run. `.codex_runs/live_capture_verified.sh` is still missing. Evidence: `.codex_tmp/r0_precheck_20261108_1941/precheck.txt`, SHA256 `d8b7306e2b646bc7f27389184a231d38a32940c72e732941e9aa1f288cb66e51`. No live USB/HDMI/wireless run occurred and no CM311 files were modified.

- 2026-11-08 20:25-20:31 HKT offline soft/hardware rate benchmark: `clean_1832x1032.h265` hardware `hevc_v4l2m2m` produced 30 frames RC=0 with wall 1.212 s, user 1.563 s, sys 0.322 s; software `hevc` produced 30 frames RC=0 with wall 1.621 s, user 2.890 s, sys 0.334 s, FFmpeg bench rtime 0.802 s, maxrss 123488 kB. FrameMD5 matched 29/30; the last hardware frame was `1517d50f...` versus software `133559bb...`. `pad_1024.h265` is 1920x1080 with ffprobe `r_frame_rate=60/1` and `avg_frame_rate=25/1`; hardware produced 38 frames RC=0 with wall 1.585 s, user 1.984 s, sys 0.489 s, bench rtime 1.248 s, maxrss 118032 kB; software produced 38 frames RC=0 with wall 2.295 s, user 5.243 s, sys 0.443 s, bench rtime 1.472 s, maxrss 143528 kB. FrameMD5 matched 36/38, differing at frames 37/38 (0-based index 36/37). These are short-sample end-to-end FFmpeg+FrameMD5 benchmarks, not steady-state FPS: hardware was about 24 fps wall, software about 16-18 fps wall; the 30-50 fps target remains unproven. Evidence: `~/mobile_vt/.codex_tmp/cm311_hw_bench_20261108_202504/` and `~/mobile_vt/.codex_tmp/cm311_hw_bench_pad_20261108_203050/`; local copies have matching manifests (14 and 12 files). Code inspection: `vt13_video/decoder.py` uses `av.CodecContext.create("hevc", "r")`, so the current Python live/replay path is software PyAV decode, not the custom FFmpeg hardware decoder. No live USB/HDMI/wireless run occurred.

- 2026-11-09 12:20-12:21 HKT PC-side V16 opt-in step (Ubuntu PC only; no CM311 command succeeded): SSH key-auth re-probe still RC=255 (V17). The PC worktree now accepts `decoder.codec: hevc_v4l2m2m` (config whitelist extended; default remains `hevc`), logs `HEVC decoder context created: requested=... actual=...`, and exposes `codec` in the decoder snapshot/`--json-stats`. Local regression: 54 tests RC=0 (3.191 s). Golden offline replay: default config RC=0, 105 frames, 0 errors (baseline unchanged); v4l2m2m config RC=1, 0 frames, `avcodec_open2` EINVAL because the PC has no V4L2 M2M HEVC device — a fail-safe negative control, not hardware acceptance. Evidence: `.codex_tmp/v16_pc_optin_20261109_122037/` (logs + SHA256 manifests). Changes are uncommitted. Next on CM311 after V17: check whether PyAV 11.0.0 exposes `hevc_v4l2m2m`, then run a bounded offline golden replay with the v4l2m2m config. Caution: PyAV links its own FFmpeg, not the patched `~/ffmpeg-6.1.1-v4l2` build, so Copy-Out/refcount workarounds do not apply and source-change hangs are possible; fallbacks are rebuilding PyAV against the custom libraries or an FFmpeg-subprocess backend.

- 2026-11-09 13:29-13:41 HKT CM311 V16 hardware-decode verification (user-authorized askpass; no remote working-tree file modified): read-only inventory confirmed idle device, **PyAV 11.0.0 `hevc_v4l2m2m` available=True**, `meson_vdec` loaded refcount 0, USB `2ca3:1020` absent; remote `decoder.py`/`pipeline.py` hashes match the 2026-11-06 snapshot and remote `config.py` equals local HEAD (`062b4ccc...`). Raw clean-sample PyAV comparison: SW/HW 30 frames each RC=0, YUV MD5 29/30 (last frame differs), cross-checked against the 2026-11-08 CLI evidence (SW 30/30 and HW 29/30 identical; PyAV HW last frame `2a745ea3...` vs CLI `1517d50f...`). Full-pipeline golden replay via real `VT13Stream` (codec set by direct dataclass assignment): SW 105 frames/0 errors; HW 80 frames, EIO×3 → 1 reset → IRAP resync at the 1832→1920 source change, 25 frames lost, automatic recovery without hang, reproduced twice; YUV-layer comparison 1832 section 8/8 and 1920 section 71/72 bit-identical (last frame only). BGR-layer hashes differ everywhere due to swscale NV12→BGR vs YUV420P→BGR rounding (mean 0.44/255; common yuv420p intermediate MD5 identical) — acceptance must compare YUV. Transient `capture POLLERR`→EIO on the first device open after the aborted session; a fresh open minutes later succeeded without R3. Evidence run dirs: `v16_cm311_pyav_v2_20261109_133245`, `v16_cm311_pipeline_20261109_133439`, `v16_cm311_pyav_v2_20261109_133812`, `v16_cm311_pipeline_yuv_20261109_133941` (remote `~/mobile_vt/.codex_tmp/`, local copies under the same relative paths); 30 files, local/remote manifests all matched (`.codex_tmp/manifests_20261109/`). Post-run 13:41:12 HKT: device idle. No live USB/HDMI/wireless run, no reboot/module reload/package install, no commit.

- 2026-11-09 14:06-14:15 HKT pre-build backup and Phase A launch (Plan 2): backup of CM311 FFmpeg source (tar + `git diff` patch + HEAD/status), `~/mobile_vt/{vt13_video,tests,config}` tar, and PC uncommitted changes stored at PC absolute path `/home/billieguo/billie_guo/src/rm/mobile_vt/.codex_tmp/backup_before_plan2_20261109_140638` (manifest `BACKUP_MANIFEST.md`, all SHA256 verified); CM311 mirror `~/mobile_vt/.codex_tmp/backup_plan2_20261109_140638`. Out-of-tree configure was rejected ("config.h in source dir"); instead `git archive HEAD` + backup patch extracted to NEW dir `~/ffmpeg-6.1.1-v4l2-shared`, 3 patched files SHA256-identical to the original tree, configured `--enable-shared --disable-static --prefix=$HOME/ffmpeg-6.1.1-v4l2-shared/install` (RC=0), `make -j2` running under `timeout -k 60 2400` (PID 46044), logs in `~/mobile_vt/.codex_tmp/plan2_build_20261109_140638/`. Original FFmpeg tree/binary untouched. Phase B will build PyAV 11.0.0 into `~/mobile_vt/.venv-v4l2` (system-site-packages venv; system av untouched). No source rewrite yet; no commit; no live run.

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

| Item | Status (latest evidence) | Evidence needed |
|---|---|---|
| Latest capture pointer | Missing | `test -f /tmp/dji_test_latest_dir`; explicit capture root; do not guess |
| Idle/ownership | 2026-11-09 13:41 HKT post-run: no `vt13_video`/`ffmpeg` process, `/dev/video0` no opener, source `meson_vdec` refcount 0; USB receiver not enumerated | Re-check immediately before a live or hardware run; do not kill; require `doctor` RC=0 |
| USB receiver enumeration | 2026-11-08 19:54 HKT `doctor` RC=1; `lsusb` has no `2ca3:1020`; only root hub and `23a9:ef18` SG Flash are present | Connect/enable the receiver; `doctor` RC=0; `lsusb -d 2ca3:1020`; usbfs access |
| Display stack | Partially checked: `/dev/dri` has `card0`/`card1`/`renderD128`; SSH `DISPLAY`/`WAYLAND_DISPLAY` are empty; `loginctl` shows active `seat0`/`tty7`; physical HDMI output not verified | `ls /dev/dri`, `DISPLAY`, `loginctl`, and actual HDMI output evidence |
| `vt13_video` stream/READY | `--help` and `stream --help` returned RC=0; confirmed `--headless`, `--seconds`, `--record`, `--json-stats`; source has no literal `READY`, so use `USB source open` plus a `waiting_*` state as readiness evidence; current decoder path is PyAV software `hevc`; stream not run yet | Real `stream` command, READY evidence, stop/exit method; confirm decoder identity at runtime |
| Live pipeline hardware decode integration | **PyAV-native verified; patched venv built (2026-11-09)**: system PyAV 11.0.0 and rebuilt venv PyAV (`~/mobile_vt/.venv-v4l2`, ldd-verified against `~/ffmpeg-6.1.1-v4l2-shared/install`) both decode raw clean 29/30 YUV-correct. Golden pipeline loss (25 frames) root-caused via dmesg to **POC8 `HEVC_LCU_CHECK status=0xf` firmware abort** (P0 family, deterministic ×6, gap-independent) — NOT source change; Copy-Out does not fix it. Emitted frames YUV-identical (1832 8/8, 1920 71/72); compare YUV not BGR (swscale artifact) | P0 `0xf` driver/firmware investigation; clean synthetic switch stream to isolate Copy-Out reinit; long-run FPS/CPU/RSS/temperature; Phase D live smoke (R2) for IRAP cadence + live `0xf` occurrence |
| `/dev/video0` function | Source `meson-vdec` loaded; V4L2 output formats include `HEVC`; clean and EOF offline hardware runs executed | `v4l2-ctl --all`; meson-vdec binding; no conflicting opener |
| Custom FFmpeg decode | 2026-11-08 `-fps_mode passthrough`: clean 30 frames RC=0, 29/30; `no_sei` POC21 `0xf` RC=134, 14-frame prefix all matching; `fresh_45_to_82` POC50 `0xf` RC=134, 32-frame prefix all matching; `pad_1024` 38 frames RC=0, 36/38; EOF `aud` 3x repeat all RC=137/19 frames and identical (cross-window counts 22/18/19), `eos` 20 frames RC=134, `zeros` 27 frames 26/27. Rate benchmark: clean HW 30/1.212 s vs SW 30/1.621 s; pad 1920x1080 HW 38/1.585 s vs SW 38/2.295 s; short-sample, not steady-state | Explain/fix `0xf`, padding mismatch, and EOF drain; explain `aud` cross-window timeout count; add more real samples; run long-duration FPS/CPU/RSS/temperature/latency tests |
| Kernel module/VDEC | R3 loaded source module (`ca46...`) with matching vermagic; HEVC advertised; 2026-11-08 dmesg shows `status=0x8` and `status=0xf` (POC21 for `no_sei`, POC50 for `fresh`); `pad` shows only `0x8` plus two missing-reference substitutions | `uname -r`, `lsmod`, module vermagic, `dmesg`, `status=0x8/0xf`; explain EOF state machine |
| Source Change/POC50/EOF | 2026-11-08 expanded matrix: EOF SW 27 frames remains identical; HW `aud`/`eos` drain failed, `zeros` 26/27; `pad_1024` RC=0 but 36/38 (first mismatch index 36); `aud` same-window 3x was 19 frames and identical, but cross-window counts were 22/18/19 | Explain/fix EOF drain/flush and `0xf`; explain timeout-window frame-count variation; validate padding content differences |
| Live wireless end-to-end | Not started; blocked by USB receiver enumeration; current Python pipeline uses software PyAV `hevc` | AGENTS.md §6 handoff; READY before human opens link; confirm hardware decode integration |
| Performance/latency targets | User targets unconfirmed; short-sample benchmark hardware about 24 fps wall, software about 16-18 fps wall; not steady-state | User acceptance plus CM311 long-run CPU/RSS/temperature/latency evidence |
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

### Control port and on-demand I-frame request (DUML)

The receiver exposes two CDC-ACM ports: `/dev/ttyACM0` is the DUML control
channel (interface 2, "DJI USB VCOM For Protocol") and `/dev/ttyACM1` is the
debug console (interface 4). The pipeline opens `ttyACM0` only when
`control.enabled: true`; otherwise the port remains free for the standalone
probe below.

The official client asks the transmitter for an I-frame on connect and whenever
its decoder needs a keyframe (DUML command set 1 / id 1 to module 14/0). The
pipeline now sends the same frame, plus a 1 Hz pairing query:

```yaml
control:
  enabled: true            # opt-in; video path unchanged
  port: null               # null = auto-detect interface 2
  iframe_on_connect: true
  iframe_on_recovery: true
  iframe_retry_s: 2.0      # retry while waiting for a keyframe
  min_iframe_interval_s: 0.5
  pairing_poll_s: 1.0
decoder:
  stall_restart_s: 5.0     # optional silent-0xf watchdog; 0 disables
```

The exact request frame (verified byte-for-byte against the official client):

```text
55 17 04 38 aa 0e 00 00 40 01 01 00 00 00 00 00 24 00 00 00 24 8f 06
```

For a control-only test without changing the pipeline config, the standalone
probe remains available (copy the single dependency-free file first):

```bash
cd ~/mobile_vt
python3 .codex_tmp/rmrx_probe/vt_iframe_probe.py \
  --port /dev/ttyACM0 --repeat 12 --interval 5
```

Watch `capture.log` / JSON stats for `control: requested I-frame`, new IRAPs
(`keyframe_starts`), and dmesg recovery after `0xf`. Port access relies on the
same udev `uaccess` rule as the video interface; over SSH the active `tty7`
session currently supplies the ACL.

Live results (2026-11-09): run 5 proved the transmitter honors the request
(10/10, IRAP in 37–162 ms); run 6 ran 150 s at 1920×1080 with 34 watchdog
resets, 565 frames, display starts = 1, USB 0 errors/timeouts, and 29 kernel
`0xf` aborts. The on-connect request started decoding in 0.2 s when the VT was
already on. The remaining instability is the 1080p `0xf` cadence; run 4 at
1832×1032 had 1 abort in 90 s. Next A/B: lock the transmitter to
1832×1032@30 and rerun the same launcher with `DJI_STALL_RESTART_S=2.0`.

### Capture-layer A/B: PyUSB vs `rmrx dump`

Staged on the PC under `.codex_tmp/rmrx_probe/`:

- `rmrx-aarch64-musl` — static aarch64 CLI, SHA256 `b05a5fbe...` (3,281,112 B)
- `capture_pyusb.py` — pure capture via the pipeline's `VT13UsbSource`
- `timestamp_stdin.py` — timestamps `rmrx dump -` output
- `summarize_capture.py` — bytes/AU/IRAP/gap comparison
- `live_capture_run5.sh` — run-4 pipeline + control + watchdog

Copy them to CM311, then run one mode at a time on the same link:

```bash
# A: PyUSB capture only (no decode, no control); enable VT after READY
cd ~/mobile_vt
.venv-v4l2/bin/python .codex_tmp/rmrx_probe/capture_pyusb.py \
  captures/ab_$(date +%Y%m%d_%H%M%S)_pyusb.bin --seconds 60
```

```bash
# B: Rust capture; --port /dev/null disables control for a fair A/B.
# READY evidence: "VideoConnected" in the log, then enable VT.
cd ~/mobile_vt
RUST_LOG=info .codex_tmp/rmrx_probe/rmrx-aarch64-musl --port /dev/null \
  dump - --seconds 60 2>rmrx_capture.log \
  | .venv-v4l2/bin/python .codex_tmp/rmrx_probe/timestamp_stdin.py \
      captures/ab_$(date +%Y%m%d_%H%M%S)_rmrx.h265
```

Compare with `summarize_capture.py <A> <B>`. Sequential runs are not
RF-identical; repeat 2–3 times and compare medians. The rmrx binary's musl
runtime on CM311 is still unverified — run `rmrx --help` first.

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
