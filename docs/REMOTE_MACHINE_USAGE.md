# Remote Machine Usage Reference

## eMMC-only cold boot / G6 — PASS_WITH_LIMITATION (2026-11-13 02:03 HKT; HDMI visual and physical hotplug pending)

> G6 was authorized and executed. No reboot, module reload, or golden-data
> overwrite occurred. It included one manual `vt13-kiosk.service` restart and
> one kernel USB `unbind/bind` hotplug simulation.

- The SG USB was physically removed and the board was powered on. The board
  boot time is `2026-11-12 23:40:55 HKT`, after the G5 `poweroff` at
  `23:19:57 HKT`.
- The old `10.42.0.11` address is no longer assigned. The PC profile
  `cm311-local` provides shared DHCP (`10.42.0.10-254`), and CM311 is currently
  at `10.42.0.253`. This is a dynamic lease; rediscover it before G6 if the
  lease changes.
- Root is `/dev/mmcblk2p2` ext4 UUID `61e6bfac-70ad-4d87-92db-a7399341722c`;
  `/boot` is `/dev/mmcblk2p1` vfat UUID `EE59-E094`. `lsblk` shows only the
  eMMC devices and `zram0`, with no USB block disk.
- SG Flash `23a9:ef18` is absent; DJI receiver `2ca3:1020` is present.
  `systemctl --failed` reports 0 units. `vt13-kiosk.service` is enabled and
  active with `MainPID=433`, `NRestarts=0`. `meson_vdec` is loaded (refcount 2)
  and `/etc/modules-load.d/vt13-vdec.conf` contains `meson_vdec`.
- Root free space is about 3.4 GiB with 354,636 free inodes; `/boot` has about
  352 MiB free.
- Evidence: `.codex_tmp/emmc_deploy_20261112/g6_coldboot_20261113_0055/g6_coldboot_precheck.txt`
  SHA256 `9c0ef4168c13d4ae03618b18fbb075c9b4ae2520d9ebe2a5cad4fa2a1a32bbbe`;
  summary `G6_COLDBOOT_PRECHECK.md`.
- **G6 layered result**: eMMC-only boot, fstab/uEnv/DTB and boot-file hashes,
  ca46 hash/vermagic, firmware, worker/config/service/runtime hashes, user
  permissions, system Python/PyAV, V4L2 HEVC output, and HDMI-A-1
  connected/enabled all passed. The live path reached ~60 FPS with
  `corrupt=0`; the service restart returned RC=0 and kept `NRestarts=0`.
- **G6 limitations**: the agent verified connector/plane/frame counters, not
  actual HDMI pixels; the user must visually confirm the picture. Physical USB
  hotplug was simulated with kernel `unbind/bind` (this kernel has no `rebind`
  attribute); the manual `bind` required `udevadm trigger` to restore the
  libusb ACL. A real connector pull remains the stronger test.
- **Residual live errors**: cold boot had a concentrated startup `0xf` burst
  (122 errors / 42 recoveries at 01:29-01:33, mostly 23:59:13-23:59:30), then
  isolated recoveries through 01:16:51. After the 01:47:23 manual restart the
  clean session had 0 errors / 0 recoveries, but content-dependent `0xf`
  occurred at 01:51:48 and 01:56:45 and auto-recovered. The service remained
  active throughout; no SSH loss.
- **Evidence**: `.codex_tmp/emmc_deploy_20261112/g6_validation_20261113_0110/`
  contains `G6_FINAL_REPORT.md`, layer/error/restart/USB/final-state logs and
  `SHA256SUMS` (9/9 OK). The remote copy has 10 files with matching SHA256;
  the cold-boot evidence copy has 3 matching files.
- **Next**: user visually confirms HDMI; optionally performs one physical DJI
  receiver unplug/replug and reports the result. Do not start G7/G8 until that
  confirmation is recorded.

- **02:12 HKT read-only post-check**: the board remained at `10.42.0.253` with
  `/` on `/dev/mmcblk2p2` and `/boot` on `/dev/mmcblk2p1`; no USB block disk
  was present. `vt13-kiosk.service` remained active with the same
  `MainPID=2935`, worker PID 2937 and `NRestarts=0`; `HDMI-A-1` remained
  `connected/enabled`. Latest counters were 78,937 frames, 60.0 FPS, 38
  errors / 1 recovery, `corrupt=0`, `backlog_max=0`, sessions=5. Boot time was
  confirmed as `2026-11-12 23:40:55 HKT` via `uptime -s` and PID 1 `lstart`;
  `who -b` displayed 21:59 due to a wtmp discrepancy. Evidence:
  `.codex_tmp/emmc_deploy_20261112/g6_postcheck_20261113_0211/g6_postcheck.txt`
  SHA256 `49919c75639340fe65abf68d6ccc2edd25480ab555623126a2c93f03a5054bb6`;
  remote `sha256sum -c` OK.

- **02:39 HKT HDMI black-screen diagnostic**: the user reported a black HDMI
  picture while the service still streamed at ~60 FPS with `corrupt=0`. The
  worker had inherited the console's `1920x1080i` CRTC mode and had no
  `--mode` argument; DRM showed the overlay plane active with NV12 while the
  primary plane was disabled. A runtime-only `VT13_WORKER_MODE=1920x1080@60`
  plus `VT13_WORKER_DUMP_FIRST=.../first` restart produced progressive
  1920x1080@60, an active overlay plane, and dumped frames with
  `Y_mean≈109` (non-black). This proves the decoder output is not black and
  points to KMS presentation. Visual confirmation of the temporary 1080p60
  test is still pending; no source/config/service file was changed. Evidence:
  `.codex_tmp/emmc_deploy_20261112/g6_hdmi_black_20261113_023851/diagnostic.txt`
  SHA256 `bd7893fe700936a62ad103b85d49fd78cf415621fd43903ef551fd73e11d54eb`;
  remote hash check OK.

## Current development stage (2026-11-13 12:37 HKT — G5 PASS; eMMC cold boot PASS; G6 user-confirmed HDMI/hotplug/cold start/reboot; rotation deployed but visually unconfirmed; ~29.7 FPS)

> G6's previously pending HDMI output and physical hotplug were confirmed by the
> user. The display-rotation service restart changed only the worker binary and
> source; no reboot, module change, or golden-data overwrite occurred.

**Stage: K3 service deployment — `ACCEPTED_WITH_LIMITATION`; display rotation is
`IMPLEMENTED / VISUALLY UNCONFIRMED`.**

| Area | Status | Evidence / remaining limit |
|---|---|---|
| D3-0 DMA-BUF/KMS feasibility | verified | Real NV12M CAPTURE buffers exported/imported and scanned out on the overlay plane. |
| D3a native V4L2 HEVC + KMS file replay | verified | Native C worker decodes and presents recorded HEVC without PyAV/FFmpeg in the hot path. |
| D3b socket AU worker | verified | Python USB/DUML control plane feeds the C worker over `SOCK_SEQPACKET`; 60 AU/s offline replay demonstrated. |
| D3c in-process recovery | verified | Fatal/POLLERR/source-change paths rebuild the V4L2 session without a systemd restart; hotplug test kept `NRestarts=0`. |
| Source Change repair | verified | Cold-start `1832x1032 → 1920x1080` wedge fixed; offline A/B, hardware replay, in-situ cold start, and visual check passed. Current worker includes this repair; the rotation variant is `build/d3/d3_probe d1257c49…`, source `tools/d3_probe.c 6838cd3e…`. |
| systemd kiosk | installed/enabled | `vt13-kiosk.service` runs as `billieguo`, `VT13_ASYNC_USB=0`, `VT13_WORKER_ROTATION=180`, `Restart=always`, `MemoryMax=512M`, dedicated volatile `vt13-kiosk` journal namespace. ExecStart uses `/usr/bin/python3`; the native worker has only a libc dependency. |
| Display 180° rotation | implemented / visual unconfirmed | Meson overlay plane 42 has **no DRM `rotation` property**. The worker uses a software fallback: four NV12 scratch dumb framebuffers, cached staging copy, and NEON row/UV-pair reversal. Service `MainPID=15994`, worker 15996, `NRestarts=0`; DRM scans scratch `fb=49`, `imported=no`. Live observation is ~29.7 FPS, `corrupt=0`, 0 errors/recoveries; user must confirm orientation. |
| ca46 `meson-vdec` module | permanently installed | Source build `ca467983…` replaced the stock `a6cc08ca…` module; cold boot after a hard power cycle auto-loaded ca46 and decoded. Backup `meson-vdec.ko.a6cc08ca.bak` retained. |
| Cold-boot acceptance | verified (user-confirmed) | User reports HDMI output, physical hotplug, cold start, and start-from-reboot all work. Cleanest observed boot was ~60.4 fps, `sessions=1`, `corrupt=0`, 0 errors, 0 `0xf`; formal G8 still requires three independent cold boots plus one supervised soft reboot. |
| Residual `0xf` | **open** | Content-dependent firmware/driver abort still occurs; automatic recovery produces roughly 217–283 ms freezes. Root cause not fixed. |
| Startup `0xf` bursts | **open** | Some boots show an initial burst before settling; automatic recovery handles it, but it is not eliminated. |
| Soft reboot | **open** | One `systemctl reboot` after the module install hung (black screen, no SSH); a hard power cycle recovered. Cold boot works; monitor soft-reboot reliability. |
| Glass-to-glass latency | **not measured** | Internal frame age (~22–35 ms) is not camera-to-photon latency. |
| Final-worker 30-min soak | optional / not done | Earlier K3 soak used `51346c85`; the current `d1257c49` rotation worker + ca46 combination has not had a fresh 30-minute soak. |
| G6 eMMC-only cold boot | **PASS (user-confirmed)** | eMMC-only boot, ca46/firmware, worker/config/service hashes, HDMI connector, V4L2 HEVC, ~60 FPS live path and `corrupt=0` verified. User then confirmed HDMI output, physical hotplug, cold start, and reboot all work. Formal G8 still requires three independent cold boots plus one supervised soft reboot. Residual content-dependent `0xf` remains open. |
| eMMC migration | G2 PASS; G3/G4 recommended; **G5 PASS**; eMMC cold-boot precondition PASS; **G6 PASS (user-confirmed)** | Installer RC=0 with ampart/ext4; `BOOT_EMMC` at 117 MiB and `ROOTFS_EMMC` at 629 MiB; required runtime/module/firmware/service/KMS checks passed. Evidence saved and SHA256-verified locally/remotely. SG USB preserved but physically removed for normal boot. After SG USB removal, CM311 cold-booted from `/dev/mmcblk2p2` and `/dev/mmcblk2p1` at 23:40:55 HKT; current SSH is `10.42.0.253` via shared DHCP. Formal G8 remains open. |
| Remote Git parity | hash-based only | CM311 `~/mobile_vt` is not a valid Git repository; runtime parity is checked with SHA256 manifests. |
| Kiosk logs | volatile | `LogNamespace=vt13-kiosk` uses volatile storage; logs do not survive reboot. |

**Plan status**

- `plans/CM311_D3_Native_V4L2_KMS_Execution_Plan.md`: historical execution
  plan. D3-0, D3a, D3b, D3c, D3d, and K3 have been implemented; the plan is no
  longer the current work queue.
- `plans/CM311_DJI_C5_Low_Latency_60FPS_Optimization_Plan.md`: RC1 was
  `ACCEPTED_WITH_LIMITATION`; L1 glass-to-glass measurement is still missing,
  L2-B is only partially executed, and the R1 `0xf`/freeze work remains open.
- `plans/CM311_HEVC_Recovery_Performance_Plan.md` and
  `plans/CM311_VDEC_Upstream_Audit_USB_RootFS_Plan.md`: audit and next-step
  plans. Upstream meson-vdec patches are audited but not fully deployed.

**Current deployment topology (2026-11-13)**: the internal eMMC is the active
boot/root: `/` is `/dev/mmcblk2p2` ext4 and `/boot` is `/dev/mmcblk2p1` vfat.
The SG Flash (`23a9:ef18`) is physically absent during normal boot; the DJI
receiver (`2ca3:1020`) is present. The SG USB remains the preserved fallback but
must not be inserted when validating eMMC-only boot.

**Display rotation evidence (2026-11-13 12:37 HKT)**:

- `tools/d3_probe.c` now supports `--rotation 0|90|180|270`; for 180° it first
  tries the DRM rotation property and falls back to the software path when the
  property is absent.
- The software path creates four 1920x1080 NV12 scratch framebuffers, copies the
  decoded dmabuf into a cached staging buffer with a NEON loop, reverses Y rows
  and UV pairs, then presents the scratch framebuffer. No bitstream/decoder or
  kernel change is involved.
- Live timing after deployment: `stage_copy_avg_ms≈17.2–17.7`,
  `rot_copy_avg_ms≈2.8–2.9`, `setplane_avg_ms≈12.2–12.7`; about 29.7 FPS with
  `corrupt=0` and no errors/recoveries during the 30-second observation.
- **Visual direction is still unconfirmed.** Do not record the rotation as
  visually fixed until the user confirms it. If the orientation is still wrong,
  distinguish 180° rotation from vertical-only or horizontal-only flip.
- Evidence: `.codex_tmp/emmc_deploy_20261112/g7_rotation_stage_20261113_1226/`
  with `SHA256SUMS` 29/29 OK locally and remotely; manifest SHA256
  `e337cce734d09715d8642ab54e1534dc834f8d19d56619210bed1c8ed70be69a`.

## G2 backup verification — PASS (2026-11-12 14:59 HKT)

- Backup root: `/home/billieguo/cm311-deployment/backups/cm311-sg-20261112_121131` (about 12 GiB). The backup includes rootfs, boot, kernel/module, FFmpeg source/install, PyAV venv, runtime tree, captures, Codex temp data, and service logs.
- `SHA256SUMS`: **28/28 OK**, failures 0, stderr empty. The original 27-entry manifest was supplemented with `sg-rootfs-toplinks.tar` (`f6847974…`) because `sg-rootfs.tar` only covered `etc/home/opt/root/srv/usr/var`; the supplement records `bin -> usr/bin`, `lib -> usr/lib`, and `sbin -> usr/sbin`.
- Archive readability: **10/10** archives passed `tar -tf`; all `.tgz` archives passed `gzip -t`; overall RC=0, stderr 0 bytes.
- Sample restore: worker, config, ca46 module, service/journald, and boot/uEnv/DTB extracted and verified. Restored files **17/17 OK**, direct boot copies **4/4 OK**, cross-archive comparisons **6/6 MATCH**; modes preserved. Worker `eb1dbb67…`, ca46 `ca467983…`, service `15ade4bb…`, uEnv `2b488bb1…`, DTB `1a568548…`/`6bdcf618…`.
- **Installed udev rule**: `/etc/udev/rules.d/99-vt13.rules` exists with SHA256 `9509a4c1…` and uses `MODE=0660`, `GROUP=plugdev`, `TAG+=uaccess`. The repo source at G2 backup time was `6d9b78ee…`; the current repo source is `4455e3b2…`, which has the same effective rule plus explanatory comments. The G1 `MISSING /etc/udev/rules.d/99-vt13-video.rules` was a filename mismatch, not a missing installed rule. Preserve the installed rule during deployment unless deliberately changing behavior.
- `codex_tmp.tgz` was created from a live `.codex_tmp`; its wrapper aggregate status was 1 because directory/socket state changed during archive creation. The archive itself passes `tar -tf`/`gzip -t`, and a sampled payload extraction matches its recorded hash.
- Sample extraction ran as PC user `1001:1001`; root-owned entries therefore show that uid/gid on the PC. Archive metadata remains authoritative: installed service/module and boot files are `0/0`; extracted modes were preserved.
- `sg-rootfs.tar` is a file-level backup of selected directories, not a block-level disk image. No original eMMC image was taken because `/dev/mmcblk2` currently has no partitions or mounted data.
- Evidence: `.codex_tmp/emmc_deploy_20261112/g2/archive_readability_20261112_145703.txt`, `.codex_tmp/emmc_deploy_20261112/g2/restore_verify_corrected_20261112_150929.txt`, and `G2_REPORT.md` (copied into the backup root). No USB/HDMI/wireless run, reboot, module reload, or eMMC write occurred.
- **Gate decision: G2 PASS** for the stated backup scope. G3/G4 may proceed; G5 eMMC installation still requires explicit human approval.

## G5 authorization and final read-only preflight — PASS (2026-11-12 22:12 HKT)

- **Authorization**: the user explicitly approved G5 eMMC installation for CM311-1S / S905L3B, target `/dev/mmcblk2`, ext4, DTB `meson-gxl-s905l3b-m302a-gxl-test.dtb`.
- **Preflight command**: Ubuntu PC ran `bash deploy/g5-run-from-pc.sh --preflight-only`; interactive SSH/sudo was used only for the prompt. Result: `G5_PREFLIGHT_OK`, `G5_PREFLIGHT_ONLY_COMPLETE`, RC=0. No eMMC write, service stop, reboot, module reload, or USB/HDMI/wireless run.
- **Passed checks**: target size `7,474,249,728 B`; source `/`=`/dev/sda2` ext4 and `/boot`=`/dev/sda1` vfat; target unmounted; eMMC first 4 MiB/boot0/boot1 all `f61b153c…90262`; source `/boot` seven reviewed hashes, KMS helper hashes, and installer/patch/exclude/service hashes all match. PC backup recheck: `28/28 OK`.
- **Current state**: SG USB remains the boot device; `vt13-kiosk.service` active (MainPID=447, NRestarts=0). eMMC has no partition table yet. After install, the wrapper must observe p1 start at 117 MiB (ampart) or 128 MiB (fallback), both beyond the reserved 4 MiB bootloader region.
- **UART**: `picocom` is installed on the PC; no `/dev/ttyUSB*` was enumerated at check time, so physical UART/recovery availability is recorded from the user's authorization. The previously observed recovery method remains: with SG USB connected, a serial-console `reboot` has started USB Armbian; this is observed, not guaranteed after eMMC flashing.
- **Evidence**: local `.codex_tmp/emmc_deploy_20261112/g5_pc_20261112_221209/` (`preflight-session.log` `64c6c9f2…b3a`, `preflight.txt` `b134db8e…1cf`, `g5-result.env` `773e939e…ab0`); remote `~/mobile_vt/.codex_tmp/emmc_deploy_20261112/g5/run_20261112_221223/`.
- **Next**: run the reviewed installer with `127`, `1` (ext4), validate the installed eMMC, save and verify logs/evidence/bootloader/MBR backups, then `sync` + `poweroff`. Stop before G6.

## G5 installer completed; wrapper post-validation false-failed (2026-11-12 22:41 HKT)

- **Installer result**: selections were exactly `127` and `1` (ext4). The installer returned RC=0 and logged `Successfully repartitioned eMMC with ampart.` plus `Installation completed successfully`.
- **Actual target geometry**: `/dev/mmcblk2` is `7,474,249,728 B`; `mmcblk2p1` is vfat `BOOT_EMMC`, START=239616 sectors (=122,683,392 B = 117 MiB), SIZE=535,822,336 B; `mmcblk2p2` is ext4 `ROOTFS_EMMC`, START=1,288,192 sectors (=659,554,304 B = 629 MiB), SIZE=6,814,695,424 B. The boot partition starts beyond the reserved 4 MiB bootloader area.
- **Why the wrapper failed**: `deploy/g5-install-wrapper.sh` compares `lsblk -bno START` values, which are 512-byte sectors, against byte constants in `validate_install()` around lines 221–235. It reported `p1_start=239616 p2_start=1288192`; multiplying by 512 yields the approved ampart starts. This is a validator unit bug, not a partition-layout failure.
- **Finalization state**: wrapper exited before mounting the target, so `g5-result.env` is `STATUS=FAILED`; no `postinstall-evidence.txt` exists; the PC runner did not transfer log/evidence/bootloader/MBR and did not issue final `sync` + `poweroff`.
- **Current boot state**: SG USB remains the boot source (`/`=`/dev/sda2`, `/boot`=`/dev/sda1`). The runner trap restarted `vt13-kiosk.service`; active, MainPID=35832, NRestarts=0. No reboot or poweroff occurred.
- **Evidence**: local `.codex_tmp/emmc_deploy_20261112/g5_pc_20261112_223331/install-session.log`; remote `~/mobile_vt/.codex_tmp/emmc_deploy_20261112/g5/run_20261112_223446/armbian-install.log` and `g5-result.env`.
- **Next**: do not rerun the installer. Perform read-only eMMC validation with corrected sector-to-byte conversion, export the install log, bootloader 4 MiB image, and post-install MBR first 512 B, transfer to the PC, verify SHA256/sizes, then `sync` + `poweroff`. A wrapper unit fix and hash reapproval are optional if the original `G5_VALIDATED` marker path is required; no eMMC rewrite is needed.

## G5 final result — PASS; evidence saved/verified; poweroff issued (2026-11-12 23:19 HKT)

- **Status**: G5 **PASS**. The installer completed with RC=0; the eMMC was not rewritten after validation.
- **Layout**: `/dev/mmcblk2` `7,474,249,728 B`; `mmcblk2p1` vfat `BOOT_EMMC`, START=122,683,392 B (117 MiB), SIZE=535,822,336 B; `mmcblk2p2` ext4 `ROOTFS_EMMC`, START=659,554,304 B (629 MiB), SIZE=6,814,695,424 B, UUID `61e6bfac-70ad-4d87-92db-a7399341722c`. The boot partition is beyond the reserved 4 MiB bootloader region.
- **Validation**: a temporary validation-only wrapper copy (`f0d71787…`) corrected the `lsblk START` sectors-to-bytes conversion and the incompatible `df -i --output=iavail` invocation; the reviewed original wrapper was not modified. It returned `G5_VALIDATED`. Boot files, uEnv, fstab/root UUID, ca46 module, firmware, native worker, system Python/PyAV closure, non-root service/enable symlink, udev rule, journald config, KMS helper, and `meson_vdec` modules-load passed. Root free space was about 3.64 GB with 354,676 free inodes.
- **Evidence**: local `.codex_tmp/emmc_deploy_20261112/g5_validation_20261112_231207/`; `SHA256SUMS` 5/5 OK. Hashes: result `9ebd188d…`, installer log `80eb6452…`, evidence `0e753462…`, bootloader `f61b153c…` (4,194,304 B), MBR `d110adfe…` (512 B). Remote `~/mobile_vt/.codex_tmp/emmc_deploy_20261112/g5/run_20261112_231207/` matches.
- **SG USB**: remains the boot source (`/dev/sda2` ext4, `/dev/sda1` vfat); source boot/runtime hashes unchanged; PC G2 backup remains 28/28 OK. Expected source-side effects were machine-id regeneration, `/ddbr` staging, and bootloader-image creation.
- **Power**: `sudo sync && sudo poweroff` at 23:19:57 HKT; SSH closed; ping 10.42.0.11 received 0/2 replies. No reboot.
- **G6**: not started. Remove the SG USB before the first eMMC-only cold boot, then verify `/`=`/dev/mmcblk2p2`, `/boot`=`/dev/mmcblk2p1`, SSH, HDMI/KMS, ca46 autoload, native worker, non-root service autostart, DJI USB reception, HEVC hardware decode, and stable display. Do not start G7/G8 until G6 passes. `K3 ACCEPTED_WITH_LIMITATION` is unchanged.

## G3/G4 eMMC final minimal-runtime audit — recommended pass; G5 not started (2026-11-12 19:16 HKT)

> This section records static/read-only audit results for the final minimal runtime payload. It does not prove that eMMC can boot. G5 writes nothing until explicitly approved; G6 is the first dynamic eMMC test. The earlier 17:16 report and its `3,685,431,296 B` payload are superseded and retained only as history.

**Status distinction**

- **Verified**: eMMC identity/capacity, final selective payload bytes/members, installer/exclude/service hashes, capacity arithmetic, bootloader header, DTB hashes/diff, module/firmware/autoload metadata, service/udev/journald hashes, worker/system-Python/system-FFmpeg dependencies, and backup archive coverage.
- **Recommended pass**: G3 selective-copy plan and G4 boot/runtime compatibility are sufficient to request G5 approval.
- **Pending G6**: eMMC-only cold boot, boot priority, DTB/HDMI output, ca46 auto-load, service auto-start, USB enumeration, video, SSH, and post-ext4 free space.

**G3 fixed plan**

- eMMC: `/dev/mmcblk2`, Biwin, `7,474,249,728 B`; no partitions/mounts during audit or at the 19:16 recheck. Final root tar stream: `2,853,621,760 B`, 61,468 members; after installer post-copy additions the final root file payload is `2,853,710,642 B` (2.6577 GiB), down `831,720,654 B` (793.2 MiB) from the superseded `3,685,431,296 B` plan.
- Include: Armbian OS/kernel/DTB/firmware; ca46 `meson-vdec.ko` and `gxl_hevc.bin`; native `build/d3/d3_probe` worker (libc only); `vt13_video` source/config/tests/deploy/udev; systemd service, volatile journald namespace, actual installed udev rule; DRM/KMS runtime; system Python plus dist-packages (`av`, `cv2`, `numpy`, `yaml`, `usb`); system FFmpeg shared libraries under `/usr/lib/aarch64-linux-gnu`.
- Exclude: `.venv-v4l2`, custom `ffmpeg-6.1.1-v4l2-shared`, `captures`, `live_runs`, both `.codex_tmp` trees, kernel/FFmpeg source/build trees, toolchains, old backups, apt lists/cache, historical logs, `/usr/share/doc|man|locale`, `/usr/src`, and unused build artifacts. The authoritative manifest is `deploy/PAYLOAD_MANIFEST.md`.
- ampart-success root budget: `6,814,695,424 B` (6.347 GiB), leaving `3,960,984,782 B` (3.6890 GiB) before filesystem metadata. ampart-fallback root: `6,048,186,368 B` (5.633 GiB), leaving `3,194,475,726 B` (2.9751 GiB). The boot partition is a separate fixed 512 MiB FAT32 `BOOT_EMMC`; G6 must measure `df -hT /`, `df -hT /boot`, and `df -i`.
- Final installer `armbian-install-final.sh` SHA256 `90cb0390…` (30,340 B); patch `175920b5…`; exclude `deploy/emmc-exclude.txt` SHA256 `58b8fe24…`; reviewed service `deploy/vt13-kiosk.service` SHA256 `3ed77408…` (842 B); original `/usr/sbin/armbian-install` `defc9646…` untouched. The installer forces the `-gxl-test` DTB, applies the exclude manifest, recreates `.codex_tmp` with `billieguo:billieguo`/`775`, copies only the two KMS helper files, installs the reviewed service, writes `/etc/modules-load.d/vt13-vdec.conf`, and fail-closes on 12 critical runtime files. Expected source-side writes remain machine-id regeneration, `/ddbr/install`, and `/usr/lib/u-boot/mybox-bootloader.img` (first 4 MiB eMMC backup); source `/boot` is not modified.
- G5 staging at `/home/billieguo/mobile_vt/.codex_tmp/emmc_deploy_20261112/g5/`: all four files match local SHA256 and `bash -n` RC=0; `/ddbr` is currently absent; `/dev/mmcblk2` is unmounted; `vt13-kiosk.service` is active with `MainPID=447`, `NRestarts=0`. No eMMC write.
- Note: the full 61,468-member payload was not expanded on the PC; capacity/member audit used the actual remote uncompressed tar stream, and the installer performs fail-closed critical-file checks. G3 is therefore **recommended pass with this documented note**; G6 must measure actual ext4 free space and inodes.

**G4 fixed findings**

- eMMC user area has an `@AML` bootloader header at `0x200` (`Built : 13:36:55, Jun 22 2020`, `gxl g85d6ad1`); `mmcblk2boot0/1` contain the same 4 MiB vendor bootloader bytes (`f61b153c…`) with `force_ro=1`. The installer backs up the first 4 MiB to `mybox-bootloader.img` and writes it back; that file did not exist before G5.
- MODEL_ID 127 / S905L3B: normal FDT `meson-gxl-s905l3b-m302a.dtb` `1a568548…`, `-gxl-test` FDT `6bdcf618…`; decompiled diff is only the HDMI node. Current `uEnv.txt` `2b488bb1…` selects `-gxl-test`, so the patched installer forces that DTB. `zImage` `4b7b8882…` has TEXT_OFFSET `0108` (`NEED_OVERLOAD=no`); `boot-emmc.cmd` uses `devtype=mmc`, `l_mmc="2 1 0"`; `u-boot-s905x-s912.bin` `207cdbe1…` is present.
- ca46 module `ca467983…`, vermagic `6.18.59-ophub SMP preempt mod_unload aarch64`, dependencies in `modules.dep`, and `modules.alias` contains `of:N*T*Camlogic,gxl-vdec`; firmware `gxl_hevc.bin` `f1336295…`. Worker depends only on libc. Target runtime uses system `/usr/bin/python3` and system dist-packages (including system PyAV 11.0.0 for diagnostics) plus system FFmpeg shared libraries; the `.venv-v4l2` and custom `ffmpeg-6.1.1-v4l2-shared/install` are excluded. The worker backend does not import PyAV. A static import/config check on CM311 reported `backend=worker`, `codec=hevc_v4l2m2m`, `av=False`; the service has not yet run on eMMC.
- Current SG USB installed service `15ade4bb…` will be replaced during G5 by the reviewed `3ed77408…` service (`ExecStart=/usr/bin/python3 ...`). Journald `f39e019b…`; actual udev rule `9509a4c1…`; repo source `4455e3b2…` has the same effective rule plus comments; preserve the installed rule unless intentionally changing it.
- `sg-boot.tar` contains `uEnv.txt`, both DTBs, kernel/initrd, `zImage`, `u-boot-s905x-s912.bin`, and `boot-emmc.*`; archive hashes match the running system.

**Residual risk**

- eMMC boot success, boot priority, HDMI/DTB behavior, ca46 auto-load, system-Python service auto-start, USB hotplug, and SSH remain unverified until G6. USB fallback is not guaranteed to win automatically after bootloader write; a failed boot may require physical reset or Amlogic USB Burning Tool. One historical soft reboot hung; use `poweroff` plus cold power cycle, not `systemctl reboot`.
- Report: `.codex_tmp/emmc_deploy_20261112/g3g4/G3G4_REPORT.md` SHA256 `82ee6c50…`; evidence manifest `EVIDENCE_SHA256.txt` SHA256 `6baab39d…`; `sha256sum -c` 30/30 OK. The old 17:16 report is retained as `G3G4_REPORT_20261112_1716_superseded.md`; copies in the backup root are from the earlier version and must not be used for G5 approval.

**G5 final confirmation — read-only review passed; G5 not started (2026-11-12 21:33 HKT)**

- **`mybox-bootloader.img` provenance/applicability**: the installer's `create_partition()` runs `dd if=/dev/mmcblk2 of=/usr/lib/u-boot/mybox-bootloader.img bs=1M count=4 conv=fsync` before partitioning. The file is therefore a **4 MiB backup of the same CM311 unit's eMMC user-area vendor bootloader**, not a generic U-Boot image and not a full-disk image. The file did not exist before G5; `/etc/ophub-release` has `MAINLINE_UBOOT=''` and `BOOTLOADER_IMG=''`, so the installer selects the mybox vendor-writeback branch. Current user-area first 4 MiB, `mmcblk2boot0`, and `mmcblk2boot1` all hash to `f61b153c1ec98ce54ee770be43198af2d2ac60642cc6004500cfbd3b87490262`; the user area has `@AML`/`gxl` at `0x200`.
- **Recovery semantics**: preserve the new G5 MBR partition table by restoring only bootloader bytes 0–443 and 512–4194303 from the backup, matching the installer: `dd if=mybox-bootloader.img of=/dev/mmcblk2 bs=1 count=444 conv=fsync` then `dd if=mybox-bootloader.img of=/dev/mmcblk2 bs=512 skip=1 seek=1 count=8191 conv=fsync`. Do **not** treat `dd bs=1M count=4` as an unverified universal recovery command: it also restores the backup's old MBR/partition table. The wrapper exports both `mybox-bootloader.img` and the post-install `mbr-first512.bin` to the PC; normal bootloader recovery does not require rewriting the new MBR unless that table itself is lost.
- **Installer target/copy/service review**: target selection uses `lsblk` boot0 detection or excludes the current root device; the only current eMMC candidate is `/dev/mmcblk2`. The wrapper additionally fail-closes on exactly one eMMC disk, exact `7,474,249,728 B`, source `/dev/sda2`/`/dev/sda1`, target unmounted, and 4 MiB boot0/boot1 with `force_ro=1`. Selective root copy remains `COPY_SRC="etc home opt root selinux srv usr var"` with `/ddbr/emmc-exclude.txt`; `/boot` is written separately as a 512 MiB `BOOT_EMMC` FAT32 partition. The reviewed service is installed to target `/etc/systemd/system/vt13-kiosk.service` and `/home/billieguo/mobile_vt/deploy/vt13-kiosk.service`; the existing `multi-user.target.wants` symlink is preserved by the tar copy. The wrapper validates the unit, `ExecStart=/usr/bin/python3 ...`, `VT13_ASYNC_USB=0`, `User=billieguo`, `Restart=always`, `WantedBy=multi-user.target`, and the enable symlink.
- **Source SG USB side effects**: expected writes are `/etc/machine-id` and `/var/lib/dbus/machine-id` regeneration, `/ddbr/install` recreation, `/usr/lib/u-boot/mybox-bootloader.img` creation, and the wrapper's four small `/ddbr` staging files. Source `/boot` content is not modified. All installer dependency commands (`tar`, `hexdump`, `mkfs.vfat`, `mkfs.ext4`, `mkfs.btrfs`, `parted`, `losetup`, `fdisk`, `lsblk`, `dbus-uuidgen`, etc.) are present, so the expected path is `Dependency check completed` rather than apt installation.
- **Final scripts**: `deploy/g5-install-wrapper.sh` SHA256 `1bef8ba4e410d7b54c6c88548de6d6273ad56eff2d0268fec2cbe82d9d34257d`; `deploy/g5-run-from-pc.sh` SHA256 `c3ef51f004f44b6ed257d83a7481b4aff32a9335abaae2a18d2c6ba727ef9af8`; both `bash -n` RC=0. The wrapper verifies source boot artifacts, KMS helpers (`a071cfed…`, `fbd8c439…`), target partitions/boot files/rootfs/service/KMS/module/firmware, rechecks source `/boot`, KMS, and `/ddbr` hashes after install, exports the bootloader backup and post-install MBR, and only then reports `VALIDATED`. The PC runner verifies local and remote wrapper hashes, fetches the install log, post-install evidence, `mybox-bootloader.img`, and `mbr-first512.bin`, verifies all SHA256 values and sizes, and only then runs `sync` and `poweroff`.
- **Final preflight evidence**: local `.codex_tmp/emmc_deploy_20261112/g5_pc_20261112_213308/`; `preflight.txt` SHA256 `41f62d3beadc5482428b9c969a94cf425742f0a20b019da733c84f3d0df0ba51`, `g5-result.env` SHA256 `8921c5a88163fdad30e09e74c69bf97cdf05ee1e3d4b25ef4d6e2feafd8157d0`, `preflight-session.log` SHA256 `2df2bae72162f0871844e2e16ec7c817882be94040a776c20a6e68755242ec40`. Remote `~/mobile_vt/.codex_tmp/emmc_deploy_20261112/g5/run_20261112_213343/preflight.txt` and `g5-result.env` match the local hashes; remote wrapper hash is `1bef8ba4…`; `/ddbr` still absent, eMMC unmounted, kiosk active. No eMMC write, service stop, reboot, module reload, or live USB/HDMI/wireless run occurred.

**Gate decision**: G3 **RECOMMENDED PASS** for the final `2,853,710,642 B` minimal payload; G4 **RECOMMENDED PASS_WITH_APPROVED_RISK** with the runtime dependency change (system Python/system FFmpeg; no venv/custom FFmpeg); **G5 later PASS**; G6 later **PASS_WITH_LIMITATION** (HDMI visual and physical hotplug pending).

## meson-vdec module — cold boot must use ca46 (FIXED permanently 2026-11-11 21:13 HKT)

- **Two different modules exist**:
  - Installed `/lib/modules/6.18.59-ophub/kernel/drivers/staging/media/meson/vdec/meson-vdec.ko` = `a6cc08ca2598caf378881a85515c211e8fc41e6bc870753e5d11a3942458f198`. **Auto-load/modprobe uses this; it parses (esparser IRQ fires) but the HEVC decoder core never completes (vdec-mbox1 IRQ stays 0) → no video.**
  - Source build `~/linux-6.18-vdec/drivers/staging/media/meson/vdec/meson-vdec.ko` = `ca46798328e0975290151c40e1ddbf191a277b563a9694344aca910507aacdab`. **This is the working module** (manually loaded before the 2026-11-11 reboot; ran 5 days).
- **Symptom of wrong module**: kiosk worker loops `no SOURCE_CHANGE within 10000 ms` every 10 s, 0 frames, console/login stays visible. `HEVC mailbox IRQ is unavailable` dmesg warning is a CONSTANT red herring (DT interrupt-names = `vdec esparser`; mbox0 has no fallback) — present with both modules, not the cause.
- **Recovery (R3)**: `sudo systemctl stop vt13-kiosk` → `sudo rmmod meson_vdec` → `sudo insmod ~/linux-6.18-vdec/drivers/staging/media/meson/vdec/meson-vdec.ko` → `sudo systemctl start vt13-kiosk`. Verified 20:53: vdec IRQ 0→1856, 60.6 fps, console hidden. `modprobe meson_vdec` does NOT work (loads the installed a6cc08ca).
- **PERMANENT FIX DONE (21:13 HKT, R3 approved)**: backed up `a6cc08ca` to `/lib/modules/6.18.59-ophub/kernel/drivers/staging/media/meson/vdec/meson-vdec.ko.a6cc08ca.bak`, installed `ca46` into `meson-vdec.ko`, `depmod -a`. **Validated after hard reboot**: auto-load uses ca46, kiosk auto-starts, vdec IRQ fires, **60.4 fps / sessions=1 / 0 errors / 0 `0xf`**. Caveat: the first *soft* `systemctl reboot` after install hung (black screen, no SSH); a **hard power cycle** recovered and cold boot works — soft-reboot reliability needs monitoring. If a boot ever hangs: hard power cycle. If decode is wrong module: `sudo insmod ~/linux-6.18-vdec/drivers/staging/media/meson/vdec/meson-vdec.ko`. A kernel package update could revert the module (backup kept).

## Source Change repair (2026-11-11 20:29 HKT) — DEPLOYED + cold-start confirmed fixed

- The deployed CM311 worker is still `51346c85` and the K3 service is unchanged (active/enabled, MainPID 263980/worker 263983). This step made **no remote write, no live run, no reboot/module/service change**.
- A minimal patch to `tools/d3_probe.c` (post-repair SHA256 `4af75b7c57aa53af437f810095925f01c33a4e07e856d12c92822a46ad87a303`, +45/−4) fixes the cold-start 1832→1920 zero-frame wedge: consume mid-stream `V4L2_EVENT_SOURCE_CHANGE` (POLLPRI) before POLLERR, force a fresh fd on SOURCE_CHANGE/CAPTURE EPIPE, keep the same-fd fast path for fixed-resolution EIO, drain stale events at teardown, and instrument the QBUF OUTPUT failure path. Decode parameters and held/scanout lifetime are unchanged.
- Root cause: meson-vdec `source_change_pending` stays set after a resolution change and `vdec_m2m_job_ready` pauses decoding; the HEVC session persists across same-fd rebuilds, so a reused fd never re-fires `amvdec_src_change` and never resumes — only close/open clears it.
- Offline-verified on PC only: clean build (binary `65d4d2f6…`), mock-syscall harness 13/13 PASS (`.codex_tmp/k3_source_change_20261111/mock_test.c`, `dd6f40fe…`), Python unittest 91 OK/38 skipped. **Hardware behavior is NOT verified.** Backup `pre_repair_local.tar` (`21c05154…`) / `pre_repair.diff` (`e5a2a2a7…`) in the same directory.
- Next (each needs fresh exact-command approval): CM311 staging build + offline damaged-replay with a resolution-switch sample, then an R2 live cold-start verification. Replacing the deployed worker/service is a separate explicit approval; preserve `51346c85` and its rollback chain until then.
- **Staging ready (19:53 HKT)**: patched worker compiled on target at `~/.codex_staging/k3_srcchange_20261111_194655/d3_probe` (aarch64, SHA256 `eb1dbb67f3193ddcbc5f37f7793f30b7b117c00e9626fb6a4ab68fbc19a95008`; source `4af75b7c…` matched). Fixed `d3_replay.py` (`0cc5cc6d…`) and a clean synthetic `switch_1832_to_1920.h265` (`6c78ff02…`, 461 AUs, 1920 IRAP at AU 30) staged; runner `run_switch_test.sh` (`1130501e…`). Deployed worker `51346c85…` and service unchanged. Hardware test awaits an approved R2 service-stop window (staged binary run directly; rollback = restart service).
- **HARDWARE-VERIFIED (20:08 HKT)**: approved R2 A/B window using `switch_multi.h265` (`f91350b1…`, 1323 AUs, 1920 IRAPs at AU 30/461/892). Patched `eb1dbb67`: 1832→1920 switch via `DQBUF EPIPE`→fresh fd, session 2 `min_buffers=16`, **DECODED 873 frames** (851×1920), corrupt=0 — recovers. Old `51346c85`: same switch via same-fd rebuild, session 2 `min_buffers=1`, **DECODED 23 frames, zero 1920 permanently** — reproduces the cold-start wedge. Service restored healthy (MainPID 270674, 60 FPS/0 errors); deployed worker still `51346c85…` (NOT replaced). Evidence local==remote: `run_patched.log 767e348a…`, `run_old.log 60363190…` under `.codex_tmp/k3_source_change_20261111/`. Note: `sudo -n` needs a fresh credential cache; the window feeds the password via `sudo -S` stdin (runtime, never echoed). Deployment + live cold-start confirmation need separate exact-command approval.
- **DEPLOYED (20:16 HKT)**: approved R2 replace of `~/mobile_vt/build/d3/d3_probe` with the patched `eb1dbb67…` (hash-guarded; backup `~/mobile_vt/.codex_tmp/backup_srcchange_20261111_201335/d3_probe.51346c85`, hash verified). Service restarted, MainPID 272334/worker 272344, active/enabled, NRestarts=0, live ~58 fps/0 errors/corrupt=0 on the 1920 stream. Python/kiosk.yaml unchanged. Rollback: `cp <backup>/d3_probe.51346c85 ~/mobile_vt/build/d3/d3_probe && sudo -n systemctl restart vt13-kiosk.service`. Evidence `.codex_tmp/k3_source_change_20261111/{deploy.log,post_deploy_health.log}`. **Pending**: human VT off→on cold-start to confirm 1832→1920 in situ; boot/hotplug/glass-to-glass/visual still untested.
- **COLD-START CONFIRMED (20:29 HKT)**: human VT off→on; restarted kiosk with VT off (MainPID 272982/worker 272990), READY 20:25:22 waiting IRAP. VT on: session 1–2 `G_FMT 1832x1032 min_buffers=16` → session 3 `G_FMT 1920x1080 min_buffers=16` — the 1832→1920 switch recovered (fresh fd), **not the old min_buffers=1 wedge**. Startup burst of 40 content-dependent `0xf poc=7` (20:26:18–49) auto-recovered and settled (0 new 0xf since 20:27). Steady state 60.0 fps instantaneous (720 frames/12 s), sessions stable 41, corrupt=0, age ~21–32 ms. The wedge is fixed in situ; 0xf itself is NOT claimed fixed. Evidence `.codex_tmp/k3_source_change_20261111/coldstart_*.log`. Still untested: boot/reboot startup, USB hotplug, glass-to-glass, fresh 30-min soak on patched worker, user visual acceptance.
- **Visual acceptance + USB hotplug PASS (20:37 HKT)**: user confirmed screen normal. Hotplug (DJI C5 only, rootfs untouched): 20:36:24 `usb 1-1 disconnect device 6` → pipeline `Errno 19` → `reopening USB in 0.25s`; 20:36:39 re-enumerated `2ca3:1020` device 7 (ttyACM0/1 recreated); 20:36:42 `USB source open address 7` + I-frame request → resumed. **NRestarts=0, MainPID 272982 unchanged (in-process recovery)**; steady 60.4 fps instantaneous (604/10 s), sessions 47, corrupt=0. Evidence `.codex_tmp/k3_source_change_20261111/hotplug_*.log`. Reboot auto-start test pending (R3; service enabled + multi-user.target; DHCP 10.42.0.11 may change IP; needs physical access).

## Current K3 state (2026-11-11 19:04 HKT) — PARTIAL acceptance

- Service installed, active and enabled; MainPID 263980, worker 263983, NRestarts=0. Sampler completed, video remains running. Unit `15ade4bb`, journal config `f39e019b`, recovery.py `275c91f6`; worker `51346c85` and kiosk.yaml `d4d155f2` unchanged. No reboot or commit.
- Final 30-min observation: **106278 presented frames / 1799.092-second counter window = 59.073 fps**, zero corrupt/oversize flags, 108 in-process rebuilds/kernel aborts. 107 measured freezes: p50 216.7 ms, p95 250.1, max 283.3; one QBUF OUTPUT EIO rebuild lacked timing instrumentation. Internal age p50 median33.6 ms; backlog max4. CPU median26.75%, temperature66–73°C, memory/FD/dmabuf stable, namespace journal7.3MiB.
- **Not fully accepted**: earlier cold-start 1832→1920 source-change froze at zero frames until manual service reopen; defect remains unfixed. Stable-run floor59.0 achieved but preferred59.5 not; abort rate exceeds historical V1 and cause is not isolated. Current-run visual confirmation, true reboot startup, USB-hotplug and glass-to-glass not verified. Do not present service-enabled status as proven unattended operation.
- Evidence mirrored with all checksums verified: `.codex_tmp/k3_service_20261111_1807/soak_20261111/` (10 files/9,330,350 B; manifest `eb3017400cdcef68c1365cafcafd0f662bf5433992b4838f3a7263de6c390e3e`). Next requires scoped staging-worker recovery repair and separate exact deployment approval; no new live experiments automatically scheduled.

## Historical K3 steady-state observation (2026-11-11 18:34 HKT)

- One explicitly approved stop/start with VT kept on restored presentation: stop 0.624 s, clean device release; gate opened 18:31:04; subsequent worker reports ~60 new displayed frames/s, corrupt=0. MainPID 263980, worker 263983, active/enabled, zero systemd restarts. Worker `51346c85`, recovery `275c91f6`, unit `15ade4bb`, journal config `f39e019b` unchanged.
- 30-minute observer started **18:34:13 HKT**, expected finish ~19:04:14. Automated 10/20-minute checkpoints and completion via monitor `b56tgh1s3`; only sampler/log readers end, kiosk remains running. Remote logs/samples: `~/mobile_vt/.codex_tmp/k3_service_20261111_1807/soak_20261111/`.
- Earlier cold-start resolution-switch zero-frame failure remains unresolved; this steady-state observation cannot erase it or prove unattended boot/resolution recovery. Full K3 acceptance still pending; no additional stop/restart or binary replacement is planned in this window.

### 18:44 HKT checkpoint (10 min)

59.141 presented fps, corrupt/oversize delta 0, 34 in-process rebuilds/aborts, maximum freeze 283.3 ms; no service or worker restart. Age p50 median 34.55 ms, backlog <=2, CPU median 26.68%, 66–70°C, bounded memory/FD/dmabuf counts, journal 4 MiB. Continue the same 30-min observer. Abort frequency is higher than historical V1 and not yet attributed; startup source-change failure remains unresolved. Evidence: local `checkpoint_600.json` (SHA256 `261af1dc8ee3c896c3654c801ee1f8c6ea799ddae4e89984507298e1a5c14acc`) and `checkpoint_600_summary.json` in the K3 step directory. No additional service changes.

### 18:54 HKT checkpoint (20 min)

58.937 presented fps (below RC1 >=59.0 target), 84 automatic in-process recoveries total, corrupt/oversize 0, max freeze 283.3 ms. Service/worker unchanged, NRestarts=0. Age median 34.5 ms/backlog <=3, CPU median 27%, 66–71°C; memory and FD/dmabuf stable, journal 4 MiB. Observation continues to planned 30 min for evidence; performance/complete K3 acceptance not PASS. `checkpoint_1200.json` source/copy SHA256 `3ebb6a9644c9fdc5a65fbd20f4ce06810afd3f073a85cc9233f077b7b5b04533`; no runtime changes.

## Earlier K3 live acceptance failure (2026-11-11 18:25–18:27 HKT)

- After user enabled VT, source changed 1832x1032 to 1920x1080 during startup. One 0xf followed by CAPTURE EPIPE and same-fd reconfiguration left worker `aus_frames=0`, despite ~60 AU/s USB/Python input. Service is active/enabled with zero systemd restarts, but video is NOT verified working. Do not use Python status FPS as display FPS.
- Suspected missing dynamic SOURCE_CHANGE event handling/stale event after fd reuse; not yet isolated. Worker is still original `51346c85`; no new deployment or restart in this diagnostic step. The 10–30 minute soak has NOT started. Evidence `.codex_tmp/k3_service_20261111_1807/zero_frames_diagnostic.log`.
- Next: ask user to choose a controlled service stop/start isolation or expanded staging-worker repair; no automatic kernel/reboot changes. Current exact stop and rollback remain below.

## K3 service installation state (2026-11-11 18:19 HKT)

- User-approved K3 installed and enabled: `vt13-kiosk.service`, non-root billieguo, existing worker `51346c85` + kiosk.yaml, async off. Unit SHA256 prefix `15ade4bb`; `recovery.py` now `275c91f6` (only runtime change, backoff saturation); all 16 runtime/config files match local K3 tree. Worker and display configuration unchanged.
- Graceful stop verified: 1.123 s, Result=success, no remaining worker/V4L2/DRM/ttyACM0 owner. Restart READY at 18:19:07: `USB source open`, waiting for IRAP; active/enabled, MainPID 262680, zero systemd restarts. VT still off at verification; 10–30 min live acceptance and real reboot startup remain NOT_TESTED.
- Logs: `journalctl --namespace=vt13-kiosk -u vt13-kiosk.service` (Ctrl-C exits follow mode only); config `/etc/systemd/journald@vt13-kiosk.conf` (`f39e019b`) uses volatile 32 MiB budget / 4 MiB files, so logs do not survive reboot. Global journal unchanged.
- Stop on CM311: `sudo systemctl stop vt13-kiosk.service`; explicit stop does not auto-restart. Start: `sudo systemctl start vt13-kiosk.service`. Do not run the manual kiosk simultaneously; this service owns USB/V4L2/DRM. Reboot is not required or authorized.
- Backup: `~/mobile_vt/.codex_tmp/k3_service_20261111_1807/backup/`; rollback script `.../staging/rollback_remote.sh` disables/stops only K3, restores prior recovery/draft and moves installed unit/config into that backup. PC evidence/backup mirrors: `.codex_tmp/k3_service_20261111_1807/`. Actual rollback not exercised; stop/cleanup verified. Changes uncommitted.

## Historical K3 service preflight (2026-11-11 18:08 HKT)

- Current verified access: documented askpass authorized for this session; key-only SSH RC=255, read-only preflight RC=0. Systemd 255, aarch64/6.18.59-ophub, multi-user.target; LightDM inactive. USB receiver/HDMI present; V4L2/DRM idle.
- `vt13-kiosk.service` is not installed or enabled. K3 implementation is underway locally; installing, enabling or starting it still awaits exact-command R3 confirmation. No reboot, boot-target, driver or network change is planned.
- Runtime parity: 15 Python files + kiosk.yaml match local HEAD `2ba4ff5`; worker remains `51346c85`. RC1 remains ACCEPTED_WITH_LIMITATION (59.86 fps/30 min, internal age ~30 ms, six content-dependent rebuilds, glass-to-glass unmeasured); historical sections below are not current instructions.
- Evidence and local pre-change backup: `.codex_tmp/k3_service_20261111_1807/` (`preflight.log`, `pre_local.tar`, SHA256 `2dfd24da463ac331d1d39ad50bc0af150dc3a94782e342a7a2c75ae767c88a4d`). No stream or remote write in this preflight.

### 2026-11-11 18:13 HKT — local K3 candidate, not yet deployed

- Candidate unit uses existing worker/YAML, async off, graceful SIGINT/mixed cleanup, 15-second automatic restart, 30-second stop timeout and non-root execution. Dedicated `vt13-kiosk` journal namespace is volatile with a 32 MiB usage target / 4 MiB files; system journal is unchanged. `deploy/vt13-kiosk-journald.conf` is the namespace configuration source.
- Only runtime candidate change: bounded backoff after long USB absence. Base suite 53 passed/38 skipped; full scoped PyAV unittest 91 tests RC=0, with an unrelated existing ffplay fallback-thread warning. PC unit graph verifies with a local-interpreter shadow; actual CM311 validation still pending.
- Installation/rollback scripts and payload manifest: `.codex_tmp/k3_service_20261111_1807/`. No service installed/enabled/started yet. R3 exact-command confirmation and READY-before-VT handoff remain required; no reboot planned.

## Historical live baseline (2026-11-10 17:20 HKT)

`decoder.backend=worker` + `VT13_ASYNC_USB=0` + control on + kernel abort watch +
`stall_restart_s=0` + no recording + `--hide-primary`: 57.8–58.8 fps, 0 corrupt,
one in-process V4L2 rebuild per ~14 s (TTFV ~260 ms, last frame held).
30-min soak: 105856 frames / 1800 s = 58.81 fps, 128 sessions, memory flat.
Residual `0xf` ~0.1–0.2/s is host-side; async reader is the main cause and must
stay off. K3 unit is a draft (`deploy/vt13-kiosk.service`), not enabled.


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
- **Soft recovery failed (2026-11-10 16:32)**: skipping REQBUFS and doing only
  STREAMOFF -> QBUF -> STREAMON makes STREAMON succeed but yields no frames;
  meson-vdec requires a full reconfigure after an abort. Reverted
  `tools/d3_probe.c` to `c9c76eb`; 30 s check = 1697 frames / 56.43 fps, clean.
  The 181 ms TTFV component is driver-inherent; reducing aborts (IRQ/CPU
  affinity, rmrx) is the remaining lever.
- **No-recording A/B (2026-11-10 16:34)**: 60 s with async OFF and no `--record`
  gave 3492 frames / 60.065 s = 58.14 fps, 6 sessions, 10 `0xf` / 5 aborts —
  the same as runs recording to the USB rootfs (10-16). Recording is not the
  remaining jitter source; residual `0xf` ~0.17/s (~260 ms freeze each, ~4%
  downtime) is VDEC/KMS vs xHCI/DRAM contention. Further gains need IRQ/CPU
  affinity (root), rmrx, or driver changes.
- **D3d + K3 soak (2026-11-10 17:13)**: three 60 s runs at 57.80 / 58.02 / 58.49 fps
  (0 corrupt, 5-7 sessions, 8-12 `0xf` each -> the "0 `0xf`" D3d gate is not met);
  30-min soak: 105856 frames / 1800.087 s = 58.81 fps, 128 sessions (~14 s each),
  0 corrupt, 0 oversize, RC=0, memory 358 -> 359 MiB, 61 -> 67 C, clean exit.
  dmesg delta undercounts due to ring wrap; use session count. K3 draft committed
  in `f43d463` (`config/vt13_video.kiosk.yaml`, `deploy/vt13-kiosk.service`, not enabled).
- **taskset affinity test (2026-11-10 17:15)**: `taskset -c 2,3` for 60 s gave
  3521 frames / 58.57 fps, 5 sessions, 8 `0xf` / 4 aborts — no significant
  change vs unbound (8-12). CPU affinity is not the residual-jitter lever.
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

### eMMC / Armbian install assessment (2026-11-11 21:40 HKT, read-only)

- Current root: `/dev/sda2` ext4 on USB `SG Flash` (117.2 GB, serial
  `63FAF0B2735338D7`); `/boot` is `/dev/sda1` vfat. The internal eMMC is
  `/dev/mmcblk2` (Biwin, 7,474,249,728 B) with no partition table, filesystem,
  or mountpoint; `mmcblk2boot0/1` are 4 MiB each and `force_ro=1`.
- Board metadata: `/etc/ophub-release` and `/etc/model_database.conf` list
  `MODEL_ID=127`, `MODEL_NAME=M302A,M304A,CM201-1,CM211-1,CM311-1`,
  `SOC=s905l3b`, `FDTFILE=meson-gxl-s905l3b-m302a.dtb`, and
  `UBOOT_OVERLOAD=u-boot-s905x-s912.bin`. The live device tree identifies
  `Amlogic Meson GXL (S905L3B) MBH-M302A Box` (`amlogic,m302a`).
- `armbian-install` is present and supports USB→eMMC installation. It detects
  `mmcblk2` and copies `etc home opt root selinux srv usr var` without excluding
  project data. `/usr/bin/ampart` exists, so the `s905l3b` layout reserves
  117 + 512 MiB and leaves about 6.3 GiB for the root filesystem; without ampart
  the fallback layout reserves 128 + 512 + 720 MiB (about 5.6 GiB).
- Current copy set is about 15.3 GiB (`/usr` 3.04 GB, `/var` 0.74 GB, `/home`
  12.60 GB; `~/mobile_vt` 8.0 GB including `captures` 4.2 GB and
  `.codex_tmp` 3.2 GB). A direct eMMC install will not fit; clean or move the
  project/build trees first, or keep the USB root.
- Current `/boot/uEnv.txt` uses
  `meson-gxl-s905l3b-m302a-gxl-test.dtb`; `uEnv.txt.bak` uses the normal
  `meson-gxl-s905l3b-m302a.dtb`. `armbian-install` rewrites FDT to the model
  database's normal m302a DTB, so verify the installed system and switch back
  to the `-gxl-test` variant if required by this board.
- No install, reboot, or remote write was performed in this read-only check.

## Full CM311 deployment runbook (system + application)

This is the complete rebuild/migration procedure for the current verified
stack. Commands are labeled by host. Approval levels follow `AGENTS.md` §5:
R0 read-only, R1 offline, R2 live USB/HDMI/service, R3 reboot/partition/
module/apt/boot changes. Do not run a phase whose prerequisites are unmet.

### Deployment choices

| Choice | Use when | Main risk |
|---|---|---|
| **A. Keep the USB SG root** (current) | Normal operation, fastest recovery, least change | USB disk is a single point of failure; root shares a USB controller with the DJI receiver |
| **B. Install Armbian to eMMC** | Standalone appliance; free the USB port/controller | eMMC root is only ~6.3 GiB; project data must be moved; the installer rewrites the DTB; boot priority changes |

Recommendation: keep A as the known-good deployment. Treat B as an optional
migration that must be separately approved and validated.

### Phase 0 — Preflight and backup (R0/R1)

```bash
# CM311, read-only
uname -a
cat /etc/os-release | head -12
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT
findmnt /
df -h /
systemctl is-enabled vt13-kiosk.service
systemctl is-active vt13-kiosk.service
systemctl show vt13-kiosk.service -p MainPID -p NRestarts
lsusb | grep 2ca3:1020 || echo 'receiver not enumerated'
```

Back up the runtime, module, custom FFmpeg install, venv, and system files.
Do not include `captures/` or `.codex_tmp/` in the runtime tar; back them up
separately if they are golden data.

```bash
# CM311, R1
STAMP=$(date +%Y%m%d_%H%M%S)
B=$HOME/mobile_vt/.codex_tmp/deploy_backup_$STAMP
mkdir -p "$B"
tar -C "$HOME" -czf "$B/mobile_vt_runtime.tgz" \
  --ignore-failed-read \
  --exclude='mobile_vt/captures' --exclude='mobile_vt/.codex_tmp' \
  mobile_vt/vt13_video mobile_vt/config mobile_vt/build/d3 \
  mobile_vt/requirements.txt mobile_vt/pyproject.toml
tar -C "$HOME" -czf "$B/kernel_module.tgz" \
  linux-6.18-vdec/drivers/staging/media/meson/vdec/meson-vdec.ko
tar -C "$HOME" -czf "$B/ffmpeg_shared_install.tgz" \
  ffmpeg-6.1.1-v4l2-shared/install
tar -C "$HOME" -czf "$B/venv_v4l2.tgz" mobile_vt/.venv-v4l2
cp /etc/systemd/system/vt13-kiosk.service "$B/"
cp /etc/systemd/journald@vt13-kiosk.conf "$B/"
cp /etc/udev/rules.d/99-vt13-video.rules "$B/" 2>/dev/null || true
cp /boot/uEnv.txt "$B/"
cp /lib/modules/6.18.59-ophub/kernel/drivers/staging/media/meson/vdec/meson-vdec.ko \
  "$B/meson-vdec.ko.installed"
( cd "$B" && sha256sum *.tgz *.service *.conf uEnv.txt *.installed > SHA256SUMS )
[ -f "$B/99-vt13-video.rules" ] && \
  ( cd "$B" && sha256sum 99-vt13-video.rules >> SHA256SUMS )
( cd "$B" && sha256sum -c SHA256SUMS )
```

Copy `SHA256SUMS` and the backup to the PC, then verify the copy:

```bash
# Ubuntu PC
rsync -a --info=progress2 \
  billieguo@10.42.0.11:~/mobile_vt/.codex_tmp/deploy_backup_*/ \
  /home/billieguo/billie_guo/src/rm/mobile_vt/.codex_tmp/deploy_backup_copy/
( cd /home/billieguo/billie_guo/src/rm/mobile_vt/.codex_tmp/deploy_backup_copy && \
  sha256sum -c SHA256SUMS )
```

### Phase 1 — Operating system (R3 for eMMC install)

#### Option A — keep the USB SG root

No OS install is needed. The current system is Armbian OS 26.11.0 noble,
kernel `6.18.59-ophub`, aarch64, with `/dev/sda1` as `/boot` and `/dev/sda2`
as ext4 root on the USB `SG Flash` (117.2 GB, serial
`63FAF0B2735338D7`). Preserve this disk; it is the fallback.

#### Option B — install Armbian to the internal eMMC

Read-only capacity check first:

```bash
# CM311, R0
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT
findmnt /
df -h /
sudo du -xhd1 /home /usr /var | sort -h
du -sh ~/mobile_vt ~/mobile_vt/captures ~/mobile_vt/.codex_tmp \
  ~/linux-6.18-vdec ~/ffmpeg-6.1.1-v4l2 ~/ffmpeg-6.1.1-v4l2-shared \
  ~/mobile_vt/.venv-v4l2
cat /boot/uEnv.txt
grep -E 'MODEL_ID|MODEL_NAME|SOC|FDTFILE|UBOOT_OVERLOAD' \
  /etc/ophub-release /etc/model_database.conf
```

Known board metadata: `MODEL_ID=127`,
`MODEL_NAME=M302A,M304A,CM201-1,CM211-1,CM311-1`, `SOC=s905l3b`,
`FDTFILE=meson-gxl-s905l3b-m302a.dtb`,
`UBOOT_OVERLOAD=u-boot-s905x-s912.bin`. The eMMC is `/dev/mmcblk2`
(Biwin, 7,474,249,728 B), currently empty; `mmcblk2boot0/1` are 4 MiB each
and `force_ro=1`.

The s905l3b layout with `ampart` reserves 117 + 512 MiB and leaves about
**6.3 GiB** for the root filesystem. The current copy set
(`etc home opt root selinux srv usr var`) is about **15.3 GiB**
(`/home` 12.6 GB, including `~/mobile_vt` 8.0 GB with 4.2 GB captures and
3.2 GB `.codex_tmp`). A direct install will not fit. Before installing,
move or delete at least ~9 GiB and keep at least ~1 GiB free:

- Move `~/mobile_vt/captures` and `~/mobile_vt/.codex_tmp` to external
  storage or the PC; verify SHA256 before deleting the originals.
- Keep `~/ffmpeg-6.1.1-v4l2-shared/install` in place: the venv rpath points
  to it. The rest of the shared source/build tree can be removed after
  `make install`.
- Keep `~/mobile_vt/.venv-v4l2` and the installed ca46 module.
- `~/linux-6.18-vdec` (~2 GB) and `~/ffmpeg-6.1.1-v4l2` (~1.3 GB) can be
  moved to external storage after the module and venv are built. Keep a copy
  of `meson-vdec.ko` for rollback.

```bash
# CM311, R1 copy then R2/R3 delete after verification
mkdir -p /mnt/backup/captures /mnt/backup/codex_tmp
rsync -a --info=progress2 ~/mobile_vt/captures/ /mnt/backup/captures/
rsync -a --info=progress2 ~/mobile_vt/.codex_tmp/ /mnt/backup/codex_tmp/
# Compare SHA256 manifests before deleting the originals.
```

Run the installer interactively:

```bash
# CM311, R3
sudo armbian-install
```

Select model ID `127` (M302A/M304A/CM201-1/CM211-1/CM311-1), the eMMC
device `mmcblk2`, and `ext4`. Confirm the erase and wait for completion.
Then power off cleanly:

```bash
sudo poweroff
```

Remove the USB SG, power on, and verify the eMMC boot:

```bash
# CM311 after eMMC boot
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT
findmnt /
uname -a
cat /boot/uEnv.txt
grep -E 'MODEL_ID|MODEL_NAME|SOC|FDTFILE' \
  /etc/ophub-release /etc/model_database.conf
ip -4 addr show
systemctl status vt13-kiosk --no-pager
modinfo meson_vdec | grep -E 'filename|vermagic'
grep -E 'vdec|esparser' /proc/interrupts
```

**DTB caveat:** the current USB system uses
`meson-gxl-s905l3b-m302a-gxl-test.dtb` in `/boot/uEnv.txt`;
`armbian-install` rewrites the FDT to the model database's normal
`meson-gxl-s905l3b-m302a.dtb`. If HDMI, Ethernet, or USB is broken after the
eMMC boot, restore the `-gxl-test` variant and cold boot again:

```bash
# CM311, R3, only if the normal DTB does not work
sudo cp /boot/uEnv.txt /boot/uEnv.txt.bak.$(date +%s)
sudo sed -i 's#meson-gxl-s905l3b-m302a\.dtb#meson-gxl-s905l3b-m302a-gxl-test.dtb#' \
  /boot/uEnv.txt
sudo poweroff
```

**Boot fallback:** keep the USB SG untouched. Reinsert it if eMMC boot fails.
After the installer writes a bootloader to eMMC, the SoC may prefer eMMC over
USB; if the board will not boot the USB disk, use the box's reset/recovery
path or the Amlogic USB Burning Tool. Verify this before depending on USB as
an automatic fallback.

### Phase 2 — Base OS packages and toolchain (R3 for apt)

```bash
# CM311, R3
sudo apt-get update
sudo apt-get install -y \
  build-essential pkg-config libdrm-dev python3-venv python3-dev \
  libusb-1.0-0 v4l-utils git rsync bc flex bison libelf-dev libssl-dev \
  device-tree-compiler
# Optional diagnostic only; the custom FFmpeg/PyAV remains the runtime:
# sudo apt-get install -y ffmpeg
```

Verify:

```bash
gcc --version | head -1
make --version | head -1
pkg-config --version
python3 --version
test -f /usr/include/drm/drm.h && echo drm-headers-ok
id billieguo
ls -l /dev/dri /dev/video* 2>/dev/null
```

The service runs as `billieguo` and needs access to `/dev/video0`,
`/dev/dri/card0`, and the USB receiver. If the account is not in the
`video`/`render` groups:

```bash
sudo usermod -aG video,render billieguo
# Log out/in or reboot (R3) before validating the service.
```

### Phase 3 — Build and install the ca46 meson-vdec module (R1 build, R3 install)

The installed stock module `a6cc08ca…` parses but never completes the HEVC
decode core. The source build `ca467983…` is the working module. Build it
against the matching kernel tree:

```bash
# CM311
cd ~/linux-6.18-vdec
test -f Module.symvers || echo 'Module.symvers missing: run a full make once'
make -j4 M=drivers/staging/media/meson/vdec modules
```

If `Module.symvers` or `include/generated/autoconf.h` is missing, the tree has
not been fully built; run `make -j4` once in the already-configured tree.
This is the standard in-tree kbuild invocation; re-confirm it on the first
clean rebuild, because the exact historical build command is not recorded.

Verify the artifact:

```bash
cd ~/linux-6.18-vdec
modinfo drivers/staging/media/meson/vdec/meson-vdec.ko | \
  grep -E 'filename|vermagic|name'
sha256sum drivers/staging/media/meson/vdec/meson-vdec.ko
```

Expected vermagic: `6.18.59-ophub SMP preempt mod_unload aarch64`. The
known-good SHA256 is
`ca46798328e0975290151c40e1ddbf191a277b563a9694344aca910507aacdab`;
record the actual hash if a rebuild differs.

Back up and install:

```bash
# CM311, R3
INST=/lib/modules/6.18.59-ophub/kernel/drivers/staging/media/meson/vdec/meson-vdec.ko
sudo cp "$INST" "$INST.$(sha256sum "$INST" | cut -c1-8).bak"
sudo cp ~/linux-6.18-vdec/drivers/staging/media/meson/vdec/meson-vdec.ko "$INST"
sudo depmod -a
sha256sum "$INST"
modinfo meson_vdec | grep -E 'filename|vermagic'
```

Expected installed hash `ca467983…`. Then cold boot; do not use a soft reboot
for the first validation because one soft reboot hung after this install:

```bash
sudo poweroff
# Power on physically.
```

Verify after boot:

```bash
lsmod | grep meson_vdec
grep -E 'vdec|esparser' /proc/interrupts
dmesg | grep -i -E 'vdec|hevc' | tail -30
```

IRQ counts may be zero while idle; start the kiosk and live stream to confirm
the VDEC core completes. If the wrong module is loaded, do not rely on
`modprobe`; load the source build explicitly:

```bash
sudo systemctl stop vt13-kiosk
sudo rmmod meson_vdec
sudo insmod ~/linux-6.18-vdec/drivers/staging/media/meson/vdec/meson-vdec.ko
sudo systemctl start vt13-kiosk
```

Rollback the installed module:

```bash
INST=/lib/modules/6.18.59-ophub/kernel/drivers/staging/media/meson/vdec/meson-vdec.ko
sudo cp "$INST".a6cc08ca.bak "$INST"
sudo depmod -a
sudo poweroff
```

### Phase 4 — Custom FFmpeg shared libraries and PyAV venv (R1 offline)

The current `~/ffmpeg-6.1.1-v4l2-shared/install` and
`~/mobile_vt/.venv-v4l2` are already built and verified. Skip this phase when
migrating a preserved system; run it for a clean rebuild.

The shared source tree must contain the three patched files from the original
`~/ffmpeg-6.1.1-v4l2` tree: `libavcodec/v4l2_buffers.c`,
`libavcodec/v4l2_m2m.c`, and `libavcodec/v4l2_m2m_dec.c`. The shared tree was
created with `git archive HEAD` plus the saved `ffmpeg_uncommitted.patch`.

```bash
# CM311, R1
cd ~/ffmpeg-6.1.1-v4l2-shared
./configure --prefix="$HOME/ffmpeg-6.1.1-v4l2-shared/install" \
  --disable-doc --disable-ffplay --disable-ffprobe --enable-debug=2 \
  --enable-decoder=hevc_v4l2m2m --enable-demuxer=hevc --enable-parser=hevc \
  --enable-muxer=null --enable-shared --disable-static
make -j3
make install
```

This build previously exceeded 40 minutes at `-j2`; use `-j3` and a generous
timeout. Verify:

```bash
ls -l "$HOME/ffmpeg-6.1.1-v4l2-shared/install/lib/libavcodec.so"
LD_LIBRARY_PATH="$HOME/ffmpeg-6.1.1-v4l2-shared/install/lib" \
  "$HOME/ffmpeg-6.1.1-v4l2-shared/ffmpeg" -hide_banner -decoders | \
  grep hevc_v4l2m2m
```

Build PyAV 11.0.0 into a venv that is linked to the custom libraries, not the
system libavcodec:

```bash
# CM311, R1
export FFSH="$HOME/ffmpeg-6.1.1-v4l2-shared/install"
export VENV="$HOME/mobile_vt/.venv-v4l2"
python3 -m venv --system-site-packages "$VENV"
export PIP_KEYRING_PROVIDER=disabled PIP_DISABLE_PIP_VERSION_CHECK=1
export PKG_CONFIG_PATH="$FFSH/lib/pkgconfig"
export LDFLAGS="-Wl,-rpath,$FFSH/lib"
export CFLAGS="-I$FFSH/include"
"$VENV/bin/pip" install --timeout 30 --retries 2 "Cython>=3.0,<3.1" wheel
D="$HOME/mobile_vt/.codex_tmp/deploy_pyav"
mkdir -p "$D"
"$VENV/bin/pip" download av==11.0.0 --no-binary :all: --no-deps \
  --no-build-isolation -d "$D"
"$VENV/bin/pip" wheel "$D/av-11.0.0.tar.gz" --no-deps \
  --no-build-isolation -w "$D/wheels"
"$VENV/bin/pip" install --force-reinstall --no-deps "$D"/wheels/av-11.0.0-*.whl
```

Install the remaining application dependencies, but **do not** run
`pip install -r requirements.txt` blindly: it lists `av` and can replace the
custom build with a generic wheel. Install the non-`av` dependencies
explicitly:

```bash
"$VENV/bin/pip" install pyusb numpy opencv-python PyYAML
```

Verify the linkage and codec availability:

```bash
"$VENV/bin/python" - <<'PY'
import av, pathlib, subprocess
print("PyAV", av.__version__, av.library_versions)
so = next((pathlib.Path(av.__file__).parent / "codec").glob("*.so"))
print(subprocess.run(["ldd", str(so)], capture_output=True, text=True).stdout)
print("hevc_v4l2m2m:", "hevc_v4l2m2m" in av.codec.codecs_available)
print("hevc:", "hevc" in av.codec.codecs_available)
PY
```

Acceptance for this phase: `libavcodec.so.60` resolves to
`~/ffmpeg-6.1.1-v4l2-shared/install/lib`, `hevc_v4l2m2m` is `True`, and
`av.__version__` is `11.0.0`. If ldd resolves to
`/lib/aarch64-linux-gnu/libavcodec.so.60`, the rpath was not baked in and the
venv is using the system library.

### Phase 5 — Deploy the application and kiosk service (R1 staging, R2/R3 install)

Copy the runtime sources and deployment assets from the PC. The remote
`~/mobile_vt` has no `tools/` directory; create it from the local tree.
Do not copy `captures/` or `.codex_tmp/`.

```bash
# Ubuntu PC
rsync -a --info=progress2 \
  vt13_video config tools deploy udev \
  billieguo@10.42.0.11:~/mobile_vt/
```

Compile the native worker on the target (aarch64), not on the PC:

```bash
# CM311
cd ~/mobile_vt
mkdir -p build/d3
gcc -O2 -Wall -Wextra -o build/d3/d3_probe tools/d3_probe.c
file build/d3/d3_probe
sha256sum build/d3/d3_probe
```

Expected: ELF 64-bit LSB pie executable, ARM aarch64. Source
`tools/d3_probe.c 4af75b7c…` built with gcc 13.3 produced
`eb1dbb67…`; record the actual hash if the compiler differs.

Install the udev rule:

```bash
# CM311, R2/R3
sudo install -m 0644 ~/mobile_vt/udev/99-vt13-video.rules \
  /etc/udev/rules.d/99-vt13-video.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=usb
ls -l /dev/video* /dev/dri/card* /dev/dri/renderD* 2>/dev/null
```

The deployed rule uses `TAG+="uaccess"`, which applies to active local
sessions. For a strictly headless deployment where the service starts before
any login, replace it with an owner/group rule:

```text
SUBSYSTEM=="usb", ATTR{idVendor}=="2ca3", ATTR{idProduct}=="1020", OWNER="billieguo", GROUP="billieguo", MODE="0660"
```

Disable the desktop display manager so it does not compete for KMS/DRM:

```bash
# CM311, R3
sudo systemctl disable --now lightdm
sudo systemctl set-default multi-user.target
systemctl get-default
systemctl is-active lightdm || true
```

Install the kiosk unit and its dedicated journal namespace:

```bash
# CM311, R3
sudo install -m 0644 ~/mobile_vt/deploy/vt13-kiosk.service \
  /etc/systemd/system/vt13-kiosk.service
sudo install -m 0644 ~/mobile_vt/deploy/vt13-kiosk-journald.conf \
  /etc/systemd/journald@vt13-kiosk.conf
sudo systemctl daemon-reload
sudo systemctl enable vt13-kiosk.service
systemctl cat vt13-kiosk.service
```

The unit must run as `billieguo`, set `VT13_ASYNC_USB=0`, use
`/home/billieguo/mobile_vt/.venv-v4l2/bin/python`, and pass
`--headless` with `config/vt13_video.kiosk.yaml`. Do not run a manual kiosk
while the service owns USB/V4L2/DRM.

Start the receiver while the VT transmitter is still off, confirm it is
waiting, then have the human turn the transmitter on:

```bash
# CM311, R2
sudo systemctl start vt13-kiosk.service
journalctl --namespace=vt13-kiosk -u vt13-kiosk -f
```

READY evidence is the `USB source open` line followed by a waiting state;
the source has no literal `READY` string. Only after that should the human
power/enable the wireless VT link.

### Phase 6 — Acceptance and evidence (R2 live; R3 cold boot)

```bash
# CM311
systemctl is-enabled vt13-kiosk.service
systemctl is-active vt13-kiosk.service
systemctl show vt13-kiosk.service -p MainPID -p NRestarts
journalctl --namespace=vt13-kiosk -u vt13-kiosk -b --no-pager | tail -200
v4l2-ctl -d /dev/video0 --list-formats-out
lsusb | grep 2ca3:1020
grep -E 'vdec|esparser' /proc/interrupts
```

Acceptance criteria:

- service is `active` and `enabled`, with `NRestarts=0` during normal
  operation;
- the receiver enumerates as `2ca3:1020` and V4L2 advertises HEVC output;
- HDMI shows live video, confirmed by a human; the console/login is hidden;
- a clean cold boot reaches approximately 60 fps with `sessions=1`,
  `corrupt=0`, and zero errors on the cleanest run;
- USB disconnect/reconnect recovers in-process without a systemd restart;
- no SSH loss and no unbounded memory/FD growth over the observation window;
- `0xf` may still occur; record the count and maximum freeze. Do not claim
  "zero `0xf`" as a universal property.

Cold-boot validation:

```bash
sudo poweroff
# Power on physically; verify service auto-start, ca46 auto-load, vdec IRQ,
# USB enumeration, HDMI output, and steady frame counters.
```

Prefer poweroff/power-on over soft reboot: one soft reboot hung after the
module install, while a hard power cycle recovered.

### Phase 7 — Rollback

```bash
# Stop and disable the kiosk
sudo systemctl disable --now vt13-kiosk.service

# Restore the previous worker binary
cp ~/mobile_vt/.codex_tmp/backup_srcchange_20261111_201335/d3_probe.51346c85 \
   ~/mobile_vt/build/d3/d3_probe

# Restore the stock module and regenerate dependencies
INST=/lib/modules/6.18.59-ophub/kernel/drivers/staging/media/meson/vdec/meson-vdec.ko
sudo cp "$INST.a6cc08ca.bak" "$INST"
sudo depmod -a

# Restore service, journald, udev, config, and uEnv.txt from the Phase 0 backup
# (or the prior known-good copies), then:
sudo systemctl daemon-reload
sudo systemctl enable --now vt13-kiosk.service
```

For an eMMC rollback, reinsert the USB SG and cold boot. If the board still
prefers the eMMC bootloader, use the box's recovery/reset path or the Amlogic
USB Burning Tool; the USB filesystem itself is untouched by the installer.

### Deployment pitfalls (verified lessons)

- Do not assume `modprobe meson_vdec` loads ca46; verify the installed hash.
- Do not run `pip install -r requirements.txt` into `.venv-v4l2` without
  checking that `av` remains the custom rpath build.
- Do not compile `d3_probe` on the PC for CM311; compile aarch64 on target.
- Do not assume the eMMC installer preserves the `-gxl-test` DTB.
- Do not run the manual kiosk and `vt13-kiosk.service` simultaneously.
- Do not treat the volatile `vt13-kiosk` journal as persistent evidence.
- Do not overwrite `captures/` golden data during migration.

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

- SSH host: current DHCP lease `10.42.0.253` (dynamic; the historical `10.42.0.11` lease is no longer assigned after the eMMC cold boot)
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

### 2026-11-10 18:00 HKT snapshot (L0 read-only)

- Identity: `armbian`, `6.18.59-ophub`, `aarch64`, Armbian OS 26.11.0 noble;
  uptime 4 d 3 h; 1787 MB RAM (~1409 MB available); root `/dev/sda2` 115 GB,
  16 GB used.
- Boot cmdline includes `video=HDMI-A-1:1920x1080@60e`; `/sys/class/graphics/fb0/virtual_size`
  is `1920,2160`; HDMI-A-1 `connected`; mode list starts `1024x600, 1920x1080`.
- Display stack: LightDM `inactive`, `multi-user.target`, no Xorg; DRM master
  free (`/dev/dri/card0` unused). The kiosk worker takes/drops master itself.
- Devices: DJI `2ca3:1020` on Bus 001 Dev 006 (USB 2.0 480 Mb/s, 6 interfaces,
  ttyACM0/ttyACM1 via cdc_acm); USB SG Flash on the same xHCI controller.
  `/dev/video0` free, `meson_vdec` refcnt 0.
- IRQ placement (idle snapshot): xhci-hcd on CPU2 (10.5 M) with 14 k on CPU0;
  `vdec-mbox1` (254 k) and `esparserirq` (258 k) on CPU0.
- Tools: `v4l2-ctl`, `jq`, `bc`, `tmux`, `rsync`, `git` present;
  **no `pidstat`, `perf`, `trace-cmd`, `modetest`** — do not install without
  approval; use `/proc` sampling (`tools/latency_sampler.py`).
- `journalctl -k` is readable as `billieguo` (no sudo needed for kernel logs).
- `/proc/pressure/*` is not available (PSI disabled).
- `~/mobile_vt` is still **not a git repository**. Deployed hashes on
  2026-11-10: `config.py 1a6160d1`, `pipeline.py 60b7d312`,
  `worker_client.py d03297a6`, `decoder.py 0a63d896`, `control.py cc0cbcdc`,
  `cli.py a74bb800`, `config/vt13_video.kiosk.yaml d4d155f2`,
  `build/d3/d3_probe 51346c85` (startup gate + green-curtain fix + R1 sleep=0 +
  L2-B newest-frame presentation, deployed 2026-11-11 14:28; previous 888118fb
  backed up at `~/.codex_tmp/backup_l2b_20261111_142801/`); the repo `decoder.py`
  differs only by the local codec-identity logging (`5c7460f0`).
- Low-latency evidence (2026-11-10/11): all three reports (baseline, replay,
  live) are archived at `.codex_tmp/docs_backup_20261111_lowlatency/`
  (each with checksums; see `ARCHIVE_MANIFEST.md`). The original plan remains
  `plans/CM311_DJI_C5_Low_Latency_60FPS_Optimization_Plan.md`.
- 2026-11-11 14:28-14:58 V1 30 min soak on the deployed L2-B worker:
  **59.86 fps, 6 rebuilds, 0 corrupt, RC=0**, device idle after. **V1 status:
  ACCEPTED_WITH_LIMITATION** (glass-to-glass TODO; startup console 1-2 s;
  ~217 ms freeze per content-dependent `0xf`).
- **Sync check (2026-11-11 15:42)**: local changes committed as `a4d82c2`
  (`rc1-latency-instrumentation`); runtime Python on the CM311 synced to that
  commit (`worker_client f227791c`, `nal f2de7db7`, `decoder 5c7460f0`;
  full `vt13_video/*.py` + `kiosk.yaml` parity passed). Backup
  `~/.codex_tmp/backup_sync_20261111_154224/`. Deployed worker `51346c85` was
  built from the same commit's `tools/d3_probe.c`. The remote is not a git repo;
  tools/tests/docs/plan stay local. **Post-sync live check with VT on (15:56):
  PASS** — 30 s, gate opened, 1,745 frames / 30.106 s = 57.96 fps, 0 corrupt,
  RC=0, idle. A previous smoke was inconclusive because
  the VT source stopped after 0.47 MB (link apparently off).
- **Local repo (2026-11-11 16:05)**: `main` = `47ddd08` (fast-forward merge of
  the RC1 session commits); working tree clean; not pushed. Runtime on CM311
  unchanged (commit `a4d82c2` Python + worker `51346c85`).
- **Operational note**: a background job started with `&` by a non-interactive
  shell ignores SIGINT, so stop the pipeline with `--seconds N` (or SIGTERM),
  not `kill -INT`.

### 2026-11-06 15:52 HKT snapshot (historical)

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
