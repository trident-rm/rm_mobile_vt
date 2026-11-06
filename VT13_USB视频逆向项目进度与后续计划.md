# VT13 USB 视频流逆向与 Linux 实时解码

**项目状态与下一步实施文档**  
**版本：** v1.2  |  **更新日期：** 2026-10-31  |  **研究对象：** RoboMaster VT03（发送端）/ VT13（接收端）

> **当前一句话结论：** 已完成 VT13 实机持续 HEVC 解码验证：`live_run09` 在 `read_size=2048` 下运行 **145.968 s**，解码 **5,537 帧、60.59 FPS、1920 × 1080**，解码错误/损坏帧/丢帧均为 **0**；VT03 断链期间的 USB 错误由 `clear_halt` 恢复，重连后无 USB 错误。当前边界是 VT13 不周期性输出 IRAP，链路丢失后需要重连 VT03 才能获得新的可解码起点。

## 1. 项目目的和范围

### 1.1 最终目标

绕过 Windows RoboMaster Client，直接使用 Ubuntu / Linux 从 VT13 的 USB-C 接口接收 VT03 的无线视频，并实现可供视觉算法调用的实时图像：

`VT03 相机 → VT03 无线图传 → VT13 接收端 → USB → libusb/PyUSB → HEVC 解码（FFmpeg/PyAV）→ OpenCV BGR 帧`

目标交付物为可运行、可复现的 Linux 接收程序，支持实时预览和获取 `numpy.ndarray` 图像帧，具备基础断流检测、恢复与状态统计能力。不依赖 RoboMaster Client，不需要重建完整的遥控器控制协议。

### 1.2 当前研究边界

- **主要范围：** VT13 USB 通道定位、HEVC 视频载荷确认、视频解码器初始化、USB 采集连续性、OpenCV 输出。
- **辅助范围：** `0x82` 结构化消息解析，仅用于判断无线链路状态、启动时机及潜在视频控制信息。
- **暂不作为主线：** 遥控器按键/摇杆协议、完整 DJI 私有消息 ID 语义、其他 RoboMaster 产品的 UDP/RNDIS 视频方案。
- **约束：** 不随意向未知 Bulk OUT 或 EP0 发送未经验证的 DJI 私有命令；优先采用只读抓包和被动分析。

## 2. 已确认的硬件和 USB 拓扑

**USB 设备：** DJI Technology Co., Ltd. C5，`VID:PID = 2ca3:1020`，USB 2.0（480 Mb/s）。在 Ubuntu 未暴露标准 UVC `/dev/video0` 或 USB 网络接口。

| USB 接口 | 描述符名称/功能 | 发送方向（Host→设备） | 接收方向（设备→Host） | 当前用途判断 |
|---|---|---|---|---|
| Interface 0 | Vendor-specific，MA Channel | Bulk OUT `0x01` | **Bulk IN `0x81`** | **已确认承载 HEVC 视频** |
| Interface 1 | Vendor-specific，HS/SS-Data Channel | Bulk OUT `0x02` | Bulk IN `0x82` | 高速结构化消息；与无线状态相关 |
| Interface 2/3 | CDC ACM / DATA | Bulk OUT `0x03` | Bulk IN `0x83`；通知 `0x84` | `/dev/ttyACM0`，少量数据 |
| Interface 4/5 | CDC ACM / DATA | Bulk OUT `0x04` | Bulk IN `0x85`；通知 `0x86` | `/dev/ttyACM1`，目前读到 0 B |
| EP0 | 标准 USB Control | Control 请求 | Control 响应 | 设备枚举；未知是否参与视频启动 |

**注意：** “Interface 0 为视频”已得到实际 HEVC 码流支持；各 OUT 端点是否负责视频启动仍未确认。

## 3. 关键实验结果与证据等级

### 3.1 视频流定位：已验证

- `captures/linked/bulk_if0_ep81.bin`：**10,929,652 B**；检测到 **508 个 HEVC AUD（NAL type 35）**。
- 典型 NAL 结构：`AUD(35) → PREFIX_SEI(39) → TRAIL_R(1) → SUFFIX_SEI(40) → SUFFIX_SEI(40)`；508 个 AUD 组中有 **504 组**符合这一序列。
- `0x81` 在 linked 状态的稳定读取速率约 **1,250–1,265 KiB/s**；用约 21.6 KB/Access Unit 推算，**约 60 FPS（估算值）**。采集头部存在积压数据且后期发生中断，不以总 AUD / 采集命令时长计算帧率。
- HEVC NAL 头（如 `46 01`、`4e 01`、`02 01`、`50 01`）和长时间稳定的合法排列，足以将 `0x81` 判定为视频主通道。

### 3.2 离线解码：已验证

最新 `captures/cold_start/bulk_if0_ep81.bin`（**2,431,249 B**）的 `hevc_audit.py` 结果：

| HEVC NAL type | 名称 | 数量 |
|---|---|---:|
| 32 | VPS | **3** |
| 33 | SPS | **3** |
| 34 | PPS | **3** |
| 20 | IDR_N_LP | **3** |
| 1 | TRAIL_R | 118 |
| 35 | AUD | 118 |
| 39 | PREFIX_SEI | 121 |
| 40 | SUFFIX_SEI | 239 |

- `ffmpeg` 成功生成 `/tmp/vt13_frame.png`，系统报告为 **1832 × 1032、RGB PNG**。
- 使用 `live_view.py --file ... --headless`，**PyAV 离线解码出 105 帧、0 个 Python 层的解析/解码异常**；输出 `vt13_pyav.png` 为 **1832 × 1032**。
- 冷启动 105 帧作为离线解码回归样本保留；其实时图像质量由 §3.3 的 `live_run09` 全帧联系表和全分辨率抽帧验证，不再用该离线文件单独证明实时画质。

### 3.3 实时解码：已验证

`live_run09` 使用模块化接收程序 `python -m vt13_video stream`，在 `read_size=2048` 下运行 **145.968 s**：

- USB `0x81` 共读取 **158,633,034 B（151.28 MiB）**、82,184 次；解码 **5,537 帧**，**60.59 FPS**，稳定输出 **1920 × 1080**。
- **0 个解码错误、0 个损坏帧、0 个丢帧**；首帧为 **1832 × 1032**，后续达到 **1920 × 1080**。
- 为验证断链恢复，先断开 VT03 再重连：断链阶段累计 **43 次 USB 错误/恢复**，全部发生在首帧之前；43 次 `clear_halt` 均成功，首帧出现于 **51.366 s**。重连后到会话结束**无 USB 错误**。
- 离线重放 `live_runs/live_run09.bin` 得到完全一致的 **5,537 帧、0 个解码错误、0 次解码器重置、0 个损坏帧**。联系表覆盖全部帧，画面稳定且无可见花屏；全分辨率第 3000 帧同样干净。
- 标准 USB reset（`live_run07`）**不会**重启 VT03 视频流或产生新 IRAP；链路丢失后需要重连 VT03。整个验证未发送 vendor-specific OUT/control 命令。

补充回归 `live_run10`（**130.641 s**）：首帧在 **0.083 s** 保存；**9.832–21.386 s** 发生 **47 次 USB stall**，47 次 `clear_halt` 均成功并在原 handle 原地恢复，之后**无 USB 错误**；共输出 **6,342 个干净帧、60.6 FPS、1920×1080**。**407 个 corrupt frame 默认抑制**；离线重放得到 **6,342 帧、409 个 corrupt、0 个解码错误**，corrupt 连续集中在 **Access Unit 4–412**，之后 **6,340 帧连续干净**；全分辨率第 6000 帧抽检清晰。另记录到 2 次 read gap（**14.701 s、2.515 s**），与断链阶段一致。

补充回归 `live_run11`（**第二次 VT03 上电后才出图**）：USB 在启动后立即有数据，但在首帧前累计读取 **7.78 MiB、0 帧**；约 **23.4 s** 才看到 IRAP，但此时 VPS/SPS/PPS 仍缺失，约 **27.9 s** 参数集到达，**28.0 s** 保存首帧。实时会话最终 **970 帧、155 次 USB 错误/恢复、161 次 discontinuity、3 次 keyframe start**；离线重放同一录像得到 **974 帧、0 个解码错误、0 次解码器重置**。这证明 **USB 有数据流不等于视频链路可解码**；判断就绪必须同时满足参数集完整、当前 epoch 看到 IRAP、解码器已从 IRAP 启动。保存的参数集文件为 **102 B**，包含完整的 VPS/SPS/PPS。

参数集字节**不是每次上电随机变化**：`run09/run10/run11` 中观察到两个稳定的 VPS/SPS 变体，分别对应 **1832×1032** 与 **1920×1080**，PPS 字节相同；`run11` 会在两个变体之间切换，当前保存文件保留最后一组（本次为 1920×1080）。因此预保存一组参数可能只匹配一种分辨率；需要两种都预存时应分别采集/保存。

**结论：** “USB Bulk IN → Annex-B → HEVC → 实时 BGR 帧”链路已在实机持续运行中验证；当前关键限制不是初始解码起点，而是无周期性 IRAP 以及链路丢失后的重连边界。接收端只能**观测并等待** IRAP，已验证范围内没有可主动请求 IRAP 的接收端命令；标准 USB reset 也不能替代 VT03 重连/上电。

### 3.4 USB 连续性：2 KiB 读长显著改善，根因仍未确认

30 秒读长探针结果：

| `read_size` | 探针数 | USB 错误 | 超时 |
|---|---:|---:|---:|
| 512 B | 1 | 2 | — |
| 1 KiB | 2 | 0 / 2 | — |
| 2 KiB | 1 | 2 | — |
| 4 KiB | 2 | 19 / 29 | 12 |
| 16 KiB | 1 | 38 | 12 |

- 已将 `read.read_size` 默认值设为 **2048 B**。`live_run09` 在重连后使用该读长持续运行且无 USB 错误。
- 4 KiB 及以上读长与频繁 EIO 相关；2 KiB 是经实测验证的传输层缓解措施，但 **EIO 根因仍未确认**，不能表述为已修复硬件或驱动问题。
- `live_run09` 的 43 次错误均发生在故意断开 VT03 的阶段，说明 `clear_halt` 能恢复 halted Bulk IN；重连后错误计数不再增长。
- 成功的 `io` 错误 halt clear 会保留 parser、AU assembler 和 decoder 状态并继续使用现有 USB handle；成功的 `pipe`/`stall` halt clear 虽继续使用现有 handle，但会标记 discontinuity 并重置解析/解码状态，等待新的 IRAP。
- 打开 USB 后读取的前 `read.drain_reads` 个 chunk 不再丢弃，而是送入 parser；避免重连后首批 VPS/SPS/PPS 或 IRAP 被预读丢弃。
- `device.status_drain` 会只读排空 `0x82`，当前默认启用，但仍是**实验性、可选**功能；现有证据没有证明它是视频稳定所必需。
- 标准 USB 设备 reset 不能替代 VT03 重连：`live_run07` 中 reset 后视频流没有重启，也没有产生新 IRAP。

### 3.5 `0x82` 结构化通道：作为背景保留

- 早期上传 `vt13_idle.bin`（**4,176,038 B**）可分成 **58,134** 个 `F5/F6/F7/F8 + 0x64` 候选消息，完整覆盖字节流；通常为小尺寸结构化消息（最大 96 B）。
- 断链阶段 `0x82` 约 **810 KiB/s**，linked 时约 **1,718 KiB/s**；变化与无线状态有关，但这不证明其包含视频主码流。
- 目前不继续深入每个消息 ID 的意义；仅在排查视频启动指令、状态同步或参数集来源时使用。

## 4. 现有工具与数据清单

### 4.1 Ubuntu 本机已经运行过的脚本

| 脚本（本机名称） | 作用 | 已验证的用途 |
|---|---|---|
| `test.py` | USB 描述符/端点验证 | 发现 6 个接口及各 Endpoint |
| `capture.py` | 单端点原始采集 | 获得最初的 `vt13_idle.bin` |
| `ana_struct.py` | `0x82` 消息结构统计 | 验证 F5/F6/F8 头长度及 C451 特殊布局 |
| `usb_video_lab.py` | 多通道 capture / analyze / compare / extract | 生成各通道 `.bin` 和 `.times.tsv`，对比 idle/linked |
| `hevc_audit.py` | HEVC Annex-B/NAL 类型扫描 | 识别 VPS/SPS/PPS、IDR、AUD 和切片 |
| `live_view.py` | 旧版 PyUSB → PyAV → OpenCV，离线/实时模式 | 离线解出 105 帧；旧实时失败录像保留作回归对照，当前实时链路由 `vt13_video` 验证 |

### 4.2 已提供的辅助工具（按实际文件名同步至工作目录后使用）

| 文件名 | 用途 | 状态 |
|---|---|---|
| `vt13_hevc_timeline.py` | 将 NAL 的字节偏移映射到 USB 读取时间，按断点切段 | 作为诊断工具提供 |
| `vt13_extract_idr.py` | 提取含 VPS/SPS/PPS + IDR 的独立候选解码片段 | 作为提取工具提供 |
| `vt13_ep81_recover_capture.py` | `0x81` 只读采集、USB 失败日志和重开尝试 | 未完成 VT13 实机稳定性验证 |
| `vt13_live_diagnostic.py` | 实时统计 NAL、记录断点、只在具备参数集与 IRAP 时启动解码 | 已提供，尚无用户实际运行结果 |
| `vt13_analyzer_v2.py` | 完整 F5/F6/F7/F8 结构化消息分帧 | 在最初 `vt13_idle.bin` 上测试 |

**软件依赖：** Python 3 / Conda `(rm)`，`pyusb`、`pyserial`、`av`（PyAV）、`opencv-python`，系统 `libusb-1.0`、`ffmpeg/ffprobe`；可选 `usbmon`/Wireshark/USBPcap 用于协议抓包。

### 4.3 关键原始数据（路径均为用户 Ubuntu 本地路径）

| 文件/目录 | 用途/特征 |
|---|---|
| `vt13_idle.bin` | 初期约 4.18 MB 的 `0x82` 断链数据 |
| `captures/idle/` | 多端点断链基线；`0x81` 仅短暂输出约 459 KB |
| `captures/linked/` | 无线连接采集；`0x81` 约 10.93 MB，508 AUD，但无 VPS/SPS/PPS |
| `captures/cold_start/bulk_if0_ep81.bin` | **核心金样本**；约 2.43 MB，包含 3 组 VPS/SPS/PPS 和 IDR，PyAV 成功解码 |
| `live_runs/live_run09.bin` | **当前实时金样本**；158,633,034 B，145.968 s，5,537 帧，0 解码错误/损坏帧/丢帧 |
| `live_runs/live_run09.{times,events}.tsv` | 实时读取与 USB 事件旁文件，可与 `dmesg -T` 对齐 |
| `live_runs/live_run10.bin` | **断链恢复回归样本**；130.6 s，6,342 个干净帧；407 个 corrupt 集中于早期，47 次 USB stall 均原地恢复 |
| `/tmp/vt13_live_first.png`、`/tmp/vt13_live10_frame6000.png` | `live_run10` 首帧与全分辨率后期抽帧；均为有效画面 |
| `/tmp/vt13_live09.json`、`/tmp/vt13_live09.log` | `live_run09` 的 JSON 统计与终端日志 |
| `/tmp/vt13_live09_replay.json`、`/tmp/vt13_live09_replay.log` | 同一录像的离线重放统计与日志；5,537 帧、0 错误、0 重置 |
| `/tmp/vt13_live09_contact.jpg`、`/tmp/vt13_live09_frames/frame_3000.jpg` | 全帧联系表与全分辨率抽帧；已目视确认画面稳定、无花屏 |
| `live_runs/live_run05.bin` | **损坏帧回归样本**；用于验证 PyAV 产生 corrupt frame 时默认抑制输出 |
| `captures/vt13_live_raw.h265` | **历史实时失败对照**；约 22.90 MB，无 VPS/SPS/PPS/IRAP，旧工具解码 0 帧 |
| `*.times.tsv` | 将每次 USB 读取的时间和长度映射至文件偏移，用于断流定位 |
| `/tmp/vt13_frame.png`、`vt13_frames/vt13_pyav.png` | 冷启动金样本的 1832×1032 图像文件 |

**数据管理注意：** 多次使用同一输出路径会覆盖同名文件；今后每次实验使用唯一目录（例如 `live_runs/20261031_live_run10/`），同时保存命令、状态、`*.times.tsv`、诊断日志和原始二进制文件。录制前确认目标目录可写；`captures/` 在早期实验中曾由 root 创建，普通用户不能直接写入，当前示例统一使用 `live_runs/`。

## 5. 当前技术难点与下一步优先级

| 优先级 | 工作项 | 实施内容 | 验收标准 |
|---|---|---|---|
| **P0** | 多场景长稳复测 | 使用 2 KiB 配置重复 150 s 以上会话，覆盖不同无线距离/干扰、VT03 重连和长时间运行；归档 JSON、事件、录像与抽帧 | 多次会话重连后均无 USB/解码错误，损坏帧与丢帧可解释且受控 |
| **P0** | 断链恢复边界 | 区分 halted endpoint 的原地恢复与无线链路丢失；明确何时需要重连 VT03；禁止跨断点盲拼参考帧 | 状态与事件能给出可操作结论，重连后重新获得参数集 + IRAP 并恢复输出 |
| **P1** | IRAP 可用性 | 当前流无周期性 IRAP；继续对比 VT03 重连、官方 Client 启动和 USB 初始化时序，确认新解码起点的触发条件 | 链路丢失后存在可重复的新 IRAP 获取方法或明确必要条件 |
| **P1** | 视觉接入与时延 | 在实际消费者负载下测量端到端时延、队列丢帧、CPU/内存；验证 `read_frame()`/`latest_frame` 语义 | BGR 帧稳定可调用，时延有界，队列不会无限积压 |
| **P2** | 被动逆向启动控制 | 仅在重连仍不能稳定获得 IRAP 时，用 usbmon/USBPcap 记录官方 Client 的 Control/Bulk OUT 时序 | 获得有证据支持的启动/关键帧请求序列；避免猜测未知 OUT 指令 |
| **P2** | 交付硬化 | 服务化启动、权限安装、依赖锁定、多主机复现、日志轮转与最小 demo | 新 Ubuntu 主机按 README 可复现，长期运行可运维 |

### 5.1 建议首先执行的四个操作

**操作 A：重放实时金样本并检查实际画面。**

```bash
python -m vt13_video replay \
  --file live_runs/live_run09.bin \
  --headless --save-first /tmp/vt13_replay_first.png \
  --json-stats
xdg-open /tmp/vt13_replay_first.png
```

**操作 B：执行新的长时会话并保存全部诊断产物。**

```bash
mkdir -p live_runs
python -m vt13_video stream \
  --config config/vt13_video.yaml \
  --headless --seconds 150 \
  --save-first /tmp/vt13_live_first.png \
  --record live_runs/live_run10.bin \
  --json-stats > /tmp/vt13_live10_stats.json 2> /tmp/vt13_live10.log
```

**操作 C：复测“先断链、后重连”的恢复路径。**

保持 VT03 断链，先启动操作 B 的命令；观察 `clear_halt`、错误计数和首帧时间，再连接 VT03。结束后检查 JSON 中的 `usb.errors`、`usb.halt_clears`、`decode.frames`、`decode.corrupt_frames` 与 `stream.irap`，确认首帧前错误存在、重连后错误不再增长，且录像可离线重放出相同帧数。

**操作 D：同时检查 USB 内核日志。**

```bash
sudo dmesg -T | grep -Ei 'usb|xhci|reset|disconnect|error -|2ca3' | tail -n 100
lsusb -t
lsusb -d 2ca3:1020
```

最好把 `dmesg` 的事件时间与 `*.events.tsv` 对齐。注意重新打开 Interface 0 仅代表重新申领接口，**不代表设备端已经恢复正常视频输出**。

## 6. 风险、推断与不能过度解读的地方

1. **两次会话已验证，但不等于所有无线环境都已覆盖。** `live_run09` 为 145.968 s；`live_run10` 为 130.6 s，并覆盖一次早期断链恢复。仍需在不同距离、干扰、重复重连和更长运行时间下复测。
2. **2 KiB 读长是缓解措施，不是 EIO 根因修复。** 4 KiB 及以上明显更差，说明传输粒度会影响故障频率，但不能据此断言硬件、驱动或无线链路的最终原因。
3. **`status_drain` 仍未证明必要。** 它只读排空 `0x82`，可减少结构化通道积压，但现有对照不足以证明缺少它会破坏视频流；应保留为实验性开关。
4. **标准 USB reset 不能替代 VT03 重连。** `live_run07` 中 reset 后视频流未重启，也没有新的 IRAP；链路丢失后必须先恢复 VT03/VT13 无线连接，再期待新的解码起点。
5. **当前流没有周期性 IRAP。** 缓存的 VPS/SPS/PPS 只能帮助解析，不能重建缺失参考帧；跨断点盲拼 P 帧可能产生大量损坏图像。
6. **损坏帧抑制是输出策略，不是“码流无损坏”的证明。** PyAV 开启 `output_corrupt` 以避免 USB 损伤后整个解码器停摆；默认队列丢弃 `av_frame.is_corrupt` 帧。若设置 `emit_corrupt_frames=true`，下游必须显式处理 `Frame.corrupt`。
7. **60.59 FPS 是流水线实测解码帧率。** 它证明持续输出能力，但不等于相机采集帧率或端到端时延；视觉接入时仍需单独测量时延、队列丢帧和抖动。
8. **固件/核心文件版本匹配问题需单独排查。** 如果无线连接不稳定或出现官方报错，应先保障 VT03/VT13 正常配对，但这不影响已经完成的 USB → HEVC → BGR 链路验证。

## 7. 阶段里程碑和完成定义

| 里程碑 | 当前状态 | 完成定义 |
|---|---|---|
| M1 USB 接口定位 | **完成** | `0x81` 连续提取合法 HEVC NAL 数据 |
| M2 离线解码 | **完成（含目视 QA）** | 冷启动文件解码 105 帧；实时录像离线重放 5,537 帧；抽帧与联系表无可见花屏 |
| M3 实时关键帧捕获 | **完成** | `live_run09` 获得 VPS/SPS/PPS 与 IRAP，并持续输出图像 |
| M4 稳定 USB 采集 | **完成（重连边界明确）** | `live_run09` 145.968 s、`live_run10` 130.6 s；两次断链阶段的 stall 均由 `clear_halt` 原地恢复，重连后无 USB 错误；标准 reset 不能替代 VT03 重连 |
| M5 OpenCV 实时图像 | **完成（基础）** | 连续输出 BGR 帧，60.59 FPS、0 丢帧；时延与消费者负载仍需专项测量 |
| M6 完整可交付程序 | **基本完成** | CLI、配置、udev、录制/日志、测试与 README 已具备；多主机复现和服务化运维仍待补齐 |

### 交接时最重要的结论

**我们已经完成“USB → HEVC → 实时 BGR 图像”的实证验证。下一阶段不是重新寻找视频端口或解码格式，而是验证不同无线环境下的长稳表现，明确“端点 halt 原地恢复”与“无线链路丢失后重连 VT03”的边界，并补齐新 IRAP、时延和交付运维的验收。**

## 8. 工程化实现状态（2026-10-31）

开发流程、问题处理、调试手册、调参建议与延迟分析见
[`docs/DEVELOPMENT_FLOW_AND_LATENCY.md`](docs/DEVELOPMENT_FLOW_AND_LATENCY.md)。

已在工作目录新增模块化接收程序 `vt13_video/`，覆盖：

- 增量 Annex-B 解析、Access Unit 组装、VPS/SPS/PPS 缓存和 IRAP 识别。
- sysfs + PyUSB 设备发现、端点校验、usbfs/权限错误诊断和 udev 规则。
- 只读 Bulk IN 采集，默认 `read_size=2048`；指数退避、抖动、健康读取判定、可选 `clear_halt`/设备复位。实测 VT13 的 halted Bulk IN 可能表现为 `EIO`，因此 `io` 错误也会尝试清除端点 halt。
- 恢复语义区分错误类型：成功的 `io` halt clear 保留 parser/assembler/decoder 状态；成功的 `pipe`/`stall` clear 标记 discontinuity 并重置解析/解码状态；halt clear 失败、触发设备 reset 或其他错误类型会关闭并重开 USB。
- PyAV HEVC 解码、关键帧门控、解码器重置、有界帧队列和 BGR/RGB/灰度输出；开启 `output_corrupt`，但默认丢弃 `av_frame.is_corrupt` 帧，可通过 `emit_corrupt_frames` 显式放开。
- `device.status_drain` 只读排空 `0x82`，当前默认启用，但保留为实验性、可选能力。
- `devices`、`inspect`、`stream`、`replay`、`doctor`、`config` CLI。
- 新增链路就绪快照 `link`：`usb_open`、`data_flowing`、`parameter_sets_complete`、`irap_seen`、`keyframe_started`、`streaming`。其中 `irap_seen` / `keyframe_started` 按当前采集 epoch 统计，遇到 discontinuity 会清零；生命周期计数仍在 `stream` 中。
- 周期性状态行附带 `usb/data/params/irap/keyframe`；日志会明确打印 `USB link is up`、`parameter sets complete`、`IRAP received; starting decoder`。若当前数据 epoch 持续 10 s 有数据但无法启动解码，会提示给 VT03 重新上电；缺少参数集时要求新的 VPS/SPS/PPS + IRAP，参数集已完整时只要求新的 IRAP。重连或 discontinuity 后计时重新开始。
- 同类恢复错误每 5 s 最多告警一次，并在恢复报告时汇总被抑制的重复详情；统计与 `.events.tsv` 仍逐条完整记录，disconnect 和 `clear_halt` 失败始终告警。
- 新增 `decoder.save_parameter_sets` 与 `--save-parameter-sets`：每完成一组 VPS/SPS/PPS 就以原子方式写入 Annex-B 文件，未变化的组不重复写。保存文件可通过 `--parameter-sets-file` 复用，但只能辅助 bootstrap，不能替代新的 IRAP 和参考帧链。
- YAML 严格校验、相对路径解析、默认配置生成、原始码流录制和事件/时间戳日志；录制路径不可写时在打开 USB 前返回可操作错误。
- USB 诊断：空读（0 字节）计数、持续无数据 stall 恢复；错误快照保留 `errno`、libusb backend code、成功读取计数/字节数和距最后数据时间。
- `doctor` 会区分设备节点缺失与存在但当前用户不可读写，并给出 udev/权限修复提示；USB 打开错误同样附带 udev 规则提示。
- 录制旁文件包含 UTC 墙钟时间（毫秒精度），`.events.tsv` 与 `.times.tsv` 可直接和 `dmesg -T` 对照（必要时统一时区）。

离线回归已验证：`captures/cold_start/bulk_if0_ep81.bin` 解码 **105 帧、0 个解码错误、121 个 Access Unit**；首帧 **1832×1032**，后续帧达到 **1920×1080**。去除参数集的码流在无缓存时为 **0 帧**，使用 `parameter_sets_file` 引导后恢复为 **105 帧**。`tests/` 下 **50 个 `unittest` 用例全部通过**。

实时回归已验证：`live_runs/live_run09.bin` 在 **145.968 s** 内解码 **5,537 帧、60.59 FPS、1920×1080**，**0 个解码错误、0 个损坏帧、0 个丢帧**；首帧前因故意断开 VT03 发生 **43 次 USB 错误/恢复**，43 次 `clear_halt` 全部成功，首帧出现于 **51.366 s**，重连后无 USB 错误。离线重放同一录像得到相同帧数，且 **0 个解码错误、0 次重置、0 个损坏帧**；全帧联系表与全分辨率抽帧已目视检查。30 秒读长探针显示 2 KiB 稳定、4 KiB 及以上错误明显增加，因此默认采用 2 KiB。

补充回归 `live_run10`：**130.6 s** 内输出 **6,342 个干净帧、60.6 FPS、1920×1080**；**47 次 USB stall** 全部由 `clear_halt` 原地恢复，**407 个 corrupt frame 默认抑制**且集中在早期，断链恢复后无 USB 错误。离线重放得到 **6,342 帧、409 个 corrupt、0 个解码错误**；全分辨率后期抽帧清晰。

补充回归 `live_run11`：首帧前已有 **7.78 MiB / 0 帧**，第二次 VT03 上电后才在 **28.0 s** 出图；实时 **970 帧、155 次 USB 错误/恢复**，离线重放 **974 帧、0 个解码错误**。用 `--save-parameter-sets` 生成的 VPS/SPS/PPS 文件为 **102 B**，并通过 NAL 扫描确认类型为 **32/33/34**。

实机运行前仍应先检查权限与设备状态；SSH/headless 环境不要依赖 `uaccess`，应使用 owner/group udev 规则。验证命令：

```bash
python -m vt13_video doctor
mkdir -p live_runs
python -m vt13_video stream --config config/vt13_video.yaml \
  --headless --seconds 150 \
  --save-first /tmp/vt13_live_first.png \
  --record live_runs/live_run10.bin \
  --json-stats
```

入口、配置、udev、API 示例和限制说明见 `README.md`。

---

**文档依据：** 截至 2026-10-31 的 `live_run09` 实机与离线重放日志、读长探针结果及 `unittest` 回归结果；关键产物路径见 §4.3。
