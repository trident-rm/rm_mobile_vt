# CM311 / DJI C5 — D3 原生 V4L2 + DMA-BUF + KMS 执行计划

> 版本：v1.0（2026-11-10）  
> 状态：**计划／待执行；本文不表示已部署或通过任何 D3 验证**  
> 面向：Codex Worker、项目维护者  
> 上位规范：仓库 `AGENTS.md`（若与本文冲突，执行更严格的安全限制）  
> 目标：在不破坏目前 kiosk + KMS 可运行基线的前提下，验证并实现 **1080p60 HEVC 持续实时接收、硬解、显示与可恢复运行**。

---

## 0. 工作原则与权限边界

1. **不覆盖现有 release，不替换当前稳定可运行程序。** 所有 D3 工作在独立工作分支、独立可执行文件和独立日志目录完成。开始前检查未提交改动，绝不擅自 `git reset --hard`、`git clean -fdx`、强制 checkout 或删除捕获文件。
2. **先审计／验证，再决定实现。** D3-0 的 Gate 不通过，不启动大规模 D3a 重写。
3. **严格区分吞吐（unpaced FPS）、显示刷新率（presented FPS）与直播有效帧率（valid unique live frames/s）。** 不能用 `ffmpeg -f null` 的 89.9 FPS 代替 HDMI 60 FPS 的证据。
4. **默认 PC 负责源码编写、静态分析、复杂差分和日志计算，CM311 负责真实 VDEC/DRM 硬件验证。** PC 构建／生成文件须在 CM311 的 aarch64、内核头文件、库版本和 ABI 上验证，不得以 PC 成功代替板端验收。
5. **KMS/DRM 会抢占显示资源。** 即使不 reboot、不改内核，任何可能取得 DRM master、黑屏、破坏 kiosk 输出或让现有应用停止的操作均必须先获得人工明确批准。不得绕过权限或强行 kill 现有进程。
6. **不擅自启动真实无线图传实验。** 当前操作要求是：**先启动接收程序，随后由人开启 DJI 无线图传**。Agent 必须核对实际 CLI，给出整段可复制命令、预期日志路径、停止步骤及现场操作顺序；由人操作后交回日志供自动分析。
7. **内核模块替换／重载、firmware 替换、重启、分区迁移、修改 boot/default target、停止 LightDM／系统关键服务、可能中断 SSH 的操作**均需单独请求人工审批（含备份、命令、影响与回滚）。
8. 所有结论附带日志或代码位置；把**测量事实、假设、目标**三者分开标注。一次成功不等于稳定可部署。

## 1. 项目现状与约束（Worker 最新阶段总结）

### 1.1 系统环境

| 项目 | 已知事实 | 注意事项 |
|---|---|---|
| CM311 | Armbian `6.18.59-ophub`、aarch64、4 核、约 1.7 GiB 内存 | 性能评估以板端为准 |
| 启动盘 | USB 根盘（SG Flash），与 DJI 接收器共享 xHCI | 已有 `/dev/shm` vs rootfs 写入对照无明显差异；不等于所有 USB 调度问题都已排除 |
| DJI USB | `2ca3:1020` | 先程序后开无线发射端才有数据 |
| 视频流 | 1920×1080、约 60.3 AU/s、DPB≈2、无重排、周期性 IRAP（约 8 帧） | 实际以新捕获 SPS/POC 为准；不能假定 P 帧可任意丢弃 |
| 当前桌面 | kiosk：LightDM 已停用，default `multi-user.target`，无渲染器则 HDMI 是控制台 | **不得**修改开机 target 或独占 DRM 不经批准 |
| 当前实现 | Python USB/DUML/HEVC、KMS 显示；已有 `tools/kms_render.c` | 保留已有控制面、I-frame request、kernel watcher 和过滤逻辑 |
| 部署改动 | `config.py 25004fb8`，`ffmpeg_pipe.py 67a40898`，`pipeline.py 9ada66df`（用户记录版本标识） | 不是 Git commit 确认；需实地核对文件 SHA / diff；本地改动未 commit |

### 1.2 已测性能（只作历史基线，不等同当前复现）

| 测试路径 | 数值 | 可推出的结论／限制 |
|---|---:|---|
| 仅接收不解码 | 约 60.3 AU/s，10.2 Mb/s；451 GOP 仅 2 个 POC 缺口 | 接收层在不受消费端压力时相对干净，不能完全排除发射端间歇异常 |
| 原 live X11/ffplay + Copy-Out | 172–273 帧／60 s，约 30–36 次 `0xf` | 旧版本的差基线 |
| KMS + 25 fps 限帧 + 丢 50% + no-copy + async 2000 | 625–659 帧／60 s，约 14–15 次 `0xf` | **现有可看回退基线**；约 10.4–10.8 有效帧／s，非目标状态 |
| 关闭显示、丢 50% | 1530 帧／60 s ≈25.5 帧／s；2 次 `0xf` | 显示相关负载是重大因素，仍需控制变量 |
| 干净本地 replay（nut no-copy） | 497 帧，58.5 FPS，0 次 `0xf` | 说明受控回放可接近 60 FPS，不代表真实 live |
| ffmpeg 裸解码 no-copy | 89.9 FPS | 这是离线未受显示节流的吞吐 |
| ffmpeg → KMS 离线 | 498 帧／6 s ≈83 FPS | 需核验该计时是否含显示同步或仅写入／队列吞吐 |
| ffmpeg → KMS 直连 live | 仍出现大量 `0xf` / 重建 | 只去掉 Python/PyAV 层不保证直播稳定 |
| Copy-Out | 38.7 FPS（最近一轮） | 与 89.9 FPS no-copy 差约 51.2 FPS；差异来自整个路径，**不能直接判定全由 memcpy 导致** |
| `0xf` 后 ffmpeg 重开 | 重开约 0.28–0.30 s；spawn 到首帧约 0.97 s | 不可相加为单次总恢复，必须按统一事件定义量测 |
| USB 入流 vs 消费 | 60.3 vs 50.7 AU/s | 条件成立时积压速率约 9.6 AU/s；但当前已有不同 drop/gate 模式，需注明测量所在配置 |

**量化核算：** `60.3 − 50.7 = 9.6 AU/s`；如果完全不丢弃且持续 60 s，理论积压约 576 AU。60 FPS 下输入帧间隔 `1000/60 ≈16.67 ms`。1920×1080 NV12 像素约 `1920×1080×1.5 = 3,110,400 B/frame`（不计 stride 对齐），每帧 CPU 复制可能产生明显读写流量。实时“清晰帧率”、`0xf` 率、端到端延迟与离线吞吐必须分别统计。

### 1.3 目前已知失败模式

- live 消费者跑不过源，发生队列堆积／读取阻塞；随之观察到 AU/POC 损伤与 `HEVC_LCU_CHECK status=0xf`。这一正反馈模型有较强实验支持，但不能将所有 `0xf` 的底层机制视为最终已证明。
- `0xf`/POLLERR 导致 ffmpeg 进程重建与有效视频空窗；I-frame request 起效快（p50 约 79–100 ms），但新进程启动到首帧仍约 0.97 s。
- No-copy 的独立裸硬解吞吐较高，当前直播中错误后恢复不完整；Copy-Out 能改善旧 FFmpeg 的 buffer 引用问题，但成本高。
- 大 async 队列会使画面看似平滑但延迟数秒至十几秒；不得把“队列继续增长”当成功。
- 原始 `0xf` 码流中做零填充，512 B 起可改变固件状态，但 **软件／硬件 FrameMD5 为 36/38，不是生产修复**。

---

## 2. 结果目标与通用测量协议

### 2.1 最终验收目标（建议 Gate，非承诺）

| 指标 | D3 阶段目标 | 口径与注意事项 |
|---|---|---|
| 本地未节流解码吞吐 | **≥75 decoded FPS**（稳定样本，最好 ≥90） | 单独 `decode-only`，不被 HDMI 60 Hz refresh 锁住 |
| 文件回放 1080p60 | **连续 ≥60 AU/s 输入**，有效解码 ≥58 frame/s | 与 live 前先测足够长文件；如短文件需循环并正确重置参考链 |
| KMS 帧提交／呈现 | 60 Hz 模式下稳定 **≥55 unique frames/s** | 不将重复刷新计入 unique frame；解释 vblank 统计与 buffer 提交节流 |
| D3b AU 输入管线 | 可持续接收／消费 **≥60 AU/s**，队列不持续增长 | 统计输入、已馈送、延迟／主动丢弃与合法重同步 |
| 直播有效显示 | 干净 1080p60 输入时 **≥55 unique valid frames/s** | 至少三轮 60 s 且不依赖长期积压 |
| `0xf` | 干净条件 **0 次／60 s，连续 3 轮** | `journalctl -k` 时间窗口；若失败，不伪装通过 |
| Fatal 后恢复 | ≥95%（≥20 次受控故障样本）；TTFV p50≤200 ms、p95≤500 ms（**探索性目标**） | **单独**统计 reopen、IRAP、first decoded/first presented；若设备本身重启耗时下限高，修订目标须给证据 |
| 延迟 | 无持续旧帧积压；目标 p95 端到端延迟≤250 ms（条件允许时） | 无可靠发射端时间戳／视觉测量前不可报告精确端到端 ms |
| 长时稳定性 | ≥10 分钟后扩展到 ≥30 分钟，队列有界、无不可恢复冻结 | 报告零帧时段、内存、USB errors、温度与系统日志 |
| 图像正确性 | 干净可对齐样本 SW/HW FrameMD5 相同；KMS 显示视觉验收无色彩错位／撕裂 | DRM scanout 不等于软件帧 MD5；分别验收 |

**强制事件定义**（日志统一采用 monotonic 纳秒或一致时间基准）：

- `usb_bytes_rx`、`au_completed`、`au_enqueued`、`au_dequeued`、`au_submitted`、`v4l2_capture_dequeued`、`frame_presented`
- `au_dropped` 带原因（overflow / damage / wait_irap / deliberate gate），`poc_gap`，`ref_missing`，`keyframe_request_sent`，`irap_received`
- `vdec_abort_0xf`、`v4l2_pollerr`、`session_teardown_begin/end`、`session_reopen_begin/end`、`first_decoded_after_restart`、`first_presented_after_restart`
- 队列 `depth_items`、`depth_bytes`、`oldest_age_ms`、各 V4L2 buffer 状态；CPU、RSS、系统 I/O 与温度

禁止将 `ffmpeg frames decoded`、`frames presented`、`unique video frames` 混用。恢复时间报告 p50/p95、样本数与定义；每次 `0xf` 可能产生许多 `POLLERR`，必须按独立事件统计。

### 2.2 通用测试记录

每项测试需保存：实验 ID、日期、设备 ID、boot-id、内核与 firmware hash、代码 commit/diff、FFmpeg 版本、屏幕 mode/Hz、输入文件 hash、文件长度/有效 AU、是否 active RF、AU drop/gate 配置、DRM master 状态、源／解码／显示计数、错误分类、耗时分位数、退出码、日志路径与复现命令。

避免在正在使用的 USB 根盘上写大量原始高码率日志；优先确认剩余容量，短时使用 `/dev/shm`（避免内存耗尽），复杂分析转到 Ubuntu PC。大规模抓包/压力测试要先定义空间预算和停止条件。全流程记录回退版本。

---

## 3. 优先级与阶段依赖

```text
P0  B0：环境冻结、版本／日志核对、安全准备
    ↓
P0  D3-0：真实 NV12M VDEC DMA-BUF → DRM/KMS 可行性 Gate
    ├─ FAIL → F0：明确失败机制，转回低拷贝 KMS dumb buffer/缓冲池方案
    └─ PASS
        ↓
P1  D3a：独立原生 C Stateful V4L2 HEVC 解码器 + KMS（文件）
        ↓
P1  D3b：Python USB/AU → C worker，离线 replay／受控输入验证
        ↓
P1  D3c：fatal/POLLERR/Source Change 的完整会话复位与状态机
        ↓
P2  D3d：人工协调 DJI live，完成三轮稳定性验证
        ↓
P3  K3：可停／可回滚的 systemd kiosk 服务 + 10–30 分钟 soak
```

**重要补充：** D3c 的状态机设计应在 D3a 就考虑，但真实 fatal 恢复验证可在 D3b 后集中进行。任何一项前置 Gate 失败均不得宣称项目完成。长期保留 kiosk + KMS 10.8 FPS 基线作为 fallback，直到 D3d/K3 达到明确 Gate。

---

## 4. B0：安全盘点与基线冻结（P0，离线／只读）

**工作：**

1. 在 Ubuntu PC 与 CM311 分别检查 `uname -a`、`cat /etc/os-release`、`git status --short`、`git diff --stat`、`command -v`、`pkg-config`、`ffmpeg -version`、`lsusb -t`、`mount`、`findmnt /`、`df -h`；确认实际权限及 SSH 路径。不要预设 SSH 主机名、登录名或源码目录。
2. 找到所有现有 C/FFmpeg/Python/KMS 入口、测试脚本、release 备份和对应日志。对 `config.py`、`ffmpeg_pipe.py`、`pipeline.py` 及 `tools/kms_render.c` 记录 sha256、当前修改 diff；如果版本标识只为用户记录而非真实哈希，须说明。
3. 确认 `/dev/video*` 对应 `meson-vdec`，DRM `/dev/dri/card*`/`renderD*`、实际 plane 格式、显示输出 mode、USB 根盘与 DJI 同 xHCI 状况；只读查看，不抢 DRM master。
4. 检查历史 run2/run4/run15、D1/D3 相关文件是否真的存在，清点其可重放性。禁止重新生成覆盖同名文件。
5. 设计独立构建路径（例如仓库下 `build/d3/`，但以实际目录核实为准）及独立日志目录，并确定回退到现有 kiosk 方案的精确操作。

**交付：** `docs/d3/B0_environment_inventory.md`、`docs/d3/baseline_manifest.json`（真实路径/哈希）、`docs/d3/B0_go_nogo.md`。路径可依真实仓库调整；不得假装已经存在。

**Gate：** 已核对代码版本、设备节点、显示独占约束、历史基线、日志路径与回退方法。缺失任何关键事实先询问人，不继续修改系统。

**安全只读命令示例（在 CM311 上执行；不操作 DRM master）：**

```bash
set -eu
uname -a
cat /etc/os-release
findmnt -no SOURCE,FSTYPE,OPTIONS /
lsusb -t
ls -l /dev/video* /dev/dri/* 2>/dev/null || true
for p in /sys/class/video4linux/video*/name; do
    [ -f "$p" ] && printf '%s: ' "$p" && cat "$p"
done
command -v ffmpeg || true
ffmpeg -hide_banner -version 2>/dev/null | head -8 || true
command -v modetest || true
command -v v4l2-ctl || true
```

**停止条件：** 无法明确当前 kiosk 显示由谁占用，或现有变更/备份不清晰 → 不开始可影响显示的实验。

---

## 5. D3-0：真实 VDEC DMA-BUF → KMS 可行性（P0，必须先过）

### 5.1 要回答的四个问题

1. HEVC 视频经 `/dev/video*` State**ful** V4L2 M2M 解码后，CAPTURE 是否确实输出 `NV12M`/多 plane，支持 `VIDIOC_EXPBUF` 导出真实 **解码图片**所在缓冲区？
2. DRM/KMS 是否能导入**同一批真实 CAPTURE DMA-BUF**（`drmPrimeFDToHandle`/`drmModeAddFB2` 或等效 API），并由兼容 plane 扫描输出？之前成功导出/PRIME/AddFB2/测试 dumb-buffer 是**组件可用证据**，不等于同一块 VDEC buffer 端到端直显成功。
3. 如果可以显示，Y 与 UV 的格式（DRM fourcc `NV12`）、两个 plane 的 fd→handle、pitch、offset、modifier、width/height、颜色范围及裁切是否正确？注意 V4L2 `NV12M` 的 *memory planes* 与 DRM image plane 的语义区别，不能假设两个 plane 必然共用 FD 或偏移为 0。
4. framebuffer 被 HDMI scanout 持有时，能否**确保解码器不会提前 QBUF 覆写同一 buffer**，同时又有足够可重用 CAPTURE buffer 避免 VDEC 饥饿？

### 5.2 最小实现范围

- 首先只做**已有完整 HEVC 文件 → V4L2 decoder → 单张 NV12M capture → PRIME/FB2 → KMS plane**。不涉及 DJI、Python pipeline、请求 IDR、内核改动或持久服务。
- 使用实际 queried capability 与格式：`VIDIOC_QUERYCAP`、`VIDIOC_ENUM_FMT`、`VIDIOC_G_FMT`、`VIDIOC_QUERYBUF`、`VIDIOC_EXPBUF`；通过 DRM plane `IN_FORMATS`、尺寸、pitch 和 modifier 确认兼容性（若支持枚举）。不要凭接口调用存在就推断兼容。
- 处理独立 Y/UV plane handle、fd lifetime、framebuffer lifetime。验证 active framebuffer 的 buffer 不会被提前回收。采用**受 page-flip 完成事件保护**的持有／释放流程；若仅做单帧固定 scanout，记录停留状态，不恢复 QBUF 直到退出显示并彻底释放。
- 与当前 kiosk 的 DRM master 冲突必须先询问人工审批；优先使用独立可执行程序，准确提供启动／退出／恢复命令，不修改 LightDM 和默认 target。
- 视频正确性：校验模式/stride、颜色（绿屏、半绿、UV swap）、裁切和至少 45 s 稳定测试图；再用真实测试视频一帧／短段显示并人工目视验收。

### 5.3 Gate

**PASS（全部满足）：** 同一真实 VDEC CAPTURE buffer 的 DMA-BUF 可被 KMS 导入并显示；像素布局正常；至少连续运行一个受控文件片段无 buffer overwrite/撕裂；所有 fd/FB2/handle 在 shutdown 路径正确释放，`VIDIOC_DQBUF`/QBUF 计数闭合；不影响 SSH、回到原 kiosk 无需 reboot。

**FAIL 决策树：**

| 失败现象 | 必须收集 | 对应下一步 |
|---|---|---|
| PRIME 导入失败 | ioctl、errno、device node、dma-buf exporter、是否多个 plane | 确认 GEM/PRIME import 支持及内存约束，不先改驱动 |
| `AddFB2`/plane commit 失败 | pixel format、pitches、offsets、modifier、plane 支持列表、errno | 检查 NV12/NV12M 语义、stride 对齐、modifier、缩放限制；按硬件支持选择兼容 plane |
| 显示纯绿／灰／色差 | 同帧 SW/HW dump、stride、Y/UV 地址/handle、colorrange | 修复 planes 映射；未验证前不计成功 |
| 正常显示但慢 | VDEC DQBUF、pageflip、CAPTURE 空闲数、排队时长 | 增加 buffer 数量或改变显示持有策略；不要盲目开大队列 |
| HDMI 黑屏／DRM master 冲突 | DRM 资源所有者、commit 错误、恢复指令 | 立即按预先审核方案退出实验并恢复原显示；停工等待人工确认 |
| 基础物理内存不兼容 | exporter/importer 证据、buffer 类型和 heap | **转 F0 低拷贝**；不要强行声明零拷贝可行 |

**F0 备选路径：** 保留已工作的 V4L2 decoder + KMS dumb-buffer scanout，使用预分配缓冲池、有限次数 CPU plane copy、减少转换／分配并做独立性能剖析；或评估其他硬件兼容 DMA-BUF 路径。不得为追求“零拷贝”进行未经批准的 cache/firmware 改动。

**交付：** `D3-0_probe.c`（或实际同等文件）、编译命令、日志、DRM/V4L2 参数清单、逐 plane 生命周期图、PASS/FAIL 结论与下一阶段准入建议。

---

## 6. D3a：原生 C Stateful V4L2 HEVC 解码 + KMS（P1，文件输入）

### 6.1 状态机（不能只写 happy path）

```text
INIT → OPEN_V4L2 → CONFIG_OUTPUT_HEVC → ALLOC_OUTPUT → STREAMON_OUTPUT
     → FEED_AU → SOURCE_CHANGE → CONFIG_CAPTURE_NV12M → ALLOC_CAPTURE
     → EXPORT_DMABUF → STREAMON_CAPTURE → RUN_DECODE_AND_PRESENT
                        ├─ EOS / V4L2_BUF_FLAG_LAST → DRAIN → CLEANUP
                        ├─ NEW_SOURCE_CHANGE → DRAIN_OLD → RECONFIGURE_CAPTURE
                        └─ POLLERR / EIO / KERNEL_ABORT → ERROR → TEARDOWN
```

**严格依照设备实际 Stateful Decoder 行为与事件返回顺序调整。** 不能在收到 Source Change 后直接释放仍被 scanout/DPB 持有的 buffer。V4L2 CAPTURE 图像的 DPB 引用和显示引用是不同的生命周期；每个 buffer 应有明确 owner (`decoder`, `application`, `scanout`, `free`)，必要时记录计数。

### 6.2 必须有的能力

- HEVC Annex-B AU 输入，正确传递完整 AU，不允许普通 P 帧的任意丢弃导致参考链破坏；仅在明确安全边界（例如有效 IRAP 且 DPB 重置可行）重新同步。
- `V4L2_EVENT_SOURCE_CHANGE` 与旧分辨率 drain；支持 1832×1032 ↔ 1920×1080；切换只释放无引用 buffer。
- 处理解码输出 zero-copy 导出、KMS frame import，按 vblank/pageflip 正确回收；至少 N 个有界 CAPTURE buffer（实际 N 根据 `min_buffers_for_capture`、DPB、scanout 持有数选择，**不得凭空写死**）。
- 对待处理的输入和 CAPTURE buffer 建立并发／异步机制，避免 page-flip 线程同步阻塞 VDEC 输入。
- 记录每个 AU/帧的输入、硬解、present 时间和状态；所有 fd、DMABUF、DRM FB、GEM handle 有确定关闭与异常清理路径。
- 文件结束需要验证 drain／最后一帧输出；旧系统 EOF 丢帧不能默认为已修复。

### 6.3 两种性能模式分别测

1. **D3a-dec**：从本地干净文件连续提供 AU，显示关闭或仅在内部回收 CAPTURE，不等待 vblank，测 unpaced 解码吞吐。**Gate：≥75 FPS**，目标 90 FPS，0 `0xf`；每帧序列/数量对得上软件解码的可比较样本。
2. **D3a-present**：1080p 60Hz KMS 正常呈现，按期提交帧，测 unique frame presented。**Gate：≥55 unique FPS**，不积压、没有持续绿／灰／撕裂；不要求 displayed FPS >60。

使用相同文件分别测 D3a-dec、D3a-present，必须明确 DRM mode、VDEC/显示输入格式及重复呈现计数；不可把 83 FPS 的离线 `write()` 吞吐当作真实已显示 83 FPS。

**若未达 Gate：** 优先量化 `VIDIOC_DQBUF` 等待、CAPTURE 空闲数、pageflip wait、CPU 用量／cache、峰值 RSS、场景是否受 vblank 影响。若 decode-only 仍 <60，先暂停 D3b；如 decode-only ≥75 但 displayed <55，优先处理 scanout buffer 回收／KMS plane 同步。

**交付：** 独立 C decoder、构建／运行说明、两模式性能表、FrameMD5/帧计数对照和可重复文件测试脚本。

---

## 7. D3b：Python USB/AU → C Worker（P1，先离线再接 live）

### 7.1 保留已有系统模块

- Python 继续管理 USB 采集、私有协议、AU/POC、DUML 控制、I-frame request、kernel watcher 和当前诊断。
- C Worker 只负责 AU → V4L2 → KMS；数据输入边界必须明确（完整 AU + seq + monotonic timestamp + POC/IRAP 标志 + EOS / RECONFIG 控制）。
- IPC 可选 Unix socket、pipe、共享内存；用实测选，不要预设“共享内存一定快”。先用现有干净 AU replay 复现，再连接真实 USB。
- 入队有严格上界，记录 bytes/items/oldest_age，不允许 25 MiB/20 s 旧帧堆积。
- Drop 策略只用于确知可丢弃且不破坏参考链的部分；如超时严重，应清空旧 GOP、等待下一个合法随机访问点并重置参考状态，不能任意删除参考 P 帧。

### 7.2 关键指标／失败分支

| 指标 | Gate | 失败应对 |
|---|---|---|
| AU replay 吞吐 | ≥60 AU/s 持续送入；worker 有效解码 ≥58 FPS（正常 1080p60 文件） | 核查 IPC write-block、AU 完整性、CPU copy、worker 输入队列、VDEC buffer 等待 |
| 输入队列 | 不持续增长，oldest age 稳态受控（探索目标 <200 ms） | 降低中间缓冲、流控回报；如资源不足，在合法 IRAP 边界重同步 |
| 清洁输入 `0xf` | 0 | 若 C 与 FFmpeg 都同样失败，则回到底层驱动／码流证据，不能认定 Python 是唯一问题 |
| 帧／时间戳 | 输出数量、顺序与对照数据一致（容忍已知 EOF 待解问题需单列） | 修复 AU framing、帧引用和 drain，不进入 live |

**此阶段允许在板上用文件或本地 socket replay；不需要开启 DJI 无线。** 用户确认并批准后，才把测试切换到真实 USB 供给。

---

## 8. D3c：致命错误恢复与分辨率变化（P1）

### 8.1 建议恢复顺序

1. 收到 kernel `0xf`（观察事件）或 V4L2 `POLLERR/EIO`（实际解码 API 错误）→ 标记当前 session invalid；阻止继续提交损坏 AU。
2. 停止 D3 worker 的当前 decode+present 会话，不要求主 Python USB/DUML 控制面退出；关闭旧 DRM FB 引用或先将 scanout 切到安全帧，再回收 buffer。
3. 关闭 V4L2 OUTPUT/CAPTURE streaming，释放所有 buffer 和 DMA-BUF/FD，彻底关闭设备句柄；必要时重开 device 并重新完成 probe/configure。
4. 清空旧 DPB 语义队列和解码输入队列，等待新合法 IRAP；利用已集成 DUML I-frame 请求，但限制请求频率，避免高频请求循环。
5. 记录每个阶段的耗时／错误与恢复结果；若内核还保留硬件错误态、重复 pollerr，停止重试并降级到受控 fallback，而不是无界 busy loop。

要把 `kernel_abort_seen` 与 `POLLERR` 作为不同事件源，采用 dedup/window，将 1582 次 POLLERR 不误认为 1582 次独立失败。出现未知 ioctl/errno 时保存 ioctl trace、dmesg、buffer 状态，不直接通过修改 kernel 忽略错误。

### 8.2 验收

- 先使用离线**已知合法/损坏**样本混合 replay 进行至少 20 次受控 session 重建，目标成功率 ≥95%；在条件可行时 TTFV（错误被观察到 → 第一张真正呈现的合法新帧）p50 ≤200 ms、p95 ≤500 ms。记录 reopen 耗时与 IRAP 等待的独立分布。
- 动态分辨率 1832×1032 → 1920×1080：CAPTURE 重新配置不丢旧 buffer 引用、没有死锁；EOF drain 的帧数与内容需单独验收。
- 通过 20 次恢复并不能替代长时 soak；如果目标被驱动能力限制，必须记录最低可重建时间与新的 Gate 候选，不得静默放宽。

**FAIL 分支：**

| 失败 | 下一步 |
|---|---|
| 仅 STREAMOFF 后仍 POLLERR | 完整 close(fd)/reopen、销毁并重建 C worker，区分内核/用户态残留 |
| close/reopen 后仍不能恢复 | 保留日志并回到 `meson-vdec` session teardown 生命周期审计，未经批准不动驱动 |
| recover 成功但经常等待 IRAP | 分离控制面请求、接收延迟与 AU gate，不无界频繁请求 |
| recover 中出现缓冲区泄漏 | 使用 fd/GEM/FB 计数与 RSS 追踪，修复后重新做所有恢复循环 |
| recover 却画面灰／绿／损坏 | 正确性不达 Gate；保留 GOP/Damage filter，检查参考状态与 buffer ownership |

---

## 9. D3d：DJI live 人工协同验收（P2）

### 9.1 执行准备（Agent 必须提供）

- 从 CM311 上真实代码/CLI `--help`/README 核实程序入口、参数和设备路径；不能编造 `--display kms` 或 `--iframe-on-recovery` 参数。
- 给人一段**可直接复制粘贴、含输出目录/超时/正确 shell quoting 的实际命令**，且说明是否会接管 DRM master。任何需要显示服务切换、停止旧进程等动作在审批后执行。
- 明确顺序：`启动 Agent 准备的接收/解码程序并确认 waiting state` → `人打开无线图传` → `运行 60s 或 10min` → `人关闭图传` → `按安全顺序停止程序` → `保存日志与系统状态`。
- 保留三组可比较对照（相同条件、记录版本）：**现有 kiosk 10.8FPS**、**D3 live with display**、**D3 live without display（如需控制显示资源亦先批准）**。避免在不同 RF/模式状态下比较而不备注。

### 9.2 Gate

| 检验 | 条件 | 未达标处理 |
|---|---|---|
| 连续显示 | 3×60s，unique valid ≥55 FPS（前提为有效 1080p60 入流） | 检查 decode queue、present ownership、USB 读阻塞、reset 时间线 |
| VDEC 稳定 | 3×60s 均 0 `0xf`，干净参考链 | 比较 `poc_gap` 是否先于 abort；按输入损坏／驱动行为拆开修 |
| 无过期视频 | 不能依靠积压 20s 后“流畅播放” | 强制记录 oldest AU age、显示 age，必要时在 IRAP 边界跳到最新 |
| 恢复 | 若发生受控错误，能够自行重新同步且不重启系统 | 参照 D3c 根因与防风暴策略 |
| 正确性 | 目视绿屏/半绿/撕裂 0，录制合法样本可对齐校验 | 修正 NV12 plane、scanout sync 或损坏帧过滤 |

**终止条件：** HDMI 无法恢复、SSH 异常、USB 系统盘报 I/O 错误、内存逼近 OOM、kernel oops、持续高频错误重建、温度过高（阈值由实际设备能力确定）→ 立即停止本次实验并保存状态，若需重启必须请求人工批准。

---

## 10. K3：服务化与 soak（P3，只有 D3d PASS 后）

- 编写 systemd unit 草案，优先 `systemd --user` 或经审核的 system service；提供 `ExecStart`、`Restart`、节流/防重启风暴、WorkingDirectory、日志限额、最小权限与 DRM/USB 访问说明。
- **仅生成 unit 文件不代表允许 enable/start**。启用服务、开机自启、变更 `multi-user.target` 和影响 DRM 资源的动作均先人工批准。
- 先完成 10 分钟 soak，再做 30 分钟；期间记录内存/FD/GEM/DMA-BUF 增长、持续 USB 输入、VDEC 错误、有效 FPS、显示帧 age、CPU 及温度趋势。
- 必须可在无 reboot 的情况下停止新服务并恢复原 kiosk 基线；提供经过核实的 rollback 命令。

**验收：** 10–30 分钟队列无持续积压、没有不可恢复冻结/资源泄漏、日志含足够的 error provenance、SSH 可靠并可复现回滚。

---

## 11. 构建、同步和交付约定

1. Ubuntu PC 上做源码改动／静态测试，可用交叉编译器或本机构建；**不假定 PC x86 编译结果能在 aarch64 运行**。验证目标 libc、内核 UAPI、libdrm、可选 libudev 与编译宏。CM311 板端用确认过的工具链编译/链接或交叉构建后板端执行。
2. 使用新的 `build/d3`/`captures/d3`（实际路径先盘点）。同步优先 `rsync --dry-run` 验证，再执行定向复制；如果没有 rsync，使用 `scp`。**禁止整目录强制覆盖**当前 `mobile_vt` 或 release，尤其不触碰 `/boot`、根文件系统分区布局。
3. Agent 先查到真实 SSH 主机名／端口与工作目录；以下为**占位示例，非可直接运行的设备地址**：

   ```bash
   # Ubuntu PC：先手工设为实际的 CM311 SSH 登录地址
   CM311_HOST='USER@CM311_IP_OR_HOSTNAME'
   # 只读环境检查
   ssh "$CM311_HOST" 'uname -a; findmnt -no SOURCE,FSTYPE /; lsusb -t'
   # 从板端复制实验日志到 PC 上新目录；路径需按实际盘点结果填充
   # scp -r "$CM311_HOST:/REAL/LOG/DIR" ./d3-logs/
   ```

4. 所有候选二进制记录 `file`、`sha256sum`、`ldd`（板端），保存精确源码 commit/diff、构建命令与依赖版本。可重复验证的测试数据须保存大小、SHA256 与 GOP/AU/POC 概要。
5. 不允许在未获许可情况下替换 `codec_hevc.c`、修改内核配置、刷 firmware、覆盖二进制 release、修改 LightDM 默认 target、开机服务或设备权限。

---

## 12. 风险审批模板（必须主动发给人）

在执行任何 DRM master 抢占、可能黑屏、启动/停止服务、安装包、驱动/firmware 变更、reboot、磁盘/分区操作之前，向人提交：

```text
[审批请求]
目的：
为什么必须在 CM311 上执行：
准确命令（可复制，已核验路径/CLI）：
预计影响：HDMI / SSH / USB / rootfs / 现有 kiosk 进程
操作窗口与自动停止条件：
备份或现有状态证据：
回滚命令（已核验）：
执行后的验收与日志路径：
待用户批准：YES（不得自行执行）
```

人没有确认就保持在只读、离线编码、数据分析与文档阶段。若出现不明确情况，先提问，不要自行“修复”系统以继续。

---

## 13. Codex 每阶段报告格式

```text
阶段：B0 / D3-0 / D3a / D3b / D3c / D3d / K3
状态：NOT_STARTED | IN_PROGRESS | PASS | FAIL | BLOCKED
环境：kernel / device / commit / diff / ffmpeg / libdrm / DRM mode
输入：文件/hash/AU/分辨率/FPS/是否 live
命令：精确可复制；是否人工批准
输出：decoded unique fps / presented unique fps / AU in/s / queue-age / error rate
正确性：FrameMD5 / YUV 目视 / POC gap / NV12 stride
恢复：重建次数、成功次数、TTFV p50/p95、POLLERR/0xf 归并
证据：日志文件、构建产物路径、SHA256、复现方式
Gate：每项逐条 PASS/FAIL，不得仅写“正常”
异常与根因：事实 vs 推断
下一步：满足依赖时才进入下一阶段，否则按 FAIL 分支执行
风险：本阶段有没有影响显示/SSH；是否需要人批准
回滚：已验证还是仅拟定
```

## 14. 第一轮明确任务（立即可交给 Codex）

> 阅读 `AGENTS.md` 和本执行计划。**当前只执行 B0，并为 D3-0 提交代码审计与实验设计**；不要直接实施 DRM master 接管、启动无线、部署新二进制、重启、安装依赖或修改内核。  
> 检查 `tools/kms_render.c`、当前 V4L2 CAPTURE 格式、EXPBUF/PRIME/FB2 既有证据、显示 plane 的真实格式/限制，画出 buffer ownership 与 page-flip 回收状态机。  
> 明确指出“原有组件级成功”与“真实 VDEC→KMS 零拷贝尚未证明”的区别。  
> 产出 D3-0 的最小实现方案、精确板端构建／运行命令、验收数据模板、失败分支、审批请求和回退流程；命令所引用的文件/CLI/设备路径必须来自实际盘点。  
> 报告 B0 Gate 后停止，等待人工批准所有影响显示的测试。

---

## 15. 决策总结

**当前推荐：** 维护已有 `kiosk + KMS` 约 10.8 FPS 版本，不继续扩大 async 队列、无差别丢 P 帧或把零填充当作生产修复。下一阶段依次为：

**B0 环境与基线 → D3-0 真正的 VDEC DMA-BUF/KMS 兼容性 → D3a 高吞吐文件解码/显示 → D3b Python AU 接入 → D3c 原生错误恢复 → D3d live 3×60 s → K3 服务化与 soak。**

如果 D3-0 失败，应立即进入 **F0 低复制开销备选路径**，并保持原基线可回滚。最终不是追求 `ffmpeg -f null` 的峰值 FPS，而是 **1080p60 源不断流时，系统能持续处理、正确呈现、不会因反压制造损坏，并能从真实错误中恢复**。
