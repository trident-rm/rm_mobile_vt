# CM311 / DJI C5 — RC1 低延迟 1080p60 稳定显示优化计划

> **版本**：v1.0 · 2026-11-10  
> **用途**：交给 Codex Worker 执行的工程计划与阶段验收规范  
> **状态**：计划；文中所列新目标**尚未验证**，不得写成既成事实  
> **上位安全规则**：仓库 `AGENTS.md`；所有更严格的人工审批约束仍然有效  
> **基线提交**：`e56c5fe`（来自维护者最新交接；执行时必须重新核对）  
> **任务重点**：**60 Hz 稳定、约 60 fps 有效新画面、无闪屏、尽可能无肉眼可见的实时滞后**；只要求 **30–60 分钟**真实 live 验收，不安排无必要的 2 小时或 8 小时 soak。

---

## 0. 执行摘要（Worker 必读）

项目已经完成 D3：CM311 上的 C Worker 使用 **Stateful V4L2 HEVC 硬解 + DMA-BUF → DRM/KMS overlay 零拷贝**，USB/DUML 控制面由现有 Python 管线负责，失效时可以请求 I-frame 并重建 VDEC 会话。画质已由使用者确认可接受；30 分钟连续运行平均 **58.81 fps**，无 corrupt 帧，内存和温度没有明显失控。

**不要重新开发解码器、不要追求 200+ FPS 的 HDMI 显示、不要重启此前失效的 async USB 读线程。** 现在有两个可区分的用户体验问题：

1. **轻微但可感知的 live 延迟**：需先测量端到端与接收器内部各段延迟，再消除过时帧和不必要的等待；不能靠“肉眼感觉”猜测瓶颈。
2. **周期性 VDEC `0xf` 与会话重建**：虽已自动恢复，但可能产生约 260 ms 的停顿；需明确“无闪屏”是指无黑/绿/灰闪、无窗口重建，同时争取减少肉眼可见的冻结。

**首轮只做只读审计与低成本测量设计**；涉及实际 HDMI/DRM 独占、无线链路、服务、内核、系统启动配置等，依照 `AGENTS.md` 申请审批。现有 RC1 始终保留，可一键回退。

---

## 1. 已证实的状态与约束（不应重复做 D3）

| 项目 | 当前交接基线 | 结论与边界 |
|---|---|---|
| 源码 | `e56c5fe`；已有 D3 交接提交链 | 仅交接记录；须通过 `git status`、哈希、板端部署路径核验 |
| CM311 | Armbian `6.18.59-ophub`，aarch64；USB 根文件系统 | 不擅自迁移启动盘或变更内核 |
| 接收器 | DJI USB `2ca3:1020` | **先启动接收程序，后由人打开无线图传** |
| 视频 | 1920×1080，约 60 fps，周期 IRAP | 在实际直播记录中重新核对 AU/s、POC 和 SPS，不凭历史假定 |
| 解码 | 原生 V4L2 worker + DMA-BUF + KMS overlay | D3 已实现；保留零拷贝与显示生命周期控制 |
| 当前 live | 57.8–58.8 fps；30 min 105,856 帧 / 58.81 fps | 帧数统计口径需检查是否为有效 decoded、unique displayed 或提交量 |
| 离线 D3a | 271.6 fps 解码、60.12 fps 呈现 | **吞吐不是当前首要目标**；60.12 不能用来推断 live 延迟 |
| 30 min soak | 128 会话，内存 358→359 MiB，温度 61→67 °C，干净退出 | 已达 30 min 稳定性基线；无需自动扩展到超长 soak |
| 解码错误 | 3×60 s 有 8–12 次 `0xf`/轮；30 min 共 128 会话 | 两套数字的统计口径和实验条件可能不同；不得直接混算 |
| 恢复 | TTFV 约 260 ms；重建时保持上一帧 | TTFV 与观测到的整段画面停顿不一定相同 |
| `VT13_ASYNC_USB` | **必须为 `0`** | 不得因 latency 优化重新启用；此前异步读导致 `0xf` 激增 |
| 其他 live 设置 | `decoder.backend=worker`、控制面和 kernel abort watcher 开、`stall_restart=0`、无录制、`--hide-primary` | 参数键名/环境变量需以真实 `config/vt13_video.kiosk.yaml` 和 CLI 为准 |
| kiosk | LightDM 已停/禁用，multi-user target | 不得为了调试擅自恢复桌面、占用 DRM master 或变更启动 target |
| K3 | systemd unit 仅 draft，未启用 | 服务化不是本轮 latency 优化的先决条件，需要单独 R3 审批 |
| CPU | soak 时 `htop` 观察总体 CPU 占比较低 | **仅代表 CPU 利用率低，不代表线程无阻塞、IRQ/DMA/内存/USB 无竞争** |

### 1.1 必须保留的现有资产

- 原生 C Worker、DRM/KMS overlay、DMA-BUF 共享与正确的 page-flip buffer 生命周期。
- DUML 1 Hz pairing、按需 I-frame 请求、kernel abort 监听、会话自动重建。
- HDMI 画面连续保持、已有 corrupt 帧过滤；`--hide-primary` 所需的 overlay 可见性配置。
- 当前 kiosk YAML、`decoder.py` codec 身份日志，以及足够的调试/回滚证据。
- 原有 release 可随时恢复，测试在独立 branch / staging / executable 完成。

### 1.2 数字关系：为什么 58.81 fps 已接近 60，但仍会卡一下

- 目标 60 fps 的视频间隔：`1000 / 60 ≈ 16.67 ms`。
- 30 min 为 `1800 s`；在 60 fps 时最多可产生 `108000` 个不同时间点的视频帧（假设源恒定 60 fps 且无异常）。
- 当前为 `105856 / 1800 = 58.809 fps`，与理想 60 相差 `2144` 帧，约 **1.985%**。
- **估算（非根因证明）**：若 128 个会话各经历一次 `0.260 s` 无新帧时间，则停顿约 `128 × 0.260 = 33.28 s`；等价于 `33.28/1800 ≈ 1.85%` 的时间，相当于理想平均 `60 × (1−0.01849) ≈ 58.89 fps`。
- 这个估算与实际 58.81 fps 接近，提示 **周期性重建足以解释绝大多数平均帧率缺口**；但不能证明每次重建都会完整丢失 260 ms，且 `128 会话`不必恰好等于`128 次恢复`。
- 要在相同模型下达到 30 min 平均 **≥59.5 unique fps**，允许总无新帧时间约 **15 s**。若单次仍为 260 ms，相当于不超过 **约 57 次**此类间断/30 min；否则就必须减少每次可见中断时间。**此数是规划推算，非要求直接修改驱动的依据。**

**含义**：额外提高 D3a 的离线 271.6 fps，对实时 60 Hz 和约 260 ms 的恢复停顿帮助不大；优先观察帧新鲜度、等待时间及 `0xf` 恢复时的可见停顿。

---

## 2. 目标定义与验收指标（以画面体验为中心）

以下是**建议工程 Gate**，绝非历史测试结论。严格区分三个“fps”：

- **解码吞吐 FPS**：不受 60 Hz 显示刷新率约束的硬件解码能力；已有明显余量。
- **KMS 提交/扫描 FPS**：DRM page-flip 或显示刷新次数，重复同一帧也可以接近 60；**不能单独证明没有丢帧**。
- **有效新视频帧 FPS**：在 HDMI 上实际首次显示、且未因重建而停顿的不同视频帧数/秒；此项更接近使用者体验。

| 指标 | 目前事实 | 优化目标 / 最终 Gate | 测量规则 |
|---|---|---|---|
| 显示模式 | KMS overlay，离线呈现 60.12 fps | **稳定 60 Hz 输出**，不反复退出/重进 DRM | `modetest`/KMS 日志及 page-flip 事件；不误认 60 Hz=60 unique fps |
| 有效 live 帧率 | 30 min 58.81 fps（口径待核对） | 先达到**持续健康区间 ≥59.5 unique fps**；最终 30–60 min **整体平均争取 ≥59.0–59.5 fps** | 按1秒及30/60 min报告：输入 AU、VDEC 输出、首次显示 unique 帧、重复帧 |
| 不可见闪屏 | 0 corrupt；尚缺正式感知 Gate | **0 次黑屏、绿屏、灰屏、半绿、窗口重建、DRM plane 消失** | 程序日志 + 人工目视验收；不以过滤黑帧掩盖长时间停顿 |
| 肉眼可见的长延迟 | 已反馈轻微可见；**未量化** | **最终人眼验收“动作几乎同步，无明显拖后”**，并尽量达到 glass-to-glass p50 ≤120 ms、p95 ≤200 ms（试验目标） | 优先高帧率摄像机同时拍输入真实动作与 HDMI；若 DJI 固有延迟大，分项解释，不谎称可达 |
| 接收器内部延迟 | 未量化 | 先建立基线，**优化前后 p50/p95 至少下降 25%（如基线显著偏大）**；稳态 p95 尽量 ≤50 ms（探索目标） | USB AU 完成→首个对应显示 page-flip 的同一时钟差值；与真正 glass-to-glass 分开 |
| 显示帧年龄/队列 | 未量化 | **稳态无长期增长**；展示 stale AU 队列深度和最大年龄；目标正常状态队列附加延迟 p95 ≤1–2帧（≤33 ms） | 记录 AU 的 `first_seen/complete`、V4L2、KMS 时间戳；不在参考链内乱丢 P 帧 |
| 可见冻结/跳帧 | 约 260 ms TTFV 相关停顿 | 健康段**无 >2 个帧周期的新画面停顿**；恢复段单独统计，重点减少频率或时间 | 区分掉帧、冻结、保留末帧、黑闪，报告最大连续未更新时长 |
| `0xf` / 恢复 | 3×60s 每轮 8–12 次；30 min 128 会话 | **方向性下降且无新增损坏/不可恢复错误**；不要要求靠吞掉固件错误实现 `0xf=0` | `0xf`、POLLERR、session rebuild、IRAP 请求分别计数 |
| 恢复时间 | ~260 ms（定义需确认） | 目标维持或改善 p50，争取 p95 ≤350 ms，绝不因优化使恢复显著恶化 | 明确 error→worker ready→IRAP→decoded→first displayed 的各时间点 |
| 资源 | 30min 内存 358→359 MiB、61→67 °C；总体 CPU 较低 | 不新增持续内存泄漏、CPU 热限制或 USB 堵塞；温度/内存与 RC1 相当 | 同样环境 A/B，记录单线程、IRQ、I/O wait、DMA buffer 数与温度 |
| 稳定时间 | 已完成 30 min | **默认 30 min 验收；有必要才扩展至 60 min** | 不进行 2h/8h 长时间 live，除非人另行要求 |

**重要**：120/200 ms 是供测量驱动的“理想延迟目标”，并非已证明 DJI 端到端一定可以达到。若摄像头曝光、编码、无线链路本身占据较大延迟，Worker 应呈现可测的不可控部分，并仅对 CM311 可控增量负责。不得为了刷新 fps 数字而伪造时间戳、重复展示旧帧或丢失 GOP 依赖关系。

---

## 3. 执行顺序总览

| 阶段 | 优先级 | 核心任务 | 是否需要真实无线 | Gate |
|---|---|---|---|---|
| **L0** | P0 | RC1 冻结、统计口径统一、低风险代码审计 | 否 | 当前工作树、配置、部署哈希与计时点可追溯 |
| **L1** | P0 | 延迟测量：外部 glass-to-glass + 内部 stage timestamps | 是：人工操作 | 输出基线 p50/p95、1秒窗口 fps、冻结、队列年龄 |
| **L2** | P0/P1 | 去掉额外排队与显示等待：最小安全改动 | 是：受控 A/B | 延迟显著下降，正确性和 `0xf` 不恶化 |
| **R1** | P1 | 量化 260ms 恢复与可见冻结；针对性减少间断 | 是：受控 A/B | 新帧中断减少、0 黑闪/绿闪，恢复成功率不降低 |
| **L3** | P1 | 优化 KMS page flip / buffer 生命周期（仅在测得瓶颈时） | 先文件，后真实无线 | 不引入 scanout 覆写、延迟不升、unique fps 维持 |
| **V1** | P0 Gate | 人工画质/延迟目视检查 + 30min live soak | 是：人工操作 | 体验通过、指标通过或明确例外 |
| **V2（可选）** | P2 | 若需要更强信心，扩展至 60 min | 是：人工批准 | 不发生新的长尾故障 |
| **K3（可选）** | P3 | systemd 服务化 / 自动启动 | 无线启动仍由人或产品流程管理 | 单独 R3 审批；不是本轮 latency 阻塞项 |

**硬规则**：每阶段只改一个变量，每个候选补丁可独立回滚；Gate 不达标先报告/分析，不要自动进入下一阶段。

---

## 4. L0（P0）— 冻结 RC1、读取代码和建立测量语义

### 步骤

1. **Ubuntu PC 只读**：查 `git status --short`、`git log -n 8 --oneline`、`git diff`，标记未提交改动；核对提交 `e56c5fe`，不得用 `git reset --hard` 清理。
2. **CM311 只读（SSH）**：读 `uname -a`、当前 worker 二进制的 SHA256、运行配置和启动参数；确认从 PC 同步的树与实际运行文件一致。
3. 检查 `config/vt13_video.kiosk.yaml`、C Worker、`tools/kms_render.c`、Python `pipeline`/USB 读取路径、KMS page-flip / DMA-BUF 回收、ring / queue、恢复状态机。**不要假定旧脚本或示例 CLI 仍正确**。
4. 输出完整当前时间线：USB bulk completion、AU assembled、AU submitted、V4L2 OUTPUT QBUF、CAPTURE DQBUF、KMS commit、page-flip complete、buffer recycled、`0xf`、worker reset、I-frame requested/received。
5. 判断现有 log 是否有统一的 `CLOCK_MONOTONIC` 时间基。不同进程使用同一系统时钟的 monotonic ns；**不要拿 wall clock 或 HEVC PTS 当作真实 wall/glass-to-glass 时间**。
6. 建立 `reports/low_latency/<run_id>/`（PC），保留 `baseline.json`、`metric_definitions.md`、diff、checksum。系统盘在 USB 上，**默认不在 CM311 大规模写原始视频/逐帧 debug log**。

### 准许的只读命令参考（由 Worker 核对目标后执行）

```bash
# Ubuntu PC：在已经确认的项目目录内执行，不写工作树
git status --short
git log -8 --oneline
git diff --stat
git rev-parse HEAD

# CM311：用户已核验 SSH alias 后，纯只读
ssh "$CM311_SSH" 'uname -r; uname -m; free -m; lsusb -t; cat /proc/interrupts | grep -Ei "vdec|esparser|xhci" || true'
```

若 `$CM311_SSH` 未设置，请 Worker 先向人询问正确别名或主机名，**不猜 IP、不扫描局域网**。涉及正在运行的进程和 sudo 的命令按 `AGENTS.md` 额外约束办理。

### L0 Gate

- 已验证当前 live 构建、真实 worker 入口/CLI、配置、日志字段与缓冲区归属。
- 明确哪些 latency 指标当前无法取到，并给出不破坏零拷贝的最小 instrumentation 方案。
- **仅完成 L0 即停止，提交下轮硬件测试需人审批的准确命令。**

---

## 5. L1（P0）— 先量化“肉眼可见延迟”来自哪里

### L1a：外部端到端 glass-to-glass（首选）

由人完成：将 DJI 发射端摄像头对准一个**可瞬时变化、可同时被测量相机拍到的真实物理事件**（例如 LED 灯亮灭或快速移动指示物）；再用手机 120/240fps 慢动作，将**真实事件本身与 CM311 HDMI 屏幕上的对应画面**同时拍进同一段视频。保持充足光照、相机锁定曝光/帧率；选 20–30 个有清晰边沿的事件。

- 每个事件测量 `Δframes / phone_fps`；240 fps 的拍摄时间量化约 `4.17 ms/帧`，120 fps 约 `8.33 ms/帧`，还需考虑两块显示/拍摄设备滚动快门误差。
- 汇报 `n`、最小、p50、p95、最大值，以及现场手机拍摄帧率。视频属于诊断数据，仅按人指定的路径保存/上传。
- **不要**用拍摄两个不共享时钟的显示器倒计时、用主机 `time.time()` 与相机视频直接减，或把接收 AU 时间误称为 camera-to-display 延迟。
- 如果手边没有 120/240fps 手机或 LED，则先做内部延迟测量，并报告“端到端未测”，可提供普通人肉眼操作检查，但不可凭猜测填数字。

### L1b：CM311 接收→显示内部时间线（优先无侵入）

记录的事件（建议字段）：

```text
run_id, session_id, frame_id, au_seq, poc, is_irap
usb_transfer_complete_mono_ns
au_complete_mono_ns
v4l2_output_qbuf_mono_ns
v4l2_capture_dqbuf_mono_ns
kms_commit_mono_ns
kms_flip_event_mono_ns
capture_requeue_mono_ns
status, dropped_reason, queue_depth, queue_oldest_age_ms
```

- **定义与注意**：`usb_transfer_complete` 是 USB transfer 完成时刻，并非像素曝光时刻；`kms_flip_event` 是显示切换事件，不等于屏幕实际发光时刻。
- 使用 `CLOCK_MONOTONIC`（Python `time.monotonic_ns()` 与 C `clock_gettime(CLOCK_MONOTONIC)`）；确保标识能跨 Python→C 匹配。若需更改 IPC，先做独立分支并记录消息格式与开销。
- 优先按 1s 统计直方图或低开销 ring buffer，输出聚合 p50/p95/p99；不要为每帧 `printf` 或同步写 USB rootfs。
- 追踪至**真实 presented frame**；如果 page flip 事件只代表 KMS 的上一次已提交帧，要明确帧 ID 对应规则。

### L1c：验证 htop“低 CPU”的含义

- 在不破坏直播的情况下采样**单线程 CPU**、run queue、context switch、minor/major faults、`iowait`、VDEC/xHCI IRQ、DMA buffer 数、CPU frequency/thermal 与 `poll`/`ioctl` 等待分布。
- 使用已安装工具；`pidstat`、`perf`、`trace-cmd` 等若缺失，不自行 `apt install`；先给出替代 `/proc` 采样方案或请求批准。
- **区分 CPU 忙、线程被阻塞、内存/总线争用以及显示同步**。总体 CPU 很低不能排除单线程、调度延迟或等待 page flip。

### L1 Gate / 输出

1. 有同一配置下至少一次短时现场基线（建议 2–5 min）和一个 30min 历史/新 soak 口径对照；先通过审批，不要求先跑长实验。
2. 图表或 CSV：每段延迟 p50/p95/p99、队列最老 AU 的年龄、有效 unique fps、重复/保持帧、`0xf` 前后时间线。
3. 给出主因分型：**编码/无线固有延迟、USB/AU 组包等待、V4L2 等待、KMS page-flip、重建恢复、或测量不足**。
4. 再决定进入 L2 的单一改动；**不得先猜测并修改队列长度**。

---

## 6. L2（P0/P1）— 减少真实画面滞后与新鲜度损失

> 原则：输入速度约 60 AU/s；优化的是 **最小帧年龄 + 无积压**，而不是“多排队使播放更平滑”。保持 `VT13_ASYNC_USB=0`。

按 L1 证据选择以下候选，并**一次只动一个**：

| 症状与证据 | 候选改动 | 预期效果 | 失败处理 |
|---|---|---|---|
| Python AU 队列持续增长 | 对现有同步 USB 路径增加**有限容量/年龄**的监控与背压策略；不额外建 async USB 线程 | 不积累旧数据，降低显示帧年龄 | 若 USB 读阻塞导致丢字节，应立即回滚；改为安全的整 GOP resync/丢弃而非盲目缩小队列 |
| 过时 AU 已在 decoder 前积压 | 检测过时帧，**仅在安全 IRAP 边界**清除待解队列并重建参考链（如果必要） | 从旧视频跳到最近有效 GOP | 若 0xf 上升/帧损坏，恢复 RC1；不能任意删除 HEVC P 帧 |
| KMS 提交队列导致滞后 | 最多保留必要显示缓存，避免无界 pending flips；追踪提交和 flip 的真实对应帧 | 降低显示端排队 | 若画面撕裂、扫描中重用 buffer，立刻回滚；正确等待 flip completion |
| 解码 CAPTURE 等空闲 buffer | 统计 VDEC buffer lease/回收耗时，调整**buffer pool**（确认内核驱动允许） | 解码与 scanout 并行，防止 buffer starvation | 若延迟增长或内存持续增加，回退到 RC1 原 pool |
| 每次同步等待额外一个 vblank | 检查现有 KMS commit 时机和 vsync 调度；**不关闭必要的同步/安全检查** | 少等待一个 16.67ms 刷新周期 | 若出现 tearing/黑闪，回退；不修改未验证的 DRM 驱动 |
| 只在 abort 附近延迟明显 | 不碰健康路径队列，进入 R1 恢复分析 | 避免为错误恢复问题重写正常播放 | 需要逐事件恢复时间线，不能全归因于网络 |

**严禁**：重新开启已证明致命的 USB async 读、无界队列、大量录制到 USB 根盘、每帧同步日志、因 FPS 不足而随意删除需要作为参考的 P 帧、在显示缓冲仍被扫描时重新 QBUF、关闭关键帧合法性检查或 Frame Damage Gate。

### L2 A/B 规则

- A：同一硬件和发射端位置的 RC1；B：候选更改；至少 A/B/A 或连续可比窗口，记录新旧 commit/二进制哈希。
- 先干净本地录制文件（若该项适用），再真实 live；由于 RF/发射端状态变化，**A/B 不可仅比较总输出帧数**。
- **通过**：p50/p95 帧年龄明显下降（优选≥25%）；每秒新帧数不降，`0xf`/corrupt 不增；KMS 0 黑闪/绿闪，30min Gate 前先做2–5min短测。
- **不通过**：任何 USB 丢字节、`0xf` 明显增加、帧陈旧度不变、内存/温度异常、KMS plane 消失 → 立即停止候选实验，回退至 RC1。

---

## 7. R1（P1）— 剩余 `0xf` / 约260ms停顿：只做有证据的改善

### 首先量化

对每次错误记录：

```text
kernel_0xf_time → V4L2 POLLERR/EIO → decoder_reinit_start
→ device_ready → DUML I-frame request → IRAP_received
→ capture_DQBUF_first_valid → KMS_present_first_valid
```

每段分别统计 p50/p95/max，重点考察**用户最后一次看到新帧 → 第一次看到恢复新帧**的 gap，而不是只报告 `TTFV`。

### 决策分支

| 结果 | 优先路径 | 必须避免 |
|---|---|---|
| 大部分时间在 worker fd close/reopen/重新分配 | 减少重复初始化；在驱动规范允许的情况下复用可复用资源，或优化恢复状态机顺序 | 不跳过必须的 `STREAMOFF`、buf 释放或驱动重置 |
| 大部分时间等待 IRAP | 检查 request 与初始化时机是否重叠，避免重复 request、错误 cooldown | 不重复密集请求 I-frame；不在 reference chain 无效时输出 P 帧 |
| 显示端出现黑闪，但 KMS plane 生命周期不应该断开 | 保持最后一帧 scanout，确保 C worker 重建不清空 primary/overlay | 不能以纯黑/全绿/旧帧长时间持有来“隐藏”故障 |
| `0xf` 与 page flip/USB/IRQ 峰值同时出现 | 先低开销监控、识别是否因果关联，再设计小范围驱动/IRQ 分支 | 不在 RC1 中直接套用内核补丁或重载模块 |
| `0xf` 始终存在但 30min 体验无明显停顿 | 可接受作为已知限制，停止高风险驱动研究 | 不为追求日志清零而破坏稳定版本 |
| 重建失败或变成永久冻结 | 立即回滚候选，检查 V4L2 session 释放与日志 | 不以 reboot 作为常规恢复手段 |

**判断**：剩余 `0xf` 被解释为 xHCI/DRAM 与 VDEC/KMS 争用，仅是目前一个有根据的工作假设，不得记作已证明根因；其他因素可由输入完整性与事件时序区分。

**驱动/IRQ 专项**必须创建独立研究任务，并审批 R3。若 L2/L3 用户态改动已达到“稳定 60 Hz + 低可见延迟 + 30min 无闪屏”，可不进入驱动研究。

---

## 8. L3（P1，条件触发）— KMS / DMA-BUF 最后阶段优化

**仅在 L1/L2 确认 KMS 等待显著影响帧年龄或显示重复后执行。**

检查点：

1. DRM atomic/legacy 提交与 `page_flip` 事件是否每帧产生不必要的额外同步；是否存在**上一帧 release 晚一周期**。
2. NV12M plane 的 fd/handle、stride、offset 与 KMS 显示 plane 匹配；保持 D3-0 的正确性证据。
3. V4L2 CAPTURE buffer 的**多方所有权**：decoder、KMS scanout、代码管理的临时句柄。仅在 flip completion 且不再被扫描后重新 QBUF。
4. 确保 `--hide-primary` 在 worker reset 过程中仍生效，避免 console/primary 突然盖住 overlay 形成闪屏。
5. 避免 VDEC、KMS 两端不断创建/销毁 DRM framebuffer，确认 `drmModeRmFB`、DMA-BUF fd、V4L2 export fd 均按生命周期释放。
6. 只在合法配置下减少额外 buffer 数量。**少 buffer 不必然更低延迟**；过少会造成 VDEC 饥饿和新的 `0xf`。

### Gate

- 对干净文件有像素正确性证明（历史 D3-0 已逐字节一致；候选补丁若改 buffer 布局须重新验证）。
- 无 DMA-BUF scanout 覆写、黑/绿/灰闪、DRM master 丢失；帧年龄、等待时间下降或至少不恶化。
- 如果优化收益小于测量抖动、引入新的资源风险，直接保留 RC1，**不为了形式完整强行改动**。

---

## 9. V1 / V2 — 30–60min 体验与稳定性验收（最终交付 Gate）

### V1：先目视，后30min

1. **短时 2–5min**：人在 HDMI 屏前确认动作跟随性、是否有可见滞后/冻结，特别是在运动和光照变化明显时。
2. **30min soak**：人在场按真实启动顺序：接收程序启动并确认 `READY` → 人开启无线图传 → 运行 30min → 正常关闭。
3. 记录 source AU/s、解码 AU/s、unique displayed fps、display page-flip fps、黑/绿/灰/半绿/tearing 次数、每次 freeze duration、`0xf`/重建/请求 IDR、TTFV、队列最大年龄、内存、温度及 CPU/IRQ/I/O wait。
4. 用户必须明确确认“**画面稳定、不闪屏、不存在肉眼明显的持续延迟**”；如果技术指标通过但人能感到拖后，不得标为完全 PASS。

### V1 PASS 标准

- HDMI 始终以稳定 60 Hz 运行；整个测试**无可见黑闪/绿闪/灰闪/窗口消失**；corrupt=0。
- 正常无恢复区间有效新帧输出接近 60fps；30min 整体平均目标 ≥59.0fps，**优选 ≥59.5fps**。若未达到、但用户明确确认体验已达到要求，可标为 `ACCEPTED_WITH_LIMITATION`，必须报告缺口及原因，不能写成严格数值 PASS。
- 对端到端延迟已有**可复现的测量或明确的未测说明**，且人眼确认无明显落后；队列不存在持续年龄增长。不能把较少肉眼闪烁视为同等于更低延迟。
- 失效后自动恢复，**无永久冻结/卡死、无 reboot、无 SSH 丢失**；内存稳定、无显著热失控；正常干净退出。
- 30min 的真实 `0xf` 频率不高于现有 RC1 同口径基线；若更高但体验更好，仍须出具原因与风险评估再决定是否接受。

### V2：仅在必要时 60min

- 如果 30min 存在偶发异常或人希望更充分确认，再延长至 60min；否则 **30min 足够**。
- 不设计默认 2h/8h soak，也不设置与实际目标无关的内核极限性能指标。

### 统一结果文件

建议交付：

```text
reports/low_latency/<run_id>/
  environment.txt
  git_and_binary_sha256.txt
  config_snapshot.yaml
  run_manifest.json
  events.csv
  metrics_1s.csv
  latency_quantiles.json
  freeze_and_recovery.csv
  kernel_errors.txt
  cpu_irq_thermal.csv
  user_visual_acceptance.md
  decision.md
```

如果实际项目已有报告机制，就复用现有格式，不要求为了满足文件名而重新构建一套日志系统。**日志保存在 Ubuntu PC 或 CM311 有限容量的临时路径**，大文件经 `scp/rsync` 受控同步，默认不向 USB 系统盘连续写入视频。

---

## 10. 当测试出现其他情况时的具体应对

| 异常 | 首先确认 | 应对措施 / 退出条件 |
|---|---|---|
| 画面 60 Hz 却仍滞后 | 是否重复旧帧、队列 oldest age、外部 glass-to-glass | 不再优化解码 throughput；定位接收前、VDEC 前或 KMS 前哪个排队 |
| 用户感觉延迟，但内部 AU→KMS 已很低 | DJI 编码/无线/摄像头显示固有延迟、外部高帧率测量是否正确 | 报告不可控下限；不凭 CPU 低就继续改内核 |
| 帧率 58–59、但无闪屏且体验正常 | 恢复时间造成的平均缺口 | 优先按体验验收；允许 `ACCEPTED_WITH_LIMITATION`，不人为补帧凑数字 |
| 新版 `0xf` 率上升 | 是否无意重开 async USB、队列/DRM 改动、buffer reuse | 立即回滚，确认 `VT13_ASYNC_USB=0`、比较同配置事件时间线 |
| 发现绿色/黑色闪屏 | KMS plane、primary 隐藏状态、CAPTURE 生命周期 | 立即终止候选并恢复 RC1；不将异常帧过滤视为已经修复 buffer 问题 |
| USB 接收延迟增加 | 线程等待、背压、丢 AU/POC、共享 xHCI 拓扑 | 保持同步 USB 路径，避免同步日志/磁盘写入；不要 blind drop HEVC P slices |
| `0xf` 不降但恢复时间改善 | 用户是否仍看得见冻结 | 优先完成体验 Gate；`0xf` 研究分离成驱动专项，不阻塞可用版本 |
| 30min 出现内存/温度上升 | C worker fd/DMABUF/FB leak、是否热降频 | 检查资源计数；若持续上升或影响画面立即停止并回滚 |
| 监测本身使 FPS 下降 | 每帧 log、trace 开销、同步写盘 | 采用抽样/环形缓存及低频聚合，关闭 instrumentation 重测 |
| KMS/HDMI/SSH 中断 | 是否独占 DRM 或系统资源竞争 | 按批准好的恢复命令回退；不擅自 reboot，联系有物理操作权限的人 |
| 发射端模式无法控成1832×1032 | 当前模式固定1080p | 明示该回归未做，不以未验证特性阻塞正常 1080p 测试 |

---

## 11. 人机协作、审批和部署边界

### 11.1 权限分级（以 `AGENTS.md` 为准）

- **R0**：Ubuntu PC/CM311 只读源码、日志、sysfs、Git 状态、历史数据；允许直接执行。
- **R1**：PC 的独立 branch、离线分析与非破坏性代码编写；可在隔离工作区执行，保留差分。
- **R2**：CM311 上占用真实 USB/V4L2/DRM/HDMI 的测试、变更测试程序、替换非关键 staging binary、长时间直播；**提前给出完整可复制命令、影响、停止及回滚方式，并得到人批准**。
- **R3**：`reboot`、驱动/内核/firmware 替换、USB unbind/reset、LightDM/默认 target、systemd kiosk 服务启用或其他可能导致板端 down/SSH 中断的系统级更改；每个操作单独申请明确批准。

**不要**在未批准情况下调用 `sudo systemctl start/stop/restart lightdm`、`reboot`、`modprobe/rmmod`、写 sysfs、启用服务、进行远端系统盘迁移；不要 `git clean -fdx`、`git reset --hard` 或覆盖 RC1。

### 11.2 实时无线测试的交接顺序

1. Worker 在 Ubuntu PC/SSH 中验证**当前 commit 的真实 CLI**，检查是否存在当前已运行的 V4L2、USB、DRM 占用者。
2. Worker 先输出 `【CM311】` **一段可复制粘贴的完整启动命令**（包含正确的 `config/vt13_video.kiosk.yaml`、环境变量 `VT13_ASYNC_USB=0`、日志目录和可控退出方式）。**不得按旧文档猜造模块名或 CLI 参数。**
3. Worker 提供完整 `【Ubuntu PC】` 日志收集和结果分析命令，标注 `scp/rsync` 传输方向和 SHA256 校验。板端命令遵守实际 bash/CLI 和可用工具；必要时生成 `scripts/run_low_latency_verified.sh` 并先离线验证。
4. 得到 R2 批准后，由人先启动接收程序、观察 `READY`，再**人工开启无线发射端**；不要让 Agent 自行模拟按键或改电源状态。
5. 人结束无线并按约定终止本轮程序；Worker 自动处理输出，生成 `PASS/FAIL/ACCEPTED_WITH_LIMITATION` 和证据路径。
6. 如需继续下一轮，同一批准不自动覆盖下一轮命令、时长或目标设备。

### 11.3 PC 与 CM311 分工

- **Ubuntu PC**：源码审计、日志/帧率/分位数计算、高帧率视频后处理、配置差分、版本控制、计划和结果报告。
- **CM311**：真实 V4L2/DRM/USB/HDMI、time monotonic 测量、少量运行期计数、经批准的短时/30min直播试验。
- 所有候选二进制最终必须在 **CM311 aarch64 + 当前 Armbian 运行时 ABI** 实际验证；PC 的编译/模拟表现不作为完成证明。
- PC→CM311 文件优先送 staging，不直接覆盖已部署二进制；经批准后切换，再验证回退。

### 11.4 K3 服务化是独立可选项目

本轮主要目标是画面效果，不自动启用 draft systemd unit。只有用户明确希望设备上电后自行进入 kiosk、且 RC1 延迟与稳定性 Gate 已通过，才启动 K3 实现与 R3 审批。

---

## 12. Worker 每阶段交付模板及停止规则

每个阶段必须交付：

```text
[阶段] L0 / L1 / L2 / R1 / L3 / V1 / V2
[执行主机] Ubuntu PC / CM311
[Git基线与候选] commit、diff、部署 binary sha256
[当前配置] yaml、VT13_ASYNC_USB=0、其他关键 flags
[事实] 实际执行的命令、退出码、证据路径
[指标] input AU/s, decoded unique/s, displayed unique/s, KMS flips/s
       glass-to-glass p50/p95（如已测）, internal latency p50/p95/p99
       oldest AU age, freezes, 0xf, POLLERR, sessions, TTFV
       CPU/thread/IRQ/iowait, memory, temperature
[对照] 同版本、同现场、相近时段和实验时长的 A/B/A
[通过门槛] PASS / FAIL / ACCEPTED_WITH_LIMITATION / NOT_TESTED
[问题与风险] 数据不足、硬件不可控因素、回退状态
[下一步] 最小可验证任务及预期效果
[需要人工参与] 完整可复制命令、风险级别、操作顺序、停止命令
```

**停止条件**：

- 未取得人批准，却需要操作真实无线、独占 DRM、替换运行程序或变更系统级设置。
- `0xf` 明显恶化、出现损坏帧/黑闪、USB 接收损坏、持续积压、失去 SSH、温度/内存趋势异常。
- 发现事实与交接总结冲突，先标记并核验而不是静默修改定义。
- 新方案延迟收益小于误差或降低可靠性，立即保留现有 RC1。

---

## 13. 第一轮交给 Codex 的任务（直接复制）

> 阅读仓库 `AGENTS.md` 和本计划 `CM311_DJI_C5_Low_Latency_60FPS_Optimization_Plan.md`。当前 RC1 基线是 `e56c5fe`，原生 V4L2/DMA-BUF/KMS 已达 30min 58.81fps，CPU 总体占用较低。项目最终只要求稳定 1080p60、无可见黑/绿/灰闪屏、尽可能无肉眼可见的实时延迟；正式 soak 只需 30min，必要时60min。
>
> **本轮只做 L0：** 核对 PC/CM311 工作树、Git、部署哈希、当前 kiosk YAML/真实入口；审计 Python USB→AU→C Worker→V4L2→KMS 的所有队列、计时点和资源所有权；解释如何准确衡量 unique displayed fps、glass-to-glass 和内部帧年龄；检查为何 `htop` CPU 低但可能仍有阻塞。输出最小侵入 instrumentation 的修改提案、可复制且经 CLI 校验的下一轮启动/退出/日志收集命令、风险及回退方案。
>
> **本轮禁止**：重启、装包、重载或修改驱动、恢复桌面、启用服务、覆盖 RC1、启动无线发射端或接管 DRM master。需要真实 live 实验必须先提交 R2 申请，等待人审批并由人按“先接收程序、后开启无线图传”执行。未经批准不要进入 L1。

---

## 14. 最终决策原则

最终成功不是“离线 271 fps 变成 300 fps”或“强行把统计器改成 60 fps”，而是：

1. **真正新的 1080p 帧**能跟上 60 Hz 且不持续落后；
2. **HDMI 无黑/绿/灰闪屏、无 plane 重建可见闪动**；
3. **端到端动作接近同步**，有度量、有可控/不可控延迟的区分；
4. **30 min 足够稳定**，有错误也能安全自动恢复，无手动 reboot；
5. **保持已证实的同步 USB 与原生 V4L2/DMA-BUF/KMS 架构**，新优化不能破坏现有 RC1。

达到用户主观体验与可靠性目标后，**停止高风险性能极限优化**，转入维护与可选服务化。
