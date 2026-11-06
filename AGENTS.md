# AGENTS.md — DJI C5 / VT13 → CM311 实时 HEVC 图传项目

> **适用对象**：在 Ubuntu PC 上运行、通过 SSH 操作 CM311 的 Codex / coding agent。  
> **项目状态基线**：2026-11-06；历史结果是排障线索，不自动等同于当前设备状态。  
> **优先级**：人身/设备安全与可恢复性 > 原始数据保护 > 解码结果正确性 > 长期稳定性 > 延迟/性能 > 开发便利性。  
> **首轮要求**：先盘点、确认、记录，**不要立即进行无线实测、改内核或安装系统组件**。

## 0. Agent 的执行契约（必须遵守）

你负责嵌入式 Linux、USB、HEVC、V4L2 M2M 与 Amlogic GXL；获相应权限后执行可追溯的审查、修改、测试、部署验证和报告。

**必须遵守**：

1. **先发现真实环境，后写命令**：确认 SSH 目标、CPU 架构、Linux/Armbian 版本、源码和 CLI 的实际存在情况。文中的路径是已知历史路径，不能无条件假设当前仍一致。
2. **关键事实不确定时向人提问**：尤其 SSH 目标、真实图传启动命令、显示技术栈、系统是否正在承担其他任务。可并行完成不依赖这些信息的只读工作；不得为了继续而猜测。
3. **先提供具体计划**：目标、涉及主机、计划改动、风险等级、回退方式、验证准则。一次只推进最小可验证改动，记录证据。
4. **按 §5 的批准制度执行**：有害、不可逆、可能让 CM311 失去 SSH 或视频能力的命令，必须先展示**完整将要执行的命令**并取得明确批准。没有回复即未批准；以前的批准不能自动扩展到新操作。
5. **无线图传实测实行人机交接**：实际顺序必须为「先启动并确认接收程序处于等待状态 → 再由人开启无线图传」。Agent 提供完整、可复制粘贴的 Bash 命令和预期 READY 证据；由人完成物理操作并反馈结果，再由 Agent 自动分析日志。不要假定 Codex 可以控制无线发射端。
6. **Ubuntu PC 与 CM311 职责分离**：复杂分析、重计算、离线软件解码、源码审查和可行时的构建优先在 PC；最终所有代码、二进制、依赖及运行流程必须兼容 **CM311 目标环境**，并在目标机完成验收。
7. **数据/源代码的所有权与同步清晰**：区分 PC 本地、CM311 远端以及历史捕获；检查 SHA256/文件大小。未经批准不覆盖远端黄金版本、已有日志、内核模块和系统配置。
8. **按证据措辞**：明确区分 `已验证`、`实验性 workaround`、`怀疑/待证实`。`FFmpeg RC=0`、帧数正确或 VDEC `status=0x8`，均不能单独证明图像内容正确。
9. **中文沟通**（代码、命令、变量名可用英文）。所有给人的命令必须标明在哪台主机执行、前提条件、预期输出、终止方法和日志路径。不得输出只能意会的伪命令或未核实的 CLI 选项。
10. **一次任务结束必须报告**：执行内容、修改文件、命令及退出码、测试结果、证据路径、剩余风险、是否需要人批准以及下一步。
11. **本地/跨机代码与数据一致性（强制）**：任何跨机同步前，先记录来源主机、目标主机、路径、Git commit/工作树 diff、文件大小和 SHA256；同步后重新计算并比对。`rsync`/复制成功、文件存在或时间戳相近都不等于内容一致。不得覆盖远端黄金数据、运行中的二进制或未提交修改；无法证明一致时必须标记“未验证”并写入交接文档。源码和文档应纳入本目录 Git；大体积原始捕获/构建产物可忽略，但必须在交接文档中维护校验清单。
12. **每步三文档同步（强制）**：每完成一个可验证步骤（只读盘点、分析、修改、测试、等待批准或失败），都必须检查并更新三份文档；交接文件至少追加该步骤的时间、主机、命令/退出码、证据、结论和下一步。未更新三文档不得宣称该步骤完成。
13. **临时文件/数据位置（强制）**：复制、拉取、分析中间产物和临时日志默认放在项目目录内的 `.codex_tmp/<step>/`，不要散落到 `/tmp`；仅在项目目录不可写或外部工具强制要求时使用 `/tmp`，并在交接文档记录实际路径和清理责任。`.codex_tmp/` 必须被 Git 忽略，临时数据不得覆盖原始捕获或 golden。

### 范围与优先级

本文作用于其所在目录及子目录。若 Codex 同时操作其他仓库（例如独立的 FFmpeg、Linux kernel 源码树），应明确读取并遵守那些仓库各自的 `AGENTS.md`；本文件的设备安全、人工批准与实测顺序规则也作为整个项目的总约束。与人的新指令冲突时先询问澄清，不得默默放宽安全要求。

---

## 1. 项目目标与可交付成果

### 1.1 总目标

在 **CM311 / Amlogic GXL** 上，通过 USB 接收 DJI C5 / VT13 无线图传，完成厂商私有协议解包、HEVC Annex-B 重组、**V4L2 M2M 硬件 H.265 解码**和 HDMI 实时显示；链路断开/恢复、缺帧、GOP 变化及动态分辨率切换时，程序必须可诊断、可恢复，不应导致系统失联或驱动死锁。

```text
DJI 摄像头/无线发射端
         │  无线图传（由人实际开启/关闭）
DJI C5 / VT13 USB 接收设备（USB VID:PID 2ca3:1020）
         │  私有 USB Bulk，关键视频 IN EP 0x81（历史识别结果）
CM311 上的 USB 接收 / VT13 解包
         │  HEVC NAL → Access Unit，记录时间戳和完整性
         ▼
CM311 Amlogic GXL meson-vdec / V4L2 M2M HEVC
         │  NV12（硬件 CAPTURE）
         ▼
帧队列 / 低延迟缩放与渲染
         │
HDMI 显示
```

### 1.2 验收维度（目前没有确认的指标不能冒充要求）

- 功能：可连续接收实际无线链路视频，并在 HDMI 上看到持续正确画面。
- 编码：以真实输入为准，当前记录有 **1832×1032** 和 **1920×1080** HEVC，并可能在同一流内切换；不可假设固定帧率、GOP 或分辨率。
- 性能：期望尽可能低延迟、平稳输出；历史讨论的 **约 30–50 FPS、显示约 1024×576** 为**待用户确认的目标**，不是已达成的结果、也不是硬门槛。实际延迟上限、最低 FPS、最大 CPU 使用率待定义。
- 稳定：长时间运行、视频帧缺失、USB/无线链路变化时无无界内存增长、无 SSH 丢失、无系统崩溃；如果无法解码，应明确报 `WAIT_IDR` / `NEED_RESYNC`，不能持续输出未标识的错误图像。
- 部署：目标机启动/停止/重启流程可重复，二进制与库版本兼容目标 Armbian；不得依赖 Ubuntu PC 在正常运行时在线（除 SSH 管理和调试阶段）。
- 证据：功能测试必须给出运行日志、输入样本 SHA256、帧数/帧哈希（适用时）、驱动日志、CPU/内存使用与错误恢复现象。

### 1.3 预期交付物

- CM311 可部署的接收 + HEVC 硬解 + HDMI 播放程序/脚本及依赖说明。
- 清晰的 `README`：安装、手工启动、退出、断线恢复、常见故障与回滚。
- 可复现的离线测试及用于对比软/硬解结果的工具。
- 可追溯的测试报告和少量经过筛选的基准码流（不得将大量原始捕获默认提交 Git）。
- 已验证的改动补丁（可能分别属于 `mobile_vt`、FFmpeg、kernel）；对实验补丁保留单独标记。

---

## 2. 环境拓扑、源码与真实状态识别

### 2.1 两台主机

| 主机 | 用途 | 已知信息 / 注意 |
|---|---|---|
| **Ubuntu PC** | Codex 主执行环境；重计算、静态分析、源码搜索、软件参考解码、可行时构建 | PC 的实际路径、CPU 架构、可用空间、SSH alias **待探测** |
| **CM311** | 真正的 USB 接收、GXL 硬解、HDMI 显示和最终部署环境 | 历史 Armbian kernel `6.18.59-ophub`；实际 `uname -r` 必须重新确认 |

**历史 CM311 路径（须核实）**：

```text
~/mobile_vt/                         # VT13/USB 视频项目
~/mobile_vt/captures/                # 捕获/实验数据
/tmp/dji_test_latest_dir             # 最近一次历史测试目录指针，读取即可；不要覆盖
~/linux-6.18-vdec/                   # 修改过的内核源码
~/linux-6.18-vdec/drivers/staging/media/meson/vdec/codec_hevc.c
~/ffmpeg-6.1.1-v4l2/                 # 自编译 FFmpeg 6.1.1
~/ffmpeg-6.1.1-v4l2/ffmpeg           # 测试硬解器
```

**用户曾使用的 FFmpeg / 解码器**：

```text
/usr/bin/ffmpeg                      # 系统 FFmpeg，可用于标准软件诊断
~/ffmpeg-6.1.1-v4l2/ffmpeg           # 试验性构建，支持 hevc_v4l2m2m
Decoder: hevc / hevc_v4l2m2m
Driver: meson-vdec
V4L2 CAPTURE: NV12M / NM12
```

### 2.2 首轮必须完成的只读检查

**先向人获取/确认 `CM311_SSH`（如已有 SSH alias 则使用 alias），不得猜 IP。** 以下是从 **Ubuntu PC** 执行的可复制检查；请先把 `CM311_SSH` 赋予真实目标，或运行 `read` 提示输入：

```bash
# Ubuntu PC；只读，不会 reboot 或修改 CM311
read -r -p 'CM311 SSH 目标（user@host 或 SSH alias）: ' CM311_SSH
export CM311_SSH
ssh "$CM311_SSH" 'bash -s' <<'REMOTE'
set -eu
printf '\n=== IDENTITY ===\n'
whoami; hostname; uname -a; cat /etc/os-release | head -12
printf '\n=== STORAGE & MEMORY ===\n'
df -h "$HOME" /tmp; free -h
printf '\n=== PROJECT PATHS ===\n'
for p in "$HOME/mobile_vt" "$HOME/linux-6.18-vdec" "$HOME/ffmpeg-6.1.1-v4l2"; do
  if [ -d "$p" ]; then ls -ld "$p"; else printf 'MISSING: %s\n' "$p"; fi
done
printf '\n=== COMMANDS ===\n'
for t in python3 ffmpeg ffprobe v4l2-ctl tmux rsync git sha256sum; do
  command -v "$t" || true
done
printf '\n=== VIDEO DEVICES ===\n'
ls -l /dev/video* 2>/dev/null || true
printf '\n=== PROJECT GIT STATUS ===\n'
for p in "$HOME/mobile_vt" "$HOME/linux-6.18-vdec" "$HOME/ffmpeg-6.1.1-v4l2"; do
  if [ -d "$p/.git" ]; then
    (cd "$p" && printf '\n-- %s --\n' "$p" && git status --short && git rev-parse --short HEAD)
  fi
done
REMOTE
```

随后只读检查 `python3 -m vt13_video --help`、项目 README、实际入口文件、已有启动脚本；如果某个命令可能连接/占用 USB 设备，先改为阅读源码或 `--help`，确认其无副作用再运行。`--help` 入口可能不符合当前工程结构，**不能猜测不存在的子命令或参数**。

CM311 真正的版本信息应通过 `uname -m`、`uname -r`、`ldd --version`、`file`、`readelf`、`v4l2-ctl`（若已安装）等检查；PC 编译的 x86_64 二进制不能直接复制给 ARM 运行。对 kernel module 还须确认 vermagic / ABI / `CONFIG_MODVERSIONS` 等兼容性。

### 2.3 三份维护文档与跨会话交接（强制）

本项目固定维护以下三份文档；任何 agent 在开始任务前必须阅读，结束时按实际证据更新：

1. `AGENTS.md`：安全、批准、验证与本地/跨机一致性规则。
2. `docs/REMOTE_MACHINE_USAGE.md`：CM311 访问方式、当前环境快照、常用命令和待复验项。
3. `docs/INTERSESSION_TRANSFER.md`：变更日志、实验记录、证据路径、待验证清单和下一会话交接。

交接文件不是“已完成”的证明；必须区分 `已验证`、`实验性 workaround`、`怀疑/待证实`。每次会话结束至少更新：执行内容、修改文件、命令/退出码、测试证据、未验证项、风险与下一步。若本轮未启动 USB/V4L2/HDMI 或无线链路，也要明确记录。

每一步（包括只读盘点、差异分析、修改、测试和等待批准）结束时都必须更新三份文档；交接文件按步骤追加记录，而不是只在会话结束补写。临时副本和中间产物放在 `.codex_tmp/<step>/`，并在交接文件记录路径；该目录不提交 Git。

本地工作树应使用 Git 管理；初始化/提交状态记录在交接文档。`.gitignore` 必须排除大体积原始捕获、构建产物和缓存，但保留必要 golden sample 或 SHA256 清单。远端工作树若尚未成为有效 Git 仓库，跨机一致性检查必须退回到明确的 SHA256 清单，不能凭目录存在推断同步完成。

### 2.4 代码权威侧与同步原则（2026-11-06 用户确认）

- **CM311 `~/mobile_vt`**：用户确认是当前最新实验代码；包含异步 USB 预取、PyAV 线程实验、低延迟 catch-up 等实验路径。最新不等于生产就绪，也不等于所有文件都比 PC 新。
- **Ubuntu PC `mobile_vt`**：用户确认是可工作的软件解码基线；本地 50 个离线测试通过，用于软件参考、回归和可复现分析。
- 两侧不得整体覆盖：以 CM311 作为最新实验参考，以 PC 作为可用软解基线；合并必须逐文件审查，记录 Git commit/diff 或 SHA256，并在两侧跑测试。

---

## 3. 已验证事实、实验补丁及未决问题（2026-11-06 基线）

### 3.1 已有证据

1. **USB 协议**：DJI C5 的 vendor-specific USB 数据可采集并部分重组成 HEVC。历史视频流的 USB 接口和 Bulk 端点已识别；`vt13_video` 有 `devices` / `inspect` / `stream` / `replay` / `doctor` / `config` 等入口（**具体 CLI 语法待查看现有代码**）。
2. **码流**：测试 `no_sei.h265` 清除异常 SEI 后可软件解码；历史样本总计约 **132 个 HEVC AU**，GOP/IRAP 起点在 packet 1、23、45。第三组真实 SPS 分辨率改为 **1920×1080**，前两组为 **1832×1032**。
3. **基础硬解**：定制的 GXL `meson-vdec` 可硬解 HEVC；不少片段的 FFmpeg 软件和硬件输出逐帧 MD5 一致。**硬解能力已验证**，但不是任意 DJI 数据均无错。
4. **Source Change**：FFmpeg 6.1.1 原 `hevc_v4l2m2m` 动态分辨率切换会卡在 `waiting for user to release AVBufferRefs`。REFSCAN 捕获到单个旧 CAPTURE buffer（两 plane）仍被持有。实验性 **Copy-Out**（`v4l2_m2m_dec.c` 把 MMAP AVFrame 复制到普通内存后释放旧引用）使 reinit 时 `refcount=0`，可以从 1832×1032 切到 1920×1080。
5. **Source Change 残留**：66 AU 软解 66 帧、硬解 65 帧；FrameMD5 对齐显示 SW index 43 在硬解丢失，SW 44–64 与 HW 43–63 一致，最后一帧还存在 EOF flush 相关差异。**不能声称完全无丢帧。**
6. **两类 `0x0F`**：原始 GOP 边界 POC21 问题通过插入 1024 B 零字节绕过；另一个在 1920×1080 的 Packet81 / POC50 触发，错误 `HEVC_LCU_CHECK status=0xf idx=404 total=2040`，独立从 packet45 IDR 启动也能复现。两者可能机制不同。
7. **POC/参考**：Packet80→81→82 的 POC `35→50→55`；SW 报缺参考 POC49/54；驱动日志有 `Missing L0 reference POC 49, using POC 50`。**参考链不连续是真实观察，不能直接归因为 USB 丢包。**
8. **Packet81 padding sweep（连续重复 3 轮）**：在 Packet81 后、Packet82 前插入 0/64/256 B，VDEC 仍 `status=0xf`；插入 512/1024/2048/4096/8192 B，VDEC `status=0x8`、退出码 0；成功时图片处理达到最后 LCU index 2039/2040。
9. **图片一致性限制**：`sw_raw == sw_pad512` 38/38；`hw_pad512 == hw_pad8192` 38/38；`sw_pad512` vs `hw_pad512` **仅 36/38 一致**，差异在 POC50、POC55（均存在参考链缺失；最后一帧也可能受 EOF 影响）。**Padding 只是实验性硬解不中断 workaround，不是生产质量修复。**
10. **POC 改写对照**：把 POC50/55 改成 36/37 但保留原压缩数据，硬解仍在相同 LCU 报 `0x0F`；克隆先前可解的 Packet80 作为 Packet81 后成功，说明触发依赖输入内容/边界，不只是 POC 缺失。

### 3.2 已知实验性代码状态——需要审查，不应照单全收

- `~/ffmpeg-6.1.1-v4l2/libavcodec/v4l2_buffers.c`：曾移动 `atomic_fetch_add_explicit(&s->refcount,1,...)`，试图修正 plane/group 引用计数不对称；**没有完成必要性与正确性验证**。
- `libavcodec/v4l2_m2m.c`：包含 `V4L2_REFSCAN` / `V4L2_REFTRACE` 诊断输出。
- `libavcodec/v4l2_buffers.c`：包含 `CAPTRACE HANDOFF/FREE` 诊断输出。
- `libavcodec/v4l2_m2m_dec.c`：包含 **Copy-Out** 诊断 workaround；在 CM311 增加每帧内存拷贝和分配成本。
- `~/linux-6.18-vdec/.../codec_hevc.c`：包含调试和参考帧替代/Source Change 相关修改。必须先对比基线，不能直接把整个文件认定为可发布修复。
- FFmpeg 前缀测试出现的 `Assertion pkt failed at fftools/ffmpeg_dec.c:597` 是解码失败导致 CLI 路径中止的现象；不要通过移除 assertion 掩盖内核错误。

### 3.3 尚未解决的关键问题（按优先度）

**P0 — 阻断生产**

- 异常 HEVC Slice / GOP 边界 `0x0F` 的真正根因和可通用修复；有 padding 成功不等于图片正确。
- 无线/USB/软件重组层的 AU 缺失与 POC 断裂发生在哪里、如何检测；恢复时如何重新获得可用 IRAP/IDR。
- 实际无线图传链路与 CM311 HDMI 的持续低延迟端到端运行和恢复。

**P1 — 正确性/健壮性**

- 动态分辨率切换时丢一帧；EOF 时最后帧可能提前输出；Copy-Out 成本/替代方案；引用计数补丁验证。
- 真实场景长时间负载、CPU/内存/温度、音视频帧调度（当前项目以视频为主）；断链重连后软件和硬件状态机恢复。
- 从 HEVC 原始数据到 HDMI 显示的时间戳、队列深度、丢帧策略及量化延迟测量。

单次 `status=0x8`、`RC=0`、POC 改写或补零均不能视为 P0 已解决。

### 3.4 待验证清单（Validation Needed）

以下项目在本基线中不能当作已验证；下一轮应先补齐证据，再推进高风险改动：

| 项目 | 当前状态 | 需要验证的证据 |
|---|---|---|
| 本地/远端代码一致性 | 用户确认：CM311 为最新实验代码，PC 为可用软解基线；2026-11-06 SHA256 对比为本地 24、远端 27；远端多 `config/vt13_video.no_status.yaml`、`config/vt13_video.yuvtest.yaml`、`vt13_video/async_usb.py`；`README.md`、`vt13_video/decoder.py`、`vt13_video/pipeline.py` 不同；远端 `.git` 仍无效；内核/FFmpeg 有未提交修改 | 逐文件审查/合并；记录 commit/diff/SHA256；两侧复测 |
| CM311 最新实验代码测试兼容性 | 远端 50 项中 49 通过；`test_allow_corrupt_frames_controls_pyav_output_flag` 因 PyAV 11.0.0 仅暴露 `Flags.OUTPUT_CORRUPT`、测试访问小写 `output_corrupt` 而报错 | 修复测试兼容性，或固定 PyAV 版本；重跑完整测试并记录 RC |
| CM311 最新捕获指针 | 2026-11-06 只读盘点时 `/tmp/dji_test_latest_dir` 不存在 | 指针存在且指向预期 capture root；不要猜测 |
| CM311 当前运行进程 | 本轮未启动任何 USB/V4L2/HDMI 程序 | `ps`/`pgrep`/`fuser` 证据；确认无冲突占用 |
| 显示技术栈 | 未核实 DRM/KMS、fbdev、X11/Wayland | `ls /dev/dri`、`loginctl`/`DISPLAY`、实际 HDMI 输出证据 |
| `vt13_video` 入口与 READY | 远端 `python3 -m vt13_video --help` RC=0；未跑 stream | 真实 `stream` 命令、READY/LISTENING 日志、退出方式 |
| golden capture | 本地与 CM311 的 `captures/cold_start/bulk_if0_ep81.bin` SHA256 已核对一致 | 记录大小、SHA256、来源路径；离线解码结果 |
| FFmpeg 硬解 | 自定义目录和修改存在；本轮未重跑解码 | `hevc_v4l2m2m` 命令、RC、帧数、FrameMD5/对比 |
| 内核模块/VDEC | 修改文件和未跟踪备份存在；本轮未看 dmesg | `uname -r`、模块 vermagic、dmesg、`status=0x8/0xf` |
| Source Change / POC50 / EOF | 历史结果，未在今日设备状态复验 | 受控离线/目标板短测证据 |
| 实时无线链路 | 本轮完全未启动 | 按 §6 人机交接；READY 后由人开图传 |
| 性能/延迟目标 | 30–50 FPS、约 1024×576 仍是待确认目标 | 用户确认 + CM311 实测 CPU/RSS/温度/延迟 |

---

## 4. 推荐工作方法与阶段顺序

原则：**现状快照 → 单变量假设 → 离线可复现 → 目标板短时验证 → 人工开启无线实测 → 性能与稳定性 → 受控部署**。用户当前只是要求准备 agent 指令；在没有新的执行任务时，停在只读盘点与待确认问题，不主动跑额外实验。

1. **发现阶段（无特权、只读）**：确认两个主机、代码版本、改动清单、设备节点、已知失败样本和磁盘空间；形成 `environment.md` 和 `baseline.md`，列不确定项。
2. **测试固化**：保留已知 HEVC 样本及 SHA256，编写离线软件解码 / `trace_headers` / FrameMD5 / 时序对齐脚本。回归覆盖：正常 GOP、源分辨率切换、POC50、EOF、输入中断。CI/PC 参考解码应尽可能无需硬件运行。
3. **接收层可靠性**：确认 VT13 帧完整性/序号、NAL 和 Access Unit 分帧、丢失检测、关键帧缓存与 `WAIT_IDR` 状态机。不要把缺失参考帧仅靠替代 POC 视为正常播放。
4. **驱动/FFmpeg 隔离修复**：分别验证 refcount 改动、Copy-Out、GOP padding；每次只变一个因素，留源代码 diff 与对照结果。若涉及模块装载、内核、V4L2 全局设备状态需按 §5 审批。
5. **HDMI 播放集成**：**先核实 CM311 当前实际显示技术栈**（DRM/KMS、fbdev、X11/Wayland 或其他）。不要虚构可用 overlay/显示设备接口；先走目标支持的最小路径，再优化零拷贝。
6. **真实无线链路验证**：严格采用 §6 人机交接流程，先接收进程后启动无线图传；对断线/重连/IDR 行为做可复现记录。物理触发由人负责。
7. **验收与发布**：在 CM311 实测通过功能、画面正确性、资源与断线恢复标准后，才将实验补丁转为部署路径。提供可回滚的构建产物和部署记录。

---

## 5. 风险分级与 HUMAN APPROVAL（强制）

默认仅授权只读、PC 沙盒文件、非破坏性离线计算。风险不明的远端操作须先询问。

| 等级 | 示例 | 执行规则 |
|---|---|---|
| **R0 只读** | `ls`、`cat`、`uname`、`git status`、读源码/已有日志、`ffprobe`、读取 sysfs | 可直接执行；注意不要触发设备占用 |
| **R1 可回滚、限沙盒** | PC 新增分析脚本、PC 离线软件解码、CM311 的单独测试目录产生日志（确认磁盘空间与进程无冲突） | 提前说明并限制磁盘、CPU 与超时时间；不得覆盖既有文件 |
| **R2 需用户明确同意** | 在 CM311 启动占用真实 USB/V4L2/HDMI 的程序；停止已有业务进程；大量拷贝/删除；写入工作树现有关键文件；非短时压力测试；连接/断开无线设备 | 展示完整命令、持续范围及退出方法；等批准后执行；无线开关仍由人操作 |
| **R3 高风险、每项单独明确批准** | `reboot`/`shutdown`/`poweroff`；`systemctl restart/stop` 影响 SSH/网络/显示/USB 的服务；`rmmod`/`modprobe`/驱动重载；写 `/lib/modules`、`/boot`、DTB、firmware、bootloader；升级 kernel/`apt upgrade`；改网络/防火墙/IP；`dd` 到设备；可能使 SSH 失联的操作 | **禁止自动执行**；必须先给人计划、完整命令、停机/失联风险、现场回退与物理访问条件，得到限定范围的明确批准，再在约定窗口进行 |

额外约束：

- **绝不**执行 `rm -rf` 清理未知目录、`git reset --hard`、`git clean -fdx`、覆盖原始捕获、抹掉 Git 历史、任意 `killall` / `pkill -f`、写 EFI/eMMC/闪存，除非人对完整作用域明确授权。危险操作即使被脚本间接调用也必须审批。
- 不用 `sudo` 碰运气；若只读诊断需要权限，先解释具体的 `sudo` 只读命令；**任何 root 写入**按高风险处理。不要索取、回显或记录人的密码、SSH 私钥、token。
- 不擅自 `apt install`（可能改包依赖和系统状态）；PC 安装开发依赖也先说明影响。优先用已安装工具或 PC 独立虚拟环境。
- 不自动调整系统电源、网络、摄像头/无线发射端及 USB 供电。`echo` 写 sysfs、unbind/bind USB、GPIO reset 等均视为可能影响链路的高风险操作。
- 不以 `timeout` 能结束进程为由忽视设备占用；实时视频解码器和内核可能存在失败后需要恢复的情形。
- 无法回退且缺少物理恢复手段时不得执行。
- 不能将人的一次 `批准` 当成整个会话对所有 reboot/驱动装载/删除的永久授权。**改变命令、目标、时间或范围，重新申请。**

### 审批申请模板（Agent 必须填完整）

```text
[NEEDS HUMAN APPROVAL]
目的：...
主机：Ubuntu PC / CM311（明确）
风险级别：R2 / R3
当前运行进程/影响范围：...
计划执行的完整命令：
  ...
可能后果：SSH 失联 / HDMI 中断 / 设备占用 / 数据覆盖 / 其他
前置检查与备份：...
回退命令与物理恢复要求：...
验证成功/失败的方法：...
请求批准范围：仅批准以上命令在本次窗口执行
```

收到明确、可对应上述命令的批准前，保持等待并可继续不冲突的只读任务。**尤其禁止先 reboot 再告诉用户。**

---

## 6. 无线图传启动顺序与人工交接（必读）

### 6.1 强制时序

实际系统有一个关键特性：**先开启 CM311 的接收程序，再由人开启无线图传，才会开始接收视频数据**。不能颠倒顺序；不能把无线发射尚未开启时的 `0 packets` 误报为程序故障。

```text
T0 Agent：验证 CM311 上可用程序及实际 CLI；备好日志目录与可停止的启动方式
T1 人：在确认不会干扰当前系统后，执行 Agent 给出的【CM311】启动命令
T2 人/Agent：检查程序确实存活并处于等待数据状态，给出 READY / LISTENING 证据
T3 人：**此时才开启无线图传**（必要时说明动作与时间）
T4 Agent：按约定收集 USB/视频/解码/显示日志及计数
T5 人：按指示结束/断开无线图传；Agent 只停止本次自己创建的测试进程
T6 Agent：自动分析数据、与基准比较、生成报告
```

### 6.2 Agent 要交付的「人可直接复制」实验包

在启动前，Agent **必须读真实 `vt13_video` 入口/帮助**，按当前源码生成一个已验证且可执行的测试入口脚本：

```text
CM311: ~/mobile_vt/.codex_runs/live_capture_verified.sh
```

此文件必须使用已核实的真实 CLI、读取环境变量 `DJI_RUN_DIR` 保存采集文件和统计、开启接收后才打印 `READY`；等待人开启无线图传。禁止臆造 `vt13_video` 参数。说明是否独占 USB/V4L2/HDMI，并按 R2 审批。

如果目标机已有 `tmux`，人可以使用如下可复制启动模板；**前提是 Agent 已在 CM311 上创建并验证可执行 `live_capture_verified.sh`，且人已批准本次启动**：

```bash
# 在 CM311 SSH shell 中执行；此刻无线图传仍保持关闭
set -euo pipefail
cd "$HOME/mobile_vt"
RUNNER="$HOME/mobile_vt/.codex_runs/live_capture_verified.sh"
test -x "$RUNNER" || { echo "ERROR: verified launcher missing"; exit 1; }
command -v tmux >/dev/null || { echo "ERROR: tmux not installed"; exit 1; }
RUN_ID="$(date +%Y%m%d_%H%M%S)"
RUN_DIR="$HOME/mobile_vt/captures/manual_live/$RUN_ID"
mkdir -p "$RUN_DIR"
printf '%s\n' "$RUN_DIR" > /tmp/dji_codex_last_live_run_dir
SESSION="dji_${RUN_ID}"
# 启动已验证的接收程序，日志保留到专用目录；不修改现有 latest 指针
tmux new-session -d -s "$SESSION" \
  "cd '$HOME/mobile_vt' && export DJI_RUN_DIR='$RUN_DIR' && exec '$RUNNER' > '$RUN_DIR/capture.log' 2>&1"
printf 'SESSION=%s\nRUN_DIR=%s\n' "$SESSION" "$RUN_DIR"
sleep 2
tmux has-session -t "$SESSION" || { echo "ERROR: capture exited early"; tail -80 "$RUN_DIR/capture.log"; exit 1; }
tail -30 "$RUN_DIR/capture.log"
echo '只有确认程序已 READY 后，才由人开启无线图传。'
```

**日志查看与结束**（CM311；仅针对本次 `dji_...` 会话，不使用 `pkill`）：

```bash
RUN_DIR="$(cat /tmp/dji_codex_last_live_run_dir)"
tail -n 100 "$RUN_DIR/capture.log"
tmux list-sessions
# 实验结束后，由人确认 SESSION 的确属于本次测试，按需执行：
# tmux kill-session -t 'dji_YYYYMMDD_HHMMSS'
```

如果目标机没有 `tmux`，Agent 需另给已审查的 `nohup`/foreground 方案，**不要默认自动安装软件**。READY 的判断须来自实际代码/日志；`sleep 2` 本身不是 READY 证明。

### 6.3 每次交接的报告内容

```text
[HUMAN ACTION REQUIRED — LIVE LINK]
测试目的：...
主机/终端：CM311 SSH shell
前置条件：无线图传关闭；确认旧接收进程状态；可用磁盘空间...
复制粘贴命令：<完整 Bash，已核查 CLI，不能包含待替换的伪参数>
预期 READY 标记：...
人执行的物理操作：看到 READY 后打开无线图传；记录开启时刻
采样时长/停止方式：...（时长由测试目标确定，不盲目后台运行）
产物路径：...
请回传：SESSION、RUN_DIR、tail 日志或对应文件；异常时不要自行 reboot
```

人反馈日志后，Agent 自动分析参数集/IRAP、POC/RPS、时间戳、VDEC、帧哈希及恢复时间；不得擅自重复无线实测。

---

## 7. Ubuntu PC 计算卸载、同步、部署约束

### 7.1 什么放 PC，什么必须在 CM311

**建议 PC 执行**：USB/HEVC 协议分析、复杂 Python 数据处理、trace/二进制统计、参考软件解码、FrameMD5 大样本比较、截图/图像质量分析、性能建模、跨编译（有完整工具链时）。**必须 CM311 执行**：真实 USB 收流、meson-vdec 硬解、V4L2 CAPTURE/Source Change、CM311 的真实 CPU/内存/温度测量、HDMI/显示测试与最终验收。

PC 上验证通过的 `ffmpeg` 不能当作 CM311 兼容性证据。若在 PC 上交叉编译，须证明目标 `aarch64`/`arm` 架构、动态加载器、glibc 依赖、FFmpeg 构建选项和目标驱动 ABI 一致；kernel module 需要严格匹配目标 `uname -r`、vermagic、符号/配置。**跨编译成功 ≠ 可直接覆盖部署。**

### 7.2 从 CM311 拉取选定测试码流到 PC（只读源数据）

以下命令在 **Ubuntu PC** 执行；前提：`CM311_SSH` 已设置，且目标路径存在。仅同步指定的小码流，不默认同步几百 MB 的原始 USB `.bin` 文件：

```bash
: "${CM311_SSH:?先执行 export CM311_SSH=user@host 或使用 SSH alias}"
PC_WORKSPACE="${HOME}/dji_cm311_workspace"
mkdir -p "$PC_WORKSPACE/input"
REMOTE_OUT="$(ssh "$CM311_SSH" 'cat /tmp/dji_test_latest_dir')"
# 校验历史数据目录，拒绝异常路径；不要将远端字符串作为命令执行
[[ "$REMOTE_OUT" =~ ^/home/[A-Za-z0-9._-]+/mobile_vt/captures/[A-Za-z0-9_./-]+$ ]] || {
  echo "Unexpected remote path: $REMOTE_OUT"; exit 1;
}
rsync -av --progress -e ssh \
  "${CM311_SSH}:${REMOTE_OUT}/hevc/no_sei.h265" \
  "$PC_WORKSPACE/input/"
REMOTE_SHA="$(ssh "$CM311_SSH" "sha256sum '$REMOTE_OUT/hevc/no_sei.h265'" | awk '{print $1}')"
LOCAL_SHA="$(sha256sum "$PC_WORKSPACE/input/no_sei.h265" | awk '{print $1}')"
printf 'remote=%s\nlocal =%s\n' "$REMOTE_SHA" "$LOCAL_SHA"
test "$REMOTE_SHA" = "$LOCAL_SHA" || { echo 'CHECKSUM MISMATCH'; exit 1; }
```

同步多个目录前列出大小和忽略规则（尤其 `captures/`、build objects），先 `rsync -avhn` 预览。`PC → CM311` 先进入 staging，并按 R2/R3 批准；禁止直接覆盖系统路径或运行中的二进制。

### 7.3 构建、测试、部署的安全路径

1. PC 或 CM311 上修改源码前保存 `git status --short`、diff 和版本号；对未跟踪的人工更改不能覆盖。优先 Git 分支 / patch；不执行会丢失本地修改的命令。
2. 小范围 FFmpeg 修改在 CM311 构建历史上用 `make -j2 ffmpeg` 或 `make -j4 ffmpeg` 增量编译；根据 CPU/内存负载选择并发数，**禁止为了速度无界 `-j$(nproc)` 导致内存耗尽**。
3. 测试输出写到独立的 `analysis/<run_id>/`，并与 golden input 隔离。若需要覆盖同名测试结果，改用新 run ID。
4. PC → CM311 时先 `rsync` 到 `~/mobile_vt/.codex_staging/<run_id>/`，验证 SHA256 和依赖、运行权限、可执行格式；真正替换活动二进制/服务必须按 R2/R3 审批并准备可执行的回滚命令。
5. 对内核 module、设备树、系统服务、引导分区的改动不得通过普通构建脚本隐式部署。构建成功后可以停在待人工批准状态。
6. **最终验证只认 CM311 实机**，不能用 PC 的 V4L2 行为替代。

---

## 8. 诊断与测试纪律

### 8.1 必须保存的结果

每轮测试至少记录：

```text
run_id / 日期与时区 / Ubuntu 或 CM311
测试目标及唯一改变的变量
Git commit + diff / 二进制版本 / uname -a
输入文件名、大小、SHA256、AU 数、VPS/SPS/PPS/IRAP 位置、分辨率
确切 Bash 命令、退出码、timeout、stdout/stderr 路径
SW/HW 解码帧数、FrameMD5 和首次不一致 index
相应 POC / RPS / Missing reference 日志
V4L2 Source Change、POLLERR、内核 HEVC_LCU_CHECK 状态
实际 USB/无线链路操作顺序、开始/结束时间（仅实测）
CPU / RSS / 温度 / 延迟和显示表现（如果可测）
本轮结论：通过 / 失败 / 不确定 + 证据 + 下一步
```

### 8.2 解释规则

- `POC` 跳变 + `Could not find ref` 说明当前参考链有缺口，**不自动说明 USB 丢包**；需检查上游序号、无线链路和 Access Unit 完整性。
- `SW_RC=0` 不证明码流无损；FFmpeg 软件解码器可能进行错误隐藏。
- `HW_RC=0`、VDEC `status=0x8` 不证明画面正确；必须比对软件参考、已知无误片段或视觉结果，并考虑软硬件对缺失参考图像的不同填充策略。
- 修改 POC/复制 payload 的合成码流只供诊断，不是生产修复。
- `status=0xf` 需要结合 LCU、shift、输入边界、参考状态判断。`shift` 包含 parser/FIFO 读取效应，不能未经验证映射成 CABAC 最后一字节。
- `refcount=0` 可支持当前 Source Change 引用释放正常，但不能证明全部 FFmpeg AVBufferRef 逻辑正确。
- 当前 Copy-Out 的 CPU 带宽开销必须在 CM311 实机量化；不要为了追求零拷贝而牺牲稳定性，也不要在未经验证时把 Copy-Out 移除。

---

## 9. 需要向人确认但不妨碍只读调查的信息

仅在成为实际阻塞点时提问，优先用一次简洁的问题收集同一阶段必须的多个信息；不要假设答案。

- Ubuntu PC 的工程路径、SSH 登录方式（`CM311_SSH` / SSH alias）、是否可使用免密登录。
- 目前 `mobile_vt` 真实启动入口和 CLI；是否已有持续运行的 USB/HDMI 进程；是否允许短时独占。
- CM311 的实际 SoC、`uname -m`、kernel、根文件系统、可用空间、构建 RAM；PC 是否已安装交叉工具链。
- HDMI 当前使用 DRM/KMS、fbdev、X11/Wayland 还是其他方式；目标物理显示设备、分辨率和权限。
- 必须达到的最低帧率、端到端延迟预算、画质/错误隐藏容忍度、测试运行时长。
- 人如何开启/关闭无线图传、无线链路是否支持主动请求 IDR；现有恢复方式是什么。
- 哪些服务/进程不可停止；是否具备 CM311 串口、现场物理访问、可恢复系统镜像。
- 是否批准安装额外开发工具、是否愿意提供对应的只读采样文件；大文件同步和日志保留限额。
- 本轮具体任务优先级：接收层恢复、内核硬解正确性、FFmpeg 引用管理、还是 HDMI 实时显示。

不要一次性因为以上问题都未回答就停止所有工作；能做的低风险只读审查、差异梳理、离线分析应先做。任何关键未知项与高风险写入冲突时则必须停下申请确认。

---

## 10. Agent 每次答复与进展报告格式

**开始一个较大任务时**：

```text
【当前目标】一句话
【已知环境】PC / CM311；已核实事实，仍需确认的事实
【行动计划】最多 3–6 个可验证步骤
【风险与批准】R0/R1/R2/R3，是否正在等待审批
【本轮输出】代码、日志或报告的准确路径
```

**结束每次执行时**：

```text
【已执行】精确命令摘要 + 主机 + 退出码
【已修改】文件路径与关键 diff；未触及的风险区域
【验证证据】日志/数据位置 + frame count、MD5/POC、dmesg 关键结果
【结论】已验证 / 尚未验证 / 有条件可用，区分根因与 workaround
【回滚】如有改动，列出恢复方式（不可破坏已有用户更改）
【需要人的操作/批准】只列必要动作，附可复制 Bash 和完整风险说明
【下一步】一项最高优先级行动及完成判据
```

**禁止**仅输出“应该重编译内核/重新连接设备/运行测试”而不给具体命令和目标主机；也禁止声称进行了未实际执行或无日志支持的验证。

### 当前第一轮应做什么

在用户未下发新的实验任务前，仅完成：**只读 SSH/项目状态盘点 → 检查现有改动与 CLI → 对照本文列出当前风险和证据缺口 → 提交小规模可执行计划**。不要自行让 CM311 reboot、替换 VDEC 模块、启动无线链路，或把 padding workaround 默认并入生产路径。

每轮开始先读 `docs/INTERSESSION_TRANSFER.md`；结束前更新该文件，即使本轮只做只读盘点或文档修改。若本地与远端代码/数据尚未建立同一 Git 基线或 SHA256 清单，必须在交接文件中明确写“未验证”，不得用“看起来一样”代替一致性证据。
