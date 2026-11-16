# Intersession Transfer: VT13 / CM311

## 2026-11-16 19:58 HKT — Worker client canonicalized; production client restored and diagnostic variant synced

- **Decision**: the remote production client `51862863…` (matching `fdd74b3`) is canonical; the local `cad4fe2a…` version is diagnostic only.
- **Repository changes**: restored `vt13_video/worker_client.py` to SHA256 `518628638a5fa0da0914a5ac38e0c7255e7b801817eb7314a915f149da887279`; preserved the diagnostic version as `vt13_video/worker_client_instrumented.py` SHA256 `cad4fe2ae0d476b37f36fb45e7e5e9aed7b77001681a854acbee7f19addcd2d2`; updated `tests/test_latency.py` to test the production 6-column CSV schema and the diagnostic 9-column schema.
- **Local verification**: `PYTHONPATH= python3 -m pytest -q` returned **54 passed, 38 skipped, 9 subtests passed** in 2.01 s; `py_compile` passed for both client files and the test module.
- **Remote sync**: `~/mobile_vt/vt13_video/worker_client.py` SHA256 `51862863…` and `~/mobile_vt/vt13_video/worker_client_instrumented.py` SHA256 `cad4fe2a…`; remote `py_compile` passed. No service restart, binary replacement, or kiosk config change.
- **Runtime state**: `vt13-kiosk.service` remains active; worker PID `1334378` still runs `build/d3/d3_probe_p128_exact`.
- **Next**: use canonical `worker_client.py` by default; use `worker_client_instrumented.py` only when the extra latency/trace fields and worker environment plumbing are needed.

## 2026-11-16 19:46 HKT — P128 source provenance fixed; exact source canonical and remote tree updated

- **Problem**: local HEAD `6167ce6` contained instrumented `tools/d3_probe.c` (`3a742e53…`), while the deployed exact worker `663f75e0…` was built from exact source `230a2604…` that existed only under `.codex_tmp`. Remote `~/mobile_vt/tools/d3_probe.c` was stale at `fa9e5d07…`.
- **Repository changes**: replaced `tools/d3_probe.c` with exact P128 source SHA256 `230a26046daaed5ce04a780f2aac4773473b864c5553c6a19061cbfe8a8bc779`; preserved instrumented source SHA256 `3a742e533fbcf557e5840feb4395c547e0b45bba6e93b9fb1a35dc72bef7d826` as `tools/d3_probe_instrumented.c`; added `Makefile` targets `exact` and `instrumented`; added `deploy/P128_BUILD_PROVENANCE.md`.
- **Build verification (CM311 `billieguo@10.42.0.253`)**: `make exact BUILD_DIR=/tmp/d3_build_check` produced `663f75e09e021b3877ee9da70c543b00fa82742c5f108af4ad6a1e69466285dc`; `make instrumented BUILD_DIR=/tmp/d3_build_check` produced `6cdb04a327df526c84912c0ee300ae9a1e2a32bea0ed14183cec19c4b17c0217`. Both matched the recorded artifacts.
- **Basename caveat**: the deployed exact binary is unstripped and records `STT_FILE`. Compiling the same exact source as `d3_exact.c` produced `1a091b6a0a4aea9d14a7d4ca50fd4114f75b5ea543afc961b3b7113d77f6a53a`; production builds must use a source named `d3_probe.c`. `make exact` does this.
- **Remote sync**: backed up old remote source `fa9e5d07d4c7b81d36df2ed81f5275d2631206c084f4e59b24f18789621263a2` to `~/mobile_vt/.codex_tmp/backup_d3_source_20261116_20261116_194545/d3_probe.c`; replaced `~/mobile_vt/tools/d3_probe.c` with exact `230a2604…`; remote rebuild produced `663f75e0…`. Also synced `Makefile`, `tools/d3_probe_instrumented.c`, and `deploy/P128_BUILD_PROVENANCE.md`. No service restart, running-binary replacement, or kiosk config change.
- **Local verification**: `PYTHONPATH= python3 -m pytest -q` returned **53 passed, 38 skipped, 9 subtests passed** in 2.01 s; `make exact` and `make instrumented` compile on the PC (x86-64 hashes differ from the ARM target as expected).
- **Worker client**: remote `vt13_video/worker_client.py` remains `518628638a5fa0da0914a5ac38e0c7255e7b801817eb7314a915f149da887279`, matching commit `fdd74b3`; local `cad4fe2ae0d476b37f36fb45e7e5e9aed7b77001681a854acbee7f19addcd2d2` is diagnostic/env plumbing and was not deployed.
- **Next**: deploy the worker-client changes separately only if wanted; otherwise keep the remote baseline. P128 production behavior is unchanged.

## 2026-11-16 18:57 HKT — P128 deployed as production default; A fallback preserved and tested

- **User decision**: P128 is now the intended production default; A remains a selectable fallback. No kernel, DTB, bootloader, ca46, eMMC partition, or USB-transport change was made; no commit was created.
- **Default config**: `config/vt13_video.kiosk.yaml` SHA256 `919a30323370a2077201feda0991d40c99f931330df787f59441074aa1b5d7ec`, identical to `config/vt13_video.kiosk.p128.yaml`; it sets `decoder.worker_path: /home/billieguo/mobile_vt/build/d3/d3_probe_p128`. Wrapper SHA256 `92d9c17c38de3263e4e2ef778be0df1bc51dac73d0c219dcb61d5158336b7685`; exact worker SHA256 `663f75e09e021b3877ee9da70c543b00fa82742c5f108af4ad6a1e69466285dc`; wrapper flags `--rotation-mode P --dmabuf-sync 1 --source-hold 2`.
- **A fallback**: `config/vt13_video.kiosk.a.yaml` SHA256 `d4d155f2c683ccb93870baea1ca1790e2f60bb228ff644378874c990448ebaa1`; A worker `build/d3/d3_probe` SHA256 `9d610808d309d0fa6a2fb19f15558ffad2505b6410f7ca3600779b7b35055d01` was not overwritten. Fallback command: `cp config/vt13_video.kiosk.a.yaml config/vt13_video.kiosk.yaml && sudo systemctl restart vt13-kiosk.service`; restore P128 with `cp config/vt13_video.kiosk.p128.yaml config/vt13_video.kiosk.yaml && sudo systemctl restart vt13-kiosk.service`.
- **P128 default verification**: service `vt13-kiosk.service` active and enabled, `MainPID=1334328`, worker PID `1334378`, `NRestarts=0`; `/dev/video0` and `/dev/dri/card0` are owned only by the P128 worker. Worker args include `--rotation-mode P --dmabuf-sync 1 --source-hold 2`; log shows four NV12 scratch framebuffers, `CAPTURE G_FMT 1920x1080 NM12`, source 59.9 FPS, worker cumulative 58.5 FPS, `corrupt=0`, backlog 0, `dmabuf_sync=1`, `atomic=1`.
- **A fallback verification**: stopped P128, switched kiosk config to the A fallback, started A, and observed worker `build/d3/d3_probe` SHA256 `9d610808…5d01`, `/dev/video0` and `/dev/dri/card0` owned only by A worker, source 60 FPS, `corrupt=0`, `stage_copy_avg_ms≈16.2`, `rot_copy_avg_ms≈2.8`. Then restored the P128 config and restarted P128; final service is active with the P128 worker.
- **Evidence**: `.codex_tmp/p128_default_20261116/` with `pre_state_and_backup.log`, `upload_and_hash_check.log`, `p128_start.log`, `fallback_and_restore.log`, `final_p128_observation.log`; manifest `SHA256SUMS` SHA256 `a699563a75970a1b4a40d42ab6fcdaee5fb64c8aa32fc571f32f76d5ae7b62d9`; local verification passed.
- **Status**: P128 is the production default. The previously recorded limitations remain: physical HDMI visual/orientation/tearing confirmation, physical USB hotplug, the 1832×1032→1920×1080 transition, content-dependent `0xf`, 80°C/DVFS, EBUSY pre-commit wait, and glass-to-glass latency. `K3 ACCEPTED_WITH_LIMITATION` is unchanged.

## 2026-11-16 18:10 HKT — exact P128 deployment candidate live validation: PASS; 59.45 FPS 30-minute soak; production A restored, no switch

- **Scope/host**: CM311 `billieguo@10.42.0.253`, eMMC-only boot, real DJI USB source and HDMI/KMS. `run_exact_validation.sh` stopped `vt13-kiosk.service`, waited for `/dev/video0` and `/dev/dri/card0` to be free, ran the exact deployment binary, and restored A through the harness `trap`. No reboot, module reload, kernel/DTB/ca46/eMMC/USB-transport change, golden-data overwrite, commit, or default-worker switch.
- **Candidate/config**: exact worker `build/d3/d3_probe_p128_exact` SHA256 `663f75e09e021b3877ee9da70c543b00fa82742c5f108af4ad6a1e69466285dc`; `P128_exact.yaml` `95d3967924290de6d3d8d511c69c7ea43f601cf6ed5f9209a2274e942f8b58b8`; `P128_exact_soak.yaml` `2e357a8dc14edb323bcb1cc32d617e094f92b290c6e52e73de09034994dd5f3d`; `run_exact_validation.sh` `4dd26941e0ea84bc51378d445ecd950aaa136fbcce20c737da7f7815b0e3449d`. All six runs returned `py_rc=0 worker_rc=0`; the run log is `phase_b/run_exact_20261116_172807.log`.
- **Exact short test**: 3×65 s with 5 s warm-up. Median completed-flip **59.95 FPS**; transform p50/p95/p99/max **8.669/11.329/12.571/16.262 ms**; AU receive→vblank **58.272/68.410 ms** p50/p95; 2 resets/5 sessions total; 0 corrupt; temp max 78°C; worker CPU 136.38%.
- **Exact 5-minute test**: **59.27 completed-flip FPS**; transform p50/p95/p99/max **8.741/11.733/13.843/19.42 ms**; receive→vblank **62.077/86.244 ms**; 14 resets/15 sessions; 0 corrupt; temp max 80°C; worker CPU 137.78%.
- **Exact 30-minute soak**: **59.45 completed-flip FPS**, decoded 59.42, submitted 59.45; transform p50/p95/p99/max **8.709/11.603/13.318/24.993 ms**; receive→vblank **59.442/79.827 ms**; AU receive→decoder p95 47.678 ms; decoder→KMS p95 32.379 ms; submit→vblank p95 16.442 ms; 62 resets/63 sessions; 0 corrupt, 0 flip mismatch/unmatched, atomic fallback 0, DMA-BUF sync supported; USB errors/recoveries 0; frame duplicates 1; skipped source intervals 989; max AU queue depth 6. CPU 138.58%, temp max 80°C, RSS max 1,684 KB, available memory min 1,356,416 KB.
- **KMS/Phase D**: exact KMS submit p95 was **6.888 ms** short, **8.144 ms** 5-minute, **7.673 ms** soak. Exact trace does not split preparation/commit; the instrumented Phase D measurement remains the attribution evidence: actual atomic commit p95 **0.124/0.128 ms**, pre-commit EBUSY/retry gap p95 **8.117/8.042 ms**. Keep synchronization and retry safeguards.
- **`0xf`/recovery caveat**: exact short runs had 2 resets total, the 5-minute run 14, and the soak 62 resets/63 sessions. The soak dmesg summary `status_0xf=0` is a ring-buffer/window artifact; worker resets are authoritative. Recovery remained automatic, with 0 corrupt frames.
- **Resource/throttling**: exact short/5-minute/soak CPU was 136.38/137.78/138.58%; temperature 78/80/80°C. The soak sampled CPU frequency below maximum in 1,446/1,779 samples (mean 1.69 GHz, p50 1.752 GHz); no thermal shutdown was observed. This is acceptable for extended testing but should remain monitored.
- **Production restore**: `vt13-kiosk.service` active with `MainPID=1314877`, worker PID `1314878`, `NRestarts=0`; A worker path/hash is unchanged (`9d610808…5d01`), both devices are owned only by the A worker, and `CAPTURE G_FMT` at restore was 1920x1080 NM12. A later read-only check showed 1280x720 NM12, indicating a source-side resolution change after validation. P128 is still not the default.
- **Evidence**: `phase_b/exact_smoke/`, `phase_b/exact_short_{1,2,3}/`, `phase_b/exact_5min/`, `phase_b/exact_soak30m/`, `phase_b/aggregate_exact_short.json`, `phase_b/run_exact_20261116_172807.log`, `configs/P128_exact*.yaml`, and `scripts/run_exact_validation.sh`. `SHA256SUMS_exact.txt` SHA256 `efeb2663f9e9f61e6b561316b5cdfcdab92b3b57fb45d21b1ce871a1edcea01b`; local and remote verification **150/150 OK**.
- **Decision**: remain **`P128_ACCEPTED_WITH_LIMITATION`**. The exact deployment candidate now passes live short, 5-minute, and 30-minute automated validation, but physical HDMI visual/orientation/tearing, physical USB hotplug, the 1832×1032→1920×1080 transition, content-dependent `0xf`, 80°C/DVFS, EBUSY wait, and glass-to-glass latency remain limitations. `K3 ACCEPTED_WITH_LIMITATION` is unchanged.
- **Next**: human confirms HDMI and optionally performs a physical DJI unplug/replug; try the resolution transition again; commit source/docs; obtain separate deployment approval before switching P128 as the default.

## 2026-11-16 16:35 HKT — P128 live A/B + 30-minute soak: PASS_WITH_LIMITATION; production A restored, no switch

- **Scope/host**: CM311 `billieguo@10.42.0.253`, eMMC root `/dev/mmcblk2p2` and boot `/dev/mmcblk2p1`, real DJI USB source and HDMI/KMS. Each measurement stopped `vt13-kiosk.service`, verified `/dev/video0` and `/dev/dri/card0` were free, ran one candidate, then restored A through the harness `trap`. No reboot, module reload, kernel/DTB/ca46/eMMC/USB-transport change, or golden-data overwrite.
- **Phase A preservation/rollback: PASS**. Production A worker is `build/d3/d3_probe` SHA256 `9d610808d309d0fa6a2fb19f15558ffad2505b6410f7ca3600779b7b35055d01`; service `adcd98ff4fa0952e40c92f55b4f6e4c665c67ab06eef150c84764e1d6217ec57`; config `d4d155f2c683ccb93870baea1ca1790e2f60bb228ff644378874c990448ebaa1`; client `518628638a5fa0da0914a5ac38e0c7255e7b801817eb7314a915f149da887279`. `scripts/phase_a_rollback_test.sh` stopped the service, confirmed both devices were released, restarted it, verified the worker path/hash, and observed `CAPTURE G_FMT 1920x1080 NM12`; result `ROLLBACK_TEST=PASS`.
- **Phase B A side: PASS**. Actual source was **1920x1080, 59.7–59.9 AU/s**. Three 60 s production-A runs had median **50.0 completed-flip FPS**; the 5-minute run had **51.0 FPS**, 10 decoder resets, 0 corrupt frames, worker CPU 98.01%, and 77°C max. The instrumented A trace (different binary, no production trace) measured fused transform p95 **22.126 ms** and AU receive→kernel-vblank p50/p95 **102.886/142.762 ms**.
- **Phase B P128 side: PASS**. Short-run median was **58.88 completed-flip FPS**; 5-minute **56.4 FPS**; 30-minute soak **59.0 FPS**. Short transform p50/p95/p99/max was **8.787/11.635/14.497/25.085 ms**; soak **8.741/11.465/13.292/24.379 ms**. Short receive→vblank was **62.745/85.117 ms**; 5-minute **65.481/83.850 ms**; soak **60.805/87.439 ms**. All reported runs had 0 corrupt frames, 0 flip mismatches/unmatched, atomic fallback 0, DMA-BUF sync supported, and max pending-flip depth 1.
- **Phase D findings**. The reported KMS submit p95 **8.199 ms (short) / 8.126 ms (soak)** is application-level waiting before the atomic commit, not driver execution. Actual `drmModeAtomicCommit`/atomic ioctl p95 was **0.124/0.128 ms**; the pre-commit gap p95 was **8.117/8.042 ms**, matching EBUSY/retry waits (6,637 short and 52,917 soak). Userspace DRM-event read lag p95 was ~15.4–15.5 ms. Keep the existing synchronization and retry safeguards.
- **Phase E: PASS_WITH_LIMITATION**. The 30-minute soak exited RC=0 with 0 corrupt frames, no flip mismatch/unmatched, pending depth 1, RSS max 1.684 MB with no growth, CPU 138.22%, 78°C max, and no USB errors/recoveries. A simulated USB `1-1` unbind/bind recovered in **3.998 s** (reopen) / **4.825 s** (stream resume), with one USB recovery and 60.0 setplane FPS afterward; this was not a physical connector pull. Repeated session initialization was exercised by smoke/short/5-minute/soak/hotplug runs. The 1832×1032→1920×1080 transition was **not reproduced**; the source remained 1920×1080. HDMI visual quality, tearing, rotation direction, and glass-to-glass latency still require human/physical measurement.
- **Critical `0xf` caveat**: the summary field `status_0xf=0` reflects a limited dmesg window and is not proof of zero kernel aborts. Worker logs show 4–7 aborts per short run, 59 in the 5-minute run, and 108 resets/109 sessions in the soak. Content-dependent `0xf` remains unresolved; recovery was automatic and no corrupt frames were counted.
- **Deployment candidate prepared, not switched**. Local revision is `fdd74b3` with uncommitted changes. Exact source SHA256 `230a26046daaed5ce04a780f2aac4773473b864c5553c6a19061cbfe8a8bc779`; instrumented source `3a742e533fbcf557e5840feb4395c547e0b45bba6e93b9fb1a35dc72bef7d826`; diff `22a27c99f52fa3e4e1a49c756a93bdd39395fb096f0e9b292134539388b0effc`. Build was `gcc 13.3.0 -O2 -Wall -Wextra` on the target. Exact candidate `build/d3/d3_probe_p128_exact` SHA256 `663f75e09e021b3877ee9da70c543b00fa82742c5f108af4ad6a1e69466285dc`; wrapper `build/d3/d3_probe_p128` SHA256 `92d9c17c38de3263e4e2ef778be0df1bc51dac73d0c219dcb61d5158336b7685`; P128 config SHA256 `919a30323370a2077201feda0991d40c99f931330df787f59441074aa1b5d7ec`. The wrapper injects `--rotation-mode P --dmabuf-sync 1 --source-hold 2`. The 16:35 instrumented metrics were superseded by a separate 18:10 validation of the exact deployment candidate (3×60 s, 5-minute, and 30-minute soak). The production client already supports `worker_path`, so no client replacement is required.
- **Code/build scope**: P128 adds a selectable `--rotation-mode P` path with four pthreads over disjoint scanout rows, tiled NV12 Y/UV-pair reversal, `DMA_BUF_IOCTL_SYNC` begin/end around CPU access, four scratch framebuffers, and flip-event-based scratch lifetime/atomic pending tracking. Existing A staging mode remains the default/fallback. Instrumentation adds trace CSV, flip matching, DMA-BUF/KMS stage timestamps, pending depth, and EBUSY counters; `worker_client.py` gained trace/worker env plumbing and receive timestamps.
- **Final production state (read-only check, RC=0)**: `/` remains eMMC; `vt13-kiosk.service` active with `MainPID=747451`, worker PID `747452`, `NRestarts=0`; worker path and SHA256 are the original A values above; `/dev/video0` and `/dev/dri/card0` are owned only by worker 747452; latest capture format was 1920x1080 NM12. No permanent P128 switch and no commit were made.
- **Local verification**: non-sandbox `PYTHONPATH= python3 -m pytest -q` returned **53 passed, 38 skipped, 9 subtests passed** in 2.01 s; `git diff --check` was clean. The first sandboxed run had 2 `test_latency.py` failures because this sandbox denies AF_UNIX `socketpair.send` with `PermissionError`; the same tests pass outside the sandbox. This is an environment limitation, not a code regression.
- **Evidence**: `.codex_tmp/p128_live_20261116/phase_a/` (12/12 hashes verified), `phase_b/` (per-run summaries, traces, dmesg, sys samples, aggregate JSON), `phase_f/` (candidate/wrapper/config/service), `p128_build/` (exact/instrumented sources and binaries), `scripts/` (rollback, A/B harness, hotplug). Final summary SHA256 `f41b409df7a41297178ffaae39c8050c8dcecbda9ffba05e1fbe9a213d5d28df`; final manifest `dc4627435d8b7a89f29e6a6162e81a46731d264556d6810fb66a4a32cce0a20e`; local archive verified 32/32.
- **Decision**: **`P128_ACCEPTED_WITH_LIMITATION`**. Automated live A/B and 30-minute soak pass; P128 is faster and materially below the A transform p95, but physical HDMI/hotplug, resolution transition, content-dependent `0xf`, ~8 ms EBUSY wait, and glass-to-glass latency remain limitations. `K3 ACCEPTED_WITH_LIMITATION` is unchanged.
- **Next**: human confirms HDMI orientation/tearing and optionally performs a physical DJI unplug/replug; try to reproduce 1832×1032→1920×1080; after separate deployment approval, switch only the worker/config/service default and keep A selectable. Commit source/docs separately from the runtime switch.

## 2026-11-16 10:03 HKT — CM311 deployment tree vs local sync audit; not synchronized, remote production state retained

- **Scope/host**: read-only `rsync -nac` comparison between CM311 `billieguo@10.42.0.253:~/mobile_vt` and the local `mobile_vt` working tree. Excluded `.git`, `.codex_tmp`, `captures/`, `live_runs/`, `vt13_frames/`, `build/`, Python caches, `AGENTS.md`, `.gitignore`, `plans/`, and `archive/`. No remote writes, service restart, or build.
- **Remote state**: CM311 is not a valid Git repository; the deployment tree is 1.9 MiB. `vt13-kiosk.service` remains active, worker PID 143053 runs `/home/billieguo/mobile_vt/build/d3/d3_probe`; that binary is SHA256 `9d610808d309d0fa6a2fb19f15558ffad2505b6410f7ca3600779b7b35055d01` (73,688 B, 2026-11-13 14:03).
- **Divergence**: 8 common files differ in content: `README.md`, `VT13_USB视频逆向项目进度与后续计划.md`, `tests/test_config.py`, `tests/test_ffmpeg_pipe.py`, `tests/test_pipeline.py`, `tools/d3_probe.c`, `udev/99-vt13-video.rules`, and `vt13_video/worker_client.py`. Remote has 13 local-absent legacy scripts/docs; local has 14 remote-absent deployment/docs/tools files. Most other common files are byte-identical and differ only in timestamps or permissions.
- **Deployment/source mapping**: remote `tools/d3_probe.c` is `fa9e5d07…` and `vt13_video/worker_client.py` is `51862863…`, matching the deployed production worker. Local `tools/d3_probe.c` is `230a2604…` (newer P128 development source) and `worker_client.py` is `43755fc2…`. Local HEAD is `fdd74b3`; local `build/` has no ARM `build/d3/d3_probe`, only an x86 L2 helper at `.codex_tmp/l2_20261113/d3_probe_local` (`68f3d514…`).
- **Conclusion**: the trees are **not synchronized**. Treat CM311 as authoritative for deployed runtime and local as the newer development tree; do not blanket-sync either direction. Selectively deploy only after tests/acceptance.
- **Next**: if a local deployment mirror is desired, sync the remote deployment subset without deleting local development artifacts; if promoting P128, deploy `tools/d3_probe.c` plus a rebuilt ARM binary and update the service deliberately.

## 2026-11-13 20:40 HKT — CM311 temp data/recording cleanup; 1.8 GiB freed, kiosk untouched

- **Scope/host**: CM311 `billieguo@10.42.0.253`, remote project `~/mobile_vt`. User requested cleanup of remote temporary data/files/recordings. No code, config, service, kernel/module, bootloader, DTB, or eMMC write.
- **Removed**: `~/mobile_vt/.codex_tmp/l2_20261113/` (benchmark staging, source HEVC/YUV dumps, evidence), `.codex_tmp/emmc_deploy_20261112/` (G5/G6/G7 logs and dumps), and `.codex_tmp/kiosk_20261110/`. Remote `.codex_tmp` went from 1.8 GiB to 4 KiB.
- **Preserved**: active `vt13-kiosk.service` socket `~/mobile_vt/.codex_tmp/d3_worker.sock`; service remained active with the same PIDs 143052/143053 and socket state LISTEN/CONNECTED. `~/.codex_tmp`, `captures/`, `live_runs/`, and `.codex_runs/` were absent; `/tmp`, `/dev/shm`, and `/var/tmp` had no material data and were left alone.
- **Capacity**: root `/dev/mmcblk2p2` went from 4.6 GiB used / 75% (1.6 GiB free) to 2.8 GiB used / 46% (3.4 GiB free).
- **Evidence**: local mirrors remain authoritative: `.codex_tmp/l2_20261113/` (1.5 GiB), `.codex_tmp/emmc_deploy_20261112/` (31 MiB), `.codex_tmp/kiosk_20261110/` (32 KiB). Earlier remote `.codex_tmp` evidence paths in this document are historical and no longer present on CM311.
- **Next**: resume L2 work from the local evidence copy; do not expect remote benchmark artifacts until a new run writes them under `.codex_tmp`.

## 2026-11-13 19:58 HKT — L2 offline A/B/C/T/P benchmark; P128 reaches 60.00 completed-flip FPS and fused p95 11.433 ms; production unchanged

- **Scope/host**: CM311 `billieguo@10.42.0.253`, remote project `~/mobile_vt`; offline file replay through the native worker and KMS only. No real USB capture, HDMI visual acceptance, wireless test, reboot, `meson_vdec` reload, or ca46/kernel/USB/bootloader/DTB/eMMC change. The kiosk was temporarily stopped for exclusive DRM access and restored by the remote `trap` after every run.
- **Production state**: after benchmarking `vt13-kiosk.service` was active with `MainPID=143052` and `NRestarts=0`. The production worker remains `build/d3/d3_probe` SHA256 `9d610808d309d0fa6a2fb19f15558ffad2505b6410f7ca3600779b7b35055d01`; P128 was not copied over it.
- **Per-frame trace/clock definitions**: the current USB/AU protocol carries no sender timestamp, so trace rows use `sender_ns=-1`. `t_pipeline_send_ns` is the CM311 replay process's `time.monotonic_ns()`, not a transmitter clock. `t_worker_recv_ns`, `t_decoder_enqueue_ns`, `t_decoder_dequeue_ns`, DMA-BUF CPU-sync start/end, copy/rotation start/end, and `t_kms_submit_start/end_ns` are same-host `CLOCK_MONOTONIC`. `t_kms_flip_event_ns` is the userspace DRM-event read time; `kms_flip_tv_ns` is the kernel vblank timestamp. Therefore `submit_end_to_flip_tv_ms` is the measured submit-to-flip interval, while `flip_event_tv_delta_ms` is event-read lag. The old 34-second baseline is retained: 49.7 FPS, AU timestamp→KMS submit p50/p95/max 79.7/109.2/187.5 ms, staging copy 16.5 ms, rotation 2.9 ms, submit 0.10 ms. Its approximately 60.2 ms upstream/decoder residual remains derived, not independently measured, and its `flip_wait=0` was not proof of scanout completion. The new replay `send→flip` endpoint differs from the old AU-timestamp endpoint and must not be presented as a direct improvement.
- **Input**: `source/live_run09_clean_2322_3600.h265`, SHA256 `b1b1af54390a82e07491ba1614190043d754dfacab9221e898b94b39ef6e8034`, 3600 AU, 1920x1080@60, one IRAP at the start. The periodic-IRAP `600x6` sample was preflight-only; `segment3_x2_ps.h265` is not steady-state because of POC16 `0xf` and `sessions=2`.
- **Benchmark command/RC**: remote `bash staging/l2_benchmark.sh --run-dir RUN --worker build/d3_probe_l2_p128 --source source/live_run09_clean_2322_3600.h265 --duration 60 --repeats 3 --modes P --source-hold 2 --warmup 5`, with `--cap-bufs 17 --dmabuf-sync 1` supplied by the script. A/B/C/T used the same shape with their respective workers/modes and three repeats each. All final P runs completed with worker RC=0 and replay RC=0; the replay sent 3600/3600 AU in 60.001 s with `dropped=0`.
- **Pooled results (3x60 s per candidate, 5 s warm-up)**:

| Candidate | Completed-flip FPS | Fused transform p50/p95/p99/max (ms) | Notes |
|---|---:|---:|---|
| A staged copy | 50.01 | 19.16 / 20.98 / 22.082 / 28.678 | Original baseline; about 99% of one core |
| B reverse read | 33.90 | 28.552 / 36.295 / 37.049 / 41.76 | Direct reverse source read |
| C forward read | 33.96 | 27.94 / 36.22 / 36.949 / 38.784 | Direct forward source read |
| T128 tiled | 52.74 | 18.025 / 19.849 / 20.046 / 22.62 | 128x128 Y / 64 UV-pair tiles |
| **P128 parallel** | **60.00** | **9.081 / 11.433 / 13.671 / 23.13** | 4 pthreads; fused p95 below the 12 ms target |

- **P128 latency detail**: enqueue→dequeue p50/p95 17.176/33.755 ms; replay→worker 7.016/23.47 ms; replay send→flip vblank 59.043/72.87 ms; submit→flip vblank p50/p95 16.339/16.438 ms. These are pooled replay-path measurements, not AU-timestamp or glass-to-glass measurements.
- **Resources**: P128 worker CPU mean 134.7% across four threads; system CPU busy p50/p95 40.6/45.8%; temperature max 64 C; available memory minimum 1,317,492 kB. A/T single-thread workers used about 99.17/98.99% of one core. Logical NV12 traffic is a derived value, not a DRAM-controller measurement: A≈622.2, B≈210.9, C≈211.3, T≈328.1, P≈373.25 MB/s.
- **Correctness**: every A/B/C/T/P long run reported `corrupt=0`, `0xf=0`, `abort=0`, `sessions=1`, flip unmatched/mismatch=0, atomic fallback=0, and DMA-BUF sync supported=1. Same-run source-NV12 plus rotated-scratch verification passed 20/20 frames for A, T, and P; Y bytes and UV pair ordering exactly matched the expected 180-degree transform. Cross-run same-sequence dumps differ on some frames because hardware-decoder output is not bit-identical across runs; the same-run comparison is the transform proof, not cross-run hashes.
- **Buffer ownership/synchronization audit**: source DMA-BUF CPU reads are wrapped by `DMA_BUF_IOCTL_SYNC` start/end; the worker never reads a CAPTURE buffer after returning it to the decoder. Four NV12 scratch framebuffers are reused only after a matching flip event/token. `source-hold=2` conservatively retains two source frames before requeue; hold0 showed equal performance without observed corruption or flip mismatch, but is not the recommended default yet. Atomic flips are matched by framebuffer/token/sequence; legacy fallback was not triggered. Planes 39/42 expose no DRM `rotation` property, so the 180-degree software fallback remains in use.
- **Artifacts/hashes**: `tools/d3_probe.c` SHA256 `230a26046daaed5ce04a780f2aac4773473b864c5553c6a19061cbfe8a8bc779`; P128 binary `0cb20aadaf5d3899528dfce30fa9e733b2cf338eb2fc1b7538349c1d459114f4`; `tools/l2_benchmark.sh` `2f4d09df98d8e94d9fae53378375102c0291d690b6b2b8f47cd4d2008fb8e06d`; `tools/l2_aggregate.py` `bd3c99b6c0a098f41ea4bb3b730b0a24f694e9c9fb86a031748d6ae15cbce2fa`; `tools/l2_report.py` `182dadc226eca5e68d16c968177acefae8e87ab29c39f51db33ee55eb61d6a9b`; `tools/latency_sampler.py` `b1559907d6339df58392c8b3e602194baa5526ced9c860b61eb4af51e79f23be`. Evidence: `.codex_tmp/l2_20261113/`, final run `bench_p128_final_20261113_195746/`, aggregate `l2_aggregate_p128_final.json` SHA256 `37694d96efe7e251b33fdacb6d716be4b6cd27af377fcd14977f9242261d99a6`, comparison `l2_final_comparison.json` SHA256 `d0d0bf71591b2ecd7691eab7c02d2806ec690186c4efd72a68f6164699e58c44`, transform proof `transform_verify.txt`, same-run dumps `dump_transform2_20261113_195344/`.
- **Regression evidence**: full pytest outside the sandbox passed with **53 passed, 38 skipped, 9 subtests passed**. Inside the restricted sandbox, two socket/subprocess tests failed with `PermissionError(1)`/read-only-filesystem effects; this is an environment limitation, not a code regression. `git diff --check` RC=0 after the documentation update.
- **Recommendation**: P128 is the best validated offline candidate; T128 remains the fallback, and A remains the original baseline. This is **not** production acceptance: controlled live USB/HDMI validation, a fresh 30-minute soak, resolution-change/hotplug checks, and glass-to-glass measurement are still pending. Do not switch the production kiosk automatically. Keep `K3 ACCEPTED_WITH_LIMITATION`; the `0xf` and glass-to-glass issues remain open.
- **Deployment/rollback if approved later**: back up the current `~/mobile_vt/build/d3/d3_probe`, replace it with the validated P128 binary, then `sudo systemctl restart vt13-kiosk.service`. Rollback is to restore the backed-up production binary and restart the service. The original `9d610808...` worker remains the selectable rollback path.

## 2026-11-13 14:35 HKT — atomic KMS optimization and delay baseline documented; 49.7 FPS; program-side p50 79.7 ms / p95 109.2 ms; rotation still visually unconfirmed

- **Scope**: CM311 deployed worker observation plus PC-side documentation/evidence update. No reboot, no `meson_vdec` reload, no golden-data overwrite.
- **Implementation**: `tools/d3_probe.c` enables `DRM_CLIENT_CAP_ATOMIC`, submits overlay-plane updates with `DRM_IOCTL_MODE_ATOMIC` (`NONBLOCK | PAGE_FLIP_EVENT`), tracks `DRM_EVENT_FLIP_COMPLETE`, and waits for the matching flip before reusing a scratch framebuffer. If atomic setup/property validation fails, it falls back to legacy `SETPLANE`; pending flips are drained during cleanup.
- **Deployed state**: worker `build/d3/d3_probe 9d610808d309d0fa6a2fb19f15558ffad2505b6410f7ca3600779b7b35055d01`; source `tools/d3_probe.c fa9e5d07d4c7b81d36df2ed81f5275d2631206c084f4e59b24f18789621263a2`; service `MainPID=24013`, worker PID 24015, `NRestarts=0`, active/running since 14:03:51 HKT. Rotation remains software 180° before KMS because plane 42 has no DRM `rotation` property.
- **Offline smoke**: 1920x1080 60 fps sample `staging/vt13_idr_03.h265`: 60 decoded frames, RC=0, 50.74 FPS, `corrupt=0`; atomic submit about 0.10 ms.
- **34-second steady window**: 49.7 FPS, `corrupt=0`, `sessions=1`; no RECOVER, atomic fallback, flip-wait timeout, or `0xf` in the sampled window. Local stage medians: staging copy 16.545 ms (p95 17.442), 180° rotation 2.855 ms (p95 3.026), KMS atomic submit 0.10 ms (p95 0.1135), flip wait 0.00 ms.
- **Measured total**: sender AU timestamp → program-side present p50 **79.7 ms**, p95 **109.2 ms**, max observed **187.5 ms**. Subtracting measured local stages yields upstream wireless/USB/AU receive + decoder queue p50 **60.2 ms**, p95 **88.6 ms** (derived, not split per frame). This is **not glass-to-glass**: HDMI scanout/panel response is not included.
- **Before/after**: rotation-only worker was ~29.7 FPS with `setplane_avg_ms≈12.5`; atomic worker is ~49.7 FPS with `setplane_avg_ms≈0.10`. The largest remaining local cost is the 16.5 ms staging copy.
- **Direction**: 180° rotation remains **IMPLEMENTED / VISUALLY UNCONFIRMED**. The user must confirm upright and unmirrored; if still wrong, distinguish 180° from vertical-only or horizontal-only flip.
- **Evidence**: `.codex_tmp/emmc_deploy_20261112/g7_atomic_20261113_1340/`; `SHA256SUMS` **20/20 OK** locally and remotely, manifest SHA256 `268c1c5b8630cce1f77fabac13f4e9ab20075fc68f23dcc0fb3589a2b3a8921f`. Plot: `delay_flow.png`; summary: `delay_flow_summary.json`.
- **Verification commands/RC**: local `rsync -avc` RC=0; local and remote `sha256sum -c SHA256SUMS` RC=0 (20/20); remote `systemctl show vt13-kiosk.service` RC=0; `git diff --check` RC=0; PC `python3 -m pytest -q` RC=0 with 53 passed, 38 skipped, 9 subtests passed in 2.00s.
- **Git**: HEAD `fdd74b3`; `tools/d3_probe.c` remains the only modified tracked file and is not yet committed. Docs/manifest are being updated in this step.
- **Next**: visual confirmation of rotation; 60 s+ then 30-minute soak on `9d610808` + ca46; glass-to-glass measurement; formal G8 cold-boot/soft-reboot matrix.

## 2026-11-13 12:37 HKT — VT 180° display rotation deployed as software fallback; visual confirmation pending; ~29.7 FPS

- **User report**: the live VT view is rotated 180° from the intended orientation.
- **Why a software fallback**: a read-only DRM probe showed that meson overlay plane 42 has no `rotation` property; `drm_set_rotation()` returns `plane 42 has no rotation property`. The worker therefore cannot use standard KMS plane rotation.
- **Implementation**: `tools/d3_probe.c` now allocates four 1920x1080 NV12 scratch dumb framebuffers and rotates the decoded NV12 frame by reversing Y rows and UV pairs into those buffers. The first staging version used glibc row copies; the deployed version copies the decoded dmabuf into a 64-byte-aligned cached staging buffer with a 128-byte-unrolled NEON loop plus prefetch, then performs the 180° rotation from staging. No HEVC bitstream, decoder, kernel, or module change was made. `vt13_video/worker_client.py` reads `VT13_WORKER_ROTATION`; `deploy/vt13-kiosk.service` sets it to `180`.
- **Deployment**: current worker is `build/d3/d3_probe d1257c49a45c2858346a517dcf1c445a2187962bce3e62b64154d7320c08a715`; source is `tools/d3_probe.c 6838cd3e1b22ceae831ea99f46252907b5a6525792e19ede5af9c6f732ae2e95`; `vt13_video/worker_client.py` is `518628638a5fa0da0914a5ac38e0c7255e7b801817eb7314a915f149da887279`; installed service hash is `adcd98ff4fa0952e40c92f55b4f6e4c665c67ab06eef150c84764e1d6217ec57`. Service `MainPID=15994`, worker PID 15996, `NRestarts=0`, active/running since 12:35:09 HKT. Journal shows `plane 42 has no rotation property`, `using software 180-degree rotation fallback`, `rotation staging`, and DRM shows overlay plane 42 scanning scratch `fb=49`, `imported=no`.
- **Measured result**: a 30-second stable observation reported about **29.7 FPS**, `corrupt=0`, 0 errors, 0 recoveries, `sessions=2`, `backlog_max≈6`; `stage_copy_avg_ms≈17.2–17.7`, `rot_copy_avg_ms≈2.8–2.9`, `setplane_avg_ms≈12.2–12.7`. The earlier direct NEON rotation was about 24.8 FPS; the first staging version was about 28.4 FPS. The board-side microbenchmark measured glibc dumb→malloc copy at 25–26 ms versus the selected NEON path at about 17 ms.
- **Limitation**: the orientation has **not** been visually confirmed by the user; do not claim it is fixed yet. The change also reduces the previous unrotated ~60 FPS path to ~29.7 FPS. The remaining bottlenecks are uncached V4L2 dmabuf reads and blocking `SETPLANE`/vblank waits; possible next steps are non-blocking atomic plane commits, further copy tuning, or accepting the current rate if the user prioritizes correct orientation.
- **PC regression**: `python3 -m pytest -q` completed with **53 passed, 38 skipped, 9 subtests passed**; `git diff --check` returned RC=0. The target-side build also completed with `-O2 -Wall -Wextra`, no warnings.
- **G6 context**: the user reported that HDMI has output and that physical hotplug, cold start, and start-from-reboot all work. That satisfies the previously pending G6 visual/hotplug observations, but formal G8 still requires three independent cold boots plus one supervised soft reboot, so G8 is not complete.
- **Safety/state**: no reboot, no `meson_vdec` reload, no golden-data overwrite, and no Git commit. HEAD remains `8bd2eac`; the rotation and earlier G5/G6 changes are intentionally uncommitted.
- **Evidence**: `.codex_tmp/emmc_deploy_20261112/g7_rotation_stage_20261113_1226/`; `SHA256SUMS` **29/29 OK** locally and remotely, manifest SHA256 `e337cce734d09715d8642ab54e1534dc834f8d19d56619210bed1c8ed70be69a`. Key files include `deploy.stage2.log`, `post_stage2_observe.log`, `stage_copy_bench2.log`, `deployed_hashes.txt`, and `pc_verification.txt`.
- **Next action**: ask the user to visually confirm whether the picture is now upright and unmirrored. If not, distinguish 180° rotation from vertical-only or horizontal-only flip before changing the algorithm. If orientation is correct, record it as visually confirmed and decide whether the ~29.7 FPS rate is acceptable or whether to pursue non-blocking KMS commits.

## 2026-11-13 02:39 HKT — G6 HDMI black-screen diagnostic: decoded YUV is non-black; temporary 1080p60 KMS test, visual confirmation pending

- **User report**: HDMI showed a black screen, so G6 cannot be treated as visual PASS.
- **Decode path**: while black, the service was still streaming at about 60 FPS with `corrupt=0`; this only proved transport/decoder API success, not pixels.
- **KMS finding**: the worker had no `--mode` argument and inherited the console CRTC mode `1920x1080i`. DRM state showed the overlay plane active with a 1920x1080 NV12 framebuffer, primary plane disabled, and the interlaced CRTC. This made interlaced KMS presentation the prime suspect.
- **Temporary diagnostic**: set runtime-only manager environment `VT13_WORKER_MODE=1920x1080@60` and `VT13_WORKER_DUMP_FIRST=.../first`, then restarted `vt13-kiosk.service`. No source, config, or service-unit file was changed. New service `MainPID=13894`, worker PID 14060, `NRestarts=0`; worker args now include `--mode 1920x1080@60`. DRM now reports progressive `1920x1080` at 60 Hz, overlay plane active with fb=64, primary plane disabled.
- **Pixel evidence**: the worker dumped the first frames as 1920x1080 NV12. `Y_min=0`, `Y_max=255`, `Y_mean≈109`, so the decoded frames are not black; the black screen is a KMS presentation problem rather than a decoder producing all-zero frames.
- **Evidence**: `.codex_tmp/emmc_deploy_20261112/g6_hdmi_black_20261113_023851/diagnostic.txt` SHA256 `bd7893fe700936a62ad103b85d49fd78cf415621fd43903ef551fd73e11d54eb`; remote `sha256sum -c` OK; dumped YUV frames are in the remote `first/` directory.
- **Status**: the 1080p60 switch is a diagnostic, not yet an accepted fix. User must visually confirm whether HDMI now shows a sustained correct picture. If still black, next checks are primary/overlay composition and alternate modes. G6 remains `PASS_WITH_LIMITATION`; G7/G8 not started. No commit.

## 2026-11-13 02:12 HKT — G6 post-check: service still stable, no restart; HDMI visual and physical hotplug still pending

- **Scope**: read-only verification after the user said "approved and continue". No reboot, module reload, service restart, source/config change, or golden-data overwrite. Only the post-check evidence file was copied to CM311 and hash-verified.
- **Boot/storage**: CM311 remains at `10.42.0.253`. `uptime -s` and PID 1 `lstart` both confirm boot at `2026-11-12 23:40:55 HKT`; `who -b` showed 21:59 due to a wtmp display discrepancy, so the uptime/PID-1 values are authoritative. `/`=`/dev/mmcblk2p2` ext4 and `/boot`=`/dev/mmcblk2p1` vfat; `lsblk` shows no USB block disk. DJI `2ca3:1020` is present and SG Flash `23a9:ef18` is absent.
- **Service/display**: `vt13-kiosk.service` is `active/running`, `MainPID=2935`, worker PID 2937, `NRestarts=0`, active since 01:47:23. `HDMI-A-1` is `connected/enabled`.
- **Latest counters**: at 02:12:20 the service reported 78,937 frames, 60.0 FPS, 38 errors / 1 recovery, `corrupt=0`, `backlog_max=0`, sessions=5. The worker reported `aus_frames=78,849` and `age_p50≈37 ms`. These error/recovery counters are cumulative since the 01:47 restart and are dominated by the manual USB bind/ACL interval plus two content-dependent `0xf` events; they do not indicate a current link outage.
- **Evidence**: `.codex_tmp/emmc_deploy_20261112/g6_postcheck_20261113_0211/g6_postcheck.txt` SHA256 `49919c75639340fe65abf68d6ccc2edd25480ab555623126a2c93f03a5054bb6`; remote copy verified by `sha256sum -c SHA256SUMS`. Local/remote match.
- **Conclusion**: G6 remains **PASS_WITH_LIMITATION**, not full visual PASS. User visual confirmation of a sustained correct HDMI picture is still required; a physical DJI receiver unplug/replug remains the stronger optional hotplug test. Do not start G7/G8 until that confirmation is recorded.

## 2026-11-13 02:03 HKT — G6 eMMC-only layered acceptance: PASS_WITH_LIMITATION; HDMI visual and physical hotplug pending; G7/G8 not started

- **Authorization and scope**: after the user physically removed SG USB and powered on, the user approved G6 and said to continue. No reboot, module reload, package install, or golden-data overwrite occurred. The only active operations were one `vt13-kiosk.service` restart and one kernel USB `unbind/bind` hotplug simulation.
- **Identity/storage/boot**: CM311 is at dynamic DHCP `10.42.0.253`; boot time `2026-11-12 23:40:55 HKT`. `/`=`/dev/mmcblk2p2` ext4 UUID `61e6bfac-70ad-4d87-92db-a7399341722c`; `/boot`=`/dev/mmcblk2p1` vfat UUID `EE59-E094`; `lsblk` shows only eMMC and `zram0`, no USB block disk; SG Flash `23a9:ef18` absent. fstab/uEnv/root UUID correct. Boot files: `zImage 4b7b8882…`, `uInitrd 61bf8725…`, `u-boot-s905x-s912.bin 207cdbe1…`, DTB `6bdcf618…`.
- **Runtime/module/service hashes**: ca46 module `ca467983…` (5,550,816 B, vermagic `6.18.59-ophub SMP preempt mod_unload aarch64`), firmware `gxl_hevc.bin f1336295…`, worker `eb1dbb67…` (libc-only aarch64), config `d4d155f2…`, service `3ed77408…`, 15 `vt13_video/*.py` hashes match local. `billieguo` is in `video`, `render`, and `plugdev`; system Python 3.12.3/PyAV 11.0.0 and FFmpeg shared libs are present. `/dev/video0` is `meson-video-decoder` and exposes HEVC output.
- **HDMI/KMS**: `HDMI-A-1 status=connected`, `enabled=enabled`, modes include 1920x1080; `card0/card1/renderD128` exist. The worker presents via KMS; **actual HDMI pixels are not agent-verified** and require user visual confirmation after this cold boot.
- **Cold-boot live state**: initial service `MainPID=433`, worker 907, `NRestarts=0`. At 01:29-01:33: 122 errors / 42 recoveries, 362,091 AU, `corrupt=0`, ~60 FPS. The `0xf` recovery burst was concentrated at 23:59:13-23:59:30; isolated recovery begins followed at 00:16:03, 00:40:19, 00:57:16, 01:01:47, 01:08:43, 01:13:14, 01:13:28, and 01:16:51. No new recovery was observed between 01:16:51 and the manual restart; counters stayed 122/42.
- **Service restart**: `sudo -S systemctl restart vt13-kiosk.service` RC=0 at 01:47:23; new `MainPID=2935`, worker 2937, `NRestarts=0`; SSH stayed reachable. At 01:51:24 the clean session reached 14,101 frames, 60 FPS, 0 errors / 0 recoveries, `corrupt=0`, `backlog_max=0`.
- **USB recovery simulation**: at 01:52:12 the DJI device was unbound via `/sys/bus/usb/drivers/usb/unbind`. This kernel has no `rebind` attribute, so `bind` was used; the manual bind did not reapply the libusb ACL, and `udevadm trigger` restored `/dev/bus/usb/001/004` permissions. USB reopened at 01:55:06, service remained active with `NRestarts=0`, video resumed at ~60 FPS and `corrupt=0`. The service logged 37 USB-open retry messages during the ACL gap. This is a kernel simulation, not a physical connector pull.
- **Residual `0xf`**: content-dependent `0xf` occurred at 01:51:48 and 01:56:45 after the restart and auto-recovered; at 01:58:38 the service reported 38 errors / 1 recovery. The worker `fps` field is a cumulative average since process start, so it read 44.6 after the USB-down interval; `aus_frames` still increased at about 60/s. dmesg retained `lcu_0xf=2`, `lcu_0x8=0`, `aborting=2`, `missing=1`, `unexpected=2`; the ring buffer is flooded by `HEVC_BOUNDARY`, so service counters are more complete.
- **Evidence**: `.codex_tmp/emmc_deploy_20261112/g6_validation_20261113_0110/` contains `G6_FINAL_REPORT.md`, `g6_layer1_2.txt`, `g6_layer3_6.txt`, `g6_errors.txt`, `g6_service_restart.txt`, `g6_service_restart_steady.txt`, `g6_usb_rebind.txt`, `g6_usb_bind_fix.txt`, `g6_final_state.txt`, and `SHA256SUMS` (9/9 OK locally and on CM311). Remote copy: 10 files SHA256 all match; cold-boot evidence copy 3 files all match. Cold-boot precheck SHA256 `9c0ef416…`.
- **Conclusion**: G6 technical path is **PASS_WITH_LIMITATION**, not full visual PASS. HDMI actual picture is pending; physical USB hotplug is still recommended. Residual `0xf`, startup burst, historical soft-reboot hang, glass-to-glass latency, and a fresh 30-minute soak remain open. Do not start G7/G8 until the user confirms HDMI (and optionally physical hotplug). No commit.
- **Next**: user visually confirms HDMI; if desired, physically unplug/replug the DJI receiver and report the result so we can verify `NRestarts=0`, USB re-enumeration and video recovery.

## 2026-11-13 01:02 HKT — eMMC-only cold boot precondition PASS; G6 not started

- **User action and boot proof**: the SG USB was physically removed and the board was powered on. Read-only SSH evidence shows boot time `2026-11-12 23:40:55 HKT`, later than the G5 `poweroff` at `23:19:57 HKT`. Uptime was 4,915 s at the 01:02 check.
- **Network discovery**: the old `10.42.0.11` address is no longer assigned; `nmap -sn 10.42.0.0/24` found only `10.42.0.1` and `10.42.0.253`. The PC profile `cm311-local` is a shared DHCP connection (`10.42.0.10-254`), and CM311 is currently at `10.42.0.253`. This is a dynamic lease, not a static guarantee.
- **eMMC-only proof**: `/` is `/dev/mmcblk2p2` ext4 UUID `61e6bfac-70ad-4d87-92db-a7399341722c`; `/boot` is `/dev/mmcblk2p1` vfat UUID `EE59-E094`. `lsblk` shows only `mmcblk2`, its two partitions, `mmcblk2boot0/1`, and `zram0`; there is no USB block disk. `findmnt` and `/proc/cmdline` both reference the eMMC root UUID.
- **SG USB removal**: `lsusb -d 23a9:ef18` returned no match (`sg_flash_present=no`). The DJI receiver `2ca3:1020` is present.
- **System state**: `systemctl --failed` reported 0 units; `vt13-kiosk.service` is enabled and active with `MainPID=433`, `NRestarts=0`; `/etc/modules-load.d/vt13-vdec.conf` contains `meson_vdec`, and `meson_vdec` is loaded (refcount 2). Root has about 3.4 GiB free and 354,636 free inodes; `/boot` has about 352 MiB free.
- **Journal limitation**: `journalctl --list-boots` shows only the current boot because the kiosk journald namespace is volatile; this is expected and does not invalidate the eMMC root/boot proof.
- **Evidence**: `.codex_tmp/emmc_deploy_20261112/g6_coldboot_20261113_0055/g6_coldboot_precheck.txt` SHA256 `9c0ef4168c13d4ae03618b18fbb075c9b4ae2520d9ebe2a5cad4fa2a1a32bbbe`; summary `G6_COLDBOOT_PRECHECK.md`.
- **Scope**: this is a **pre-G6 cold-boot confirmation only**. HDMI/KMS visual output, exact ca46 hash/vermagic recheck after this cold boot, native worker/config hashes, service journal/errors, USB access, HEVC hardware decode, and stable live display remain pending. No remote file was modified, no reboot was issued, and no wireless link was started.
- **Next**: wait for separate G6 authorization. Do not start G7/G8 until G6 passes. `K3 ACCEPTED_WITH_LIMITATION` remains unchanged.

## 2026-11-12 23:19 HKT — G5 PASS: eMMC installed/validated; evidence saved and verified; poweroff issued; G6 pending

- **Result**: G5 **PASS**. The reviewed installer ran with selections `127` and `1` (ext4), returned RC=0, and logged `Detected eMMC device: [ /dev/mmcblk2 ]`, `Successfully repartitioned eMMC with ampart.`, and `Installation completed successfully`.
- **Final layout**: `/dev/mmcblk2` `7,474,249,728 B`; `mmcblk2p1` vfat `BOOT_EMMC`, START=122,683,392 B (117 MiB), SIZE=535,822,336 B; `mmcblk2p2` ext4 `ROOTFS_EMMC`, START=659,554,304 B (629 MiB), SIZE=6,814,695,424 B, UUID `61e6bfac-70ad-4d87-92db-a7399341722c`. Boot partition starts beyond the 4 MiB bootloader reservation.
- **Validation**: the reviewed wrapper's post-install check initially false-failed because it treated `lsblk START` sectors as bytes. A temporary validation-only copy (`f0d71787…`) corrected that conversion and replaced incompatible `df -i --output=iavail` with `df -i | awk`; the original reviewed wrapper was not modified. Validation returned `G5_VALIDATED` with root free ~3.64 GB, 354,676 free inodes, correct boot files/uEnv/fstab/root UUID, ca46 module, firmware, worker, system Python/PyAV closure, non-root service plus enable symlink, udev rule, journald config, KMS helper, and `meson_vdec` modules-load.
- **Evidence and verification**: local `.codex_tmp/emmc_deploy_20261112/g5_validation_20261112_231207/` contains `g5-result.env` (`9ebd188d…`), `armbian-install.log` (`80eb6452…`), `postinstall-evidence.txt` (`0e753462…`), `mybox-bootloader.img` (`f61b153c…`, 4,194,304 B), and `mbr-first512.bin` (`d110adfe…`, 512 B); `SHA256SUMS` is 5/5 OK. Remote copies in `~/mobile_vt/.codex_tmp/emmc_deploy_20261112/g5/run_20261112_231207/` have identical hashes.
- **SG USB preservation**: still boots from `/dev/sda2` ext4 and `/dev/sda1` vfat; source `/boot` seven reviewed files and worker/config/KMS/service hashes remain unchanged. PC G2 backup `28/28 OK`. Expected SG USB side effects only: machine-id regeneration, `/ddbr` staging, and `/usr/lib/u-boot/mybox-bootloader.img` creation.
- **Power state**: `sudo sync && sudo poweroff` issued at 23:19:57 HKT; SSH closed; ping to 10.42.0.11 received 0/2 replies. No reboot.
- **Next**: G6 is **not started**. Before the first eMMC-only cold boot, physically remove the SG USB. Then verify `/`=`/dev/mmcblk2p2`, `/boot`=`/dev/mmcblk2p1`, SSH, HDMI/KMS, ca46 autoload, native worker, non-root `vt13-kiosk.service` autostart, DJI USB reception, HEVC hardware decode, and stable live display. Do not enter G7/G8 until G6 passes. `K3 ACCEPTED_WITH_LIMITATION` remains unchanged.

## 2026-11-12 22:41 HKT — G5 installer completed eMMC write; wrapper post-validation false-failed; no poweroff

- **Execution**: Ubuntu PC ran `bash deploy/g5-run-from-pc.sh`; sudo password was entered only at the TTY prompt. Installer selections were exactly `127` and `1` (ext4). The installer completed with RC=0 and logged `Successfully repartitioned eMMC with ampart.` and `Installation completed successfully`.
- **Actual eMMC state**: `/dev/mmcblk2` remains `7,474,249,728 B`; `mmcblk2p1` is vfat `BOOT_EMMC`, START=239616 sectors (=122,683,392 B = 117 MiB), SIZE=535,822,336 B; `mmcblk2p2` is ext4 `ROOTFS_EMMC`, START=1,288,192 sectors (=659,554,304 B = 629 MiB), SIZE=6,814,695,424 B. The boot partition starts beyond the 4 MiB bootloader reservation.
- **False failure**: the wrapper reported `G5_ERROR: unexpected eMMC layout: p1_start=239616 p2_start=1288192`. Root cause is a reviewed-wrapper unit bug: `deploy/g5-install-wrapper.sh` reads `lsblk -bno START` values (512-byte sectors) and compares them against byte constants in `validate_install()` (around lines 221–235). The layout itself matches the approved ampart geometry.
- **Not finalized**: wrapper exited before mounting/validating the target. `g5-result.env` is `STATUS=FAILED`; `postinstall-evidence.txt` was not created; the PC runner did not copy the install log, evidence, bootloader image, or MBR, and did not issue the final `sync` + `poweroff`.
- **Current boot/recovery state**: SG USB remains the boot source (`/`=`/dev/sda2`, `/boot`=`/dev/sda1`). The runner trap restarted `vt13-kiosk.service`; it is active with MainPID=35832 and NRestarts=0. No reboot or poweroff occurred.
- **Evidence**: local `.codex_tmp/emmc_deploy_20261112/g5_pc_20261112_223331/install-session.log` (8,977 B) and `restart-kiosk-session.log`; remote `~/mobile_vt/.codex_tmp/emmc_deploy_20261112/g5/run_20261112_223446/armbian-install.log` and `g5-result.env`. The install log contains the successful installer tail; no post-install evidence file exists yet.
- **Next**: do not rerun the installer. Perform read-only eMMC validation with corrected sector-to-byte conversion, export the installer log, `/usr/lib/u-boot/mybox-bootloader.img`, and post-install MBR first 512 B, transfer to the PC, verify SHA256/sizes, then `sync` + `poweroff`. If strict wrapper `VALIDATED` semantics are required, fix only the START unit bug and reapprove the wrapper hash; the eMMC does not need to be rewritten.

## 2026-11-12 22:12 HKT — G5 authorized; final read-only preflight PASS; install not yet started

- **Task**: execute the reviewed G5 procedure only after revalidating all safety gates. The user explicitly authorized G5; this step was the safe preflight before any eMMC write.
- **Command/host**: Ubuntu PC, `bash deploy/g5-run-from-pc.sh --preflight-only`; interactive SSH to CM311, sudo password entered only at the TTY prompt. Result: `G5_PREFLIGHT_OK`, `G5_PREFLIGHT_ONLY_COMPLETE`, RC=0. No eMMC write, service stop, reboot, module reload, or USB/HDMI/wireless run.
- **Safety checks passed**: target `/dev/mmcblk2` is `7,474,249,728 B`; source `/` is `/dev/sda2` ext4 and `/boot` is `/dev/sda1` vfat; target is unmounted; user-area first 4 MiB, `mmcblk2boot0`, and `mmcblk2boot1` all hash to `f61b153c1ec98ce54ee770be43198af2d2ac60642cc6004500cfbd3b87490262`; source `/boot` seven artifacts, KMS helper, and installer/patch/exclude/service all match approved SHA256 values.
- **Backups/recovery**: PC G2 backup `/home/billieguo/cm311-deployment/backups/cm311-sg-20261112_121131` rechecked with `sha256sum -c SHA256SUMS`: **28/28 OK**. SG USB remains `/dev/sda` with `/boot` and root; kiosk remains active (MainPID=447, NRestarts=0). `picocom` is installed; no `/dev/ttyUSB*` was enumerated on the PC at check time, so physical UART availability is recorded from the user's authorization rather than a live device node.
- **BOOT_EMMC start**: the target currently has no partition table. The wrapper will fail-close after install unless p1 starts at `122683392` B (ampart, 117 MiB) or `134217728` B (fallback, 128 MiB), both beyond the reserved 4 MiB bootloader region.
- **Evidence**: local `.codex_tmp/emmc_deploy_20261112/g5_pc_20261112_221209/`; `preflight-session.log` SHA256 `64c6c9f24a93077ffcfb2aabc460e96638155e6a2f769dfafac7d06345696b3a`, `preflight.txt` SHA256 `b134db8ea3c029aaac09e72004973b459ac6673c982af65633663ef6e08b21cf`, `g5-result.env` SHA256 `773e939ede333e22df4ffc783dc9f3daf62cc8cb3ab7e793e087403210224ab0`; remote run directory `~/mobile_vt/.codex_tmp/emmc_deploy_20261112/g5/run_20261112_221223/`.
- **Files changed**: `AGENTS.md` (item 118), `docs/REMOTE_MACHINE_USAGE.md` (G5 authorization/preflight section), `docs/INTERSESSION_TRANSFER.md` (this section). No remote runtime files changed by preflight; only the wrapper staging copy and G5 run/preflight files were written under the remote `.codex_tmp` staging tree.
- **Next**: run the reviewed installer with selections `127`, `1` (ext4), then validate target layout/boot/rootfs/module/firmware/worker/service, transfer logs and bootloader/MBR backups, verify SHA256/sizes, `sync`, `poweroff`, and stop before G6.

## 2026-11-12 21:33 HKT — G5 final read-only confirmation passed; G5 NOT started; no eMMC write

- **Task**: answer the three pre-G5 questions without re-running G0–G4 or redoing the G2 backup: verify the real origin/SHA256/applicability of `/usr/lib/u-boot/mybox-bootloader.img`; strengthen the G5 wrapper to validate the installed eMMC before saving logs and powering off; and confirm the patched installer's target lock, selective copy, service installation locations, and source SG USB side effects.
- **Bootloader provenance**: the installer's `create_partition()` performs `dd if=/dev/mmcblk2 of=/usr/lib/u-boot/mybox-bootloader.img bs=1M count=4 conv=fsync` before partitioning. It is therefore a **4 MiB backup of this same CM311 unit's eMMC user-area vendor bootloader**, not a generic U-Boot and not a full-disk image. The file did not exist before G5; `/etc/ophub-release` has `MAINLINE_UBOOT=''` and `BOOTLOADER_IMG=''`, so the installer chooses the mybox vendor-writeback branch. Current user-area first 4 MiB, `mmcblk2boot0`, and `mmcblk2boot1` all hash to `f61b153c1ec98ce54ee770be43198af2d2ac60642cc6004500cfbd3b87490262`; the user area has `@AML`/`gxl` at `0x200`.
- **Recovery semantics**: restore only bootloader bytes 0–443 and 512–4194303 to preserve the new G5 MBR table, matching the installer:
  `dd if=mybox-bootloader.img of=/dev/mmcblk2 bs=1 count=444 conv=fsync`
  `dd if=mybox-bootloader.img of=/dev/mmcblk2 bs=512 skip=1 seek=1 count=8191 conv=fsync`
  Do **not** treat `dd bs=1M count=4` as an unverified universal recovery command; it also overwrites the backup-era MBR/partition table. The wrapper exports both `mybox-bootloader.img` and the post-install `mbr-first512.bin` to the PC; normal bootloader recovery does not need to rewrite the new MBR unless that table itself is lost.
- **Patched installer review**: target selection uses `lsblk` boot0 detection or excludes the current root device; the only current eMMC candidate is `/dev/mmcblk2`. The wrapper additionally fail-closes on exactly one eMMC disk, exact `7,474,249,728 B`, source `/dev/sda2`/`/dev/sda1`, target unmounted, and 4 MiB boot0/boot1 with `force_ro=1`. Selective root copy remains `COPY_SRC="etc home opt root selinux srv usr var"` with `/ddbr/emmc-exclude.txt`; `/boot` is written separately as a 512 MiB `BOOT_EMMC` FAT32 partition. The reviewed service is installed to target `/etc/systemd/system/vt13-kiosk.service` and `/home/billieguo/mobile_vt/deploy/vt13-kiosk.service`; the existing `multi-user.target.wants` symlink is preserved by the tar copy. The wrapper validates the unit, `ExecStart=/usr/bin/python3 ...`, `VT13_ASYNC_USB=0`, `User=billieguo`, `Restart=always`, `WantedBy=multi-user.target`, and the enable symlink.
- **Source SG USB side effects**: expected writes are `/etc/machine-id` and `/var/lib/dbus/machine-id` regeneration, `/ddbr/install` recreation, `/usr/lib/u-boot/mybox-bootloader.img` creation, and the wrapper's four small `/ddbr` staging files. Source `/boot` content is not modified. All installer dependency commands (`tar`, `hexdump`, `mkfs.vfat`, `mkfs.ext4`, `mkfs.btrfs`, `parted`, `losetup`, `fdisk`, `lsblk`, `dbus-uuidgen`, etc.) are present, so the expected path is `Dependency check completed` rather than apt installation.
- **Wrapper/runner changes**: new `deploy/g5-install-wrapper.sh` SHA256 `1bef8ba4e410d7b54c6c88548de6d6273ad56eff2d0268fec2cbe82d9d34257d`; new `deploy/g5-run-from-pc.sh` SHA256 `c3ef51f004f44b6ed257d83a7481b4aff32a9335abaae2a18d2c6ba727ef9af8`; both `bash -n` RC=0. The wrapper adds source `/boot` hash checks, KMS helper checks (`a071cfed…`, `fbd8c439…`), required-command checks, target KMS executable checks, post-install source `/boot`/KMS/`/ddbr` rechecks, bootloader/MBR export and size checks, and only reports `VALIDATED` after target partition/boot/rootfs/service validation. The PC runner verifies local and remote wrapper hashes, fetches `armbian-install.log`, `postinstall-evidence.txt`, `mybox-bootloader.img`, and `mbr-first512.bin`, verifies all SHA256 values/sizes, and only then issues `sync` + `poweroff`.
- **Final read-only preflight**: local `.codex_tmp/emmc_deploy_20261112/g5_pc_20261112_213308/`; `preflight.txt` SHA256 `41f62d3beadc5482428b9c969a94cf425742f0a20b019da733c84f3d0df0ba51`, `g5-result.env` SHA256 `8921c5a88163fdad30e09e74c69bf97cdf05ee1e3d4b25ef4d6e2feafd8157d0`, `preflight-session.log` SHA256 `2df2bae72162f0871844e2e16ec7c817882be94040a776c20a6e68755242ec40`. Remote `~/mobile_vt/.codex_tmp/emmc_deploy_20261112/g5/run_20261112_213343/preflight.txt` and `g5-result.env` match the local hashes; remote wrapper hash is `1bef8ba4…`; `/ddbr` still absent, eMMC unmounted, `vt13-kiosk.service` active. No eMMC write, service stop, reboot, module reload, or live USB/HDMI/wireless run occurred.
- **Files changed**: `AGENTS.md` (item 116), `docs/REMOTE_MACHINE_USAGE.md` (G5 final confirmation), `docs/INTERSESSION_TRANSFER.md` (this entry), `plans/CM311_eMMC_Deployment_Runbook.md` (final G5 command), plus new `deploy/g5-install-wrapper.sh` and `deploy/g5-run-from-pc.sh`. No commit.
- **Final G5 command (still awaiting explicit approval)**:
  ```bash
  cd /home/billieguo/billie_guo/src/rm/mobile_vt
  bash deploy/g5-run-from-pc.sh
  ```
  Interactive inputs: CM311 sudo password; then `127` at `Please Input ID:`; then `1` at `Please Input ID (1/2):` for ext4 (do not choose `2`/btrfs). The runner uploads and hash-verifies the wrapper, executes the reviewed installer, validates the target, saves the complete install log and evidence to the PC, then runs `sync` and `poweroff` only after successful validation.
- **Next**: obtain explicit G5 execution approval, run the command above, then for G6 first boot **unplug the SG USB**, cold boot, and verify `/` is `/dev/mmcblk2p2` and `/boot` is `/dev/mmcblk2p1`. Do not treat a boot with the SG USB still inserted as eMMC success.

## 2026-11-12 19:16 HKT — Final minimal eMMC payload audited; G5 awaiting approval; no eMMC write

- **Task**: revalidate the selective eMMC payload against the new dedicated-appliance requirements, update the G3/G4 conclusions, and fix the final G5 installation plan. No eMMC write was performed.
- **Final payload**: supersedes the earlier `3,685,431,296 B` / 90,723-member plan. Root tar stream `2,853,621,760 B`, 61,468 members; installer post-copy additions `kms_render` + source 88,621 B, service replacement +250 B, and `/etc/modules-load.d/vt13-vdec.conf` 11 B; **final root file payload `2,853,710,642 B` (2.6577 GiB)**, `831,720,654 B` (793.2 MiB) smaller. The payload excludes `/boot`, which the installer writes to a separate fixed 512 MiB FAT32 `BOOT_EMMC`.
- **Runtime decision changed**: target uses system `/usr/bin/python3` and system dist-packages (`cv2`, `numpy`, `yaml`, `usb`, system PyAV 11.0.0) plus system FFmpeg shared libraries under `/usr/lib/aarch64-linux-gnu`; `.venv-v4l2` and the custom `ffmpeg-6.1.1-v4l2-shared/install` are excluded. The reviewed service uses `ExecStart=/usr/bin/python3 -u -m vt13_video stream ...`; the native `build/d3/d3_probe` worker has only a libc dependency and does not import PyAV. A static import/config check on CM311 reported `backend=worker`, `codec=hevc_v4l2m2m`, `av=False`, but the system-Python service has **not yet run as a service on eMMC**.
- **Include/exclude**: retained Armbian OS/kernel/DTB/firmware, ca46 `meson-vdec.ko`, `gxl_hevc.bin`, native worker, `vt13_video` source/config/tests, systemd service, volatile journald namespace, actual installed udev rule, DRM/KMS runtime, system Python/dist-packages, and system FFmpeg shared libraries. Excluded `.venv-v4l2`, custom FFmpeg shared tree, `captures`, `live_runs`, both `.codex_tmp` trees, kernel/FFmpeg source/build trees, toolchains, old backups, apt lists/cache, historical logs, `/usr/share/doc|man|locale`, `/usr/src`, and unused build artifacts. Authoritative manifest: `deploy/PAYLOAD_MANIFEST.md`.
- **Capacity**: ampart-success root `6,814,695,424 B`, free before ext4 metadata `3,960,984,782 B` (3.6890 GiB); ampart-fallback root `6,048,186,368 B`, free before metadata `3,194,475,726 B` (2.9751 GiB). Both exceed 1 GiB; G6 must measure `df -hT /`, `df -hT /boot`, and `df -i`.
- **Final installer/staging**: original `/usr/sbin/armbian-install` remains untouched (`defc9646…`). Reviewed installer `armbian-install-final.sh` `90cb0390…` (30,340 B), patch `175920b5…` (4,529 B), exclude `deploy/emmc-exclude.txt` `58b8fe24…` (1,397 B), reviewed service `deploy/vt13-kiosk.service` `3ed77408…` (842 B). All four files are staged at `/home/billieguo/mobile_vt/.codex_tmp/emmc_deploy_20261112/g5/`; remote SHA256 matches local and `bash -n` RC=0. `/ddbr` is currently absent (installer creates it); `/dev/mmcblk2` is `7,474,249,728 B`, unmounted; current root `/dev/sda2` ext4 and `/boot` `/dev/sda1` vfat; `vt13-kiosk.service` active, `MainPID=447`, `NRestarts=0`.
- **G3/G4 conclusion changes**: G3 is **RECOMMENDED PASS** for the final `2,853,710,642 B` minimal payload (documented note: the full 61,468 members were not expanded on the PC; measured from the remote uncompressed tar stream and installer fail-closed checks; G6 must measure ext4 free space/inodes). G4 is **RECOMMENDED PASS_WITH_APPROVED_RISK** with the runtime dependency change from PyAV venv/custom FFmpeg to system Python/system FFmpeg; eMMC-only boot, boot priority, DTB/HDMI, ca46 autoload, service auto-start, USB hotplug, and SSH remain **PENDING G6**. The old 17:16 G3/G4 report is superseded and retained as `G3G4_REPORT_20261112_1716_superseded.md`.
- **Evidence**: `.codex_tmp/emmc_deploy_20261112/g3g4/G3G4_REPORT.md` SHA256 `82ee6c50…`; `EVIDENCE_SHA256.txt` SHA256 `6baab39d…`; `sha256sum -c` 30/30 OK; `G3G4_REPORT.md.sha256` verifies. G5 staging evidence `.codex_tmp/emmc_deploy_20261112/g5/STAGING.txt`. The G3/G4 report/evidence copies in the backup root remain the 17:16 version and must not be used for G5 approval; the authoritative final copies are the `.codex_tmp/emmc_deploy_20261112/g3g4/` files above.
- **Files changed**: `AGENTS.md` (new item 115), `docs/REMOTE_MACHINE_USAGE.md` (stage table + G3/G4 section), `docs/INTERSESSION_TRANSFER.md` (this entry), `deploy/PAYLOAD_MANIFEST.md`, `plans/CM311_eMMC_Deployment_Runbook.md` (final payload/decision/G5 command), and the G3/G4 report/manifest files. No commit.
- **No side effects**: no eMMC write, no service stop, no reboot, no module reload, no live USB/HDMI/wireless run. G5 is **NOT EXECUTED**; the exact approved-only command, interactive inputs (`127`, then `1` for ext4), target layout, recovery path, and residual risks are in `plans/CM311_eMMC_Deployment_Runbook.md` §8.3.
- **Next**: obtain explicit G5 approval, then run the reviewed installer on CM311; after success `sync` + `poweroff`, remove SG USB, cold boot, and execute G6. Do not claim production acceptance or closure of the content-dependent `0xf`, recovery freezes, or glass-to-glass latency without new evidence.

## 2026-11-12 17:16 HKT — G3/G4 audit report complete; recommended pass; G5 awaiting approval (superseded by the 19:16 entry above)

- **Task**: finish the G3/G4 eMMC deployment audit and generate a report that distinguishes verified facts, recommended gate results, and G6-only dynamic checks.
- **Result**: G3 **RECOMMENDED PASS** (with a documented note that the full 90,723-member payload was not expanded on the PC; capacity/member audit used the actual remote uncompressed tar stream, and the installer has fail-closed critical-file checks). G4 **RECOMMENDED PASS_WITH_APPROVED_RISK**; eMMC-only boot and all runtime behavior remain **PENDING G6**. G5 was not executed.
- **Verified numbers**: eMMC `/dev/mmcblk2` Biwin `7,474,249,728 B`; selective tar stream `3,662,858,240 B`, 90,723 members; additional FFmpeg shared install 21,660 KiB and kiosk helper 384 KiB; total payload `3,685,431,296 B` (3.432 GiB). ampart-success root `6,814,695,424 B` with `3,129,264,128 B` (2.914 GiB) free before filesystem metadata; fallback root `6,048,186,368 B` with `2,362,755,072 B` (2.200 GiB) free. Both exceed 1 GiB; G6 must measure actual ext4 free space.
- **Installer**: original `/usr/sbin/armbian-install` `defc9646…` untouched; patched `armbian-install-selective.sh` `1ed75849…`; patch `6c8dcfdf…`; exclude manifest `e6d978bc…`; remote copies match and `bash -n` OK. The patched installer forces `-gxl-test` DTB, applies the exclude manifest, copies FFmpeg shared `install/`, recreates `.codex_tmp` with `billieguo:billieguo`/`775`, copies the optional KMS helper, and fail-closes on missing critical runtime files. Expected source-side writes: machine-id regeneration, `/ddbr/install`, and `/usr/lib/u-boot/mybox-bootloader.img` (first 4 MiB eMMC backup); source `/boot` is not modified.
- **Boot/runtime audit**: eMMC user area has `@AML`/gxl bootloader header at `0x200`; boot0/boot1 are zero 4 MiB regions with `force_ro=1`. MODEL_ID 127, uEnv `2b488bb1…`, normal/`-gxl-test` DTB `1a568548…`/`6bdcf618…` (HDMI-only diff), zImage `4b7b8882…` TEXT_OFFSET 0108, boot-emmc mmc `2 1 0`, u-boot candidate `207cdbe1…`; ca46 `ca467983…` with matching vermagic/deps/alias and firmware `f1336295…`; worker only libc; PyAV RUNPATH to FFmpeg shared install; service `15ade4bb…`, journald `f39e019b…`, actual udev `9509a4c1…` (preserve installed rule, differs from repo source).
- **Residual risk**: eMMC boot success, boot priority, HDMI/DTB behavior, ca46 auto-load, service auto-start, USB video, and SSH remain unverified until G6. USB fallback is not guaranteed after bootloader write; use `poweroff` plus cold boot, not soft reboot. A failed eMMC boot may require physical reset or Amlogic USB Burning Tool.
- **Artifacts**: `.codex_tmp/emmc_deploy_20261112/g3g4/G3G4_REPORT.md` SHA256 `1d54fbfa…`; `EVIDENCE_SHA256.txt` SHA256 `711d9a82…`; `sha256sum -c` 36/36 OK. Copies: backup root `G3G4_REPORT.md`, `G3G4_EVIDENCE_SHA256.txt`, `G3G4_REPORT.md.sha256`.
- **Files changed**: `AGENTS.md` (item 114), `docs/REMOTE_MACHINE_USAGE.md` (current stage + G3/G4 section), `docs/INTERSESSION_TRANSFER.md` (this entry), `plans/CM311_eMMC_Deployment_Runbook.md` (status/decision/G5 command), and the three `g3g4` report/manifest files. Documentation/evidence only; no eMMC write, service stop, reboot, module reload, or live run. No commit.
- **Next**: obtain explicit G5 approval, then run the reviewed installer with MODEL_ID 127 and rootfs 1 (ext4); after success `poweroff`, remove SG USB, cold boot, and execute G6 checks.

## 2026-11-12 14:59 HKT — G2 backup verification PASS; no eMMC write

- **Task**: continue the eMMC deployment runbook at G2 after the rootfs/boot/Codex-temp transfers completed. The user reported the archives finished at 13:37 HKT (rootfs about 5.4 GB, boot about 159 MB, Codex temp about 965 MB); the apparent stall was normal completion.
- **Backup root**: `/home/billieguo/cm311-deployment/backups/cm311-sg-20261112_121131` (about 12 GiB). `sg-rootfs.tar` SHA256 `94c300a4…`; `sg-boot.tar` `cd62f744…`; `codex_tmp.tgz` `10eab3c8…`; `captures.tgz` `a62a74e6…`; `mobile_vt_runtime.tgz` `d2360d1b…`; `kernel_module.tgz` `60618b73…`; `linux_source.tgz` `bd8147b7…`.
- **SHA256**: `SHA256SUMS` now has 28 entries and `sha256sum -c` returned **28/28 OK**, failures 0, stderr empty. Added `sg-rootfs-toplinks.tar` (`f6847974…`) because the original rootfs archive covered only `etc/home/opt/root/srv/usr/var` and omitted top-level `bin/lib/sbin` symlinks; the supplement records `bin -> usr/bin`, `lib -> usr/lib`, `sbin -> usr/sbin`. `SHA256SUMS` SHA256 `77e08027…`; verification output `37a27c0f…`.
- **Archive readability**: all 10 archives passed `tar -tf`; all `.tgz` files passed `gzip -t`; overall RC=0, stderr 0 bytes. Evidence `.codex_tmp/emmc_deploy_20261112/g2/archive_readability_20261112_145703.txt` (SHA256 `4f483e6b…`).
- **Sample restore**: extracted worker, kiosk/config, ca46 module, systemd service/journald, boot/uEnv/DTB, FFmpeg symlink sample, and a Codex-temp payload. Corrected verification returned RC=0: restored files **17/17 OK**, direct boot copies **4/4 OK**, cross-archive comparisons **6/6 MATCH**; modes preserved. Worker `eb1dbb67…`, config `d4d155f2…`/`1a6160d1…`, ca46 `ca467983…`, service `15ade4bb…`, uEnv `2b488bb1…`, normal DTB `1a568548…`, `-gxl-test` DTB `6bdcf618…`. Evidence `.codex_tmp/emmc_deploy_20261112/g2/restore_verify_corrected_20261112_150929.txt` (SHA256 `61e8cb3b…`) and restore root `.codex_tmp/emmc_deploy_20261112/g2/restore_test_20261112_150327/`.
- **Important correction**: the first restore verification attempt returned RC=1 because the script passed a relative expected-manifest path after changing directory and used relative paths for cross-archive `cmp`. The hashes themselves matched; the corrected rerun used absolute paths and returned RC=0. The failed log is retained for audit.
- **Coverage notes**: `sg-boot.tar` has 233 members including `vmlinuz-6.18.59-ophub`, initrd/uInitrd, config, boot scripts, uEnv, and DTBs. Rootfs includes the installed ca46 module, `modules.dep`/`modules.alias`, systemd units, and `/etc/udev/rules.d/99-vt13.rules`. The installed udev rule (`9509a4c1…`, MODE/GROUP/uaccess) differed from repo `udev/99-vt13-video.rules` at G2 time (`6d9b78ee…`; current repo source `4455e3b2…` adds explanatory comments with the same effective rule); both are backed up, and deployment should preserve the installed rule unless intentionally changing it. The earlier G1 `MISSING` line was a filename mismatch. `codex_tmp.tgz` wrapper status 1 was due live directory/socket changes; archive readability and sampled extraction passed.
- **Limits**: rootfs tar is a file-level backup of selected directories, not a block-level disk image. No original eMMC image was taken because `/dev/mmcblk2` currently has no partitions/mounts. Root-owned samples restore as PC uid/gid `1001:1001`; archive metadata remains authoritative and modes were preserved.
- **Files changed**: `AGENTS.md` (item 113), `docs/REMOTE_MACHINE_USAGE.md` (G2 section/status), `docs/INTERSESSION_TRANSFER.md` (this entry); backup-root additions `sg-rootfs-toplinks.tar` and `G2_REPORT.md`. Documentation/evidence only; no Python/C/config/service change, no commit.
- **Verification state**: **G2 PASS** for the stated scope. No USB/HDMI/wireless run, service restart, reboot, module reload, or eMMC write occurred. The read-only SSH check confirmed `/bin`, `/lib`, `/sbin` symlinks and `/lib64` absent.
- **Next**: proceed to G3 (capacity/selective eMMC payload) and G4 (DTB/module/boot-chain audit). Do not start G5 eMMC installation without explicit human approval.

## 2026-11-12 HKT — Stage summary + full CM311 system/application deployment runbook documented (no runtime change)

- **Task**: summarize the current development stage from `AGENTS.md`, `docs/`, and `plans/`, and document how to fully deploy the system (including the OS) plus the application on CM311.
- **Stage recorded**: K3 service deployment is `ACCEPTED_WITH_LIMITATION`. Verified: D3-0/D3a/D3b/D3c, Source Change repair, USB hotplug recovery, systemd kiosk, permanent ca46 module, cold boot with ~60.4 fps / `sessions=1` / 0 errors / 0 `0xf` on the cleanest run. Open: content-dependent `0xf` with ~217–283 ms recovery freezes, startup `0xf` bursts, one soft-reboot hang, unmeasured glass-to-glass latency, no fresh 30-min soak on the final `eb1dbb67`+ca46 combination, volatile kiosk journal, hash-only remote parity, and no eMMC install yet.
- **Runbook added** to `docs/REMOTE_MACHINE_USAGE.md`: deployment choice (keep USB root vs eMMC), Phase 0 backup/preflight, Phase 1 OS install (`armbian-install`, model ID 127, ext4, capacity/DTB/boot-fallback caveats), Phase 2 toolchain packages, Phase 3 ca46 module build/install/cold-boot verification, Phase 4 custom shared FFmpeg + PyAV venv build and ldd/codec checks, Phase 5 application/udev/service deployment, Phase 6 acceptance, Phase 7 rollback, and verified pitfalls.
- **Exact commands captured**: `d3_probe` build is `gcc -O2 -Wall -Wextra` on target; the worker source `4af75b7c…` produced `eb1dbb67…` with gcc 13.3. FFmpeg shared configure is the documented `--enable-shared --disable-static` variant of the original flags. PyAV 11.0.0 build uses `PKG_CONFIG_PATH`/`CFLAGS`/`LDFLAGS=-Wl,-rpath` against `~/ffmpeg-6.1.1-v4l2-shared/install`, `--no-build-isolation`, and force-reinstall into `.venv-v4l2` only. The kernel module command is documented as `make -j4 M=drivers/staging/media/meson/vdec modules`; this is the standard in-tree kbuild invocation and is explicitly flagged for re-confirmation because the historical exact command is not recorded.
- **Files changed**: `docs/REMOTE_MACHINE_USAGE.md` (stage section + deployment runbook), `docs/INTERSESSION_TRANSFER.md` (this entry), `AGENTS.md` (item 112). Documentation only; no Python/C/config/service change, no commit.
- **Verification**: no CM311 write, service restart, reboot, module reload, or live run. A read-only SSH probe was attempted but key-only auth still returned RC=255 (`Permission denied (publickey,password)`); no askpass was used in this window. The runbook therefore relies on the previously verified evidence and is marked where a fresh target check is required.
- **Remaining uncertainty**: the eMMC install path has not been executed; its capacity, DTB rewrite, and boot-priority fallback are documented from the 2026-11-11 read-only assessment. The kernel-module rebuild command needs one target-side confirmation on the next clean rebuild.
- **Next**: user decides USB-root vs eMMC migration. If eMMC, R3 approval, free/move at least ~9 GiB, run `sudo armbian-install`, cold boot, and verify DTB/SSH/HDMI/module/service. Optional further confidence: a fresh 30-min soak on `eb1dbb67`+ca46 and a glass-to-glass measurement.

## 2026-11-11 21:40 HKT — CM311 storage / Armbian eMMC installability read-only assessment

- User asked whether CM311's USB `SG-xxx` system can be installed on CM311. Read-only SSH checks: root `/dev/sda2` on USB `SG Flash` 117.2 GB; `/boot` `/dev/sda1`; internal eMMC `/dev/mmcblk2` Biwin 7.47 GB with no partitions or mount. Board `S905l3b` / `meson-gxl` / MBH-M302A.
- `/etc/ophub-release` and `/etc/model_database.conf` list `MODEL_ID=127`, `MODEL_NAME=M302A,M304A,CM201-1,CM211-1,CM311-1`, `FDTFILE=meson-gxl-s905l3b-m302a.dtb`, `UBOOT_OVERLOAD=u-boot-s905x-s912.bin`; ophub Armbian is installable and currently running from USB.
- `armbian-install` supports USB→eMMC; `/usr/bin/ampart` is present, so the s905l3b layout leaves about 6.3 GiB for root (fallback about 5.6 GiB). Current root copy set is about 15.3 GiB (`~/mobile_vt` 8.0 GB, captures 4.2 GB, `.codex_tmp` 3.2 GB), so direct eMMC install lacks space. Clean/move project/build trees or keep USB root.
- Current `/boot/uEnv.txt` uses `meson-gxl-s905l3b-m302a-gxl-test.dtb`; the installer writes the normal `meson-gxl-s905l3b-m302a.dtb`. Verify after install and restore the test DTB if this board needs it.
- No install/reboot; no remote writes. Next: decide USB vs eMMC; if eMMC, free space, run `sudo armbian-install` (model ID 127), then poweroff, remove USB, cold boot; R3 approval required.

## 2026-11-11 21:23 HKT — Committed 0e274eb + runtime parity verified (RUNTIME_PARITY_OK)

- **Commit `0e274eb`** (main, no push): "k3: service hardening, Source Change recovery fix, cold-boot module fix" — 8 intended files (AGENTS.md, deploy/vt13-kiosk.service, deploy/vt13-kiosk-journald.conf, docs/INTERSESSION_TRANSFER.md, docs/REMOTE_MACHINE_USAGE.md, tests/test_pipeline.py, tools/d3_probe.c, vt13_video/recovery.py). Structured Summary/Verification/Conclusion. Secret scan: no new credential occurrence added; the pre-existing plaintext CM311 password in REMOTE_MACHINE_USAGE.md (already in HEAD) is untouched — **rotation/removal recommended** with a replacement credential path. `.codex_tmp`/binaries/captures/sibling repo excluded.
- **Runtime parity (verified, not re-synced — runtime was deployed during this session)**: full-package hash matrix local-commit vs CM311 `~/mobile_vt` = **16/16 match (RUNTIME_PARITY_OK)** (15 `vt13_video/*.py` + `config/vt13_video.kiosk.yaml`). Worker: committed source `tools/d3_probe.c 4af75b7c…` → on-device binary `build/d3/d3_probe eb1dbb67…` (built from that source; remote `~/mobile_vt` has no `tools/`, tools/tests/docs stay local). Module installed `ca467983…`. Manifests `.codex_tmp/k3_source_change_20261111/parity_{local,remote}.txt`.
- **Live state at commit**: kiosk healthy (MainPID 449, sessions=1, 60.4 fps, 0 errors/0 `0xf`, vdec IRQ firing) — serves as post-commit live evidence; no separate smoke needed.
- **K3 ACCEPTED_WITH_LIMITATION** (see 21:13 entry). Backups: worker `backup_srcchange_20261111_201335/d3_probe.51346c85`; module `meson-vdec.ko.a6cc08ca.bak`.

## 2026-11-11 21:13 HKT — Permanent module fix VALIDATED: cold-boot auto-load ca46 → kiosk auto-start → 60.4 fps, sessions=1, 0 errors

- **Permanent install (R3 approved)**: backed up wrong module to `/lib/modules/6.18.59-ophub/.../meson-vdec.ko.a6cc08ca.bak` (`a6cc08ca…`), installed source build `ca467983…` into `/lib/modules/.../meson-vdec.ko`, `depmod -a` RC=0. Installed hash verified `ca467983…`.
- **Boot incident (caveat)**: the first soft `systemctl reboot` after install (20:58) **hung** — black screen (power on), PC `enp4s0` no carrier, SSH unreachable at 10.42.0.11 (>5 min). User **hard power-cycled** → recovered. Cause not isolated (possibly warm-reboot left VDEC hardware in a state ca46's boot probe couldn't handle, or a one-off fsck/boot glitch). **Cold boot works; soft-reboot reliability needs monitoring.**
- **VALIDATED after hard reboot**: system booted, service auto-started (MainPID 449, NRestarts=0, enabled), **installed module `ca467983…` auto-loaded**, worker `eb1dbb67`, **vdec IRQ firing (5842)**, IP stable 10.42.0.11, USB Dev 002. Steady 21:13:14→21:13:26 aus_frames 4999→5724 = **725/12 s = 60.4 fps**, **sessions=1 (zero rebuilds)**, corrupt=0, age ~22–34 ms, **0 errors / 0 recoveries / 0 `0xf`**. Cleanest state achieved.
- **Acceptance summary**: Source Change wedge fix (offline A/B + in-situ + visual) ✓; USB hotplug (in-process recovery, NRestarts=0) ✓; cold-boot auto-start + decode + present with permanent ca46 ✓. **K3 ≈ ACCEPTED_WITH_LIMITATION**. Remaining caveats/limits: soft-reboot hang observed once (monitor); startup 0xf burst on some boots (content-dependent, auto-recovers); glass-to-glass unmeasured; ca46 is an out-of-tree experimental module (kernel package update could revert it — backup `.a6cc08ca.bak` kept). A fresh 30-min soak on the patched worker + ca46 is optional further confidence.
- **Evidence**: `.codex_tmp/k3_source_change_20261111/{install_module,reboot_verify2,reboot_final_verify,reboot_final_steady}.log`. Recovery command if a boot hangs: hard power cycle; if decode wrong module, `insmod ~/linux-6.18-vdec/.../meson-vdec.ko` (see REMOTE_MACHINE_USAGE).

## 2026-11-11 20:54 HKT — Reboot test exposed WRONG-MODULE cold-boot defect; source-build meson_vdec (ca46) restores decode; permanent install pending

- **Reboot auto-start (R3, approved, user physical access)**: `sudo systemctl reboot` 20:40:09; SSH back ~70 s; service auto-started (enabled + multi-user.target, MainPID 448, NRestarts=0), worker `eb1dbb67` persisted, USB re-enumerated Dev 002, **IP stable 10.42.0.11** (DHCP same lease). **BUT no video** — user saw Armbian login console.
- **Cold-boot decoder defect**: worker fed first AU then `no SOURCE_CHANGE within 10000 ms` → rebuild every 10 s, 0 frames, `G_FMT` never reached. Kernel: `vdec-mbox1` IRQ count **0** (decoder core never completes) while `esparserirq` fired (parser OK). `HEVC mailbox IRQ is unavailable` warning is a **constant red herring** (DT `interrupt-names` = `vdec esparser` only; driver falls back to `vdec` for mbox1, mbox0 has no fallback). Firmware present; runtime PM `unsupported`.
- **Failed remedy**: `rmmod`+`modprobe meson_vdec` (R3 approved) did NOT fix — modprobe reloads the **installed** module, still vdec IRQ 0.
- **ROOT CAUSE**: two different modules. Installed `/lib/modules/6.18.59-ophub/.../meson-vdec.ko` = **`a6cc08ca2598caf378881a85515c211e8fc41e6bc870753e5d11a3942458f198`** (auto-load uses this; parses but HEVC core never completes). Source build `~/linux-6.18-vdec/.../meson-vdec.ko` = **`ca46798328e0975290151c40e1ddbf191a277b563a9694344aca910507aacdab`** (the known-working module recorded in AGENTS.md, manually loaded before reboot). Before reboot the source build was insmod'd manually; reboot auto-loaded the wrong installed one.
- **Fix verified (R3 approved)**: stop kiosk → `rmmod meson_vdec` → `insmod ~/linux-6.18-vdec/.../meson-vdec.ko` (ca46, "out-of-tree module taints kernel") → start kiosk (MainPID 4466). **vdec IRQ 0→1856**, START_GATE open, primary plane disabled (console hidden), first_frame presented. Steady 20:53:21→20:53:31 aus_frames 1129→1735 = **606/10 s = 60.6 fps**, sessions 2, corrupt=0, age ~35 ms, 1 minor 0xf. Decode fully restored.
- **PERMANENCE GAP (critical)**: the insmod is **temporary**. Next reboot will auto-load `a6cc08ca` again and break. Permanent fix needs R3 approval: backup `a6cc08ca` → install `ca46` into `/lib/modules/.../meson-vdec.ko` → `depmod -a` (so auto-load uses ca46), then re-reboot to confirm. NOT done yet.
- **Acceptance status**: Source Change wedge fix verified + visually accepted; USB hotplug PASS; reboot auto-start of *service* works but **unattended boot decode is BROKEN until ca46 is installed permanently**. K3 cannot be called fully accepted yet. Evidence `.codex_tmp/k3_source_change_20261111/{reboot_test,reboot_diag,reboot_irq*,module_compare,reload_test,reload_source_test,reload_source_steady}.log`.

## 2026-11-11 20:37 HKT — User visual acceptance + USB hotplug PASS (in-process recovery, no service restart); reboot test next

- **Visual acceptance**: user confirmed "screen is normal" after the cold-start fix → the deployed patched worker's live picture is accepted. Cold-start wedge fix + visual = K3 core acceptance met (ACCEPTED_WITH_LIMITATION territory).
- **USB hotplug PASS** (user physically unplugged/replugged the DJI C5 receiver only; rootfs SG Flash untouched). Baseline 20:35:24 Dev 006, MainPID 272982/NRestarts=0, presenting. Sequence:
  - 20:36:24 kernel `usb 1-1: USB disconnect, device number 6`; pipeline `USB read failure (disconnected) Errno 19 No such device` → `stream discontinuity (usb_disconnected)` → `reopening USB in 0.25s` (graceful, no crash).
  - 20:36:39 kernel re-enumerated `2ca3:1020` as **device 7**, ttyACM0/ttyACM1 recreated.
  - 20:36:42 pipeline `USB source open … bus 1 address 7` → `USB re-enumerated after a disconnect; VT03 encoder not reset` → `control: requested I-frame`. A few post-replug content-dependent `kernel_0xf` auto-recovered.
  - **NRestarts=0, MainPID 272982 unchanged** — recovery entirely in-process (ideal). Steady 20:37:29→20:37:39 aus_frames 37148→37752 = **604/10 s = 60.4 fps instantaneous**, sessions stable 47, corrupt=0, age ~30 ms, only 1 `0xf` since 20:37.
- **Evidence**: `.codex_tmp/k3_source_change_20261111/{hotplug_baseline,hotplug_capture,hotplug_steady}.log`.
- **Next**: physical reboot auto-start test (R3, user deferred it behind hotplug). Precheck done: service `enabled` + `multi-user.target`, SSH `enabled`, network DHCP `10.42.0.11` (gw 10.42.0.1, IP may change on reboot), root `/dev/sda2` ext4, worker `eb1dbb67`. Needs explicit R3 approval + user physical access (HDMI/keyboard) for SSH-loss recovery. Still untested after that: glass-to-glass, fresh 30-min soak on patched worker.

## 2026-11-11 20:29 HKT — Live cold-start 1832→1920 CONFIRMED FIXED in situ; deployed patched worker steady at 60 fps

- **Human VT cycle done** (user off→on). With VT off, restarted kiosk (MainPID 272982/worker 272990, patched `eb1dbb67`), READY at 20:25:22 (usb=up/data=no/0 frames, waiting IRAP). User opened VT ~20:26.
- **Cold-start sequence (the original failure scenario), now fixed**:
  - 20:26:18 session 1–2: `G_FMT 1832x1032`, `min_buffers=16` (source starts 1832).
  - 20:26:21 session 3: `G_FMT 1920x1080`, **`min_buffers=16`** — the 1832→1920 switch recovered via fresh fd, **NOT the old `min_buffers=1` permanent-zero wedge**. Presentation continued through the switch.
- **Startup 0xf burst (separate known P0, content-dependent)**: 40 `HEVC_LCU_CHECK status=0xf poc=7` aborts during 20:26:18–49 (~31 s), each auto-recovered (sessions 3→41, all `min_buffers=16`). **Last 0xf 20:26:49; zero new 0xf since 20:27** (>90 s clean). This is the content/RF-dependent firmware abort, NOT the source-change wedge; the patch does not claim to fix 0xf, only the wedge.
- **Steady state**: 20:28:25→20:28:37 aus_frames 5678→6398 = **720/12 s = 60.0 fps instantaneous**, sessions stable at 41, corrupt=0, age_p50≈21–32 ms, NRestarts=0, active/enabled. Deployed worker `eb1dbb67…`; backup `backup_srcchange_20261111_201335/d3_probe.51346c85` intact.
- **Gate status**: the K3 blocking defect (cold-start 1832→1920 zero-frame wedge) is **fixed + offline A/B + in-situ confirmed**. K3 can move to ACCEPTED_WITH_LIMITATION pending user visual confirmation. **Still untested**: physical reboot/boot startup, USB hotplug, glass-to-glass latency, and a fresh 30-min soak on the patched worker (earlier 30-min soak was on old `51346c85`). Startup 0xf burst (~40/31 s then settles) is a known limitation. Do not claim 0xf solved or full unattended PASS.
- **Evidence**: `.codex_tmp/k3_source_change_20261111/{coldstart_restart,coldstart_ready,coldstart_capture,coldstart_head,coldstart_steady}.log`.

## 2026-11-11 20:16 HKT — Patched worker DEPLOYED to CM311 kiosk; live cold-start 1832→1920 confirmation pending (human VT cycle)

- **Approved R2 deployment executed**: backup → hash-guarded replace → restart → verify. Deployed `~/mobile_vt/build/d3/d3_probe` now `eb1dbb67f3193ddcbc5f37f7793f30b7b117c00e9626fb6a4ab68fbc19a95008` (was `51346c85…`). Backup `~/mobile_vt/.codex_tmp/backup_srcchange_20261111_201335/d3_probe.51346c85` (hash `51346c85…` verified). Deploy script `deploy_window.sh` (`dd06c58d…`): hash guard restores backup on mismatch; trap always restarts service. Python runtime/kiosk.yaml unchanged. No reboot/kernel/network change.
- **Old worker clean shutdown**: 28878 frames, 1920x1080, 8 keyframe starts, 7 discontinuities, 0 USB errors. **New patched worker live**: MainPID 272334/worker 272344 owns `/dev/video0`, active/enabled, NRestarts=0, presenting ~58 fps / 60 FPS source, 0 errors/0 recoveries, corrupt=0, sessions=1, age_p50≈25–56 ms (VT on, 1920 stream). Evidence `.codex_tmp/k3_source_change_20261111/{deploy.log,post_deploy_health.log}`.
- **Rollback ready**: `cp ~/mobile_vt/.codex_tmp/backup_srcchange_20261111_201335/d3_probe.51346c85 ~/mobile_vt/build/d3/d3_probe && sudo -n systemctl restart vt13-kiosk.service`.
- **Remaining for full K3 acceptance**: a real live cold-start 1832→1920 confirmation (the original failure scenario) needs a human VT off→on cycle so the source starts at 1832 then switches; the offline A/B already proved the fix, this is the in-situ confirmation. Boot startup, USB hotplug, glass-to-glass and user visual acceptance still untested. K3 moves toward PASS pending the cold-start confirmation; do not claim full PASS yet.

## 2026-11-11 20:08 HKT — Source Change fix HARDWARE-VERIFIED on CM311 (patched resumes 1920, old wedges); deployed worker still unchanged

- **Approved R2 windows executed** (user approved patched+old A/B, then a corrected re-run). Service stop/start via `sudo -S`/`sudo -n` (password fed at runtime via stdin, never echoed; `sudo -n` alone failed first because the earlier credential cache had expired — service was never stopped on that aborted attempt, device-retained guard worked). Deployed worker binary **never replaced**; rollback = restart service. No reboot/kernel/network change.
- **First run inconclusive (test-design flaw)**: synthetic `switch_1832_to_1920.h265` had only ONE 1920 IRAP (AU 30). After the switch the worker rebuilt and sent `R`; the replay dropped non-IRAP AUs waiting for the next IRAP, but the only 1920 IRAP had passed → both workers starved at 22 frames (SENT=33/DROPPED=428). Useful signal: patched logged `RECOVER (DQBUF EPIPE)` (fresh-fd path executes on hardware), old logged `(DQBUF EIO)`.
- **Corrected stream**: `switch_multi.h265` = clean_1832 + 3× segB_irp1080, SHA256 `f91350b137f5a8ed414d95648c14df5efc06194e82e686d5d1e8fcd1d06f1148`, 24,706,659 B, **1323 AUs, 1920 IRAPs at AU 30/461/892** (matches live periodic-IRAP behavior). Runner `run_switch_test.sh` (`33febd6c…`) defaults to this stream.
- **DECISIVE A/B (same stream, same window)**:
  - **Patched `eb1dbb67`**: session 1 1832 (22 frames) → `DQBUF EPIPE` → fresh-fd rebuild → session 2 receives 1920 IRAP AU 461 → `G_FMT 1920x1080`, **min_buffers_for_capture=16** → decodes the 1920 segment. **DECODED frames=873 corrupt=0 oversize=0 sessions=2** (22×1832 + 851×1920), steady age_p50≈53.5 ms. **Recovers.**
  - **Old `51346c85`**: session 1 1832 (23 frames) → `DQBUF EIO` → same-fd rebuild → session 2 receives the SAME 1920 IRAP AU 461 → `G_FMT 1920x1080`, **min_buffers_for_capture=1** → `aus_frames` frozen at 23, age=-1, **zero 1920 frames permanently**. **DECODED frames=23 sessions=2 fps=1.04.** **Wedged — exactly the cold-start defect.**
  - This confirms the root cause on hardware (same-fd rebuild leaves `source_change_pending` set → `min_buffers=1` → decoder paused) and that the fresh-fd fix clears it. The patched `VISIBLE_GAP gap_ms=7350` is the replay's drop-to-IRAP wait (428 AUs ≈ 7 s between synthetic IRAPs), NOT a worker freeze; live IRAPs arrive ~2 s apart so the real gap is bounded by that.
- **Service restored healthy** after each window: final MainPID 270674/worker 270678, active/enabled, NRestarts=0, live 60 FPS/0 errors (VT on). Deployed worker confirmed still `51346c85bfe2e6aaed134c6004abb59e615b36ed03f0386f8e99eca0829affe6`.
- **Evidence** (local == remote SHA256): `.codex_tmp/k3_source_change_20261111/run_patched.log` `767e348a…`, `run_old.log` `60363190…`, `replay_patched.log` `138ac92f…`, `replay_old.log` `afbe1a5c…`, full window `test_window3.log` `d357c4c6…` (first run `test_window2.log`). Remote `~/.codex_staging/k3_srcchange_20261111_194655/`.
- **Status**: fix is offline + hardware verified. **NOT deployed** — replacing `build/d3/d3_probe` (and a live cold-start confirmation with VT) needs a separate exact-command approval. K3 overall acceptance can move toward PASS once the patched worker is deployed and a real 1832→1920 cold start is confirmed; boot/hotplug/glass-to-glass still untested.

## 2026-11-11 19:53 HKT — Patched worker staged on CM311 + offline switch-replay assets ready (service untouched, R2 window pending)

- **Done (safe, no device/service change)**: read-only precheck (service active/enabled, MainPID 263980/worker 263983 owns `/dev/video0`, deployed worker confirmed `51346c85bfe2e6aaed134c6004abb59e615b36ed03f0386f8e99eca0829affe6`, gcc 13.3 aarch64, LightDM inactive). Transferred patched `tools/d3_probe.c` to `~/.codex_staging/k3_srcchange_20261111_194655/` — remote source SHA matches local `4af75b7c…`; compiled on target `gcc -O2 -Wall -Wextra` **BUILD_RC=0, no warnings**, aarch64 PIE binary SHA256 `eb1dbb67f3193ddcbc5f37f7793f30b7b117c00e9626fb6a4ab68fbc19a95008`. Transferred fixed `tools/d3_replay.py` (`0cc5cc6d…`, matches local; remote old staging copy is the buggy pre-item-83 version, NOT used).
- **Controlled offline repro built**: synthetic `switch_1832_to_1920.h265` = `clean_1832x1032.h265` (`2e13db18…`, 698640 B) + `segB_irp1080.h265` (`c7f5da00…`); SHA256 `6c78ff028ca33ebdf2dd60ab6535ea7a2e3b0fce9d19790c9dc845c164cde657`, 8,701,313 B. `split_aus` verification (no device): **461 AUs, 2 IRAP at AU 0 and AU 30**; the 1920 IRAP at AU 30 carries its VPS/SPS/PPS (clean boundary). This reproduces the cold-start 1832→1920 SOURCE_CHANGE without RF/0xf damage. Runner `run_switch_test.sh` (`1130501e…`, `bash -n` OK both hosts) takes `<worker-binary> <label>`, assumes service already stopped, runs replay@60 AU/s + worker `--socket --cap-bufs 17 --start-gate 0 --hide-primary` under `timeout -k 5 40`, prints DECODED/sessions and device-free checks.
- **NOT done**: no service stop, no device streaming, no worker replacement. The hardware verification needs an approved R2 window because the running service owns `/dev/video0` + DRM. The deployed worker binary is never replaced in this test (staged binary run directly), so rollback = restart the service.
- **Pending approval (R2)**: stop `vt13-kiosk.service` → run patched worker offline switch-replay (expect frames resume past AU 30, sessions=2, ~461 frames) → optional A/B with old `51346c85` (expect wedge/zero 1920 frames) → restart service → verify READY. Exact commands presented to user; awaiting scoped approval. No reboot/kernel/network change. Evidence `.codex_tmp/k3_source_change_20261111/{precheck_remote,stage_build,stage_replay,prep_switch_remote}.log`.

## 2026-11-11 19:36 HKT — Source Change zero-frame wedge: root cause confirmed, minimal worker patch implemented + offline-verified (staging only)

- **Scope**: user approved "继续修复并验证" — backup first, minimal local change + offline tests; the deployed CM311 worker (`51346c85`) and K3 service stay untouched; any device run or binary replacement needs fresh exact-command approval. This step is PC-only; no remote write, no USB/V4L2/HDMI live run, no reboot/module/service change, no commit.
- **Root cause (driver source + logs)**: meson-vdec `amvdec_src_change` sets `source_change_pending=true` + `STATUS_NEEDS_RESUME` on a resolution change; `vdec_m2m_job_ready` (vdec.c:492) returns 0 while that flag is set, so the decoder is silently paused — no errors, zero frames. The HEVC session (`sess->priv`) persists across same-fd STREAMOFF/REQBUFS rebuilds (only `codec_hevc_release` on file close frees it). On a same-fd rebuild after a switch, `hevc->dst_width` already equals the new value, so `process_rpm` reports `src_changed=0`, no fresh `amvdec_src_change` fires, the flag never clears → permanent wedge. Only close/open recovers. OUTPUT STREAMON full-init resets `ctrl_min_buf_capture` to 1, explaining `min_buffers=1` in the wedged session. Same-resolution `0xf` rebuilds are safe (soak: `min_buffers` 1→16 every rebuild proves a fresh event each session). Caveat: the running module differs from the current source tree (source has `dev_warn HEVC_SHIFT_INIT`; soak kernel.jsonl had 0 such lines over 108 starts), so driver archaeology is indicative; the empirical log facts (EPIPE → stale SOURCE_CHANGE 0.0 ms → min_buffers=1 → aus_frames=0) are authoritative.
- **Patch** (`tools/d3_probe.c`, +45/−4; pre-repair SHA256 `8ace8282ec1f3dcafcbe8e138034e65561bd09ad4b95adab8388d0094e15f260`, post-repair `4af75b7c57aa53af437f810095925f01c33a4e07e856d12c92822a46ad87a303`): added `ctx.need_fresh_fd`, reset in `session_open`. (1) Inner `run_socket` loop consumes POLLPRI events BEFORE the POLLERR check; a `V4L2_EVENT_SOURCE_CHANGE` sets `need_fresh_fd=1` + `mark_recovering("SOURCE_CHANGE")`. (2) CAPTURE DQBUF `EPIPE` (both the first dequeue and the L2-B drain) sets `need_fresh_fd=1`; `EIO` keeps the fast same-fd path. (3) Teardown call is `session_teardown(c, recovered && !c->need_fresh_fd ? 1 : 0)`. (4) `session_teardown` drains pending events when `keep_fd`; a queued SOURCE_CHANGE flips `keep_fd=0` (race backup for a switch that raced the abort). (5) QBUF OUTPUT failure now calls `mark_recovering("QBUF OUTPUT")` (was an uninstrumented rebuild). Decode parameters and held/scanout release lifetime are deliberately unchanged.
- **Offline verification**: PC build `gcc -O2 -Wall -Wextra` RC=0, no warnings (binary SHA256 `65d4d2f6ab9ff4616374487d21e605f0f469c5e621a5f163e053e574065ef449`). Mock-syscall harness `.codex_tmp/k3_source_change_20261111/mock_test.c` (SHA256 `dd6f40fe81217a2f44b92f09314a23f5463d165781b46d2e452a05f34fc1f034`; renames libc syscalls, includes the worker, drives `run_socket` with `card_fd=-1`): **13/13 checks PASS, RC=0**. `open_calls` distinguishes physical reopens from the logical `sessions` counter: normal=1; mid-stream SOURCE_CHANGE=2; CAPTURE EPIPE=2; fixed-res EIO=1 (reuse); stale-event-raced-with-EIO=2 (teardown drain); QBUF OUTPUT fail=1 + R signal. Every scenario resumes frames and sends R. Python regression `unittest discover -s tests -t .`: **91 tests OK (38 skipped), RC=0** (the "configuration file not found" line is an expected negative-path test).
- **Backup**: `.codex_tmp/k3_source_change_20261111/pre_repair_local.tar` (SHA256 `21c05154c7eaa36cab09f88da81f9152deb124faf0ffebe4f3e5803d5929a5d3`), `pre_repair.diff` (`e5a2a2a7c65d9d129d9cf0d58834f805560eaf725e7d3da55f16eb33e718a6dc`), `pre_repair_head.txt`. Build/test artifacts and `mock_stderr.log` in the same directory (gitignored).
- **NOT verified**: hardware behavior. The mock proves the recovery state machine, not meson-vdec timing or pixels. No CM311 staging run, no worker replacement, no live run yet. K3 overall acceptance remains PARTIAL until this is hardware-verified and the cold-start 1832→1920 path is confirmed.
- **Next**: propose exact-command CM311 staging build + offline damaged-replay (resolution-switch sample) for the patched worker, then a fresh R2 live cold-start verification; replacement of the deployed worker/service requires separate explicit approval. Preserve `51346c85` and the rollback chain until then.

## 2026-11-11 19:04 HKT — K3 observation complete; overall acceptance PARTIAL

- **Current state**: K3 installed, enabled and active. MainPID 263980 / worker 263983, NRestarts=0; worker `51346c85`, kiosk.yaml `d4d155f2`, recovery.py `275c91f6`, unit `15ade4bb`, namespaced journal config `f39e019b`. Sampler and its journal readers exited; the kiosk remains running. No automatic extension, additional stop/start, reboot, source change or commit.
- **Final window**: 18:34:13.844–19:04:14.017 HKT, 1800.173 s. Presented counter delta **106,278 / 1799.092 s = 59.073 fps**, satisfying the >=59.0 floor but below preferred >=59.5; source/send delta 107,246 AUs. `corrupt=0`, `oversize=0` are flags, not complete SW/HW pixel validation. Backlog max 4; per-second age p50 median 33.6 ms, p95 median 36.05 ms.
- **Recovery**: 108 V4L2 rebuilds and 108 kernel aborts, no process restart or persistent frozen interval detected. 107 instrumented gaps: p50 216.7 / p95 250.1 / max 283.3 ms, summed 23.653 s (~1.31%). The additional rebuild at 18:56:15 came from QBUF OUTPUT EIO without mark_recovering, so its gap is not included; don't report the 107 timings as complete coverage. The much higher abort rate than historical V1 (6/30 min) is not isolated to systemd or content.
- **Resources**: 1799 samples, CPU median 26.75% (discard initial near-zero interval for peak interpretation), 66–73°C; MemAvailable 1139576→1148056 KiB. Python RSS 128184→128488 KiB and worker 1468→1532 KiB; no unbounded growth. Main FD12 fixed; worker steady FD40/dmabuf34, transient maximum44/38. Cgroup ~46–47 MB; hardware CMA is not fully accounted there. Namespace journal 7.3 MiB against configured 32 MiB budget; retention-limit stress not tested.
- **Gate**: unit installation, normal stop/cleanup, runtime parity and steady resource behavior verified. **Overall K3 remains PARTIAL**, because cold-start 1832→1920 produced zero presentation until one manually approved service reopen; that recovery defect is NOT fixed. User visual acceptance for this run, physical reboot startup, USB hotplug and glass-to-glass remain untested/unconfirmed. Do not reuse earlier RC1 user acceptance as acceptance of this K3 run.
- **Evidence**: all 10 final artifacts (9,330,350 B) copied from CM311 and hash-verified under `.codex_tmp/k3_service_20261111_1807/soak_20261111/`; manifest SHA256 `eb3017400cdcef68c1365cafcafd0f662bf5433992b4838f3a7263de6c390e3e`, complete.json SHA256 `94a217be40a8089b58f75d12a07f898c2763e4bab279d6ebe2861c5fe164da10`. Analysis siblings `complete_summary.json`, `final_analysis.json`, `final_inventory.log`; retrieval/analysis RC=0. Monitor `b56tgh1s3` completed. Host-generated monitor output is under `/tmp/qoder-cli-1001/` (external tool-managed); canonical evidence is project-local.
- **Next**: propose a minimal staging Source Change/zero-frame recovery repair, with offline replay and then exact-command hardware approval. Preserve current worker and rollback until approved. No further live runs or privileged changes are automatically authorized.

## 2026-11-11 18:54 HKT — K3 20-minute checkpoint, performance gate currently unmet

70,706 presented frames / 1199.692 s = **58.937 fps**, below RC1 >=59.0 target; 84 in-process rebuilds/kernel aborts total (+50 in second ten minutes), corrupt/oversize 0, max visible gap 283.3 ms, total gaps 18.536 s. PIDs unchanged, NRestarts=0, no permanent freeze. Age p50 median 34.5 ms, backlog max 3; CPU median 27%, temperature 66–71°C; memory, FD/dmabuf counts remain bounded (main FD12, steady worker FD40/dmabuf34); journal 4 MiB. Continue only the already planned final ten minutes to finish evidence, not to claim PASS. Source/copy SHA256 `3ebb6a9644c9fdc5a65fbd20f4ce06810afd3f073a85cc9233f077b7b5b04533`; local `checkpoint_1200.json` and `checkpoint_1200_summary.json`. Read-only retrieval/analysis RC=0; no runtime/service modifications.

## 2026-11-11 18:44 HKT — K3 10-minute checkpoint, observation continues

- Checkpoint at 18:44:14.573 HKT, elapsed 600.730 s: 35,465 new presented frames / 599.668 s = **59.141 fps**; corrupt/oversize delta 0; 34 session rebuilds and kernel aborts, 34 visible gaps (max 283.3 ms, total 7.518 s). All recovered in-process; service/worker PIDs unchanged, NRestarts=0, active/enabled.
- Per-second age p50 median 34.55 ms, age p95 median 36.8 ms; backlog max 2. CPU median 26.68% (initial near-zero sampling interval is unsuitable for peak CPU); 66–70°C. Available memory ~1.14→1.15 million KiB; Python RSS 128184→128368 KiB, main FD count fixed 12; worker FD steady 40 (range 10–44 during rebuild), dmabuf steady 34 (4–38). Namespace journal remains 4 MiB.
- This abort rate is higher than historical V1 (6/30 min); cause not isolated, so no claim that systemd caused it or that it is only content variation. Continue the same bounded run; previous startup/source-change failure remains open.
- Remote immutable checkpoint copied locally; SHA256 `261af1dc8ee3c896c3654c801ee1f8c6ea799ddae4e89984507298e1a5c14acc` matches. Local `.codex_tmp/k3_service_20261111_1807/checkpoint_600.json` and `checkpoint_600_summary.json`; summary includes resource samples <= checkpoint time. Read-only commands RC=0, no service/config/source change.

## 2026-11-11 18:34 HKT — K3 steady-state soak RUNNING after one approved reopen

- User explicitly approved one stop/start while keeping VT on as a diagnostic exception. Stop at 18:30:56 took 0.624 s, no device retained; new MainPID 263980, worker 263983, invocation `d7721b76ad4a4b43a4fc9b5f6204ce97`, active/enabled, NRestarts=0. START_GATE opened at 18:31:04; following worker reports gain ~60 presented frames per second, corrupt=0. No source/binary/config change.
- This isolates successful fresh-process startup on the now-stable source, not a fix for the earlier 1832→1920 startup failure. The failed startup remains an open defect; do not call the full K3 acceptance PASS solely on the later stable window.
- Bounded 1800-second read-only observer started **2026-11-11 18:34:13.843 HKT**, expected end ~19:04:14; checkpoints at 600/1200 seconds. Monitor task `b56tgh1s3` automatically reports events; do not poll it. It stops observation on 10 seconds without presented-frame progress or a service/worker process replacement and does not alter/stop the video service.
- Observer source `.codex_tmp/k3_service_20261111_1807/observe_soak.py` (8984 B, SHA256 `ad4b38890669a10b67079daa89aba67819c9db22a1fff4477cba493def3e4109`) matched target staging copy. Remote evidence `~/mobile_vt/.codex_tmp/k3_service_20261111_1807/soak_20261111/`: metadata, 1 Hz samples, service/kernel JSONL, checkpoint/final JSON and manifest. Metrics distinguish sent AUs from worker-presented frames; FD/dmabuf counts supplement memory checks, global GEM count unmeasured.
- Pending 10/30-minute results and user visual confirmation. Service stays enabled/running. No reboot, driver change or commit. Local evidence: `reopen_once.log`, `reopen_observation.log`, `observer_transfer.log`.

## 2026-11-11 18:25–18:27 HKT — K3 live precheck FAIL, no valid soak started

- User confirmed VT on and requested acceptance. Actual input resumed 18:24:13 at 1832x1032; POC7 caused kernel 0xf. At 18:24:17 the source switched to 1920x1080 and CAPTURE DQBUF returned EPIPE. Session 3 reused the fd, immediately received SOURCE_CHANGE (0.0 ms), and reported min_buffers_for_capture=1; thereafter USB/Python sustained ~60 AU/s but worker aus_frames remained zero, age=-1 through at least 18:27. MainPID 262680, worker 263148, systemd NRestarts=0. No valid display soak can be counted.
- Read-only code inspection: inner run_socket loop requests POLLPRI but does not consume source-change events; same-fd teardown does not drain queued events. Stale SOURCE_CHANGE/early CAPTURE configuration is a hypothesis, not yet isolated. While VT was off, the 120-second IRAP wait exited twice and Python respawned the worker; this alone does not prove the zero-frame cause.
- Evidence: `.codex_tmp/k3_service_20261111_1807/{live_precheck,zero_frames_diagnostic,zero_frames_status}.log`. No new source/deployment/privileged changes in this diagnostic step. Existing service remains active/enabled. Next requires a user decision: controlled stop/start isolation or a staging worker Source Change fix (outside the earlier promise to leave worker unchanged). Do not mark K3 PASS or infer displayed fps from Python's placeholder frames.

## 2026-11-11 18:19 HKT — K3 installed/enabled, READY; live acceptance pending

- User explicitly approved the shown R3 install/start/stop/enable/rollback scope and confirmed VT off. Staging transfer ~8.6 KB: all checksums matched. Target backoff 30,000-call check and original unit verification RC=0. Installed unit `15ade4bb`, dedicated journal config `f39e019b`, recovery.py `275c91f6`; worker `51346c85` and kiosk.yaml unchanged. Complete 16-file runtime parity verified against local uncommitted K3 tree.
- Remote backup: `/home/billieguo/mobile_vt/.codex_tmp/k3_service_20261111_1807/backup/`; local archive `.codex_tmp/k3_service_20261111_1807/remote_backup.tar`. Install and rollback scripts remain in staging and local evidence. No reboot/kernel/network/boot-target/global-journal changes.
- First start (18:17:40) received 19 stale AUs then no input; worker gated 18 and presented zero. Not live evidence. `systemctl stop` at 18:18:55 took 1.123 s, Result=success, no worker or V4L2/DRM/control device ownership afterward. Enable/start then succeeded: MainPID 262680, invocation `89ce1cafbb8a4118b5b36a4140c68ab0`, active/enabled, NRestarts=0; at 18:19:07 USB source open and waiting for IRAP, zero new data. User notified to enable VT only after this READY.
- Namespace journal is operational (~4 MiB at first check), kernel watcher child alive. Evidence `.codex_tmp/k3_service_20261111_1807/{staging,install,lifecycle,ready}.log` and `post_parity.txt`.
- Pending: human VT-on/visual check, 10 min then total 30 min service soak, physical reboot startup NOT_TESTED, automatic crash-restart not deliberately injected. Service remains running and enabled while waiting. No commits.

## 2026-11-11 18:08 HKT — K3 implementation preflight

- User requested K3 implementation and authorized this session's documented askpass. Scope: service installation/testing; no reboot, kernel, boot target, network or existing decoder/display changes. Exact privileged commands still require R3 confirmation. The old D3d zero-0xf gate remains unmet; RC1 stays ACCEPTED_WITH_LIMITATION.
- PC HEAD `2ba4ff5`, initially clean. Key-only SSH RC=255; authorized askpass `bash -s < preflight.sh` RC=0. CM311: aarch64, 6.18.59-ophub, systemd 255, multi-user.target, LightDM inactive, USB and HDMI available, V4L2/DRM idle. Service is not installed. All 16 runtime Python/config files match PC; worker remains `51346c85`. Remote service draft differs only in comments.
- Local backoff reproduction (1100 calls to `RecoveryController.on_error`) RC=1, OverflowError: a long USB absence could kill the receive thread. Next: minimal saturation fix and tests; service ordering, SIGINT/mixed cleanup, bounded restarts and isolated journal limits.
- Local backup: `/home/billieguo/billie_guo/src/rm/mobile_vt/.codex_tmp/k3_service_20261111_1807/pre_local.tar`, SHA256 `2dfd24da463ac331d1d39ad50bc0af150dc3a94782e342a7a2c75ae767c88a4d`. Evidence in the same directory: `preflight.sh`, `preflight.log`, `backoff_before.log`, pre-change git status/diff/HEAD. Temporary files stay project-local; they include sensitive existing docs and must not be published.
- No remote writes, USB stream, V4L2 streaming, HDMI takeover or wireless operations occurred. No commit/push. Next: offline tests, then explicit R3 install/rollback commands and READY handoff.

## 2026-11-11 18:13 HKT — K3 local implementation, exact R3 approval pending

- Unit: remove multi-user.target ordering cycle and ignored DJI overrides; use Restart=always with 15-second backoff, SIGINT to main Python only (KillMode=mixed), 30-second stop timeout, non-root/NoNewPrivileges, and a dedicated journal namespace. New namespace configuration: volatile 32 MiB total target, 4 MiB per file, one-day retention; no global journald changes. Runtime change is limited to overflow-safe USB backoff (including zero initial delay); decoder worker/YAML unchanged.
- Tests: base pytest 53 passed/38 skipped (RC=0); rm environment lacks pytest (RC=1), so scoped unittest `discover -s tests -t .` ran 91 tests (RC=0). Existing ffplay fallback test logs a join-current-thread exception; no worker K3 code uses that path. Initial unscoped unittest collected legacy hardware `test.py` and failed because the PC has no DJI device (no stream started). Early test temp files used /tmp with automatic TemporaryDirectory cleanup; subsequent tests use this step's test_tmp.
- `systemd-analyze verify` on PC: production unit RC=1 due to CM311-only executable; shadow unit replacing only interpreter RC=0 (unrelated host netplan/snapd warnings). Target systemd 255 supports namespaces; actual target verification pending. `bash -n` install/rollback and `git diff --check` RC=0.
- Evidence: `.codex_tmp/k3_service_20261111_1807/{pytest.log,unittest_rm_scoped.log,unit_verify_pc_shadow.log,payload_manifest.json,install_remote.sh,rollback_remote.sh}`. No target writes/start/enable yet. Next: approve exact install, bounded service stop/start validation, boot enablement and 10–30 min observation; no reboot. All changes uncommitted.

## Final status (2026-11-11 15:00 HKT) — V1 ACCEPTED_WITH_LIMITATION (session closed)

- **User decision**: the working kiosk is accepted with limitations
  (`ACCEPTED_WITH_LIMITATION`); no further optimization on CM311 is required
  now.
- **Final deployed state**: `build/d3/d3_probe 51346c85` (L2-B drain-to-newest),
  Python unchanged (`config.py 1a6160d1`, `pipeline.py 60b7d312`,
  `worker_client.py d03297a6`, `kiosk.yaml d4d155f2`), kiosk config, gate 60,
  recover sleep 0. Backup chain:
  `888118fb` -> `~/.codex_tmp/backup_l2b_20261111_142801/`;
  `f288c28a` -> `backup_r1_20261111_135710/`;
  `21c7f288` -> `backup_gate_20261111_124124/`;
  `4749ed94` -> `backup_greenfix_20261111_114324/`.
- **V1 30 min soak** (`captures/manual_live/soak_l2b_20261111_142851`):
  **107,763 frames / 1800.102 s = 59.86 fps**; 1-s presented p50/p10 = 60,
  0 zero-frame seconds; **0 corrupt/oversize**; **6 rebuilds/`0xf`**;
  visible freeze **200-233 ms (p50 216.7, ~0.07 % of the time)**; internal
  age median **29.7 ms** (per-second p50); CPU 26 %, Python ~0.96 core;
  IRQ vdec/esparser 59.8/s; memory steady ~1.12 GB; 61-72 °C;
  `PIPELINE_RC=0`, idle after exit.
- **Fixes delivered this session**: green curtain/tearing (held fb release
  deferred 5 presents + two-frame display ownership); startup green (primary
  hidden only at the first frame); startup black (60-frame start gate, console
  visible ~1-2 s); R1 freeze (rebuild sleep 100 -> 0 ms, ~366 -> ~217 ms);
  L2-B newest-frame presentation (internal 131.5 -> ~30-32 ms p50).
  L2-A (shrinking the socket queue) was tested and rejected (age worsened).
- **Known limitations**:
  1. `0xf` is content-dependent (not USB/RF); ~6/30 min in this window, each
     rebuild freezes ~217 ms with automatic recovery (no reboot/SSH loss).
  2. Console visible ~1-2 s at startup (start gate hides the startup flash).
  3. A very small eye-visible delay remains; **glass-to-glass is TODO
     (not measured)**; the remaining delay is likely DJI encode/wireless and
     the display panel, not CM311.
  4. L2-B skips at most 2 frames per drain (display only; references intact).
  5. `0xf` driver/firmware root cause unresolved; further freeze reduction is
     a separate driver task (R3).
- **Evidence**: the three reports of this session are archived at
  `.codex_tmp/docs_backup_20261111_lowlatency/`
  (`rc1_baseline_20261110/`, `rc1_replay_20261110/`, `rc1_live_20261111/`,
  each with checksums; see `ARCHIVE_MANIFEST.md`). The original plan remains
  `plans/CM311_DJI_C5_Low_Latency_60FPS_Optimization_Plan.md`.
- **Sync state (2026-11-11 15:42)**: local changes committed as **`a4d82c2`**
  on `rc1-latency-instrumentation` (12 files, clean tree). Runtime Python on
  CM311 synced to that commit: `worker_client.py f227791c`, `nal.py f2de7db7`,
  `decoder.py 5c7460f0`; full `vt13_video/*.py` + `kiosk.yaml` parity check
  passed (`RUNTIME_PARITY_OK`). Backup
  `~/.codex_tmp/backup_sync_20261111_154224/`. Deployed worker `51346c85` was
  built from the same commit's `tools/d3_probe.c` (`8ace8282`). A post-sync
  20 s smoke was inconclusive because the source stopped after 0.47 MB / 21 AU
  (VT link apparently off); the gate kept 0 frames, RC=0, no leftover process.
  **Post-sync live check (15:56, VT on): PASS** — 30 s, `START_GATE` after
  60 frames, **1,745 frames / 30.106 s = 57.96 fps** (includes ~1 s gate),
  0 corrupt, 1 session, RC=0, idle. The remote is still not a git repo; the
  local tools/tests/docs/plan are not mirrored there.
- **Working tree**: uncommitted changes on branch- **Working tree**: clean. `main` is **47ddd08** (fast-forward merge of
  `a4d82c2` + `c19a436` + `47ddd08`); `rc1-latency-instrumentation` points at
  the same commit. **Not pushed.** No commit/push without the user's explicit
  instruction.
- **Future work (not scheduled)**: glass-to-glass L1a, 60 min V2, K3 systemd
  service (R3), driver/firmware `0xf` investigation.

## Current status (2026-11-11 10:25 HKT) — L1 live internal latency measured

- VT link on; instrumented package + worker ran **from staging only**
  (`~/.codex_staging/l1_live_20261111_101319/`), deployed tree unchanged.
- Baseline 180 s (201.6 s of data): source 59.9 AU/s, **11,781 presented frames
  = 58.42 fps**, 18 rebuilds/`0xf`, 0 corrupt, 250 AUs dropped in rebuilds.
- **Internal `AU complete → present`: p50 131.5 ms, p95 160.2, p99 216.8**;
  decomposition p50 = socket 51.8 + decode 49.8 + present 16.5 ms.
  Steady (excluding 0.5 s after rebuilds) 130.8 ms.
- **Present wait = one vblank (16.5 ms) on 99.9 % of frames.**
- **Visible freeze per rebuild: 283.7-367.1 ms** (18 events, p50 ≈317 ms).
- CPU: total 26.4 % of 4 cores; **Python ≈0.95 core** (73 % user + 21 % sys),
  worker ≈3.4 %; iowait ≈0; IRQ vdec/esparser ≈58/s; 59-64 °C; backlog_max 15/17.
- Reporting: `reports/low_latency/rc1_live_20261111/live_results.md` +
  `run_manifest.json` + both run dirs + checksums.
- Operational fix: `kill -INT` is ignored for background jobs in a
  non-interactive shell; launchers now use `--seconds` and wait/TERM.
- Next = L2 (new R2, one variable): age-bound the socket backlog; present the
  newest decoded frame; atomic flip (L3); reduce Python read CPU.
- Not tested: glass-to-glass, DJI-inherent latency, 1832 mode, long soak.

## 2026-11-11 11:10-11:45 HKT — rebuild green curtain fixed and deployed

- User visual: rebuild produced a short freeze, then a **partial black band /
  tearing and a green curtain** (not a full-screen flash).
- Diagnosis: 20 dumped frames (held + first 4 after 4 rebuilds) were complete
  and normal; `primary_fb=0` at every recovery. Root cause: the held frame's
  **Y and UV are separate dmabufs**, and the old code freed them right after the
  first new SETPLANE returned; meson flips can latch 1-2 frames later, so the UV
  plane could be freed while still scanned -> chroma 0 over valid luma (green).
- Fix: defer `held_release()` by **5 presents (~83 ms)**; teardown releases a
  held frame only if a new frame was presented after it, then keeps the current
  scanout. No latency change.
- Confirmed: replay 4 rebuilds + live 90 s 2 rebuilds show **only the freeze**,
  no green/tearing. Deployed `build/d3/d3_probe` `4749ed94` -> `21c7f288`
  (backup `~/.codex_tmp/backup_greenfix_20261111_114324/`); deployed Python
  unchanged. Post-deploy live 60 s: 3,573 frames/59.43 fps, 1 rebuild,
  `VISIBLE_GAP 266.6 ms`, 0 corrupt, RC=0, idle.
- Remaining: the freeze itself (267-728 ms, R1 recovery cost) and the ~130 ms
  internal queue (L2 candidates).

## 2026-11-11 12:30-12:42 HKT — startup gate, final worker deployed

- Added `--start-gate N` (default 60 frames in socket mode): decoded frames are
  requeued without presenting until the current session has survived 60 frames;
  the console is visible until then, then the primary is hidden and video
  starts. The gate resets on an early rebuild and never re-engages once open.
- Replay: the first two sessions presented 0 frames (early `0xf` hidden); gate
  opened in session 3 after 60 frames; later rebuilds stayed live.
- Worker also defers the primary hide to the first present (fixes startup
  green), defers `held_release` by 5 presents (green curtain fix), holds the
  last two presented frames, and requeues N-2 (display ownership).
- Deployed `build/d3/d3_probe` `21c7f288` -> `f288c28a` (backup
  `~/.codex_tmp/backup_gate_20261111_124124/`); deployed Python unchanged.
  Post-deploy live 30 s: 1 early rebuild hidden, 1,722 frames/57.21 fps,
  0 corrupt, RC=0.
- Known limitation: console visible ~1-2 s at startup (hides the startup
  black flash). Remaining: rebuild freeze 267-728 ms (R1), ~130 ms queue (L2).

## 2026-11-11 13:50-13:58 HKT — R1 freeze shortened (sleep removed), deployed

- A/B replay with the same worker: fixed rebuild `usleep(100 ms)` vs 0.
  Mid-run `VISIBLE_GAP` 350/383/367 and 383/317/383 ms -> 283/250/283 and
  250/217/250 ms; `first_frame` 314-375 -> 215-271 ms; `reopened` 211-240 ->
  119-150 ms; 0 corrupt, no new errors (fewer AUs dropped).
- Default `recover_sleep_ms=0`; deployed `build/d3/d3_probe` `f288c28a` ->
  `888118fb` (backup `~/.codex_tmp/backup_r1_20261111_135710/`); Python
  unchanged. Post-deploy live 60 s: 4 rebuilds, gaps 200.0/216.7/216.7 ms,
  3,495 frames/58.14 fps, 0 corrupt, RC=0.
- R1 gate (-25 %) met for the sleep component; remaining freeze ~200 ms.

## 2026-11-11 14:00-14:40 HKT — L2: A negative, B adopted, deployed; soak started

- L2-A (worker `SO_RCVBUF` limit): **negative** — age 128.8/136.7 ->
  163.9/157.3 ms, socket/decode worse; not deployed.
- L2-B (drain to newest, present only the newest): live internal
  `AU complete -> present` **p50 32.3 / p95 50.5 ms** (was 131.5/160.2),
  socket 0.3, decode 17.6, present 13.7; 0 corrupt. Rebuild gap 216.6 ms.
  User: motion follow a bit better, a very small delay remains.
- Deployed `build/d3/d3_probe` `888118fb` -> `51346c85` (backup
  `~/.codex_tmp/backup_l2b_20261111_142801/`); Python unchanged.
- **30 min soak running** (`captures/manual_live/soak_l2b_20261111_142851`,
  started 14:28:51) on the deployed path with 1 Hz /proc sampling; results
  pending. Keep the VT link on during the soak.
- Composition of the remaining delay: ~32 ms CM311 (decode ~17 + vblank ~14 +
  socket ~0.3), plus unmeasured DJI encode/wireless and panel; glass-to-glass
  (L1a) is the next measurement to split controllable vs inherent.

## 2026-11-11 14:28-14:58 HKT — V1 30 min soak: metrics PASS

- Deployed L2-B worker `51346c85`, kiosk config, VT on for 30 min, 1 Hz sampler.
- **107,763 frames / 1800.102 s = 59.86 fps**; 1-s presented p50/p10 = 60,
  0 zero-frame seconds; 0 corrupt/oversize; **6 rebuilds**, visible freeze
  200-233 ms (p50 216.7, total ~1.3 s = 0.07 %).
- Worker age p50 median 29.7 ms; Python 0.96 core; total CPU 26 %; IRQ
  vdec/esparser 59.8/s; memory steady ~1.12 GB; 61-72 °C.
- `PIPELINE_RC=0`; no leftover processes; `/dev/video0` free; refcnt 0.
- V1: frame-rate/correctness/recovery/resources/internal latency PASS;
  **glass-to-glass NOT_TESTED**; known limits: startup console 1-2 s,
  ~217 ms freeze per `0xf`, a very small eye-visible delay. Final visual
  verdict pending (PASS vs ACCEPTED_WITH_LIMITATION).
- Report `reports/low_latency/rc1_live_20261111/V1_soak_results.md`.

## Previous status (2026-11-10 18:30 HKT) — RC1 low-latency plan: L0 PASS

- New plan archived: `plans/CM311_DJI_C5_Low_Latency_60FPS_Optimization_Plan.md`
  (SHA256 `8dfff72e…`). Round 1 = L0 only (read-only audit + measurement design).
- Report: `reports/low_latency/rc1_baseline_20261110/` — `decision.md` (PASS),
  `baseline.json`, `metric_definitions.md`, `latency_path_audit.md`,
  `instrumentation_proposal.md`, `L1_runbook.md`, remote K3/D3d logs, checksums.
- **Metric correction**: `stats.decode.fps` / `decode.frames` count AUs *sent*
  (K3: 107,445), not presented frames. Presented = worker `DECODED` 105,856 /
  1800.087 s = 58.81 fps. 127 rebuilds × 266 ms TTFV explains the whole
  average-fps gap (model 58.87 fps).
- **Audit**: AU completion is only known when the next AU starts (no timestamp
  existed); present uses blocking legacy SETPLANE before requeue (display-paced
  loop, so low `htop` CPU is expected); every rebuild contains a fixed 100 ms
  `usleep`; only 10/127 rebuilds carried `RECOVER` markers (`QBUF CAPTURE` EIO
  was unmarked); no per-frame age/backlog/visible-gap record existed.
- **Prepared (local branch `rc1-latency-instrumentation`, uncommitted, NOT
  deployed)**: `AccessUnit.completed_at`; Python `VT13_LAT_CSV`; worker
  `--lat-csv` with a 32-entry seq FIFO (age/decode/wait/backlog); per-second
  `age_p50/p95/max`; `VISIBLE_GAP` freeze duration; recovery markers on every
  requeue failure; `tools/latency_report.py`; `tools/latency_sampler.py`;
  `.codex_runs/live_latency_l1.sh`. PC gcc build clean, pytest 50/38.
- **Next = L1 (needs R2 approval)**: deploy instrumented worker + Python files
  (backups kept), run one 180 s live baseline per `L1_runbook.md`, optionally a
  240 fps phone glass-to-glass clip. No reboot/service/kernel change.
- CM311 state at L0: idle, `/dev/video0` free, no Xorg, LightDM inactive,
  `multi-user.target`, DJI receiver enumerated; no writes, no live run.

## 2026-11-10 19:00-19:15 HKT — replay validation (R2, no wireless)

- Approved R2 window: ran the **instrumented worker from staging** against
  recorded streams on CM311. Deployed files untouched (`d3_probe 4749ed94`,
  `worker_client.py d03297a6`, `kiosk.yaml d4d155f2`); staging
  `~/.codex_staging/l1_replay_20261110_185859/`; no reboot/service/module.
- **Instrumentation works end-to-end**: 3500+ frames/60 s per run, 0 corrupt,
  `seq_gaps` 4-7 (AU→frame FIFO valid), clean exit, console restored.
- **Recorded "clean" stream reproduces `0xf`**: 4-5 aborts/60 s (same as live)
  from a transport-clean 10.6 Mbps capture → **content-dependent, not USB/RF**.
- **Visible freeze per rebuild: 367-400 ms** (one 733.7 ms outlier), first
  direct measurement.
- **Present waits one vblank**: 12.4-16.4 ms on ~100 % of frames.
- **Age decomposition**: `clean4` (60.0 AU/s) 161.6 ms = socket 63.0 +
  decode 65.7 + present 16.4; `clean5` (59.5) 62.8 ms; `damaged2` (59.5)
  30.8 ms = socket 0.7 + decode 17.8 + present 12.4 → intrinsic floor ~31 ms.
  Queue depth is the dominant variable; live `SO_SNDBUF=1 MB` (~48 AU ≈800 ms)
  is the prime L2 candidate to bound (age-based drop at IRAP), to be measured
  live first.
- **Replay-tool defect fixed**: `d3_replay.split_aus` used to leave VPS/SPS/PPS
  on the previous AU (first IRAP lacked parameter sets → 453 rebuilds/0 frames).
  Now mirrors `AccessUnitAssembler`; validated **1056/1056 AUs identical** on
  `captures/vt13_live_raw.h265`. Sender also honours the worker `R` event.
- Report: `reports/low_latency/rc1_replay_20261110/` (`replay_results.md`,
  `run_manifest.json`, 6 run dirs, checksums). Not tested: live USB/assembly,
  1 MB SNDBUF queue, glass-to-glass, real recovery cadence.

## Previous status (2026-11-10 17:20 HKT) — D3 live kiosk working
**Working configuration** (`config/vt13_video.kiosk.yaml`): `decoder.backend=worker`
(C V4L2/KMS worker), `VT13_ASYNC_USB=0` (must stay off), control on, kernel abort
watch on, `stall_restart_s=0`, no recording, `--hide-primary`.

**Measured**: live 57.8–58.8 fps, 0 corrupt; one rebuild per ~14 s (TTFV ~260 ms),
last frame held on screen during the rebuild (no black flash).
- D3d 3×60 s: 57.80 / 58.02 / 58.49 fps; 8–12 `0xf` per run → strict "0 `0xf`" gate not met.
- K3 30-min soak: 105856 frames / 1800.087 s = 58.81 fps, 128 sessions, 0 corrupt,
  0 oversize; memory 358→359 MiB; 61→67 °C; clean exit.

**Root causes learned**: the raw USB stream is clean (capture-only 10.6 Mbps,
60.3 AU/s, no gaps); the Python async USB reader thread (GIL/scheduling) was the
main `0xf` source and is off; KMS scanout is a secondary contributor. Soft
recovery (STREAMOFF without REQBUFS) does not work — meson-vdec needs a full
reconfigure; taskset affinity has no effect. Residual `0xf` ~0.1–0.2/s is
host-side VDEC/KMS vs xHCI/DRAM contention.

**Plan status**: B0/D3-0/D3a/D3b PASS; D3c PARTIAL (TTFV 260 ms vs target 200,
dynamic resolution untested); D3d PARTIAL (fps PASS, 0 `0xf` FAIL); K3 PASS
(30-min soak; `deploy/vt13-kiosk.service` is a draft, NOT enabled).

**Repo**: synced with the deployed CM311 tree (decoder.py keeps the local codec
identity logging); tests 43 passed / 38 skipped. Docs are exactly three files:
`AGENTS.md`, `docs/INTERSESSION_TRANSFER.md`, `docs/REMOTE_MACHINE_USAGE.md`.
D3 reports are archived under `.codex_tmp/docs_backup_20261110_d3/`.


Status: 2026-11-10 02:55 HKT — **root cause corrected**. Moving the receiver
(USB2 extension, re-enumeration 005→006) did NOT change the failure (3×60 s:
31/32/34 aborts, 243/278/182 frames). A capture-only run with the same receiver
and USB path but NO decoding delivered a clean stream: 76.2 MB/60 s (10.2 Mbps),
60.3 AU/s, max gap 0.17 s, only 2/451 GOPs with POC gaps. The pipeline's clean
1080p replay tops out at **38.5 fps**, below the 60 fps source, so it sustains a
backlog (async queue 15k/16k), the receiver overflows, the stream is damaged and
`0xf` follows. So the damage is pipeline-throughput-induced, not RF/upstream.
Best live result today: async + control disabled = **778 frames/61 s (12.7 fps),
10 aborts, 0 green drops**. An opt-in `VT13_SHED_TO_IRAP` whole-GOP shed block was
tested and then **reverted**; the remote pipeline is back to `c700b8cd...`
(patch script kept in `.codex_tmp/p1_2_shed_20261109/`). Next: raise pipeline
throughput above 60 fps or close the loop on shed-to-IRAP. Both the shed block
(`pipeline.py` `9d0013c2`) and the display cap (`ffmpeg_pipe.py` `edb960c2`) are
opt-in and default-off; the default path is unchanged. S0/S1: per-frame cost is all in ffmpeg/nut/PyAV wait (p50 17.1 ms no-copy); raw
transport lifts clean replay to 65.3 fps but live is unchanged. Display-off + 50%
GOP shed remains best (1530 frames, 2 aborts); ffplay/X11 software rendering is
the biggest reducible load. Best watchable combo: small async queue (2000) +
50% GOP shed + display cap 25 + no-copy + control off = 552/529 frames/60 s
(9.2/8.7 fps), 15/17 aborts, ~3 MiB backlog. Deployed: pipeline `9d0013c2`,
ffmpeg_pipe `b6672def` (all opt-in, default nut/off). **User visual check
(23:30): the default config still updates every few seconds (~5 s lag), while
async ON barely updates — async buffers ~25 MiB (~20 s) of stream, so decoded
frames are stale; async is a diagnostic only, not a viewing path.**
Earlier: P1-1 offline
profiling (clean startup 0.26–0.32 s; post-`0xf` reopen 0.277–0.305 s; 300-frame
rawvideo Copy-Out 38.7 fps vs no-copy 89.9 fps). Earlier: P0-1 A/B/A (ON 31/32
aborts, 267/216 frames; OFF 33 aborts, 225 frames) → requested IDR is not the
`0xf` trigger. Earlier: P0-0 snapshot and baseline metric definitions.
(`journalctl -k -f` → reset + I-frame request). Median recovery is **116 ms**
(60–303 ms) with 0 watchdog waits, but the abort rate rose to **33/min** and
only 166 frames/60 s were produced; each requested IDR dies after a few frames.
That makes the requested IDR/link damage — not recovery latency — the limiting
factor. Hardware clean-sample throughput measured 38.7 fps for 1080p raw output
(no 200 fps reproduced; CPU idle is expected). Display filters keep the window
open and suppress green/grey. Next: a no-request control run to measure natural
abort rate, RF/link mitigation, and POC/missing-AU analysis. Earlier: software
decode ruled out on CM311; runs 5–10; consolidated
progress snapshot in `.codex_tmp/docs_backup_20261110/PROGRESS_20261109.md` (verified capabilities,
deployed hashes, P0 root cause: upstream stream damage → firmware 0xf session
death → IRAP starvation; evidence index, backups, next tracks A/B/C/D).
Nothing committed (user instruction).

### 2026-11-10 17:15 HKT — taskset 亲和实验：无显著收益

- `taskset -c 2,3` 跑 60 s：**3521 帧 / 58.57 fps**、5 会话、0 corrupt；
  dmesg **8 `0xf` / 4 abort**，与未绑核（8–12 次）无差异。
- 结论：CPU 亲和不是残余 `0xf` 的杠杆；属 DRAM/中断级，需驱动/IRQ 改动或接受。
- 证据 `captures/manual_live/d3d_taskset_20261110_171535`。未 reboot。未 commit。

### 2026-11-10 16:39–17:13 HKT — D3d 3×60 s + K3 30 分钟 soak

- D3d 三轮（`config/vt13_video.kiosk.yaml`，无录制）：**57.80 / 58.02 / 58.49 fps**、
  0 corrupt、RC=0；每轮 5–7 会话；每轮 8–12 `0xf` → 计划“0 `0xf`”Gate 未达。
- K3 soak 1800 s：**105856 帧 = 58.81 fps**、128 会话（每 ~14 s 一次）、0 corrupt、
  0 oversize、RC=0；内存 358→359 MiB、温度 61→67 °C、退出无残留。
  soak 的 dmesg 差分因 ring 回绕低估；以会话数计重建。
- K3 草案：`config/vt13_video.kiosk.yaml`、`deploy/vt13-kiosk.service`（draft，不启用），
  commit `f43d463`。
- 结论：长时稳定性 PASS；残余 `0xf` 是 D3d 唯一未达 Gate。
- 证据 `captures/manual_live/d3d_k3_20261110_163945/`。未 reboot。未 commit。

### 2026-11-10 16:34 HKT — 无录制 A/B：录制不是剩余抖动主因

- async OFF、60 s、无 `--record`：**3492 帧 / 60.065 s = 58.14 fps**、6 会话、
  corrupt=0；dmesg **10 `0xf` / 5 abort**，与带录制根盘运行（10–16 次）相同。
- soak 的 20 次/600 s 属窗口波动；剩余 `0xf` ≈0.17/s、每次 ~260 ms，约占 4% 时间。
- 软件侧优化到此为止；继续需 IRQ/CPU 亲和（root）、rmrx（收益不确定）或驱动修改。
- 证据 `captures/manual_live/d3c_norec_20261110_163408`。未 reboot。未 commit。

### 2026-11-10 16:28–16:32 HKT — soft recovery 失败并回滚

- 尝试 0xf 后不 REQBUFS、仅 STREAMOFF→QBUF→STREAMON：STREAMON 成功但无帧，
  meson-vdec abort 后必须完整重配。
- 首版回退逻辑 bug 导致 101 次 soft 循环（60 s 仅 15 帧）；已回滚
  `tools/d3_probe.c` 到 c9c76eb；30 s 验证 1697 帧/56.43 fps、6 会话、干净退出。
- 结论：TTFV 181 ms 是驱动固有成本，p50≤200 ms 在当前驱动下不可达。
  继续压缩只能减少 abort 次数（IRQ/CPU 亲和、rmrx）或改驱动。

### 2026-11-10 15:17–15:29 HKT — 恢复优化与 TTFV 埋点

- worker 复用同一 V4L2 fd（STREAMOFF→S_FMT/REQBUFS，失败才 reopen）；检测到
  POLLERR/DQBUF EIO 时 socket 发 `R`，Python 立即请求 I-frame，与重建重叠。
- TTFV 分阶段：reopen **181 ms**、等 IRAP 28 ms、17 buffer 导出 35 ms、首帧 18 ms，
  合计 **260–265 ms**（优化前 282 ms）。`reused fd` 未回退，说明 181 ms 是驱动
  abort 后重配成本。计划目标 p50≤200 ms 未达。
- 吞吐 57–58 fps、0 corrupt、退出干净。证据 `captures/manual_live/d3c_ttfv*`。
- 下一步可选：soft recovery（不 REQBUFS）/预开备用 fd/接受当前值。

### 2026-11-10 15:05 HKT — 部署基线回流：本地与 CM311 一致

- 远端非 Git，kiosk/async/shed/damage/ffmpeg_pipe 改动此前仅在现场。本次以部署为准：
  `config.py 1a6160d1`、`pipeline.py 75071b00`、`ffmpeg_pipe.py 0936da17`、
  `async_usb.py d5b52faa`、launcher `e5f73157`、`control.py cc0cbcdc`；
  `decoder.py` = 部署 `0a63d896` + 本地 codec 身份日志 = `5c7460f0`。
- 新增 `config/vt13_video.no_status.yaml`、`config/vt13_video.yuvtest.yaml`。
- 本地测试 43 passed / 38 skipped / RC=0；备份
  `.codex_tmp/sync_20261110/local_backup.tar`（`8410cc9d…`）。
- 政策：本地仓库为唯一代码来源；部署改动必须回流并提交。

### 2026-11-10 14:44–14:54 HKT — 10 分钟 soak：PASS

- 配置：`DJI_BACKEND=worker`、async OFF、control on、kernel watch on、stall 0、
  无录制、显示由 worker 接管。
- 结果：**35226 帧 / 600.112 s = 58.70 fps**、45 个会话、`corrupt=0`、
  `oversize=0`、`errors=0`、`dropped_aus=0`、`PIPELINE_RC=0`。
- dmesg：**20 `0xf` / 10 abort / 4 缺参考**（约每 30 s 一次损伤，重建后恢复）。
- 内存 376→365 MiB（无增长）；温度 59→66 °C；退出无残留。
- 待优化：重建闪烁/0.1–0.2 s 停顿、剩余 0xf 抖动、30 min soak/服务化。
- 证据 `captures/manual_live/soak_20261110_144438/`。未 reboot。未 commit。

### 2026-11-10 14:39 HKT — 用户验收：live 基线可接受，闪烁/停顿后续优化

- 60 s 复跑：**3487 帧 / 60.066 s = 58.05 fps**、6 会话、corrupt=0、errors=0；
  dmesg 10 `0xf`/5 abort；退出干净。
- 用户确认画面质量可接受；重建闪烁与 ~0.1–0.2 s 停顿列为后续优化。
- 推荐配置：`DJI_BACKEND=worker`、async OFF、control on、kernel watch on、stall 0。
- 待优化：held fb 释放时机/双缓冲；0xf 后 STREAMOFF→STREAMON 免 close/reopen；
  缩短等 IRAP；剩余 0xf 抖动（IRQ/CPU 亲和或 rmrx）；10 min soak + 服务化。
- 证据 `captures/manual_live/d3c_show2_20261110_143809/`。未 reboot。未 commit。

### 2026-11-10 14:35–14:36 HKT — 最佳 live：59.22 fps，单会话、0 0xf

- 修复重建闪屏：`session_close` 把正在 scanout 的 buffer 移入 `held`，新会话第一帧
  上屏后才释放，重建期间屏幕保持最后一帧。
- live 45 s（worker、async OFF、control on）：**2671 帧 / 45.106 s = 59.22 fps**、
  **sessions=1**、corrupt=0、errors=0、resets=0；dmesg **0 `0xf`/0 abort**；退出干净。
- 同配置各轮 0xf 波动大（6–78），本轮是完全干净样本；`held` 修复未在本轮触发。
- 构建 `d3_probe.c c4203cb6` → 板端 `87da0d9e`。
- 证据 `captures/manual_live/d3c_noflash_20261110_143507/`。未 reboot。未 commit。

### 2026-11-10 14:27–14:28 HKT — 决定性 A/B：async 读取线程是损伤主因，关闭后 58 fps

- 同一 worker+显示配置，仅 `VT13_ASYNC_USB=1→0`：
  **2330 帧 / 40.129 s = 58.06 fps**、5 个会话、corrupt=0；
  dmesg **6 `0xf` / 4 abort / 12 缺参考**。
- 对比 async ON：44.8 fps/34 会话/34 `0xf`（45 s）、38.9 fps/46 会话/78 `0xf`（shm）。
- 结论：Python async 读线程与解析/发送线程的 GIL/调度竞争延迟 USB 读取 →
  接收器 FIFO 溢出 → `0xf`；单线程读→解析→发送反而干净。
  修正此前“显示占大头”的判断：async 是更大因素，显示有次要影响。
- 推荐 live 配置：`DJI_BACKEND=worker`、async OFF（默认）、control on。
- 证据 `captures/manual_live/d3c_noasync_20261110_142750/`。未 reboot。未 commit。

### 2026-11-10 14:16–14:21 HKT — 关键 A/B：原始流干净，0xf 是主机侧自激

- 只抓取不解码 60 s：**79.34 MB / 10.6 Mbps**、max gap 0.01 s、0 个 ≥100 ms 间隔、
  **3616 AU = 60.3 AU/s**、452 IRAP 全部带 VPS/SPS/PPS、无异常参数集
  → 射频/上游完全干净（推翻上一轮“输入损伤”结论）。
- 解码不显示（`VT13_WORKER_NO_DISPLAY=1`）40 s：**2288 帧 = 57.06 fps**、8 会话、
  0 corrupt；dmesg 12 `0xf`/7 abort/3 缺参考。
- 解码 + KMS 显示 45 s：44.78 fps、34 会话；dmesg 34 `0xf`/18 abort/82 缺参考。
- 结论：`0xf` 由主机侧负载诱导，KMS 扫描输出占大头；去掉显示后 0xf 约 1/3、fps 57。
  剩余指向 VDEC/KMS DMA 与 xHCI 共享 DRAM/中断延迟，或 Python 读线程调度。
- 证据 `captures/manual_live/caponly_20261110_141622/`、`d3c_nodisp_20261110_141920/`。
  未 reboot。未 commit。

### 2026-11-10 14:12–14:13 HKT — D3c-lite：worker 内重建，44.8 fps

- worker 遇 `POLLERR`/EIO 不再退出：关闭 V4L2 会话、保留 socket/DRM、丢弃非 IRAP AU、
  等下一个 IRAP 后原地重开；Python `reset()` 对存活 worker 改为 no-op，
  并把 `bootstrap` 参数集前缀到 IRAP AU。
- live 45 s：**34 个会话、2018 帧 = 44.78 fps**、corrupt=0、oversize=0；
  pipeline `resets=31`、`errors=0`、`dropped_aus=0`；`STREAM_EXIT_RC=0`，退出无残留。
- 对比进程级重启：每次冻结从 ~1 s 降到 ~0.1–0.2 s，画面基本连续。
- 剩余限速：上游损伤 ~0.75 `0xf`/s（位置未变，VT 重启后仍存在）。
- 构建：`d3_probe.c 756b3e02` → 板端 `9ad1fb16`；`worker_client.py 93a7087a`。
- 证据 `captures/manual_live/d3c_recover_20261110_141200/`。未 reboot。未 commit。

### 2026-11-10 14:00–14:06 HKT — D3b 管线集成 live：链路 OK，输入损伤是唯一限速项

- 新增 `vt13_video/worker_client.py`（opt-in `decoder.backend=worker`）；部署
  `config.py 25004fb8→1a6160d1`、`pipeline.py 4f129217→75071b00`、
  `worker_client.py 7929f009`、launcher `e5f73157`（`DJI_BACKEND`），
  备份 `~/.codex_tmp/backup_worker_backend_20261110_1400/`。
- live 40 s（async 2000）：USB **2287 AU/40 s ≈ 57 AU/s**；worker 每会话
  **60.3–60.5 fps**；但 dmesg **30 `0xf` / 17 abort / 64 缺参考**，每个会话约 1 s
  被 EIO 终止并重启（2 次）。退出无残留。
- `frames_decoded` 现为 AU 计数（合成 Frame），真实解码数以 worker `DECODED` 为准。
- 结论：worker/显示路径正常；剩余问题是上游输入损伤 ~0.75 `0xf`/s。
  下一步 D3c 进程内恢复 + RF/链路排查。未 reboot。未 commit。

### 2026-11-10 13:54–13:57 HKT — D3b 阶段 1：离线 AU socket 回放 PASS

- 新增 `tools/d3_replay.py`（AU 服务端：Annex-B→AU，`SOCK_SEQPACKET`，24 B 头 +
  一个 AU，60 AU/s，背压丢非 IRAP）与 `d3_probe --socket` C worker（复用 D3a 路径）。
- 结果：300 AU / 5.001 s = **60.00 AU/s，发送端 0 丢弃**；worker 解码 **299 帧**，
  稳态 **60.2–60.6 fps**，corrupt=0、oversize=0；dmesg **0 `0xf`/0 abort/0 缺参考**；
  收尾干净。
- 构建：`tools/d3_probe.c` `c5db1467…` → 板端 `5a23fa8b…`；`d3_replay.py` `dfbbe424…`。
- 报告 `.codex_tmp/docs_backup_20261110_d3/D3b_report.md`。未完成：管线 opt-in 集成、live、EOS/动态分辨率/
  `0xf` 状态机。未 reboot；本轮无无线图传。未 commit。

### 2026-11-10 13:45–13:46 HKT — kiosk live 验证：画面可见（lag + flash 仍在）

- 用户开启 VT；`live_capture_run5.sh`，`display=kms`、`--hide-primary`、
  async 2000 + 50% GOP shed + 限帧 25 + no-copy + control off，45 s。
- 结果：**570 帧 / 45 s = 12.7 fps**；`resets=10`（全为 `kernel_0xf`）、
  `dropped_frames=144`、`display_dropped=5`、`keyframe_starts=11`、`IRAP=279`。
- USB async **backlog 3.1–3.7 MiB（queue 2000/2000，约 3 s 流）** → lag ≈3 s。
- dmesg 窗口：0xf=20、abort=10、0x8=108、POLLERR=0。
- 用户目视：**live VT 画面可见**，但卡顿与闪烁。闪烁来自 10 次 0xf 复位
  （每次冻结到下一 IRAP）+ dumb 单缓冲与 scanout 同时读写的撕裂。
- 根因仍是 Python/nut 路径 12–17 fps < 60 fps 源；D3a 已证 C 解码 271 fps，
  **D3b（C worker）是正解**。
- 证据 `captures/manual_live/d3_live_20261110_134503/`。未 reboot、未开无线图传。未 commit。

### 2026-11-10 12:15–13:45 HKT — kiosk 显示修复：overlay 被控制台覆盖（--hide-primary）

- 根因：overlay zpos=0、primary（控制台）zpos=1；部署的 `kms_render --stdin --dumb`
  从不关 primary，所以 SETPLANE 成功但屏幕一直是控制台。用户已目视确认关掉 primary
  后彩条可见。
- `tools/kms_render.c` 新增 `--hide-primary`：识别 primary plane → `SETPLANE(fb=0)`；
  退出 `DROP_MASTER` 由 fbdev 恢复控制台。源码 `fbd8c439…`，板端 binary `a071cfed…`；
  旧 binary `fbb208d7…` 备份于 `~/.codex_tmp/backup_kms_hideprimary_20261110_1200/`。
- 部署 `vt13_video/ffmpeg_pipe.py` 加 `--hide-primary`：`67a40898→0936da17`，
  同目录备份，`py_compile` RC=0。
- 渲染器验证：lavfi 90 帧（12.86 fps）、软件解码真实内容 120 帧/240 帧（24 fps）
  均正常消费、干净退出、控制台恢复。
- **绿幕原因**：上一轮 ffmpeg 用 `-frames:v 600` 超过文件实际 ~430 帧，卡在已知 EOF
  drain 并占用 `/dev/video0`；渲染器收到 0 帧，dumb buffer 全零 NV12 → 绿色。
  不是格式/plane 错误。`-f rawvideo` 管道本身也不稳定（与 raw transport 旧记录一致），
  kiosk 仍走 nut。
- 待办：live 验证（需要 VT/USB）。未 reboot、未开无线图传。未 commit。

### 2026-11-10 12:06–12:12 HKT — D3a（文件）PASS：dec 271.6 fps / present 60.12 fps

- 构建 `tools/d3_probe.c` `5ba4af69…` → 板端 `126acd1c…`；输入 `segB_irp1080.h265`（431 AU）。
- **D3a-dec**：240 帧 / 0.884 s = **271.60 fps**，0 corrupt，RC=0（Gate ≥75 / 目标 90）。
- **D3a-present**：`--hide-primary`，240 帧 / 3.992 s = **60.12 fps**，0 corrupt，RC=0
  （阻塞 SETPLANE 每帧一次 vblank，60 Hz 是面板上限；解码余量约 4.5×）。
- dmesg 时间窗：**0 `0xf`、0 abort、0 缺参考、0 POLLERR**；`status=0x8` 约 0.95/帧
  （over=0，非致命）。仅第 0 帧做过 SW/HW 逐字节对照，未做 240 帧全量 MD5。
- 工程结论：AU 级喂流必需（单 NAL 会在 2 帧后停住）；17 buffer = DPB16+1 足够；
  显示必须 `--hide-primary`。
- 收尾：overlay 释放、控制台恢复、`refcnt=0`。报告 `.codex_tmp/docs_backup_20261110_d3/D3a_report.md`。
- 未测时间戳节拍/动态分辨率/EOF/live USB；未 reboot、未改部署文件、未开无线图传。未 commit。

### 2026-11-10 11:38–11:50 HKT — D3-0 实机执行：真实 VDEC DMA-BUF → KMS PASS

- 用户批准 R2；探针 `tools/d3_probe.c` `7d4eaab4…`，板端 binary `1c196647…`。
- **T1 1832×1032**（`clean_1832x1032.h265`）：34 NAL chunks、20 CAPTURE buffers 全部
  `EXPBUF`→`PRIME`→`ADDFB2`（fb 49–68）、1 帧、HOLD 10 s、RC=0；硬件 dump MD5
  `00221868…` 与软件解码**逐字节一致**；画面为标准彩条（颜色顺序/UV/无错行均正常）。
- **T2 1920×1080**：`segB_clean.h265` 首帧是 TRAIL_R POC34（缺 POC33，软件解码同样报
  `Could not find ref with POC 33`）→ 绿屏，属输入起点问题。从流内唯一 IRAP（NAL index 8）
  连同 VPS/SPS/PPS 重切 `segB_irp1080.h265`（`c7f5da00…`），用 `--cap-bufs 17` 后
  1 帧 POC0 起解，dump `35b75b16…` 与软件解码**逐字节一致**；画面为真实 DJI 室内场景。
- **CMA 约束**：`CmaTotal=256 MB`，空闲约 106–115 MB；请求 20 个 1080p buffer 时驱动只分配
  12 个但 `num_dst_bufs` 仍记 20 → `STREAMON` EINVAL。新增 `--cap-bufs`，17=DPB+1 通过。
- **执行中修复**：首轮把文件切成 2 个大 chunk 一次喂入，解码器跑在用户态之前、DPB(16) 耗尽
  → `can't match offset` / `No dst buffer available` / `Aborting decoding session`（332164）。
  改为按 Annex-B NAL 分块 + 主循环回收 OUTPUT 后消除。
- **收尾已核**：overlay `crtc=0 fb=0`、primary `crtc=45 fb=47`、`video0 free`、
  无 master holder、`refcnt=0`；通过的两轮 dmesg **0 次 `0xf`、0 次 abort**
  （本 boot 唯一 abort 是修复前首轮）。
- **用户已目视确认**（11:50）：两次 10 s 保持期间 HDMI 分别显示彩条与 DJI 画面。
  → D3-0 全项 PASS。未测连续轮转（D3-0b）、动态分辨率、EOF、live USB。
- 证据：`~/.codex_tmp/d3_0_20261110_112758/`（`run_1832.log`、`run_1080_irp.log`、
  `dump1832/`、`dump1080/`、`segB_irp1080.h265`）；报告 `.codex_tmp/docs_backup_20261110_d3/D3-0_report.md`。
- **12:05 关键发现**：overlay zpos=0、primary（控制台）zpos=1；两者同时活跃时控制台
  覆盖视频。`SETPLANE(overlay)` 成功且 DRM 状态正确，但屏幕仍是控制台。必须
  `--hide-primary` 关掉 plane 39 才能看到画面（用户 120 s 目视确认彩条）。
  → 部署的 `kms_render --stdin --dumb` 从不关 primary，此前“KMS 10.8 fps 可看基线”
  并未被目视证实，需要回写 kiosk/D3b 设计。退出 `DROP_MASTER` 后控制台恢复已复验。
- 未 reboot、未改部署文件、未开无线图传。未 commit。

### 2026-11-10 11:10–11:50 HKT — B0 环境盘点 + D3-0 源码审计/设计（只读）

- 只读访问 CM311（askpass）。`armbian` / aarch64 / `6.18.59-ophub`；4 核 1.7 GiB；
  `/dev/sda2` 101 G 可用；boot_id `779b73da-…`；cmdline `video=HDMI-A-1:1920x1080@60e`。
- **显示占用状态变化**：无 Xorg、LightDM inactive、`multi-user.target`、DRM master
  无人持有；HDMI-A-1 connected+enabled+dpms On；fb0 `mesondrmfb` 1920×2160。
  → P2-2 记录的 “Xorg 持有 master” 阻塞在当前状态不存在。
- `/dev/video0` = `meson-video-decoder`，无 opener，`meson_vdec` refcnt=0；CAPTURE 仅
  `NM12`；`ENUM_FRAMESIZES` 无返回；`G_PARM` EINVAL；板端有 `/usr/include/drm/*.h`
  但无 libdrm-dev，`modetest` 缺失 → 探针用裸 ioctl、不链接 libdrm。
- **版本一致性偏差（重大）**：远端 `~/mobile_vt` 非 Git；`config.py 25004fb8`、
  `ffmpeg_pipe.py 67a40898`、`pipeline.py 4f129217`、`decoder.py 0a63d896` 与本地 HEAD
  `3e3e1a6`（`f47c7d9b/871af9b2/33ab8e85/4d1205c9`）**均不同**；kiosk KMS 路径只在远端。
  已镜像 5 个文件 + `kms_render` 二进制到 `.codex_tmp/b0_inventory_20261110/remote/`，
  SHA256 与远端逐项相符；**远端 tar 快照未做**。
- **`tools/kms_render.c` 审计**：默认模式做 S_FMT/REQBUFS(1)/EXPBUF/PRIME/ADDFB2 后写
  测试图案，**从不 STREAMON/QBUF/DQBUF**；部署实际是 `--stdin --dumb`（CPU 拷贝进
  dumb buffer、SETPLANE 只调用一次、持续覆写正在 scanout 的内存，无 page flip）。
  因此“EXPBUF/PRIME/ADDFB2 成功”只是组件级证据，**真实解码帧 → KMS 尚未验证**。
- 交付：`.codex_tmp/docs_backup_20261110_d3/B0_environment_inventory.md`、`.codex_tmp/docs_backup_20261110_d3/baseline_manifest.json`、
  `.codex_tmp/docs_backup_20261110_d3/B0_go_nogo.md`、`.codex_tmp/docs_backup_20261110_d3/D3-0_design.md`；D3 计划原文入库
  `plans/CM311_D3_Native_V4L2_KMS_Execution_Plan.md`（`ea243a23…`）。
- 新增 `tools/d3_probe.c`（`7d4eaab4…`）：file→stateful V4L2→真实 NV12M CAPTURE→
  EXPBUF/PRIME/ADDFB2→overlay，阻塞 SETPLANE + 只回队“上一个”buffer；PC 编译 RC=0。
- **D3-0 准备完成（11:28–11:35）**：远端快照 `~/.codex_tmp/backup_d3_20261110_112758/`
  （`deployed.tar` `0ed6e107…`）；暂存源码 `7d4eaab4…`；板端构建 RC=0（binary
  `86641a49…`，aarch64，仅 libc；后续修复版 `1c196647…`）；只读 `--inventory` RC=0（未取 master、未 stream）。
  自检修复：`GETRESOURCES` 未清 `count_encoders/count_fbs` → EFAULT；未设
  `UNIVERSAL_PLANES` 只看到 overlay。运行时平面：primary 39（crtc 45、fb 47）、
  overlay 42（NV12）。运行目录 `~/.codex_tmp/d3_0_20261110_112758/` 内含
  `READINESS.txt`、`commands.sh`（`9f7f3231…`）、`inventory.txt`、`prestate.txt`。
  **显示测试（T1/T2）未执行，等待 R2 批准。**
- B0 Gate = **CONDITIONAL PASS**：设计可继续；D3-0 实机测试需 R2 批准，并建议先补
  远端快照。未接管 DRM master、未启动 V4L2 流、未改远端文件、未重启、未开无线图传。
- 证据：`.codex_tmp/b0_inventory_20261110/{cm311_readonly.txt,cm311_drm_v4l2.txt,cm311_samples.txt,remote/}`。
- 未 commit。

### 2026-11-10 01:15–01:30 HKT — Kiosk K1/K2：KMS 直显验证（无 Xorg）

- **K1 渲染器**（`tools/kms_render.c`，远端 `.codex_tmp/kiosk_20261110/kms_render`，
  SHA256 `d3dc2d6e...`）：取 DRM master、自适应读取当前 CRTC mode、枚举 connector/
  plane、NV12 overlay、信号退出时清 plane + drop master。
  - 第一次运行（lightdm 已停）：读到 **当前模式 1920×1080**，测试图 45 s
    `PLANE_ON fb=48`，干净退出 RC=0。
- **K2a 真实码流**：ffmpeg（no-copy）→ rawvideo → `kms_render --stdin --dumb`：
  干净 498 帧 **6.0 s = 83 fps**，`STDIN_DONE frames=498`。
- **K2b 管线集成**：`decoder.display: kms`（`config.py` `f47c7d9b→25004fb8`；
  `ffmpeg_pipe.py` `b6672def→67a40898`；备份
  `~/.codex_tmp/backup_kms_20261110_ffmpeg_pipe.py`）；渲染器用 **dumb buffer**
  （`ADDFB2 NV12` 已验证），不占用 `/dev/video0`。
  - KMS1（不丢 GOP、不限帧）：610 帧/61 s=10.0 fps、27 次 0xf、AU 42/s。
  - KMS2（限帧 25 + 丢 50%）：**659 帧/60.9 s=10.8 fps、15 次 0xf、AU 48.5/s、
    read gap 0、绿/半绿 3/3**；同条件 ffplay 对照 ASMALL2：529 帧/8.7 fps/17 次。
    → KMS 直显比 X11+ffplay **约 +25% 帧、略少 abort**，但仍受解码/管道拷贝限制。
- **系统状态**：lightdm 已 stop、enable 链接已移除（unit 为 static），
  default=`multi-user.target`；HDMI 无渲染器时为文字终端；SSH 正常。
  恢复桌面：`sudo systemctl start lightdm`（需 sudo），必要时 `chvt 7`。
- 回滚：恢复 `ffmpeg_pipe.py` 备份/`config.py` 哈希，`systemctl set-default
  graphical.target && systemctl start lightdm`。
- 未 commit；未装包；未改内核/模块。
- 下一步：K3 systemd 服务 + K2c DMA 零拷贝；方案交付
  `.codex_tmp/docs_backup_20261110/dma_optimization_plan.md`（D1 kms-direct 旁路 Python → D3 自定义 V4L2
  客户端 dmabuf→KMS 零拷贝；实测 renderer 拷贝 ~1 ms/帧，Python/nut ~3–6 ms/帧；
  live 仍受输入损伤/reset 限制）。

### 2026-11-10 00:40–00:42 HKT — U4-lite：录制放 /dev/shm vs USB rootfs

- 目的：U0 发现 rootfs 与 DJI 共用 xhci 控制器；验证“录制写 rootfs”是否影响
  live。配置与 ASMALL2 完全相同（async 2000 + 丢 50% + 限帧 25 + no-copy +
  关控制 + iframe on connect/recovery），仅把 `DJI_RUN_DIR` 放到 `/dev/shm`。
- 结果：**541 帧、14 次 0xf、AU 45.8/s、输入 7.3 Mbps、read gap 4 次**；
  对照 ASMALL2（rootfs 录制）：529 帧、17 次、AU 47.6/s、backlog ~3 MiB。
  → **无显著差异；rootfs 写回不是当前 live 的限制因素。**
- 结论：U4 受控 A/B **不需要启动**（没有存储干扰证据）；保留“未来 live 可把
  录制放 /dev/shm”作为无成本卫生措施。测试数据已从 /dev/shm 清理。
- 未改系统配置/未重启/未装包。

### 2026-11-10 00:38–00:40 HKT — P2-2 显示路径只读探测

- 交付：`.codex_tmp/docs_backup_20261110/p2_2_display_feasibility.md`；证据
  `.codex_tmp/p2_2_display_probe_20261110/probe.txt`。
- V4L2：`meson-vdec` m2m multiplanar；CAPTURE 仅 `NM12`（NV12M）；
  两队列 `io_modes = VB2_MMAP | VB2_DMABUF`；CAPTURE 为 `vb2_dma_contig`。
- DRM：`meson-drm`（GXL VPU）；**overlay 平面支持 `DRM_FORMAT_NV12`**
  （`meson_overlay.c:580`）与 YUV420；平面代码支持 src/dst 缩放（文档 5×，
  1080p→1024×576 为缩小，需运行时验证）；primary 平面仅 RGB。
- **EXPBUF 运行时验证（R1，C 探针）**：`/dev/video0` S_FMT HEVC→NM12
  1920×1080，REQBUFS 4（MMAP，caps=0x15），4 个缓冲 × 2 平面
  **VIDIOC_EXPBUF 全部成功**（fd 导出，len 2,088,960 / 1,044,480，stride 1920）
  → 解码 CAPTURE dmabuf 导出可行。探针源码/二进制
  `.codex_tmp/p2_2_expbuf_20261110/`（远端同名目录）。
- **DRM 运行时验证（R1，裸 ioctl，无 libdrm）**：
  - `GETPLANERESOURCES`：card0 仅 **1 个 plane**，formats 含
    `NV12/NV21/YU12/YUYV/...` → overlay NV12 运行时确认；
  - `PRIME_FD_TO_HANDLE`（Y/UV 两 fd）+ `ADDFB2`（NV12 1920×1080）
    **成功创建 fb_id=49** → dmabuf→DRM framebuffer 端到端可用。
  - 探针：`.codex_tmp/p2_2_expbuf_20261110/{expbuf_probe.c,planes_probe.c,prime_probe.c}`。
- **PoC 阻塞项**：① `libdrm` 只有运行库、**无头文件**（不擅自 apt install）；
  ② Xorg 在 tty7 持有 DRM master，第二进程不能设置 overlay 平面，需要
  `chvt` 切到空闲 VT 并接管 master（会影响 HDMI/X，属 R3 级操作，需单次批准）；
  ③ 备选：安装 libdrm-dev（需批准）或写裸 ioctl（struct 定义多、风险高）。
- `modetest` 未安装（不擅自 apt install）。
- 可行性：NV12 overlay + 硬件缩放架构上可行；`VIDIOC_EXPBUF` 尚未运行时验证；
  DRM master 被 Xorg(tty7) 占用，是 PoC 的主要架构障碍。
- PoC 计划：① R1 运行 EXPBUF 探测（REQBUFS+EXPBUF，不 streaming）；② R2 DRM
  overlay 测试；③ 先做“pipe NV12 → dumb buffer → overlay（硬件缩放）”，再做
  “dmabuf → DRM PRIME”零拷贝。Gate：显示开启 live ≥25 fps、0–3 次 0xf、无绿屏/
  撕裂，ffplay 保留为回退。
- 风险：改 KMS/模式可能影响 HDMI/X11；DRM master 需要 VT 切换或接管；均需 R2，
  不做 R3。
- 未 streaming/未改显示/未装包。

### 2026-11-10 00:34–00:38 HKT — damage-aware GOP gate（opt-in）实现与离线验证

- 远端 `pipeline.py` 新增 `VT13_DAMAGE_GATE=1`（默认关）：解析 SPS/PPS/slice POC，
  非 IRAP AU 的 POC 不等于 prev+1（模 LSB）时，跳过该 GOP 直到下一个 IRAP；
  解析失败自动回退正常喂流。`pipeline.py` `9d0013c2 → 9ada66df`；备份
  `~/.codex_tmp/backup_damagegate_20261110/`。
- 性能修正：初版对每个 slice 全量 unescape（~20 KB/帧）导致干净 replay 从
  58.5 掉到 18.8 fps；改为只解析头部 64 B 后恢复 **58.27 fps**（开销可忽略）。
- 离线验证：
  - 干净 498 帧：497 帧、0 误报、`skipped_access_units=1`、58.27 fps。
  - B1（管线录制的损坏流）：检出 21+ 次 POC 断链，490 AU 被跳过，**0 帧**、
    RC=1。原因：B1 几乎每个 GOP 的首个 P 帧就断链，gate 只能整段跳过；IDR
    单独不足以让 v4l2m2m 输出帧。**这是“输入已严重损坏”的必然结果，不是 gate
    逻辑错误。**
- 结论：gate 适合作“偶发损坏”场景的精准丢弃；当前 live 流的损伤频率太高，
  必须先解决输入/吞吐（显示负载、积压），gate 才能体现价值。
- 远端现状：`VT13_DAMAGE_GATE` 默认关，默认路径不变；`pipeline.py 9ada66df`、
  `ffmpeg_pipe.py b6672def`。未 reboot/重载模块；未新 live。

### 2026-11-10 00:33–00:35 HKT — U3 `0xf`/padding 分层表

- 交付：`.codex_tmp/docs_backup_20261110/0xf_layer_matrix.md`（L1 USB/VT13 → L2 AU → L3 esparser/边界 →
  L4 firmware/driver → L5 FFmpeg；`0xf` 类型 A/B/C）。
- 关键判定：
  - **L1 输入损伤是主因**：只抓取 60 s 干净（60.3 AU/s、2/451 GOP 缺口）；
    管线录制流 25% GOP 有 POC 缺口。损伤由主机侧读取滞后/背压诱导。
  - L3 边界敏感：pad≥512 B 使 `0xf→0x8`，但 36/38 帧不完全一致，属诊断
    workaround，不是正确性修复。
  - L4 firmware 只在参考链不完整/损坏样本上中止；clean 1832/1080p 样本无
    `0xf`；v7 上游系列的 FIFO-full 死锁是另一类问题。
  - L5 FFmpeg Copy-Out 不能阻止 `0xf`；新 open 0.28–0.30 s。
- 类型：A 缺参考 GOP（POC21/POC50/live POC5/7/24/269）；B 边界/padding
  敏感（Packet81 sweep）；C 1080p 高码率节奏（管线欠载导致更频繁损伤）。
- 下一步可执行项：**damage-aware GOP gating**——检测 POC 不连续后跳过该
  GOP 到下一个 IRAP（比当前固定 50% 丢弃更精准）；其次把录制放 `/dev/shm`。
- 未改设备/未 live。未 commit。

### 2026-11-10 00:32–00:34 HKT — U2 FFmpeg V4L2 生命周期与 Copy-Out 对照

- 交付：`.codex_tmp/docs_backup_20261110/ffmpeg_lifecycle_comparison.md`；本地 diff
  `.codex_tmp/u2_ffmpeg_audit_20261110/local_ffmpeg.diff`。
- 本地树：FFmpeg n6.1.1 HEAD `e38092ef`，修改 3 文件（`v4l2_buffers.c` +26/−4、
  `v4l2_m2m.c` +47、`v4l2_m2m_dec.c` +60）；上游 `v4l2_context.c` 已有
  SOURCE_CHANGE、LAST/drain、EPIPE 处理。
- 三个修改：① Copy-Out（dequeue→alloc→copy→props→unref→move_ref，无池化）；
  ② 全局 refcount 从“每 plane +1”改为“每 buffer group +1”，与
  `v4l2_free_buffer()` 的“每 group −1”对称——机制上解释了原 Source Change
  等待挂起，但仍是未上游评审的本地实验；③ 诊断日志（CAPTRACE/REFSCAN）。
- 三问题分离：Source Change（Copy-Out 解决）、fatal 0xf/EIO（Copy-Out 不能
  解决，需新进程/新 open，实测 0.28–0.30 s）、Copy-Out 成本（管线 wait
  21.8–25.8 ms vs no-copy 17.1 ms；非 live 主限速）。
- 路线 A（no-copy+重建）吞吐 89.9 fps，但 0xf 后 POLLERR 无法同进程恢复；
  路线 B（Copy-Out 降本，如池化）可能小幅提升，但不解决显示瓶颈。
- Gate U2：对照交付 PASS；**不建议部署任何 FFmpeg 修改**（refcount 需回归、
  Copy-Out 池化收益有限）。
- 下一步：U3 `0xf`/padding 分层表（使用 POC50/POC21/pad512 既有样本）。

### 2026-11-10 00:27–00:32 HKT — U1 上游 meson-vdec 19 补丁审计（PC + CM311 只读）

- 交付：`.codex_tmp/docs_backup_20261110/upstream_patch_matrix.md`（19 行状态矩阵 + 候选项 + Gate）。
- 来源核验：v7 `[PATCH 00/19]`，Anand Moon，2026-07-13；cover letter 统计
  7 个文件、+388/-106；作者自述“硬件 VIFIFO 满时 workqueue 死锁仍未解决”。
  v8/v9/合入状态在本次检索中**未找到**（记为 unverified，不是不存在）。
- 本地上游树：HEAD `0e80ef956`（2026-11-04），`codec_hevc.c`/`vdec_platform.c`
  有本地实验修改；目录 git 历史为浅历史，无法靠 log 判断 backport。
- 逐项结构核对（grep/函数位置）结果：present 4（P01/P13 等）、partial 3
  （P03/P06/P11）、absent 4（P05 `synchronize_irq`、P16 `dma_set_mask*`、
  P19 `dma_set_max_seg_size`、P18 未见 32 MiB 常量）、unknown 8。
- 候选（未批准部署）：P05 IRQ 同步、P16/P19 DMA mask/segment、P18 VIFIFO 32 MiB
  （需先定位当前 FIFO 大小；1.7 GiB 板上 32 MiB 有内存风险）。
- Gate U1：审计交付 PASS；**“可直接部署补丁”FAIL**——尚无候选同时具备
  可复现失效样本 + 观测指标；禁止整套 cherry-pick。
- 下一步：U2 FFmpeg V4L2 生命周期对照（`ffmpeg_lifecycle_comparison.md`），
  再做 U3 `0xf`/padding 分层表。

### 2026-11-10 00:06–00:15 HKT — 新专项 U0：USB 根盘与 DJI 共用同一个 xhci 控制器

- 依据 `plans/CM311_VDEC_Upstream_Audit_USB_RootFS_Plan.md` U0，只读盘点（R0）：
  证据 `.codex_tmp/u0_usb_rootfs_20261110/readonly.txt`。
- **rootfs 在 USB 盘上**：`/dev/sda2` ext4，`TRAN=usb`，`ID_BUS=usb`，
  `ID_MODEL=SG_Flash`，udev path
  `platform-xhci-hcd.2.auto-usb-0:2:1.0-scsi-0:0:0:0`；`/dev/sda1` vfat 挂 `/boot`。
- **共享 host controller：是**。`lsusb -t`：Bus 001 root hub `xhci-hcd/2p 480M`；
  Port 001 = DJI `2ca3:1020`（480M）；Port 002 = `23a9:ef18 USB SG Flash`（480M）。
  两者同在一个 USB 2.0 控制器上。
- Swap = `zram0` 1 GB（RAM 后端，201.7 MB 已用），**不是** USB 盘 swap。
- `/tmp`、`/dev/shm` 均为 tmpfs；`/dev/shm` 894 MB，可用于临时录制。
- 根挂载：`rw,noatime,nodiratime,errors=remount-ro,commit=600,data=writeback`。
- 当前 boot 的 `journalctl -k` 过滤 usb/uas/reset/I/O error/ext4 等：**无匹配**；
  空闲 `vmstat`：`wa=0`，CPU 96% idle。
- 影响判断：Bandwidth 不是问题（视频 10.2 Mbps + 录制 ~10 Mbps « 480 Mbps），
  但共享控制器上的 `usb-storage` 调度/周期性 writeback 可能给视频端点增加延迟。
  既有证据：只抓取 60 s（同时向 rootfs 写 76 MB）仍得到干净流 → **单纯磁盘写不足以
  损坏流**；`stream` 不录制也只有 ~30 AU/s → 根盘 I/O 也不是主要限速项。
  结论：共享总线是**风险项，不是已证明的根因**；后续 live 测试建议把录制改到
  `/dev/shm`（894 MB）以移除该变量，无需改系统。
- 未修改 CM311 任何配置；未重启/重载模块；未开始新 live。

### 2026-11-10 23:58–00:06 HKT — S0 计时 + S1 raw 传输：传输不是 live 主因，显示/X11 才是

- S0（离线 replay，`VT13_PIPE_TIMING=1`，干净 498 帧 1080p）：
  - no-copy：**wait p50=17.1 ms / p95=30.0 ms**，display=0（关）、bgr=0、build=0.2 ms；
    497 帧、58.52 fps。
  - copy：wait p50=21.8–25.8 ms / p95≈55 ms；491 帧、37.84 fps。
  - → 每帧成本几乎全部在“等 ffmpeg/nut/PyAV”，Python 侧只有 0.2 ms。
- S1（新增 opt-in `VT13_PIPE_TRANSPORT=raw`：ffmpeg 输出定长 rawvideo NV12，
  reader 不经 nut/PyAV）：干净 replay **497 帧、0 错误、65.33 fps**（nut 58.52）。
  首次达到 >60 fps，但余量很小。
- S2 live（3 段，均关控制、no-copy、1920×1080）：
  - `raw + 同步读 + 限帧 25`：171 帧（2.7 fps）、35 次 0xf（与默认同量级）。
  - `raw + 小队列 async(2000) + 丢 50% + 限帧 25`：260 帧、收尾 RC=1（raw reader
    在停止时置错，属实验路径缺陷）。
  - `raw + 小队列 async + 关显示 + 不丢 GOP`：**725 帧（12.1 fps）、20 次 0xf**。
  - 对照 `nut + 小队列 async + 关显示 + 丢 50%`：**1530 帧、2 次 0xf**（仍最佳）。
- 结论（修正）：**raw 传输只把离线上限从 58.5 提到 65.3 fps，对 live 帮助有限；
  真正的负载来自“解码 + X11/ffplay 显示 + 录制”，其中 ffplay 的软件渲染/缩放是
  最大可减项。整 GOP 丢弃仍是压制 0xf 最有效的手段。**
- 部署：远端 `ffmpeg_pipe.py` `edb960c2→b6672def`（新增显示限帧、计时、raw 传输，
  全部 opt-in 默认关/默认 nut）；`pipeline.py` 保持 `9d0013c2`（shed 默认关）。
  备份 `~/.codex_tmp/backup_timing_20261109/`、`backup_rawtransport_20261109/`。
- 未验证/风险：raw 路径停止时 RC=1；`-vf fps` 与 CFR 方案此前已失败并回滚；
  raw 仅作实验，默认仍 nut。
- 下一步（最高优先级）：**P2-2 轻量显示**——评估 DRM/KMS overlay 或至少避免
  ffplay 对 1080p 的软件缩放（例如解码侧输出 1024×576，或单独的轻量显示进程），
  目标：显示开启时 live ≥25 fps、0–3 次 0xf。其次是继续用 shed 闭环控制在
  无显示/低显示负载下的长时稳定性。

### 2026-11-09 23:02–23:25 HKT — P0-2/P1-2 关键转折：损伤是管线吞吐不足造成的，不是 RF

**修正前一条 P0-3 的归因**：P0-3 说“损伤来自 USB 上游（无线/接收器）”，当时依据是
管线 capture 的 raw 已损坏且 USB 无错误。本轮用**同一接收器、同一 USB 路径、只抓取
不解码**复测，raw 基本干净 → 损伤不是接收器输出固有，而是**解码负载导致管线读不动
（或设备 FIFO 溢出）**。P0-3 的“上游强关联”结论作废，保留为方法论教训。

- 实验顺序与主机：CM311 实时 USB（VT 链路全程开启）。23:02 用户把接收器移到
  USB2 延长线并重新枚举（bus1 dev 005→006，ttyACM0/1 重建）。
- **P0-2 物理隔离（3×60 s，同配置 ON）**：31/32/34 次 0xf（30.5/31.6/33.5 每
  60 s），243/278/182 帧，AU 38.8–41.7/s，输入 6.3–6.8 Mbps。
  与移动前 A1/A2（31/32 次、267/216 帧）**无差异** → 换位置/USB2 延长线不改变
  故障，RF 布置不是主因。
- **只抓取不解码（60 s，`capture_pyusb.py`）**：76,218,090 B（**10.2 Mbps**）、
  39,649 次读、最大间隙 **0.17 s**、无 ≥0.5 s 间隙；AU **3620 个 = 60.3 AU/s**，
  450 个 IDR，GOP p50=8，451 个 GOP 中**仅 2 个** POC 缺口，超大伪参数集仅 2 个
  （PPS 24,492 B 一处；AUD 最大 7 B 正常）。→ **接收器输出在主机持续读取时基本干净。**
- **管线吞吐上限（离线 replay，干净 498 帧 1080p60 样本）**：
  ffmpeg-pipe + Copy-Out 498 AU → 497 帧、0 错误、**38.54 fps**。
  → 源是 60 fps，管线上限 38.5 fps，**结构性欠 21 fps**。
- **async 预取（`VT13_ASYNC_USB=1`）**：读侧间隙降为 **0**，读取 64.9 MiB（满速
  10.2 Mbps），但 60 s 只交付 36.7 MiB（5.6 Mbps）；队列涨到 15,191/16,384，
  527 帧（8.7 fps）、18 次 0xf。→ 读侧不再停，但**解析/解码仍跟不上**，积压到
  队列满后接收器照样溢出。
- **async + no-copy**：627 帧、16 次 0xf、交付 30.3 MiB；队列触顶 16,384 →
  仍无改善（说明瓶颈不在 Copy-Out，而在 nut 管道/PyAV 的每帧 3.1 MB 搬运与
  Python 每 AU 开销）。
- **async + 整 GOP 丢弃（新增 opt-in `VT13_SHED_TO_IRAP`，KEEP=1/SKIP=1）**：
  505 帧、14 次 0xf、AU 43.8/s、积压稳定 10–14 MiB（队列 7.5k/16k）→ 丢弃生效、
  积压受控，但输出仍只有 8.2 fps，且交付 raw 仍有 28 个超大伪参数集。
- **async + 关闭控制面（`DJI_CONTROL_ENABLED=false`）**：**778 帧（12.7 fps）、
  10 次 0xf、绿/半绿过滤均为 0**，为今日最佳 live 结果；但交付仅 30.4 MB/61 s
  （4.0 Mbps），说明解析/解码仍在追赶，结束时队列仍有积压。
- 重要口径：管线录制的 `raw_ep81.bin` 是**已交付给解析器的字节**；async 队列在
  运行结束时仍有积压时，录制文件**不是完整的 USB 流**，不能用它计算绝对丢包率。
- **用户目视反馈（23:30）**：默认配置（async 关闭）画面仍会“过几秒更新一次”，
  约有 5 s 滞后；打开 async 后画面基本不更新。解释：async 把 10.2 Mbps 的流
  缓冲进有界队列（60 s 时积压 ~25 MiB ≈ 20 s 的流），解析/解码虽然更快，但处理
  的是**很旧的帧**；ffplay 的 drop-oldest 队列进一步丢弃新帧，观感就是“不更新”。
  默认模式虽然设备端丢字节、损坏更多，但管线始终贴着实时头，所以还能断续显示。
  → **async 预取只能作为诊断/吞吐测量工具，不能作为观看路径**；低延迟要求下必须
  丢弃积压本身（或在读取侧跳字节到下一个 IRAP），而不是缓冲。
- 结论（强关联，未最终证明）：**根因链 = 1080p60@10.2 Mbps 源 → 管线
  (nut+PyAV+Copy-Out) 上限 ~38.5 fps → 持续欠载 → USB 接收器 FIFO 溢出/丢字节
  → 图像损坏 → `0xf` 中止 → reset 循环**。RF/接收器本身在“读得动”时是干净的。
- 实验性改动已回滚：远端 `pipeline.py` 曾加入默认关闭的 `VT13_SHED_TO_IRAP` 块
  （`c700b8cd→9d0013c2`，REG1 默认回归 36 次 0xf/172 帧正常），验证完成后已从
  `~/.codex_tmp/backup_shed_20261109/pipeline.py.before_shed` 恢复为
  **`c700b8cd...`**，import 验证通过；patch 脚本保留在
  `.codex_tmp/p1_2_shed_20261109/` 供后续闭环实验复用。默认工作路径与改动前一致。
- 未 reboot/重载模块/装包；未改其他远端文件；VT 链路保持开启。
- 后续实验（23:26–23:45，均为 opt-in 组合，默认配置不变）：
  - `async + no-copy + 关控制`：571 帧/19 次 0xf，交付 5.3 Mbps，积压 27 MiB。
  - `async + no-copy + 关控制 + 关显示 + 50% GOP 丢弃`：**1530 帧（25.3 fps）、仅 2 次
    0xf**；显示路径是主要残余负载，但队列仍满（解析 ~27 AU/s）。
  - 新增 opt-in `VT13_DISPLAY_FPS`（在 pack/拷贝前跳过）：`async+no-copy+关控制+
    25 fps` → 800 帧（13.1 fps）、10 次 0xf、绿/半绿 0；积压仍满。
  - 同步 + 限帧 + no-copy + 关控制：352 帧（5.8 fps）、32 次 0xf（低延迟、低产出）。
  - 同步 + 限帧 + no-copy + 50% GOP 丢弃：507 帧（8.4 fps）、17 次 0xf、绿帧 3。
  - **小队列 async（`VT13_ASYNC_CHUNKS=2000`，≈2.5 s）+ 50% GOP 丢弃 + 限帧 +
    no-copy + 关控制**：两次 60 s 分别为 **552/529 帧（9.2/8.7 fps）、15/17 次
    0xf**，积压稳定 ~3 MiB，read gap 1–2 次 → **目前吞吐/延迟/稳定性最好的组合**。
  - `-vf fps=30` 失败（最小构建无 fps 滤镜）；输出 `-r 30 -fps_mode cfr` 导致 0 帧/
    EIO，均已回滚。
- 最终远端状态：`pipeline.py` `9d0013c2`（shed 块，默认关）、`ffmpeg_pipe.py`
  `edb960c2`（显示限帧，默认关）；两者均 opt-in，默认工作路径与改动前一致。
  备份 `~/.codex_tmp/backup_shed_20261109/`、`backup_dispcap_20261109/`、
  `backup_pipefps_20261109/`。
- 下一步（优先级）：
  0. 可直接体验的最佳组合：
     `DJI_CONTROL_ENABLED=false DJI_DISPLAY_FPS=25 FFMPEG_V4L2_NO_COPY=1
     VT13_SHED_TO_IRAP=1 VT13_ASYNC_USB=1 VT13_ASYNC_CHUNKS=2000`（≈9 fps、~2.5 s 延迟）；
  1. **提高管线吞吐到 >60 fps**：去掉 nut/PyAV 每帧 3.1 MB 往返（例如 ffmpeg
     子进程直接输出固定大小 NV12 帧、Python 直接读；或缩小解码输出），目标
     offline ≥90 fps、live 交付 ≥60 AU/s；
  2. 若短期无法提速：把“整 GOP 丢弃”改成**基于 async 积压的闭环控制**（积压升高
     就跳过下一 GOP，降低就恢复），目标稳定 30 fps、0 次 0xf、无冻结；
  3. 完成后再评估 Copy-Out/no-copy 与显示路径；RF 不再是优先项。

### 2026-11-09 22:52–23:00 HKT — P1-1 离线剖析：Copy-Out 不是 live 瓶颈，0xf 后设备重建也不慢

- 主机：CM311 离线（`/dev/video0` 空闲），release Copy-Out 二进制
  `1ed2b711...`，输入 `run2_segB_bootstrapped.h265`（9,226,274 B，
  SHA256 `e12bbf92...`，1080p），脚本
  `.codex_tmp/p1_1_profile_20261109/{profile_matrix.sh,profile_b.sh}`。
- 启动成本（干净样本、设备空闲、`-frames:v 1 -f null -`）：
  - copy：5 次 0.275–0.322 s（中位 ~0.29 s）；no-copy：0.256–0.264 s。
  - 说明 ffmpeg 进程 + V4L2 初始化约 **0.26 s**，Copy-Out 对单帧仅加 ~0.03 s。
- 0xf 后立即重开（用 `no_sei.h265` 注入 abort，rc=134，每次 ~0.85 s；
  随后立刻解 1 帧干净样本）：5 次分别为 **0.302/0.281/0.277/0.305/0.297 s**，
  与空闲基线相同 → **设备 teardown/session 清理不是 live 启动慢的原因**。
- 300 帧 rawvideo 输出（`-f rawvideo -pix_fmt nv12 /dev/null`）：
  - Copy-Out：7.752 s → **38.7 fps**；
  - `FFMPEG_V4L2_NO_COPY=1`：3.336 s → **89.9 fps**。
  - 两者都远高于 live 的 3.6–4.4 fps；Copy-Out 的 18–25 ms/帧差距真实存在，
    但当前 live 输入只有 ~41 AU/s，解码吞吐不是限制项。
- live 会话结构（A1/B1/A2）：每次 spawn 到下一次 spawn 之间，
  **中位仅 1–6 帧**，每段有 4–5 个会话产 0 帧，偶尔出现 20–85 帧的会话；
  `spawn→首个 CAPTRACE HANDOFF` 中位约 970 ms，但其中很多会话根本没有输出。
  结合 P0-3（raw 流已损坏）与本节（空闲/abort 后启动仅 0.28 s），
  **live 启动慢来自“首个可解画面迟迟不到”，而不是进程/设备初始化**。
- P1-1 Gate 判定：可以解释 live 产出低的主因（损坏输入 + 0xf 重启循环），
  Copy-Out 逐阶段（alloc/copy/DQBUF）分解尚未做；由于它当前不是限制项，
  按计划优先级暂缓，先做 P0-2 RF 隔离。
- 未 reboot/重载模块/装包/改远端工作树；设备在测试后空闲。

### 2026-11-09 22:50–23:00 HKT — P0-3 输入完整性：raw 流本身已字节级损坏；重启成本是主要产出瓶颈

- 分析对象：B1（`iframe_on_recovery=false`，60 s，1920×1080，raw 50,031,223 B，
  SHA256 `b18bd14b...`）。本地 `.codex_tmp/p0_1_abba_20261109/abba_20261109_224500_B1/`。
- 方法：`times.tsv` 按 chunk 回放 `raw_ep81.bin` → 项目 `AnnexBParser` +
  `AccessUnitAssembler`（`.codex_tmp/p0_3_au_analysis/au_analyze.py`）；
  另用最小 SPS/PPS/slice 头解析器取 `slice_pic_order_cnt_lsb`
  （`poc_analyze.py`）；对照 `/usr/bin/ffmpeg` 软件解码与 dmesg。
- 结果：
  1. AU 结构：2460 个 VCL AU / 60 s ≈ **41 AU/s**；IDR（NAL 20）294 个，
     GOP 长度 p50 = **8 个 AU**（IDR ≈ 每 0.2 s 一个）；参数集 310 组。
     → 当前流 IRAP 充裕，恢复不是 IRAP 饥饿。
  2. 完整性：出现 **18 个超大“参数集” NAL**（PPS 最大 16,594 B、AUD 最大
     16,327 B；正常 PPS 12 B/AUD ~6 B），说明多处 start code 丢失后解析器
     误同步；`discarded_prefix_bytes=4080`。
  3. POC：295 个 GOP 中 **74 个（25%）存在 POC 不连续**；软件解码日志出现
     `Could not find ref with POC N`、`Duplicate POC in a sequence`、
     `Truncating likely oversized PPS`、`cu_qp_delta outside range`。
     **结论：raw 字节流本身已损坏，不是解码器“看到完好流却报错”。**
  4. 归因：`times.tsv` 长度和 = 文件大小（记录无丢字节）；B1 的 USB 层
     `errors=0`、无 `usb_error`/`clear_halt`，仅有 12 次 read gap（p50 0.89 s）。
     同一采集链路在 run2（1.5 m+遮挡）曾交付 497/498 干净帧。因此损伤最可能
     来自 USB 之前的上游（无线/接收器输出），而非 Python/USB 记录层；
     这是**强关联，不是已证明**，需 P0-2 物理变量隔离。
  5. 视觉产出瓶颈：每次会话 `abort → 下一次 ffmpeg spawn` p50 约 150 ms，
     但 **`spawn → 第一帧 CAPTRACE HANDOFF` p50 ≈ 970 ms、p95 ≈ 2.4 s**；
     每会话平均只解 8.6 帧（267/31）。即 60 s 内约 30 个会话，每会话约
     1.0–1.2 s 花在 ffmpeg/V4L2 初始化上。**45 fps Copy-Out 解码能力不是
     当前 live 产出瓶颈，进程/设备初始化与 0xf 循环才是。**
- 待验证：`spawn→首帧`在设备空闲（无 0xf 残留）时的基线需离线测量（P1-1 正在做）；
  POC 解析在损坏流上可能与真实 POC 有偏差，仅用于“存在不连续”的存在性证据。
- 补充（23:40）：POC 跳变与 read gap 的相关性
  （`.codex_tmp/p0_3_au_analysis/gap_poc.py`，B1）：
  - 2458 个 AU、12 次 read gap（合计 10.78 s，占 18% 时间）；
  - POC delta 直方图：delta=1 共 1743 次（71%）；delta 2–6 共 62 次（前向跳帧）；
    delta 250–255 共 57 次（POC 回退，疑为切片头解析错误/POC 重置）；
  - read gap 内异常 23 次，read gap 外 108 次 → **大多数 POC 不连续发生在
    数据持续流动期间**，不是“长停顿导致整段丢失”。损伤更像持续性的包/比特损坏。
  - 软件解码（`-err_detect ignore_err`）输出 2438/2458 帧（99.2%，含错误隐藏），
    统计：`Could not find ref` 136、`Duplicate POC` 22、超大参数集 38、
    `cu_qp_delta` 34、NAL 解析错误 24。→ 流可被软件“带隐藏地”解出，但参考链
    与像素正确性不能保证；硬件解码器（严格）在首个损伤 GOP 即中止。
  - 该补充支持“上游持续损伤”而非“USB 记录层丢字节”；P0-2 物理隔离仍是判定
    无线链路责任的关键实验。
- 未 reboot/重载模块/装包/改远端工作树；离线分析仅读 raw。

### 2026-11-09 22:43–22:48 HKT — P0-1 A/B/A：requested I-frame 与 0xf 无因果关系

- 主机：CM311（实时 USB + HDMI/ffplay），PC 发起与分析。R2 由用户在本轮会话
  预先授权；VT 链路当时已开启，接收器已枚举，因此未要求人工再次打开图传。
- 唯一变量：`control.iframe_on_recovery`（ON/OFF/ON）。其余固定：
  `iframe_on_connect=true`、`stall_restart_s=0`、`kernel_abort_watch=true`、
  release Copy-Out FFmpeg `1ed2b711...`、`convert_bgr=false`、
  `display=ffplay` 1024×576、60 s、1920×1080 源。
- 运行目录（远端与本地同名）：
  - A1 `abba_20261109_224334_A1`（ON）
  - B1 `abba_20261109_224500_B1`（OFF）
  - A2 `abba_20261109_224618_A2`（ON）
  本地副本 `.codex_tmp/p0_1_abba_20261109/<run_id>/`（capture.log、events、
  times、smoke.yaml、cmd.txt、dmesg_before/after）。三次 `LAUNCHER_RC=0`。
- 结果（同一 `live_metrics.py` 口径）：

  | 段 | 请求 | unique abort | abort/60s | 间隔 p50 | frames | fps | AU/s | keyframe starts | 绿/半绿丢弃 |
  |---|---|---|---|---|---|---|---|---|---|
  | A1 ON | 18 | 31 | 30.8 | 1501 ms | 267 | 4.43 | 39.2 | 32 | 27/20 |
  | B1 OFF | 0 | 33 | 32.8 | 1502 ms | 225 | 3.73 | 40.2 | 34 | 36/24 |
  | A2 ON | 18 | 32 | 31.8 | 1520 ms | 216 | 3.58 | 37.9 | 33 | 16/11 |

- 请求→IRAP 延迟（capture.log 时间戳）：A1 p50 100 ms / p95 188 ms / 18–231 ms；
  A2 p50 79 ms / p95 118 ms / 18–172 ms。与 run5 的 37–162 ms 同量级。
- 判定（按计划 P0-1 Gate）：OFF 相对 ON 的 abort 率差为 +4.8%（32.8 vs 31.3），
  远小于 20% → **requested IDR 不是 0xf 的触发因素或放大因素**；ON 的帧数略高
  （241.5 vs 225，+7%），属噪声范围。恢复请求仍然是有用的快速启动/恢复手段。
- 附带确认：OFF 段（零请求）仍有 34 次 `IRAP received`/60 s（≈1.8 s 一个），
  证明当前发射端/链路本身周期性发送 IRAP；0xf 间隔 p50≈1.5 s 与该节奏一致。
  这修正了“IRAP 仅建链发送、恢复必然饥饿”的旧结论（旧结论可能只适用于当时
  的链路/模式）。
- 未验证：恢复 TTFV（从 abort 到下一张通过过滤并进入显示队列的帧）当前无逐帧
  时间戳，需在 P2-1 增加单调时钟埋点；本次只报告 abort 率与帧数。
- 未 reboot/重载模块/装包；未改远端工作树；三次运行后设备空闲。

### 2026-11-09 22:40–22:58 HKT — P0-0 环境快照、基线指标口径（只读）

- 主机：Ubuntu PC 工作目录 `/home/billieguo/billie_guo/src/rm/mobile_vt`；CM311
  `billieguo@10.42.0.11`。SSH 使用 `docs/REMOTE_MACHINE_USAGE.md` 记录的 askpass
  模式（密码运行时从文档读取到环境变量，未回显；helper 位于
  `.codex_tmp/p0_0_snapshot_20261109/ssh-askpass.sh`，包装器
  `.codex_tmp/p0_0_snapshot_20261109/cm311.sh`）。未安装 SSH key。
- CM311 身份：`armbian`/`aarch64`/`6.18.59-ophub`，4 核，1.7 GiB RAM，根分区
  103 GB 可用，uptime 3 天 7 小时；负载 0.22。
- 设备与占用：`/dev/video0` 无 opener；`meson_vdec` 已加载且 refcnt=0；
  `/dev/ttyACM0`、`/dev/ttyACM1` 存在；USB `2ca3:1020 DJI C5` 已枚举（接收器在线）；
  `/dev/dri/{card0,card1,renderD128}` 存在；Xorg `:0`/tty7，`xdpyinfo` RC=0。
- 进程：无 `vt13_video`/`ffmpeg`/`ffplay` 残留；仅有 htop/Xorg/xfce 桌面进程。
- 部署哈希（远端）：`vt13_video/config.py` `f47c7d9b...`、`pipeline.py`
  `c700b8cd...`、`ffmpeg_pipe.py` `871af9b2...`、`control.py` `cc0cbcdc...`、
  `decoder.py` `0a63d896...`（实验版）、`.codex_runs/live_capture_run5.sh`
  `c0e35756...`；release FFmpeg `~/ffmpeg-6.1.1-release/ffmpeg` `1ed2b711...`；
  custom FFmpeg `~/ffmpeg-6.1.1-v4l2/ffmpeg` `2a204518...`；venv PyAV 11.0.0。
  远端工作树不是 Git 仓库（`fatal: not a git repository`），一致性只能靠哈希清单。
- 基线日志已拉取到 `.codex_tmp/baseline_20261109/`（run2 `20261109_170226`、
  run4 `20261109_184856`、run15 `20261109_214849`、run17 `20261109_220040`、
  run18 `20261109_220409`）。run2/run4 的 launcher/params 文件不存在，属历史格式，
  仅作趋势参考，不能与当前版本逐项等同。
- 指标脚本：`.codex_tmp/p0_1_abba_20261109/live_metrics.py`；基线结果
  `.codex_tmp/baseline_20261109/metrics.json`。口径：`unique_kernel_aborts` 取
  `events.tsv` 的 `kernel_abort` 行；`frames` 取 `decode.frames`；显示丢弃取
  `decoder.display_*`；AU/IRAP 取 `stream.*`；输入 Mbps 取 `recording.bytes/duration`。
- 基线（同一脚本）：

  | run | 分辨率 | 时长 s | unique abort | abort/60s | abort 间隔 p50 ms | I-frame 请求 | AU/s | IRAP AU | keyframe starts | frames | fps | 显示丢弃 |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|
  | 15 (ON) | 1920×1080 | 61.2 | 33 | 32.3 | 1501 | 19 | 38.9 | 280 | 34 | 195 | 3.18 | 96（绿 23/半绿 13） |
  | 17 (OFF) | 1920×1080 | 61.1 | 30 | 29.5 | 1752 | 0 | 34.3 | 241 | 31 | 273 | 4.47 | 50（绿 35/半绿 6） |
  | 18 (ON) | 1920×1080 | 45.3 | 23 | 30.5 | 1742 | 12 | 38.8 | 195 | 23 | 183 | 4.04 | 86（绿 13/半绿 7） |
  | 4 | 1832×1032 | 95.7 | 0 | 0 | — | 0 | 22.4 | 2 | 2 | 110 | 1.15 | — |

- 新发现（`未验证/待证实`，进入 P0-1/P0-3 复核）：
  1. 当前参数集（`params_latest.h265`，102 B）trace_headers：1920×1080、level 5.0、
     `vui_time_scale=60`、`num_units_in_tick=1`（名义 60 fps）；
     `sps_max_dec_pic_buffering_minus1=1`（DPB=2）、`max_num_reorder_pics=0`
     （低延迟、无重排）。
  2. 实测 AU 速率仅 34.3–38.9 AU/s，明显低于名义 60 fps。要么上游实际约 35 fps，
     要么约 40% AU 未到达；需 P0-3 用 AU 序号/POC 证明，不能直接归因 RF。
  3. run17 关闭恢复请求后，61 s 内仍有 31 次 `IRAP received`（≈2 s 一个），说明
     当前流内存在周期性 IRAP，并非由我们的请求触发。这与 2026-11-09 早些时候
     “IRAP 仅建链时发送”的结论不一致，可能是发射端模式/链路状态变化；后续 A/B
     与 P0-3 必须按实际 IRAP 时间线统计，不能沿用旧假设。
  4. run17/18 的 `0xf` 间隔 p50 ≈ 1.74 s，与 IRAP 间隔一致，指向“每个新 GOP 解码
     数帧后中止”，但因果仍需 P0-3 对齐 AU/POC。
- 未启动新的实时链路（VT 已由用户开启、接收器已枚举）；未 reboot、未重载模块、
  未安装包、未修改远端工作树。本轮只产生 `.codex_tmp/` 下证据。

Docs layout (2026-11-10 03:00 HKT, user-requested cleanup): the maintained
document set is now exactly `AGENTS.md`, `docs/INTERSESSION_TRANSFER.md` and
`docs/REMOTE_MACHINE_USAGE.md`. The one-off analysis deliverables (U1/U2/U3,
P2-2, DMA plan, bottleneck analysis, plan review) were removed from `docs/`
and archived under `.codex_tmp/docs_backup_20261110/`; the two governing plan
files were moved to `plans/`, and `DEVELOPMENT_FLOW_AND_LATENCY.md` to
`archive/`. References below point at those archived paths.

Scope of this entry: documentation, read-only inventory, source-authority
decision, experimental-code diff audit, and offline V4L2 hardware decode,
including the 2026-11-08 expanded software/hardware matrix, `aud` EOF repeat,
the 19:54 HKT R0 precheck for the first live smoke test, and the 20:25-20:31
HKT offline soft/hardware rate benchmark plus decoder-path audit. No live USB
stream, HDMI display, or wireless-link test was started. The R0 precheck found
CM311 idle but no `2ca3:1020` USB receiver enumerated; live capture is blocked
until the receiver is connected and `doctor` returns RC=0. The benchmark shows
the custom FFmpeg hardware decoder is faster than software on short samples, but
`vt13_video` still uses PyAV software `hevc`, not `hevc_v4l2m2m`.

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
| CM311 `billieguo@10.42.0.253` (dynamic DHCP; historical 10.42.0.11) | `armbian`, `aarch64`, kernel `6.18.59-ophub`, 4 cores, 1.7 GiB RAM; eMMC-only root `/dev/mmcblk2p2`; `vt13-kiosk` active with atomic worker `9d610808...`; HDMI-A-1 connected; delay baseline recorded 2026-11-13 | Glass-to-glass latency; fresh 30-minute soak; visual rotation confirmation |

## Cross-machine consistency ledger

| Item | Local state | CM311 state | Result |
|---|---|---|---|
| `captures/cold_start/bulk_if0_ep81.bin` | 2,431,249 bytes; SHA256 `d4cec190f35eac9b32944aff0b32ca501d54e451c1e7e0c800ab10cbdd5aa698` | Same size and SHA256 | MATCH |
| `live_runs/vt13_params.h265` | 102 bytes; SHA256 `f9f019a14e2fc2990863221cca5bd1187cf3898dceb38277ba2b86194f94887f` | Same size and SHA256 | MATCH |
| Project source tree | Workable software-decode baseline; local Git baseline; 24 source/config/test entries hashed; 50/50 local tests pass | Latest experimental code; `.git` invalid; 27 source/config/test entries hashed; remote-only `async_usb.py` and two config files; `README.md`, `decoder.py`, `pipeline.py` differ; remote tests 49/50 due PyAV API mismatch | DIVERGENT BY DESIGN; MERGE PENDING |
| Atomic worker + evidence | Local source `tools/d3_probe.c fa9e5d07...`; local evidence manifest `268c1c5b...` | Deployed worker `build/d3/d3_probe 9d610808...`; remote source `fa9e5d07...`; evidence `sha256sum -c` 20/20 OK | MATCH for source/evidence; worker is target-built |
| Kernel source tree | Not present in this workspace | HEAD `0e80ef956`; modified `codec_hevc.c`, `vdec_platform.c`; untracked backups | REMOTE-ONLY SNAPSHOT |
| FFmpeg source tree | Not present in this workspace | HEAD `e38092e`; modified `v4l2_buffers.c`, `v4l2_m2m.c`, `v4l2_m2m_dec.c` | REMOTE-ONLY SNAPSHOT |
| Project docs | Updated locally this session | Older remote copies not re-read/synced | EXPECTED DIVERGENCE UNTIL SYNC |
| `/tmp/dji_test_latest_dir` | Not applicable | Missing | UNRESOLVED |

## Current validation-needed checklist

| ID | Item | Current status | Evidence required to close |
|---|---|---|---|
| V01 | Local/remote source consistency | Authority documented: CM311 is latest experimental, PC is workable software-decode baseline; trees remain divergent (24 vs 27 entries); remote tests 49/50 due PyAV API mismatch | Per-file merge/review; Git commit/diff or full SHA256 manifest; test both sides |
| V02 | Latest capture pointer | Missing on CM311 | `test -f /tmp/dji_test_latest_dir`, `cat`, and a verified capture root |
| V03 | CM311 process ownership | 2026-11-08 19:54 HKT R0 precheck: no `vt13_video`/`ffmpeg` process and no `/dev/video0` opener; source `meson_vdec` remains loaded; USB receiver is not enumerated | Re-check immediately before a live or hardware run; do not kill unknown processes; require `doctor` RC=0 |
| V04 | Display stack | Partially checked: `/dev/dri` has `card0`/`card1`/`renderD128`; SSH `DISPLAY`/`WAYLAND_DISPLAY` are empty; `loginctl` shows active `seat0`/`tty7`; physical HDMI output not verified | Actual HDMI output evidence; confirm DRM/KMS, fbdev, or other display path |
| V05 | `vt13_video` stream/READY | `--help` and `stream --help` returned RC=0; confirmed `--headless`, `--seconds`, `--record`, `--json-stats`; source has no literal `READY`, so use `USB source open` plus a `waiting_*` state; stream not run yet | Real `stream` command, READY evidence, stop/exit procedure |
| V06 | Golden capture decode | `clean_1832x1032.h265` software decode 30 frames RC=0 with no missing-reference messages; `no_sei.h265` software decode 132 frames RC=0 but with missing refs | Offline replay RC, frame count, decoder errors, FrameMD5 or equivalent |
| V07 | Custom FFmpeg hardware decode | 2026-11-08 `-fps_mode passthrough`: clean 30 frames RC=0, 29/30; `no_sei` POC21 `0xf` RC=134, 14-frame prefix all matching; `fresh_45_to_82` POC50 `0xf` RC=134, 32-frame prefix all matching; `pad_1024` 38 frames RC=0, 36/38; EOF `aud` same-window 3x all RC=137/19 frames and identical (cross-window 22/18/19), `eos` 20 frames RC=134, `zeros` 27 frames 26/27. 20:25-20:31 benchmark: clean HW 30/1.212 s vs SW 30/1.621 s; pad 1920x1080 HW 38/1.585 s vs SW 38/2.295 s; short-sample, not steady-state | Explain/fix `0xf`, padding mismatch, and EOF drain; explain `aud` timeout-window count; add more real samples; run long-duration FPS/CPU/RSS/temperature/latency tests |
| V08 | Kernel module/VDEC | Source module `ca46...` loaded after R3; HEVC advertised; 2026-11-08 dmesg shows `status=0x8` and `status=0xf` (POC21 for `no_sei`, POC50 for `fresh`); `pad` shows `0x8` plus two missing-reference substitutions; EOF drain remains problematic | `uname -r`, `lsmod`, vermagic, relevant `dmesg`, `status=0x8/0xf`; explain EOF state machine |
| V09 | Source Change/POC50/EOF | 2026-11-08 expanded matrix: EOF SW 27 frames RC=0 and identical; HW `aud`/`eos` drain failed, `zeros` 26/27; `pad_1024` RC=0 but 36/38 (first mismatch index 36); `aud` same-window 3x was 19 frames and identical, cross-window counts 22/18/19 | Explain/fix EOF drain/flush and `0xf`; explain timeout-window frame-count variation; validate padding content differences |
| V10 | Live wireless end-to-end | **First live smoke done 2026-11-09 16:12 (R2 approved)**: 43 correct frames via venv v4l2m2m, clean bounded exit; IRAP only at link establishment (3/90 s, user observation confirmed); live `0xf` at POC24 → reset → ~35 s IRAP-starvation freeze; 117 USB stall recoveries + 33.3 s gap (wireless-vs-USB attribution unproven); HDMI not used (headless) | Stable-link throughput run; stall attribution; recovery-policy experiment (continue-without-reset vs WAIT_IDR); HDMI R2; raw capture offline analysis |
| V11 | Performance/latency targets | Atomic worker 34 s steady: 49.7 FPS, `corrupt=0`; sender AU→program present p50 79.7 ms/p95 109.2 ms/max 187.5 ms; local stages p50 ≈19.5 ms; upstream+decode queue derived 60.2/88.6 ms; not glass-to-glass; 30–50 FPS appears met at program-side | User acceptance criteria; glass-to-glass measurement; CM311 30-minute CPU/RSS/temperature/latency soak |
| V12 | Cross-machine sync | Golden and parameter-set data match; source/docs not yet synced | Post-copy SHA256 verification and an updated ledger |
| V13 | Remote test/PyAV compatibility | 49/50 pass; PyAV 11.0.0 exposes `OUTPUT_CORRUPT`, while the test expects lowercase `output_corrupt` | Fix the compatibility test or pin PyAV; rerun all tests and record RC |
| V14 | USB receiver enumeration | **Satisfied 2026-11-09 16:05 HKT**: user connected receiver; `lsusb` `2ca3:1020 DJI C5`; `doctor` RC=0; usbfs accessible | Re-check immediately before the live run |
| V15 | Verified live launcher | **Created 2026-11-09**: `~/mobile_vt/.codex_runs/live_capture_verified.sh`, bash -n OK, SHA256 `c254b631...`; verified CLI, READY=`USB source open`, bounded 90 s, pid/log/raw/stats in DJI_RUN_DIR | Execute under R2 approval; confirm READY evidence in the real run |
| V16 | Live pipeline hardware decode integration | **CM311-verified via PyAV-native route (2026-11-09)**: PyAV 11.0.0 exposes `hevc_v4l2m2m`; raw clean sample SW/HW 30 frames, YUV MD5 29/30 (last frame differs); full-pipeline golden replay HW 80/105 frames — 1832 section 8/8 and 1920 section 71/72 YUV-identical; source change causes EIO×3 → reset → IRAP resync losing 25 frames, automatic recovery, no hang (reproduced twice). BGR-layer hashes differ systematically (swscale NV12→BGR vs YUV420P→BGR rounding; mean 0.44/255) — acceptance must compare YUV. Transient `capture POLLERR` on first open after an aborted session; a later fresh open succeeded. PC opt-in config change still uncommitted | Decide source-change mitigation: tolerate IRAP-resync gap vs rebuild PyAV against patched FFmpeg (Copy-Out) vs FFmpeg-subprocess backend; then long-run FPS/CPU/RSS/temperature/latency; last-frame EOF difference still open (V09) |
| V17 | Agent non-interactive SSH auth to CM311 | **Unblocked 2026-11-09 ~13:29 HKT via user-authorized askpass** (documented `SSH_ASKPASS_REQUIRE=force` pattern; password extracted from `docs/REMOTE_MACHINE_USAGE.md` into env at runtime, never echoed; helper in `.codex_tmp/`). Key auth still not installed; `BatchMode=yes` probes at 12:03/12:20/12:26 were RC=255 | Recommended hygiene: human runs `ssh-copy-id -i ~/.ssh/id_ed25519.pub billieguo@10.42.0.11` once and rotates the plaintext password out of the repo; askpass authorization was for this test window only |
| V18 | On-demand IRAP (DUML I-frame request) | **Hardware-verified 2026-11-09**: run 5 10/10 requests → IRAP in 37–162 ms; run 6 35 requests/34 IRAP starts; on-connect request decoded in 0.2 s with the VT already on. Integrated in the pipeline (`control.enabled`), pairing poll 1 Hz | Closed for recovery; re-verify the same latency in 1832×1032 mode |
| V19 | Capture layer A/B (PyUSB vs `rmrx dump`) | 2026-11-09: static aarch64 `rmrx` built (SHA256 `b05a5fbe...`); `capture_pyusb.py`, `timestamp_stdin.py`, `summarize_capture.py`, `live_capture_run5.sh` staged and syntax-checked. **Not run live** | CM311: same link, sequential 60 s runs; compare bytes/AU, gaps ≥500 ms, CPU/RSS, dmesg stalls; confirm nusb works on aarch64 |
| V20 | 1080p `0xf` cadence | Run 5: 11/107 s; run 6: 29/150 s; run 7: 19/90 s; run 10: 14/60 s; run 11: 33/60 s; POC 5/7 with missing references. Run 4 at 1832×1032: 1/90 s. Display filters + fast kernel-abort recovery added; freeze time now ~0.1 s but abort rate dominates | RF/link mitigation; offline POC/missing-AU comparison of run 11 vs run 4 to separate packet loss from firmware |
| V21 | Software decode viability | Runs 8/9: 0 `0xf`, 0 resets, but ~3 cores, 1.8–2 Mbps read, grey concealment dominates; user confirmed unusable. `convert_bgr=false` only slightly helps | Not viable on CM311 at 1080p60; keep as diagnostic contrast only |
| V22 | Requested IDR vs `0xf` | Run 11 recovers in 116 ms but abort rate rose to 33/60 s; each requested IDR dies after a few frames. Run 4 had 1 `0xf`/90 s without requests. Suspect large IDR bursts on a weak link or an incomplete requested GOP | No-request control run (disable `iframe_on_recovery`) to measure natural abort rate; POC/missing-AU trace after a requested IDR; RF mitigation |

## Data manifest

| Path | Host | Size | SHA256 | Status |
|---|---|---|---|---|
| `captures/cold_start/bulk_if0_ep81.bin` | Ubuntu PC | 2,431,249 | `d4cec190f35eac9b32944aff0b32ca501d54e451c1e7e0c800ab10cbdd5aa698` | MATCH with CM311 |
| `/home/billieguo/mobile_vt/captures/cold_start/bulk_if0_ep81.bin` | CM311 | 2,431,249 | `d4cec190f35eac9b32944aff0b32ca501d54e451c1e7e0c800ab10cbdd5aa698` | MATCH with PC |
| `live_runs/vt13_params.h265` | Ubuntu PC | 102 | `f9f019a14e2fc2990863221cca5bd1187cf3898dceb38277ba2b86194f94887f` | MATCH with CM311 |
| `/home/billieguo/mobile_vt/live_runs/vt13_params.h265` | CM311 | 102 | `f9f019a14e2fc2990863221cca5bd1187cf3898dceb38277ba2b86194f94887f` | MATCH with PC |
| `.codex_tmp/emmc_deploy_20261112/g7_atomic_20261113_1340/SHA256SUMS` | Ubuntu PC + CM311 | 20 files | `268c1c5b8630cce1f77fabac13f4e9ab20075fc68f23dcc0fb3589a2b3a8921f` | 20/20 OK on both hosts |

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
regression gate, not hardware-decode acceptance. V16 now has a PC-side opt-in
`hevc_v4l2m2m` config path (54 local tests pass), but CM311-side acceptance is
blocked by V17 key auth; EOF instrumentation or a CLI drain-policy change
remains the parallel open track. PyAV compatibility (V13) remains a sidecar;
live streaming and HDMI remain later R2 work.

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

### 2026-11-09 22:00-22:05 HKT — duplicate ffplay window on resolution change fixed (run 18)

- User observed two display windows. Run 17's log shows two
  `ffplay display started` lines: 1832×1032 at 22:00:47 and 1920×1080 at
  22:00:49. `_ensure_display` only closed the old display when the size was
  unchanged and the process had exited; a resolution change spawned a new
  ffplay **without closing the old one**, leaving the 1832 window on screen.
- Fix: `_ensure_display` now calls `_close_display()` whenever the size
  differs or the old process is dead, then starts the new display;
  `_close_display` logs `ffplay display closed`. 81/81 tests pass.
- Verification run 18 (`dji_20261109_220409`, 45 s, 1920 only): one
  `ffplay display started` + one `ffplay display closed`; no ffplay process
  remains afterward. A run with a real 1832→1080 switch will now show
  start/close/start (one window at a time). `pgrep -fc ffplay` can report 2
  because the tmux shell command contains `DJI_DISPLAY=ffplay`; use
  `ps -eo cmd | grep '[f]fplay'` for the real count.
- Deployed `ffmpeg_pipe.py` `871af9b2...`; backup `backup_run18_*`. No commit.

### 2026-11-09 22:00-22:01 HKT — no-request control run (run 17): requests are not the trigger

- User re-enabled the VT link and requested the no-recovery-request control.
  Run `dji_20261109_220040` (60 s): `iframe_on_recovery=false`,
  `iframe_on_connect=true`, `stall_restart_s=0`, release Copy-Out,
  kernel-abort watch, `convert_bgr=false`, ffplay.
- Result: **1 I-frame request, 30 kernel aborts, 31 IRAPs, 273 frames,
  45.2 MB USB, 0 USB errors/timeouts**. The abort rate without recovery
  requests (30/60 s) equals the rates with requests (run 15: 33/60 s,
  run 14: 31/60 s).
- Conclusion: the requested IDRs are **not** the cause of the `0xf`; the
  earlier correlation was confounded by the stream/link state. In this state
  the source itself sends an IRAP about every 2 s, and each IRAP's GOP dies
  after a few frames. The root remains the damaged 1080p stream/link plus the
  meson-vdec firmware abort. I-frame requests remain useful for fast
  startup/recovery but do not change the abort rate.
- Next: RF/link investigation (run 2 decoded clean 1080p60 at 1.5 m with
  obstruction, while the current 0.5 m setup is worse), 1832×1032 mode, and
  the P0 firmware/driver root cause. No commit.

### 2026-11-09 21:48-21:50 HKT — partial-green frame filter (run 15)

- User reported bottom-half green flashes in run 14. Cause: after a
  `0xf`/POLLERR the Copy-Out path copies a **partially written** frame whose
  bottom half is zeroed (Y=0, U=V=0); the old full-frame green detector
  missed it because the frame mean was not green.
- Fix: `_looks_like_partial_green` samples the NV12 planes and drops a frame
  when more than 20% of both Y and UV are near zero; the display holds the
  last complete frame. New counter `display_partial_green_dropped`.
  81/81 tests pass.
- Run 15 (`dji_20261109_214849`): release Copy-Out (no no-copy env),
  `stall_restart_s=2.0`, kernel watch, `convert_bgr=false`, ffplay, 60 s.
  Result: **195 frames, 33 aborts, 1582 POLLERR, 23 green + 13 partial-green
  frames dropped, 0 watchdog resets**. Green flashes are filtered; the
  `0xf`/POLLERR freeze remains.
- Deployed `ffmpeg_pipe.py` `2d99b0a0...`; backup `backup_run15_*`. No commit.

### 2026-11-09 21:45-21:46 HKT — release Copy-Out live A/B (run 14)

- User requested the release Copy-Out comparison. Run `dji_20261109_214510`
  (21:45:10-21:46:16, 60 s): `ffmpeg_path=~/ffmpeg-6.1.1-release/ffmpeg`,
  **no** `FFMPEG_V4L2_NO_COPY` (verified via tmux and `/proc/PID/environ`),
  `stall_restart_s=2.0`, `kernel_abort_watch=true`, `convert_bgr=false`,
  ffplay 1024×576. Result: **258 frames, 31 kernel aborts, 1507
  `output POLLERR`, 0 watchdog resets, USB 47.1 MB/0 errors**.
- Copy-Out recovers and yields frames, but does **not** eliminate POLLERR;
  the live picture remains limited by the 0xf cadence (~6–8 frames per
  requested IDR). Run 13 no-copy had 219 frames vs run 14 Copy-Out 258;
  the difference does not change the conclusion that `0xf`/link damage is
  the primary limiter. The release Copy-Out binary is a cleaner live
  candidate (no debug logs), selected via `DJI_FFMPEG_PATH`; the launcher
  default remains the custom binary. No commit.

### 2026-11-09 21:25-21:38 HKT — release patched build: 249 fps no-copy, but Copy-Out required live

- Built the patched FFmpeg in release mode (`--disable-debug`, `-O3`,
  minimal HEVC/v4l2m2m/nut/rawvideo components). With Copy-Out it still runs
  **45 fps**; adding an env-gated bypass (`FFMPEG_V4L2_NO_COPY=1`) skips the
  per-frame copy and reaches **1127 frames / 4.516 s = 249 fps**, matching
  the system build (221 fps).
- However, no-copy cannot survive live: run 13 (release no-copy, kernel-abort
  watch, 2 s watchdog, 60 s) produced 219 frames, 34 kernel aborts, **1503
  `output POLLERR`** and 0 watchdog resets. Each requested IDR decodes about
  6 frames, then `0xf` → POLLERR; no-copy never recovers. Copy-Out releases
  the CAPTURE references and is what allows recovery, at a 249→45 fps cost.
- Conclusion: the 210 fps is a real **offline no-copy** figure, but it does
  not translate to the live damaged stream. The live limiter is the `0xf`
  cadence per requested IDR (~6 frames), not decoder throughput. The working
  live path remains the Copy-Out build (release copy is cleaner than the
  custom debug build); smoothing requires fixing the `0xf`/link or returning
  to 1832×1032, not more decoder optimization.
- Release binary: `~/ffmpeg-6.1.1-release/ffmpeg`, SHA256 `1ed2b711...`;
  `FFMPEG_V4L2_NO_COPY=1` selects no-copy (offline/clean-stream only), unset
  selects Copy-Out (live recovery, 45 fps). No commit.

### 2026-11-09 21:09-21:19 HKT — 210 fps explained: custom debug build regression; release build started

- User supplied the original Nov 5 command/log (`~/vdec_hevc_hw_test.log`):
  20 MB `idr_test/vt13_idr_02.h265`, 1127 frames, **fps 210–222**, 0 decode
  errors. Reproduced today with `/usr/bin/ffmpeg` (release): 1127 frames in
  5.1 s = **221 fps**. The custom `~/ffmpeg-6.1.1-v4l2/ffmpeg` and its shared
  build are both `--enable-debug=2` and only reach **45 fps**. The 210 fps is
  real; the later debug/diagnostic build is the regression.
- Live test with the system release binary (run 12, `DJI_FFMPEG_PATH=/usr/bin/ffmpeg`)
  fails after the first kernel `0xf`: repeated `output POLLERR` and
  `Error submitting packet to decoder: EIO`, 7 frames / 28 resets in 60 s.
  The system v4l2m2m wrapper does not recover; the custom patched build does.
  This is why the user saw one starting frame then a freeze; the system binary
  is suitable only for offline benchmarks.
- Started a release build of the patched FFmpeg in
  `~/ffmpeg-6.1.1-release` (`--disable-debug`, minimal hevc/v4l2m2m/nut/
  rawvideo components), PID 104978, log
  `~/ffmpeg-6.1.1-release/buildlog/build.log`. Next: benchmark the 20 MB file
  (target ≥100 fps), then live test with `DJI_FFMPEG_PATH` pointing at the new
  binary. The current launcher default remains the working custom binary.
- Hypothesis: the debug build's 45 fps caused USB backpressure/reference loss
  and amplified the `0xf`; the release patched build should reduce both the
  decode overhead and the abort rate. The 0xf/link remains the primary issue.
- No commit.

### 2026-11-09 20:58-21:04 HKT — hardware throughput benchmark + kernel-abort fast recovery

- CPU observation: hardware decode usually uses <50% of the 4 cores because the
  VDEC does the work; the idle CPU cannot help while the decoder session is
  dead/restarting. Software decode saturates all cores and is not viable.
- Offline benchmark: 30-frame 1832×1032 `clean_1832x1032.h265` with
  `hevc_v4l2m2m -f null` took 1.04 s (≈29 fps wall including init); the
  498-frame 1080p60 `run2_segB_bootstrapped.h265` decoded to raw NV12 at
  **38.7 fps** (12.85 s, 15.1 s CPU). `-f null` hangs at EOF drain (known
  issue), so its short-run `fps` line is not a valid steady-state metric.
  The historical >200 fps figure was not reproduced; it is most likely a
  short-burst/progress-line artifact or a different output path, not an
  end-to-end rate.
- Added `recovery.kernel_abort_watch`: a background thread watches
  `journalctl -k -f` for `HEVC_LCU_CHECK status=0xf` / `Aborting decoding
  session` and triggers an immediate decoder reset + I-frame request instead
  of waiting for the 2 s watchdog. Run 11 (60 s): 33 kernel aborts, **0
  watchdog resets**, median abort→IRAP **116 ms** (60–303 ms), 34 IRAPs, 166
  frames, USB 49.5 MB, 0 errors.
- Key finding: faster recovery did not raise the frame count because the abort
  rate doubled (run 10: 14/60 s → run 11: 33/60 s). Each requested IDR dies
  after a few frames; run 4 with no requests had 1 `0xf`/90 s. This strongly
  associates the requested IDRs (or the large IDR bursts on a weak link) with
  the aborts. Next: a no-request control run, RF mitigation, and a POC/
  missing-AU comparison after a requested IDR.
- Deployed hashes: config `f47c7d9b...`, pipeline `c700b8cd...`, launcher
  `673dd0f8...` (ffmpeg_pipe `8e6c4411...` unchanged). Backups:
  `backup_run11_*`. No commit.

### 2026-11-09 20:46-20:55 HKT — display filters + software/hardware decode A/B

- User feedback on runs 5/6: ~5 s delay, frequent green curtain, window
  closing/restarting. Root cause was twofold: every watchdog reset killed
  ffplay, and the display tap wrote corrupt/green frames synchronously.
- Display fixes deployed: async drop-oldest display queue (decode reader no
  longer blocks on ffplay), skip `is_corrupt`, zeroed/green (Y≈0, U=V≈0) and
  uniform grey (Y≈128, low variance) frames, ffplay low-latency flags, and
  `decoder.convert_bgr` to skip BGR conversion when only the NV12 display is
  needed.
- Hardware runs 7/10: display starts = 1, green frames dropped (22 in 90 s;
  14 in 60 s), window stays open; 19 and 14 `0xf` aborts respectively. Frames
  still freeze for the watchdog interval.
- Software A/B (runs 8/9): 0 `0xf`, 0 resets, display starts = 1, but
  ffmpeg+Python+ffplay ≈3 cores; only 1.8–2 Mbps of the 1080p stream was read
  (USB backpressure), POC gaps led to uniform-grey concealment, and the user
  confirmed the picture was mostly grey. `convert_bgr=false` cut Python CPU
  from 131% to 97% but did not make it viable. **Software decode ruled out on
  CM311.**
- Conclusion: keep hardware decode + display filters + 2 s watchdog. The
  remaining `0xf` cadence is upstream stream damage/firmware at 1920×1080;
  1832×1032 was much more stable. Resolution cannot be controlled by the
  pipeline/user. Next: RF/link mitigation and an offline POC/missing-AU
  comparison of run 10 vs run 4 to separate packet loss from a firmware bug.
- Deployed hashes: config `93b3d6b5...`, pipeline `a14b3aa2...`, ffmpeg_pipe
  `8e6c4411...`, launcher `ae7f3f42...`. Backups: `backup_run7/8/9/10_*`.
  No commit.

### 2026-11-09 20:31-20:41 HKT — live runs 5/6: I-frame request hardware-verified; display/restart fixes

- Run 5 (`dji_20261109_203158`, 20:31:58-20:34:34, 150 s): receiver enumerated,
  `/dev/ttyACM0` rw, control link opened, VT enabled by the user at ~20:32:37.
  **10/10 watchdog I-frame requests were followed by an IRAP within 37–162 ms**
  — the transmitter honors the request on demand. The run also hit 11 kernel
  `HEVC_LCU_CHECK status=0xf` aborts (POC 5/7, 1920×1080) → silent decoder
  death → 5 s watchdog → request → IRAP → resume. Each reset closed and
  reopened ffplay, which the user saw as continuous window restarts and lag.
  VT-off period produced 56 request messages (0.5 s throttle only). Run 5:
  152 frames, 10.8 fps, 64 requests, 12 IRAP starts, 10 display starts,
  raw 99,967,789 B SHA256 `ee2f3b370ada58ff66e6bd0d6becb846039c352d7163a78fc272a0a8c993830e`.
- Fixes (PC 76/76 tests, remote golden replay 105 frames): `FfmpegPipeDecoder`
  keeps ffplay alive across `reset()`, defers the next ffmpeg spawn until a
  usable IRAP, and keeps the display across SPS restarts; `_request_iframe`
  only sends while data is flowing and is throttled by `_next_iframe_at`;
  `_mark_discontinuity` no longer resets that throttle.
- Run 6 (`dji_20261109_203830`, 20:38:30-20:41:00, 150 s,
  `DJI_STALL_RESTART_S=2.0`): **display starts = 1** (no window close/reopen
  across 34 resets), 565 frames, 13.14 fps, 34 watchdog resets, 35 requests /
  34 IRAP starts, 149 pairing queries, USB 0 errors/timeouts, raw
  127,890,043 B SHA256
  `ed1329e80842d6e4df6f61139d05ed45c7840b181ea80b1b4c481bfb73c67769`.
  With the VT already on, the on-connect request started decoding in **0.2 s**
  (20:38:36.519 request → 20:38:36.735 IRAP).
- Remaining: 29 `0xf` aborts in run 6, all at 1920×1080; each requested IRAP
  yields only a few decodable frames before the firmware aborts. Run 4 at
  1832×1032 had 1 `0xf` in 90 s. The watchdog/request loop now recovers, but
  the 1080p cadence limits smoothness to ~2 s freeze every ~5 s.
- Backups: `~/mobile_vt/.codex_tmp/backup_run5_20261109_203028/`,
  `~/mobile_vt/.codex_tmp/backup_run6_20261109_203755/`.
  Installed hashes: pipeline `a99d6a81...`, ffmpeg_pipe `756fe77e...`,
  control `cc0cbcdc...`, config `5b42c925...`. No commit.
- Next A/B: user locks the transmitter to 1832×1032@30, rerun with the same
  control+watchdog; if `0xf` drops sharply, mode is confirmed as the driver.
  Otherwise trace the POC/reference chain after a requested IDR in the raw
  capture.

### 2026-11-09 20:15-20:45 HKT — control plane + recovery architecture integrated; capture A/B staged

- User instruction: keep the working Python pipeline; adapt only rm-receiver's
  control plane and recovery architecture, test the capture layer, absorb the
  protocol findings, and follow the recommended adoption order.
- Backup before edits: `.codex_tmp/backup_before_control_20261109_201531`
  (13 files, `SHA256SUMS` verified).
- Added `vt13_video/control.py` (SHA256
  `cc0cbcdc93a58e408d4609a608e623d34654be65b3b9edeeb5370ee375b2b525`):
  DUML v1 encode/decode, CRC-8/16, sysfs control-port discovery (interface 2),
  `ControlLink` reader/writer thread with reconnect, the exact official
  I-frame request, 1 Hz pairing query, and downlink frame decode/log. Stdlib
  only.
- Config: new `[control]` section (`enabled`, `port`, `iframe_on_connect`,
  `iframe_on_recovery`, `iframe_retry_s`, `min_iframe_interval_s`,
  `pairing_poll_s`) and `decoder.stall_restart_s` (default 0 = off).
- Recovery integration: request an I-frame on control-port connect, on
  discontinuity, after a decoder reset, and every 2 s while waiting for a
  keyframe; optional output-stall watchdog resets the decoder when VCL access
  units keep arriving but no frames are produced for N seconds, then requests
  an I-frame (targets the silent 0xf session death).
- Tests: 8 control tests (real DUML frame + PTY), 2 config tests, 4 pipeline
  tests; full suite **73/73 in 7.36 s**. Golden replay with a PTY control
  link: 105 frames, 1 on-connect I-frame request, 4 pairing queries, 0
  watchdog resets — no regression.
- Capture layer: static aarch64-musl `rmrx` built via rustup target
  `aarch64-unknown-linux-musl` + `rust-lld` (3,281,112 B, SHA256
  `b05a5fbe7e13e1b3e0655827e30e939f30bef16a0eaa1006530c6353a8989fae`,
  ELF64 AArch64 statically linked). Staged scripts: `capture_pyusb.py`
  (`3a75902f...`), `timestamp_stdin.py` (`47941799...`),
  `summarize_capture.py` (`aeb7a81b...`), `live_capture_run5.sh`
  (`132b3444...`, `bash -n` OK). **Not run live**: no receiver on the PC and
  no CM311 access this session.
- Cognitive gains folded into README: EP 0x81 is raw Annex-B (no private video
  framing); IRAP scarcity is by design (the official client requests on
  demand); `ttyACM0` is control and `ttyACM1` is debug.
- Risks: the I-frame request's live effect is unverified; the watchdog may
  false-positive under heavy corruption (default off); control writes are
  best-effort; the musl binary's CM311 runtime is unverified; run 5 is not
  deployed. No commit.
- Next: deploy run 5 (control + watchdog) to CM311, do a live run, then the
  capture A/B on the same link.

### 2026-11-09 19:05-19:18 HKT — rm-receiver (Rust) evaluated offline: DUML I-frame request is the missing recovery primitive

- Scope: PC-only evaluation of `/home/billieguo/billie_guo/src/rm/rm-receiver`
  (HEAD `10e381b`), reverse-engineered from RoboMaster Client 12.0.0.213 for the
  same USB `2ca3:1020` receiver. No receiver attached to the PC; no CM311
  access; no live USB/HDMI/wireless run.
- Build: HEAD fails `cargo test --workspace` because the workspace dependency
  `rm-receiver` does not declare `default-features = false` while
  `rm-receiver-cli` overrides it. One-line fix applied in the root
  `Cargo.toml` (uncommitted). With FFmpeg 9.0.2 from conda env `colmap`,
  `/usr/lib/llvm-14/lib` libclang and the GCC-12 include path for bindgen:
  the full workspace passes 37 tests (proto 28, receiver 2, decode 3, doctest
  1, plus integration cases), clippy is clean, and `rm-receiver-viewer` builds. System FFmpeg 4.4 is too old for `decode`.
- Codec equivalence on the run-4 capture (`raw_ep81.bin`, SHA256
  `b5b5339f...`): Rust `AccessUnitSplitter` and Python
  `AccessUnitAssembler` both yield 2147 AUs / 2 IRAP AUs / 1 PS-bearing AU and
  byte-identical output (41,417,070 bytes, SHA256
  `ceef970ea1b4908ad19c41bd46e6558a16c2063c86c1c3b3af39104aafad9f08`);
  ffprobe reports 2148 packets / 2 keyframes. Output is chunk-size invariant.
  On the run-3 capture the only delta is one invalid 5-byte pseudo-NAL that
  Python rejects and Rust keeps (no decode impact).
- DUML decoder on the real control-port captures: 1,421 frames from
  `cold_start` (431 non-`Other`) and 552 from `linked`, 0 dropped bytes;
  command addresses/types decode as expected.
- Control logic exercised without hardware (PTY as `--port`): `rmrx` emits
  exactly `55170438aa0e0000400101000000000024000000248f06` (request I-frame,
  DUML 1/1 → 14/0) on control-port open and the pairing query
  `550f04a2aa0e00004009550002e742` at 1 Hz.
- Architecture: keyframe-gated AUs, I-frame request on queue overflow, and
  decode error → reset → request I-frame in the viewer. Caveat: FFmpeg
  reports missing parameter sets as log-only, not `DecodeError`; the
  bootstrapped 1080p60 segment decoded 0 frames, and the run-4 capture decoded
  42 frames only from the PS-bearing IRAP at AU 2105. Parameter-set priming
  remains required; this repo does not replace it.
- New probe `.codex_tmp/rmrx_probe/vt_iframe_probe.py` (SHA256
  `d4b5ab428a9c0acc900ebeba1a6df7a799aaf8fa9d8933b8fc6a4e3163eac69b`),
  dependency-free DUML encoder; dry-run and PTY test emitted the exact request
  3/3. Intended use: run alongside the existing CM311 pipeline (which never
  opens `ttyACM0`) to test whether the transmitter honors an on-demand I-frame
  request. Candidate fix for 0xf session death + IRAP starvation, unverified on
  hardware.
- No tracked `mobile_vt` changes; the rm-receiver one-line fix is uncommitted.
  No commit. Next: CM311 live test — start the pipeline, wait for READY, run
  the probe (`--repeat 12 --interval 5`), and count new IRAPs in
  `capture.log`/dmesg; if honored, integrate into the watchdog recovery path.

### 2026-11-09 18:54-19:05 HKT — recovery experiments: primary killer is 0xf session death + IRAP starvation

- User smoothness verdict (run 4): first segment UNUSABLE (freeze/corrupt),
  second segment choppy-but-watchable. Effective live display ≈1.2 fps wall.
- Recovery A/B on run-4 recording: first attempt invalid — discovered
  **FileSource.realtime defaults False and CLI replay never paces** (times
  file only shapes chunks/gap metadata); "timed" replays were full-speed
  floods. Redone with realtime=True via stdin scripts:
  - reset policy (reset_on_gap=true, max_err=3): 84 frames/90.3 s, 2048/2144
    AUs skipped, 3 resets — reproduces live-like loss.
  - continue policy (reset_on_gap=false, max_err=100000, concurrent
    consumer, drop-oldest): **68 frames/88.7 s, 0 errors/resets/corrupt/
    drops, 26 skipped** — same ~68 as without consumer fixes.
- Diagnosis: 68 ≈ clean prefix before **POC70 `0xf` firmware abort**
  (dmesg-confirmed in run 4). ffmpeg process stays alive but the decode
  session is dead; ~2000 subsequent AUs swallowed until the second
  (link-reestablishment) IRAP at t≈87 s. Reset policy is SECONDARY; primary
  = firmware abort + establishment-only IRAP = decode halt until link
  cycle. Matches live run-4 110-frame pattern.
- Earlier "timed replay" conclusions corrected where they assumed pacing;
  throughput capacity tests (gapless, full-speed) remain valid.
- Options: (A) backend output-stall watchdog → restart ffmpeg + re-prime
  params (mitigation; may show concealment artifacts; no IDR still limits
  recovery); (B) P0 `0xf` driver/firmware root-cause track (kernel work);
  (C) RF environment investigation (0.5 m still corrupt → interference/
  transmitter health; user-side experiments); (D) accept + document.
  Recommendation: A (quick mitigation) + C in parallel; B long-term.
- Evidence: `recovery_rt_20261109_185610`, `recovery_continue_fixed_20261109_190011`
  (remote; outputs in prep dir). No commit; no working-tree writes.

### 2026-11-09 18:48-18:55 HKT — live run 4 (full chain, 0.5 m): 0 pipeline errors, 0xf absorbed

- R2 approved; current setup ≈0.5 m (user confirmed run 3/current = 0.5 m;
  run 2 was 1.5 m + person/laptop obstruction). Device's normal
  1832→1080p startup behavior accepted as-is (no mode locking available;
  this run stayed 1832 throughout). Launcher `live_capture_run4.sh`
  (SHA256 `e5df70bc...`, bash -n both sides): ffmpeg-pipe backend +
  display ffplay + DISPLAY/:0 defaults; priming `params_1832.h265`
  (`64ecfdeb...`, hashes cross-verified vs run-2 seg1 params).
- Run `dji_20261109_184856`: READY 18:49:02; user cycled wireless; first
  IRAP 18:49:40 (37.3 s establishment gap), ffplay window 18:49:41 (+1.13 s,
  consistent with measured startup); second segment IRAP 18:50:29 after
  9.465 s gap (in-band params), window restarted 1832.
- Results: **110 frames, 17.52 fps run-average (incl. 37.3/9.5/4.9 s gaps),
  0 decoder errors, 0 corrupt**; 146 USB stall recoveries (0 failures);
  61 live-queue drops (drop-oldest); **skipped AUs 25/2145 (1.2%) vs run-3
  87%**; 2/2 IRAPs started immediately (priming + in-band).
- dmesg: **1 firmware `0xf` abort at POC70** (idx=570/1914) — **absorbed by
  ffmpeg CLI error tolerance; pipeline saw zero errors** (vs runs 1-3 where
  EIO propagated → reset → IRAP starvation). Major robustness win of the
  subprocess backend.
- Evidence: `.codex_tmp/live_smoke_20261109_184856/` (raw 41,424,636 B
  SHA256 `b5b5339f63ca206bb78a69a6321a98d36c3632c5706948eed6a3185cddd25662`
  local==remote; capture.log, times/events, params_latest.h265 1832 config);
  dmesg excerpt `dmesg_live_smoke4.txt`. Post-run: no process, device free.
- User HDMI smoothness verdict pending (moving content this run; asked).
- Conclusions: `verified` — full chain live at 0.5 m: receive→HW decode→
  HDMI with 0 pipeline errors; 0xf no longer fatal; priming eliminates
  param-missing stalls; startup ~1.1 s. `unverified` — subjective
  smoothness (user), long-run stability, 1080p live switch (not triggered
  this run), RF damage mode at 0.5 m (POC70 0xf indicates some corruption
  still present close-range — obstruction not the sole cause).
- No commit; no working-tree writes (launcher/params in .codex_runs/.codex_tmp).

### 2026-11-09 19:00 HKT — user RF setup disclosure; attribution nuance corrected

- User: run 3 and current setup ≈ **0.5 m**; run 2 ≈ **1.5 m with a person
  and laptop-corner obstruction**. This CORRECTS the simple distance
  attribution: run 2 (farther, obstructed) delivered 99.8% clean frames
  (damage = gaps/disconnects), while run 3 (0.5 m) delivered CORRUPT frames
  (POC chaos + 0xf at POC269). Two distinct failure modes; distance alone
  does not explain them — likely link-adaptation behavior or time-varying
  interference. Run 4 at 0.5 m with the new backend will discriminate:
  corruption at close range rules out simple obstruction.
- "Mode locking" explained to user: transmitter auto-switched
  1832x1032@30 ↔ 1920x1080@60 mid-stream (run 1 t=53.8 s, run 2 ~39.7 s),
  each switch with ~11 s outage + new VPS/SPS + IRAP; locking = fixing
  output resolution/framerate in DJI app/device settings. Asked user which
  device and whether the setting exists; backend already handles SPS-change
  restarts if auto-switching remains.
- Smoothness verdict still deferred to run 4 (moving content). No code
  change; no commit.

### 2026-11-09 18:50 HKT — display startup-delay analysis (user question)

- User reported a long wait before the HDMI window appeared and stationary
  content (smoothness unjudgeable; deferred to live run 4).
- Root cause of the perceived ~2 min wait: the verification command ran the
  111 s test suite BEFORE the display replay (verify dir created 18:30:41;
  replay started 18:32:54). Command-ordering issue, not decoder latency;
  future display tests run first.
- Actual startup latency measured from `display_replay.log`: backend init
  18:32:54.466 → source open +23 ms → first IRAP +41 ms → **first decoded
  frame / ffplay launch +1.21 s** (v4l2m2m firmware init + DPB fill). Normal
  for hardware decode; window follows immediately. Optional pre-spawn of
  ffplay would shave a few hundred ms — not pursued.
- Smoothness verdict deferred to live run 4 (moving content); user will
  confirm RF setup first. No code change; no commit.

### 2026-11-09 18:30-18:40 HKT — display sink deployed + verified: 21.55 fps integrated HDMI

- R2 approved and executed: remote pre-backup
  `~/mobile_vt/.codex_tmp/backup_display_remote_20261109_183007/` (4 files,
  hashes recorded); staging `display_20261109_183007`; all pre/post hashes
  verified (config `4d76e34a→b33c6b81`, ffmpeg_pipe `4889a2fc→7c31bbbe`,
  test_config `2f57e7f4→f148d609`, test_ffmpeg_pipe `7867fc71→223ec850`);
  pipeline.py untouched this round; config check passed.
- R1 verification (evidence `display_verify_20261109_183041`, local copy +
  manifests MATCH): suite 57 tests, only known V13 error; **integrated
  display replay (segB_clean, backend ffmpeg-pipe + display ffplay on :0):
  491 frames, 21.55 fps, 0 errors, display=ffplay active, pipe_dropped 0,
  RC=0, no ffplay residual, device free**. Full pipeline overhead ~15% vs
  the raw ffmpeg→ffplay chain (25.13 fps). User visual confirmation of the
  VT13-Video window pending (asked).
- Product display path now built into the pipeline: `decoder.display:
  ffplay` (+ display_width/height, ffplay_path); operator sets DISPLAY/
  XAUTHORITY; graceful disable on ffplay failure; resolution-change restart.
- No commit. Rollback: cp back from backup_display_remote_20261109_183007.
- Next: live run 4 (user will confirm RF info), recovery-policy experiment,
  long-run stability; V13 one-line fix optional.

### 2026-11-09 18:24-18:30 HKT — NV12 display sink integrated (PC): 59/59 tests

- User order: integration first; live run 4 info later. Backup #3:
  `/home/billieguo/billie_guo/src/rm/mobile_vt/.codex_tmp/backup_before_display_20261109_182449`
  (manifest inside).
- Implemented in `ffmpeg_pipe.py`: reader thread taps NV12 before cv2
  conversion → ffplay rawvideo NV12 SDL window (`decoder.display: ffplay`,
  `display_width/height` default 1024x576, `ffplay_path` optional; DISPLAY/
  XAUTHORITY inherited from operator env). Lazy start on first frame;
  restart on resolution change (with the ffmpeg process); broken pipe /
  missing binary → graceful disable, decode continues; cleanup on
  terminate/flush. `_pack_nv12` strips stride padding (unit-tested);
  `_frame_to_bgr` refactored onto it. Config fields validated.
- PC regression: **59/59 RC=0** (5.43 s), incl. golden pipe 105 frames
  1832→1920, display-degrades-without-X (105 frames, 0 errors), NV12 pack
  correctness. Evidence `.codex_tmp/display_integration_tests_20261109_182646/`
  (unittest.log + changed_files.sha256).
- R2 deployment package presented (config.py, ffmpeg_pipe.py, 2 test files;
  pipeline.py unchanged this round); CM311 verification will replay segB
  with display=ffplay on :0 for user visual confirmation + stats.
- No commit.

### 2026-11-09 18:18-18:30 HKT — NV12-direct HDMI retest: 25.1 fps; user confirmed video on first test

- **User visually confirmed dynamic video on HDMI** (first BGR test) —
  display path functionally established (V04 core evidence).
- NV12-direct retest (R2 approved): custom ffmpeg HW decode → rawvideo NV12
  pipe → ffplay `-pixel_format nv12` SDL window 1024x576 on :0. Result:
  **498/498 frames displayed, 19.82 s, 25.13 fps** (vs 5.4 fps BGR path,
  4.6×), ffmpeg RC=0, ffplay RC=0, clean exit, no residual, device free.
  Evidence `~/mobile_vt/.codex_tmp/hdmi_nv12_20261109_181828/` (local copy
  + manifest fetched).
- Interpretation: ffplay NV12 overlay + Xorg rendering caps ~25 fps on this
  box (decode free-run 33 fps); BGR→SDL conversion was the 5.4 fps
  bottleneck. Product integration should tap NV12 before cv2 conversion
  for the display sink (backend option), keeping cv2 BGR for recording/
  processing consumers.
- No commit; no working-tree writes (standalone scripts).
- Next options: (1) integrate NV12 display sink into the pipeline/backend
  (PC implementation + R2 deploy); (2) live run 4 with new backend +
  priming (R2; RF setup questions still unanswered); (3) recovery-policy
  offline experiment; (4) long-run stability/thermals.

### 2026-11-09 18:15-18:25 HKT — HDMI display test executed (R2 approved): video on screen, ffplay BGR path slow

- R2 approved via question; executed standalone stdin script (no tree
  writes): segB_clean replay → ffmpeg-pipe HW decode → BGR frames → ffplay
  rawvideo bgr24 1920x1080 window 1024x576 on DISPLAY=:0 (XAUTHORITY
  ~/.Xauthority). Evidence `~/mobile_vt/.codex_tmp/hdmi_test_20261109_181557/`
  (local copy fetched: stats.json, ffplay.log).
- Results: **162 frames displayed / 30.01 s = 5.4 fps**, write_errors 0,
  ffplay RC=0 clean exit, decoder 251 frames / 0 errors / 0 resets /
  pipe_dropped 0; post-run no ffplay process, `/dev/video0` free.
  Display-side backpressure throttled the pipeline (ffplay BGR→SDL texture
  conversion on A53 is the new bottleneck; decode free-runs at 33 fps).
- User visual confirmation of HDMI content pending (asked).
- Next proposed: NV12-direct ffplay retest (SDL native NV12 overlay, skip
  BGR conversion) — new R2 package after user confirms; also recovery-policy
  offline experiment and live run 4 (RF questions still open).
- No commit; no working-tree writes.

### 2026-11-09 18:20 HKT — display stack probe (V04): X11 + ffplay is the minimal HDMI path

- Read-only probe (`.codex_tmp/v16_cm311_prep_20261109_122603/display_stack_probe.txt`):
  HDMI-A-1 **connected+enabled**; meson-drm card0 (lima card1 = GPU, not
  display); `/dev/fb0` mesondrmfb 32bpp virtual 1920x2160; **Xorg running on
  :0/tty7 via lightdm, billieguo session active**; `~/.Xauthority` readable;
  `DISPLAY=:0 XAUTHORITY=~/.Xauthority xrandr` RC=0 — **X access verified**;
  HDMI current mode **1024x600@59.82** (1920x1080@60 available); modetest/
  kmscube absent; libdrm present; **system cv2 is headless (no GUI backend)
  → cv2.imshow unusable**; **ffplay available** (system ffmpeg).
- Minimal display path chosen: pipeline frames → rawvideo pipe → ffplay SDL
  window on :0 (no installs, no tree changes; standalone test script).
  cv2 GUI alternative would need pip opencv-python (not pursued).
- V04 status: display stack now identified (X11/meson-drm/HDMI 1024x600);
  actual video-on-HDMI evidence pending the R2 display test (package
  presented). RF setup questions for live run 4 still unanswered by user.
- No remote writes; no commit.

### 2026-11-09 18:02-18:12 HKT — Plan 3 CM311 deployment + verification: 33.3 fps @1080p60

- R2 approved and executed: staging `plan3_20261109_180206`, all pre/staging/
  post hashes verified (config `3bf1229e→4d76e34a`; pipeline experimental
  `85e57ea8` → factory-hunk merge `62382e56`, VT13_LOW_LATENCY_MS marker
  preserved; ffmpeg_pipe.py `4889a2fc`; test_config `24d02c30→2f57e7f4`;
  test_ffmpeg_pipe `7867fc71`). Config check passed on target.
- R1 verification (device idle pre-checked; evidence
  `~/mobile_vt/.codex_tmp/plan3_verify_20261109_180248/`, local copy fetched,
  4 evidence files hash-matched):
  - **Throughput: segB_clean (1080p60) via ffmpeg-pipe + custom HW binary:
    497 frames, 33.32 fps, 0 errors, 0 pipe drops, RC=0 clean exit** —
    vs 7.3 fps (cv2 PyAV path) / ~2 fps (to_ndarray). 30-50 fps target range
    reached (stream is 60 fps; decode ceiling ~33 fps).
  - Golden HW via pipe: 72 frames (= the 1920 section), 0 errors/0 resets;
    dmesg confirms the expected POC8 `0xf` abort (1832 section lost to the
    known P0 firmware issue); ffmpeg CLI error tolerance + reinit at the
    1920 IDR recovered the rest without pipeline-level resets.
  - Remote suite (venv): 54 tests, 53 pass, **only the known V13 error**
    (`Flags.output_corrupt` lowercase on PyAV 11) — no new failures; the new
    ffmpeg-pipe golden test passes on target.
  - Post-run: no process, `/dev/video0` free.
- Conclusions: `verified` — ffmpeg-pipe backend meets throughput target on
  CM311 with correct clean-stream content (497/498; the 1 corrupt frame is
  the stream's own); deployment hash-chain intact; rollback available from
  backup tar. `unverified` — live-link behavior with the new backend (needs
  R2 run 4), HDMI output, YUV hash comparison of the golden 72 frames
  (count + prior 71/72 evidence inherited), long-run thermals/RSS.
- No commit (user instruction). Remote working tree now carries: config.py
  (backend fields), pipeline.py (factory merge), ffmpeg_pipe.py (new),
  tests (new/updated) — all hash-recorded; prior backups cover rollback.
- Next options: (1) live run 4 with ffmpeg-pipe + priming (R2; confirm RF
  setup first); (2) HDMI display integration (R2); (3) recovery-policy
  redesign (stall→continue-without-reset experiment); (4) trivial V13 test
  compat fix; (5) long-run stability/thermal measurement.

### 2026-11-09 17:46-18:05 HKT — Plan 3 PC implementation complete (ffmpeg-pipe backend)

- User approved recommendation: FFmpeg-subprocess backend. Backup #2 before
  implementation: `/home/billieguo/billie_guo/src/rm/mobile_vt/.codex_tmp/backup_before_plan3_20261109_174637`
  (manifest.sha256 inside; PC source snapshot + uncommitted patch + HEAD).
- Implemented `vt13_video/ffmpeg_pipe.py` (`FfmpegPipeDecoder`, subclasses
  HevcDecoder reusing IRAP gating/error-reset): ffmpeg subprocess
  (`-c:v <ffmpeg_codec> -f hevc -i pipe:0 ... -pix_fmt nv12 -c:v rawvideo
  -flush_packets 1 -f nut pipe:1`), reader thread demuxes nut via PyAV
  (correct per-frame dimensions), cv2 NV12→BGR conversion, bounded frame
  queue (256, drop-oldest), stderr drain to logger, EOF drain 10 s guard
  then kill (V09 workaround), version-aware `-fps_mode`/`-vsync`.
- Config: `decoder.backend: pyav|ffmpeg-pipe` (default pyav),
  `decoder.ffmpeg_path`, `decoder.ffmpeg_codec` (default hevc_v4l2m2m);
  pipeline factory selects backend. Default behavior unchanged.
- Key bug found and fixed during PC validation: the CLI raw-hevc demuxer
  sets extradata, after which the decoder IGNORES mid-stream same-id SPS
  updates (CLI stayed 1832x1032 on the golden while PyAV CodecContext —
  no extradata — correctly produced 33x1832 + 72x1920, verified on CM311
  with the same 6.1.1 library; nut packet sizes/framemd5 confirmed).
  Fix: backend detects SPS payload hash change and gracefully restarts the
  ffmpeg process (drain old frames ≤5 s, new process initializes from new
  in-band params). Also sidesteps nut dynamic-header limitations.
  Earlier reader bug (`au.au_index` AttributeError) fixed to `self._au_index`.
- PC validation: **56/56 tests RC=0** (4.544 s), including new golden
  ffmpeg-pipe test on system ffmpeg 4.4 SOFTWARE hevc: 105 frames,
  1832x1032 → 1920x1080 via SPS restart, 0 errors. Evidence
  `.codex_tmp/plan3_pc_tests_20261109_174910/` (logs + changed_files.sha256:
  ffmpeg_pipe.py `4889a2fc...`, config.py `4d76e34a...`, pipeline.py
  `c05d63db...`, test_ffmpeg_pipe.py `7867fc71...`, test_config.py
  `2f57e7f4...`).
- No commit (user instruction). CM311 deployment is R2 (working-tree
  writes): package presented, awaiting approval. Remote pipeline.py is the
  experimental version (`85e57ea8...`) — merge = apply ONLY the decoder
  factory hunk, preserve async-USB/catch-up experiments; verify markers.
- Next: on approval, staging sync (ffmpeg_pipe.py new; config.py replace
  with hash checks; pipeline.py hunk merge; tests), remote test suite,
  segB_clean 30 s throughput with custom ffmpeg + hevc_v4l2m2m
  (target ≥20 fps), golden HW replay behavior, manifests, docs.

### 2026-11-09 17:30-17:55 HKT — offline throughput profiling: Python serial path is the bottleneck

- User order: run 3 first, then offline work. Run 3 results in previous entry;
  this entry covers the offline profiling campaign (all R1, device idle
  verified before each run, evidence in prep dir + CM311
  `plan2_build_20261109_140638/prof_*`, `tput_*`).
- Isolation matrix (30 s gapless replay, run2_nogap.bin): v4l2m2m bgr24
  22 frames/2.08 fps; v4l2m2m gray 22/2.25; SW hevc bgr24 25/5.67; SW gray
  25/5.32. Output format barely matters; HW slower than SW inside the
  pipeline (opposite of raw-codec benchmarks).
- Instrumented profile: `_convert_frame` (to_ndarray) 470 ms/frame in situ;
  v4l2m2m decode itself ~5 ms/AU excluding convert; parser/reads negligible.
  BUT cv2 monkeypatch experiment cut convert to 31 ms/frame with NO wall-time
  change → conversion was not the sole limiter; also discovered the 22-frame
  count was an ARTIFACT: without priming, run2 raw's first two IRAPs lack
  parameter sets → 554/579 AUs skipped, only the last 25 AUs decodable.
- Microbench (1080p NV12): custom swscale 81 ms/frame == Ubuntu swscale
  83 ms (HAVE_NEON=yes; "no accelerated colorspace conversion" C fallback is
  inherent to this conversion, not a build defect); **cv2.cvtColor
  NV12→BGR = 10.8 ms (7.5× faster)**.
- True steady-state test on fully-decodable `segB_clean.h265` (498 frames,
  params bootstrapped, 1080p60): to_ndarray run hit 40 s timeout with no
  final JSON (`--seconds 30` did not terminate promptly — stop-responsiveness
  issue, V09 family); **cv2 path: 220 frames/30 s = 7.3 fps**, still running
  at 30 s. Per-AU serial v4l2m2m round-trips (~400 ms/AU when fed one-by-one)
  + Python per-chunk plumbing dominate. Custom FFmpeg CLI does 24 fps at
  1080p (2026-11-08 benchmark) → hardware capable; the Python integration
  pattern is the ceiling.
- Conclusions: `verified` — cv2 conversion is a 3.5–7.5× win worth adopting;
  `verified` — current PyAV-serial pipeline tops out ~7 fps at 1080p60,
  cannot meet 30–50 fps; `verified` — profile artifacts from missing params
  (always prime for throughput tests); `unverified` — batched/asynchronous
  PyAV feeding ceiling; subprocess-backend end-to-end latency.
- Options for 30+ fps: (a) optimize PyAV path (batch packets in flight,
  async drain, cv2, chunk batching) — moderate work, uncertain ceiling;
  (b) FFmpeg-subprocess backend using the verified 24 fps custom binary
  (rawvideo pipe + cv2) — clearer path; (c) accept lower fps temporarily.
- No source changes made (all monkeypatch/stdin experiments); no commit.
- Next: user decision on backend direction; recovery-policy redesign still
  open (stall→WAIT_IDR devastating with establishment-only IRAPs); RF setup
  confirmation still pending; HDMI later R2.

### 2026-11-09 17:20-17:30 HKT — live run 3 (priming): mitigation verified; RF damage persists

- Third R2 smoke, user approved; launcher updated (SHA256 `c565cc22...`,
  bash -n both sides) with `DJI_PARAMS_FILE` priming + `--save-parameter-sets`.
  Priming file SHA256 `f9f019a1...` == project's `live_runs/vt13_params.h265`
  (cross-verified 1080p60 config). User cycled wireless at READY and once
  mid-run. Session `dji_20261109_172018`; evidence local
  `.codex_tmp/live_smoke_20261109_172018/`, raw SHA256
  `f263935b20aea921aefcaee61456e43bb6086a46db604bd9b8106bab1f47099d`;
  `params_latest.h265` auto-saved (same 1080p60 hash). Post-run idle.
- **Priming VERIFIED**: all 4 IRAPs started the decoder immediately
  (`keyframe_starts=4`), no "parameter sets incomplete" stalls — run 2's
  failure mode eliminated. Frames 22→70, corrupt 0, 1920x1080.
- **But RF damage persists**: 32.7 s dropout before first establishment;
  data arrives in ~0.5 s periodic bursts; 123 USB stall recoveries; driver
  POCs jump 46→110→205→235→269 (missing frames); **1 firmware `0xf` abort
  at POC269** (idx=1078/2040, dmesg `dmesg_live_smoke3.txt`); recurring
  `output POLLERR` → 12 decode errors. Distance/obstruction during runs 2-3
  still unconfirmed by user.
- **Recovery policy still devastating**: 127 decoder resets (123 from
  usb_stall discontinuities + 4 error resets), 615/709 AUs skipped (87%).
  With IRAP only at establishment, every stall-reset discards video until
  the next link cycle. Priming alone cannot fix this; the stall→WAIT_IDR
  policy needs redesign (continue-without-reset / concealment tolerance).
- Conclusions: `verified` — parameter-cache priming removes the
  missing-params failure; `verified` — good-link content decodes clean
  (run 2 offline 497/498; run 3 corrupt=0 on arrived frames); `unverified`
  — RF environment quality (POC jumps indicate ongoing loss), pipeline
  throughput root cause (~2-4 fps), HDMI.
- No commit; no working-tree writes beyond .codex_runs launcher (own
  scratch file, hash-recorded).
- Next (user ordered: offline work now): (1) throughput isolation matrix
  (codec × output_format, bounded gapless replays); (2) recovery-policy
  replay experiments; (3) user to confirm RF setup/distance and mode-lock
  options before further live runs.

### 2026-11-09 17:02-17:12 HKT — live run 2 (close-range): RF attribution resolved; param-cache mitigation verified

- Second R2 smoke (user approved "launch the experiment"; user cycled wireless
  off once; expected two 1080p segments). Session `dji_20261109_170226`,
  evidence local `.codex_tmp/live_smoke_20261109_170226/`, raw 11,103,382 B
  SHA256 `624a0f93a11ec4a210d2ea019f54afd92b9bfdd0dd8c5c3f5737fa1f4d62b6c0`
  (local==remote). Data stopped at t=58.5 s of the 90 s window.
- Run 2 timeline: 4 IRAPs (t=0.375/27.81/39.688/58.547); **first two IRAPs
  arrived WITHOUT VPS/SPS/PPS** → pipeline logged "parameter sets incomplete",
  never started decoding those segments; 26.3 s gap (user off-cycle) + 11.0 s
  gap coinciding with mode change 1080p60→1832x1032@30 at t=39.7 (in-band
  params, decoder started, ~22-25 clean frames); 1080p60 params reappeared at
  t=58.5 just before data stopped. 124 USB stall recoveries; final line:
  22 frames, data=no.
- **RF attribution resolved (offline bootstrap test)**: run 2's 1080p60
  segments decoded with run 1's hash-identical 1080p60 parameter sets
  prepended: **segB 497/498 clean (99.8%), segA 34/35 clean**; authoritative
  trace of the 1832 section: POC 1–21 sequential; **zero NEW `0xf` events in
  dmesg for run 2** (the 2 grep hits are run-1/Phase-C old events). Conclusion:
  **run 1's 97% corruption was RF-environment damage; 1080p60 mode itself and
  the CM311 decoder produce clean output on a good link.** (Distance during
  run 2 not yet confirmed by user.)
- **Parameter-cache mitigation verified (R1 replay)**: run 2 raw (gapless
  copy) + `--parameter-sets-file params_1080p60.h265` (102 B, extracted from
  run 1, hash-verified config) + venv v4l2m2m: decoding started at the first
  IRAP, **222+ frames, 0 errors, 0 recoveries** before the 120 s replay
  timeout (RC=124, not EOF). Live run 2 without priming had been stuck at
  22 frames/124 errors. Evidence `plan2_build_20261109_140638/` on CM311
  (`run2_nogap.bin`, `params_1080p60.h265`, `replay_v4l2.yaml`) + local
  `param_cache_replay_output.txt` in prep dir; forensic artifacts in
  `.codex_tmp/live_smoke_forensics_20261109_163037/` (incl.
  `run2_segB_bootstrapped.h265`, `run2_seg3.trace.log` on CM311).
- **NEW performance finding (V11)**: gapless pipeline replay on CM311 runs
  at only ~2–4 fps end-to-end (222 frames/120 s), while raw codec tests do
  17–24 fps — pipeline overhead (likely per-AU serial v4l2m2m round-trips,
  Copy-Out memcpy, bgr24 swscale+numpy on A53) must be profiled before any
  30–50 fps claim. Regular 0.5 s "read gaps" in gapless replay indicate
  source-thread backpressure from the slow decode path, not USB timing.
- Reader-bug note: a quick inline POC reader produced garbage on run 2
  (wrong offset); authoritative `trace_headers` overruled it — always
  cross-check bit readers against trace (run 1 reader was trace-verified).
- Conclusions: `verified` — good-link 1080p60 stream is clean; param-cache
  priming recovers decoding when re-establishment IRAPs lack parameter sets;
  mode auto-switching causes ~11 s outages; IRAP-only-at-establishment
  reconfirmed. `unverified` — run-2 physical distance; pipeline throughput
  root cause; HDMI.
- No commit; remote writes limited to .codex_tmp test artifacts.
- Next: (1) user confirms run-2 distance + how to lock DJI output mode;
  (2) live run 3 WITH primed parameter cache (R2) to validate end-to-end
  recovery; (3) pipeline throughput profiling (offline); (4) HDMI later R2.

### 2026-11-09 16:30-16:55 HKT — live-capture forensics: upstream stream damage, 1080p60 mode switch

- PC-side forensics of `live_smoke_20261109_161254` (R1; evidence
  `.codex_tmp/live_smoke_forensics_20261109_163037/`): 90 s, 41.6 MB,
  2161 AUs; 12 gaps >0.5 s incl. **33.3 s zero-data dropout (t≈9.7–43 s)**
  despite user's controller LED showing link-on; 117 USB stall recoveries.
- Timeline: t=0–10 s sparse 1832x1032@30 (23 VCL); t=40–50 s sparse
  (18 VCL); **t=53.8 s transmitter switches to 1920x1080@60** (IRAP #3 with
  NEW VPS+SPS; authoritative trace: seg1 `pic_width=1832 height=1032
  time_scale=30`, seg3 `1920/1080/60`; PPS identical throughout); t=54–90 s
  full-rate ~600 VCL/10 s (~10 Mbps).
- Stream integrity (PyAV SW with OUTPUT_CORRUPT): **2161 frames = 65 clean +
  2096 corrupt (97%)**; clean per IRAP segment: 22 / 24 / 19 then corrupt to
  end. Firmware `0xf` at POC24 (dmesg) agrees with SW corruption onset.
- POC sequence (custom-FFmpeg `trace_headers`, TRACE_RC=0 both segments,
  logs on CM311 `plan2_build_20261109_140638/segment{1,3}_vps.trace.log`):
  seg1 POC 1–22 sequential; seg3 POC 1–16 sequential then **erratic jumps
  (~+30 with occasional +1 runs: 16,32,61,62,95,126,156,...,247,248,249,250,
  52,53,82,...,208–221...)** — inconsistent with a healthy sequential 60 fps
  stream; indicates severe bursty loss or slice-header bit corruption
  arriving from upstream (wireless/transmitter), NOT a CM311 decoder bug.
- Corrections to earlier entries: (1) "3 identical SPS" was a NAL-type
  labeling error (VPS=32/SPS=33/PPS=34; the 6-byte NAL is the PPS, normal);
  VPS+SPS actually CHANGE at segment 3 (the 1080p60 switch). (2) "35 s of
  healthy video discarded after the 0xf reset" is wrong — that video was
  97% corrupt; the pipeline's IRAP wait discarded mostly unusable input.
  (3) The 33 s dropout contradicts the LED; link-layer health cannot be
  judged by the controller LED alone.
- Conclusions: `verified` — live receiver→USB→pipeline path delivers and
  records faithfully; decoder reactions (SW corrupt marking, HW 0xf abort)
  are consistent with damaged input; IRAP-only-at-establishment + no IDR
  request makes any damage persistent until physical link re-establish.
  `unverified` — damage attribution (RF loss vs transmitter 1080p60-mode
  anomaly vs receiver); needs controlled experiments.
- User info received: link took ~10 s to establish after program start, LED
  stayed on, no other link-loss indicator available, no active IDR request
  found in DJI ecosystem.
- Next (needs human/hardware): (1) close-range ideal-RF smoke to isolate RF
  vs mode; (2) if configurable, lock transmitter to 1832x1032@30 and retest;
  (3) question: how is the DJI output mode selected (auto/app/goggles)?
  Offline meanwhile: recovery-policy replay experiments (lower priority than
  link integrity); driver 0xf-abort robustness remains a long track.
- No commit; no new remote working-tree writes (trace logs in .codex_tmp).

### 2026-11-09 16:12-16:20 HKT — Phase D live smoke executed (R2 approved): IRAP starvation confirmed

- Approval: user replied "批准" to the R2 package; executed exactly the
  approved scope (config sync + one 90 s headless run). Wireless was already
  flowing at launch (data + IRAP immediately after `USB source open`).
- Config sync verified: pre `062b4ccc...` → staging → post `3bf1229e...`;
  `from_dict({'decoder':{'codec':'hevc_v4l2m2m'}})` accepted on CM311.
  Remote working tree now carries the PC whitelist edit (rollback: backup tar).
- Run: session `dji_20261109_161254`, RUN_DIR
  `~/mobile_vt/captures/manual_live/20261109_161254`, launcher READY confirmed
  (`USB source open` 16:13:00.677), bounded exit ~16:14:30, clean post-state
  (no process, `/dev/video0` free, no dji session).
- Evidence (local `.codex_tmp/live_smoke_20261109_161254/`): `capture.log`
  (21,624 B), `raw_ep81.bin` 41,592,763 B SHA256
  `beb6057b9634878bbe552e8e16c43f5e2e86e574341c5a7ed2b5510fb723507b`
  (local==remote), `raw_ep81.times.tsv`, `raw_ep81.events.tsv`, `smoke.yaml`;
  dmesg tail `plan2_build_20261109_140638/dmesg_live_smoke.txt` (local copy in
  prep dir).
- Results (venv PyAV + patched shared FFmpeg, `hevc_v4l2m2m`, 1832x1032):
  - **43 frames decoded, 0 corrupt**; run-average fps 2.03 (includes freeze
    periods — NOT decode throughput); 2160 AUs / 39.67 MiB over 90 s.
  - **IRAP cadence: 3 IRAPs in 90 s, only at link (re-)establishment** —
    start (16:13:00), after a **33.3 s read gap** (16:13:43), and near end.
    No periodic IRAPs: **user's prior observation CONFIRMED live**.
  - **Live content triggers P0 `0xf`**: dmesg `HEVC_LCU_CHECK status=0xf
    poc=24 idx=910 total=1914 over=1` → `Aborting decoding session!`
    (16:13:55) → EIO×3 → decoder reset → **no further IRAP → ~35 s freeze
    until run end** (the predicted IRAP-starvation failure mode, observed).
  - **USB/wireless instability**: 117 stall errors/recoveries/halt-clears
    (all successful, 0 failures), 128 read timeouts, 129 discontinuities,
    frequent 0.5–1 s gaps + one 33.3 s gap; each `usb_stall` forces
    `_mark_discontinuity` → decoder reset → IRAP wait. 2108/2160 AUs skipped
    (97.6%) mostly waiting for IRAP after resets. Attribution wireless-vs-USB
    not proven; the 33 s gap + IRAP-on-reestablish pattern points to wireless
    link drops.
  - Recovery architecture mismatch (P0): pipeline resets to WAIT_IDR on
    stalls/errors, but the link provides IRAP only at establishment → any
    mid-stream reset freezes video until link re-establishment.
- Conclusions: `verified` — live USB→v4l2m2m→frames path works end-to-end
  when data flows (43 correct frames, clean bounded exit, no SSH loss);
  IRAP-only-at-establishment; live `0xf` at POC24; IRAP-starvation freeze.
  `unverified` — stall attribution (wireless vs USB), decode throughput under
  stable link, 1920x1080 live behavior, HDMI output (headless run).
- No reboot/module reload/service stop; no commit. Remote config.py change is
  the only working-tree write (approved, backed up, hash-verified).
- Human questions raised: wireless environment/distance and whether link drops
  were observed around 16:13:43; whether the link can request a fresh IDR;
  acceptance for stall-reset policy change (continue-without-reset vs WAIT_IDR).
- Next: analyze the recorded raw capture offline (replay with/without reset
  policies, 0xf reproduction at POC24); decide recovery-policy experiment;
  stable-link throughput run; HDMI path remains later R2.

### 2026-11-09 16:05-16:15 HKT — receiver connected; Phase D R2 package prepared

- User connected the USB receiver. Read-only verification: `lsusb` shows
  `2ca3:1020 DJI Technology Co., Ltd. C5` (bus 1, addr 5);
  `python3 -m vt13_video doctor` **RC=0** (usbfs exists, deps OK); no
  decode process; `/dev/video0` free; venv python + tmux present; 105G disk.
  V14 (receiver enumeration) is now satisfied; V03 idle re-verified.
- Created and verified `.codex_runs/live_capture_verified.sh` on CM311
  (V15 closed): bash -n OK both sides, SHA256
  `c254b6315d8090f0c37b95a6b4ac65ebd121a9037cd274e27787b830a825f54f`;
  local copy in the prep dir. Uses verified CLI (`stream --config
  --headless --seconds --record --json-stats`), venv python, run config
  with `decoder.codec: hevc_v4l2m2m`, READY = `USB source open` log line
  (pipeline.py:297), bounded 90 s default, pid/log/raw/JSON-stats in
  `DJI_RUN_DIR`. venv `stream --help` re-confirmed RC=0.
- Remote `config.py` pre-hash re-verified `062b4ccc...` (== local HEAD);
  the R2 package includes a staged per-file sync of the PC whitelist edit
  (post-hash `3bf1229e...`), rollback from the backup tar.
- R2 approval package presented to user (config sync + 90 s headless live
  smoke; wireless enabled by human only after READY). **Awaiting explicit
  approval; no live stream started.** No commit.
- Next: on approval, execute the package, report READY, human opens
  wireless; collect IRAP cadence / `0xf` occurrence / FPS / errors; then
  analyze and update docs.

### 2026-11-09 15:27-15:55 HKT — Phase B success; Phase C root-cause correction (POC8 `0xf`)

- Phase B v3 **RC=0**: PyAV 11.0.0 built into `~/mobile_vt/.venv-v4l2`
  (Cython 3.0.12, `--no-build-isolation`, PKG_CONFIG_PATH exported before
  metadata generation). Identity verified: `ldd` resolves
  `libavcodec.so.60`/`libavutil.so.58` to
  `~/ffmpeg-6.1.1-v4l2-shared/install/lib` (rpath baked in); libavcodec
  (60,31,102); both `hevc` and `hevc_v4l2m2m` available. System Python/av
  untouched. (`libswresample` resolves to system — audio-only, no patches
  there; the patched code is all in libavcodec.)
- Phase C raw clean (venv): SW/HW 30 frames RC=0, YUV 29/30 (index 29);
  HW drain now yields 4 frames (vs 2 with system PyAV) — patched DPB
  behavior confirmed active. Evidence `v16_cm311_pyav_v2_20261109_154228`.
- Phase C full-pipeline golden (venv, timed replay ×2): HW 80 frames,
  errors=3, resets=1 — **identical to unpatched system PyAV**; run 2 also
  hit the 60 s join timeout at EOF drain (78 frames). Copy-Out did NOT
  reduce the loss. Evidence `v16_cm311_pipeline_yuv_20261109_154304/154346`.
- Hypothesis 1 (read-gap firmware idle abort): timed replay logs showed
  `output POLLERR` 0.46 s after a 9.502 s read gap; FileSource auto-loads
  the sibling `.times.tsv` (sources.py:434). Tested with a gapless copy
  (no times file): **same 80-frame/EIO×3 result, discontinuities=0, ×2** —
  hypothesis FALSIFIED. Evidence `v16_cm311_pipeline_nogap_20261109_154851/154928`.
- Hypothesis 2 (earlier attribution "loss at resolution switch"): also
  wrong — after the reset the decoder starts a NEW context at the 1920
  IRAP, so no dynamic reinit was ever exercised in these runs.
- **Root cause (dmesg, deterministic across all 6 pipeline runs)**:
  `HEVC_LCU_CHECK status=0xf poc=8 idx=489 total=1914 over=1` →
  `HEVC_DBG unexpected status=0000000f curr_poc=8` → `Aborting decoding
  session!` — the golden's POC8 (1832 section) triggers the same firmware
  LCU-check failure family as POC21 (`no_sei`) / POC50 (`fresh`) from the
  2026-11-08 matrix. Driver aborts → EIO×3 → pipeline reset → IRAP resync
  at the 1920 section → 25 frames lost. This is the unresolved P0 `0xf`
  issue (AGENTS.md §3.3), NOT a refcount/source-change problem; Copy-Out
  cannot fix it. Full dmesg: `plan2_build_20261109_140638/dmesg_phase_c.txt`
  (local copy in the prep dir; abort lines ~1837/2046-2052).
- Evidence consistency: 5 Phase C run dirs fetched, local/remote manifests
  all matched (6+9+9+10+10 = 44 files), `.codex_tmp/manifests_20261109/`.
- Conclusions:
  - `verified`: Plan 2 Phases A/B — patched shared FFmpeg + venv PyAV work;
    content correct on clean samples; rollback = delete new dirs/venv.
  - `verified`: golden pipeline loss is the P0 firmware `0xf` abort at
    POC8; deterministic; independent of input gaps and of Copy-Out.
  - `falsified`: "Copy-Out rebuild reduces golden loss 25→≈1" and
    "read-gap idle abort" hypotheses.
  - `untested`: dynamic source-change reinit in the pipeline (preempted by
    the POC8 abort); needs a clean synthetic switch stream to isolate.
  - User's IRAP observation raises the stakes: any `0xf` abort mid-live-stream
    waits for an IRAP that may only come at link re-establishment.
- No source file rewritten (all work in new dirs/venv); no commit; no live
  USB/HDMI/wireless run; device idle at close.
- Next decisions: (1) P0 `0xf` driver/firmware investigation (kernel work);
  (2) optional synthetic clean-switch test to isolate Copy-Out's reinit
  benefit; (3) Phase D live smoke (R2, needs USB receiver + human) to measure
  live IRAP cadence and whether live content hits `0xf` — user notified.

### 2026-11-09 15:20-15:27 HKT — Phase B v2 metadata failure, v3 relaunched

- v2 result: **RC=1**. Keyring fix worked (Cython 3.0.12 aarch64 wheel
  installed at 5.2 MB/s), but `pip download --no-build-isolation` failed at
  metadata generation: `pkg-config could not find libraries [...,
  libswresample, ...]` — the script exported `PKG_CONFIG_PATH` AFTER the
  download step, and the system has no FFmpeg dev packages. Script ordering
  bug, not a toolchain problem.
- v3 fix: `PKG_CONFIG_PATH`/`CFLAGS`/`LDFLAGS(rpath)` exported before any pip
  invocation. Verified all 7 `.pc` files present in
  `~/ffmpeg-6.1.1-v4l2-shared/install/lib/pkgconfig/`. Launched via nohup,
  PID 58076, logs `phase_b3.*`; waiter armed. Cython already in venv (no-op).
- No source rewrite; no commit; no live run. Next: on notification, check
  `pyav_identity.txt` ldd paths point at the custom install, then Phase C.

### 2026-11-09 15:13-15:20 HKT — Phase B v1 timeout, v2 relaunched

- Phase B v1: **RC=124**. The 3.7 MB PyAV sdist downloaded fine (4.9 MB/s),
  but pip stalled 300 s at "Installing build dependencies" (isolated build
  env) — likely non-interactive keyring backend blocking or isolated-env
  resolution; root cause not proven. No pip process left running.
- Fix (v2 script `phase_b_pyav_venv_v2.sh`): `PIP_KEYRING_PROVIDER=disabled`,
  `PIP_DISABLE_PIP_VERSION_CHECK=1`, per-command `--timeout 30 --retries 2`,
  preinstall `Cython>=3.0,<3.1` + `wheel` into the venv, then
  `pip download`/`pip wheel` with `--no-build-isolation` (uses venv
  setuptools/Cython directly). Same PKG_CONFIG_PATH/CFLAGS/rpath and
  venv-only force-reinstall; identity check via ldd unchanged.
- v2 launched via nohup, PID 57221, logs `phase_b2.*`/`cython_install.log`/
  `pyav_download2.log`/`pyav_build.log` in the build dir; waiter armed.
- No source rewrite; no commit; no live run. Next: on notification, verify
  ldd points at `~/ffmpeg-6.1.1-v4l2-shared/install/lib`, then Phase C.

### 2026-11-09 15:05-15:10 HKT — Phase A complete; Phase B launched

- Resumed `make -j3` finished: **MAKE2_RC=0** (shared libs + ffmpeg linked).
- `make install` → RC=0 into `~/ffmpeg-6.1.1-v4l2-shared/install`
  (`libavcodec.so.60.31.102` etc.). Original tree/binary untouched.
- Device idle re-checked (no decode process, `/dev/video0` free). Clean-sample
  regression with the NEW shared binary (`LD_LIBRARY_PATH=install/lib`,
  `-fps_mode passthrough -flush_packets 1`, `timeout -k 5 45`): **RC=0,
  30 frames, MATCHED=29/30 vs the 2026-11-08 SW reference, first mismatch
  index 29** — identical to the patched static build's known result; the
  Copy-Out/refcount patches are functional in the shared build. Evidence:
  `plan2_build_20261109_140638/shared_regression.framemd5` + `.log`.
- Linkage caveat verified: the installed binary has no rpath and defaults to
  the SYSTEM `libavcodec.so.60` (same SONAME); with `LD_LIBRARY_PATH` set,
  ldd resolves to `~/ffmpeg-6.1.1-v4l2-shared/install/lib/libavcodec.so.60`.
  Phase B must therefore bake an rpath into the PyAV extension and verify
  with ldd; version numbers alone cannot distinguish custom vs system.
- Phase B launched: `phase_b_pyav_venv.sh` uploaded and run via nohup
  (PID 56270, internal bounds 300/1500/300 s), log/rc/pid `phase_b.*` in the
  same build dir; local background waiter armed. Creates
  `~/mobile_vt/.venv-v4l2` (--system-site-packages), pip-downloads PyAV
  11.0.0 sdist, builds with PKG_CONFIG_PATH/CFLAGS/rpath against the new
  shared install, force-reinstalls into the venv only, prints ldd identity.
- No source rewrite; no commit; no live USB/HDMI/wireless. Next: on Phase B
  notification verify ldd points at the custom lib, then Phase C comparisons.

### 2026-11-09 14:52 HKT — Phase A build timeout and resume

- First `make -j2` hit the 2400 s hard bound: `make.rc` = **124**, terminated
  mid-libavcodec. Progress check: 1554/2033 objects (~76%) built; no leftover
  build process; 1.3Gi RAM available; load dropping.
- Resumed incremental `make -j3` (concurrency raised per AGENTS.md §7.3
  load-based rule; memory headroom verified) under `timeout -k 60 3600`,
  remote PID 53066; log/rc/pid `make2.*` in the same
  `~/mobile_vt/.codex_tmp/plan2_build_20261109_140638/` directory. Local
  background waiter armed. No source change; no commit; no live run.
- Next: on notification, if RC=0 → `make install`, clean-sample regression of
  the new shared binary, then Phase B/C.

### 2026-11-09 14:06-14:15 HKT — pre-build backup; Phase A shared FFmpeg build launched

- User instruction: do not commit yet; back up source to the PC `.codex_tmp`
  before any rewrite and markdown the absolute backup path; proceed with
  Plan 2; inform when real-hardware live streaming is needed (Phase D).
- **Backup absolute path (Ubuntu PC):**
  `/home/billieguo/billie_guo/src/rm/mobile_vt/.codex_tmp/backup_before_plan2_20261109_140638`
  (contents and restore procedures: `BACKUP_MANIFEST.md` in that directory).
  CM311 mirror: `/home/billieguo/mobile_vt/.codex_tmp/backup_plan2_20261109_140638`.
  Includes: FFmpeg source tar (no objects/binaries/.git) + `git diff` patch +
  HEAD/status; CM311 `vt13_video/tests/config` tar; PC uncommitted code+docs
  tar + patch. `sha256sum -c remote_manifest.sha256` → all OK, RC=0.
- Phase A attempt 1 (out-of-tree `build-shared/`): configure RC=1 —
  "Out of tree builds are impossible with config.h in source dir" (the
  original static build was in-tree). Original tree NOT modified; the failed
  `build-shared/` scratch dir remains (harmless, documented).
- Phase A attempt 2 (clean-copy approach): `git archive HEAD` from
  `~/ffmpeg-6.1.1-v4l2` extracted to NEW dir `~/ffmpeg-6.1.1-v4l2-shared`;
  applied the backed-up `ffmpeg_uncommitted.patch`; all 3 patched files
  SHA256-verified identical to the original tree (`patch_verify.txt`:
  `v4l2_buffers.c` `6b7eecc6...`, `v4l2_m2m.c` `c077a4b5...`,
  `v4l2_m2m_dec.c` `6a87d081...`). In-tree configure there with the original
  flags + `--enable-shared --disable-static --prefix=$HOME/ffmpeg-6.1.1-v4l2-shared/install`
  → **RC=0**. `make -j2` launched via nohup, remote PID 46044, hard bound
  `timeout -k 60 2400`; log/rc/pid under
  `~/mobile_vt/.codex_tmp/plan2_build_20261109_140638/`. Local background
  waiter will notify on completion.
- Phase B script prepared locally:
  `.codex_tmp/v16_cm311_prep_20261109_122603/phase_b_pyav_venv.sh` — venv
  `--system-site-packages` at `~/mobile_vt/.venv-v4l2`, pip-download PyAV
  11.0.0 sdist (PyPI reachable), build wheel with
  `PKG_CONFIG_PATH`/`CFLAGS`/rpath pointing at the new shared install,
  `--force-reinstall --no-deps` into the venv (shadows system av only),
  then ldd/codec-availability identity check. System Python untouched.
- No source file rewritten anywhere yet; no commit; no live USB/HDMI/wireless.
- Next: on build notification, verify MAKE_RC=0, `make install`, regression-
  test the new shared binary on the clean sample (expect 30 frames 29/30),
  then run Phase B and Phase C. Live hardware streaming is NOT needed until
  Phase D (R2) — user will be informed then.

### 2026-11-09 13:59 HKT — Plan 2 build recon; user IRAP observation

- User operational knowledge (prior hardware use, `unverified` live): the
  wireless VT link appears to send **only one IRAP at link establishment**,
  not periodic IRAPs. If confirmed, any mid-stream decoder reset that waits
  for an IRAP could freeze indefinitely — this raises the Copy-Out fix from
  optimization to critical path, and the live smoke test must measure IRAP
  cadence. The golden capture's 3 IRAPs coincide with 2 read gaps/link
  re-establishments, consistent with this observation.
- User asked for the total Plan 2 (rebuild PyAV against the patched FFmpeg).
  Read-only recon on CM311 via askpass (`.codex_tmp/v16_cm311_prep_20261109_122603/plan2_recon.txt`,
  SHA256 `910aacab5b32567379bb6d95fdc49275f38fac3dc55570b58a182a438a8de27e`):
  - Custom FFmpeg: `CONFIG_STATIC=yes`, `CONFIG_PIC=yes`; `install/lib` has
    no shared libraries; configure = `--prefix=.../install --disable-doc
    --disable-ffplay --disable-ffprobe --enable-debug=2
    --enable-decoder=hevc_v4l2m2m --enable-demuxer=hevc --enable-parser=hevc
    --enable-muxer=null` (defaults otherwise enabled; both `hevc` and
    `hevc_v4l2m2m` present). Git HEAD `e38092e`, 3 patched files modified.
  - PyAV 11.0.0 = system apt package (`/usr/lib/python3/dist-packages`,
    cpython-312), linked to system `/lib/aarch64-linux-gnu/libavcodec.so.60`
    (unpatched) — confirms PyAV bypasses the custom build today.
  - Toolchain: gcc 13.3, make 4.3, pkg-config 1.8.1, pip 24.0, setuptools
    68.1.2, venv OK; Cython missing (installable into venv). PyPI reachable
    (HTTP 200). Disk 106G free; 1.3Gi RAM available; 4 cores → `-j2` builds.
- Plan 2 outline (presented to user, awaiting GO): (A) out-of-tree shared
  FFmpeg rebuild into a NEW prefix `install-shared`, original binary/tree
  untouched, regression-test the new binary on the clean sample; (B) venv
  with `--system-site-packages`, pip-download PyAV 11.0.0 sdist + Cython,
  build with `PKG_CONFIG_PATH`/rpath against `install-shared`, install into
  venv only; (C) re-run raw + full-pipeline YUV comparisons with the venv
  python, acceptance = source-change loss ≈1 frame instead of 25, no hang,
  2x reproducible; (D) later R2: sync PC opt-in config per-file and live
  smoke test. Rollback at every phase: delete new build dir/prefix/venv;
  system Python and the verified static binary never modified.
- No build started yet; no remote file modified; no commit. Next action:
  user GO for Phase A (R1 offline build, bounded `-j2`, logged).

### 2026-11-09 13:29-13:41 HKT — CM311 V16 hardware-decode verification (user-authorized askpass)

- Authorization: user explicitly directed use of the `Local askpass helper`
  pattern from `docs/REMOTE_MACHINE_USAGE.md` ("why we need ssh-copy-id,
  cannot we use askpass"), relaxing the prior conservative §5 interpretation
  for this window. Password was extracted from the doc into `SSH_PASSWORD`
  at runtime (never echoed in commands or output); helper script
  `.codex_tmp/v16_cm311_prep_20261109_122603/ssh-askpass.sh` contains no
  credential. Key auth remains uninstalled; `ssh-copy-id` + password rotation
  still recommended. User also instructed: **do not commit**.
- Access probe: askpass SSH `hostname; uname -m; uname -r` → RC=0,
  `armbian`/`aarch64`/`6.18.59-ophub`.
- Read-only inventory (`.codex_tmp/v16_cm311_prep_20261109_122603/cm311_readonly_output.txt`,
  SHA256 `3d6c95fd0692b156a66467bd9abfae779a7c32ab0ecb79ada9b591b0331d8522`):
  idle (no `vt13_video`/`ffmpeg` process, `/dev/video0` no opener);
  **PyAV 11.0.0 `hevc_v4l2m2m available: True`, context create OK**;
  `meson_vdec` loaded refcount 0; USB `2ca3:1020` still not enumerated;
  custom FFmpeg `n6.1.1` present. Remote hashes: `decoder.py`
  `0a63d896...` and `pipeline.py` `85e57ea8...` match the 2026-11-06 snapshot;
  `config.py` `062b4cccdb20b6478353331dc0ac3002de9047a8b6e6fb92316540484b948edc`
  equals local `git show HEAD:vt13_video/config.py` — remote config is the
  pre-edit baseline, so the PC whitelist diff is the only config divergence.
- All tests ran as stdin scripts over SSH with `ulimit -c 0` and nested
  `timeout -k`; outputs only in fresh `~/mobile_vt/.codex_tmp/` run dirs.
  **No remote working-tree file was modified.** Scripts kept locally under
  `.codex_tmp/v16_cm311_prep_20261109_122603/`.
- Raw PyAV comparison v1 (`v16_cm311_pyav_20261109_133037`, remote only):
  methodological flaws found — parser not flushed (29/30 AUs) and HW hashed
  at aligned 1840x1040 instead of visible 1832x1032 (0/29 match artifact).
  Not used as acceptance evidence.
- Raw PyAV comparison v2 (`v16_cm311_pyav_v2_20261109_133245`): parser flush
  + plane-crop to visible size + planar Y+U+V hashing (framemd5 convention).
  SW 30 frames RC=0 wall 2.114 s; HW 30 frames RC=0 wall 1.752 s, drain OK
  (2 frames); **YUV MD5 29/30, first mismatch index 29** — reproduces the
  custom-CLI baseline exactly. Cross-check vs 2026-11-08 CLI evidence:
  SW 30/30 identical; HW 29/30 identical, only last frame differs
  (CLI `1517d50f...` vs PyAV `2a745ea3...`); frame-0 hash `8071e636...`
  identical across all four. Repeat run `v16_cm311_pyav_v2_20261109_133812`
  gave the same 30/30 and 29/30 result.
- Full-pipeline golden replay, BGR output
  (`v16_cm311_pipeline_20261109_133439`): real `VT13Stream` + `FileSource`,
  `decoder.codec` set by direct dataclass assignment (bypasses the remote
  tree's older config whitelist without editing it). SW 105 frames, 0 errors,
  0 resets; HW 80 frames, **3× `[Errno 5] Input/output error` → 1 reset →
  IRAP resync**, finished without hang. SW switches 1832→1920 at seq 34; HW
  emitted 8×1832 then 72×1920 — the 25 lost frames are the 1832-section tail
  in flight when the driver aborted the old session at the source change.
  BGR hashes matched 0 everywhere → conversion-artifact suspicion.
- BGR rounding isolation (`cm311_bgr_rounding_output.txt`): frame 0 converted
  to a common `yuv420p` intermediate has **identical MD5** (`8071e636...`)
  for SW and HW; direct BGR outputs differ with mean abs 0.44/255, max 93,
  9.3% pixels affected — swscale NV12→BGR24 vs YUV420P→BGR24 path difference,
  not decode corruption. **Acceptance comparisons must use the YUV layer.**
  First attempt of this script failed with `capture POLLERR` ×22 → EIO on
  the first HW open after the pipeline's aborted session; device idle check
  was clean; a fresh open ~4 min later decoded normally (v2 repeat above).
  Observation: post-abort first open can be transiently broken; retry
  succeeds; no R3 reload was needed. Root cause unverified.
- Full-pipeline golden replay, YUV output (definitive,
  `v16_cm311_pipeline_yuv_20261109_133941`): `output_format="yuv420p"` by
  direct assignment. SW 105 frames / 0 errors; HW 80 frames / 3 errors /
  1 reset — **identical counts to the BGR run (reproducible)**. Section
  comparison: **1832: HW 8/8 YUV-identical; 1920: HW 72 frames, 71/72
  YUV-identical, only last frame (index 71) differs** — the same known
  EOF/last-frame pattern as the clean sample. Every HW frame except the last
  is bit-identical to software through the real pipeline.
- Evidence consistency: 4 run dirs fetched; local/remote SHA256 manifests
  all matched (9+9+6+6 = 30 files), under
  `.codex_tmp/manifests_20261109/*.local.sha256` / `*.remote.sha256`.
- Post-run state 13:41:12 HKT (`post_run_state.txt`, SHA256
  `7240fa57f624d449e7a9ba7ce122acf659177399f1c3a5cce90bf7ab78ffc848`): no
  `vt13_video`/`ffmpeg` process, `/dev/video0` no opener, `meson_vdec`
  refcount 0. No live USB/HDMI/wireless run; no reboot/module reload/package
  install; no commit (per user instruction); local worktree remains dirty.
- Conclusions:
  - `verified`: PyAV-native `hevc_v4l2m2m` works on CM311 with the loaded
    source `meson_vdec`; decoded content is YUV-bit-identical to software for
    all emitted frames except the known last-frame EOF difference; the
    pipeline's existing error→reset→IRAP state machine recovers automatically
    from the source-change EIO without hanging.
  - `verified` limitation: unpatched PyAV FFmpeg (no Copy-Out) loses 25 frames
    at the 1832→1920 source change in this golden capture (EIO×3 then IRAP
    resync). Live acceptability is a user decision.
  - `unverified`: root cause of the transient post-abort POLLERR; whether a
    PyAV rebuild against the patched FFmpeg libraries removes the
    source-change loss; long-run performance/thermals; live link behavior.
- Human decisions needed next:
  1. Source-change mitigation: (a) tolerate the IRAP-resync gap; (b) rebuild
     PyAV against `~/ffmpeg-6.1.1-v4l2` libraries (Copy-Out); (c) FFmpeg
     subprocess backend using the verified custom binary.
  2. Hygiene: run `ssh-copy-id` and rotate the plaintext password (askpass
     authorization was window-limited).
  3. Connect the USB receiver (V14) when ready for the R2 live smoke test.
- Next single action: user chooses the source-change mitigation; meanwhile
  the PC opt-in change can be synced per-file to CM311 staging (R2 approval)
  so `decoder.codec: hevc_v4l2m2m` works through the normal YAML path.

### 2026-11-09 12:26 HKT — third V17 probe; CM311 V16 pre-test package prepared

- User instruction: do not commit; continue and test on CM311.
- Host: Ubuntu PC. V17 re-probe (R0): same `BatchMode=yes` SSH command →
  **RC=255** again. Key auth still not installed; agent cannot reach CM311
  non-interactively, and per `AGENTS.md` §5 the plaintext password recorded in
  `docs/REMOTE_MACHINE_USAGE.md` is not used by the agent.
- Prepared a read-only CM311 pre-test package (no device occupation, no file
  modification): `.codex_tmp/v16_cm311_prep_20261109_122603/cm311_readonly_check.sh`,
  `bash -n` RC=0, SHA256
  `109056361b57ee55ed0f9103e577d5b7df65c93f29efbd89f60683f9519f1717`.
  It checks identity, process/`/dev/video0` idle state, PyAV version and
  `hevc_v4l2m2m` availability plus context creation, `meson_vdec` module,
  USB `2ca3:1020` enumeration, remote `decoder.py`/`config.py`/`pipeline.py`
  SHA256 for merge planning, and custom FFmpeg presence.
- Awaiting human choice: (a) run `ssh-copy-id` once so the agent can execute
  the full sequence autonomously; (b) run the read-only script manually in a
  CM311 SSH shell and return the output; (c) explicitly authorize a one-time
  askpass login with the recorded password (would relax §5 for this window;
  not recommended, credential would appear in command logs).
- No CM311 command executed successfully; no USB/HDMI/wireless activity; no
  commit made (per user instruction); local worktree remains dirty.
- Next single action: once access is available, run the read-only check, then
  decide the CM311 V16 path (PyAV-native vs FFmpeg-subprocess) based on the
  codec-availability result.

### 2026-11-09 12:20-12:21 HKT — V17 re-probe and V16 PC-side opt-in hardware path

- Trigger: user asked to continue from the last experiment/plan. The declared
  next action was V16 (integrate `hevc_v4l2m2m` into the live/replay path),
  gated by V17 (agent key auth to CM311).
- Host: Ubuntu PC only. No CM311 command executed successfully this round; no
  CM311 file read or written; no USB/HDMI/wireless activity.
- V17 re-probe (R0): `timeout -k 2 15 ssh -T -o BatchMode=yes -o
  ConnectTimeout=8 -o StrictHostKeyChecking=accept-new billieguo@10.42.0.11
  'hostname; uname -m; uname -r'` → **RC=255**, `Permission denied
  (publickey,password)`. Key auth is still not installed; the human one-time
  `ssh-copy-id` remains the blocker for all remote steps.
- PC-side review (R0): `vt13_video/config.py` `validate_config` restricted
  `decoder.codec` to `hevc`/`h265`, rejecting `hevc_v4l2m2m`, even though
  `HevcDecoder._new_context()` already passes `config.codec` to
  `av.CodecContext.create`. PC `rm` env PyAV 17.1.0 (libavcodec 62.28.101)
  exposes `hevc_v4l2m2m`; context creation succeeds without any V4L2 device.
  The remote snapshot `.codex_tmp/cm311_latest_20261106/vt13_video/decoder.py`
  differs only by the `VT13_AV_THREADS` experiment block inside
  `_new_context`; the new log line was placed at the end of that method to
  keep the future per-file merge clean.
- Changes (PC worktree, **uncommitted**):
  - `vt13_video/config.py`: codec whitelist now `hevc`, `h265`,
    `hevc_v4l2m2m`; default remains `hevc` (opt-in only).
  - `vt13_video/decoder.py`: INFO log `HEVC decoder context created:
    requested=... actual=...` on every context creation/reset; `snapshot()`
    now includes `codec` so `--json-stats` carries decoder identity evidence.
  - `tests/test_config.py`: +2 tests (v4l2m2m accepted; unknown codec
    rejected).
  - `tests/test_pipeline.py`: +2 tests (default stays software `hevc`;
    v4l2m2m context created when the PyAV build exposes it, else skipped).
- Verification (R1, PC):
  - `timeout -k 5 300 /home/billieguo/miniconda3/envs/rm/bin/python -m
    unittest discover -s tests -t . -v` → **RC=0, 54 tests, 3.191 s, OK**;
    all 4 new tests ran without skips. Baseline was 50 tests.
  - Golden offline replay, default config: RC=0, 105 frames, 0 errors,
    0 resets, log `requested=hevc actual=hevc` — software baseline unchanged.
  - Golden offline replay, `decoder.codec: hevc_v4l2m2m`: RC=1, 0 frames,
    `avcodec_open2("hevc_v4l2m2m") returned 22` (PC has no V4L2 M2M HEVC
    device), 9 errors / 3 resets, clean exit at EOF. Negative control only:
    the opt-in path is wired and fails safe without hardware; this is **not**
    hardware-decode acceptance.
- Evidence: `.codex_tmp/v16_pc_optin_20261109_122037/` with `unittest.log`,
  `replay_sw.log`, `replay_v4l2m2m.log`, `v4l2m2m.yaml`, `manifest.sha256`,
  and `changed_files.sha256`. Changed-file SHA256: `config.py`
  `3bf1229e600a4756748c5f73ee6692217909e81d0dc0b09ad2937ef8de6ae9e7`;
  `decoder.py` `4d1205c94c875869d752b4dc87f9bf572f237414222fde49488eb5b3bb5f0a0b`;
  `test_config.py` `7c53740345b227375c63effba155aa9f22693489ece3bfa57865595e053852e1`;
  `test_pipeline.py` `632d4fa07ec279d2c87f072c72d6448223afc256f9b58c8dcd7d4f9deda94e0b`.
- Unverified / risks:
  - CM311 PyAV 11.0.0 may not expose `hevc_v4l2m2m` (its FFmpeg build is
    unknown); must check on target after V17 is unblocked.
  - Even if exposed, PyAV links its own FFmpeg, not the patched
    `~/ffmpeg-6.1.1-v4l2` build: the Copy-Out / refcount workarounds do not
    apply, so dynamic-resolution source change may hang. Fallback options:
    rebuild PyAV against the custom libraries, or an FFmpeg-subprocess
    backend using the verified custom binary.
  - Local Git worktree is dirty: 3 control docs from the prior round plus
    the 4 files above; nothing committed this round.
- Human action needed (one time, on the Ubuntu PC):
  `ssh-copy-id -i ~/.ssh/id_ed25519.pub billieguo@10.42.0.11`, then verify
  `ssh -o BatchMode=yes -o ConnectTimeout=8 billieguo@10.42.0.11 'hostname;
  uname -r'` → `armbian` / `6.18.59-ophub`, RC=0.
- Next single action: after key auth works, re-run the `AGENTS.md` §2.2
  read-only inventory, then check CM311 PyAV `hevc_v4l2m2m` availability and
  run a bounded offline golden replay with the v4l2m2m config (R1), comparing
  frame count/content against the software reference.

### 2026-11-09 12:03 HKT — agent SSH access probe (read-only, Ubuntu PC)

- Trigger: user asked whether the agent can reach another machine over SSH.
  No project experiment was requested; this entry records only the access
  probe and its consequence for future CM311 work.
- Host: Ubuntu PC. Commands and exit codes:
  - `command -v ssh scp rsync sshpass` → RC=0; `ssh`, `scp`, `rsync` present at
    `/usr/bin/`; `sshpass` **not installed**.
  - `command -v ssh-copy-id ssh-agent ssh-add` → RC=0; all three present.
  - `ssh-add -l` → RC=0; one ED25519 identity loaded in the agent,
    `SHA256:+EPYDiNosoF8tOu7qDJmQ74L9GXw++Fa/O4zcZBLUz4`.
  - `ssh-keygen -lf ~/.ssh/id_ed25519.pub` → same fingerprint, so the agent key
    and the on-disk default identity are the same key.
  - `timeout -k 2 12 ssh -T -o BatchMode=yes -o ConnectTimeout=8 -o
    StrictHostKeyChecking=accept-new billieguo@10.42.0.11 'hostname; uname -m;
    uname -r'` → **RC=255**, `Permission denied (publickey,password)`.
  - `ssh -v` variant → TCP connect and SSH handshake succeeded; the server
    offered `publickey,password`; the ED25519 key was offered and rejected;
    no other default identity file exists.
- Conclusion (`verified`): CM311 `10.42.0.11` is network-reachable from this PC
  and its SSH daemon answers, but the PC's ED25519 public key is **not** in the
  remote `authorized_keys`. Non-interactive key auth therefore fails.
- Conclusion (`verified`): the agent's shell is non-interactive, so it cannot
  type a password at an SSH prompt. `sshpass` is absent. Password-based
  automation would require either an askpass helper holding the credential or
  a new package install; neither was attempted.
- Action deliberately **not** taken: `docs/REMOTE_MACHINE_USAGE.md` records the
  account and sudo password in plaintext (lines 29-30, 79, 95, 437). The agent
  did not use, echo, or copy that credential, per `AGENTS.md` §5 (no requesting,
  echoing, or recording human passwords). This is flagged to the user as a
  separate hygiene issue: the file is Git-tracked, so the password is in repo
  history and should be rotated and removed if the repo is ever shared.
- No remote file was read or written; no CM311 command executed successfully;
  no USB/V4L2/HDMI/wireless activity, reboot, module reload, or package install.
- Human action needed to unblock agent-driven CM311 work (one time, on the
  Ubuntu PC, requires typing the CM311 password once):
  `ssh-copy-id -i ~/.ssh/id_ed25519.pub billieguo@10.42.0.11`
  then verify with
  `ssh -o BatchMode=yes -o ConnectTimeout=8 billieguo@10.42.0.11 'hostname; uname -r'`
  which should print `armbian` and `6.18.59-ophub` with RC=0.
- Next single action: after key auth works, re-run the `AGENTS.md` §2.2 read-only
  inventory before any hardware or live step. Tracked as V17.

### 2026-11-08 20:25-20:31 HKT — offline rate benchmark and decoder-path audit

- Preconditions: `/dev/video0` was free; no `vt13_video`/`ffmpeg` process; no
  live USB/HDMI/wireless run.
- Samples: `clean_1832x1032.h265` SHA256
  `2e13db183d5e562094e2952b169f3486cfaad5221b5a4ec8d97ff152f2a7d5bb`;
  `pad_1024.h265` SHA256
  `75e8eb4799d4a6b0341886a8d2fc35ec8fad4e8fc201b34d90cf6ac324b0938c`.
  `pad_1024` ffprobe: 1920x1080, `r_frame_rate=60/1`, `avg_frame_rate=25/1`.
- Commands: Bash built-in `time` plus FFmpeg `-benchmark`; `/usr/bin/time` is
  absent on CM311 (first attempt RC=127), so wall/user/sys came from Bash and
  FFmpeg supplied rtime/maxrss where available.
- Results:
  - `clean_1832x1032`: hardware 30 frames RC=0, wall 1.212 s, user 1.563 s,
    sys 0.322 s; software 30 frames RC=0, wall 1.621 s, user 2.890 s,
    sys 0.334 s, FFmpeg rtime 0.802 s, maxrss 123488 kB. FrameMD5 matched
    29/30; the last hardware hash was `1517d50f...`, software `133559bb...`.
  - `pad_1024` (1920x1080): hardware 38 frames RC=0, wall 1.585 s, user
    1.984 s, sys 0.489 s, FFmpeg rtime 1.248 s, maxrss 118032 kB; software
    38 frames RC=0, wall 2.295 s, user 5.243 s, sys 0.443 s, FFmpeg rtime
    1.472 s, maxrss 143528 kB. FrameMD5 matched 36/38, differing at frames
    37/38 (0-based index 36/37).
- Interpretation: these are short-sample end-to-end FFmpeg+FrameMD5
  benchmarks, not steady-state FPS. Hardware was about 24 fps wall; software
  was about 16-18 fps wall. The 30-50 fps target remains unproven.
- Decoder-path audit: `vt13_video/decoder.py` calls
  `av.CodecContext.create(self.config.codec, "r")` with default
  `decoder.codec: "hevc"`; it does not explicitly select `hevc_v4l2m2m`.
  Therefore current `vt13_video stream/replay` is PyAV software decode. The
  hardware benchmark above is from the custom FFmpeg CLI, not the live pipeline.
- Evidence: `~/mobile_vt/.codex_tmp/cm311_hw_bench_20261108_202504/` and
  `~/mobile_vt/.codex_tmp/cm311_hw_bench_pad_20261108_203050/`; local copies
  under `.codex_tmp/`. Local/remote manifests matched 14 and 12 files,
  respectively.
- Next action: integrate `hevc_v4l2m2m` into the live/replay path, then measure
  long-run FPS, CPU/RSS, temperature, latency, and frame content. Do not treat
  the short-sample rate as an acceptance result.

### 2026-11-08 19:54 HKT — CM311 R0 precheck for live smoke test

- Preconditions: read-only SSH precheck; no `vt13_video`/`ffmpeg` process;
  `/dev/video0` had no opener.
- Identity: `armbian`, `aarch64`, kernel `6.18.59-ophub`.
- Display: `/dev/dri` has `card0`, `card1`, and `renderD128`; SSH
  `DISPLAY`/`WAYLAND_DISPLAY` are empty; `loginctl` shows an active
  `seat0`/`tty7` session; physical HDMI output is not verified.
- CLI: `python3 -m vt13_video --help` RC=0 and `stream --help` RC=0; confirmed
  `--headless`, `--seconds`, `--record`, and `--json-stats`. The source has no
  literal `READY`; use `USB source open` plus a `waiting_*` state as readiness
  evidence.
- USB: `python3 -m vt13_video doctor` RC=1; no matching `2ca3:1020` device;
  `lsusb` shows only the root hub and `23a9:ef18` SG Flash. Live capture cannot
  start until the receiver enumerates.
- Runner: `.codex_runs/live_capture_verified.sh` is missing.
- Commands: SSH `bash -s` read-only checks (`pgrep`, `fuser`, `ls /dev/dri`,
  `loginctl`, `--help`, `stream --help`, `doctor`, `lsusb`, `dmesg` tail).
- Evidence: `.codex_tmp/r0_precheck_20261108_1941/precheck.txt`, SHA256
  `d8b7306e2b646bc7f27389184a231d38a32940c72e732941e9aa1f288cb66e51`.
- Conclusion: CM311 is idle and the VDEC/DRM nodes exist, but the USB receiver
  is absent; the real stream/READY path is still unverified because stream was
  not run.
- Next action: connect/enable the `2ca3:1020` receiver and re-run `doctor`
  until RC=0; then create and verify `.codex_runs/live_capture_verified.sh`,
  request R2 approval for a 30-60 s headless capture, and have the human open
  the wireless link only after READY. No live USB/HDMI/wireless run occurred;
  no CM311 files were modified.

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
