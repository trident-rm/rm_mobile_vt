# CM311 / DJI C5 HEVC 硬解与实时图传：优先级执行计划

> **面向**：Ubuntu PC 上的 Codex / 工程 Agent，通过 SSH 管理 CM311；人在现场控制无线图传。  
> **基线日期**：2026-11-09（以用户提交的最新状态为准；实际环境仍须再核验）。  
> **性质**：可以执行的工程计划，不是已执行报告；任何预测 FPS、时延和成功率均为**阶段性目标**而非已验证的硬件能力。  
> **治理**：以仓库 `AGENTS.md` 中的安全、HUMAN APPROVAL、双机同步、人工无线实测规则为准；如与此计划矛盾，执行更严格的规则。  
> **总目标**：保留既有 USB/DUML/Python/显示资产，在 CM311 上实现 1920×1080 HEVC 实时解码、稳定显示、错误自动恢复；争取 1080p60，并在证据充分时恢复 No-copy 高吞吐路径。

## 0. 执行规则：先读完再做

1. **禁止一次性执行整份计划。** 每阶段设置 Gate（通过条件）。只完成已批准的当前阶段、出具报告，然后决定下一步。
2. **先从真实系统发现配置，严禁猜 CLI、SSH 地址、硬件状态和启动参数**。历史路径仅供线索：CM311 `~/mobile_vt`、`~/linux-6.18-vdec`、`~/ffmpeg-6.1.1-v4l2`；记录实际 Git diff、构建哈希、module vermagic、设备节点、显示技术栈和 release 入口。
3. **不复写基线**：保留用户提供的 release Copy-Out 配置：`stall_restart=2.0`、kernel watcher、显示过滤、`convert_bgr=false`。保护未提交改动、备份、原始采样及 run2/run4/run15。
4. **无线实测严格按时序**：先运行 CM311 接收程序并确认 READY/WAITING，再由人打开无线图传；不得反过来。真实启动命令必须在阅读当前 CLI、脚本及配置后生成；不能凭本文给出臆测的 CLI。
5. **高危操作必须每次单独审批**：reboot/shutdown，驱动加载/卸载，内核模块/DTB/boot 修改，影响 SSH/USB/HDMI 的服务变更，发射端重启/配对更改，停止已运行的 release 进程，大量覆盖/删除，以及占用 V4L2/USB/HDMI 的受控实测。展示完整命令、对象、潜在停机/失联影响、备份及回滚，等待明确授权。
6. **不要掩盖失败**：不把 `0xf` 当正常完成，不去掉有意义的 assertion，不强制清零引用计数，不使用尚未证实图片正确性的 padding 作为生产方案，不将软件缺失参考时的图像简单视为真值。
7. **主机分工**：Ubuntu PC 做分析、统计、软件解码/FrameMD5、复杂构建/模拟；CM311 只做必须依赖 ARM、V4L2、DMA、USB/HDMI 的验证。涉及 ARM 可执行文件必须确认架构、动态库、glibc、内核及模块 ABI，最终在 CM311 真机验收。
8. **证据和报告必须可回放**：每组测试有 `run_id`、代码版本、配置快照、操作时刻、原始日志、统计结果、退出码、磁盘路径和 SHA256。每个假设标注 `已验证 / 强关联 / 尚未证明 / 已排除`。

---

## 1. 最新已知事实与不能混淆的指标

### 1.1 真实 live 现状

| 项目 | 已知测量 | 解释/限制 |
|---|---:|---|
| 发射端 | 1920×1080，当前不可控 | 最终以每次 SPS 和实际 AU 到达速率判定是否为 60 fps |
| run15 | 195 帧 / 60 s | 约 **3.25 帧/s**；需核对这是 decode、filter 前还是实际呈现帧 |
| kernel abort | 33 次 / 60 s | 约 **0.55 次/s**，平均 **1.82 s/次**；独立 `0xf` 事件计数 |
| POLLERR | 1582 次 / 60 s | 属于同一故障后的重复报错可能很大，**不可当成 1582 次独立硬件失败** |
| 被过滤异常帧 | 全绿 23、半绿 13 | 与是否计入 195 帧的分母关系待核查；另有全灰/损坏过滤机制 |
| 请求 I-frame | 10/10 请求后 37–162 ms 出 IRAP | 这是**从命令到 IRAP 到达**的观测区间，非端到端显示延迟 |
| 重建恢复 | 中位数 116 ms | 必须核实 `recovery` 起点/终点定义；中位数不能代表最坏情况 |
| IDR 后解码 | 通常约 6–8 帧后 `0xf` | 需按请求与首个坏 AU/POC 严格时间关联，不能直接认定请求导致损坏 |
| 观感 | 出帧短暂、冻结、约 5 s 滞后感 | **主观描述**，尚未测量 camera-to-photon latency |

### 1.2 离线吞吐与实时需求

| 路径 | 离线吞吐 | 单帧平均处理时间的粗略倒数 | 现实限制 |
|---|---:|---:|---|
| No-copy | 221–249 FPS | 4.52–4.02 ms/frame | 硬件 fatal error 后当前应用无法可靠恢复 |
| Copy-Out | ~45 FPS | ~22.22 ms/frame | 能恢复，1080p60 情况下缺 15 frame/s 的能力 |
| 软件 HEVC | ~14 FPS | ~71.43 ms/frame | A53 CPU/USB backpressure，不可作为 1080p60 主路径 |

- **249 / 45 ≈ 5.53×**；按 249 FPS 对照，Copy-Out 路径每帧总耗时粗估多 **18.2 ms**。**这是路径总差值，不是 `memcpy()` 的实测成本**；可能还包含阻塞、缓存/DMA 同步、分配及输出队列。
- 1920×1080 NV12 可见像素大小 **3,110,400 B/帧**（Y 2,073,600 B + UV 1,036,800 B，实际 DMA stride/sizeimage 以运行时查询为准）；60 FPS 单向搬运约 **186.6 MB/s**，复制可能同时涉及读和写，更不能直接换算成 CPU 占用。
- 45 FPS 若面对持续 60 AU/s 且不丢弃旧 AU、队列无限增长，吞吐缺口是 **15 AU/s**（60s 为 900 AU）。实际是否积压须测 **解码前 AU 队列长度和年龄**，不能由这个理论差值直接判定 5 秒滞后根因。
- 当下 **优先问题是 0xf 发生率和 live 有效帧产出**；之后必须解决 1080p60 可持续吞吐。即使 249 FPS 也不能自动消除 `0xf` 或 RF 失真。

### 1.3 既往实验所支持的边界

- 1832×1032 历史 run4：90s 仅 1 次 `0xf`；1080p 的 run2 曾有 497/498 干净结果。**两者与 run15 的 RF、码流、请求频率和运行版本是否可比尚未确认**。
- 早期特定 POC50：POC35→50→55、缺参考 POC49/54。独立 GOP 仍报 `0xf`；在特定 NAL 边界插 512B 及以上零字节可让该图片的解码状态变为 `0x8`；但 SW vs HW **仅 36/38 帧相同**，差异集中在缺参考图片。**不能推出通用固件补丁，也不能宣称样本原本无缺帧。**
- Source Change：原 FFmpeg 6.1.1 曾等待旧 `AVBufferRef`；Copy-Out 能让 refcount 归零并跨 1832→1920，但曾丢一张旧分辨率图片。这与 `0xf` fatal error 是**不同的问题**。

---

## 2. 成功标准、统计口径和试验有效性

**所有下表门槛都是建议的阶段性工程 Gate；用户可调整后锁定。不可把它们说成当前已满足的产品规格。**

| 指标 | 统计定义 | 基线 | Gate / 目标 |
|---|---|---|---|
| `fatal_abort_rate` | 60s 内按唯一内核 abort 事件计数，辅以 `run_id` 和时间戳 | 33/60s（run15） | P0 阶段：同条件 3×60s，**每轮 0 次**作为进入高 FPS 集成的优先门槛；若做不到，先定量降低并解释剩余错误 |
| `recovery_success` | fatal 后、限定超时内回到**有效可显示帧**的次数 / 触发次数 | Copy-Out 可恢复 | 开发 Gate **≥95%（至少 20 次受控事件）**；最终稳定性目标需扩大样本 |
| `recover_ttfv` | 从唯一 abort 时间至下一张通过过滤且实际交付显示队列的帧 | 中位数 116ms（口径待核） | 目标 median ≤200ms、p95 ≤500ms；必须报告样本数与超时失败 |
| `input_au_rate` | 完整可解析 AU/s，分辨率、NAL type、POC 按事件统计 | 未统一 | 每次记录发射端真实速率，不能将 `25 fps` 探测行当作已知 live 60 FPS |
| `good_decode_ratio` | 正常返回且通过画面筛查的帧 / 解码器收到的有效完整 AU（加注 IDR/重排序例外） | 待重算 | 干净链路目标 ≥99%；对有缺失参考的流单独标记不能误称全成功 |
| `live_present_fps` | 实际送达呈现层的**新鲜不同帧**/s（并标注显示 API 是否能测到真正上屏） | run15 的 195 帧口径未知 | 若输入 60fps，稳定阶段目标 ≥55fps；输入不等于60时按有效 AU 归一化 |
| `freeze_events` | **有效输入仍在到达**但连续 >250ms 无新鲜可显示帧的一次事件 | 用户观察频繁 | 干净链路 60s 目标 0；如源本身不发帧，不能算作解码 freeze |
| `age_at_display_queue` | `display_enqueue_time - receiver_AU_complete_time`，**同一主机 monotonic clock** | 未测 | 先建立 p50/p95/p99，初期建议 p95 <150ms（调优目标非事实） |
| `capture_to_photon` | 真实摄像头曝光/事件到 HDMI 光学呈现（LED/高速摄影） | 约 5s 主观感受 | 独立测定，具体正式 SLA 待用户决定；不能拿 ffmpeg 的 `time=` 代替 |
| `offline_hw_fps` | 同一 HEVC 样本、同 null 输出、同设备温度/构建，多次测吞吐 | Copy 45 / No-copy 221–249 | 1080p60 的可行下限 >60；调优 Gate **≥90fps**（1.5×输入帧率），理想 ≥120 |
| `data_integrity` | 同文件 SHA256、AU 数、参数集、基线测试 FrameMD5/对齐 | 部分测试已做 | 无隐藏数据丢失；正常参考链样本 SW/HW FrameMD5 全匹配；异常样本标明 concealment，不要求与软件错误隐藏必然一致 |

试验设计要求：每组至少 **3 次 60 秒**（尽量 A/B/A 或随机交替），记录 RF 布局/距离/遮挡、发射端状态、请求配置、视频分辨率、代码版本与温度。正式评估至少长时 10–30 分钟；短时成功不等于生产可靠。若条件在测试期间改变（分辨率、无线强度、配置），分段报告，不能合并。

**重要统计口径**：
- 使用 `CLOCK_MONOTONIC` 或等价单机时间轴关联 USB/AU/decoder/display；`journalctl` 的 wall-clock 需与进程时钟校准；不能直接拿两台主机未同步的时间相减。
- 一个 fatal 事件可能引出数十次 `POLLERR`。分别计 `unique_abort`、`POLLERR_count`、`decoder_restart_attempts`、`restart_success`。
- POC 计数存在 IDR/IRAP 重置、LSB wrap、层/时序结构；不能把每一次 POC 跳号直接等同 USB 丢包。
- `RC=0`、`status=0x8` 或画面过滤通过，只能说明特定层完成；关键样本仍做 SW/HW FrameMD5 和人工可视检查。

---

## 3. 优先级总览与依赖关系

| 顺序 | 任务 | 风险 | 依赖 | 核心产出 | 决策 Gate |
|---|---|---|---|---|---|
| **P0-0** | 环境快照、数据/版本冻结、建立日志口径 | R0–R1 | 无 | baseline 包、run2/4/15 对齐表 | 能复现或解释所有计数 |
| **P0-1** | I-frame 自动请求 ON/OFF 对照 | R2（真实设备） | P0-0 | 3×60s A/B/A 报告 | 判断请求关联强弱 |
| **P0-2** | RF 位置、USB2 延长线、发射端状态对照 | R2；重启/配对可能 R3 | P0-0，尽量 P0-1 | 可控输入质量基线 | 是否存在接近 run2 的稳定流 |
| **P0-3** | USB→AU→POC→VDEC 证据链，定位 `0xf` 输入条件 | R0–R2 | P0-1/2 | 完整性时间线、最小复现 | 决定输入层/驱动层修复 |
| **P1-1** | Copy-Out 45 FPS 逐段性能剖析 | R1–R2 | P0-0 | 逐阶段耗时分布 | 选池化/同步/拷贝策略 |
| **P1-2** | No-copy 出错后会话/进程重建 PoC | R1–R2；内核级改动 R3 | P0-0 | 可恢复的 No-copy 验证分支 | EIO 后恢复，不留 fd/mmap 引用 |
| **P1-3** | GXL `0xf` 内核/firmware 边界诊断 | R1–R3 | P0-3 | 分类与最小复现；经批准的驱动候选补丁 | 不造假输出、不破坏状态 |
| **P1-4** | Source Change / EOF 帧生命周期回归 | R1–R2 | P1-1/2 | 旧格式末帧不丢、无引用死锁 | 与 `0xf` 分开验收 |
| **P2-1** | live AU 节流、队列时延及显示路径调优 | R1–R2 | P0; P1 可并行 | 有界缓冲与端到端时序 | 不再积累过期帧 |
| **P2-2** | DMA-BUF/DRM-KMS、buffer-pool 零拷贝可行性 | R1–R3 | P1-1/2 | 架构验证报告或 PoC | 无悬空内存/格式不兼容 |
| **P3** | 长时稳定、部署、回滚与 release 验收 | R2–R3 | 以上关键 Gate | 可回滚的 ARM 发布包 | 通过真实 CM311 目标条件 |

**并行安排**：P0-1/2 的人工时间之外，Codex 可在 PC 进行 P0-3 离线分析和 P1-1 源码插桩；**不得因 P1 优化延后 P0 的链路诊断**。所有合并前做同一 golden stream 回归。

---

## 4. 各阶段详细执行、结果解释与应对分支

### P0-0 环境快照与回归基线（优先开始）

**任务**：从 Ubuntu PC 经 SSH 对 CM311 做只读盘点；建立 `manifest`：hostname、`uname -a`、`uname -m`、`/etc/os-release`、`/dev/video*`、模块信息、FFmpeg `-version` 与解码器列表、Python/USB 工具入口、Git status+diff、`sha256sum`、实际运行进程/端口、内核日志范围。复制已知实验数据与日志到 PC 的独立分析目录。

**安全示例（Ubuntu PC 上执行，只有只读远端命令）**：

```bash
read -r -p 'CM311 SSH target (user@host or configured alias): ' CM311_SSH
ssh "$CM311_SSH" 'uname -a; uname -m; cat /etc/os-release | head -12; ls -l /dev/video* 2>/dev/null; command -v ffmpeg; command -v python3'
```

**Gate**：得到可信的版本/配置差异和基线数据位置；对重复 run15 计数来源给出定义。如果 run2/4 的原始数据不存在，明确标记「历史摘要，无法同条件复验」，不编造归一化比较。

**异常处理**：SSH 不通 → 停止，不调整网络；代码未 commit → `git diff` 和安全备份，不 `reset --hard`；CM311 磁盘不足 → 分析留在 PC，不写大文件到目标机。

### P0-1 requested I-frame 与 `0xf` 的因果性对照（最高实验优先级）

**唯一变量**：只改变验证过的配置 `iframe_on_recovery`（必须先从当前 CLI/源码确认真实选项名、语义和默认值）；其余发射端位置、USB 拓扑、显示和重启阈值保持一致。推荐 **A (ON) → B (OFF) → A (ON)**，每段 60s，必要时同样条件扩充 3 轮/组。记录每次人工无线启动时刻。

**采样**：`duML_request_ts`、`IRAP_detected_ts`（区分 IDR/CRA）、完整 AU 序号/大小/POC、`0xf` 唯一事件时刻、`POLLERR`、decoder restart、good frame、queue age、分辨率、RF 条件。

**判定**：
- OFF 的 abort rate 稳定下降 **≥80%**（例如从约 33 降至 ≤6/60s），且输入质量/分辨率相近 → **强支持请求策略参与故障**，但还需判断是大 IDR 突发、requested GOP 结构还是带宽占用；进入请求节流/退避验证。
- ON/OFF 差别 **<20%** 且数据完整性相近 → 请求不是主导因素，转 P0-2/P0-3。
- OFF 后 decoder 没有可用 IRAP 长期冻结 → **不能把缺少 abort 当成功**；必须同时报告有效帧/s 与可恢复性，短时结束试验并恢复原配置。
- 结果强烈随试验顺序/分辨率/RF 变化 → 视为混杂，重新以相同条件交错测试，不得下因果结论。

**可选策略（先在分支评估）**：token bucket / cooldown 限制请求频率；每次 fatal 最多请求一次、等待确认 IRAP、超时再指数退避；不能在尚未确认 IRAP 质量时无限请求。与当前 2s stall watchdog 的交互必须单独记录。

**人工交接**：Codex 先检验真实启动命令，交付两套**完整可复制**的 `[CM311]` 命令（ON/OFF），每套包含日志路径、运行超时、READY 判断、停止方法；人确认批准后先启动程序，再启动无线发射。实验结束自动拉日志、计算 A/B/A 指标。禁止 Agent 擅自打开/关闭发射端。

### P0-2 RF / 发射端链路隔离

**变量设计**：在**固定 I-frame 请求策略**与固定代码版本下改变**一个**物理条件：原布置 vs USB2 延长线使接收器远离 USB3/HDMI/主机 vs 开阔/不同方向。记录供电、线材型号、遮挡、干扰源、链路状态；1.5 m 干净历史样本不自动证明 0.5 m 一定更差。

**Gate**：恢复接近 run2 的干净 1080p 时，目标为 3×60s 唯一 `0xf=0`，同时验证输入 AU/POC 连续性与 good frame/s。若已出现明显改善但尚有 abort，保留原始轨迹及上下文，继续单变量对照。

**分支**：
- RF 改变后缺 AU、缺参考、`0xf` 同时显著下降 → 首先稳定链路，暂缓驱动大修改。
- AU 与 payload 完整，仍稳定复现 `0xf` → 优先 P1-3 firmware/driver。
- SPS 在 1832 与 1920 之间改变 → 分辨率作为协变量分层分析，不把分辨率效应误报成 RF 效应。
- 需要重启/重新 pairing/修改信道 → **先单独申请人工审批**，人操作发射端；测试前后保留 pairing/DUML 状态。

### P0-3 将 `0xf` 精确对应到输入完整性（离线优先）

**沿同一 `run_id` 建时间线**：USB 读取事件/状态、VT13 frame 头与序号（如有）、AU 原始字节与 checksum、NAL types、VPS/SPS/PPS、IRAP、POC（考虑 wrap/IRAP reset）、提交 V4L2 时的 bytesused 和 buffer index、内核中 `poc`/`idx`/`total`/`shift`、fatal/reopen 事件。

**优先区分四种情况**：
1. USB/VT13 序号断裂或损坏 → 采集/无线/拼帧层调查，不能靠 VDEC conceal 修复原图。
2. AU 完整但 HEVC RPS 缺引用 → 发射端跳帧/链接丢 AU/上游条件，测试 IRAP 与中断恢复；软件可 conceal 不代表原图无损。
3. AU 和参考链完整，在可重放样本固定 NAL/LCU 报错 → GXL firmware/driver 候选，构建最小安全复现。
4. 只在高 bitrate IDR 突发、BUF backlog 下发生 → 检查 USB read、parser 提交节奏、OUTPUT/CAPTURE 供应量与背压；不要直接认定 RF 故障。

**禁止**：把 `0xf` 机械改成 `0x8`，把任意 P 帧强制当 IDR，未经像素正确性测试自动全局 padding。先做 PC 软件帧解析/校验和历史样本对齐，再审批设备实验。

### P1-1 Copy-Out 性能剖析（目标：说明 249→45 的真实去向）

**在目标 ARM 的测试分支上**给以下环节做轻量级单调时钟计时，记录 per-frame p50/p95/p99：
- `VIDIOC_DQBUF` 等待与 active 时间（区分等待硬件与用户代码）；
- `av_frame_get_buffer` 分配/复用；
- `av_frame_copy`（单独 Y/UV plane），及 `av_frame_copy_props`；
- `av_frame_unref` 的 CAPTURE 释放、重新 `QBUF` 与 refcount；
- 转换/像素格式、Python IPC、显示队列、滤镜和窗口渲染；
- CPU 总/逐核使用、频率、温度、内存水位、VDEC interrupts。

**对照矩阵**：同一干净固定 HEVC 样本，No-copy vs Copy-Out；分别做纯 null sink 与完整显示栈；无需无线发射，消除 RF 变量。用 `perf` 等工具前确认目标内核支持；不要编造性能计数。对不同构建保证相同驱动版本和输出设置。

**Gate**：能将约 18ms/frame 总差值划分到可解释的阶段（计时覆盖率 ≥90%，或明确记录未覆盖项）。再决定：
- `get_buffer` 显著 → 预分配/AVBufferPool，测内存与正确性；
- `copy` 显著 → 分析 mmap/cache/sync/stride，测试 plane 优化或 DMA-BUF；不得随意改缓存属性；
- `DQBUF`/`QBUF`/队列显著 → 排查 CAPTURE 缓冲不足、锁/引用保持、背压；
- 主要耗时在格式转换/显示 → 避免不必要 BGR 转换，但不得牺牲现有滤镜与画质；
- null 输出 ≥90、live <60 → 重点在 IPC/显示/输入队列，而不是 VDEC 算力。

**优化 Gate**：先 ≥60 稳定且无积压；建议 ≥90 offline fps（保留 50% 余量），理想 ≥120。每一次优化必须通过正常参考链 FrameMD5、异常/Source Change/EOF 及 EIO 恢复回归。

### P1-2 可恢复 No-copy：最优先的长期架构验证

**核心原则**：不让错误后的旧 AVFrame/MMAP 引用阻塞设备重建；`0xf` 和 V4L2 fatal EIO 发生后，正确释放旧会话。优先进行离线可复现测试。

**候选 1：同进程显式关闭与 reopen**：停止输入新 AU，停止输出队列、释放上层 AVFrame/引用，完成 `STREAMOFF`、buffer release、fd close，再 open、新建 OUTPUT/CAPTURE、等待新 IRAP；记录每一步耗时和 EIO。是否可行以本机 driver/FFmpeg 实测为准。

**候选 2：独立 decoder worker 进程**：USB/DUML/显示主进程持续运行；只重建 decoder worker。**不能把 worker 的 MMAP 指针交给独立显示进程然后关闭 worker**，必须经由有明确所有权与同步的 IPC copy 或 DMA-BUF 导入；零拷贝优势可能在进程边界消失，必须全路径测量。先验证 worker 崩溃不会留下占用 `/dev/video0` 的 fd 或不可靠 kernel 状态。

**对照**：No-copy decoder + null sink + fatal 注入（优先历史损坏 HEVC 文件）；随后同一解码器连续重建至少 20 次，每次以可解 IRAP 恢复，统计 restart 成功率、time-to-first-valid、fd/mmap 数量、VDEC 空间/错误。经批准再 live 测。

**Gate**：达到 ≥95% 的受控重建成功率、没有增长的 fd/mmap/内存泄漏、没有 SSH 受损；恢复后正常片段 FrameMD5 匹配，性能 ≥90 FPS（理想保留 120–200+），然后集成显示队列。若 worker exit 仍留 kernel dead state，应停止该候选，进入 P1-3 而非反复重载模块。

**标准依据**：Linux V4L2 stateful decoder 对 fatal error 允许 close/reopen 或停止双队列释放缓冲重建实例；Source Change 则有独立的 LAST/drain/重启时序。参见：https://docs.kernel.org/userspace-api/media/v4l/dev-decoder.html 。实际局部 driver 行为必须测。

### P1-3 GXL firmware `0xf` 驱动级分类与修复

**不要直接提交补丁**。先用 P0-3 的可复现文件分型：GOP 尾端、POC 缺失、短 VCL、分辨率变化、高码率突发。记录 `HEVC_LCU_CHECK` (`status`, `poc`, `idx`, `total`, `over`, `shift`) 与原始 AU bytesused；以发生前最后一个正常 VCL 为参照。

**核查项**：ES parser 送入长度/对齐/跨帧读取位置、input ring/fifo 预读、当前图片完整完成的时序、CAPTURE/OUTPUT buffer 生命周期、DPB 已存在参考帧、是否错误回退到当前帧自引用、可用缓冲量、firmware 版本与 CPU/GXL 型号。

**主要分支**：
- 只在 input 截断发生：需要 upstream AU 验证、丢弃不可修复 AU、请求新 IRAP；不允许把补零后的 `status=0x8` 当正确图片。
- 在完整参考链 + SW 可严格解码的固定样本发生：可设计最小 driver patch；在 Ubuntu PC 审查/构建，CM311 经 **R3 审批**部署，对照 FrameMD5 和 `0xf`。
- 如果 firmware 内部错误不可修复：降风险使用恢复策略与输入约束（例如稳定 RF，若确有可控模式则选择 1832），不要无限追求 `0xf` 后继续在坏 DPB 解码。
- 如果驱动状态无法通过实例重建恢复：收集故障 dump 与安全回退方案再考虑模块替换/重载，**不允许未经批准做 reboot**。

### P1-4 Source Change 与 EOF 独立回归

- 遵循 V4L2 Source Change 事件 → 旧 CAPTURE 队列 drain 到 `V4L2_BUF_FLAG_LAST` → 正确释放旧引用 → CAPTURE format/queue 重建 → 恢复流程；需要结合**实际驱动**的事件时序，不要仅靠同步等 refcount。官方状态机见上述 V4L2 文档。
- 历史混合分辨率 66 AU：SW 66 vs HW 65，SW index43 丢失、最后图片异常；先离线定位最后一张旧分辨率帧与 EOF cur_frame 的时间点。
- Gate：正常固定流 / 源变更 / EOF / 重连全部没有永久引用等待；完整参考链样本帧数和 FrameMD5 一致。`0xf` 的回归单列，不能混算。

### P2-1 真正低延迟：限制**解码之前**的积压

- `AU_queue` 有界（初始候选 2–4 AU，不是确定最优值），监控 queue depth、oldest age、bytes/seconds；显示侧现有 drop-oldest 继续保留。
- **不能任意丢一个 P 帧并继续让 decoder 以为参考链完整**。当 backlog 超过上限，标记丢失参考，进入 `WAIT_IRAP`，可触发经过节流的请求；对画面连续性与延迟做 trade-off 报告。
- 对所有关键阶段加单机 monotonic 时间戳：USB receive、AU complete、decoder submit、CAPTURE DQBUF、filter、display enqueue、display presented（如 API 可观测）。要明确 CPU/内核跨时钟误差。
- Gate：在干净 1080p60 输入下，输入 AU age 不持续上升，队列不无限增长，正常显示无 >250ms freeze；有错误时按照受控恢复策略清空陈旧数据。
- **物理端到端延迟**必须另外做摄像头→显示同屏计时；不能把 queue age 替代完整 camera-to-photon。

### P2-2 零拷贝显示与 DMA-BUF（最后才做）

- 只读探测 V4L2 `EXPBUF` / DRM/KMS 支持、NV12M 多平面、stride、modifier、同步与生命周期；不要假设 ffplay 支持 DMA-BUF 直通。
- 如果驱动/显示可共享 buffer：开发 PoC，验证释放与重建不使画面引用悬空；对照 Copy-Out / No-copy CPU、fps、latency。
- 如果 DMA-BUF 不可用或跨 worker 拷贝仍然昂贵：优先保留可恢复的 Copy-Out/缓冲池，或同进程 display/decoder 明确帧 ownership；不为理论零拷贝破坏当前稳定架构。

### P3 部署与长期验收

1. 代码走独立分支，Ubuntu PC 先 lint/静态审查/软件解码/PC 统计；目标 ARM 二进制做架构/依赖检查，实际发行在 CM311 真机测。
2. 同一帧集回归：正常 1832、正常 1080、动态分辨率、已知 POC50、GOP 边界、EOF、USB/无线重连、EIO 后重建。记录 per-run SHA256/FrameMD5 和错误类型。
3. 先 3×60s，达标后连续 10–30min，再由人决定更长 soak。指标至少包括唯一 `0xf`、good fps、freeze、recovery p95、CPU/温度/内存、fd、AU 队列年龄与显示窗口连续性。
4. 发布时保留 working release、日志与回滚目录；不直接覆盖原可运行二进制。涉及系统文件/模块/服务操作按 R3 单次审批。提供人工可执行的回退与现场恢复说明。

---

## 5. 统一决策树：出现异常时怎样调整

| 观测 | 解释优先级 | 下一步，不要做什么 |
|---|---|---|
| `iframe_on_recovery=OFF` 后 `0xf` 下降 ≥80%，有效显示也改善 | 请求时机/突发可能是诱因 | 先做冷却/单次请求/超时退避；不要无条件停止所有恢复请求 |
| OFF 后 `0xf` 少，但彻底无画面 | 失去恢复条件而非问题解决 | 恢复安全基线；请求 IDR 的必要性仍在 |
| RF 布置变化后 `0xf` 和 POC 缺口一起下降 | 输入质量问题优先 | 稳定收发环境与供电、分析 USB/VT13；不要先修改 VDEC 内核 |
| RF 改变不影响，固定完整 HEVC 样本每次同一 LCU 失败 | firmware/driver 边界问题更可能 | 构造最小可复现、对照 SW 严格解码、研究 ring/DPB；不把 padding 直接上产线 |
| No-copy offline 快、EIO 之后不能再次出图 | 会话资源/引用/驱动 fatal state | 优先 close/reopen 或 worker 进程隔离；不强行更改 refcount 数值 |
| Worker 重启后依然 `POLLERR`、内核设备不可用 | 可能 kernel session 清理不完整 | 收集 fd/ioctl/kernel 日志，停止重启风暴，需 R3 审批才改驱动 |
| Copy-Out 分配耗时主导 | per-frame allocation | pool/复用，统计 correctness 与内存；不要只优化 `memcpy` |
| Copy-Out 复制耗时主导 | DMA mmap/CPU cache/stride | 分 plane/profile、检查同步、测试导出路径；勿随意改 cacheability |
| Null sink ≥90 FPS、live <60 FPS | 显示/IPC/输入阻塞 | 分解各层队列和耗时；勿把显示问题错判成 VDEC 算力 |
| 1080p60 只有 ~45 decode FPS，AU 队列持续增长 | 前端吞吐不足 | 有界队列 + 在下一个 IRAP 重同步，同时并行提升 Copy-Out/No-copy |
| Hardware RC=0，SW/HW FrameMD5 不一致且有缺参考 | concealment 差异、图片质量风险 | 标记不可直接等价，生成可视对比和参考链报告 |
| `status=0xf` 触发频率下降但 freeze 不降 | 可能有输入堵塞/队列/显示时间轴问题 | 排查 AU age、render timestamps、worker state，而不再仅统计 `0xf` |
| 图传未开时 0 packets | 预期行为 | 不判为接收器故障；必须先 READY 再人工开图传 |

---

## 6. PC↔CM311 数据/构建/日志同步规范

**原则**：PC 保存分析仓库与历史快照，CM311 保存部署版本与短时现场日志；两者的代码版本和数据哈希始终可追踪。

```bash
# Ubuntu PC：示例，只读取远端数据。先确认实际路径与大小。
read -r -p 'CM311 SSH target: ' CM311_SSH
read -r -p 'CM311 remote run directory (absolute path): ' REMOTE_RUN_DIR
mkdir -p "$HOME/cm311_hevc_analysis/imports"
# 先显示会同步什么，不删除、不覆盖当前 release
rsync -avhn -- "$CM311_SSH:$REMOTE_RUN_DIR/" "$HOME/cm311_hevc_analysis/imports/"
# 核对预览与数据量后，才执行以下非破坏性下载（新目录、只新增）
# rsync -avh --ignore-existing -- "$CM311_SSH:$REMOTE_RUN_DIR/" "$HOME/cm311_hevc_analysis/imports/"
```

重要约束：未核实 `rsync` 是否在两台机器安装前，不假设它可用；可退回 `scp`，但仍需检查文件大小与 SHA256。部署使用独立 staging 路径、`rsync --dry-run`、比较哈希，**禁止默认 `--delete` / 覆盖系统模块**。PC 构建的动态库架构、依赖、目标 `glibc` 和 kernel vermagic 必须与 CM311 对齐。

---

## 7. 每一轮 Codex 应交付的产物

建议目录（在 PC 新建独立工作目录，不覆盖项目）：

```text
cm311_hevc_analysis/
  inventory/                  # SSH/版本/修改快照
  baseline/                   # run2 run4 run15 原始日志、SHA256
  experiments/<run_id>/
    manifest.json             # 两机、代码、启动配置、无线手动事件时刻
    raw/                      # 原始日志和 HEVC/VT13 摘要或按容量许可的样本
    metrics.json              # 可机读计数与时间分位数
    events.csv                # AU/POC/IRAP/0xf/restart/display 事件时间线
    report.md                 # 假设、结果、结论置信度、异常分支
  benchmarks/                 # Copy-Out/No-copy profile 表
  patches/                    # 每个补丁独立 diff、回归与回滚
  release_candidates/         # 打包、hash、兼容性与 CM311 验收日志
```

**报告固定结构**：当前阶段/状态；测试前提和人是否批准；实际执行命令及在哪台主机；样本、输入帧率与分辨率；代码版本和环境；指标（分母明确，包含 p50/p95/样本数）；异常日志；结论（事实 vs 推断）；是否通过 Gate；失败后下一可选路线；影响系统的行为与回滚状态。**绝不能将未完成的实验写为已经成功**。

## 8. 下一轮给 Codex 的明确起始任务（只读）

> 阅读本计划和仓库根目录的 `AGENTS.md`，先在 Ubuntu PC 与 CM311 做只读盘点，建立 manifest、确认最新 release 和历史 run2/run4/run15 的日志及配置，核对所有指标分母。比较当前 `iframe_on_recovery` 的真实 CLI/配置，设计 A/B/A 60 秒对照并**生成准确、可复制的人工操作命令**，但暂不运行真实无线实验、不改配置、不停止进程。把需要人批准的实验包、风险、预期指标、回滚和数据存储路径列出供我确认。离线数据分析可先做，涉及远端写入、占用 USB/V4L2、驱动重载和 reboot 一律遵守人工审批。

---

### 参考（用于设计判据；现场代码才是实际版本真相）

- Linux V4L2 stateful decoder 的 fatal `-EIO`、close/reopen 与完整队列重初始化说明：<https://docs.kernel.org/userspace-api/media/v4l/dev-decoder.html>
- FFmpeg V4L2 M2M CAPTURE 重建存在旧 `AVBufferRef` 等待逻辑（网页可能对应不同 FFmpeg 版本，以 CM311 已安装 6.1.1 源码为准）：<https://www.ffmpeg.org/doxygen/trunk/v4l2__m2m_8c_source.html>
