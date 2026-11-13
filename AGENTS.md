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

> 2026-11-10 03:00 用户要求精简 docs：分析交付文档已归档到 `.codex_tmp/docs_backup_20261110/`，两份计划移入 `plans/`，历史流程图文档移入 `archive/`；`docs/` 仅保留交接与远端使用两份，根目录 `AGENTS.md` 为第三份。

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

44. **2026-11-09 22:40-22:58 HKT P0-0 环境快照与基线指标口径（只读）**：PC 经文档 askpass 模式（密码运行时读取、未回显；helper `.codex_tmp/p0_0_snapshot_20261109/`）对 CM311 只读盘点：`armbian`/`aarch64`/`6.18.59-ophub`、4 核 1.7 GiB、根分区 103 GB 可用、uptime 3d7h；`/dev/video0` 无 opener、`meson_vdec` refcnt 0、USB `2ca3:1020` 已枚举、`/dev/ttyACM0`/`ttyACM1` 存在、Xorg `:0` 可用、无 `vt13_video`/`ffmpeg`/`ffplay` 残留。远端工作树仍非 Git 仓库；部署哈希：config `f47c7d9b`、pipeline `c700b8cd`、ffmpeg_pipe `871af9b2`、control `cc0cbcdc`、decoder `0a63d896`（实验版）、launcher `c0e35756`、release FFmpeg `1ed2b711`、custom FFmpeg `2a204518`、venv PyAV 11.0.0。基线日志已拉取 `.codex_tmp/baseline_20261109/`（run2/4/15/17/18）；统一指标脚本 `.codex_tmp/p0_1_abba_20261109/live_metrics.py`，口径：unique abort=events.tsv `kernel_abort` 行，frames=`decode.frames`，显示丢弃=`decoder.display_*`，AU/IRAP=`stream.*`。基线：run15 ON 33 abort/61 s（p50 间隔 1501 ms、19 请求、195 帧/3.18 fps）、run17 OFF 30/61 s（1752 ms、0 请求、273 帧/4.47 fps）、run18 ON 23/45 s（1742 ms、12 请求、183 帧/4.04 fps）、run4 1832×1032 0/96 s（2 IRAP、110 帧）。**新发现（待证实）**：当前 SPS/VUI 为 1920×1080、level 5.0、`vui_time_scale=60`、`num_units_in_tick=1`（名义 60 fps）、`max_dec_pic_buffering_minus1=1`（DPB=2）、`max_num_reorder_pics=0`；实测仅 34–39 AU/s（约 40% 名义帧率缺口，需 P0-3 证明是上游帧率还是丢 AU）；run17 无恢复请求仍有 31 次 `IRAP received`/61 s（≈2 s 一个），**与早期“IRAP 仅建链发送”结论不一致**，当前流存在周期性 IRAP；`0xf` 间隔 p50≈1.5–1.75 s 与 IRAP 间隔一致。未启动新实时链路（VT 已开、接收器在线），未 reboot/重载模块/装包/改远端工作树。证据 `.codex_tmp/p0_0_snapshot_20261109/`、`.codex_tmp/baseline_20261109/`；本地文档已更新，未 commit。

45. **2026-11-09 22:43-22:48 HKT P0-1 A/B/A 对照：requested I-frame 不是 0xf 触发因素**：CM311 实时运行三段各 60 s，唯一变量 `control.iframe_on_recovery`（ON→OFF→ON），其余固定（`iframe_on_connect=true`、`stall_restart_s=0`、`kernel_abort_watch=true`、release Copy-Out `1ed2b711`、`convert_bgr=false`、ffplay 1024×576、1920×1080 源）。结果：A1 ON 18 请求/31 abort/267 帧、B1 OFF 0 请求/33 abort/225 帧、A2 ON 18 请求/32 abort/216 帧；abort/60 s 分别 30.8/32.8/31.8，OFF 与 ON 差 +4.8%（远小于 20%）→ **Gate 通过：请求 IDR 不触发也不放大 0xf**；ON 帧数 +7% 属噪声。请求→IRAP p50 100/79 ms、p95 188/118 ms。OFF 段零请求仍有 34 次 `IRAP received`/60 s（≈1.8 s 一个），证明当前源/链路周期性发 IRAP，**旧“IRAP 仅建链发送”结论不再适用于当前条件**。证据 `.codex_tmp/p0_1_abba_20261109/{abba_20261109_224334_A1,abba_20261109_224500_B1,abba_20261109_224618_A2}/`（capture.log、events、times、smoke.yaml、cmd.txt、dmesg_before/after），三次 `LAUNCHER_RC=0`。恢复 TTFV 未测（无逐帧单调时钟埋点，归入 P2-1）。未 reboot/重载模块/装包/改远端工作树，运行后设备空闲。未 commit。

46. **2026-11-09 22:50-23:25 HKT P0-3 输入完整性：raw 流字节级损坏、重启成本主导产出**：对 B1 capture（50,031,223 B，SHA256 `b18bd14b...`）离线重放：2460 VCL AU/60 s≈41 AU/s、IDR 294 个、GOP p50=8 AU（IDR≈0.2 s 一个，**IRAP 不饥饿**）、参数集 310 组；发现 18 个超大伪参数集 NAL（PPS 最大 16,594 B、AUD 16,327 B，正常 12/6 B）、`discarded_prefix_bytes=4080`，295 GOP 中 74 个（25%）POC 不连续；`/usr/bin/ffmpeg` 软件解码同 raw 报 `Could not find ref with POC`、`Duplicate POC`、`Truncating likely oversized PPS`、`cu_qp_delta outside range`。**结论：raw 字节流本身已损坏，解码器不是对完好流误报。** 归因：`times.tsv` 长度和=文件大小（记录无丢字节）、B1 USB errors=0/无 stall、仅 12 次 read gap；同一链路 run2 曾 497/498 干净 → 损伤最可能来自 USB 上游（无线/接收器），属**强关联未证明**，需 P0-2 物理隔离。**产出瓶颈**：`abort→ffmpeg spawn` p50≈150 ms，但 `spawn→首帧 CAPTRACE HANDOFF` p50≈970 ms、p95≈2.4 s；每会话平均仅解 8.6 帧（267/31）→ 45 fps Copy-Out 不是 live 产出瓶颈，进程/V4L2 初始化+0xf 循环才是。脚本 `.codex_tmp/p0_3_au_analysis/{au_analyze.py,poc_analyze.py}`；证据 B1_au.json/B1_poc.json/B1_sw_decode.log/B1_trace.log。POC 解析在损坏流上仅作存在性证据。未 reboot/重载模块/装包/改远端工作树。未 commit。

47. **2026-11-09 23:30-23:50 HKT P1-1 离线剖析：Copy-Out 与进程启动都不是 live 瓶颈**：CM311 离线（`/dev/video0` 空闲），release Copy-Out `1ed2b711`，输入 `run2_segB_bootstrapped.h265`（1080p，SHA256 `e12bbf92`）。干净启动 `-frames:v 1`：copy 0.275–0.322 s、no-copy 0.256–0.264 s（ffmpeg+V4L2 初始化≈0.26 s）；**0xf 注入（`no_sei.h265` rc=134）后立即重开干净样本仅 0.277–0.305 s**（5/5），证明设备 teardown 不慢。300 帧 rawvideo：copy 7.752 s=**38.7 fps**，`FFMPEG_V4L2_NO_COPY=1` 3.336 s=**89.9 fps**。A1/B1/A2 会话统计：每 spawn 窗口帧数中位 1–6，每段 4–5 个零帧会话，偶有 20–85 帧；故 live 启动慢是“首个可解画面迟到”（输入损坏）而非初始化。**P1-1 Gate：Copy-Out 不是当前 live 限制项，逐阶段 alloc/copy/DQBUF 分解暂缓**，优先 P0-2 RF 隔离。脚本/证据 `.codex_tmp/p1_1_profile_20261109/`（matrix.tsv、matrix_b.tsv、ffmpeg_stderr*.log）。未 reboot/重载模块/装包/改远端工作树；测试后设备空闲。未 commit。

48. **2026-11-09 23:02-23:25 HKT P0-2/P1-2 关键转折：损伤是管线吞吐不足造成，RF 与接收器被排除**（**修正 item 46 的“上游损伤”归因**）：23:02 用户把接收器移到 USB2 延长线并重新枚举（bus1 dev 005→006）。移动后 3×60 s：31/32/34 次 0xf、243/278/182 帧、AU 38.8–41.7/s，与移动前 A1/A2（31/32 次、267/216 帧）无差异 → **RF 位置不是主因**。**只抓取不解码 60 s**（`capture_pyusb.py`）：76,218,090 B=**10.2 Mbps**、max gap 0.17 s、无 ≥0.5 s gap、**60.3 AU/s**、GOP p50=8、451 GOP 仅 2 个 POC 缺口、超大伪参数集仅 2 个 → **接收器输出在主机持续读取时基本干净**。**管线干净 replay 上限 38.54 fps**（498 AU→497 帧、0 错误）< 源 60 fps → 结构性欠载。async 预取（`VT13_ASYNC_USB=1`）读侧 0 gap、读取满速 64.9 MiB/60 s，但只交付 36.7 MiB（5.6 Mbps），队列涨到 15191/16384，527 帧/18 次 0xf；async+no-copy 627 帧/16 次、队列触顶 16384；async+整 GOP 丢弃（新增 opt-in `VT13_SHED_TO_IRAP`，KEEP=1/SKIP=1）505 帧/14 次、积压稳定 10–14 MiB；async+关闭控制面 **778 帧/61 s=12.7 fps、10 次 0xf、绿/半绿过滤 0**（今日最佳）。**结论（强关联，未最终证明）：源 10.2 Mbps/60 fps → 管线 ~38.5 fps 上限 → 持续欠载 → 接收器 FIFO 溢出丢字节 → 图像损坏 → 0xf → reset 循环**。口径：录制 raw 是“已交付解析器”的字节，async 队列有积压时不是完整 USB 流，不能算绝对丢包率。后续 opt-in 实验（23:07–23:25）：async+no-copy+关控制 571 帧/19 次；async+no-copy+关显示+50% GOP 丢弃 **1530 帧/2 次 0xf**；新增 `VT13_DISPLAY_FPS` 显示限帧后 async+25 fps 800 帧/10 次；同步+限帧 352 帧/32 次；同步+限帧+丢弃 507 帧/17 次；**小队列 async（`VT13_ASYNC_CHUNKS=2000`≈2.5 s）+50% GOP 丢弃+限帧+no-copy+关控制 两次 552/529 帧（9.2/8.7 fps）、15/17 次 0xf、积压 ~3 MiB** = 目前最佳组合；`-vf fps=30`（最小构建无该滤镜）与 `-r 30 -fps_mode cfr`（0 帧/EIO）均失败并回滚。最终远端：`pipeline.py` `9d0013c2`（shed 块，默认关）、`ffmpeg_pipe.py` `edb960c2`（显示限帧，默认关），均 opt-in、默认路径不变；备份 `~/.codex_tmp/backup_shed_20261109/`、`backup_dispcap_20261109/`、`backup_pipefps_20261109/`，patch 脚本 `.codex_tmp/p1_2_shed_20261109/`。未 reboot/重载模块/装包。证据 `.codex_tmp/p0_2_captureonly_20261109/`、`.codex_tmp/p0_1_abba_20261109/{..._P02a/b/c,..._ASYNC1,..._ASYNC_NC1,..._SHED1,..._NCTRL1,..._REG1}/`、`.codex_tmp/p1_1_profile_20261109/`。**用户目视反馈（23:30）**：默认（async 关）画面约每几秒更新一次、约 5 s 滞后；async 开画面基本不更新——async 把 10.2 Mbps 缓冲进有界队列（60 s 积压 ~25 MiB≈20 s 流），解码的是很旧的帧，属“延迟换吞吐”，**只能作诊断，不能作观看路径**。REG1 默认回归：36 次 0xf、172 帧、6 次 read gap，与移动前同量级。下一步：体验最佳组合用 `DJI_CONTROL_ENABLED=false DJI_DISPLAY_FPS=25 FFMPEG_V4L2_NO_COPY=1 VT13_SHED_TO_IRAP=1 VT13_ASYNC_USB=1 VT13_ASYNC_CHUNKS=2000`；根治仍需把管线吞吐提到 >60 fps（去掉 nut/PyAV 每帧 3.1 MB 往返）或在读侧实现按 IRAP 丢弃的闭环；RF 不再是优先项。

49. **2026-11-09 23:58-00:06 HKT S0 计时 + S1 raw 传输：传输不是 live 主因，显示/X11 是**：S0 用 `VT13_PIPE_TIMING=1` 在干净 498 帧 1080p 上实测：no-copy `wait p50=17.1 ms/p95=30.0 ms`、display=0、bgr=0、build=0.2 ms、58.52 fps；copy `wait p50=21.8-25.8 ms/p95≈55 ms`、37.84 fps → 每帧成本几乎全在“等 ffmpeg/nut/PyAV”，Python 仅 0.2 ms。S1 新增 opt-in `VT13_PIPE_TRANSPORT=raw`（rawvideo 定长 NV12，不经 nut/PyAV）：干净 replay **497 帧、0 错误、65.33 fps**（nut 58.52），首次 >60 但余量小。S2 live（关控制、no-copy）：raw+同步+限帧 25 = 171 帧/35 次 0xf；raw+小队列 async+丢 50%+限帧 = 260 帧、收尾 RC=1（raw 停止缺陷）；raw+小队列 async+关显示 = 725 帧/20 次；**nut+小队列 async+关显示+丢 50% = 1530 帧/2 次（仍最佳）**。结论：raw 只提升离线上限，live 负载来自“解码+ffplay/X11 软件渲染+录制”，显示是最大可减项，整 GOP 丢弃仍是压制 0xf 最有效手段。部署：`ffmpeg_pipe.py` `edb960c2→b6672def`（显示限帧/计时/raw，全 opt-in，默认 nut）；`pipeline.py` 保持 `9d0013c2`（shed 默认关）；备份 `backup_timing_20261109/`、`backup_rawtransport_20261109/`。未 reboot/重载模块；raw 路径停止 RC=1 未修，仅实验。下一步：P2-2 轻量显示（DRM/KMS overlay 或避免 ffplay 1080p 软件缩放），目标显示开启时 live ≥25 fps、0-3 次 0xf。未 commit。

50. **2026-11-10 00:06-00:15 HKT U0 USB 根盘拓扑（只读）**：`/dev/sda2` ext4 根分区位于 **USB SG Flash**（`TRAN=usb`、`ID_BUS=usb`、udev path `platform-xhci-hcd.2.auto-usb-0:2:1.0-scsi`），`/dev/sda1` vfat 为 `/boot`；`lsusb -t` 显示 Bus 001 `xhci-hcd/2p 480M` 上 Port 001=DJI `2ca3:1020`、Port 002=SG Flash → **rootfs 与 DJI 共用同一个 USB 2.0 host controller**。Swap 为 `zram0`（RAM 后端 1 GB，201.7 MB 已用），非 USB swap；`/tmp`、`/dev/shm` 为 tmpfs（`/dev/shm` 894 MB）；根挂载 `noatime,nodiratime,commit=600,data=writeback`；当前 boot 无 usb/uas/reset/I/O error/ext4 日志，空闲 `wa=0`。判断：带宽非瓶颈（10.2 Mbps « 480 Mbps），共享控制器是风险项但非已证明根因——只抓取 60 s 同时向 rootfs 写 76 MB 仍得到干净流；不录制也只有 ~30 AU/s。后续 live 建议录制改到 `/dev/shm` 以移除该变量。证据 `.codex_tmp/u0_usb_rootfs_20261110/readonly.txt`。未改配置/未重启/未开始新 live。未 commit。

51. **2026-11-10 00:27-00:32 HKT U1 上游 meson-vdec 补丁审计**：交付 `.codex_tmp/docs_backup_20261110/upstream_patch_matrix.md`。来源：v7 `[PATCH 00/19]`（Anand Moon，2026-07-13，7 文件 +388/-106，作者自述 VIFIFO 满时 workqueue 死锁未解）；v8/v9/合入状态检索未找到（unverified）。本地树 HEAD `0e80ef956`（2026-11-04，浅历史），`codec_hevc.c`/`vdec_platform.c` 有本地实验修改。结构核对：present 4（P01 m2m init 在 probe、P13 job_abort 等）、partial 3（P03 recycle kthread stop、P06 cancel_work_sync 部分、P11 m2m state）、absent 4（P05 无 `synchronize_irq`、P16 无 `dma_set_mask*`、P19 无 `dma_set_max_seg_size`、P18 未见 32 MiB 常量）、unknown 8。候选 P05/P16/P19（P18 需先定位当前 FIFO 大小）均无“可复现样本+指标”，**禁止整套 cherry-pick**。Gate：审计 PASS、可直接部署 FAIL。证据 `.codex_tmp/u1_patch_audit_20261110/`。未改设备/未 live。未 commit。

52. **2026-11-10 00:32-00:34 HKT U2 FFmpeg V4L2 生命周期对照**：交付 `.codex_tmp/docs_backup_20261110/ffmpeg_lifecycle_comparison.md` + 本地 diff `.codex_tmp/u2_ffmpeg_audit_20261110/local_ffmpeg.diff`。本地 FFmpeg n6.1.1 HEAD `e38092ef`，改 3 文件：`v4l2_m2m_dec.c` Copy-Out（dequeue→av_frame_get_buffer→copy→copy_props→unref→move_ref，无池化）；`v4l2_buffers.c` 把全局 `s->refcount++` 从“每 plane”移到“每 buffer group”，与 `v4l2_free_buffer()` 的“每 group −1”对称——机制上解释了原 Source Change 的 sem_wait 挂起，但仍是未上游评审实验；`v4l2_m2m.c` 仅 REFSCAN/REFTRACE 诊断。上游 `v4l2_context.c` 已有 SOURCE_CHANGE/LAST/drain/EPIPE 处理。三问题分离：Source Change（Copy-Out 解决）、fatal 0xf/EIO（Copy-Out 不能解决，需新进程/新 open，实测 0.28-0.30 s）、Copy-Out 成本（管线 wait 21.8-25.8 ms vs no-copy 17.1 ms，非 live 主限速）。Gate U2：对照交付 PASS；**不建议部署 FFmpeg 修改**。下一步 U3（`0xf`/padding 分层表）。未改设备/未 live。未 commit。

53. **2026-11-10 00:33-00:35 HKT U3 `0xf`/padding 分层表**：交付 `.codex_tmp/docs_backup_20261110/0xf_layer_matrix.md`。分层：L1 USB/VT13（只抓取 60 s=10.2 Mbps/60.3 AU/s/2 缺口 vs 管线流 25% GOP 缺口 → **宿主侧滞后诱导损伤**）；L2 AU（无独立故障）；L3 esparser/边界（pad≥512B 使 `0xf→0x8`，36/38 一致，仅诊断）；L4 firmware（只在缺参考/损坏样本中止，clean 样本无 0xf；v7 的 FIFO-full 死锁属另一类）；L5 FFmpeg（Copy-Out 不能阻止 0xf；新 open 0.28-0.30 s）。`0xf` 类型 A 缺参考 GOP（POC21/POC50/live POC5/7/24/269）、B 边界/padding 敏感、C 1080p 高码率节奏。下一步：damage-aware GOP gating（POC 不连续→跳过到下一 IRAP）优先于固定比例丢弃。未改设备/未 live。未 commit。

54. **2026-11-10 00:34-00:38 HKT damage-aware GOP gate（opt-in）**：远端 `pipeline.py` 新增 `VT13_DAMAGE_GATE=1`（默认关）：解析 SPS/PPS/slice POC；非 IRAP AU 的 POC ≠ prev+1（模 LSB）时跳过该 GOP 到下一 IRAP；解析失败回退正常喂流。`9d0013c2→9ada66df`，备份 `~/.codex_tmp/backup_damagegate_20261110/`。初版每 slice 全量 unescape 使干净 replay 掉到 18.8 fps；只解析头部 64 B 后恢复 **58.27 fps**。验证：干净 498 帧→497 帧、0 误报、skip=1；B1 损坏流→21+ 次断链、490 AU 跳过、**0 帧**（每 GOP 首个 P 帧即断，IDR 单独不足以出帧）→ gate 对“偶发损坏”有效，对当前高频损坏流无效，必须先解决输入/吞吐。默认路径不变。未 reboot/未 live。未 commit。

55. **2026-11-10 00:38-00:40 HKT P2-2 显示路径只读探测**：交付 `.codex_tmp/docs_backup_20261110/p2_2_display_feasibility.md`。V4L2 `meson-vdec`：CAPTURE 仅 `NM12`，两队列 `VB2_MMAP|VB2_DMABUF`，CAPTURE 为 `vb2_dma_contig`；DRM `meson-drm`（GXL）：**overlay 平面支持 NV12**（`meson_overlay.c:580`）与 YUV420，支持 src/dst 缩放；primary 仅 RGB；`modetest` 未安装。**`VIDIOC_EXPBUF` 已运行时验证成功**（C 探针：NM12 1920×1080、REQBUFS 4 caps=0x15、4 缓冲×2 平面全部导出，len 2,088,960/1,044,480、stride 1920）；**DRM 运行时验证（裸 ioctl，无 libdrm）**：GETPLANERESOURCES 显示 card0 仅 1 个 plane，formats 含 NV12/NV21/YU12 等；PRIME_FD_TO_HANDLE（Y/UV 两 fd）+ ADDFB2 成功创建 NV12 fb_id=49 → dmabuf→DRM framebuffer 端到端可用。剩余阻塞：Xorg(tty7) 持有 DRM master，设置 plane 需 `chvt` 切 VT 接管（R3 单次批准）或停 X；探针 `.codex_tmp/p2_2_expbuf_20261110/`。PoC：R1 EXPBUF 探测 → R2 overlay 测试 → 先 pipe NV12→dumb buffer→overlay（硬件缩放），再 dmabuf→PRIME 零拷贝；Gate：显示开启 live ≥25 fps、0-3 次 0xf、无绿屏/撕裂，ffplay 保留回退。证据 `.codex_tmp/p2_2_display_probe_20261110/probe.txt`。未 streaming/未改显示/未装包。未 commit。

56. **2026-11-10 00:40-00:42 HKT U4-lite 录制位置 A/B**：同一配置（async 2000+丢 50%+限帧 25+no-copy+关控制）仅把录制放 `/dev/shm`：**541 帧/14 次 0xf/AU 45.8/s/输入 7.3 Mbps**；对照 rootfs 录制 ASMALL2 529 帧/17 次/47.6 AU/s → **无显著差异，rootfs 写回不是 live 限制因素**；U4 受控 A/B 不需要启动。证据 `.codex_tmp/u4_shm_20261110/`；/dev/shm 测试数据已清理。未改系统/未重启。未 commit。

57. **2026-11-10 01:15-01:30 HKT Kiosk K1/K2：KMS 直显（无 Xorg）**：新增 `tools/kms_render.c`（远端 `.codex_tmp/kiosk_20261110/kms_render`，SHA256 `d3dc2d6e`）：DRM master 获取/释放、自适应当前 CRTC mode、NV12 overlay、信号退出清理。K1 测试图 45 s `PLANE_ON fb=48`（当前模式 1920×1080）RC=0；K2a ffmpeg no-copy→rawvideo→`--stdin --dumb` 498 帧/6.0 s=**83 fps**；K2b 管线 `decoder.display: kms`（`config.py f47c7d9b→25004fb8`、`ffmpeg_pipe.py b6672def→67a40898`，备份 `backup_kms_20261110_ffmpeg_pipe.py`），dumb buffer 自带显存不占 `/dev/video0`。live：KMS1 610 帧/10.0 fps/27 次；KMS2（限帧 25+丢 50%）**659 帧/10.8 fps/15 次 0xf/AU 48.5/s/read gap 0**，同条件 ffplay 529 帧/8.7 fps/17 次 → KMS 约 +25% 帧。系统：lightdm stop、enable 链接移除（static）、default=multi-user.target；恢复桌面 `sudo systemctl start lightdm`。回滚：恢复 ffmpeg_pipe 备份 + `set-default graphical.target`。未 commit；未装包。

58. **2026-11-10 01:30-01:45 HKT K2c DMA 优化方案**：交付 `.codex_tmp/docs_backup_20261110/dma_optimization_plan.md`。实测：ffmpeg no-copy 89.9 fps（11.1 ms/帧）、Copy-Out 38.7 fps、管线 nut 58.5、raw 65.3、**ffmpeg→kms_render 直管 83 fps（12.0 ms/帧，renderer 拷贝仅 ~1 ms）**；live KMS2 10.8 fps/15 次 0xf 受输入损伤/reset 限制。优化阶梯：D1 `kms-direct`（ffmpeg rawvideo 直连 renderer，Python 不再搬帧，滤镜移到 renderer 双缓冲）→ D2 双缓冲+限帧 → D3 自定义 V4L2 解码客户端 EXPBUF dmabuf→KMS 真零拷贝。Gate 分别：live ≥20 fps/0xf≤8、稳定节奏、≥25 fps/0xf≤3/CPU≤1.5 核/无泄漏。明确：单纯提解码吞吐/池化不能解决 0xf。未改设备。未 commit。

59. **2026-11-10 01:45-02:10 HKT D1 尝试（未通过）**：① raw 传输 + KMS：400 帧/63.9 s=6.3 fps、10 次 0xf、AU 31.8/s、RC=1（raw 停止缺陷），差于 nut+KMS；② ffmpeg→kms_render 直连（`VT13_KMS_DIRECT`，备份 `backup_kmsdirect_20261110/`）：0 帧到达 renderer、ffmpeg 启动即 EIO、两次重建 → **未验证并回滚**到 `ffmpeg_pipe.py 67a40898`。回归 nut+KMS：**625 帧/10.4 fps/14 次/AU 50.7/s/read gap 1**，与 KMS2 一致。当前 kiosk 最佳配置：`DJI_DISPLAY=kms DJI_DISPLAY_FPS=25 DJI_CONTROL_ENABLED=false FFMPEG_V4L2_NO_COPY=1 VT13_ASYNC_USB=1 VT13_ASYNC_CHUNKS=2000 VT13_SHED_TO_IRAP=1`。下一步：先在干净文件验证直连管道，再决定 D1/D3。未 reboot/未装包。未 commit。

60. **2026-11-10 02:10-02:25 HKT D1 离线复验 + 计划 Review**：D1 直连（ffmpeg rawvideo → kms_render --stdin --dumb）在干净 498 帧文件上验证成功：renderer 日志 **480 帧/7.4 s≈65 fps**，管线 frames=0 属预期；RC=1（EOF/停止待修）。→ 直连管道可用，live 失败是损坏流下缺少错误反馈/节奏。验证后已回滚 `ffmpeg_pipe.py` 到 `67a40898`。计划 Review 交付 `.codex_tmp/docs_backup_20261110/plan_review_20261110.md`：Plan A P0-2 FAIL（RF 无关）、P0-0/1/3 PASS、P1-1/4/P2-1 PARTIAL、P1-2/3/P3 NOT DONE、P2-2 可行性 PASS；Plan B U0-U3 PASS、U4 CLOSED。建议把 P2-1/P2-2 升为 P0、P0-2/P1-3 降级；成功标准改为先打断闭环（≥55 AU/s、0xf≤3/60 s）。未满足：0xf=0、≥55 fps、recovery≥95%、soak、KMS 像素对照。未 commit。

61. **2026-11-10 02:25-02:35 HKT 全链路瓶颈分析**：交付 `.codex_tmp/docs_backup_20261110/pipeline_bottleneck_analysis.md`。KMS3 量化：源 60.3 AU/s → 解析交付 50.7 AU/s（缺 16%）→ 50% 丢弃后 ~25 AU/s 入解码 → 10.4 fps；14 次 0xf/60 s，每次约 1 s 恢复（abort→IRAP 0.15 s + spawn→首帧 0.97 s），约 23% 时间在重启；入解码 AU 仅 41% 变帧，~896 AU/60 s 损失在 reset/无输出会话。瓶颈排序：B1 reset 循环+损坏输入（主导）> B2 消费者吞吐<源 > B3 显示（ffplay 8.7/KMS 10.8/关显示 25.3）> B4 解码器（no-copy 89.9，不限制）> B5 录制（排除）。干预：D1/D3 打断闭环（≥55 AU/s、0xf≤3/60 s）→ 降 reset 成本 → KMS 滤镜 → K3 服务/soak → 驱动候选。待测：逐进程 CPU、每会话 fed-AU→frame、TTFV、KMS YUV。未改设备。未 commit。

62. **2026-11-10 02:35-02:55 HKT D1 修复复测（仍不足）**：修复：直连时 ffmpeg 输出 nut→**rawvideo**（此前是 0 帧直接原因）、SET_MASTER 15×200ms 重试、终止顺序先杀 ffmpeg 后关 renderer、停止忽略 BrokenPipe。live KMSD3 60 s：**19 次 0xf、20 次 direct 重建**、管线 frames=0（预期）、renderer 每会话 <120 帧、log 空 → **D1 只换帧路径，不能打断 reset 循环**。结论：D1 关闭；下一步 **D3**（自定义 V4L2 客户端：进程内重建 + dmabuf→KMS）。已回滚 `ffmpeg_pipe.py` 到 `67a40898`；D1 代码保留 `.codex_tmp/kiosk_20261110/`。未 reboot/装包。未 commit。

63. **2026-11-10 11:10-11:50 HKT B0 环境盘点 + D3-0 源码审计与设计（只读，未实机）**：交付 `.codex_tmp/docs_backup_20261110_d3/B0_environment_inventory.md`、`.codex_tmp/docs_backup_20261110_d3/baseline_manifest.json`、`.codex_tmp/docs_backup_20261110_d3/B0_go_nogo.md`、`.codex_tmp/docs_backup_20261110_d3/D3-0_design.md`；D3 计划原文入库 `plans/CM311_D3_Native_V4L2_KMS_Execution_Plan.md`（SHA256 `ea243a23…`）；新增探针 `tools/d3_probe.c`（SHA256 `7d4eaab4…`，PC 编译 RC=0）；**已在 CM311 构建成功**（当次 binary `86641a49…`；修复后 `1c196647…`，见 item 64），只读 `--inventory` RC=0（未取 master、未 stream）；显示测试未执行。远端快照 `~/.codex_tmp/backup_d3_20261110_112758/deployed.tar`（`0ed6e107…`），暂存 `~/.codex_staging/d3_0_20261110_112758/`，运行目录 `~/.codex_tmp/d3_0_20261110_112758/`（含 `READINESS.txt`、`commands.sh` `9f7f3231…`）。自检修复两个探针缺陷：`GETRESOURCES` 未清 `count_encoders/count_fbs` 导致 EFAULT；未设 `UNIVERSAL_PLANES` 只看到 overlay。运行时平面：primary 39（crtc 45、fb 47）、overlay 42（NV12）。CM311 实测：`armbian`/aarch64/`6.18.59-ophub`；**无 Xorg、LightDM inactive、`multi-user.target`、DRM master 无人持有**（P2-2 的 master 阻塞在当前状态不存在）；HDMI-A-1 connected+enabled、dpms On、cmdline `video=HDMI-A-1:1920x1080@60e`、fb0 `mesondrmfb` 1920×2160；`/dev/video0` meson-vdec 无 opener、`meson_vdec` refcnt=0；CAPTURE 仅 `NM12`；板端有 `/usr/include/drm/{drm.h,drm_mode.h}` 但无 libdrm-dev → 裸 ioctl 可编译；`modetest` 缺失。**版本一致性重大偏差**：远端 `~/mobile_vt` 非 Git，`config.py 25004fb8`、`ffmpeg_pipe.py 67a40898`、`pipeline.py 4f129217`、`decoder.py 0a63d896` 均与本地 HEAD `3e3e1a6` 不同；kiosk KMS 路径只存在于远端；已将 5 个文件 + `kms_render` 二进制镜像到 `.codex_tmp/b0_inventory_20261110/remote/`（SHA256 逐项相符），**远端 tar 快照未做**（属写操作）。审计结论：`tools/kms_render.c` 从不 `STREAMON/QBUF/DQBUF`，默认模式只是测试图案 + PRIME 组件验证；部署实际走 `--stdin --dumb`（CPU 拷贝进 dumb buffer、只 SETPLANE 一次、无 page flip）→ 现有“EXPBUF/PRIME/ADDFB2 成功”**不等于真实解码帧可 scanout**。dmesg 本 boot 计数 `HEVC_LCU_CHECK` 453、`Aborting decoding session` 36。B0 Gate = **CONDITIONAL PASS**（设计可继续；实机 D3-0 需 R2 批准并补远端快照）。未接管 DRM master、未启动 V4L2 流、未改远端文件、未重启、未开无线图传。未 commit。

64. **2026-11-10 11:38-11:50 HKT D3-0 实机执行（用户批准 R2）：PASS**。探针 `tools/d3_probe.c` `7d4eaab4…` → 板端 `build/d3/d3_probe` `1c196647…`。**T1 1832×1032**（`clean_1832x1032.h265`）：34 NAL chunks、20 CAPTURE buffers 全部 EXPBUF/PRIME/ADDFB2（fb 49–68）、1 帧、HOLD 10 s、RC=0；dump `00221868…` 与软件解码**逐字节一致**，画面为标准彩条。**T2 1920×1080**：原 `segB_clean.h265` 首帧是 TRAIL_R POC34（缺 POC33，软解同样报错）→ 绿屏，属输入起点问题；从流内 IRAP（NAL 8）连 VPS/SPS/PPS 重切 `segB_irp1080.h265`（`c7f5da00…`）后，用 `--cap-bufs 17`（CMA 只剩 ~106 MB，请求 20 实际只分配 12、驱动仍按 20 设 `min_queued` → STREAMON EINVAL）1 帧 POC0 起解，dump `35b75b16…` 与软件解码**逐字节一致**，画面为真实 DJI 室内场景。**执行中修复**：①首轮把文件切 2 个大 chunk 一次喂入导致解码器跑在用户态之前、DPB(16) 耗尽 → `can't match offset`/`No dst buffer`/`Aborting`（332164），改为按 Annex-B NAL 分块并同时回收 OUTPUT；②分配不足时探针明确报错并支持 `--cap-bufs`。**收尾已核**：overlay 回 `crtc=0 fb=0`、primary `crtc=45 fb=47`、`video0 free`、无 master holder、`refcnt=0`；通过的两轮 dmesg **0 次 `0xf`、0 次 abort**（本 boot 唯一 abort 是修复前首轮）。新增 `.codex_tmp/docs_backup_20261110_d3/D3-0_report.md`。**用户已目视确认**（11:50）：两次 10 s 保持分别显示彩条与 DJI 画面；未测连续轮转/动态分辨率/EOF/live。**12:05 追加关键发现**：overlay zpos=0、primary（控制台）zpos=1，两者同时活跃时控制台盖住视频；必须 `--hide-primary` 关闭 plane 39 才能看到画面（用户 120 s 目视确认彩条）。这意味着部署的 `kms_render --stdin --dumb`（从不关 primary）此前并未被目视证实，“KMS 10.8 fps 可看基线”需重新验证。未 reboot、未改部署文件、未开无线图传。未 commit。

65. **2026-11-10 12:06-12:12 HKT D3a（文件）两项 Gate 均 PASS**：构建 `tools/d3_probe.c` `5ba4af69…` → 板端 `126acd1c…`。输入 `segB_irp1080.h265`（431 AU）。**D3a-dec**：`--no-display --frames 240 --cap-bufs 17` → **240 帧/0.884 s=271.60 fps**、0 corrupt、RC=0（Gate ≥75，目标 90）。**D3a-present**：`--hide-primary --frames 240 --cap-bufs 17` → **240 帧/3.992 s=60.12 fps**（阻塞 SETPLANE，每帧一次 vblank，是面板 60 Hz 上限而非解码上限）、0 corrupt、RC=0（Gate ≥55）。dmesg 时间窗（≥338500）：**0 次 `0xf`、0 次 abort、0 次缺参考、0 次 POLLERR**；`status=0x8` 约 0.95 次/帧（over=0，非致命）——仅第 0 帧做过 SW/HW 逐字节对照，**未做 240 帧全量 FrameMD5**。**关键工程结论**：①必须按 Access Unit 喂流（按单 NAL 会在 2 帧后停住）；②17 个 CAPTURE buffer 足够（DPB=16 + 1），20 个在 CMA 碎片化时可能只分配 12 并导致 STREAMON EINVAL；③显示必须 `--hide-primary`（overlay zpos=0 在控制台 primary zpos=1 之下）。收尾：overlay 释放、控制台恢复、refcnt=0。新增 `.codex_tmp/docs_backup_20261110_d3/D3a_report.md`。未测时间戳节拍/动态分辨率/EOF/live USB。未 reboot、未改部署文件、未开无线图传。未 commit。

66. **2026-11-10 12:15-13:45 HKT D3-0/A 后续：kiosk 显示修复（`--hide-primary`）**。原因已证实：overlay zpos=0、控制台 primary zpos=1，kiosk 从不关 primary，所以视频一直被控制台覆盖。改动：①`tools/kms_render.c` 新增 `--hide-primary`（自动识别 primary plane 并 `SETPLANE(fb=0)`，退出 `DROP_MASTER` 恢复；源码 `fbd8c439…`，板端 binary `a071cfed…`，旧 `fbb208d7…` 备份于 `~/.codex_tmp/backup_kms_hideprimary_20261110_1200/`）；②部署 `vt13_video/ffmpeg_pipe.py` 的 kms 启动参数加 `--hide-primary`（`67a40898→0936da17`，同目录备份，`py_compile` RC=0）。验证：`kms_render --stdin --dumb --hide-primary` 用 lavfi 90 帧（12.86 fps）与软件解码真实内容 120/240 帧（24 fps）均正常消费、干净退出、控制台恢复。**绿幕排障**：上一轮 ffmpeg 卡在 EOF（`-frames:v 600` > 文件 ~430 帧）并占用 `/dev/video0`，渲染器收到 0 帧，dumb buffer 为全零 NV12（Y=0/U=V=0）→ 绿色；不是格式错误。另确认 `-f rawvideo` 管道本身不稳定（与 `VT13_PIPE_TRANSPORT=raw` 的“raw 停止缺陷”一致），kiosk 仍走 nut。**待办**：live 验证（需 VT/USB）。未 reboot、未开无线图传。未 commit。

67. **2026-11-10 13:45-13:46 HKT kiosk live 验证（A 完成）：画面可见，但卡顿+闪烁**。用户开启 VT；launcher `live_capture_run5.sh`，`display=kms`、`--hide-primary`、async 2000 + 50% GOP shed + 限帧 25 + no-copy + 控制面关闭，45 s。结果：**570 帧 / 45 s = 12.7 fps**，`keyframe_starts=11`、`IRAP=279`、`resets=10`（全部 `kernel_0xf`）、`dropped_frames=144`、`display_dropped=5`；USB async **backlog 3.1–3.7 MiB（queue 2000/2000，约 3 s 流）**；dmesg 窗口 0xf=20、abort=10、0x8=108、POLLERR=0。退出后 device free、refcnt=0、控制台恢复。**用户目视确认 live VT 画面可见**，但卡顿与闪烁。归因：①lag≈3 s 来自 async 积压；②闪烁来自 10 次 0xf 复位（每次冻结到下一 IRAP）+ `--stdin --dumb` 单缓冲被 scanout 同时覆写的撕裂；③根因仍是 Python/nut 路径 12–17 fps < 60 fps 源。D3a 已证明 C 解码 271 fps，**D3b（C worker）是消除积压/复位的正解**。证据 `captures/manual_live/d3_live_20261110_134503/`。未 reboot、未开无线以外的操作。未 commit。

68. **2026-11-10 13:54-13:57 HKT D3b 阶段 1（离线 AU socket 回放）：PASS**。架构：`d3_replay.py`（AU 服务端，`SOCK_SEQPACKET`，24 B 头 `magic/len/seq/flags/ts` + 一个完整 AU，60 AU/s，背压时丢非 IRAP 到下一 IRAP）→ `d3_probe --socket` C worker（复用 D3a 的 V4L2/KMS 路径，8×512 KB OUTPUT、17 CAPTURE、`--hide-primary`、阻塞 SETPLANE、EOS 后 drain 1 s）。结果：**300 AU / 5.001 s = 60.00 AU/s，发送端 0 丢弃；worker 解码 299 帧，稳态 60.2–60.6 fps，corrupt=0、oversize=0**；dmesg **0 `0xf`、0 abort、0 缺参考、0 POLLERR**（`0x8` 40 次，非致命）；收尾 overlay 释放、控制台恢复、`video0 free`、refcnt=0。构建 `tools/d3_probe.c` `c5db1467…` → 板端 `5a23fa8b…`；`tools/d3_replay.py` `dfbbe424…`。新增 `.codex_tmp/docs_backup_20261110_d3/D3b_report.md`。**未完成**：Python 管线 opt-in 集成（`decoder.backend: worker`）、live 背压/丢弃验证、EOS/动态分辨率/`0xf` 重建状态机。未 reboot、未开无线图传（本轮为文件回放）。未 commit。

69. **2026-11-10 14:00-14:06 HKT D3b 管线集成（live）：链路跑通，但输入损伤成为唯一限速项**。新增 `vt13_video/worker_client.py`（opt-in `decoder.backend=worker`：Python 建 socket 服务端并拉起 C worker，AU 经 `SOCK_SEQPACKET` 发送；背压丢非 IRAP、worker 死亡才重启、`atexit`/`flush` 停 worker）。部署改动：`config.py 25004fb8→1a6160d1`、`pipeline.py 4f129217→75071b00`、新增 `worker_client.py 7929f009`、launcher 支持 `DJI_BACKEND`（`e5f73157`），备份 `~/.codex_tmp/backup_worker_backend_20261110_1400/`。**live 结果（40 s，async 2000）**：USB 读取 **2287 AU / 40 s ≈ 57 AU/s**（async 生效），worker 每会话 **60.3–60.5 fps**，但 dmesg **30 次 `0xf`、17 次 abort、64 次缺参考**，worker 每约 1 s 被 EIO 终止、被重启 2 次；`pipeline frames_decoded=2287` 是 AU 计数（合成 Frame，占位 1920×1080），真实解码数以 worker 的 `DECODED` 为准。**结论**：worker 与显示路径正常（离线 300 AU/0 `0xf`、live 每会话 60 fps），剩余问题是**上游输入损伤 ~0.75 次 `0xf`/s**；此前只读抓包（60 s 干净）与当前链路状态不同。清理修复后退出无残留（`video0 free`、无 master holder、refcnt=0）。下一步：D3c 进程内恢复（把冻结从 ~1 s 降到 ~0.1 s）+ 链路/RF 排查。未 reboot。未 commit。

70. **2026-11-10 14:12-14:13 HKT D3c-lite（worker 内重建）live：44.8 fps，进程不再退出**。worker 新增 `session_open/session_close/wait_irap_au`：遇到 `POLLERR`/`DQBUF EIO` 时不再退出，而是关闭 V4L2 会话、保留 socket 与 DRM、丢弃非 IRAP AU 直到下一个 IRAP，然后原地重开；Python 侧 `reset()` 对存活 worker 改为 no-op，并支持把 `bootstrap` 参数集前缀到 IRAP AU。构建 `tools/d3_probe.c` `756b3e02…` → 板端 `9ad1fb16…`；`worker_client.py` `93a7087a…`。**live 45 s 结果**：**34 个会话、2018 帧 = 44.78 fps**、`corrupt=0`、`oversize=0`；pipeline `resets=31`（kernel watcher，但不再杀 worker）、`errors=0`、`dropped_aus=0`；`STREAM_EXIT_RC=0`，退出无残留。对比：进程级重启版本约 1 s 冻结/次、总帧数低；现在每 1.3 s 重建一次、每次约 0.1–0.2 s（等 IRAP），画面基本连续。**剩余限速项仍是上游损伤 ~0.75 `0xf`/s**（位置未变，VT 重启后仍存在）。未 reboot。未 commit。

71. **2026-11-10 14:16-14:21 HKT 关键 A/B：原始流干净，损伤是主机侧自激**。**只抓取不解码 60 s**（`capture_pyusb.py`）：**79,343,146 B / 60.004 s = 10.6 Mbps**、`max_gap=0.01 s`、0 个 ≥100 ms 间隔、**3616 AU = 60.3 AU/s**、452 IRAP 全部自带 VPS/SPS/PPS、`oversized_ps=0`、`ps_max=51 B` → **上游/射频完全干净**。**解码不显示**（`VT13_WORKER_NO_DISPLAY=1`，40 s）：**2288 帧 = 57.06 fps**、8 个会话、`corrupt=0`；dmesg **12 `0xf` / 7 abort / 3 缺参考**。对比 **解码+KMS 显示**（45 s）：2018 帧=44.78 fps、34 会话、dmesg **34 `0xf`/18 abort/82 缺参考**。结论：①此前“上游输入损伤”判断被推翻——原始流无缺口；②`0xf` 是主机侧负载诱导（KMS 扫描输出 + VDEC/USB 共存），显示占大头（去掉显示后 0xf 约降到 1/3、fps 升到 57）；③剩余损伤指向 VDEC/KMS DMA 与 xHCI 共享 DRAM/中断延迟，或 Python 读线程调度。证据 `captures/manual_live/caponly_20261110_141622/`、`d3c_nodisp_20261110_141920/`。未 reboot。未 commit。

72. **2026-11-10 14:27-14:28 HKT 决定性 A/B：async 读取线程是损伤主因；关闭后 58.06 fps**。同一 worker+显示配置，仅把 `VT13_ASYNC_USB` 从 1 改为 0：**2330 帧 / 40.129 s = 58.06 fps**、仅 **5 个会话**、`corrupt=0`；dmesg **6 `0xf` / 4 abort / 12 缺参考**。对比 async ON：44.8 fps/34 会话/34 `0xf`（45 s）、38.9 fps/46 会话/78 `0xf`（shm 录制）。**结论**：Python async 读线程与解析/发送线程的 GIL/调度竞争会延迟 USB 读取，导致接收器 FIFO 溢出 → 字节损伤 → `0xf`；单线程“读→解析→发送”反而干净（58 fps，约每 8 s 一次重建）。此前“KMS 显示占大头”的结论需修正：async 是更大因素；显示仍有次要影响（no-display 57 fps/8 会话）。**推荐 live 配置：`DJI_BACKEND=worker`、async OFF（默认）、control on**。证据 `captures/manual_live/d3c_noasync_20261110_142750/`。未 reboot。未 commit。

73. **2026-11-10 14:35-14:36 HKT 最佳 live：59.22 fps，单会话、0 `0xf`**。worker 增加“保留最后上屏 fb”机制（`session_close` 把正在 scanout 的 buffer 移入 `held`，新会话第一帧上屏后才释放），避免重建时闪黑/回控制台。live 45 s（worker、async OFF、control on）：**2671 帧 / 45.106 s = 59.22 fps**、**sessions=1**、`corrupt=0`、`errors=0`、`resets=0`；dmesg **0 `0xf`/0 abort**；退出无残留。构建 `d3_probe.c c4203cb6…` → 板端 `87da0d9e…`。说明：同配置各轮 `0xf` 数波动大（6–78），本轮为完全干净样本；`held` 修复在无重建轮次未触发，但已就位。证据 `captures/manual_live/d3c_noflash_20261110_143507/`。未 reboot。未 commit。

74. **2026-11-10 14:39 HKT 用户验收：当前 live 基线可接受；重建闪烁/短停顿列为后续优化**。60 s 复跑（worker、async OFF、control on）：**3487 帧 / 60.066 s = 58.05 fps**、6 个会话、`corrupt=0`、`errors=0`；dmesg 10 `0xf`/5 abort/6 缺参考；退出干净。用户确认**画面质量可接受**，但要求后续优化：①每次会话重建时的闪烁；②重建造成的约 0.1–0.2 s 停顿。当前推荐配置固定为 `DJI_BACKEND=worker`、`VT13_ASYNC_USB=0`（默认）、`DJI_CONTROL_ENABLED=true`、`DJI_KERNEL_ABORT_WATCH=true`、`DJI_STALL_RESTART_S=0`。**待优化清单**：a) `held` fb 的释放时机/双缓冲（排除重建瞬间的黑帧）；b) 0xf 后不 close/reopen，尝试 STREAMOFF→STREAMON 或更快 reinit；c) 缩短等 IRAP 时间（更早请求、预置参数集）；d) 剩余 0xf 抖动（USB 读调度/DRAM 争用，候选 IRQ/CPU 亲和或 rmrx 读取进程）；e) 10 分钟 soak 与服务化。证据 `captures/manual_live/d3c_show2_20261110_143809/`。未 reboot。未 commit。

75. **2026-11-10 14:44-14:54 HKT 10 分钟 soak：PASS**。配置：`DJI_BACKEND=worker`、async OFF、control on、kernel watch on、stall 0、无录制、显示由 worker 接管。结果：**35226 帧 / 600.112 s = 58.70 fps**、**45 个会话**（约每 13 s 一次 0.1–0.2 s 重建）、`corrupt=0`、`oversize=0`、pipeline `errors=0`、`dropped_aus=0`、`PIPELINE_RC=0`；dmesg 窗口 **20 `0xf` / 10 abort / 4 缺参考**；内存 376→365 MiB（无增长，available 1.4 GiB）；温度 59→66 °C；收尾无残留（`video0 free`、无 master holder）。证据 `captures/manual_live/soak_20261110_144438/`（`capture.log`、`soak.yaml`、`dmesg_before/after.txt`、`pre/post_mem.txt`、`pre/post_temp.txt`）。**待优化**：重建闪烁与 ~0.1–0.2 s 停顿（held fb 双缓冲、免 close/reopen、缩短 IRAP 等待）、剩余 0xf 抖动（IRQ/CPU 亲和或 rmrx）、30 min soak/服务化。未 reboot。未 commit。

76. **2026-11-10 15:05 HKT 部署基线回流：本地仓库与 CM311 部署一致**。远端 `~/mobile_vt` 非 Git，此前的 kiosk/async/shed/damage/ffmpeg_pipe 改动只存在于现场。本次以部署为准回流：`config.py 1a6160d1`、`pipeline.py 75071b00`、`ffmpeg_pipe.py 0936da17`、`async_usb.py d5b52faa`、`launcher e5f73157`、`control.py cc0cbcdc`（其余 cli/device/nal/recovery/sources/stats 哈希相同）；`decoder.py` 以部署 `0a63d896` 为基座，重新合并本地的 codec 身份日志（`requested/actual` + `snapshot.codec`），合并后 `5c7460f0`。新增 `config/vt13_video.no_status.yaml`、`config/vt13_video.yuvtest.yaml`。本地测试 **43 passed / 38 skipped / RC=0**。备份 `.codex_tmp/sync_20261110/local_backup.tar`（`8410cc9d…`）。**今后以本地仓库为唯一代码来源，部署改动必须回流并提交**。未 reboot。commit `2a16dca`。

77. **2026-11-10 15:17-15:29 HKT 恢复优化 + TTFV 埋点（D3c 部分完成）**。改动：①worker 复用同一 V4L2 fd 做 `STREAMOFF→S_FMT/REQBUFS`（不再 close/reopen；失败才回退）；②worker 检测到 `POLLERR`/`DQBUF EIO` 时通过 socket 发 `R`，Python 侧立即 `_request_iframe("worker_recover")`，把 I-frame 请求与重建重叠；③`RECOVER begin/reopened/streamon/capture_ready/first_frame` 全阶段埋点。实测（60/45 s，async OFF）：TTFV **260–265 ms**（reopen 181 ms、等 IRAP 28 ms、17 buffer 导出 35 ms、首帧 18 ms），较优化前 282 ms 略降；`reused fd config failed` 未出现，说明 181 ms 是驱动在 abort 后同一 fd 上重配的成本，不是 open。计划 D3c 的 TTFV 目标 p50≤200 ms **未达**；下一步可选 soft recovery（不 REQBUFS，仅 STREAMOFF/STREAMON）、预开备用 fd，或接受。吞吐仍 57–58 fps、0 corrupt、退出干净。构建 `d3_probe.c d6c91234…`（板端随构建）、`worker_client.py d03297a6…`、`pipeline.py 60b7d312…`。证据 `captures/manual_live/d3c_ttfv{2,3,4,5}_*`。未 reboot。未 commit。

78. **2026-11-10 16:28-16:32 HKT soft recovery 实验：失败并回滚**。尝试 0xf 后不 `REQBUFS`，仅 `STREAMOFF → 重新 QBUF → STREAMON`（保留 buffer/fb）：`STREAMON` 返回成功，但**soft 会话产不出帧**（500 ms 内无帧），说明 meson-vdec 在 abort 后必须完整重配。首版回退逻辑有 bug（soft 循环 101 次、60 s 仅 15 帧），已 `git checkout c9c76eb -- tools/d3_probe.c` 回滚；板端重建后 30 s 验证 **1697 帧/56.43 fps**、6 会话、0 corrupt、干净退出。**结论**：TTFV 的 181 ms 是驱动 abort 后完整重配的固有成本，userspace 无法通过复用队列消除；计划 D3c 的 p50≤200 ms 在当前驱动下不可达。若要继续压缩，只能减少 abort 次数（IRQ/CPU 亲和、rmrx 独立读取）或改驱动（高风险）。证据 `captures/manual_live/d3c_soft2_20261110_163006`（失败）、`d3c_revert_20261110_163210`（回滚验证）。未 reboot。未 commit（代码已回到 c9c76eb）。

79. **2026-11-10 16:34 HKT 无录制 A/B：录制不是剩余抖动主因**。async OFF、60 s、直接跑管线（无 `--record`）：**3492 帧 / 60.065 s = 58.14 fps、6 会话、corrupt=0**；dmesg **10 `0xf` / 5 abort**，与带录制到 USB 根盘的 60 s 运行（10–16 次）相同 → **录制写根盘不是剩余 `0xf` 的主因**；此前 soak 的 20 次/600 s 属窗口波动。剩余 `0xf` ≈0.17 次/s，每次约 260 ms 冻结，约占 4% 时间；属 VDEC/KMS 与 xHCI/DRAM 的主机侧争用。**软件侧可做的优化到此为止**；继续需 IRQ/CPU 亲和（root）、独立读取进程（rmrx，收益不确定）或改驱动（高风险）。证据 `captures/manual_live/d3c_norec_20261110_163408`。未 reboot。未 commit。

80. **2026-11-10 16:39-17:13 HKT D3d 3×60 s + K3 30 分钟 soak**。配置 `config/vt13_video.kiosk.yaml`（worker、async OFF、control on、kernel watch、stall 0、无录制）。**D3d 三轮**（各 60 s）：**57.80 / 58.02 / 58.49 fps**、`corrupt=0`、`PIPELINE_RC=0`；每轮 5–7 个会话；dmesg 每轮 8–12 `0xf` / 4–6 abort → **计划 D3d 的“0 `0xf`”Gate 未达**，但 ≥55 fps、恢复、正确性（0 corrupt）满足。**K3 soak（1800 s）**：**105856 帧 / 1800.087 s = 58.81 fps**、**128 个会话**（约每 14 s 一次重建）、`corrupt=0`、`oversize=0`、`PIPELINE_RC=0`；内存 358→359 MiB（无增长）、温度 61→67 °C、退出无残留。注：soak 的 dmesg 前后差分显示 12 `0xf`/6 abort 明显低估（30 分钟重日志导致 ring buffer 回绕），以 128 个会话作为重建次数。**K3 草案**已提交 `f43d463`：`config/vt13_video.kiosk.yaml`、`deploy/vt13-kiosk.service`（draft，不启用）。**结论**：长时间稳定性 PASS；残余 `0xf` 仍是 D3d “0 次”Gate 的唯一缺口。证据 `captures/manual_live/d3d_k3_20261110_163945/`。未 reboot。未 commit。

81. **2026-11-10 17:15 HKT taskset 亲和实验：无显著收益**。`taskset -c 2,3` 绑核跑 60 s：**3521 帧 / 60.115 s = 58.57 fps**、5 个会话、`corrupt=0`；dmesg **8 `0xf` / 4 abort**，与未绑核的 D3d（8–12 次）无显著差异 → CPU 亲和不是残余 `0xf` 的杠杆。残余抖动属 DRAM/中断级，继续需驱动/IRQ 改动（高风险）或接受。证据 `captures/manual_live/d3d_taskset_20261110_171535`。未 reboot。未 commit。

82. **2026-11-10 18:30 HKT RC1 低延迟计划 L0（只读审计 + 测量设计）：PASS**。新计划原文入库 `plans/CM311_DJI_C5_Low_Latency_60FPS_Optimization_Plan.md`（SHA256 `8dfff72e...`）；报告目录 `reports/low_latency/rc1_baseline_20261110/`（`baseline.json`、`metric_definitions.md`、`latency_path_audit.md`、`instrumentation_proposal.md`、`L1_runbook.md`、`decision.md`、远程 K3/D3d 日志副本、`checksums.sha256` 27 文件）。**PC**：仓库干净，HEAD `e56c5fe`；新建本地分支 `rc1-latency-instrumentation`（未提交、未部署）。**CM311 只读盘点**：`armbian`/`6.18.59-ophub`/aarch64，uptime 4d3h，`video=HDMI-A-1:1920x1080@60e`，LightDM inactive、`multi-user.target`、无 Xorg，`/dev/video0` 空闲、`meson_vdec` refcnt 0，DJI `2ca3:1020` 已枚举（Bus1 Dev6，USB2 480M），`journalctl -k` 可读、无 `pidstat`/`perf`/`trace-cmd`/`modetest`；`~/mobile_vt` 仍非 Git。部署哈希：`config.py 1a6160d1`、`pipeline.py 60b7d312`、`worker_client.py d03297a6`、`decoder.py 0a63d896`（仓库 `5c7460f0`，仅本地 codec 日志差异）、`control.py cc0cbcdc`、`cli.py a74bb800`、`kiosk.yaml d4d155f2`、worker `4749ed94`；`deploy/vt13-kiosk.service` 与仓库差 1 行注释。**基线复核**：D3d 1–3 = 57.80/58.02/58.49 fps，dmesg 窗口 0xf = 6/6/4 与 rebuild 6/6/4 一致；K3 = 105,856 帧 / 1800.087 s = 58.81 fps，128 会话/127 rebuild，源 107,779 AU（59.87/s）、发送 107,445（59.70/s），**Python `decode.fps` 是 AU 发送率，不是显示帧率**；127×266 ms TTFV 模型给出 58.87 fps，可解释全部均值缺口。**关键审计**：AU 仅在下一个 AU 起始 NAL 到达时才完成（结构性 ~1 帧延迟且无完成时间戳）；`drm_present` 为阻塞 legacy SETPLANE，present 后才 requeue 上一帧（显示节拍闭环，`htop` 低 CPU 属正常）；rebuild 内含固定 `usleep(100000)`；仅 10/127 次 rebuild 有 `RECOVER` 标记（`QBUF CAPTURE` EIO 未调用 `mark_recovering`）；无逐帧 age/backlog/可见 gap 记录。**已实现（本地、未部署）**：`AccessUnit.completed_at` + `VT13_LAT_CSV`（Python CSV，`seq/send_ns/completed_ns`）、worker `--lat-csv`（`age/decode/wait/backlog`，32 入 FIFO 按 seq 关联）、每秒 `age_p50/p95/max`、`VISIBLE_GAP`、所有 requeue 失败均标记 recovery、`tools/latency_report.py`、`tools/latency_sampler.py`、`.codex_runs/live_latency_l1.sh`；PC `gcc -O2 -Wall -Wextra` 通过、pytest **50 passed / 38 skipped**（新增 7 项）。**未执行**：未 live、未接管 DRM、未重启/重载模块/装服务/装包、未写远端工作树、未开无线。下一步：L1 需 R2 批准（部署 instrumented worker + 180 s baseline + 可选 240 fps 手机 glass-to-glass），见 `L1_runbook.md`。未 commit。

83. **2026-11-10 19:00-19:15 HKT 回放模式验证 instrumentation（R2 已批准，无无线）：关键发现**。在 CM311 上用 **staging 二进制**（`~/.codex_staging/l1_replay_20261110_185859/d3_probe` `5c20744e...`）回放已录制流；**部署文件零改动**（`build/d3/d3_probe 4749ed94`、`worker_client.py d03297a6`、`kiosk.yaml d4d155f2` 不变），未 reboot/重载/装包/开无线。共 6 轮（`clean2/clean3/clean4/clean5/damaged/damaged2`），最终有效 4 轮：`clean4`（60.0 AU/s，stall 20 ms + R 丢弃）**3520 帧**、age p50 **161.6 ms**（socket 63.0 + decode 65.7 + present 16.4）、4 次 0xf、`VISIBLE_GAP` 383.8/367.1/400.4/383.9 ms；`clean5`（59.5 AU/s）**3537 帧**、age p50 **62.8 ms**、4 次 0xf；`damaged2`（59.5 AU/s）**3504 帧**、age p50 **30.8 ms**（socket 0.7 + decode 17.8 + present 12.4）、5 次 0xf、一个 733.7 ms gap。**结论**：①instrumentation 端到端可用（`seq_gaps` 4–7/60 s，FIFO 映射有效）；②**“干净”录制流本身可确定性复现 4–5 次 0xf/60 s → 0xf 是内容相关，不是 USB/RF**；③每次 rebuild 的可见冻结为 **367–400 ms**（首次实测）；④`SETPLANE` present 等待 **12.4–16.4 ms ≈ 一个 vblank，覆盖 ~100% 帧**；⑤age 分解显示 socket 队列是主要变量：60.0 AU/s 与消费者打平时队列填满（~10 AU≈167 ms），59.5 AU/s 时排空，内在下限 **~31 ms**；⑥**live 客户端 `SO_SNDBUF=1 MB`（≈48 AU≈800 ms）是待测延迟风险**，L2 候选应为按年龄在 IRAP 边界丢弃而非依赖大缓冲；⑦`tools/d3_replay.py` 旧版把 VPS/SPS/PPS 附到**前一个** AU，导致首个 IRAP 缺参数集（453 次 rebuild/0 帧）；已改为与 `AccessUnitAssembler` 一致并在 `captures/vt13_live_raw.h265` 上验证 **1056/1056 AU 分组一致**，新哈希 `0cc5cc6d`；sender 现会响应 worker 的 `R` 丢弃到下一 IRAP（与 live 客户端一致）。**未测**：live USB/组包、1 MB SNDBUF 的真实队列、glass-to-glass、真实恢复节奏。证据 `reports/low_latency/rc1_replay_20261110/`（`replay_results.md`、`run_manifest.json`、6 个 run 目录、`checksums.sha256`）。收尾：无残留进程、`video0` free、refcnt 0、LightDM inactive。未 commit。

84. **2026-11-11 10:13-10:19 HKT L1 live 内部延迟基线（VT 已开、staging 运行）：完成**。instrumented 包与 worker 全部从 `~/.codex_staging/l1_live_20261111_101319/` 运行（staged `vt13_video` = 部署包 + 仅 `nal.py`/`worker_client.py` 埋点；`d3_probe 5c20744e`；config `worker_path` 指向 staged 二进制），**部署树未改**（`d3_probe 4749ed94` 等），未 reboot/服务/内核/网络变更。VT 在接收程序启动前已开，`iframe_on_connect` 使首 IRAP 在 USB open 后约 70 ms 到达。smoke 23 s + baseline 180 s（实际数据 201.6 s）。**baseline**：源 59.9 AU/s、发送 12,029 AU、**presented 11,781（joined 11,779）/201.63 s = 58.42 fps**、18 次 rebuild/`0xf`、0 corrupt、250 AU 在 rebuild 中丢弃。**内部延迟**（`seq` 关联）：`AU complete → present` **p50 131.5 ms / p95 160.2 / p99 216.8**；分解 p50 = socket **51.8** + decode **49.8** + present **16.5**；剔除 rebuild 后 0.5 s：age p50 **130.8**（socket 50.7 + decode 49.8 + present 16.5）。**present 等待 16.53 ms（16.6 p95）覆盖 99.9% 帧 = 一个 vblank**。**可见冻结**：18 次 `VISIBLE_GAP` 283.7–367.1 ms（p50≈317），与 18 次 present gap/`0xf` 一一对应。**系统**：4 核总忙 26.4%；**Python 管线 ≈0.95 核**（73.4% user + 21.5% sys）、worker 仅 0.2% user + 3.2% sys；iowait≈0；load1 2.1（含 USB 存储 I/O）；IRQ vdec 58.2/s、esparser 58.4/s、xhci 1516/s；MemAvailable 1.29–1.40 GiB；59–64 °C；`backlog_max=15`（CAPTURE 17，接近上限，风险项）。**结论**：live 存在约 8 帧（≈130 ms）的持久队列，来源是 60 Hz present 节拍 + 1 MB socket 缓冲 + 8 OUTPUT/17 CAPTURE 池且**从不丢弃陈旧帧**；这是“轻微可感知延迟”的内部成分（不含 DJI 编码/无线）。**操作发现**：非交互 shell 的 `&` 后台任务忽略 SIGINT，launcher 的 `kill -INT` 无效（20 s 后 SIGTERM），已改为 `--seconds` 定时退出；worker 仍干净退出，无残留。**L2 候选**（需新 R2，一次一项）：①按年龄在 IRAP 边界限制 socket 积压/缩小 SNDBUF；②present 最新帧并跳过较旧 CAPTURE（仅显示层跳过，参考链不受影响）；③atomic 非阻塞 flip + event（L3，约 16.5 ms）；④降低 Python 读 CPU（更大 read_size 或 C reader）。**未测**：glass-to-glass、DJI 固有延迟、1832 模式、长期 soak、L2。证据 `reports/low_latency/rc1_live_20261111/`（`live_results.md`、`run_manifest.json`、smoke+baseline 目录、`checksums.sha256`）。未 commit。

85. **2026-11-11 11:10-11:45 HKT rebuild 绿 curtain/撕裂根因、修复与部署：完成**。用户目视：live 中 rebuild 时先短暂冻结、随后出现**局部黑块/撕裂→绿色 curtain**（非全屏闪）。诊断：`--dump-recover` 抓取 4 次 rebuild 的保持帧 + 恢复后前 4 帧共 20 帧，全部完整正常（Y≈95、黑/绿/白 0%、上下左右一致）；每次 RECOVER 的 `primary_fb=0`（GETPLANE），排除控制台/primary。**根因**：`held` 帧的 Y/UV 是**两个独立 dmabuf**，原代码在第一条新帧 SETPLANE 返回后立即 unmap/close/GEM_CLOSE/RMFB；meson flip 可能晚 1–2 帧生效，UV plane 被释放后仍被扫描 → chroma=0（绿）叠加在有效 luma 上，即“绿 curtain/撕裂”。**修复**：`held_release` 推迟 **5 次 present（≈83 ms）**；teardown 只在“held 之后已出过新帧”时才释放旧 held，再保持当前扫描帧。**验证**：damaged 捕获回放 4 次 rebuild（11:41:40.8/11:42:28.9/11:42:36.9/11:42:40.3）用户确认**只剩冻结、无绿幕/撕裂**；live 90 s（2 次 rebuild）同样；**已部署** `build/d3/d3_probe 4749ed94→21c7f288`（备份 `~/.codex_tmp/backup_greenfix_20261111_114324/`），部署 Python 未改；部署后 live 60 s：3,573 帧/59.43 fps、1 次 rebuild/`0xf`、`VISIBLE_GAP 266.6 ms`、0 corrupt、RC=0、退出后设备空闲。**剩余**：冻结本身 267–728 ms（R1 恢复优化），与 L2 的 ~130 ms 队列延迟分开处理。证据 `reports/low_latency/rc1_live_20261111/`（`flashdiag2/`、`flashfix/`、`live_results.md`、`deploy_greenfix_20261111_114334/`）。未 commit。

86. **2026-11-11 12:30-12:42 HKT 启动门控与最终 worker 部署：完成**。用户确认开流瞬间仍有黑闪后，新增 `--start-gate N`（socket 模式默认 60 帧）：门控期间解码帧只 requeue、不上屏，控制台保持可见；当前会话连续解码 60 帧（约 1 s）后才隐藏 primary 并开始上屏；门控未开时遇 rebuild 会重置，**一旦打开不再回退**，后续 rebuild 保持视频（只冻结）。同时加入：**首帧才隐藏 primary**（消除开流绿屏，代价是启动先看到控制台）、**teardown 保留最近两帧**、**present N 只归还 N−2**（避免解码器写入仍在扫描的帧）。回放验证（damaged 捕获）：前两个会话 **0 帧上屏**（两次开流 0xf 全被挡在控制台后），第三个会话 `START_GATE open after 60 frames`；后续 rebuild 画面保持。**已部署** `build/d3/d3_probe 21c7f288→f288c28a`（备份 `~/.codex_tmp/backup_gate_20261111_124124/`），部署 Python 未改；部署后 live 30 s：1 次开流 rebuild 被门控隐藏（`gated=73`）、1,722 帧/57.21 fps、0 corrupt、RC=0、无残留。**已知限制**：启动时控制台可见约 1–2 s。**剩余**：rebuild 冻结 267–728 ms（R1）与 ~130 ms 队列延迟（L2）。证据 `reports/low_latency/rc1_live_20261111/`（`live_results.md`、`deploy_gate_20261111_124128/`）。未 commit。

87. **2026-11-11 13:50-13:58 HKT R1 rebuild 冻结优化与部署：完成**。把 worker rebuild 内固定的 `usleep(100000)` 做成 `--recover-sleep-ms`（默认 100）并做 A/B：damaged 捕获回放（门控开、各 2 轮）中段 `VISIBLE_GAP` 100 ms = 350/383/367 与 383/317/383 ms；0 ms = 283/250/283 与 250/217/250 ms；`first_frame dt` 314–375→215–271 ms，`reopened` 211–240→119–150 ms；0 corrupt、无新增会话/错误，且回放丢 AU 更少（20–23 vs 51–60）。**默认改为 0 并部署** `build/d3/d3_probe f288c28a→888118fb`（备份 `~/.codex_tmp/backup_r1_20261111_135710/`），部署 Python 未改；部署后 live 60 s：4 次 rebuild、`VISIBLE_GAP 200.0/216.7/216.7 ms`（此前 266.6–317 ms，约 −30%）、3,495 帧/58.14 fps、0 corrupt、RC=0。计划 R1 的“冻结 p50/p95 −25%”Gate 对本项达成；进一步缩短需 V4L2 重配/驱动层专项。证据 `reports/low_latency/rc1_live_20261111/`（`live_results.md`、`deploy_r1_20261111_135714/`）。未 commit。

88. **2026-11-11 14:00-14:40 HKT L2（队列延迟）A/B：A 失败、B 成功并部署，30 min soak 启动**。**L2-A（限制 worker `SO_RCVBUF`）失败**：干净回放 60.0 AU/s、默认 vs 48 KB、各 2 轮，age p50 128.8/136.7→163.9/157.3 ms，socket 30/38→48/42、decode 82/83→99，drops 相当 → 队列同时是抖动缓冲，缩小会饥饿并频繁丢弃；flag 仅留 staging，未部署。**L2-B（drain 到最新帧，只 present 最新）成功**：worker 取完所有已解码 CAPTURE 帧、只上屏最新，旧的直接 requeue（解码器仍解全部，参考链不变）。干净回放 age p50 **63.2**（socket 14.2/decode 17.5/present 15.5/backlog_max 4）；live 无 rebuild 轮 `AU complete→present` **p50 32.3/p95 50.5**、3,661 帧/58.97 fps；live 有 1 次 rebuild 轮 **p50 31.8/p95 54.8**、`VISIBLE_GAP 216.6 ms`、0 corrupt。相对 L1 基线 131.5/160.2 **-75%**，接近回放 ~30 ms 下限；用户目视“跟随好一点，但仍有极小延迟”。**已部署** `build/d3/d3_probe 888118fb→51346c85`（备份 `~/.codex_tmp/backup_l2b_20261111_142801/`），部署 Python 未改；部署后 20 s 烟测 1,146 帧、0 corrupt、门控正常。**30 min soak 已启动**（`captures/manual_live/soak_l2b_20261111_142851`，14:28:51，含 1 Hz /proc 采样），结果待回。证据 `reports/low_latency/rc1_live_20261111/`（`live_results.md`、`l2b_live/`）。未 commit。

89. **2026-11-11 14:28-14:58 HKT V1 30 min soak（部署 L2-B）：指标 PASS**。部署路径（kiosk 配置、worker `51346c85`、Python 未改、门控 60、sleep 0），VT 全程开启，1 Hz /proc 采样。**107,763 帧 / 1800.102 s = 59.86 fps**；1 秒上屏增量 p50/p10=60、min 41、**0 个零帧秒**；0 corrupt、0 oversize；**6 次 rebuild/`0xf`**（7 会话，约每 5 min 一次；dmesg 30 min 后 ring 回绕，以 pipeline 日志为准），可见冻结 **200.0–233.4 ms（p50 216.7，合计约 1.3 s = 0.07%）**；worker 每秒 age p50 中位 **29.7 ms**（p95 31.7），`backlog_max=2`；Python 发送 107,870 AU（60.36/s），仅 107（0.1%）未上屏；CPU 总忙 26.1%（max 63.7）、Python ≈0.96 核（74.6% user + 21.3% sys）、iowait≈0；IRQ vdec/esparser 59.8/s、xhci 1530/s；MemAvailable 1.25 GB→稳定 ~1.12 GB（无增长）；温度 61→69 °C（max 72）；`PIPELINE_RC=0`，退出无残留、video0 free、refcnt 0。相对 K3：58.81→**59.86 fps**、128→**6** 次 rebuild、每次冻结 266→**217 ms**、内部 age 131→**~30 ms**（0xf 触发率下降主要是当前链路/内容更好，不是修复改变了触发条件）。**V1 Gate**：帧率/正确性/恢复/内存温度/内部延迟 PASS；**glass-to-glass NOT_TESTED**；启动控制台 1–2 s、每次 0xf 约 217 ms 冻结、极小肉眼延迟为已知限制；最终 PASS 或 ACCEPTED_WITH_LIMITATION 待用户目视确认。证据 `reports/low_latency/rc1_live_20261111/V1_soak_results.md` 与 `soak_l2b/soak_l2b_20261111_142851/`。未 commit。

90. **2026-11-11 15:00 HKT V1 最终结论：ACCEPTED_WITH_LIMITATION；报告归档**。用户目视接受当前体验（连续、画质好、仅极小延迟），按计划记为 **ACCEPTED_WITH_LIMITATION**。最终部署：`build/d3/d3_probe 51346c85`（L2-B；备份链 `888118fb`→`backup_l2b_20261111_142801`、`f288c28a`→`backup_r1_20261111_135710`、`21c7f288`→`backup_gate_20261111_124124`、`4749ed94`→`backup_greenfix_20261111_114324`），部署 Python 未改。V1 30 min：**59.86 fps、0 corrupt、6 次 rebuild/`0xf`、冻结 p50 216.7 ms（200–233 ms）、内部 age ~30 ms、CPU 26%、内存稳定、61–72 °C、RC=0**。**已知限制**：①`0xf` 为内容相关（~6/30 min，随链路/内容波动），每次约 217 ms 冻结，自动恢复；②启动控制台 1–2 s（启动门控隐藏开流闪）；③仍有极小肉眼延迟，**glass-to-glass TODO（未测）**；④L2-B 每次 drain 最多跳过 2 帧（仅显示层，参考链不受影响）；⑤`0xf` 驱动/固件根因未解，进一步缩短冻结需驱动专项。**归档**：本会话 `reports/low_latency/*`（baseline/replay/live 三份）已移至 `.codex_tmp/docs_backup_20261111_lowlatency/`（含各报告 checksums 与归档清单）；计划原文保留 `plans/CM311_DJI_C5_Low_Latency_60FPS_Optimization_Plan.md`。已提交并合并到 main（见 item 91-93）。

91. **2026-11-11 15:42 HKT 提交并同步到远端：完成**。本地改动提交为 **`a4d82c2`**（分支 `rc1-latency-instrumentation`，12 文件，工作树干净）；随后把运行时 Python 同步到 CM311：`vt13_video/worker_client.py f227791c`、`nal.py f2de7db7`、`decoder.py 5c7460f0`，备份 `~/.codex_tmp/backup_sync_20261111_154224/`；**全包逐文件核对 `RUNTIME_PARITY_OK`**（`vt13_video/*.py` + kiosk.yaml 与提交一致）。部署 worker 仍为 `51346c85`，由该提交的 `tools/d3_probe.c`（`8ace8282`）在板端构建。**同步后 20 s 烟测不具结论**：USB 仅 0.47 MB/21 AU/1 IRAP 后无数据（VT 链路应已关闭），门控保持 0 帧、RC=0、无残留；不是同步回归，live 复验需重新开启 VT。远端 `~/mobile_vt` 仍非 Git 仓库，无 `tools/`/本地 docs；tools/tests/plans 仅本地。未 push。

92. **2026-11-11 15:56 HKT 同步后 live 复验（VT 已开）：PASS**。部署路径（`a4d82c2` 同步后的 Python + worker `51346c85`），30 s：`START_GATE open after 60 frames`、**1,745 帧 / 30.106 s = 57.96 fps**（含约 1 s 门控；稳态约 60）、0 corrupt/0 oversize、sessions=1（无 rebuild）、`RC=0`、无残留进程、device idle。同步闭环完成；`glass-to-glass` 仍为 TODO；未 push。

93. **2026-11-11 16:05 HKT 合并到 main：完成**。`git merge --ff-only rc1-latency-instrumentation`，`main e56c5fe→47ddd08`；工作树干净；分支 `rc1-latency-instrumentation` 与 main 同一提交；**未 push**。部署运行时不变（`a4d82c2` 同步的 Python + worker `51346c85`）。

94. **2026-11-11 18:08 HKT K3 服务化预检（PC + CM311，只读）**：用户要求实施 K3 并授权本次文档 askpass；公钥登录 RC=255，askpass 预检 RC=0。CM311 仍为 `aarch64/6.18.59-ophub`、systemd 255、`multi-user.target`、LightDM inactive，USB 接收器与 HDMI 在线，V4L2/DRM 无业务占用；`vt13-kiosk.service` 未安装。部署 Python + kiosk.yaml 共 16 文件与本地 HEAD `2ba4ff5` 一致，worker 仍为 `51346c85`；仅远端 service 草案注释有差异。原 D3d“零 0xf”未达，继续沿用用户接受的 RC1 限制，不冒充严格通过。PC 复现长期 USB 缺席导致 backoff 指数溢出（RC=1）；K3 将最小修复并用正常 SIGINT 清理、受控重启、独立有界日志。备份 `.codex_tmp/k3_service_20261111_1807/pre_local.tar`（SHA256 `2dfd24da463ac331d1d39ad50bc0af150dc3a94782e342a7a2c75ae767c88a4d`）；证据同目录 `preflight.log/backoff_before.log`。未启流/接管 HDMI、未写远端文件、未 reboot/改内核/服务、未 commit；下一步本地验证与完整 R3 安装命令审批。

95. **2026-11-11 18:13 HKT K3 本地实现与离线验证，等待 R3**：修改 `deploy/vt13-kiosk.service`：取消 `After=multi-user.target` 循环、使用真实 YAML 而非无效 DJI 环境覆盖、`Restart=always/15s`、`SIGINT/KillMode=mixed/30s`、非 root/NoNewPrivileges、独立日志 namespace；新增 `deploy/vt13-kiosk-journald.conf`（volatile 32 MiB、单文件 4 MiB）。`recovery.py` 仅修 backoff 溢出/零初始退避；新增三项测试。PC pytest 53 passed/38 skipped，PyAV 环境 scoped unittest 91/91 RC=0（旧 ffplay 测试有 join-current-thread 警告，与 worker K3 无关）；首次无范围 unittest 误收集旧硬件 `test.py`，因 PC 无 DJI 设备 RC=1，未开流。原 unit 在 PC 验证因远端 Python 路径不存在 RC=1；仅替换验证副本解释器后 RC=0，CM311 原样验证仍待执行；bash -n/git diff --check RC=0。测试临时文件已改放本步 test_tmp；早期套件用 /tmp，由 TemporaryDirectory 清理。备份/命令/日志位于 `.codex_tmp/k3_service_20261111_1807/`；尚未安装/启用服务或改远端，下一步精确 R3 命令批准与 READY 人机交接。未 commit。

96. **2026-11-11 18:19 HKT K3 安装/启停/开机启用完成，等待人工开 VT**：用户明确批准安装、start/stop/enable 与必要回退，确认 VT 已关。约 8.6 KB staging 全部 SHA256 匹配；CM311 backoff 30,000 次验证与原样 `systemd-analyze verify` 均 RC=0。安装 `/etc/systemd/system/vt13-kiosk.service`（`15ade4bb`）和 `/etc/systemd/journald@vt13-kiosk.conf`（`f39e019b`），部署 `recovery.py 95f49816→275c91f6`，worker `51346c85`/kiosk.yaml 不动。备份远端 `~/mobile_vt/.codex_tmp/k3_service_20261111_1807/backup/`，PC 副本同项目步骤目录 `remote_backup.tar`。首次启动仅收到旧缓存 19 AU、门控 18 帧且 0 上屏（VT 关，不是 live 验收）；18:18:55 systemctl stop 1.123 s、Result=success、无 worker/设备占用；随后 enable/start，18:19:07 `USB source open` + waiting/0 data，MainPID 262680、NRestarts=0、active/enabled。独立 journal 当时 4 MiB；内核监听子进程存活。全 16 文件运行时 parity OK；实际重启开机行为、直播质量及 10–30 min 服务 soak 尚未验证。证据 `.codex_tmp/k3_service_20261111_1807/{install,lifecycle,ready}.log`；已通知用户 READY 后开 VT。无 reboot/内核/网络/target 变更，未 commit。

97. **2026-11-11 18:25–18:27 HKT K3 实时验收预检失败（未开始 soak）**：用户反馈 VT 已开启并要求验收。18:24:13 首 IRAP 为 1832×1032，POC7 触发 0xf；18:24:17 输入切到 1920×1080，CAPTURE DQBUF EPIPE 后复用 fd 重建；第三会话 `SOURCE_CHANGE after 0.0ms/min_buffers_for_capture=1`，之后 USB/Python 持续约60 AU/s，但 worker `aus_frames=0/age=-1`，直到18:27仍未上屏。systemd active/enabled、NRestarts=0；不能把 Python 占位 Frame 当上屏 FPS。代码核查：run_socket 监听 POLLPRI 但内循环未消费 SOURCE_CHANGE；session_teardown 复用 fd 未清事件，怀疑旧事件导致新会话过早 CAPTURE setup，根因待对照确认。等待 VT 时120s无IRAP会退出/被重拉两次，但非本次零帧原因的充分证明。证据 `.codex_tmp/k3_service_20261111_1807/{live_precheck,zero_frames_diagnostic}.log`；此次无源码/部署变更、无额外启停、无重启系统。下一步需用户确认受控停启隔离或 staging worker 的 Source Change 专项修复；30分钟服务验收尚未启动，K3不能标PASS。

98. **2026-11-11 18:31–18:34 HKT K3 单次重开对照恢复；30 min 稳态观察启动**：用户明确批准仅本次保持 VT 开启执行 `systemctl stop/start vt13-kiosk.service`。18:30:56 stop 0.624 s、设备释放；新 MainPID 263980/worker 263983，18:31:04 门控打开，后续每秒上屏增加约60帧、corrupt=0，worker及配置未变，支持启动/动态切换路径问题但根因尚未确认/修复。18:34:13 HKT 启动1800s只读观察（Monitor `b56tgh1s3`，10/20/30 min 检查点）；CPU/内存/FD/dmabuf/帧年龄/上屏增量/冻结/内核fatal日志采样1Hz，诊断日志有上限。脚本 `observe_soak.py` 本地/远端 SHA256 `ad4b3889` 一致；远端输出 `~/mobile_vt/.codex_tmp/k3_service_20261111_1807/soak_20261111/`。测试结束只停止采样器，不自动停服务。启动失败不计入稳态帧率，但作为未解决缺陷保留；即使稳态通过也不能冒充完整冷启动/动态切换验收。无 reboot/驱动/源码变更，未 commit；等待10min检查及最终30min结果、人眼确认。

99. **2026-11-11 18:44 HKT K3 稳态10min检查点：继续观察**：自动 checkpoint_600 已到（600.730s），实际上屏增量35,465/599.668s=59.141fps，corrupt/oversize增量0；34次V4L2重建/内核abort、34个可见gap，最大283.3ms、累计7.518s；无服务/worker进程重启，NRestarts=0，自动恢复后继续上屏。每秒age p50中位34.55ms、p95中位36.8ms，backlog_max=2；CPU中位26.68%，66–70°C，内存无持续增长；主进程FD12恒定，worker FD稳态40（重建瞬态10–44）、dmabuf稳态34（4–38）；独立journal仍4MiB。0xf频率高于历史V1的6/30min，本轮尚不能归因于服务或内容；此前启动切换失败仍未修。checkpoint JSON 本地/远端SHA256 `261af1dc8ee3c896c3654c801ee1f8c6ea799ddae4e89984507298e1a5c14acc` 相同，汇总 `checkpoint_600_summary.json` 位于本地K3步骤目录。无新的服务/源码改动；继续同一30min观察，不标整体PASS。

100. **2026-11-11 18:54 HKT K3 稳态20min检查点：性能低于RC1目标，资源稳定**：上屏70,706/1199.692s=58.937fps，累计84次重建/内核abort（第二个10min新增50次），corrupt/oversize=0，gap累计18.536s/最大283.3ms；NRestarts=0、PID未变，age p50中位34.5ms、backlog_max=3。CPU中位27%，66–71°C；主FD12、worker稳态FD40/dmabuf34，RSS与cgroup无持续增长；journal4MiB。已低于RC1整体≥59.0fps目标，不能标性能PASS；未出现不可恢复冻结/资源异常，继续原定30min以完成取证，不追加测试。证据 `checkpoint_1200{,_summary}.json`，源/副本SHA256 `3ebb6a9644c9fdc5a65fbd20f4ce06810afd3f073a85cc9233f077b7b5b04533` 一致；无服务/代码变更。

101. **2026-11-11 19:04 HKT K3 30min观察结束：服务实现/稳态资源通过，完整验收PARTIAL**：观察18:34:13.844–19:04:14.017、1800.173s，计数窗口上屏106,278/1799.092s=59.073fps（满足RC1最低59.0、未达优选59.5）；corrupt/oversize增量0（非全像素校验），108次内核abort/V4L2重建、服务/worker PID不变、NRestarts=0。107次冻结有完整埋点：p50 216.7/p95 250.1/max283.3ms，累计23.653s≈1.31%；另1次18:56:15的QBUF OUTPUT EIO直接进入重建而未调用mark_recovering，故不能把107次当全部冻结。age每秒p50中位33.6ms/p95中位36.05ms，backlog_max=4；CPU中位26.75%、66–73°C；Python RSS128184→128488KiB、worker1468→1532KiB，主FD12、worker稳态FD40/dmabuf34，未见无界增长；journal7.3MiB、低于配置32MiB。相比历史V1重建6→108/30min，原因未隔离，不归罪systemd或单独内容变化。首轮1832→1920零帧仍是阻塞，boot/物理热插拔/真实端到端/全面像素验收未测；本次未获新的目视结论。完整证据10文件9,330,350B逐文件SHA256一致，PC `.codex_tmp/k3_service_20261111_1807/soak_20261111/`，manifest SHA256 `eb3017400cdcef68c1365cafcafd0f662bf5433992b4838f3a7263de6c390e3e`；最终分析 `complete_summary.json/final_analysis.json`。观察器已结束，服务仍active/enabled（MainPID263980/worker263983）；未自动延长、未改代码/服务/内核、未 reboot/commit。下一步优先以staging修复/验证Source Change及零帧恢复，部署worker需新的精确批准。

102. **2026-11-11 19:36 HKT Source Change 零帧根因确认 + 最小 worker 补丁（仅本地/staging，离线验证通过）**：用户批准“继续修复并验证”（先备份、最小本地改动+离线测试；部署 worker `51346c85` 与 K3 服务不动；任何实机运行/替换需新的精确命令批准）。**根因**（驱动源码+日志）：meson-vdec `amvdec_src_change` 在分辨率切换时置 `source_change_pending=true`+`STATUS_NEEDS_RESUME`，`vdec_m2m_job_ready`（vdec.c:492）在该标志置位时返回0→解码器静默暂停、无错误、零帧；HEVC 会话（`sess->priv`）在同 fd STREAMOFF/REQBUFS 重建间存活（仅文件 close 时 `codec_hevc_release` 释放），切换后同 fd 重建时 `hevc->dst_width` 已等于新值→`process_rpm` 报 `src_changed=0`→不再触发 `amvdec_src_change`→标志永不清除→永久卡死，只有 close/open 能恢复；OUTPUT STREAMON 全初始化把 `ctrl_min_buf_capture` 重置为1，解释卡死会话 `min_buffers=1`。同分辨率 0xf 重建安全（soak 每次重建 min_buffers 1→16 证明每会话都有新事件）。注意运行模块与当前源码树不同（源码有 `dev_warn HEVC_SHIFT_INIT`，soak kernel.jsonl 108 次启动 0 条），驱动考古仅作指示，日志事实（EPIPE→stale SOURCE_CHANGE 0.0ms→min_buffers=1→aus_frames=0）为权威。**补丁** `tools/d3_probe.c`（+45/−4；改前 SHA256 `8ace8282…`、改后 `4af75b7c57aa53af437f810095925f01c33a4e07e856d12c92822a46ad87a303`）：新增 `ctx.need_fresh_fd`（session_open 清零）；①内循环在 POLLERR 之前消费 POLLPRI 事件，遇 SOURCE_CHANGE 置 need_fresh_fd+mark_recovering；②CAPTURE DQBUF EPIPE（首取与 L2-B drain 两处）置 need_fresh_fd，EIO 保留同 fd 快路径；③teardown 调用 `session_teardown(c, recovered && !need_fresh_fd ? 1 : 0)`；④session_teardown 在 keep_fd 时排空待决事件，遇 SOURCE_CHANGE 翻 keep_fd=0（与 abort 竞态的兜底）；⑤QBUF OUTPUT 失败补 mark_recovering("QBUF OUTPUT")。**不改解码参数与 held/scanout 释放寿命**。**离线验证**：PC `gcc -O2 -Wall -Wextra` RC=0 无警告（binary `65d4d2f6…`）；mock-syscall 测试 `.codex_tmp/k3_source_change_20261111/mock_test.c`（`dd6f40fe…`，重命名 libc  syscall 后 include worker、card_fd=-1 驱动 run_socket）**13/13 PASS、RC=0**，以 open_calls 区分物理重开与逻辑 sessions：normal=1、流中 SOURCE_CHANGE=2、EPIPE=2、定分辨率 EIO=1（复用）、stale 事件竞态 EIO=2（teardown 排空）、QBUF OUTPUT 失败=1+R 信号，各场景均恢复出帧并发 R；Python `unittest discover -s tests -t .` **91 OK（38 skipped）RC=0**。**未验证**：实机行为（mock 只证恢复状态机，不证 meson-vdec 时序/像素）；未做 CM311 staging 运行/worker 替换/live。备份 `.codex_tmp/k3_source_change_20261111/pre_repair_local.tar`（`21c05154…`）/`pre_repair.diff`（`e5a2a2a7…`）。K3 整体验收仍 PARTIAL，待实机验证冷启动 1832→1920。未写远端、未启流/接管 HDMI、未 reboot/改内核/服务、未 commit。下一步：精确命令的 CM311 staging 构建+损坏流（含分辨率切换）离线回放，再新的 R2 live 冷启动验证；替换部署 worker/服务需另行明确批准。

103. **2026-11-11 19:53 HKT 补丁 worker 已 staging 编译 + 离线切换回放资产备妥（服务未动，待 R2 窗口）**：只读预检确认服务 active/enabled（MainPID 263980/worker 263983 占用 `/dev/video0`）、部署 worker 仍 `51346c85bfe2e6aaed134c6004abb59e615b36ed03f0386f8e99eca0829affe6`、gcc 13.3 aarch64。补丁源码传至 `~/.codex_staging/k3_srcchange_20261111_194655/`，远端 SHA 与本地 `4af75b7c…` 一致；板端 `gcc -O2 -Wall -Wextra` **BUILD_RC=0 无警告**，aarch64 binary `eb1dbb67f3193ddcbc5f37f7793f30b7b117c00e9626fb6a4ab68fbc19a95008`。传修正版 `d3_replay.py`（`0cc5cc6d…`，远端旧 staging 副本是 item 83 前的错误版，不用）。合成干净切换流 `switch_1832_to_1920.h265`=clean_1832x1032（`2e13db18…`）+segB_irp1080（`c7f5da00…`），SHA `6c78ff028ca33ebdf2dd60ab6535ea7a2e3b0fce9d19790c9dc845c164cde657`、8,701,313B；split_aus 无设备验证 **461 AU、IRAP 在 AU0/AU30**，1920 IRAP（AU30）自带 VPS/SPS/PPS，干净复现冷启动 1832→1920 SOURCE_CHANGE（无 RF/0xf 损伤）。runner `run_switch_test.sh`（`1130501e…`，两端 bash -n OK）接 `<worker> <label>`、假定服务已停、replay@60AU/s + worker `--socket --cap-bufs 17 --start-gate 0 --hide-primary`、`timeout -k 5 40`。**未停服务/未流设备/未替换 worker**；实机验证需获批 R2 窗口（服务占用 video0+DRM），测试直接跑 staged binary、不替换部署 binary，回退=重启服务。待批精确命令：stop→补丁回放（期望 AU30 后继续出帧、sessions=2、约461帧）→可选旧 worker A/B（期望卡死零帧）→start→READY。无 reboot/内核/网络变更。证据 `.codex_tmp/k3_source_change_20261111/{precheck_remote,stage_build,stage_replay,prep_switch_remote}.log`。

104. **2026-11-11 20:08 HKT Source Change 补丁实机验证通过（补丁恢复 1920、旧 worker 卡死）；部署 worker 仍未替换**：用户批准 R2 A/B 窗口及修正复测。停启用 `sudo -S`/`sudo -n`（密码运行时经 stdin 喂入、不回显；首次 `sudo -n` 因凭据缓存过期失败，该次未停服、设备占用守卫正确中止）。**部署 worker 二进制全程未替换**，回退=重启服务，无 reboot/内核/网络变更。**首轮不具区分性（测试设计缺陷）**：`switch_1832_to_1920.h265` 仅 1 个 1920 IRAP（AU30），切换后 worker 重并发 R，replay 丢非 IRAP 等下一个 IRAP 但该 IRAP 已过→两 worker 均饿死在 22 帧（SENT=33/DROPPED=428）；有用信号：补丁记 `RECOVER (DQBUF EPIPE)`（新 fd 路径实机执行）、旧记 `(DQBUF EIO)`。**修正流** `switch_multi.h265`=clean_1832+3×segB_irp1080，SHA `f91350b137f5a8ed414d95648c14df5efc06194e82e686d5d1e8fcd1d06f1148`、24,706,659B、**1323 AU、1920 IRAP 在 AU30/461/892**（贴合 live 周期 IRAP）。**决定性 A/B**：补丁 `eb1dbb67` 1832（22帧）→EPIPE→新 fd→session2 收 1920 IRAP AU461→G_FMT 1920×1080 **min_buffers=16**→**DECODED 873 帧**（22×1832+851×1920）corrupt=0、age_p50≈53.5ms，**恢复**；旧 `51346c85` 1832（23帧）→EIO→同 fd→session2 收同一 IRAP→G_FMT 1920×1080 **min_buffers=1**→aus_frames 永冻 23、age=-1、**1920 零帧**，**DECODED 23 帧 fps=1.04，卡死**（精确复现冷启动缺陷）。实机证实根因（同 fd 重建残留 source_change_pending→min_buffers=1→解码暂停）且新 fd 修复清除之。补丁 `VISIBLE_GAP 7350ms` 是 replay 丢包等 IRAP 的等待（合成 IRAP 间隔≈7s），非 worker 冻结；live IRAP ≈2s 一个故实际间隙受其限制。**服务恢复健康**（最终 MainPID 270674/worker 270678、active/enabled、NRestarts=0、live 60FPS/0 错误、VT 开）；部署 worker 仍 `51346c85bfe2e6aaed134c6004abb59e615b36ed03f0386f8e99eca0829affe6`。证据本地==远端 SHA：`run_patched.log 767e348a…`、`run_old.log 60363190…`、`replay_patched.log 138ac92f…`、`replay_old.log afbe1a5c…`、`test_window3.log d357c4c6…`（首轮 test_window2.log），目录 `.codex_tmp/k3_source_change_20261111/`。**补丁离线+实机已验证，未部署**；替换 `build/d3/d3_probe` 与 VT live 冷启动确认需另行精确批准。K3 整体验收待部署补丁并确认真实 1832→1920 冷启动后可趋向 PASS；boot/热插拔/glass-to-glass 仍未测。

105. **2026-11-11 20:16 HKT 补丁 worker 已部署到 CM311 kiosk；live 冷启动 1832→1920 确认待人工 VT 循环**：获批 R2 部署（备份→哈希守卫替换→重启→核验）。部署 `~/mobile_vt/build/d3/d3_probe` 现为 `eb1dbb67f3193ddcbc5f37f7793f30b7b117c00e9626fb6a4ab68fbc19a95008`（原 `51346c85…`）；备份 `~/mobile_vt/.codex_tmp/backup_srcchange_20261111_201335/d3_probe.51346c85`（哈希 `51346c85…` 已核）。`deploy_window.sh`（`dd06c58d…`）哈希不符即还原备份、trap 保证服务不被留在停止态。Python/kiosk.yaml 未动，无 reboot/内核/网络变更。旧 worker 干净收尾（28878 帧、1920×1080、8 keyframe、0 USB 错误）；**新补丁 worker live**（MainPID 272334/worker 272344 占用 video0、active/enabled、NRestarts=0、约58fps/源60FPS、0 错误/0 恢复、corrupt=0、sessions=1、age_p50≈25–56ms，VT 开 1920 流）。证据 `.codex_tmp/k3_source_change_20261111/{deploy.log,post_deploy_health.log}`。回退：`cp <备份>/d3_probe.51346c85 ~/mobile_vt/build/d3/d3_probe && sudo -n systemctl restart vt13-kiosk.service`。**完整 K3 验收尚差**：真实 live 冷启动 1832→1920 确认（原失败场景）需人工 VT 关→开使源从 1832 起再切换；离线 A/B 已证修复，此为原位确认。boot/热插拔/glass-to-glass/目视仍未测；冷启动确认前不标完整 PASS。

106. **2026-11-11 20:29 HKT live 冷启动 1832→1920 原位确认修复；部署补丁 worker 稳态 60fps**：人工 VT 关→开。VT 关时重启 kiosk（MainPID 272982/worker 272990、补丁 `eb1dbb67`），20:25:22 READY（usb=up/data=no/0 帧、等 IRAP）；用户约 20:26 开 VT。**冷启动序列（原失败场景）已修复**：20:26:18 session1–2 `G_FMT 1832×1032 min_buffers=16`（源从 1832 起）→20:26:21 session3 `G_FMT 1920×1080 min_buffers=16`——1832→1920 切换经新 fd 恢复，**非旧 min_buffers=1 永久零帧卡死**，切换后持续上屏。**启动 0xf 突发（另一已知 P0、内容相关）**：20:26:18–49 约31s 内 40 次 `HEVC_LCU_CHECK status=0xf poc=7`，每次自动恢复（session3→41 全 min_buffers=16）；**末次 0xf 20:26:49，20:27 起 0 次新 0xf**（>90s 干净）。此为内容/RF 相关固件中止，非切换卡死；补丁不声称修复 0xf，仅修卡死。**稳态**：20:28:25→20:28:37 aus_frames 5678→6398=**720/12s=60.0fps 瞬时**、sessions 稳定 41、corrupt=0、age_p50≈21–32ms、NRestarts=0、active/enabled。部署 worker `eb1dbb67…`、备份 `backup_srcchange_20261111_201335/d3_probe.51346c85` 完好。**Gate**：K3 阻塞缺陷（冷启动 1832→1920 零帧卡死）**已修复+离线 A/B+原位确认**；K3 可趋向 ACCEPTED_WITH_LIMITATION，待用户目视确认。**仍未测**：物理 reboot/boot 启动、USB 热插拔、glass-to-glass、补丁 worker 的新 30min soak（此前 30min 是旧 51346c85）。启动 0xf 突发（约40/31s 后 settles）为已知限制；不声称 0xf 已解决或完整无人值守 PASS。证据 `.codex_tmp/k3_source_change_20261111/{coldstart_restart,coldstart_ready,coldstart_capture,coldstart_head,coldstart_steady}.log`。

107. **2026-11-11 20:37 HKT 用户目视接受 + USB 热插拔 PASS（进程内恢复、服务未重启）；reboot 待测**：用户确认“screen is normal”（冷启动修复后画面接受）。**USB 热插拔 PASS**（用户仅拔插 DJI C5 接收器，根盘 SG Flash 未动）：基线 20:35:24 Dev006、MainPID 272982/NRestarts=0、上屏。20:36:24 kernel `usb 1-1 USB disconnect device 6`→管线 `Errno 19 No such device`→`reopening USB in 0.25s`（优雅、无崩溃）；20:36:39 重新枚举 `2ca3:1020` **device 7**、ttyACM0/1 重建；20:36:42 `USB source open address 7`+`requested I-frame`→恢复；拔插后数次内容相关 kernel_0xf 自动恢复。**NRestarts=0、MainPID 272982 不变（全程进程内恢复，理想）**；稳态 20:37:29→20:37:39 aus_frames 37148→37752=**604/10s=60.4fps 瞬时**、sessions 稳定 47、corrupt=0、age≈30ms、20:37 起仅 1 次 0xf。证据 `.codex_tmp/k3_source_change_20261111/{hotplug_baseline,hotplug_capture,hotplug_steady}.log`。**下一步**：物理 reboot 自启（R3，用户先做热插拔、reboot 顺延）。预检：服务 enabled+multi-user.target、SSH enabled、网络 DHCP 10.42.0.11（gw 10.42.0.1，reboot 可能换 IP）、root /dev/sda2 ext4、worker eb1dbb67。需明确 R3 批准+用户物理访问（HDMI/键盘）以备 SSH 失联恢复。其后仍未测：glass-to-glass、补丁 worker 新 30min soak。

108. **2026-11-11 20:54 HKT reboot 测试暴露“冷启动加载错误模块”缺陷；源码版 meson_vdec（ca46）恢复解码；永久安装待批**：R3 reboot（获批、用户物理访问）20:40:09，SSH 约70s 恢复，服务自启（enabled+multi-user、MainPID 448、NRestarts=0）、worker eb1dbb67 持久、USB 重枚举 Dev002、**IP 稳定 10.42.0.11**。**但无画面**（用户见 Armbian login）。**冷启动解码缺陷**：worker 喂首 AU 后 `no SOURCE_CHANGE within 10000 ms`→每10s 重建、0 帧、不达 G_FMT；kernel `vdec-mbox1` IRQ **0**（解码核不完成）而 esparserirq  firing（解析正常）。`HEVC mailbox IRQ is unavailable` 是**恒定红鲱鱼**（DT interrupt-names 仅 `vdec esparser`，mbox1 回退 vdec、mbox0 无回退），两模块都有、非根因。固件在、runtime PM unsupported。**失败补救**：rmmod+modprobe（R3 获批）无效——modprobe 重载的是 installed 模块，vdec IRQ 仍 0。**根因**：两个不同模块。installed `/lib/modules/6.18.59-ophub/.../meson-vdec.ko`=`a6cc08ca2598caf378881a85515c211e8fc41e6bc870753e5d11a3942458f198`（自动加载用此；解析但 HEVC 核不完成）；源码版 `~/linux-6.18-vdec/.../meson-vdec.ko`=`ca46798328e0975290151c40e1ddbf191a277b563a9694344aca910507aacdab`（AGENTS 记录的可用模块，reboot 前手动加载、跑 5 天）。reboot 自动加载了错误的 installed 版。**修复已验证（R3 获批）**：stop kiosk→rmmod→`insmod ~/linux-6.18-vdec/.../meson-vdec.ko`（ca46，out-of-tree taints kernel）→start kiosk（MainPID 4466）：**vdec IRQ 0→1856**、START_GATE open、primary 关闭（控制台隐藏）、first_frame 上屏；稳态 20:53:21→31 aus_frames 1129→1735=**606/10s=60.6fps**、sessions2、corrupt=0、age≈35ms、1 次轻微 0xf。**永久缺口（关键）**：insmod 是临时的，下次 reboot 仍自动加载 a6cc08ca 而失效；永久修复需 R3 批准：备份 a6cc08ca→把 ca46 装入 `/lib/modules/.../meson-vdec.ko`→`depmod -a`→再 reboot 确认。**未做**。**验收**：Source Change 卡死修复已验证+目视接受；USB 热插拔 PASS；reboot 服务自启可用但**无人值守 boot 解码仍坏，直到 ca46 永久安装**；K3 尚不能称完整接受。证据 `.codex_tmp/k3_source_change_20261111/{reboot_test,reboot_diag,reboot_irq*,module_compare,reload_test,reload_source_test,reload_source_steady}.log`。

109. **2026-11-11 21:13 HKT 永久模块修复已验证：冷启动自动加载 ca46→kiosk 自启→60.4fps、sessions=1、0 错误**：R3 获批永久安装：备份错版至 `/lib/modules/6.18.59-ophub/.../meson-vdec.ko.a6cc08ca.bak`（`a6cc08ca…`），把源码版 `ca467983…` 装入 `/lib/modules/.../meson-vdec.ko`，`depmod -a` RC=0，installed 哈希核验 `ca467983…`。**boot 事故（警示）**：安装后首次 soft `systemctl reboot`（20:58）**挂死**——黑屏（电源亮）、PC enp4s0 无载波、SSH 10.42.0.11 >5min 不通；用户**硬断电重启**恢复。根因未隔离（可能 warm-reboot 使 VDEC 硬件处于 ca46 boot probe 无法处理的状态，或一次性 fsck/boot 故障）；**冷启动可用，soft-reboot 可靠性需观察**。**硬重启后验证**：服务自启（MainPID 449、NRestarts=0、enabled）、**installed ca46 自动加载**、worker eb1dbb67、**vdec IRQ firing（5842）**、IP 稳定 10.42.0.11、USB Dev002；稳态 21:13:14→26 aus_frames 4999→5724=**725/12s=60.4fps**、**sessions=1（零重建）**、corrupt=0、age≈22–34ms、**0 错误/0 恢复/0 0xf**（迄今最干净）。**验收汇总**：Source Change 卡死修复（离线 A/B+原位+目视）✓；USB 热插拔（进程内恢复 NRestarts=0）✓；冷启动自启+解码+上屏（永久 ca46）✓。**K3≈ACCEPTED_WITH_LIMITATION**。剩余警示/限制：soft-reboot 曾挂死一次（观察）；部分 boot 启动 0xf 突发（内容相关、自恢复）；glass-to-glass 未测；ca46 为 out-of-tree 实验模块（内核包升级可能还原，备份 .a6cc08ca.bak 保留）。可选：补丁 worker+ca46 的新 30min soak。证据 `.codex_tmp/k3_source_change_20261111/{install_module,reboot_verify2,reboot_final_verify,reboot_final_steady}.log`。

110. **2026-11-11 21:23 HKT 提交 0e274eb + 运行时 parity 核验通过**：commit `0e274eb`（main，未 push）“k3: service hardening, Source Change recovery fix, cold-boot module fix”，8 个 intended 文件（AGENTS、service、journald.conf、两份 docs、tests/test_pipeline.py、tools/d3_probe.c、recovery.py），Summary/Verification/Conclusion 结构。密钥扫描：未新增凭据；REMOTE_MACHINE_USAGE.md 既有明文 CM311 密码（已在 HEAD）未动——**建议轮换/移除**并先备替代凭据路径。排除 .codex_tmp/二进制/捕获/sibling repo。**运行时 parity（核验而非重同步，本会话已部署）**：全包哈希矩阵 local-commit vs CM311 `~/mobile_vt` **16/16 一致 RUNTIME_PARITY_OK**（15 vt13_video/*.py + kiosk.yaml）；worker 提交源码 `d3_probe.c 4af75b7c…`→板端 binary `eb1dbb67…`（由该源码构建；远端无 tools/，tools/tests/docs 留本地）；模块 ca467983 已装。清单 `.codex_tmp/k3_source_change_20261111/parity_{local,remote}.txt`。提交时 live 健康（MainPID 449、sessions=1、60.4fps、0 错误/0 0xf）作 post-commit 证据。K3 ACCEPTED_WITH_LIMITATION。

111. **2026-11-11 21:40 HKT CM311 存储与 Armbian 安装可行性只读核验**：远端仍为 Armbian OS 26.11.0 noble / 6.18.59-ophub / S905l3b / meson-gxl，设备树 `Amlogic Meson GXL (S905L3B) MBH-M302A Box`。`/dev/sda2`（USB `SG Flash`，117.2G）为 `/`，`/dev/sda1` 为 `/boot`；eMMC 为 `/dev/mmcblk2`（Biwin，7,474,249,728 B），当前无分区/无挂载，`mmcblk2boot0/1` 各 4 MiB、force_ro=1。`/etc/ophub-release` 与 `/etc/model_database.conf` 明确列出 `MODEL_ID=127`、`MODEL_NAME=M302A,M304A,CM201-1,CM211-1,CM311-1`、`SOC=s905l3b`、`FDTFILE=meson-gxl-s905l3b-m302a.dtb`、`UBOOT_OVERLOAD=u-boot-s905x-s912.bin`；故 ophub Armbian 可安装且已在 USB 运行。`armbian-install` 存在，支持从 USB 安装到 eMMC；`/usr/bin/ampart` 存在，s905l3b 布局预留 117+512 MiB，eMMC 根分区约 6.3 GiB（无 ampart 的 fallback 为 128+512+720 MiB，约 5.6 GiB），而当前根复制集（etc/home/opt/root/selinux/srv/usr/var）约 15.3 GiB，直接安装空间不足；需先清理/迁移 `~/mobile_vt`（8.0G，其中 captures 4.2G、.codex_tmp 3.2G）及内核/FFmpeg 构建树，或继续使用 USB 根。当前 `uEnv.txt` 使用 `meson-gxl-s905l3b-m302a-gxl-test.dtb`，安装脚本会改为普通 `meson-gxl-s905l3b-m302a.dtb`，安装后需验证/必要时改回。本轮仅只读，未安装、未 reboot、未改远端文件。

112. **2026-11-12 HKT 阶段总结 + CM311 全量部署手册文档化（仅文档，无运行时变更）**：`docs/REMOTE_MACHINE_USAGE.md` 新增当前阶段快照与完整部署 runbook。阶段结论：K3 为 **ACCEPTED_WITH_LIMITATION**；D3-0/D3a/D3b/D3c、Source Change 修复、USB 热插拔、systemd kiosk、ca46 永久模块、冷启动 ~60.4fps/sessions=1/0 错误已验证；剩余 `0xf` 内容相关冻结（约 217–283ms 恢复）、启动 `0xf` 突发、soft reboot 曾挂死一次、glass-to-glass 未测、最终 `eb1dbb67`+ca46 组合未做新 30min soak、kiosk journal 易失、远端非 Git 仓库、eMMC 未安装。部署手册覆盖：保留 USB 根 vs eMMC 安装的决策与风险；Phase 0 备份/预检（含 SHA256 清单）；Phase 1 `sudo armbian-install`（MODEL_ID=127、ext4、约 6.3GiB 容量上限、需先腾出约 9GiB、DTB 会被改写为普通 m302a、eMMC bootloader 可能改变启动优先级）；Phase 2 apt 工具链；Phase 3 ca46 模块构建/安装/冷启动验证；Phase 4 自定义 shared FFmpeg + PyAV venv 构建与 ldd/codec 验收；Phase 5 应用/udev/service 部署；Phase 6 验收；Phase 7 回滚。**证据措辞**：本轮无 CM311 写入、无服务重启、无 reboot、无模块重载、无 live；只读 SSH 探测仍因公钥未授权 RC=255（本窗口未用 askpass），故 runbook 依赖既有已验证证据，并在需现场复核处明确标注。**未决**：eMMC 安装尚未执行；内核模块构建命令按标准 `make -j4 M=drivers/staging/media/meson/vdec modules` 记录，历史确切命令未留档，下次干净重建须在目标机确认。下一步：用户决定 USB vs eMMC；若 eMMC 则 R3 批准、腾空间、安装、冷启动并验证 DTB/SSH/HDMI/模块/服务；可选补 30min soak 与 glass-to-glass。

113. **2026-11-12 14:59 HKT G2 备份验证 PASS（无 eMMC 写入）**：备份根 `/home/billieguo/cm311-deployment/backups/cm311-sg-20261112_121131`（约 12 GiB；`sg-rootfs.tar` 5.4G、`sg-boot.tar` 159M、`codex_tmp.tgz` 965M、`captures.tgz` 3.5G 等）。归档 `tar -tf` 10/10 RC=0、`.tgz` `gzip -t` 全 RC=0、stderr 0；`SHA256SUMS` 28/28 OK（原 27 项 + 补入顶层链接归档）。抽样恢复 worker/config/ca46/service/boot：恢复文件 17/17、直接 boot 副本 4/4、跨归档 6/6 全 MATCH，模式保持；worker `eb1dbb67…`、config `d4d155f2…`/`1a6160d1…`、ca46 `ca467983…`、service `15ade4bb…`、uEnv `2b488bb1…`、DTB `1a568548…`/`6bdcf618…`。补入 `sg-rootfs-toplinks.tar`（`bin/lib/sbin -> usr/...`，SHA256 `f6847974…`），因原 rootfs tar 仅含 `etc/home/opt/root/srv/usr/var`。**关键差异**：实际安装 udev 规则是 `/etc/udev/rules.d/99-vt13.rules`（`9509a4c1…`，MODE/GROUP/uaccess），与仓库 `udev/99-vt13-video.rules`（`6d9b78ee…`）不同；G1 的 `MISSING /etc/udev/rules.d/99-vt13-video.rules` 是文件名误判，部署应保留已安装规则。`codex_tmp.tgz` wrapper 聚合状态 1 系活动目录变化，归档读取/抽样恢复通过。证据 `.codex_tmp/emmc_deploy_20261112/g2/{archive_readability_20261112_145703.txt,restore_verify_corrected_20261112_150929.txt,G2_REPORT.md}`；报告副本在备份根。未启动 USB/HDMI/无线，未重启/重载模块，未写 eMMC。下一步 G3/G4，G5 需明确批准。

114. **2026-11-12 17:16 HKT G3/G4 eMMC 部署审计完成，G5 待明确批准（无 eMMC 写入）**：G3 **建议通过**：远端 eMMC `/dev/mmcblk2` 为 Biwin `7,474,249,728 B`，审计时无分区/挂载；选择性 tar 流精确 `3,662,858,240 B`、90,723 成员，含 `vt13_video`/`config`/`build/d3`/`.venv-v4l2`/service/journald/udev/ca46/`gxl_hevc.bin`，排除 captures/live_runs/.codex_tmp/kernel/FFmpeg 源码/toolchains；加 FFmpeg shared `install/` 21,660 KiB 与 kiosk helper 384 KiB 后 payload `3,685,431,296 B`（3.432 GiB）。ampart 成功布局 root `6,814,695,424 B`（6.347 GiB，余 2.914 GiB），fallback root `6,048,186,368 B`（5.633 GiB，余 2.200 GiB），均高于 1 GiB 阈值但 ext4 元数据待 G6 实测。原 `/usr/sbin/armbian-install` `defc9646…` 未改；patched installer `1ed75849…`、patch `6c8dcfdf…`、exclude manifest `e6d978bc…`，远端哈希一致且 `bash -n` OK；patch 强制 `-gxl-test` DTB、tar exclude、FFmpeg install、`.codex_tmp` 775、KMS helper 和关键文件 fail-closed。安装器预期源盘副作用：重建 machine-id、`/ddbr/install`、`/usr/lib/u-boot/mybox-bootloader.img`（eMMC 前 4 MiB 备份）；不改源 `/boot`。**G4 建议以受控风险通过**：eMMC 用户区 `0x200` 有 `@AML`/gxl 2020-06-22 bootloader，boot0/boot1 为零且 `force_ro=1`；MODEL_ID 127、uEnv `2b488bb1…`、普通/`-gxl-test` DTB `1a568548…`/`6bdcf618…`（差异仅 HDMI 节点）、zImage `4b7b8882…` TEXT_OFFSET 0108、`boot-emmc.cmd` mmc `2 1 0`、u-boot candidate `207cdbe1…`；ca46 `ca467983…`、vermagic 匹配、modules.dep/alias 含 gxl-vdec、固件 `f1336295…`；worker 仅 libc、PyAV RUNPATH 指向 FFmpeg shared install；service `15ade4bb…`、journald `f39e019b…`、实际 udev `9509a4c1…`（与仓库源不同，保留实际规则）。汇总报告 `.codex_tmp/emmc_deploy_20261112/g3g4/G3G4_REPORT.md` SHA256 `1d54fbfa…`，证据清单 `EVIDENCE_SHA256.txt` SHA256 `711d9a82…`，`sha256sum -c` 36/36 OK；报告/清单副本已放入备份根。**明确区分**：以上为已验证/建议通过；eMMC 独立启动、启动优先级、HDMI、ca46 自动加载、service 自动启动与 SSH 均**待 G6 实测**。本轮未写 eMMC、未停服务、未 reboot、未重载模块、未启动 USB/HDMI/无线。G5 需设备持有人明确批准；下一步按 runbook 执行 patched installer，选择 MODEL_ID 127、rootfs 1（ext4），完成后 `poweroff`、拔 SG USB、冷启动。

115. **2026-11-12 19:16 HKT G3/G4 最终最小运行时 payload 复核；G5 仍待批准（无 eMMC 写入）**：本条**明确取代 item 114 的 payload 与运行时数字**。最终 root tar 流 `2,853,621,760 B`、`61,468` 成员；安装后新增 `kms_render`+源码 `88,621 B`、service 替换 `+250 B`、`/etc/modules-load.d/vt13-vdec.conf` `11 B`，**最终 root 文件 payload `2,853,710,642 B`（2.6577 GiB）**，比旧 `3,685,431,296 B` 少 `831,720,654 B`（793.2 MiB）。目标运行时改为系统 `/usr/bin/python3` + 系统 dist-packages（含系统 PyAV 11.0.0）与系统 FFmpeg 共享库；排除 `.venv-v4l2` 和自定义 `ffmpeg-6.1.1-v4l2-shared/install`；worker 后端不导入 PyAV，native `build/d3/d3_probe` 仅依赖 libc。reviewed service `ExecStart=/usr/bin/python3 ...`（`3ed77408…`，842 B）；CM311 静态 import/config 检查为 `backend=worker`、`codec=hevc_v4l2m2m`、`av=False`，但**尚未在 eMMC 上作为 service 运行**。最终 installer `90cb0390…`（30,340 B）、patch `175920b5…`（4,529 B）、exclude `58b8fe24…`（1,397 B）；原 `/usr/sbin/armbian-install` `defc9646…` 未改。四文件已暂存 `/home/billieguo/mobile_vt/.codex_tmp/emmc_deploy_20261112/g5/`，远端 SHA256 与本地一致且 `bash -n` RC=0；`/ddbr` 当前不存在（安装器创建），`/dev/mmcblk2` `7,474,249,728 B` 无分区/未挂载，`/` `/dev/sda2` ext4、`/boot` `/dev/sda1` vfat，service active `MainPID=447`/`NRestarts=0`。容量：ampart 成功 root `6,814,695,424 B`、未计元数据余 `3,960,984,782 B`（3.6890 GiB）；fallback root `6,048,186,368 B`、余 `3,194,475,726 B`（2.9751 GiB）；boot 为独立 512 MiB FAT32，G6 必测 `df -hT /`、`df -hT /boot`、`df -i`。**G3 建议通过**最终最小 payload（附注：未在 PC 整包展开 61,468 成员，使用远端实际 tar 流与安装器 fail-closed 检查）；**G4 建议以受控风险通过**，相对旧结论的关键变化是系统 Python/系统 FFmpeg 替代 PyAV venv/自定义 FFmpeg；eMMC 独立启动、启动优先级、HDMI、ca46 自动加载、service 自动启动、USB hotplug、SSH 均**待 G6**。报告 `.codex_tmp/emmc_deploy_20261112/g3g4/G3G4_REPORT.md` SHA256 `82ee6c50…`，证据 `EVIDENCE_SHA256.txt` `6baab39d…`，`sha256sum -c` 30/30 OK；旧 17:16 报告保留为 `G3G4_REPORT_20261112_1716_superseded.md`，备份根中的 G3G4 副本仍为 17:16 版本、不得用于 G5 审批。本轮未写 eMMC、未停服务、未 reboot、未重载模块、未启动 USB/HDMI/无线。G5 **未执行**，需明确批准后按 runbook §8.3 执行，输入 `127`、`1`（ext4），成功后 `sync`+`poweroff`、拔 SG USB、冷启动进入 G6。

116. **2026-11-12 21:33 HKT G5 三项最终确认完成；只读 preflight 通过，G5 仍未执行（无 eMMC 写入）**：本条记录 G5 执行前的最终审查，不替代 G0–G4。**`mybox-bootloader.img` 来源/适用性**：安装器 `create_partition()` 在分区前执行 `dd if=/dev/mmcblk2 of=/usr/lib/u-boot/mybox-bootloader.img bs=1M count=4 conv=fsync`，因此该文件是**同一台 CM311 当前 eMMC 用户区前 4 MiB 的 vendor bootloader 备份**，不是通用 U-Boot，也不是完整磁盘镜像；当前该文件不存在，`/etc/ophub-release` 的 `MAINLINE_UBOOT=''`、`BOOTLOADER_IMG=''`，installer 会走 mybox 回写分支。当前 eMMC 用户区前 4 MiB、`mmcblk2boot0`、`mmcblk2boot1` 均为 `f61b153c…90262`，用户区 `0x200` 有 `@AML`、`gxl` 头。正确恢复语义应保留 G5 新 MBR 分区表：`dd if=... bs=1 count=444` 恢复 0–443，`dd if=... bs=512 skip=1 seek=1 count=8191` 恢复 512–4194303；不要把 `dd bs=1M count=4` 当作未经验证的通用恢复命令，因为它会把备份时的旧 MBR/分区表一并覆盖。Wrapper 安装后会验证目标 0–443 和 512–4194303 与备份一致、MBR `55aa`、`@AML` 存在，并把 `mybox-bootloader.img` 与安装后 MBR 首 512 B 导出到 PC。**Patched installer 复核**：目标锁定逻辑通过 `lsblk` 找 `mmcblk*boot0`，否则排除当前 root 后找 mmc；当前唯一候选 `/dev/mmcblk2`；Wrapper 额外 fail-closed 锁定唯一 eMMC、精确 `7,474,249,728 B`、源 `/dev/sda2`/`/dev/sda1`、目标无挂载、boot0/boot1 各 4 MiB 且 `force_ro=1`。选择性复制仍为 `COPY_SRC="etc home opt root selinux srv usr var"` + `/ddbr/emmc-exclude.txt`；`/boot` 不进 root tar，由 installer 单独写 512 MiB `BOOT_EMMC`。service 安装到目标 `/etc/systemd/system/vt13-kiosk.service` 与 `/home/billieguo/mobile_vt/deploy/vt13-kiosk.service`，源系统已有 enable symlink，tar 复制后保留；Wrapper 检查 target unit、`ExecStart=/usr/bin/python3 ...`、`Environment=VT13_ASYNC_USB=0`、`User=billieguo`、`Restart=always`、`WantedBy=multi-user.target` 和 enable symlink。源 SG USB 预期副作用仅：重建 `/etc/machine-id` 与 `/var/lib/dbus/machine-id`；重建 `/ddbr/install` 并 `chmod 777 /ddbr`；创建 `/usr/lib/u-boot/mybox-bootloader.img`；Wrapper 先写 `/ddbr` 4 个 reviewed 文件。源 `/boot` 内容不修改；installer 依赖工具均已存在，预计走 `Dependency check completed` 分支而非 apt 安装。**Wrapper/runner 修订**：新增 `deploy/g5-install-wrapper.sh` SHA256 `1bef8ba4…4257d` 与 `deploy/g5-run-from-pc.sh` SHA256 `c3ef51f0…f9af8`，二者 `bash -n` RC=0；Wrapper 增加 source `/boot` 七项哈希（安装前后各一次）、KMS helper `a071cfed…`/`fbd8c439…`、所需命令完整性检查、目标 KMS helper 可执行检查、安装后源 `/ddbr`/`/boot`/KMS 复核、bootloader/MBR 导出及尺寸校验；runner 在 PC 校验 Wrapper 本地/远端哈希，成功后回传 `armbian-install.log`、`postinstall-evidence.txt`、`mybox-bootloader.img`、`mbr-first512.bin` 并逐文件校验，最后才 `sync`+`poweroff`。**最终只读 preflight 证据**：本地 `.codex_tmp/emmc_deploy_20261112/g5_pc_20261112_213308/`，`preflight.txt` SHA256 `41f62d3b…0ba51`、`g5-result.env` `8921c5a8…157d0`、`preflight-session.log` `2df2bae7…2ec40`；远端 `~/mobile_vt/.codex_tmp/emmc_deploy_20261112/g5/run_20261112_213343/` 的 `preflight.txt`/`g5-result.env` 与本地 SHA256 相同；远端 Wrapper `1bef8ba4…`；`/ddbr` 仍不存在，eMMC 无挂载，`vt13-kiosk.service` active。**未执行**：未写 eMMC、未停服务、未 reboot、未重载模块、未启动 USB/HDMI/无线。G5 仍需明确执行授权；获授权后从 Ubuntu PC 运行 `cd /home/billieguo/billie_guo/src/rm/mobile_vt && bash deploy/g5-run-from-pc.sh`，交互输入 `127`，随后 `1`（ext4，不选 2/btrfs）。G6 首次启动必须先拔掉 SG USB，再冷启动，确认 `/` 为 `/dev/mmcblk2p2`、`/boot` 为 `/dev/mmcblk2p1`，不能把插着 SG USB 的正常运行当作 eMMC 成功。

117. **2026-11-12 21:33 HKT 更正 item 114 的 boot0/boot1 描述**：item 114 中“`boot0/boot1` 为零”不准确。当前实测 `mmcblk2boot0`/`mmcblk2boot1` 的 4 MiB 内容 SHA256 均为 `f61b153c…90262`，与 eMMC 用户区前 4 MiB 相同；4 MiB 全零的 SHA256 是 `bb9f8df61474d25e71fa00722318cd387396ca1736605e1248821cc0de3d3af8`。`force_ro=1` 仍成立，G4 其余结论不变。
118. **2026-11-12 22:12 HKT G5 授权后最终只读 preflight PASS；尚未写 eMMC**：用户明确授权执行 G5。Ubuntu PC 以 `bash deploy/g5-run-from-pc.sh --preflight-only` 经交互式 SSH 运行 reviewed wrapper；`G5_PREFLIGHT_OK`、`G5_PREFLIGHT_ONLY_COMPLETE`，未停 kiosk、未写 eMMC、未 reboot、未重载模块、未启动 USB/HDMI/无线。Wrapper 校验通过：`/dev/mmcblk2` 容量 `7,474,249,728 B`；源 `/`=`/dev/sda2` ext4、`/boot`=`/dev/sda1` vfat；目标无挂载；用户区前 4 MiB、`mmcblk2boot0`、`mmcblk2boot1` 均为 `f61b153c…90262`；SG USB `/boot` 七项、KMS helper、installer/patch/exclude/service 四件套哈希全部匹配。PC 侧 G2 备份 `/home/billieguo/cm311-deployment/backups/cm311-sg-20261112_121131` 复验 **28/28 OK**。远端复核仍为 `armbian/aarch64/6.18.59-ophub`，kiosk active、MainPID=447、NRestarts=0；`/dev/mmcblk2` 当前无分区表，故 `BOOT_EMMC` 起始位置将在安装后由 wrapper fail-closed 校验为 ampart `122683392` B（117 MiB）或 fallback `134217728` B（128 MiB），两者均 >4 MiB。UART 工具 `picocom` 可用；PC 当时未枚举 `/dev/ttyUSB*`，物理串口/恢复设备可用性按用户授权记录。证据：本地 `.codex_tmp/emmc_deploy_20261112/g5_pc_20261112_221209/`，`preflight-session.log` SHA256 `64c6c9f2…b3a`、`preflight.txt` `b134db8e…1cf`、`g5-result.env` `773e939e…ab0`；远端 `~/mobile_vt/.codex_tmp/emmc_deploy_20261112/g5/run_20261112_221223/`。下一步：运行正式 installer，按顺序输入 `127`、`1`（ext4），成功后保存/校验证据并 `sync`+`poweroff`，停在 G6 前。

119. **2026-11-12 22:41 HKT G5 installer RC=0 完成 eMMC 写入；wrapper 后置校验误报 FAILED，尚未 poweroff**：正式安装按批准输入 `127`、`1`（ext4）执行；installer 日志含 `Successfully repartitioned eMMC with ampart.`、`Installation completed successfully`，`G5_INSTALLER_RC=0`。实际 eMMC 布局正确：`mmcblk2p1` START=239616 sectors（×512=`122683392 B`=117 MiB）、SIZE `535822336 B`、vfat `BOOT_EMMC`；`mmcblk2p2` START=1288192 sectors（×512=`659554304 B`=629 MiB）、SIZE `6814695424 B`、ext4 `ROOTFS_EMMC`；总容量 `7474249728 B`。随后 wrapper 报 `G5_ERROR: unexpected eMMC layout: p1_start=239616 p2_start=1288192`；根因是 `deploy/g5-install-wrapper.sh` 在 `validate_install()` 中把 `lsblk -bno START` 返回的 **512-byte sectors** 当作 bytes 与 ampart/fallback 的字节常量比较（约 line 221-235），不是分区布局错误。wrapper 在 mount/validate 前退出，`g5-result.env` 为 `STATUS=FAILED`，未生成 `postinstall-evidence.txt`，PC runner 未回传日志/evidence/bootloader/MBR，也未执行最终 `sync`+`poweroff`。源 SG USB 未受影响，runner trap 已恢复 `vt13-kiosk.service`（active、MainPID=35832、NRestarts=0）；当前仍未 reboot、未 poweroff、未启动无线/HDMI 验收。下一步：不重装、不改 reviewed installer；以只读方式挂载 eMMC 完成等价校验，导出 installer log、bootloader 4 MiB 和安装后 MBR，回传 PC 校验 SHA256/尺寸后再 `sync`+`poweroff`。若坚持复用原 wrapper 的 `VALIDATED` 路径，只需修正其 START 单位并重新审批 wrapper hash；无需重写 eMMC。

120. **2026-11-12 23:19 HKT G5 PASS：eMMC 安装与只读验证完成，证据已回传校验，poweroff 已发出；G6 未开始**：installer 以 `127`、`1`（ext4）完成，RC=0；ampart 布局实测 `mmcblk2p1` START `122683392 B`（117 MiB）/SIZE `535822336 B`/vfat `BOOT_EMMC`，`mmcblk2p2` START `659554304 B`（629 MiB）/SIZE `6814695424 B`/ext4 `ROOTFS_EMMC`/UUID `61e6bfac-70ad-4d87-92db-a7399341722c`。reviewed installer/wrapper 未改写；原 wrapper 的 `validate_install()` 将 `lsblk START` 的 sectors 当 bytes，导致首次安装后误报 `unexpected eMMC layout`；随后仅使用临时副本（`.codex_tmp/emmc_deploy_20261112/g5_validate_20261112_2245/g5-install-wrapper-validate.sh`，SHA256 `f0d717879663c7acf02968ab3b703a636ee7d2663e70ebf1a80e927a79fc0845`）修正 sectors→bytes，并把不兼容的 `df -i --output=iavail` 改为 `df -i | awk`，执行 `--validate-only` 后得到 `G5_VALIDATED`。证据：`g5-result.env` SHA256 `9ebd188d…ae756`、installer log `80eb6452…da595`、postinstall evidence `0e753462…f808`、bootloader backup `f61b153c…90262`、MBR `d110adfe…b8eae`；本地目录 `.codex_tmp/emmc_deploy_20261112/g5_validation_20261112_231207/`，`SHA256SUMS` 5/5 OK，远端同路径 SHA256 与本地逐一相同。目标 root 可用约 3.64 GB、free inodes 354676；boot/root 文件、uEnv、fstab、root UUID、ca46 模块、firmware、worker、system Python/PyAV、service enable symlink、udev、KMS helper、modules-load 均通过。SG USB 仍为 `/dev/sda2`/`/dev/sda1`，源 `/boot` 七项与 worker/config/KMS/service 哈希未变；G2 备份 28/28 OK。23:19:57 HKT 执行 `sudo sync && sudo poweroff`，SSH 断开，随后 ping 2/2 无响应；未 reboot。当前 G6 未开始；首次 eMMC-only 冷启动必须先物理拔掉 SG USB，确认 `/`=`/dev/mmcblk2p2`、`/boot`=`/dev/mmcblk2p1`、SSH/HDMI/ca46/service/USB/HEVC/稳定显示，再决定是否进入 G7/G8。`K3 ACCEPTED_WITH_LIMITATION` 不变，0xf/启动 burst/soft-reboot/latency/30min soak 仍未因 G5 关闭。

121. **2026-11-13 01:02 HKT eMMC-only 冷启动前置确认 PASS；G6 未开始**：用户物理拔除 SG USB 后，板子于 2026-11-12 23:40:55 HKT 启动（晚于 G5 `poweroff` 23:19:57 HKT）。PC 的 `cm311-local` 共享 DHCP 给出新租约 `10.42.0.253`；旧文档地址 `10.42.0.11` 已不再分配，`nmap -sn 10.42.0.0/24` 仅见 `.1` 与 `.253`。只读核验：`/`=`/dev/mmcblk2p2` ext4 UUID `61e6bfac-70ad-4d87-92db-a7399341722c`，`/boot`=`/dev/mmcblk2p1` vfat UUID `EE59-E094`；`lsblk` 仅见 mmc 设备（`mmcblk2`、p1/p2、boot0/boot1）与 `zram0`，无 USB 块盘；`lsusb` 中 SG Flash `23a9:ef18` **不存在**，DJI `2ca3:1020` 存在；`systemctl --failed` 0 项；`vt13-kiosk.service` enabled/active，`MainPID=433`、`NRestarts=0`；`/etc/modules-load.d/vt13-vdec.conf` 为 `meson_vdec`，`meson_vdec` 已加载 refcount 2；root 可用 3.4 GiB、354636 free inodes，`/boot` 可用 352 MiB。证据 `.codex_tmp/emmc_deploy_20261112/g6_coldboot_20261113_0055/g6_coldboot_precheck.txt` SHA256 `9c0ef4168c13d4ae03618b18fbb075c9b4ae2520d9ebe2a5cad4fa2a1a32bbbe`，摘要 `G6_COLDBOOT_PRECHECK.md`。**结论**：eMMC 独立启动与 SG USB 移除已确认；G6 的 HDMI/KMS、ca46 精确哈希/vermagic、native worker/config、service journal、HEVC 硬解与稳定显示仍待单独授权后执行。未改远端文件、未重启、未启动无线链路；G6 尚未开始，G7/G8 不得启动。

122. **2026-11-13 02:03 HKT G6 eMMC-only 分层验收：PASS_WITH_LIMITATION；HDMI 实际画面和物理 USB 拔插待用户确认；G7/G8 未开始**：用户明确授权 G6 后执行。**已验证**：eMMC-only 冷启动、root/boot/fstab/uEnv/DTB/启动文件哈希、ca46 `ca467983…`（5,550,816 B，vermagic `6.18.59-ophub SMP preempt mod_unload aarch64`）、firmware `f1336295…`、worker `eb1dbb67…`、config `d4d155f2…`、service `3ed77408…`、15 个 `vt13_video/*.py` 哈希、`video/render/plugdev` 权限、system Python 3.12.3/PyAV 11.0.0、V4L2 HEVC output、HDMI-A-1 connected/enabled（1920x1080 可用）。**实时路径**：冷启动服务 `MainPID=433`/worker 907，01:29-01:33 为 122 errors/42 recoveries、362,091 AU、`corrupt=0`；启动 `0xf` 集中在 23:59:13-23:59:30，之后仅在 00:16、00:40、00:57、01:01、01:08、01:13、01:16 出现孤立恢复，01:16:51 后至手动重启无新增。**手动重启**：01:47:23 `sudo -S systemctl restart vt13-kiosk.service` RC=0，新 PID 2935/worker 2937，`NRestarts=0`，SSH 未丢；01:51:24 达 14,101 帧、60 FPS、0 errors/0 recoveries、`corrupt=0`。**USB 恢复**：01:52:12 用内核 `unbind` 模拟拔出；该内核无 `rebind` 属性，改用 `bind` 恢复，`udevadm trigger` 恢复 `/dev/bus/usb/001/004` ACL；01:55:06 USB 重开、60 FPS、`corrupt=0`，`NRestarts=0`。期间 01:51:48 与 01:56:45 各发生一次内容相关 `kernel_0xf` 并自动恢复；01:58:38 服务计数 38 errors/1 recovery（其中 37 条为手动 bind/ACL 时序导致的 USB open 重试）。worker 的 `fps` 字段是自进程启动累计均值，受 USB 断开影响显示 44.6，但 `aus_frames` 仍约 60/s 增长。**限制**：HDMI connector/plane/帧计数已验证，但 agent 不能验证实际像素；物理 USB 拔插本轮用 `unbind/bind` 模拟，未重复真实拔插；残留内容相关 `0xf`、启动 burst、soft-reboot 历史、glass-to-glass 未测、当前 worker+ca46 未做新 30min soak 均未关闭。**证据**：`.codex_tmp/emmc_deploy_20261112/g6_validation_20261113_0110/` 含 `G6_FINAL_REPORT.md`、`g6_layer1_2.txt`、`g6_layer3_6.txt`、`g6_errors.txt`、`g6_service_restart.txt`、`g6_service_restart_steady.txt`、`g6_usb_rebind.txt`、`g6_usb_bind_fix.txt`、`g6_final_state.txt`、`SHA256SUMS`（9/9 OK）；远端同路径 10 文件 SHA256 全匹配；冷启动证据远端 3 文件亦全匹配。未 reboot、未重载模块、未覆盖 golden；未 commit。下一步：请用户目视确认 HDMI 实际画面；如需物理拔插，再做一次并复核 `NRestarts=0` 与视频恢复；确认后再决定 G7/G8。

123. **2026-11-13 02:12 HKT G6 只读 post-check；状态不变，HDMI 目视与物理拔插仍待用户确认**：用户批准并继续后，仅执行只读复核与证据归档，未 reboot、未重载模块、未改源码/config、未停服务。CM311 仍在 `10.42.0.253`；`uptime -s` 与 PID 1 `lstart` 均为 **2026-11-12 23:40:55 HKT**（`who -b` 显示 21:59，为 wtmp 偏差，已记录校正）。`findmnt` 确证 `/`=`/dev/mmcblk2p2` ext4、`/boot`=`/dev/mmcblk2p1` vfat；`lsblk` 无 USB 块盘，DJI `2ca3:1020` 存在，SG Flash `23a9:ef18` 不存在。`vt13-kiosk.service` 仍为 `active/running`，`MainPID=2935`、worker PID 2937、`NRestarts=0`，`ActiveEnterTimestamp=01:47:23`；HDMI-A-1 仍 `connected/enabled`。02:12:20 最新统计为 **78,937 frames、60.0 FPS、38 errors/1 recovery、`corrupt=0`、`backlog_max=0`、sessions=5**；worker `aus_frames=78,849`、`age_p50≈37 ms`。38 errors/1 recovery 是自 01:47 重启以来的累计值，主要来自手动 USB bind/ACL 阶段与两次内容相关 `0xf`，不表示当前链路中断。证据 `.codex_tmp/emmc_deploy_20261112/g6_postcheck_20261113_0211/g6_postcheck.txt` SHA256 `49919c75639340fe65abf68d6ccc2edd25480ab555623126a2c93f03a5054bb6`；本地/远端 `sha256sum -c` OK。**结论不变**：G6 技术路径 `PASS_WITH_LIMITATION`，尚不能升级为视觉 PASS；需用户目视确认 HDMI 持续正确画面，物理 DJI USB 拔插仍为可选的更强验收；G7/G8 暂不启动。未 commit。

124. **2026-11-13 02:39 HKT G6 HDMI 黑屏诊断：解码输出非黑，问题在 KMS 呈现；已临时切到 1080p60，等待目视确认**：用户目视报告 HDMI 为黑屏。只读检查发现解码/USB 路径仍约 60 FPS、`corrupt=0`，但 worker 启动参数没有 `--mode`，沿用了控制台留下的 **1920x1080i** CRTC 模式；当时 DRM 状态为 overlay plane 激活（NV12、1920x1080）、primary plane 关闭、CRTC `1920x1080i`。为隔离原因，使用 **runtime-only** 环境变量 `VT13_WORKER_MODE=1920x1080@60` 与 `VT13_WORKER_DUMP_FIRST=.../first` 重启 `vt13-kiosk.service`（未改源码/config/service 文件）。重启后服务 `MainPID=13894`、worker 14060、`NRestarts=0`；worker 已带 `--mode 1920x1080@60`，DRM 状态变为 progressive `1920x1080` 60 Hz，overlay plane 激活 fb=64，primary plane 关闭。前 3 帧 YUV dump 为 1920x1080 NV12，`Y_min=0`、`Y_max=255`、`Y_mean≈109`，证明解码内容不是黑帧；因此黑屏属于 KMS/模式/平面呈现问题，而不是 HEVC 解码全黑。**尚未确认修复**：需用户再次目视 HDMI；若仍黑，下一步检查 primary/overlay 合成或改用其他模式。证据 `.codex_tmp/emmc_deploy_20261112/g6_hdmi_black_20261113_023851/diagnostic.txt` SHA256 `bd7893fe700936a62ad103b85d49fd78cf415621fd43903ef551fd73e11d54eb`，远端 `sha256sum -c` OK；YUV dump 在远端同目录 `first/`。G6 仍为 `PASS_WITH_LIMITATION`，视觉 PASS 未达成；G7/G8 未启动。未 commit。

125. **2026-11-13 12:37 HKT VT 画面 180° 方向修复：已部署软件旋转，方向待用户目视确认；约 29.7 FPS**：用户报告实时 VT 画面整体 180° 翻转。只读 DRM 探针确认 meson overlay plane 42 **没有 `rotation` 属性**（`drm_plane_create_rotation_property` 未创建），因此采用实验性软件 fallback：worker 分配 4 个 1920x1080 NV12 scratch dumb framebuffer（fb 49–52），先把解码 dmabuf 顺序拷贝到 cached staging，再用 NEON 反向 Y 行和 UV pair，最后把 scratch fb 交给 overlay 扫描；不改码流、解码器或内核。`vt13_video/worker_client.py` 读取 `VT13_WORKER_ROTATION`，服务单元已设 `VT13_WORKER_ROTATION=180`。已部署 `build/d3/d3_probe d1257c49…`（源码 `tools/d3_probe.c 6838cd3e…`），服务 `MainPID=15994`/worker 15996、`NRestarts=0`、active/running；journal 显示 `plane 42 has no rotation property`、`using software 180-degree rotation fallback`、`rotation staging`，DRM overlay fb=49、`imported=no`。30 秒稳定观察约 **29.7 FPS**，`corrupt=0`、0 errors/0 recoveries，`stage_copy_avg_ms≈17.2–17.7`、`rot_copy_avg_ms≈2.8–2.9`、`setplane_avg_ms≈12.2–12.7`。相比未旋转约 60 FPS 有性能回退；瓶颈是 V4L2 dmabuf uncached 读取（板端 benchmark glibc memcpy 25–26 ms vs NEON 17 ms）和 blocking `SETPLANE` 等待。**方向尚未由人目视确认，不能宣称已修复**；若方向仍不对，需确认实际是 180°、垂直翻转还是水平翻转，再调整算法。PC 侧 `python3 -m pytest -q` 为 **53 passed / 38 skipped / 9 subtests**，`git diff --check` RC=0。G6 用户已口头确认 HDMI 有输出、物理热插拔、冷启动和重启均正常；但正式 G8 仍需三次独立 cold boot + 一次 supervised soft reboot，不能过度声称。未 reboot、未 reload `meson_vdec`、未 commit。证据 `.codex_tmp/emmc_deploy_20261112/g7_rotation_stage_20261113_1226/`，`SHA256SUMS` **29/29** 本地/远端匹配，清单 SHA256 `e337cce734d09715d8642ab54e1534dc834f8d19d56619210bed1c8ed70be69a`。

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
| 1080p 0xf 频率（V20） | **2026-11-10 已判定为主机侧自激**：只抓取 60 s 原始流完全干净（10.6 Mbps、0 缺口、0 异常 PS）；解码时出现 0xf，且 async 读线程是主因（关闭后 58–59 fps、0–10 次/40–60 s）；显示为次要因素 | 剩余抖动可用 IRQ/CPU 亲和或 rmrx 独立读取进程继续压；不再是 RF 优先项 |
| 软件解码可行性（V21） | run8/9：0 0xf、0 reset，但 CPU ≈3 核、只读入 1.8–2 Mbps、POC 缺失导致软件错误隐藏整帧灰色；用户确认不可看。`convert_bgr=false` 仅小幅改善 | 不可用；除非源降到 1832/更低码率或换更强 SoC。保留为诊断对照，不作生产路径 |
| 请求 IDR 与 0xf 的关系（V22） | **2026-11-09 22:43-22:48 A/B/A 已判定：不是触发因素**。ON 31/32 abort、OFF 33 abort（差 +4.8%），请求→IRAP p50 79–100 ms；run17 OFF 30/61 s 与 run15 ON 33/61 s 同样接近。旧“请求 IDR 后数帧即 0xf”只是“每个 GOP 数帧后中止”的表现，不是请求导致 | 已关闭；剩余问题是 GOP 内部损伤来源，转 P0-3/P1-3 |
| 性能/延迟目标 | 30–50 FPS、约 1024×576 仍是待确认目标；短样本基准硬件约 24 fps wall，软件约 16–18 fps wall；非稳态 | 用户确认 + CM311 长时实测 CPU/RSS/温度/延迟与画面质量 |
| Agent 免密 SSH（V17） | **2026-11-09 ~13:29 HKT 经用户授权 askpass 解锁**（本窗口）：密码运行时从文档提取、未回显；12:03/12:20/12:26 三次 `BatchMode=yes` 探测均 RC=255，公钥仍未安装 | 卫生建议：人执行一次 `ssh-copy-id -i ~/.ssh/id_ed25519.pub billieguo@10.42.0.11` 并轮换明文密码；askpass 授权仅限本测试窗口，后续会话需重新确认 |
| D3-0/D3a/D3b 真零拷贝（V23） | **已验证**：真实解码帧 dmabuf→PRIME→ADDFB2→KMS overlay，dump 与软件解码逐字节一致；D3a dec 271.6 fps / present 60.12 fps；D3b live worker 58–59 fps（async OFF）。重建闪烁与 0.1–0.2 s 停顿列为后续优化 | 后续：held fb 双缓冲、免 close/reopen、IRAP 等待、剩余 0xf 抖动、10 min soak |

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
