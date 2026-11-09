# AGENTS.md — DJI C5 / VT13 → CM311 实时 HEVC 图传项目

> **适用对象**：在 Ubuntu PC 上运行、通过 SSH 操作 CM311 的 Codex / coding agent。  
> **项目状态基线**：2026-11-06（2026-11-08 更新；离线硬解证据与 R0 实时烟测前预检见 §3.1。2026-11-09 追加 SSH 探测、PC 侧 opt-in 与 CM311 PyAV 硬解实测，见 §3.1 item 20-22 与 §3.4 V16/V17；同日 19:18 追加 rm-receiver 协议/驱动离线评估（item 33/V18）；20:45 完成控制面与恢复架构集成、捕获层 A/B 备妥（item 34/V19）；20:41 完成 run 5/6 实时验证（item 35/V20）；20:55 完成显示过滤与软件/硬件解码对比（item 36/V21））。历史结果是排障线索，不自动等同于当前设备状态。
> **优先级**：人身/设备安全与可恢复性 > 原始数据保护 > 解码结果正确性 > 长期稳定性 > 延迟/性能 > 开发便利性。  
> **首轮要求**：先盘点、确认、记录，**不要立即进行无线实测、改内核或安装系统组件**。

## 0. Agent 的执行契约（必须遵守）

你负责嵌入式 Linux、USB、HEVC、V4L2 M2M 与 Amlogic GXL；获相应权限后执行可追溯的审查、修改、测试、部署验证和报告。

**必须遵守**：

1. **先发现真实环境，后写命令**：确认 SSH 目标、CPU 架构、Linux/Armbian 版本、源码和 CLI 的实际存在情况。文中的路径是已知历史路径，不能无条件假设当前仍一致。
2. **关键事实不确定时向人提问**：尤其 SSH 目标、真实图传启动命令、显示技术栈、系统是否正在承担其他任务。可并行完成不依赖这些信息的只读工作；不得为了继续而猜测。
3. **先提供具体计划**：目标、涉及主机、计划改动、风险等级、回退方式、验证准则。一次只推进最小可验证改动，记录证据。
4. **按 §5 的批准制度执行**：离线测试/分析（PC 或 CM311 上不启动实时 USB/HDMI 的只读分析或短时测试，包括离线 `hevc_v4l2m2m` 解码）无需逐次人工批准，但须先确认设备空闲、使用独立输出目录和 `timeout`，并记录命令/RC/证据。有害、不可逆、可能让 CM311 失去 SSH 或视频能力的命令，必须先展示**完整将要执行的命令**并取得明确批准。没有回复即未批准；以前的批准不能自动扩展到新操作。
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

## 3. 已验证事实、实验补丁及未决问题（2026-11-06 基线；2026-11-07 更新）

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
11. **2026-11-07 CM311 离线硬解证据（clean 与 EOF）**：源码 `meson_vdec` 加载后，`clean_1832x1032.h265` 用 `-vsync 0` 软/硬解均 30 帧、RC=0，FrameMD5 29/30 一致，仅 index 29 不同，未观察 `status=0xf`。三个 EOF 变体软件均 27 帧、RC=0，且 SW FrameMD5 完全一致。硬件在 EOF drain/flush 阶段表现不同：`aud` 在 `timeout -k 5 45` 下 RC=137，`eos` 断言中止 RC=134；未启用 `-flush_packets` 时 framemd5 没有持久化帧。`zeros1024` 加 `-flush_packets 1 -pix_fmt yuv420p` 可 RC=0、27 帧，但 26/27 一致、末帧不同且跨运行哈希可变；三次无 flush 也均 RC=0/27，但第 2 次 FrameMD5 与第 1/3 次不同。`-frames:v` 提前停止时 `aud` 22 帧、`eos` 20 帧均全部匹配，说明已输出的普通帧内容正确，失败集中在 EOF drain；`flush_packets` 只是保留超时前输出的实验性手段，不是根治。根因未证实。
12. **2026-11-08 00:51 HKT CM311 只读盘点**：`/dev/video0` 无 opener，源码 `meson_vdec` 仍加载；`clean_1832x1032.h265`、`no_sei.h265`、`fresh_45_to_82.h265`、`pad_1024.h265` 和三个 EOF 样本均存在，SHA256 与既有记录一致。下一步是 clean 的 `-fps_mode passthrough` 复验及扩展样本硬解矩阵；本轮尚未启动 USB/HDMI/无线链路。
13. **2026-11-08 01:09-01:11 HKT CM311 扩展硬解矩阵**：全部使用 `-fps_mode passthrough`、硬件 `-flush_packets 1`、`timeout -k 5 45`。`clean` 软/硬解 30 帧、RC=0，FrameMD5 29/30 一致（仅 index 29 不同）；`no_sei` 软件 132 帧 RC=0，硬件在 POC21 报 `HEVC_LCU_CHECK status=0xf` 并中止 RC=134，仅输出 14 帧但全部匹配前缀；`fresh_45_to_82` 软件 38 帧 RC=0，硬件在 POC50 报 `status=0xf`、RC=134，输出 32 帧且全部匹配前缀；`pad_1024` 硬件 38 帧 RC=0，但仅 36/38 匹配，首差异 index 36，驱动仅见 `status=0x8` 与两条缺失参考替代。EOF：`aud` 本次 RC=137、18 帧全匹配；后续同窗口 3 次均为 19 帧且逐帧相同（跨窗口 22/18/19，见 item 14）；`eos` RC=134、20 帧全匹配；`zeros1024` RC=0、27 帧但 26/27 匹配。三份 EOF 软件参考仍完全一致。**结论：clean 的 `-fps_mode passthrough` 复验通过帧数/RC，但末帧仍不一致；POC21/POC50 的 `0xf` 中止、padding 内容差异和 EOF drain 均未解决。**
14. **2026-11-08 02:57-03:00 HKT CM311 `aud` EOF 重复**：同一命令连续 3 次均为 RC=137、19 帧，FrameMD5 完全相同且 19/19 匹配 SW；本次窗口内输出稳定。结合先前 22 帧与 01:09 矩阵 18 帧，超时前已输出帧数会跨窗口变化；根因仍指向 EOF drain/超时窗口，未证实。**不能把 18、19 或 22 任一帧数当作完整 EOF 解码结果。**
15. **2026-11-08 03:00 HKT 本地/远端证据一致性**：扩展矩阵证据目录 74 个文件、`aud` 重复证据目录 29 个文件，完整 SHA256 清单本地与 CM311 逐文件一致；清单保存在 `.codex_tmp/manifests_20261108/`。这是证据副本一致性，不代表硬解内容已验收。
16. **2026-11-08 03:51 HKT 测试后状态**：CM311 无 `ffmpeg`/`vt13_video` 残留，`/dev/video0` 无 opener，源码 `meson_vdec` 仍加载；未启动 USB/HDMI/无线链路。
17. **2026-11-08 19:54 HKT CM311 R0 实时烟测前预检**：CM311 仍为 `armbian`/`aarch64`/`6.18.59-ophub`；无 `vt13_video`/`ffmpeg` 进程，`/dev/video0` 无 opener；`/dev/dri` 有 `card0`、`card1`、`renderD128`，SSH 非交互环境 `DISPLAY`/`WAYLAND_DISPLAY` 为空，`loginctl` 有 active `seat0`/`tty7` 会话，实际 HDMI 输出仍未验证。`python3 -m vt13_video --help` 与 `stream --help` 均 RC=0，确认 `--headless`、`--seconds`、`--record`、`--json-stats` 等真实选项；源码没有字面 `READY`，应以 `USB source open` 后进入 `waiting_*` 状态作为接收端就绪证据。`doctor` RC=1：当前无匹配 `2ca3:1020`，`lsusb` 仅有 root hub 与 `23a9:ef18` SG Flash；USB 接收器未枚举，是实时烟测的硬阻塞。`.codex_runs/live_capture_verified.sh` 仍缺失。证据 `.codex_tmp/r0_precheck_20261108_1941/precheck.txt`，SHA256 `d8b7306e2b646bc7f27389184a231d38a32940c72e732941e9aa1f288cb66e51`。本轮未启动 USB/HDMI/无线链路，未修改 CM311 文件。
18. **2026-11-08 20:25-20:31 HKT CM311 离线软/硬解速率基准**：`clean_1832x1032.h265`（SHA256 `2e13db18...`）硬件 `hevc_v4l2m2m` 30 帧 RC=0，wall 1.212 s，user 1.563 s，sys 0.322 s；软件 `hevc` 30 帧 RC=0，wall 1.621 s，user 2.890 s，sys 0.334 s，FFmpeg bench rtime 0.802 s、maxrss 123488 kB；FrameMD5 29/30，末帧硬件 `1517d50f...` vs 软件 `133559bb...`。`pad_1024.h265`（1920×1080；ffprobe `r_frame_rate=60/1`、`avg_frame_rate=25/1`；SHA256 `75e8eb47...`）硬件 38 帧 RC=0，wall 1.585 s，user 1.984 s，sys 0.489 s，bench rtime 1.248 s、maxrss 118032 kB；软件 38 帧 RC=0，wall 2.295 s，user 5.243 s，sys 0.443 s，bench rtime 1.472 s、maxrss 143528 kB；FrameMD5 36/38，差异在帧 37/38（0-based index 36/37）。这是短样本端到端 FFmpeg+FrameMD5 基准，不是稳态 FPS：硬件约 24 fps wall（clean 30/1.212、pad 38/1.585），软件约 18.5/16.6 fps wall；30–50 fps 目标仍未证明。证据远端 `~/mobile_vt/.codex_tmp/cm311_hw_bench_20261108_202504/`、`.../cm311_hw_bench_pad_20261108_203050/`，本地同路径；14/12 个文件 SHA256 全匹配。未启动 USB/HDMI/无线链路。
19. **2026-11-08 代码核查：实时 Python 管线仍走软件解码**：`vt13_video/decoder.py` 使用 `av.CodecContext.create(self.config.codec, "r")`，默认 `decoder.codec: "hevc"`，没有显式选择 `hevc_v4l2m2m`。因此当前 `vt13_video stream/replay` 是 PyAV 软件 HEVC 解码；上述硬件基准来自 `~/ffmpeg-6.1.1-v4l2/ffmpeg -c:v hevc_v4l2m2m`。要把硬件解码用于实时管线，需要显式集成 V4L2 M2M（例如 PyAV 硬件 codec 或 FFmpeg 子进程），并以运行日志/CPU 证据确认。
20. **2026-11-09 12:03 HKT Ubuntu PC SSH 能力探测（只读）**：`ssh`/`scp`/`rsync`/`ssh-copy-id`/`ssh-agent`/`ssh-add` 均已安装，`sshpass` 未安装；agent 已加载 ED25519 key（fingerprint `SHA256:+EPYD...`，与 `~/.ssh/id_ed25519` 同一把）。`ssh -T -o BatchMode=yes -o ConnectTimeout=8 billieguo@10.42.0.11 'hostname; uname -m; uname -r'` **RC=255**，`Permission denied (publickey,password)`；`ssh -v` 证明 TCP/SSH 握手成功、公钥被 offer 后拒绝，即 CM311 在线但该公钥未写入远端 `authorized_keys`。Agent shell 非交互，无法在密码提示处输入；本轮**未使用**文档中明文记录的账号/sudo 密码（§5 禁止索取、回显、记录人的密码）。结论：agent 具备 SSH 能力，但 CM311 免密登录未建立，是后续所有远端步骤的前置阻塞（交接清单 V17）。需人执行一次 `ssh-copy-id -i ~/.ssh/id_ed25519.pub billieguo@10.42.0.11`。另发现 `docs/REMOTE_MACHINE_USAGE.md` 明文保存密码且已入 Git 历史，建议轮换并移出仓库。本轮未成功执行任何远端命令，未启动 USB/HDMI/无线链路。
21. **2026-11-09 12:20-12:21 HKT V17 复测 + PC 侧 V16 opt-in 硬解路径（未提交）**：SSH `BatchMode=yes` 复测仍 **RC=255**，免密未建立，远端步骤仍被 V17 阻塞。PC 侧审查发现 `config.py` 白名单把 `decoder.codec` 限死为 `hevc/h265`，而 `HevcDecoder._new_context()` 本就按 `config.codec` 创建 PyAV context；PC `rm` 环境 PyAV 17.1.0 暴露 `hevc_v4l2m2m`。最小改动：白名单加入 `hevc_v4l2m2m`（默认仍 `hevc`，opt-in）；`_new_context` 末尾记录 `requested/actual` codec 身份证据，`snapshot()` 增加 `codec` 键；新增 4 项测试。验证：本地 54 项测试 RC=0（3.191 s，无跳过）；golden 离线 replay 默认配置 RC=0、105 帧、0 错误（软解基线无退化）；v4l2m2m 配置在 PC 上 RC=1、0 帧、`avcodec_open2` EINVAL（PC 无 V4L2 设备）、错误/reset 状态机正常收尾——这是负面对照，**不是硬解验收**。证据 `.codex_tmp/v16_pc_optin_20261109_122037/`（含 SHA256 清单）。风险：CM311 PyAV 11.0.0 是否暴露 `hevc_v4l2m2m` 未验证；PyAV 链接自带 FFmpeg 而非 `~/ffmpeg-6.1.1-v4l2` 补丁构建，Copy-Out/refcount workaround 不适用，动态分辨率切换可能挂起；备选为对自定义库重建 PyAV 或 FFmpeg 子进程后端。本轮未修改 CM311 文件，未启动 USB/HDMI/无线链路；本地改动未提交 Git。
22. **2026-11-09 13:29-13:41 HKT CM311 V16 硬解实测（用户授权 askpass）**：用户明确指示使用 `REMOTE_MACHINE_USAGE.md` 的 askpass 模式（本窗口内放宽 §5 的保守解释）；密码运行时从文档提取到环境变量、未回显，helper 不含凭据。CM311 只读盘点：设备空闲，**PyAV 11.0.0 暴露 `hevc_v4l2m2m`=True**；远端 `config.py` SHA256 `062b4ccc...` 与本地 HEAD 一致。全部测试以 stdin 脚本 + 双层 `timeout` + 独立 `.codex_tmp` 输出目录执行，**未改远端工作树任何文件**。结果：raw clean 样本 PyAV SW/HW 各 30 帧 RC=0，YUV MD5 **29/30**（仅末帧异），与 2026-11-08 自定义 CLI 证据交叉一致（SW 30/30、HW 29/30 相同，末帧哈希不同）；全管线 golden replay（直接赋值 `decoder.codec` 绕过远端旧白名单）：SW 105 帧 0 错误，HW 80 帧、**EIO×3→reset→IRAP 重同步，分辨率切换丢 25 帧（1832 段尾部），自动恢复无挂起**，两次运行计数完全一致；YUV 层对照 **1832 段 8/8、1920 段 71/72 逐位一致**（仅末帧异）。BGR 层哈希全异是 swscale NV12→BGR vs YUV420P→BGR 转换伪影（均值 0.44/255，统一 yuv420p 后 MD5 相同）——**验收必须比 YUV 层**。另观察：源切换中止后首次重新打开设备可能瞬态 `capture POLLERR`→EIO，数分钟后新打开恢复正常（无需 R3）。4 个证据目录 30 文件本地/远端 SHA256 清单全匹配（`.codex_tmp/manifests_20261109/`）；13:41 收尾设备空闲。未启动 USB/HDMI/无线链路，未 reboot/重载模块/装包，未 commit（用户指示）。待决策：源切换丢帧缓解方案（容忍 IRAP 间隙 / 对补丁 FFmpeg 重建 PyAV / FFmpeg 子进程后端）。
23. **2026-11-09 13:59 HKT 方案 2 构建侦察 + 用户 IRAP 观察**：用户据先前硬件使用经验指出**无线 VT 链路似乎仅在建链时发一个 IRAP，无周期 IRAP**（待实时证实）——若属实，流中 reset 后等 IRAP 可能永久冻结，Copy-Out 根因修复成为关键路径；实时烟测须测 IRAP 节奏。CM311 只读侦察：自定义 FFmpeg 为静态构建（`CONFIG_STATIC=yes`/`CONFIG_PIC=yes`，`install/lib` 无 .so）；PyAV 11.0.0 是系统 apt 包、链接系统未补丁 `libavcodec.so.60`；gcc 13.3/pkg-config/venv 齐全，Cython 缺（可装 venv），PyPI 可达，磁盘 106G/可用 RAM 1.3Gi。方案 2 总计划已给出待 GO：A) out-of-tree 共享库重建至新前缀 `install-shared`（原二进制不动）+ clean 回归；B) `--system-site-packages` venv 内构建 PyAV 11.0.0（PKG_CONFIG_PATH+rpath 指向新库）；C) venv 重跑 raw/全管线 YUV 对照，验收源切换丢帧 25→≈1、无挂起、2 次复现；D) 后续 R2 同步 opt-in 配置与实时烟测。每阶段回退=删除新目录/venv，系统与已验证二进制零改动。尚未开始构建。
24. **2026-11-09 14:06-14:15 HKT 备份 + Phase A 启动（用户指示：不 commit、先备份、需要实时硬件时通知）**：备份绝对路径 **`/home/billieguo/billie_guo/src/rm/mobile_vt/.codex_tmp/backup_before_plan2_20261109_140638`**（清单 `BACKUP_MANIFEST.md`；FFmpeg 源码 tar+patch+HEAD、CM311 `vt13_video/tests/config` tar、PC 未提交改动 tar+patch；`sha256sum -c` 全 OK；远端镜像 `~/mobile_vt/.codex_tmp/backup_plan2_20261109_140638`）。out-of-tree configure 因原树存在 `config.h` 被拒（RC=1，原树未动）；改用 `git archive HEAD` 展开至新目录 `~/ffmpeg-6.1.1-v4l2-shared` + 应用备份 patch，3 个补丁文件 SHA256 与原树逐一相同，in-tree `--enable-shared --disable-static --prefix=.../ffmpeg-6.1.1-v4l2-shared/install` configure RC=0；`make -j2` nohup 运行中（PID 46044，`timeout -k 60 2400`），日志 `~/mobile_vt/.codex_tmp/plan2_build_20261109_140638/`。Phase B 脚本已备好（venv `~/mobile_vt/.venv-v4l2`，系统 Python 不动）。尚未改写任何源码文件，未 commit，未启动实时链路。
25. **2026-11-09 15:27-15:55 HKT 方案 2 A/B 完成 + Phase C 根因修正**：Phase A 续建（首次 -j2 超 40 分钟 RC=124，-j3 续编 RC=0）+ install RC=0，新共享二进制 clean 回归 30 帧 29/30（补丁生效）；Phase B v3 RC=0（v1 卡 pip 隔离环境 keyring、v2 环境变量顺序 bug，均已修复记录），venv PyAV 11.0.0 的 ldd 确证链接自定义 `libavcodec.so.60`（rpath），系统环境零改动。**Phase C 关键修正**：venv 全管线 golden 仍 80 帧/EIO×3/reset（与未补丁完全一致）；无间隙对照×2 同样结果（间隙假说被证伪）；dmesg 实证真因是 **golden POC8 触发 `HEVC_LCU_CHECK status=0xf`→`Aborting decoding session!`**（与 POC21/POC50 同族的 P0 固件问题，6 次运行确定性复现）——**不是源切换、不是引用计数，Copy-Out 无法修复**；此前"丢帧=源切换"归因错误。reset 后从 1920 IRAP 新上下文恢复，动态 reinit 路径实际未被测到（需干净合成切换流隔离验证）。5 个证据目录 44 文件本地/远端清单全匹配；dmesg 全文 `plan2_build_20261109_140638/dmesg_phase_c.txt`。未改写任何现有源码，未 commit，未启动实时链路。待决策：P0 `0xf` 驱动/固件根因调查；合成切换流验证 Copy-Out；Phase D 实时烟测（R2，需接 USB 接收器，测 IRAP 节奏与实时内容是否触发 0xf）——已通知用户需要真实硬件。
26. **2026-11-09 16:12-16:20 HKT Phase D 首次实时烟测（R2 已批准并执行）**：接收器枚举 doctor RC=0；launcher `live_capture_verified.sh` 验证就位（V15）；config.py 经 staging 哈希校验同步（`062b4ccc→3bf1229e`，唯一工作树写入，有备份回退）。90 秒 headless 实测（venv PyAV + 补丁共享库，`hevc_v4l2m2m`）：**43 帧正确解码、0 corrupt、有界干净退出、无 SSH 丢失**；**IRAP 仅建链/重建链时发送（90 秒 3 个，用户观察被实时证实）**；**实时内容在 POC24 触发 `status=0xf`**（dmesg `idx=910 total=1914 over=1`→Aborting）→EIO×3→reset→**无后续 IRAP→冻结约 35 秒至运行结束**（预言的 IRAP 饥饿失效模式成立）；USB 层 117 次 stall 恢复（全成功）+129 次不连续+33.3 秒读间隙（无线/USB 归因未证实，模式指向无线掉链）；2160 AU 跳过 2108（97.6%，多为 reset 后等 IRAP）。证据 `~/mobile_vt/captures/manual_live/20261109_161254`（raw 41,592,763 B SHA256 `beb6057b...` 本地一致）+ 本地 `.codex_tmp/live_smoke_20261109_161254/` + dmesg。**P0 恢复架构矛盾实证**：stall/错误→WAIT_IDR，但链路无周期 IRAP→任何流中 reset 即冻结至重建链。未 reboot/重载模块/停服务，未 commit。下一步：离线分析本次 raw 捕获（POC24 复现、恢复策略对照）；稳定链路吞吐实测；HDMI 仍为后续 R2。
27. **2026-11-09 16:30-16:55 HKT 实录取证：上游流损伤 + 1080p60 模式切换**：对 41.6MB 实录做 PC 取证 + CM311 权威 trace_headers（TRACE_RC=0）。时间线：0–10s 稀疏 1832×1032@30 → **33.3 秒零数据**（LED 仍常亮，用户无其他断链判据）→ 43–54s 稀疏恢复 → **t=53.8s 发射端切到 1920×1080@60**（IRAP#3 携带新 VPS/SPS，trace 确证分辨率/时基变化；PPS 全程相同）→ 54–90s 满速率 ~600 VCL/10s。流完整性：软解带 OUTPUT_CORRUPT 得 **2161 帧=65 干净+2096 corrupt（97%）**，每 IRAP 段仅 22/24/19 帧干净；seg3 POC 1–16 连续后**不规则跳变（~+30 夹杂 +1 段）**，与健康 60fps 流不符——**损伤来自上游（无线严重突发丢包/切片头比特错误/发射端 1080p60 模式异常，待隔离），CM311 解码器反应正确**。修正前述两处误判：①"SPS 三段相同"系 NAL 类型标号错（VPS=32/SPS=33/PPS=34，6 字节的是 PPS 属正常），seg3 的 VPS/SPS 实际已变；②"0xf 后丢弃 35 秒健康视频"错误——该视频 97% corrupt。用户信息：建链约 10 秒、LED 常亮、无主动 IDR 请求手段。证据 `.codex_tmp/live_smoke_forensics_20261109_163037/` + CM311 `plan2_build_20261109_140638/segment{1,3}_vps.trace.log`。未 commit，无新工作树写入。**下一步需人/硬件**：近距离理想射频烟测隔离 RF vs 模式；如可配置锁定 1832×1032@30 复测；确认 DJI 输出模式如何选择（自动/App/眼镜）。
28. **2026-11-09 17:02-17:12 HKT 实时 run 2 + RF 归因解决 + 参数集缓存缓解验证**：第二次 R2 烟测（用户批准并手动断链一次）：4 个 IRAP，**前两个重建链 IRAP 不携带 VPS/SPS/PPS**→管线无法起解（健康流被弃）；26.3s 用户断链间隙 + 11s 模式切换间隙（1080p60→1832×1032@30）；124 次 stall 恢复；最终 22 帧。**离线 bootstrap 判定**：用 run1 哈希相同的 1080p60 参数集前置解码 run2 的 1080p60 段——**segB 497/498 干净（99.8%）、segA 34/35**；1832 段 trace POC 1–21 连续；run2 时段 dmesg **无新 0xf**。**结论：run1 的 97% 损伤是射频环境问题，1080p60 模式与解码器在好链路下输出干净**（run2 实际距离待用户确认）。**参数集缓存缓解已验证**：`--parameter-sets-file`  priming 后无间隙硬解 replay 从首个 IRAP 起解 222+ 帧、0 错误（120s 超时未到 EOF）。**新性能问题（V11）**：CM311 Python 管线端到端仅 ~2–4 fps（裸 codec 17–24 fps），疑似逐 AU 串行 v4l2m2m 往返 + Copy-Out 拷贝 + bgr24 转换开销，30–50fps 目标前必须 profiling。另：快速 POC 读取器曾出错，以 trace_headers 权威结果为准。证据 `.codex_tmp/live_smoke_20261109_170226/`（raw SHA256 `624a0f93...` 本地一致）+ forensics 目录。未 commit。下一步：用户确认距离与模式锁定方法；带参数缓存的 live run 3（R2）；管线吞吐 profiling（离线）；HDMI 后续 R2。
29. **2026-11-09 17:20-17:30 HKT 实时 run 3（priming）：缓解验证成功，RF 损伤仍在**：launcher 升级（`c565cc22...`，DJI_PARAMS_FILE priming + --save-parameter-sets；priming 文件哈希 `f9f019a1...` 与项目 live_runs/vt13_params.h265 相同）。用户 READY 后及流中各断链一次。**Priming 验证成功**：4 个 IRAP 全部立即起解（keyframe_starts=4），无参数集缺失卡死；帧数 22→70、corrupt 0、1920×1080；params_latest.h265 自动保存。**但 RF 损伤持续**：32.7s 建链前间隙、数据 0.5s 周期突发、123 stall、驱动 POC 跳变 46→110→205→235→269（丢帧）、**POC269 触发 0xf 中止**（idx=1078/2040）、周期性 output POLLERR→12 解码错误。**恢复策略仍破坏性**：127 reset（123 stall+4 错误）、709 AU 跳过 615（87%）——IRAP 仅建链发送下 stall→WAIT_IDR 策略丢弃大部分视频，需重新设计（不 reset 续解/容忍隐藏）。距离/遮挡仍未获用户确认。证据 `.codex_tmp/live_smoke_20261109_172018/`（raw `f263935b...`）+ dmesg_live_smoke3.txt。未 commit。按用户指示转入离线：吞吐隔离矩阵（codec×output_format）+ 恢复策略 replay 实验；后续实时运行前先确认 RF 布置。
30. **2026-11-09 17:30-17:55 HKT 离线吞吐 profiling：Python 串行路径是瓶颈**：隔离矩阵（30s 无间隙 replay）：v4l2m2m bgr24/gray ≈2.1–2.25fps，SW hevc ≈5.3–5.7fps，输出格式影响甚微。仪表 profiling：to_ndarray 实测 470ms/帧；cv2 monkeypatch 降至 31ms 但总耗时不变→转换非唯一限速点；并发现 22 帧是**假象**（无 priming 时 run2 前两个 IRAP 缺参数集，554/579 AU 被跳过，仅尾部 25 AU 可解）。微基准：自定义与 Ubuntu swscale 同慢（81/83ms，NEON 已启用但该转换无加速路径）；**cv2.cvtColor NV12→BGR 10.8ms（7.5×）**。真实稳态（segB_clean.h265 498 帧全可解 1080p60）：to_ndarray 路径 40s 超时且 --seconds 30 未及时退出（V09 族停止响应问题）；**cv2 路径 220 帧/30s=7.3fps**。瓶颈=逐 AU 串行 v4l2m2m 往返（~400ms/AU）+ Python 逐 chunk 开销；自定义 CLI 同分辨率 24fps→硬件能力足够，集成模式是天花板。30+fps 选项：(a) PyAV 批量喂包+异步 drain+cv2（工作量中等、上限不确定）；(b) FFmpeg 子进程后端（已验证 24fps 二进制+rawvideo 管道+cv2，路径更明确）；(c) 暂受低帧率。未改源码（全 monkeypatch/stdin），未 commit。待用户决策后端方向；恢复策略重设计、RF 布置确认、HDMI 仍开放。
31. **2026-11-09 17:46-18:12 HKT 方案 3 实现+部署+验证：33.3fps@1080p60 达标**：用户批准推荐方向 (b)。备份 #2 `/home/billieguo/billie_guo/src/rm/mobile_vt/.codex_tmp/backup_before_plan3_20261109_174637`。PC 实现 `vt13_video/ffmpeg_pipe.py`（FfmpegPipeDecoder，子类复用 HevcDecoder 门控/错误状态机）：ffmpeg 子进程硬解→nut/rawvideo 管道→PyAV demux 线程→cv2 转换；config 增 `backend/ffmpeg_path/ffmpeg_codec`（默认 pyav 不变）；pipeline 工厂选择。**关键 bug 修复**：CLI raw-hevc demuxer 设 extradata 后解码器忽略流中同 ID SPS 更新（CLI 停在 1832，PyAV 无 extradata 路径正确切 1920，同库对照证实）→后端检测 SPS 哈希变化即优雅重启子进程（drain≤5s），兼解 nut 动态头问题。PC 56/56 测试通过（含 golden 管道测试 105 帧 1832→1920）。R2 部署 CM311：staging 哈希链全验（pipeline 实验版仅合并工厂行，VT13_LOW_LATENCY_MS 标记保留，合并后 `62382e56`）。**R1 验证：segB_clean 1080p60 经 ffmpeg-pipe+自定义硬解 497 帧、33.32fps、0 错误、0 丢帧、干净退出**（旧路径 2–7.3fps）；golden 硬解 72 帧=1920 段，dmesg 确认预期 POC8 0xf（1832 段损于已知 P0），ffmpeg 容错+1920 IDR 自动 reinit 恢复；远端套件 54 项仅已知 V13 错误，新管道测试通过；收尾空闲。证据 `plan3_verify_20261109_180248` 本地/远端 4 文件哈希一致。未 commit。下一步可选：live run 4（R2，先确认 RF 布置）/HDMI 集成（R2）/恢复策略重设计/V13 小修/长时稳定性。
32. **2026-11-09 18:15-18:40 HKT HDMI 显示验证+NV12 显示槽集成部署**：显示栈盘点（V04）：HDMI-A-1 connected+enabled，meson-drm，Xorg :0/tty7（lightdm，billieguo 会话），HDMI 当前 1024×600@59.82；X 访问验证 RC=0；系统 cv2 headless 无 GUI→**ffplay 路径**。R2 显示测试：BGR→ffplay **用户亲眼确认 HDMI 动态视频**，但仅 5.4fps（ffplay BGR→SDL 转换瓶颈）；NV12 直传重测 **498 帧 25.13fps**。随后 PC 集成 NV12 显示槽进 ffmpeg-pipe 后端（reader 线程 cv2 转换前 tap NV12→ffplay；`decoder.display: ffplay`+display_width/height/ffplay_path；首帧懒启动、分辨率变更重启、失败优雅降级；_pack_nv12 去 stride padding 单测）；备份 #3 `backup_before_display_20261109_182449`；PC 59/59 通过（含无 DISPLAY 降级测试）。R2 部署 CM311（远端预备份 `backup_display_remote_20261109_183007`，4 文件哈希链全验，pipeline 不动）。**集成验证：segB replay+display=ffplay 491 帧、21.55fps、0 错误、display 活跃、0 丢帧、干净退出**（全管线开销较裸链 ~15%）；套件 57 项仅 V13；证据 `display_verify_20261109_183041` manifest 一致。用户流畅度确认待回。未 commit。下一步：live run 4（用户将确认 RF 信息）、恢复策略实验、长时稳定性。

33. **2026-11-09 19:05-19:18 HKT rm-receiver（Rust）离线评估：DUML I-frame 请求是缺失的恢复原语**：PC 只读/离线评估 `/home/billieguo/billie_guo/src/rm/rm-receiver`（HEAD `10e381b`，从官方客户端 12.0.0.213 逆向，同一 USB `2ca3:1020`）；PC 未接接收器、未访问 CM311、未启动实时链路。**构建**：HEAD 的 workspace 依赖 `rm-receiver` 未声明 `default-features = false`，而 CLI 覆盖该字段，`cargo test --workspace` 直接解析失败；在根 `Cargo.toml` 做一行修复（未提交）。用 conda `colmap` 的 FFmpeg 9.0.2 + `/usr/lib/llvm-14/lib` libclang + GCC-12 include 路径，workspace 37 项测试全过（proto 28、receiver 2、decode 3、doctest 1 等），clippy 0 警告，viewer 全量构建通过；系统 FFmpeg 4.4 太旧，不能开 `decode`。**码流等价性**：run-4 捕获（`raw_ep81.bin` SHA256 `b5b5339f...`）经 Rust `AccessUnitSplitter` 与 Python `AccessUnitAssembler` 均得 2147 AU / 2 IRAP AU / 1 个带 PS 的 AU，输出逐字节一致（41,417,070 B，SHA256 `ceef970e...`）；ffprobe 报 2148 packets / 2 keyframes；对 chunk 大小不变。run-3 捕获唯一差异是 Python 拒绝、Rust 保留的 5 字节非法伪 NAL（不影响解码）。**DUML**：真实 ttyACM0 捕获解码 1421 帧（431 非 Other）/552 帧、0 丢字节。**控制逻辑**：PTY 冒充 `--port`，`rmrx` 在控制口打开时精确发送 `55170438aa0e0000400101000000000024000000248f06`（DUML 1/1→14/0 request I-frame），并按 1 Hz 发送 pairing 查询 `550f04a2aa0e00004009550002e742`。**架构**：keyframe 门控、队列溢出请求 I-frame、viewer 解码错误→reset→请求 I-frame；但 FFmpeg 对缺参数集只打日志不返回 `DecodeError`（bootstrapped 段 0 帧；run-4 仅从 AU 2105 的带 PS IRAP 解出 42 帧），**参数集 priming 仍是必需，此 repo 不能替代**。**新探针** `.codex_tmp/rmrx_probe/vt_iframe_probe.py`（SHA256 `d4b5ab42...`，无第三方依赖）已 dry-run+PTY 3/3 精确复现；用于在 CM311 下一次实时运行中与现有管线并行（管线不占用 ttyACM0），验证发射端是否响应按需 I-frame。**这是 0xf 会话死亡 + IRAP 饥饿的候选修复，硬件效果未验证。** mobile_vt 无跟踪文件改动；rm-receiver 的一行修复未提交。下一步：CM311 实时测试（READY 后跑 `--repeat 12 --interval 5`，统计新 IRAP/`keyframe_starts` 与 dmesg 恢复）。

34. **2026-11-09 20:15-20:45 HKT 控制面 + 恢复架构集成（Python 工作管线），捕获层 A/B 备妥**：用户要求保持现有工作管线，只适配 rm-receiver 的控制面与恢复架构、测试抓取层、吸收认知收益。**备份** `.codex_tmp/backup_before_control_20261109_201531`（13 文件，SHA256 校验通过）。**新增** `vt13_video/control.py`（DUML v1 编解码、CRC-8/16、sysfs 按 interface 2 发现 ttyACM0、后台读写线程、断线重连；I-frame 请求帧与官方客户端逐字节一致；1 Hz pairing 查询；下行帧解码日志；无第三方依赖）。**配置**新增 `[control]`（enabled/port/iframe_on_connect/iframe_on_recovery/iframe_retry_s/min_iframe_interval_s/pairing_poll_s）与 `decoder.stall_restart_s`（默认 0=关闭）。**恢复集成**：连接时由 ControlLink 请求 I-frame；discontinuity/decoder reset/等待 keyframe 时管线按 2 s 重试；可选 watchdog 在 VCL AU 持续到达但 N 秒无解码输出时 reset decoder 并请求 I-frame（针对 0xf 静默会话死亡）。**测试**：新增 8 项 control（PTY + 真实 DUML 帧）、2 项 config、4 项 pipeline；全套 73/73 通过（7.36 s）。**回归**：golden replay + PTY control 仍 105 帧、1 次 on-connect 请求、4 次 pairing、watchdog 0，无退化。**抓取层 A/B**：用 rustup musl target + rust-lld 交叉编译出静态 aarch64 `rmrx`（3,281,112 B，SHA256 `b05a5fbe...`，`file`=ELF64 AArch64 statically linked）；staging 脚本 `capture_pyusb.py`/`timestamp_stdin.py`/`summarize_capture.py`/`live_capture_run5.sh`（bash -n 通过）；**未在 CM311 实机运行**（PC 无接收器，本会话未访问 CM311）。**认知收益**：EP 0x81 是裸 Annex-B（无私有视频封装）；IRAP 稀缺是设计使然（官方客户端按需请求）；ttyACM0=控制、ttyACM1=调试；README/架构已更新。**风险**：I-frame 硬件效果未验证；watchdog 在高损伤下可能误触发（默认关闭）；control 写失败为非致命；musl 二进制的 CM311 运行时未验证；未部署。**下一步**：CM311 run 5（control+watchdog），再跑捕获 A/B。

35. **2026-11-09 20:31-20:41 HKT 实时 run 5/6：I-frame 请求获硬件证实；控制面/显示恢复修复**：用户执行 run 5。**run5**（20:31:58-20:34:34，150 s）：设备空闲、接收器枚举、`ttyACM0` 可读写；VT 开启后 20:32:37 首 IRAP；**10/10 次 watchdog 请求后 37–162 ms 内出现 IRAP，发射端按需 I-frame 得到硬件证实**；同时 11 次 `HEVC_LCU_CHECK status=0xf`（POC5/7，1920×1080）→ decoder 静默死亡 → 5 s watchdog → 请求 → 恢复。每次 reset 都通过 `FfmpegPipeDecoder._terminate()` 关闭/重启 ffplay，造成用户可见的窗口反复关闭+卡顿；VT 关闭期间还产生 56 次请求 spam。run5：152 帧、10.8 fps、64 请求、12 IRAP、display starts 10、raw 99,967,789 B SHA256 `ee2f3b37...`。**修复**（PC 76/76 测试通过，远程 golden replay 105 帧）：`FfmpegPipeDecoder.reset()` 保留 ffplay、延迟 ffmpeg 启动到下一个可用 IRAP；`_request_iframe` 仅在数据流动时发送且 ≥2 s 节流；`_mark_discontinuity` 不再重置节流。**run6**（20:38:30-20:41:00，150 s，`DJI_STALL_RESTART_S=2.0`）：**display starts=1**（窗口不再关闭/重启）、565 帧、13.14 fps、34 次 watchdog、35 请求/34 IRAP、149 pairing、USB 0 errors/timeouts、raw 127,890,043 B SHA256 `ed1329e8...`；VT 已开时 on-connect 请求后 **0.2 s** 起解（旧建链等待 33–37 s）。**仍存在**：29 次 0xf（1080p），每轮解码数帧后死亡，用户仍见约 5 s 周期的 ~2 s 冻结；根因是 1080p 流的参考链/固件中止，非 I-frame 请求本身（run4 1832 模式仅 1 次 0xf/90 s）。**下一步 A/B**：用户锁定 1832×1032@30 后用同一 control+watchdog 复跑；若 0xf 大幅下降则确认模式，否则排查 requested-IDR 的 GOP 完整性。远程备份 `~/mobile_vt/.codex_tmp/backup_run5_20261109_203028/`、`backup_run6_20261109_203755/`；安装哈希 pipeline `a99d6a81...`、ffmpeg_pipe `756fe77e...`、control `cc0cbcdc...`、config `5b42c925...`；未 commit。

36. **2026-11-09 20:46-20:55 HKT 显示过滤 + 软件/硬件解码 A/B：软件解码在 CM311 不可用**：用户反馈 run5/6 “约 5 s 延迟、经常绿屏”。**显示修复**（已部署）：ffplay 改为异步 drop-oldest 显示队列（不再阻塞 nut 读取）、跳过 `is_corrupt`/全绿（Y≈0,U=V≈0）/全灰（Y≈128 且方差≈0）帧、ffplay 加 `-fflags nobuffer -flags low_delay -framedrop -probesize 32 -analyzeduration 0`；新增 `decoder.convert_bgr`（headless+ffplay 时可关，省 Python CPU）。**run7/10 硬件验证**：display starts=1（窗口不再关闭/重开），run7 90 s 357 帧/21 reset/19 次 0xf/green_dropped=22；run10 60 s 313 帧/14 reset/14 次 0xf/green_dropped=14/grey_dropped=0，画面不再闪绿/灰，但 0xf 期间冻结。**软件解码 A/B**：run8（`DJI_FFMPEG_CODEC=hevc`，90 s）1264 帧、0 0xf、0 reset、display starts=1，但 CPU ≈3 核（ffmpeg 144% + Python 131% + ffplay 29%），只读入 20.6 MB USB（≈1.8 Mbps，远低于 1080p60 流），大量 POC 缺失 → 软件错误隐藏输出整帧灰色；用户确认“大部分时间闪灰、几乎看不到真实画面”。run9 加 `convert_bgr=false` 后 Python CPU 降至 97%，1081 帧/60 s，仍 CPU 受限、USB 回压。**结论**：CM311 的 4×A53 无法实时软解 1080p60；软件路径不可用。**根因仍是 1080p 流的参考链损伤 + meson-vdec 0xf**；用户无法控制发射端分辨率。**下一步**：优先 RF/链路缓解（远离 USB3/HDMI/主机、USB2 延长线、重新配对/重启发射端、换信道），并离线对比 run10/run4 的 POC/缺失 AU，判定 0xf 是丢包驱动还是固件本身。部署哈希：config `93b3d6b5...`、pipeline `a14b3aa2...`、ffmpeg_pipe `8e6c4411...`、launcher `ae7f3f42...`；备份 `backup_run7/8/9/10_*`。未 commit。

37. **2026-11-09 20:58-21:04 HKT 硬件吞吐基准 + 内核中止快速恢复（run11）**：用户观察 htop：硬件解码 CPU 通常 <50%，软件解码接近 4 核；并回忆历史上有 >200 fps 的硬件解码。**基准**（CM311 离线）：30 帧 1832×1032 `clean_1832x1032.h265` 用 `hevc_v4l2m2m` → `-f null` 墙钟 1.04 s（≈29 fps，含启动）；498 帧 1080p60 `run2_segB_bootstrapped.h265` → `-f rawvideo -pix_fmt nv12 /dev/null` 498 帧/12.85 s=**38.7 fps**，utime 15.1 s；`-f null` 在 EOF drain 卡住（已知问题，120 s 后仅 474 帧），不能作为吞吐证据。**未复现 >200 fps**；该读数更可能是短样本 burst/progress 行、不同输出路径或误读，不是端到端速率。**新恢复**：`recovery.kernel_abort_watch`（journalctl -k -f 监听 `HEVC_LCU_CHECK status=0xf`/`Aborting decoding session`，命中后立即 reset+请求 I-frame，无需等 watchdog）；run11 60 s：33 次 kernel abort、**0 次 watchdog**、恢复延迟中位数 **116 ms**（60–303 ms）、34 IRAP、166 帧、USB 49.5 MB/0 errors。**关键发现**：快速恢复把死亡时间从 2 s 降到 0.1 s，但 abort 率从 run10 的 14/60 s 升到 33/60 s，帧数反而下降；每个 requested IDR 后约数帧即 0xf（run4 无请求时仅 1 次/90 s）→ **请求 IDR 与 0xf 强相关，可能是大 IDR 突发加剧弱链路丢包或 requested GOP 本身不完整**。**下一步**：无请求对照（control.iframe_on_recovery=false）测自然 0xf 率；RF 缓解（远离 USB3/HDMI、USB2 延长线、重新配对/重启发射端）；离线 POC 对比 requested-IDR 后的缺失 AU。部署哈希：config `f47c7d9b...`、pipeline `c700b8cd...`、launcher `673dd0f8...`；备份 `backup_run11_*`。未 commit。

38. **2026-11-09 21:09-21:19 HKT 210 fps 根因与 release 重建**：用户提供 2026-11-05 02:56 的原始命令与日志 `~/vdec_hevc_hw_test.log`：同一 20 MB `idr_test/vt13_idr_02.h265`，**1127 帧、fps 210–222、0 解码错误**。当前同一命令：自定义 `~/ffmpeg-6.1.1-v4l2/ffmpeg` 与 shared 构建均为 **`--enable-debug=2`**，仅 **45 fps**（891 帧/20 s）；系统 `/usr/bin/ffmpeg`（release 6.1.1）**1127 帧/5.1 s = 221 fps**。**结论：210 fps 是真实离线吞吐，不是测量错误；自定义 debug + 诊断构建是回归。** 但系统 release 二进制**不能直接用于 live**：run12（`DJI_FFMPEG_PATH=/usr/bin/ffmpeg`）在首次 kernel `0xf` 后持续 `output POLLERR` + `Error submitting packet to decoder: EIO`，60 s 仅 7 帧、28 次 reset；用户看到“只有起始一帧然后冻结”。自定义 patched 构建能恢复但只有 45 fps。**修复中**：从 patched 源码复制 `~/ffmpeg-6.1.1-release`，`--disable-debug`、只保留 hevc_v4l2m2m/hevc、hevc demuxer/parser、nut/rawvideo/null、pipe/file；configure RC=0，`make -j2 ffmpeg` PID 104978 后台构建，日志 `~/ffmpeg-6.1.1-release/buildlog/build.log`。预期 release patched 同时获得 ~200 fps 与 live 恢复；构建后先在 20 MB 文件 benchmark，再以独立二进制 + `DJI_FFMPEG_PATH` 做 live 测试。**注意**：系统 `/usr/bin/ffmpeg` 仅用于离线基准，不可作 live 路径；当前 launcher 默认仍是可工作的 custom 二进制。CPU 低是 VDEC 卸载的正常现象；debug 构建的低吞吐造成回压/参考链丢失，可能放大 `0xf`（系统 release 在 POLLERR 前 25 s 仅 1 次 abort，支持该假设）。0xf/链路仍是首要问题。未 commit。

39. **2026-11-09 21:25-21:38 HKT release patched 构建 + Copy-Out 权衡（run13）**：release patched FFmpeg 构建完成（`~/ffmpeg-6.1.1-release/ffmpeg`，含 Copy-Out 时 45 fps；新增 `FFMPEG_V4L2_NO_COPY=1` 运行开关跳过 Copy-Out 后 **1127 帧/4.516 s=249 fps**，与系统 221 fps 同级）。**但 no-copy 不能 live**：run13（release no-copy + kernel watcher + 2 s watchdog，60 s）219 帧、34 次 kernel abort、**1503 次 output POLLERR**、0 watchdog；每次 requested IDR 后约 6 帧即 0xf，随后 POLLERR，无法恢复。Copy-Out 是 live 恢复的必要代价（per-frame alloc/copy 使 249→45 fps）；即使 249 fps，live 仍被 0xf/requested IDR/链路限制，吞吐不是首要瓶颈。**结论**：210 fps 是真实离线 no-copy 吞吐，但与 live 流畅度无关；当前 1080p60 流每个 requested IDR 仅约 6 帧可解，必须解决 0xf/链路（RF/1832/P0），而非继续优化解码吞吐。工作 live 路径仍是 Copy-Out 构建（release copy 或 custom）；release copy 无需 debug 日志，可作默认候选。部署：release binary SHA256 `1ed2b711...`（含 env 开关），Copy-Out 模式 45 fps，no-copy 模式 249 fps。未 commit。

40. **2026-11-09 21:45-21:46 HKT release Copy-Out 同链路 A/B（run14）**：用户要求对比 release Copy-Out。run14（`dji_20261109_214510`）：`ffmpeg_path=$HOME/ffmpeg-6.1.1-release/ffmpeg`、**未设置** `FFMPEG_V4L2_NO_COPY`（`tmux show-environment` 与 `/proc/PID/environ` 均无该变量，确认 Copy-Out 生效）、`stall_restart_s=2.0`、`kernel_abort_watch=true`、`convert_bgr=false`、ffplay 1024×576、60 s。结果：**258 帧/60 s、31 次 kernel abort、1507 次 `output POLLERR`、0 watchdog reset、USB 47.1 MB/0 errors**。Copy-Out 能恢复并出帧，但**不消除 POLLERR**，画面仍受 0xf 周期限制（每次 requested IDR 约 6–8 帧）；run13 no-copy 219 帧 vs run14 copy 258 帧，差异不改变“0xf/链路是主限速”的结论。release Copy-Out 无 debug 日志、行为与 custom debug 同级，可作 live 候选（`DJI_FFMPEG_PATH` 指定），launcher 默认暂保持 custom。未 commit。

41. **2026-11-09 21:48-21:50 HKT 部分绿屏过滤（run15）**：用户反馈 run14 有“下半屏绿色闪烁”。原因是 0xf/POLLERR 后 Copy-Out 复制了**部分写入**的帧（下半 Y=0/U=V=0），旧的全帧绿色检测（整帧均值）漏掉。**修复**：`_looks_like_partial_green` 按 8 像素采样，若 Y<4 与 UV<4 的像素比例均 >20% 则丢弃该帧（保留上一张完整帧）；新增 `display_partial_green_dropped` 计数；全帧绿色/灰色检测保留。PC 81/81 测试通过。run15（`dji_20261109_214849`，21:48:49-21:49:58）：release Copy-Out（无 `FFMPEG_V4L2_NO_COPY`）、stall_restart=2.0、kernel watch、convert_bgr=false、ffplay；结果 **195 帧、33 次 abort、1582 次 POLLERR、display_green_dropped=23、display_partial_green_dropped=13、0 watchdog**；绿色闪烁已被过滤，但 0xf/POLLERR 冻结仍在。部署 ffmpeg_pipe `2d99b0a0...`；备份 `backup_run15_*`。未 commit。

42. **2026-11-09 22:00-22:01 HKT 无恢复请求对照（run17）：请求不是 0xf 的触发因素**：用户重新打开 VT 链路后执行 `iframe_on_recovery=false`、`iframe_on_connect=true`、`stall_restart_s=0`、release Copy-Out、kernel watch、60 s。结果：**仅 1 次 I-frame 请求，30 次 kernel abort，31 个 IRAP，273 帧，USB 45.2 MB/0 errors/0 timeouts**。无恢复请求时 abort 率（30/60 s）与有请求时（run15 33/60 s、run14 31/60 s）**相同** → **requested IDR 不是 0xf 的触发因素**；此前“请求 IDR 与 0xf 强相关”的假设被证伪/修正。源码在该状态下主动发送约每 2 s 一个 IRAP（31 个/60 s），但每个 IRAP 的 GOP 仍在数帧后触发 0xf；根因是 **1080p 流/链路损伤 + meson-vdec 固件 abort**。I-frame 请求仍是有用的快速恢复/启动手段，但不改变 abort 率。下一步：RF/链路（run2 在 1.5 m 有遮挡时 1080p60 仍 497/498 干净，当前 0.5 m 状态反而更差）、1832 模式、P0 固件/驱动。run17 设置：`DJI_IFRAME_ON_RECOVERY=false DJI_IFRAME_ON_CONNECT=true DJI_STALL_RESTART_S=0 DJI_FFMPEG_PATH=~/ffmpeg-6.1.1-release/ffmpeg DJI_CONVERT_BGR=false DJI_KERNEL_ABORT_WATCH=true`。未 commit。

43. **2026-11-09 22:00-22:05 HKT 分辨率切换重复 ffplay 窗口修复**：用户发现“两个显示窗口”。run17 日志确证：22:00:47 启动 1832×1032，22:00:49 启动 1920×1080，共 2 次 `ffplay display started`。原因：`_ensure_display` 在分辨率变化时只处理“尺寸相同且进程已死”的情况，尺寸不同会**直接 spawn 新 ffplay 而不关闭旧的**，旧窗口残留。**修复**：`_ensure_display` 在尺寸不同或旧进程已退出时先 `_close_display()`；`_close_display` 增加 `ffplay display closed` 日志。PC 81/81 测试通过；run18（`dji_20261109_220409`，45 s，1920 单分辨率）只有 1 次 start + 1 次 close，退出后无 ffplay 进程；`pgrep -fc ffplay` 的 2 是 tmux 命令行含 `DJI_DISPLAY=ffplay` 的假阳性。部署 ffmpeg_pipe `871af9b2...`；备份 `backup_run18_*`。未 commit。

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
- IRAP 饥饿的恢复路径：官方客户端 DUML 1/1→14/0 `request I-frame` 已离线验证并集成进 Python 管线（`control.enabled`）。**2026-11-09 run5 硬件证实：10/10 次请求后 37–162 ms 内出现 IRAP；VT 已开时 on-connect 请求 0.2 s 起解**。0xf 后已可不依赖链路重连恢复；剩余问题是 1080p 模式下 0xf 过于频繁（V20）。
- 实际无线图传链路与 CM311 HDMI 的持续低延迟端到端运行和恢复。

**P1 — 正确性/健壮性**

- 动态分辨率切换时丢一帧；EOF drain/flush 可挂起或断言中止，`zeros1024` 末帧内容/哈希仍不稳定；Copy-Out 成本/替代方案；引用计数补丁验证。
- 真实场景长时间负载、CPU/内存/温度、音视频帧调度（当前项目以视频为主）；断链重连后软件和硬件状态机恢复。
- 从 HEVC 原始数据到 HDMI 显示的时间戳、队列深度、丢帧策略及量化延迟测量。

单次 `status=0x8`、`RC=0`、POC 改写或补零均不能视为 P0 已解决。

测试套件 `RC=0` 只证明 Python 回归基线通过；它不等于 `hevc_v4l2m2m`
实机硬解成功，也不能替代帧内容一致性检查。硬解目标应优先用 CM311
离线 golden HEVC 解码证据（交接清单 V07/V08）推进。

### 3.4 待验证清单（Validation Needed）

以下项目在本基线中不能当作已验证；下一轮应先补齐证据，再推进高风险改动：

| 项目 | 当前状态 | 需要验证的证据 |
|---|---|---|
| 本地/远端代码一致性 | 用户确认：CM311 为最新实验代码，PC 为可用软解基线；2026-11-06 SHA256 对比为本地 24、远端 27；远端多 `config/vt13_video.no_status.yaml`、`config/vt13_video.yuvtest.yaml`、`vt13_video/async_usb.py`；`README.md`、`vt13_video/decoder.py`、`vt13_video/pipeline.py` 不同；远端 `.git` 仍无效；内核/FFmpeg 有未提交修改 | 逐文件审查/合并；记录 commit/diff/SHA256；两侧复测 |
| CM311 最新实验代码测试兼容性 | 远端 50 项中 49 通过；`test_allow_corrupt_frames_controls_pyav_output_flag` 因 PyAV 11.0.0 仅暴露 `Flags.OUTPUT_CORRUPT`、测试访问小写 `output_corrupt` 而报错 | 修复测试兼容性，或固定 PyAV 版本；重跑完整测试并记录 RC |
| CM311 最新捕获指针 | 2026-11-06 只读盘点时 `/tmp/dji_test_latest_dir` 不存在 | 指针存在且指向预期 capture root；不要猜测 |
| CM311 当前运行进程 | 2026-11-09 13:41 HKT 收尾检查：无 `vt13_video`/`ffmpeg` 进程，`/dev/video0` 无 opener，源码 `meson_vdec` refcount=0；USB `2ca3:1020` 仍未枚举 | `ps`/`fuser` 证据；确认无冲突占用；实时运行前重查 |
| USB 接收器枚举 | 2026-11-08 19:54 HKT `doctor` RC=1；`lsusb` 无 `2ca3:1020`；当前仅有 root hub 与 `23a9:ef18` SG Flash | 连接接收器后 `doctor` RC=0；`lsusb -d 2ca3:1020` 可见；usbfs 可访问 |
| 显示技术栈 | 部分核实：`/dev/dri` 有 `card0`/`card1`/`renderD128`；SSH 环境 `DISPLAY`/`WAYLAND_DISPLAY` 为空；`loginctl` 有 active `seat0`/`tty7`；实际 HDMI 输出未验证 | 实际 HDMI 输出证据；确认 DRM/KMS、fbdev 或其他显示路径 |
| `vt13_video` 入口与 READY | `--help` 与 `stream --help` 均 RC=0；确认 `--headless`/`--seconds`/`--record`/`--json-stats`；源码无字面 `READY`，以 `USB source open` 后 `waiting_*` 状态为判据；尚未跑 stream | 真实 `stream` 命令、READY 证据、退出方式 |
| golden capture | 本地与 CM311 的 `captures/cold_start/bulk_if0_ep81.bin` SHA256 已核对一致 | 记录大小、SHA256、来源路径；离线解码结果 |
| FFmpeg 硬解 | R3 已加载源码模块，V4L2 已枚举 HEVC；2026-11-08 `-fps_mode passthrough`：clean 30 帧 RC=0、29/30；`no_sei` POC21 `0xf` RC=134（14 帧前缀全匹配）；`fresh_45_to_82` POC50 `0xf` RC=134（32 帧前缀全匹配）；`pad_1024` 38 帧 RC=0、36/38；EOF `aud` 3 次重复均 RC=137/19 帧且逐帧相同（跨窗口曾见 22/18/19）、`eos` 20 帧 RC=134、`zeros` 27 帧 26/27。20:25-20:31 基准：clean HW 30 帧/1.212 s、SW 30 帧/1.621 s；pad 1920×1080 HW 38 帧/1.585 s、SW 38 帧/2.295 s；短样本非稳态 | 解释/修复 EOF drain 与 `0xf`；说明 `aud` 超时前帧数跨窗口差异；继续覆盖真实样本；做长时/实时 FPS、CPU、RSS、温度与延迟测量 |
| 内核模块/VDEC | R3 已卸载 stock 并加载源码 `meson_vdec`（SHA256 `ca46...`）；HEVC 已注册；2026-11-08 dmesg 已见 `status=0x8` 与 `status=0xf`：`no_sei` POC21、`fresh` POC50 触发 `0xf`；`pad` 仅见 `0x8` 且两次缺失参考替代 | `uname -r`、模块 vermagic、dmesg、`status=0x8/0xf`；解释 EOF 状态机 |
| Source Change / POC50 / EOF | 2026-11-08 扩展矩阵确认：三份 EOF SW 27 帧仍一致；HW `aud`/`eos` drain 失败，`zeros` 26/27；`pad_1024` 虽 RC=0 但 36/38，首差异 index 36；`aud` 同一窗口 3 次均为 19 帧且相同，但跨窗口帧数为 22/18/19 | 解释 EOF drain/flush 状态机与超时窗口；验证 `0xf` 根因与 padding 内容差异 |
| 实时管线硬解集成 | **CM311 已验证 PyAV 原生路径（2026-11-09，item 22/25）**：PyAV 11.0.0 暴露 `hevc_v4l2m2m`；raw clean 29/30；补丁共享库 + venv PyAV 已构建并 ldd 确证（方案 2 A/B 完成）。全管线 golden 丢 25 帧的真因经 dmesg 修正为 **POC8 `status=0xf` 固件中止（P0 族）**，非源切换/引用计数，Copy-Out 不能修复；YUV 层已输出帧内容正确（1832 8/8、1920 71/72）；BGR 哈希差异为 swscale 伪影，验收须比 YUV | P0 `0xf` 根因调查（驱动/固件）；干净合成切换流隔离验证 Copy-Out reinit；长时 FPS/CPU/RSS/温度/延迟；Phase D 实时烟测测 IRAP 节奏（R2） |
| 实时无线链路 | 2026-11-09 run 4 已跑通（0.5 m，110 帧、17.52 fps 均值、0 管线错误，0xf 被 ffmpeg CLI 吸收但同会话仍吞掉 ~2000 AU 直到重连 IRAP）；USB 接收器当前不在 PC，CM311 未在本会话访问 | 继续按 §6 人机交接；READY 后由人开图传 |
| 按需 IRAP（DUML I-frame 请求，V18） | **2026-11-09 硬件证实**：run5 10/10 次 watchdog 请求后 **37–162 ms** 内出现 IRAP；run6 35 请求/34 IRAP；VT 已开时 on-connect 请求 **0.2 s** 起解（旧建链等待 33–37 s）。已集成进管线并默认用于恢复 | 已完成；后续只需在 1832 模式下复验同样的请求延迟 |
| 抓取层 A/B（PyUSB vs `rmrx dump`，V19） | 2026-11-09：静态 aarch64 `rmrx` 已构建（SHA256 `b05a5fbe...`），录制/时间戳/汇总脚本已备；PC 无接收器，**未实机运行** | CM311 同一链路顺序各跑 60 s，比较 bytes/AU、gaps≥500 ms、CPU/RSS、dmesg stall；确认 nusb 在 aarch64 正常 |
| 1080p 0xf 频率（V20） | run5 11 次/107 s、run6 29 次/150 s、run7 19 次/90 s、run10 14 次/60 s，均在 1920×1080；POC5/7、missing reference。run4 1832×1032 仅 1 次/90 s。显示/请求已修复，0xf 仍造成冻结 | 用户无法控分辨率；优先 RF/链路缓解，并离线对比 run10/run4 的 POC/缺失 AU，判定丢包 vs 固件 |
| 软件解码可行性（V21） | run8/9：0 0xf、0 reset，但 CPU ≈3 核、只读入 1.8–2 Mbps、POC 缺失导致软件错误隐藏整帧灰色；用户确认不可看。`convert_bgr=false` 仅小幅改善 | 不可用；除非源降到 1832/更低码率或换更强 SoC。保留为诊断对照，不作生产路径 |
| 请求 IDR 与 0xf 的关系（V22） | run11 快速恢复 116 ms，但 33 次 abort/60 s、166 帧；run4 无请求仅 1 次/90 s。每个 requested IDR 后数帧即 0xf，疑似大 IDR 突发加剧弱链路丢包或 requested GOP 不完整 | 无请求对照（关闭 iframe_on_recovery）测自然 abort 率；离线 POC/缺失 AU 对比 requested-IDR 后序列；RF 缓解后复测 |
| 性能/延迟目标 | 30–50 FPS、约 1024×576 仍是待确认目标；短样本基准硬件约 24 fps wall，软件约 16–18 fps wall；非稳态 | 用户确认 + CM311 长时实测 CPU/RSS/温度/延迟与画面质量 |
| Agent 免密 SSH（V17） | **2026-11-09 ~13:29 HKT 经用户授权 askpass 解锁**（本窗口）：密码运行时从文档提取、未回显；12:03/12:20/12:26 三次 `BatchMode=yes` 探测均 RC=255，公钥仍未安装 | 卫生建议：人执行一次 `ssh-copy-id -i ~/.ssh/id_ed25519.pub billieguo@10.42.0.11` 并轮换明文密码；askpass 授权仅限本测试窗口，后续会话需重新确认 |

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

默认授权只读、PC/CM311 的离线测试与分析、PC 沙盒文件和非破坏性离线计算。风险不明的远端操作须先询问。

| 等级 | 示例 | 执行规则 |
|---|---|---|
| **R0 只读** | `ls`、`cat`、`uname`、`git status`、读源码/已有日志、`ffprobe`、读取 sysfs | 可直接执行；注意不要触发设备占用 |
| **R1 离线测试/分析（无需批准）** | PC/CM311 的离线软件或硬件解码、FFmpeg/V4L2 短测、只读分析脚本、在独立测试目录产生日志；前提是 `/dev/video0` 等目标设备无其他占用 | 可直接执行；执行前只读检查设备空闲，限制磁盘、CPU 与 `timeout`；输出到独立目录，不覆盖原始捕获/golden；记录命令、RC、证据路径 |
| **R2 需用户明确同意** | 在 CM311 启动实时 USB 接收、HDMI 显示或长期/独占 V4L2 测试；停止已有业务进程；大量拷贝/删除；写入工作树现有关键文件；非短时压力测试；连接/断开无线设备 | 展示完整命令、持续范围及退出方法；等批准后执行；无线开关仍由人操作 |
| **R3 高风险、每项单独明确批准** | `reboot`/`shutdown`/`poweroff`；`systemctl restart/stop` 影响 SSH/网络/显示/USB 的服务；`rmmod`/`modprobe`/驱动重载；写 `/lib/modules`、`/boot`、DTB、firmware、bootloader；升级 kernel/`apt upgrade`；改网络/防火墙/IP；`dd` 到设备；可能使 SSH 失联的操作 | **禁止自动执行**；必须先给人计划、完整命令、停机/失联风险、现场回退与物理访问条件，得到限定范围的明确批准，再在约定窗口进行 |

额外约束：

- **绝不**执行 `rm -rf` 清理未知目录、`git reset --hard`、`git clean -fdx`、覆盖原始捕获、抹掉 Git 历史、任意 `killall` / `pkill -f`、写 EFI/eMMC/闪存，除非人对完整作用域明确授权。危险操作即使被脚本间接调用也必须审批。
- **离线测试/分析无需批准，但不是无约束**：先检查目标设备/进程无冲突；使用 `timeout`、有限磁盘和独立 `.codex_tmp/<step>/` 或专用 run 目录；不得覆盖 golden 或既有日志；结束后报告命令、RC、证据和是否需要后续审批。
- 不用 `sudo` 碰运气；若只读诊断需要权限，先解释具体的 `sudo` 只读命令；**任何 root 写入**按高风险处理。不要索取、回显或记录人的密码、SSH 私钥、token。
- 不擅自 `apt install`（可能改包依赖和系统状态）；PC 安装开发依赖也先说明影响。优先用已安装工具或 PC 独立虚拟环境。
- 不自动调整系统电源、网络、摄像头/无线发射端及 USB 供电。`echo` 写 sysfs、unbind/bind USB、GPIO reset 等均视为可能影响链路的高风险操作。
- 不以 `timeout` 能结束进程为由忽视设备占用；离线短测也不得抢占正在使用的 USB/V4L2/HDMI 资源。实时视频解码器和内核可能存在失败后需要恢复的情形。
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
硬超时策略（如 timeout -k 5 45）及 framemd5 是否持久化；空文件不等于 0 帧解码
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
- `-vsync 0` 是旧写法；新测试用 `-fps_mode passthrough`，并在证据中记录实际命令。默认 vsync 会筛选帧，不能把少量输出误判为解码失败。
- `-frames:v` 提前停止只绕过 EOF drain；它证明已输出帧内容，不证明 EOF 处理正确。
- `-flush_packets 1` 让超时前已解码帧写入 framemd5，是实验性诊断手段，不是 EOF 修复；未启用时 framemd5 为空不等于 0 帧被解码。
- 硬件 EOF 测试必须使用 `timeout -k 5 <seconds>` 一类硬杀策略；只发 TERM 可能让 V4L2 进程在 EOF 挂起。

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
