# Intersession Transfer: VT13 / CM311

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
| V03 | CM311 process ownership | 2026-11-08 19:54 HKT R0 precheck: no `vt13_video`/`ffmpeg` process and no `/dev/video0` opener; source `meson_vdec` remains loaded; USB receiver is not enumerated | Re-check immediately before a live or hardware run; do not kill unknown processes; require `doctor` RC=0 |
| V04 | Display stack | Partially checked: `/dev/dri` has `card0`/`card1`/`renderD128`; SSH `DISPLAY`/`WAYLAND_DISPLAY` are empty; `loginctl` shows active `seat0`/`tty7`; physical HDMI output not verified | Actual HDMI output evidence; confirm DRM/KMS, fbdev, or other display path |
| V05 | `vt13_video` stream/READY | `--help` and `stream --help` returned RC=0; confirmed `--headless`, `--seconds`, `--record`, `--json-stats`; source has no literal `READY`, so use `USB source open` plus a `waiting_*` state; stream not run yet | Real `stream` command, READY evidence, stop/exit procedure |
| V06 | Golden capture decode | `clean_1832x1032.h265` software decode 30 frames RC=0 with no missing-reference messages; `no_sei.h265` software decode 132 frames RC=0 but with missing refs | Offline replay RC, frame count, decoder errors, FrameMD5 or equivalent |
| V07 | Custom FFmpeg hardware decode | 2026-11-08 `-fps_mode passthrough`: clean 30 frames RC=0, 29/30; `no_sei` POC21 `0xf` RC=134, 14-frame prefix all matching; `fresh_45_to_82` POC50 `0xf` RC=134, 32-frame prefix all matching; `pad_1024` 38 frames RC=0, 36/38; EOF `aud` same-window 3x all RC=137/19 frames and identical (cross-window 22/18/19), `eos` 20 frames RC=134, `zeros` 27 frames 26/27. 20:25-20:31 benchmark: clean HW 30/1.212 s vs SW 30/1.621 s; pad 1920x1080 HW 38/1.585 s vs SW 38/2.295 s; short-sample, not steady-state | Explain/fix `0xf`, padding mismatch, and EOF drain; explain `aud` timeout-window count; add more real samples; run long-duration FPS/CPU/RSS/temperature/latency tests |
| V08 | Kernel module/VDEC | Source module `ca46...` loaded after R3; HEVC advertised; 2026-11-08 dmesg shows `status=0x8` and `status=0xf` (POC21 for `no_sei`, POC50 for `fresh`); `pad` shows `0x8` plus two missing-reference substitutions; EOF drain remains problematic | `uname -r`, `lsmod`, vermagic, relevant `dmesg`, `status=0x8/0xf`; explain EOF state machine |
| V09 | Source Change/POC50/EOF | 2026-11-08 expanded matrix: EOF SW 27 frames RC=0 and identical; HW `aud`/`eos` drain failed, `zeros` 26/27; `pad_1024` RC=0 but 36/38 (first mismatch index 36); `aud` same-window 3x was 19 frames and identical, cross-window counts 22/18/19 | Explain/fix EOF drain/flush and `0xf`; explain timeout-window frame-count variation; validate padding content differences |
| V10 | Live wireless end-to-end | **First live smoke done 2026-11-09 16:12 (R2 approved)**: 43 correct frames via venv v4l2m2m, clean bounded exit; IRAP only at link establishment (3/90 s, user observation confirmed); live `0xf` at POC24 → reset → ~35 s IRAP-starvation freeze; 117 USB stall recoveries + 33.3 s gap (wireless-vs-USB attribution unproven); HDMI not used (headless) | Stable-link throughput run; stall attribution; recovery-policy experiment (continue-without-reset vs WAIT_IDR); HDMI R2; raw capture offline analysis |
| V11 | Performance/latency targets | 30–50 FPS and ~1024×576 remain unconfirmed; short-sample benchmark hardware about 24 fps wall, software about 16-18 fps wall; not steady-state | User acceptance criteria plus CM311 long-run CPU/RSS/temperature/latency evidence |
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
