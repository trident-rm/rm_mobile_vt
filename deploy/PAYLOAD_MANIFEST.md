# CM311 eMMC minimal runtime payload manifest

Status: **G3 final minimal payload audited; G5 PASS on 2026-11-12 23:19 HKT; eMMC-only cold boot PASS; G6 PASS with user-confirmed HDMI output, physical hotplug, cold start, and reboot; display 180° rotation deployed as a software fallback but visually unconfirmed; atomic KMS worker deployed at ~49.7 FPS with program-side p50 79.7 ms / p95 109.2 ms (not glass-to-glass); P128 parallel tiled worker is now the production default (59.45 FPS 30-minute soak), with the A staging worker/config preserved as a tested fallback; formal G8 still pending.**
Updated: 2026-11-16 18:57 HKT.

## Exact payload measurement

- Source host: CM311, SG USB root.
- Measurement: root tar stream with `deploy/emmc-exclude.txt`, excluding `/boot`
  because the installer writes the separate eMMC boot partition.
- Tar stream: `2,853,621,760 B` (2.6577 GiB), `61,468` members.
- Installer post-copy additions:
  - `kms_render` 71,600 B + `kms_render.c` 17,021 B = `88,621 B`.
  - Replace two 717-byte service files with the reviewed 842-byte service:
    `+250 B`.
  - Add `/etc/modules-load.d/vt13-vdec.conf`: `11 B`.
- Final file payload: `2,853,710,642 B` (2.6577 GiB).
- Final tree entries: `61,473` (61,468 tar members + 2 created directories +
  2 helper files + 1 modules-load file; the two service files are replacements,
  not additions).
- Additional ext4 metadata and the two empty `.codex_tmp` directories are not
  included in that byte count; the G6 pre-start check recorded about 3.4 GiB
  free and 354,636 free inodes on `/`.
- Previous payload was `3,685,431,296 B`; the final payload is
  `831,720,654 B` smaller (793.2 MiB).

## Include

- Armbian OS, kernel, DTB, firmware, boot chain and system libraries under
  `/etc`, `/usr`, `/var` and the selected `/home` runtime tree.
- `usr/lib/modules/6.18.59-ophub/.../meson-vdec.ko` (ca46) and
  `usr/lib/firmware/meson/vdec/gxl_hevc.bin`; OF modalias autoload remains
  available. The installer adds `etc/modules-load.d/vt13-vdec.conf` as an
  explicit boot-time load.
- Native worker `home/billieguo/mobile_vt/build/d3/d3_probe` (only libc
  dependency).
- `vt13_video` source, config, deploy/udev sources, tests and docs.
- `etc/systemd/system/vt13-kiosk.service` (reviewed hash `3ed77408…`),
  `etc/systemd/journald@vt13-kiosk.conf`, and the actual installed udev rule
  `etc/udev/rules.d/99-vt13.rules` (`MODE=0660`, `GROUP=plugdev`,
  `TAG+=uaccess`, hash `9509a4c1…`).
- System Python `/usr/bin/python3` plus system `cv2`, `numpy`, `yaml`, `usb`
  and system PyAV 11.0.0 under `/usr/lib/python3/dist-packages`. The worker
  backend does not import PyAV; system PyAV remains available for diagnostics.
- System FFmpeg shared libraries under `/usr/lib/aarch64-linux-gnu`
  (`libavcodec.so.60`, `libavutil.so.58`, `libswscale.so.7`, and their
  dependencies). The custom `ffmpeg-6.1.1-v4l2-shared/install` tree is not
  required by the worker backend.
- The installer recreates `.codex_tmp` with owner `billieguo:billieguo` and
  mode `775`; only `kms_render` and `kms_render.c` are copied into it.

## Exclude

- `home/billieguo/mobile_vt/.venv-v4l2` (`53,038,516 B`): the target uses the
  system Python closure; local venv packages are PyAV/Cython/pip.
- `home/billieguo/ffmpeg-6.1.1-v4l2-shared` (`451,315,431 B`): the custom
  shared build is not used by the worker backend; the previous payload's
  `install/` copy (`21,660 KiB`) is no longer needed.
- Historical data: `captures` (`4,192,946,620 B`), `live_runs`
  (`1,003,038,014 B`), `mobile_vt/.codex_tmp` (`3,160,165,563 B`),
  `home/billieguo/.codex_tmp` (`11,166,659 B`), old logs and test artifacts.
- The old 384 KiB `kiosk_20261110` directory is reduced to the two required
  helper files (`88,621 B`); its logs and probe outputs stay on SG USB/PC.
- Kernel/FFmpeg source/build trees: `linux-6.18-vdec`, `ffmpeg-6.1.1-v4l2`,
  `ffmpeg-6.1.1-release`, toolchains and VDEC backup/release trees.
- Package metadata/cache: `/var/lib/apt/lists` (`446,341,742 B`) and
  `/var/cache/apt` (`116,582,575 B`); `/var/cache/debconf` and other small
  caches are retained.
- Historical logs: `/var/log/*` (`83,185,518 B`) and `/var/log.hdd`
  (`88,944,099 B`); the journald namespace remains volatile and bounded.
- Non-runtime documentation/source: `/usr/share/doc` (`36,050,056 B`),
  `/usr/share/man` (`15,684,903 B`), `/usr/share/locale` (`53,866,159 B`),
  `/usr/src` (`55,380,828 B`).
- Unused build products: `mobile_vt/build/lib`, `bdist.linux-x86_64`,
  `vt13_video.egg-info`, `__pycache__`, `.pytest_cache`, old backup trees and
  `hevc_capture_first`.

## Capacity and free space

- eMMC: `/dev/mmcblk2`, `7,474,249,728 B` (7128 MiB), subject to G5 identity
  recheck.
- ampart-success layout: vendor bootloader area 0–4 MiB; p1 FAT32
  `BOOT_EMMC` 117–628 MiB (512 MiB); p2 ext4 root 629 MiB–100%,
  `6,814,695,424 B` (6.3467 GiB). Free before ext4 metadata:
  `3,960,984,782 B` (3.6890 GiB).
- ampart-fallback layout: p1 FAT32 `BOOT_EMMC` 128–639 MiB (512 MiB); p2
  ext4 root 1360 MiB–100%, `6,048,186,368 B` (5.6328 GiB). Free before ext4
  metadata: `3,194,475,726 B` (2.9751 GiB).
- The boot partition is a fixed 512 MiB FAT32 partition separate from the root
  payload; the G6 pre-start check measured about 352 MiB free on `/boot`. Both
  root layouts exceed the 1 GiB free-space threshold before filesystem metadata;
  actual ext4 free space and inode availability are recorded above.

## G6 pre-start cold-boot evidence (2026-11-13 01:02 HKT)

- The SG USB was physically removed before power-on. CM311 boot time is
  `2026-11-12 23:40:55 HKT`, after the G5 `poweroff` at `23:19:57 HKT`.
- Root is `/dev/mmcblk2p2` ext4 UUID `61e6bfac-70ad-4d87-92db-a7399341722c`;
  `/boot` is `/dev/mmcblk2p1` vfat UUID `EE59-E094`. `lsblk` shows only eMMC
  devices and `zram0`; there is no USB block disk.
- SG Flash `23a9:ef18` is absent. DJI receiver `2ca3:1020` is present.
- `systemctl --failed` reports 0 units. `vt13-kiosk.service` is enabled and
  active (`MainPID=433`, `NRestarts=0`). `meson_vdec` is loaded (refcount 2)
  and `/etc/modules-load.d/vt13-vdec.conf` contains `meson_vdec`.
- Root free space is about 3.4 GiB with 354,636 free inodes; `/boot` has about
  352 MiB free.
- Current SSH is `10.42.0.253` through the PC's `cm311-local` shared DHCP
  (`10.42.0.10-254`). The old `10.42.0.11` lease is no longer assigned; this is
  a dynamic address.
- Evidence: `.codex_tmp/emmc_deploy_20261112/g6_coldboot_20261113_0055/g6_coldboot_precheck.txt`
  SHA256 `9c0ef4168c13d4ae03618b18fbb075c9b4ae2520d9ebe2a5cad4fa2a1a32bbbe`;
  summary `G6_COLDBOOT_PRECHECK.md`.
- This proves only the eMMC root/boot and SG-USB-removal precondition. HDMI/KMS,
  exact ca46 hash/vermagic after cold boot, native worker/config hashes, service
  journal/errors, USB access, HEVC hardware decode, and stable live display
  remain pending for G6.

## Changed paths/service configuration

- Target `vt13-kiosk.service` `ExecStart` uses `/usr/bin/python3`, not
  `.venv-v4l2/bin/python`. It remains non-root with `Restart=always`,
  `MemoryMax=512M`, and volatile `vt13-kiosk` journald namespace. Reviewed
  service SHA256 `3ed774081ba0e95f57fff253ae2c5fb5b76f0c5f2a65d00405741fded65149f1`,
  842 B. This system-Python service has passed a static import/config check and
  is now enabled and active on eMMC (`MainPID=433`, `NRestarts=0`); G6 must
  still review its journal/errors and restart behavior.
- Installer adds `/etc/modules-load.d/vt13-vdec.conf` containing `meson_vdec`.
- Installer copies the reviewed service from `/ddbr/vt13-kiosk.service` to both
  the installed unit and the target source `deploy/vt13-kiosk.service` path.
- Actual installed udev rule is preserved (`9509a4c1…`, 140 B). Repository
  source `4455e3b2…` has the same effective rule plus explanatory comments.
- Journald namespace remains `Storage=volatile`, `RuntimeMaxUse=32M`,
  `RuntimeMaxFileSize=4M`, `MaxRetentionSec=1day`; it cannot fill eMMC and
  logs do not survive reboot.
- No video recording is configured; the kiosk path writes no continuous video
  files.

## Final G5 staging hashes

- Reviewed installer: `90cb03905726b2aa3cfa5f2948f552694ab992642c750c1938cacd1bad5b5c12`
  (30,340 B).
- Installer patch: `175920b50b288a597d98e8209e0b575b067531042163756fbf7ff6bc2c2c5bf2`
  (4,529 B).
- Exclude manifest: `58b8fe241085f4cd996ea84340148aea2f5919bfca55e234542b28ca1fc6b88a`
  (1,397 B).
- Reviewed service: `3ed774081ba0e95f57fff253ae2c5fb5b76f0c5f2a65d00405741fded65149f1`
  (842 B).
- Original `/usr/sbin/armbian-install` remains untouched:
  `defc9646cd0aee8d33afcad04441a91f12eed7b82e8d1e6833c38401bd68f6f4`.
- Remote G5 staging directory:
  `/home/billieguo/mobile_vt/.codex_tmp/emmc_deploy_20261112/g5/`; all four
  hashes match and `bash -n armbian-install-final.sh` passed on CM311.
- At 19:16 HKT, a read-only SSH recheck confirmed the four staged hashes still
  match, `bash -n` still passes, `/ddbr` is currently absent (the installer
  creates it), `/dev/mmcblk2` is unmounted, and `vt13-kiosk.service` is active
  with `MainPID=447`, `NRestarts=0`. No eMMC write occurred.

## Gate conclusions

- G3: **RECOMMENDED PASS** for the final minimal payload, subject to the exact
  installer hash and G5 approval. The 61,468-member stream was measured as root;
  critical files were checked present and large excluded groups were checked
  absent.
- G4: **RECOMMENDED PASS_WITH_APPROVED_RISK**. Bootloader/DTB/ca46/firmware
  static compatibility remains valid. The runtime dependency conclusion changes:
  the target no longer needs the PyAV venv or custom FFmpeg shared install;
  system Python and system shared libraries are sufficient for the worker
  backend. G6 confirmed eMMC-only root/boot, ca46 autoload, service behavior,
  SSH/network access, and the live HEVC path; the user later confirmed HDMI
  output and physical USB hotplug.
- G5: **PASS**. eMMC installed with ampart/ext4; required runtime/module/firmware/service/KMS checks passed; evidence saved/verified; board powered off. The first eMMC-only cold boot has now been confirmed from `/dev/mmcblk2p2` and `/dev/mmcblk2p1`.
- G6: **PASS (user-confirmed)**. eMMC-only boot, boot files, ca46/firmware, worker/config/service/runtime hashes, permissions, HDMI connector, V4L2 HEVC, and a live ~60 FPS / `corrupt=0` path were verified. Service restart RC=0 and USB kernel `unbind/bind` recovery kept `NRestarts=0`; the manual bind needed `udevadm trigger` to restore the libusb ACL. The user then reported HDMI output, physical hotplug, cold start, and start-from-reboot all work. Formal G8 still requires three independent cold boots plus one supervised soft reboot. Residual content-dependent `0xf`, startup burst, glass-to-glass latency, and a fresh 30-minute soak remain open. Evidence `.codex_tmp/emmc_deploy_20261112/g6_validation_20261113_0110/` with `SHA256SUMS` 9/9 OK locally/remotely; cold-boot evidence 3/3 remote match.
- G6 post-check (02:12 HKT): the same service instance remained active with `MainPID=2935`, worker PID 2937 and `NRestarts=0`; `HDMI-A-1` stayed `connected/enabled`. Latest counters were 78,937 frames, 60.0 FPS, 38 errors / 1 recovery, `corrupt=0`, `backlog_max=0`, sessions=5. Boot time was confirmed as `2026-11-12 23:40:55 HKT` via `uptime -s`/PID 1; `who -b` showed 21:59 due to a wtmp discrepancy. Evidence `.codex_tmp/emmc_deploy_20261112/g6_postcheck_20261113_0211/g6_postcheck.txt` SHA256 `49919c75639340fe65abf68d6ccc2edd25480ab555623126a2c93f03a5054bb6`; remote hash check OK. The earlier PASS_WITH_LIMITATION caveat was later superseded by the user's HDMI/hotplug/cold-start/reboot confirmation.
- G6 HDMI black-screen diagnostic (02:39 HKT): the user reported black HDMI while the service streamed ~60 FPS with `corrupt=0`. The worker had no `--mode` and inherited `1920x1080i`; DRM showed overlay active with NV12 and primary disabled. A runtime-only 1080p60 test produced progressive 1920x1080@60 and YUV dumps with `Y_mean≈109`, proving decoded pixels are non-black. This isolates the fault to KMS presentation. Visual confirmation of the temporary mode is pending; no source/config/service file was changed. Evidence `.codex_tmp/emmc_deploy_20261112/g6_hdmi_black_20261113_023851/diagnostic.txt` SHA256 `bd7893fe700936a62ad103b85d49fd78cf415621fd43903ef551fd73e11d54eb`; remote hash check OK.
- G6 user confirmation (after the 02:39 diagnostic): the user reported that physical hotplug, cold start, and start-from-reboot all work and that HDMI has output. This closes the pending G6 HDMI-output and physical-hotplug observations. It does not satisfy the formal G8 matrix, which still requires three independent cold boots plus one supervised soft reboot.

## Display 180° rotation (2026-11-13 12:37 HKT)

- The user reported that the live VT view is rotated 180°.
- Meson overlay plane 42 has no DRM `rotation` property; standard KMS plane rotation is unavailable. The worker therefore uses a software fallback with four NV12 scratch dumb framebuffers, a cached staging copy, and NEON Y-row/UV-pair reversal.
- `vt13_video/worker_client.py` reads `VT13_WORKER_ROTATION`; the deployed service sets it to `180`. No bitstream, decoder, kernel, or module change was made.
- Rotation-only baseline worker: `build/d3/d3_probe d1257c49a45c2858346a517dcf1c445a2187962bce3e62b64154d7320c08a715`; source: `tools/d3_probe.c 6838cd3e1b22ceae831ea99f46252907b5a6525792e19ede5af9c6f732ae2e95`; service `MainPID=15994`, worker 15996, `NRestarts=0`, active/running. DRM scans scratch `fb=49`, `imported=no`.
- 30-second observation before the atomic optimization: about **29.7 FPS**, `corrupt=0`, 0 errors/recoveries, `stage_copy_avg_ms≈17.2–17.7`, `rot_copy_avg_ms≈2.8–2.9`, `setplane_avg_ms≈12.2–12.7`. This was a performance regression from the previous unrotated ~60 FPS path; the bottlenecks were uncached V4L2 dmabuf reads and blocking `SETPLANE` waits. The current atomic worker supersedes this baseline; see the next section.
- **Visual direction is still unconfirmed.** Do not record the rotation as visually fixed until the user confirms the picture is upright and unmirrored. If it is still wrong, distinguish 180° rotation from vertical-only or horizontal-only flip.
- Evidence: `.codex_tmp/emmc_deploy_20261112/g7_rotation_stage_20261113_1226/`; `SHA256SUMS` **29/29 OK** locally and remotely, manifest SHA256 `e337cce734d09715d8642ab54e1534dc834f8d19d56619210bed1c8ed70be69a`.

## Atomic KMS optimization and delay baseline (2026-11-13 14:03-14:06 HKT)

- `tools/d3_probe.c` now enables `DRM_CLIENT_CAP_ATOMIC`, submits overlay-plane
  updates with `DRM_IOCTL_MODE_ATOMIC` (`NONBLOCK | PAGE_FLIP_EVENT`), tracks
  `DRM_EVENT_FLIP_COMPLETE`, and waits for the matching flip before reusing a
  scratch framebuffer. If atomic setup or property validation fails, it falls
  back to legacy `SETPLANE`; pending flips are drained during cleanup.
- Deployed worker: `build/d3/d3_probe 9d610808d309d0fa6a2fb19f15558ffad2505b6410f7ca3600779b7b35055d01`;
  source: `tools/d3_probe.c fa9e5d07d4c7b81d36df2ed81f5275d2631206c084f4e59b24f18789621263a2`.
  Service `MainPID=24013`, worker PID 24015, `NRestarts=0`, active/running
  since 14:03:51 HKT. The 180° rotation remains software before KMS because
  plane 42 has no DRM `rotation` property.
- Offline smoke on the 1920x1080 60 fps sample `staging/vt13_idr_03.h265`:
  60 decoded frames, RC=0, 50.74 FPS, `corrupt=0`; atomic submit about
  0.10 ms.
- 34-second steady window: 49.7 FPS, `corrupt=0`, `sessions=1`; no RECOVER,
  atomic fallback, flip-wait timeout, or `0xf` in the sampled window. Local
  stage medians: staging copy 16.545 ms (p95 17.442), rotation 2.855 ms
  (p95 3.026), KMS atomic submit 0.10 ms (p95 0.1135), flip wait 0.00 ms.
- Sender AU timestamp to program-side present: p50 **79.7 ms**, p95
  **109.2 ms**, max observed **187.5 ms**. Subtracting measured local stages
  yields upstream wireless/USB/AU receive + decoder queue p50 **60.2 ms**,
  p95 **88.6 ms** (derived, not split per frame). This is **not
  glass-to-glass**; HDMI scanout/panel response is not included.
- The previous rotation-only worker was ~29.7 FPS with
  `setplane_avg_ms≈12.5`; the atomic worker is ~49.7 FPS with
  `setplane_avg_ms≈0.10`. The largest remaining local cost is the 16.5 ms
  staging copy, followed by the 2.9 ms software rotation.
- **Visual direction is still unconfirmed.** Do not record the rotation as
  visually fixed until the user confirms the picture is upright and
  unmirrored.
- Evidence: `.codex_tmp/emmc_deploy_20261112/g7_atomic_20261113_1340/`;
  `SHA256SUMS` **20/20 OK** locally and remotely; manifest SHA256
  `268c1c5b8630cce1f77fabac13f4e9ab20075fc68f23dcc0fb3589a2b3a8921f`;
  plot `delay_flow.png` and summary `delay_flow_summary.json`.

## Residual risks

- The eMMC bootloader write now has dynamic proof for the eMMC-only cold boot;
  G6 passed with user-confirmed HDMI output, physical hotplug, cold start, and
  reboot. Formal G8 still requires three independent cold boots plus one
  supervised soft reboot. Residual content-dependent `0xf` and the startup burst
  are not closed by eMMC migration.
- The 180° rotation is implemented but **visually unconfirmed**. Atomic KMS
  removes blocking `SETPLANE` waits and raises the live rate to about 49.7 FPS;
  the largest remaining local cost is the 16.5 ms NV12 staging copy, followed
  by the 2.9 ms software rotation. KMS plane 42 still has no hardware rotation
  property.
- A failed eMMC boot may require physical reset or Amlogic USB Burning Tool;
  the SG USB remains the verified fallback but is not a byte-for-byte disk image.
- The content-dependent `0xf` abort, recovery freeze (~217–283 ms), occasional
  boot `0xf` burst, one historical soft-reboot hang, and unmeasured
  glass-to-glass latency remain open; eMMC migration does not close them.
  Program-side p50 79.7 ms / p95 109.2 ms is not a glass-to-glass measurement.
- The fresh 30-minute soak for the current `9d610808` atomic worker + ca46
  combination is still required in G7/G8.
