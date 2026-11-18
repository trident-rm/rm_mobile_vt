# CM311 / DJI C5：USB 系统盘影响评估与上游 VDEC/FFmpeg 修复审计计划

> **版本**：2026-11-09（规划稿；未经执行）  
> **面向**：在 Ubuntu PC 上工作的 Codex Agent，通过 SSH 对 CM311 / Armbian 执行只读盘点和经授权的硬件验证。  
> **文档定位**：这是对 `AGENTS.md` 和 `CM311_HEVC_Recovery_Performance_Plan.md` 的**补充专项计划**，不是替代文件，不要求先完成旧计划所有步骤。  
> **约束优先级**：用户当次明确授权与安全边界 > `AGENTS.md` > 两份工程计划中更严格的条款；冲突时停止并询问。  
> **本轮授权范围**：初始仅做只读检查、Ubuntu PC 离线源码研究、分析报告。**不自动进行无线 live 实验、重启、驱动替换、系统盘迁移或正在运行的 release 切换。**

---

## 0. 目标、问题定义、范围

### 0.1 总目标

在保留当前 `mobile_vt` Python USB/DUML/显示控制面、`meson-vdec`、`hevc_v4l2m2m` 及人工操作无线图传顺序的前提下，定位并改善：

1. **高频固件失败**：1920×1080 live 环境约每 2 秒出现 `HEVC_LCU_CHECK status=0xf`，造成冻结。
2. **吞吐与恢复的矛盾**：No-copy 离线曾达 210–249 FPS，但 `POLLERR` 后不能恢复；Copy-Out 可恢复但离线约 45 FPS，无法持续处理真实 1080p60。
3. **USB 系统盘风险**：当前 Armbian 根文件系统位于 USB 硬盘，而非板载储存。确认它是否与 DJI `2ca3:1020` 接收器存在 USB 控制器、供电、I/O latency、Swap、日志写入等竞争。
4. **重复造轮子风险**：审计 Linux 上游 `meson-vdec` 2026 年稳定性补丁与可借鉴的 FFmpeg / Amlogic 解码实现，选出可局部移植、可验证、可回滚的最小改动。

**明确非目标**：立刻换系统盘、直接升级整个 kernel、从头用 Rust 重写 Python、盲目切换 GStreamer、未经验证直接合并全部上游补丁、为了减少 `0xf` 而篡改错误状态或输出不可信帧。

### 0.2 关键判断（必须区分事实和假设）

- **已知事实**：当前系统从 USB 硬盘运行（用户补充）；**未知**：根磁盘具体设备、USB 代际、桥接芯片、是否与 DJI 接收器共用 host controller/hub、Swap 及日志产生率。
- **硬件事实/合理推断**：VDEC 主要通过 SoC/DRAM 完成视频图片解码；USB 根盘不会让 VDEC 的运算单元直接降频。**但** USB 存储 I/O、USB 总线仲裁、供电及调度阻塞会影响端到端持续接收/解码。
- **不能直接推断**：Copy-Out 249→45 FPS 的全部损失来自 `memcpy` 或来自 USB 硬盘。需要在 CM311 上按阶段计时。
- **旧实验**：同类硬件曾有相对干净的 1080p live 样本（run2）；不能因此认定当前数据损坏必定发生在 RF，而不是 AU 重组、DMA/驱动、请求 IDR 或控制策略。
- **上游补丁**：邮件列表公开存在不等于已经合入官方 kernel，更不等于可直接用于本机改过的 `6.18.59-ophub`。必须查版本、修订、反馈、合入和功能重叠。

---

## 1. 与现有两份 Markdown 的执行关系

| 文档 | 作用 | 何时执行 |
|---|---|---|
| `AGENTS.md` | 长期 Agent 行为、安全权限、SSH、备份、人工开启无线图传 | **始终先读，始终遵循** |
| `CM311_HEVC_Recovery_Performance_Plan.md` | 整体性能、恢复、RF/IDR、`0xf`、显示延迟与验收 | **仍然有效**；P0-0 是共同前置条件 |
| **本文** | USB 根盘拓扑和上游源码审计、补丁选型、合并与回归门槛 | **可在旧计划 P0-1/2/3 live 实验之前和期间并行执行** |

### 推荐依赖顺序

```text
[先读 AGENTS.md + 两份计划]
                 |
                 v
[共用环境/版本/根文件系统快照（旧 P0-0 + 新 U0）]
                 |
         +-------+--------+
         |                |
         v                v
[新 U1/U2/U3]        [旧 P0-1/P0-2/P0-3]
源码/拓扑离线审计         受控 live/RF/输入完整性
         |                |
         +-------+--------+
                 v
       [最小修复候选、隔离编译]
                 |
                 v
        [需人工批准的 CM311 验证]
                 |
                 v
    [统一 0xf / FPS / 恢复 / 像素正确性回归]
```

**不需要先做完旧计划**才能查上游补丁；但是在宣布“新补丁解决 live `0xf`”之前，必须拥有旧计划中可比的输入样本、日志口径和基线。源码审计与不触碰设备的 Ubuntu PC 构建可以先做。

---

## 2. 已知现场性能与统一验收口径

### 2.1 现场已报告数据（不是产品承诺）

| 配置/测试 | 已报告指标 | 解释限制 |
|---|---|---|
| No-copy 离线 | 210–249 FPS | 本地 HEVC → V4L2 → null；不代表实时/显示 FPS |
| Copy-Out 离线 | 约 45 FPS | 可恢复，但是否完全由拷贝造成未知 |
| 软件 HEVC | 约 14 FPS | 不适合作为 CM311 上持续 1080p60 备用主路径 |
| run15 live | 195 帧/60s，33 次 abort，1582 次 POLLERR | 195 帧具体是 decoded / filtered / displayed 必须核对计数分母 |
| 恢复 | 中位数约 116 ms | 需确认起止时间戳、样本数和 p95 |
| run4 1832×1032 | 90s 约 1 次 `0xf` | 不可简单归因于分辨率，测试条件可能不同 |
| 1080p run2 | 497/498 帧干净 | 为重要对照证据，先核实完整日志与输入速率 |

### 2.2 基础计算（由上述数据推得）

- 249 FPS → **4.02 ms/frame**；45 FPS → **22.22 ms/frame**；总体相差约 **18.20 ms/frame**（不能视为纯复制耗时）。
- 1920×1080 NV12：`1920×1080×1.5 = 3,110,400 bytes ≈ 2.97 MiB/frame`；60 FPS 单向像素数据约 **186.6 MB/s**（十进制）。这属于 SoC/DRAM 的数据运动，不意味着视频通过 USB 盘传输 186.6 MB/s。
- 若持续 60 AU/s 输入、45 AU/s 可处理，且输入不被提前丢弃/重同步，**理论排队增长 15 AU/s**；必须用 decoder input queue 测量而不能只凭显示窗口判断。
- 33 次 fatal/60 s → **0.55 次/s，约 1.82 秒/次**。

### 2.3 新专项门槛（与旧计划共用、避免双重标准）

| 指标 | 怎么量 | 目标/Gate | 注意 |
|---|---|---|---|
| `USB_ROOT_CONFIRMED` | `findmnt`+`lsblk`+设备 sysfs 链 | 精确确认根盘设备与 bus/port | 必须先做 |
| `SHARED_HOST` | `lsusb -t` + sysfs 拓扑 | 标记 yes/no/unknown | 不仅看物理插口 |
| `USB_STORAGE_ERROR` | kernel 日志中 reset/UAS/I/O error | 可比测试期间 **0 次** | 目标，不是当前事实 |
| `USB_RX_DROPS` | libusb/VT13 序号、读错误、完整 AU | 不增加，尽可能 0 丢失 | 具体计数器取决于已有代码 |
| `FATAL_ABORT_RATE` | 按唯一 kernel abort 事件计数 | 同条件 3×60s 均 0 次为优先 Gate | `POLLERR` 不等于多个 fatal |
| `RECOVERY_RATE` | 一次受控 fatal 后恢复有效图像的比例 | ≥95%，至少 20 次受控测试 | 需要有效 IRAP 与正确图片 |
| `RECOVERY_LATENCY` | fatal 到第一张有效新帧 | median ≤200 ms、p95 ≤500 ms | 不含人工操作时间，口径注明 |
| `DECODE_TPUT` | 离线完整解码/墙钟时间 | 1080p60 至少 ≥72 FPS 余量；工程候选优先 ≥90 FPS | 必须先保证 correctness |
| `COPY_OUT_COST` | get_buffer/copy/props/DQBUF/queue 阶段 p50/p95 | 覆盖已观察总差值 ≥90%，否则列出未解释部分 | 不凭单个 FPS 判断 |
| `BIT_EXACT_NORMAL` | 正常完整参考链 SW/HW FrameMD5 | 基线一致，候选不得回退 | 已损坏输入不能强求 bit-exact |
| `DATA_INTEGRITY` | PC/CM311 SHA256、Git diff、配置快照 | 所有候选可追踪、可恢复 | 不覆盖原始捕获 |

**以上是建议验收目标，不是已经达到的当前性能。**

---

## 3. 权限等级与系统盘安全（强制）

| 等级 | 允许/要求 |
|---|---|
| R0 | 只读：`uname`、`findmnt`、`lsblk`、`lsusb -t`、`cat /proc/...`、`git status`、读取源码/日志；Ubuntu PC 上创建独立分析文件 |
| R1 | PC 上新建分支/源码副本/离线编译及回归；CM311 独立测试目录小体量输出需先检查空间、I/O 和影响 |
| R2 **需批准** | 占用真实 DJI USB、V4L2、HDMI；live 无线开关/请求策略 A/B；可能引起 USB 干扰的磁盘压力测试；停掉当前服务；驱动测试二进制切换 |
| R3 **单次明确批准** | `reboot`、`shutdown`、`rmmod/modprobe`、固件/模块/内核/DTB/bootloader 替换、启动盘迁移、USB unbind/bind、`dd`/磁盘分区/文件系统操作、`apt upgrade`、导致 SSH 中断的网络/电源修改 |

**额外特别规则（因为 rootfs 在 USB 上）**：

1. **禁止未经批准对 USB 系统盘做压力写入、拔插、设备 reset、UAS/usb-storage 驱动切换、文件系统检测修复、SWAP 关闭或系统盘迁移。**
2. 如果从系统盘启动，一次 USB reset 不只是“USB 稍断”，也可能让 rootfs 只读、崩溃或 SSH 彻底失联。
3. 不要将原始码流、debug trace、大量 FrameMD5 或高频 verbose 日志持续写入 CM311 系统盘作为默认策略。优先在 PC 上处理历史数据；需要实时采集的日志选定小体量、限时、有上限的输出，必要时经 SSH 向 PC 传送，**仍需考虑网络与 CPU 开销**。
4. 不假定 `/tmp` 是 RAM；先用 `findmnt /tmp`。`/dev/shm` 通常为 tmpfs，但必须确认容量，不能无限写入。
5. 为任何可能让 SSH 失联的操作制定现场物理恢复方案。无人值守时不得执行 R3。
6. 人批准一次实验，不代表批准一系列之后的 reboot/模块操作；每次变更作用域都要重新审批。

---

## 4. 第一优先级 U0：只读确认 USB 系统盘与 DJI 拓扑

### 4.1 目标

精确回答：

- 真正的 `/` 根分区是 `sda?`、LVM、overlay 还是其他？底层设备是否 USB？
- 系统盘与 DJI 设备是否共享一个 USB **host controller**？是否位于同一 hub/transaction translator？各自协商速率是什么？
- 根文件系统所在磁盘是否使用 UAS 或 `usb-storage`？系统是否启用 Swap 文件/分区？
- 是否存在 USB reset、UAS command timeout、I/O error、文件系统错误、OOM/内存回收？
- live 时是否将高频视频数据和日志写在根盘？是否存在 `fsync`、日志 flush 或频繁随机写？

### 4.2 Ubuntu PC 执行：安全的只读现场清单

只在**确认自己的 SSH 别名或 IP**后执行。不要猜测地址，不要把 `CM311_SSH` 填成未经验证的主机名。

```bash
# Ubuntu PC 终端：必须先填写经确认的 SSH 目标
: "${CM311_SSH:?请先设置 CM311_SSH（例如 export CM311_SSH='user@host'）}"

# 输出仅写到 Ubuntu PC 的新目录，不修改 CM311
PC_RUN_DIR="$HOME/cm311_audit/usb_rootfs_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$PC_RUN_DIR"

ssh -o BatchMode=yes "$CM311_SSH" 'bash -s' <<'REMOTE' \
  | tee "$PC_RUN_DIR/usb_rootfs_readonly.txt"
set -u
printf '\n=== IDENTIFICATION ===\n'
date -Is
uname -a
id
printf '\n=== ROOT MOUNT ===\n'
findmnt -n -o SOURCE,TARGET,FSTYPE,OPTIONS /
printf '\n=== /tmp and /dev/shm MOUNTS ===\n'
findmnt -T /tmp || true
findmnt -T /dev/shm || true
printf '\n=== BLOCK DEVICES ===\n'
lsblk -o NAME,PATH,MAJ:MIN,TRAN,TYPE,FSTYPE,SIZE,MODEL,MOUNTPOINTS || lsblk
printf '\n=== ROOT BLOCK PATH ===\n'
ROOT_SRC="$(findmnt -n -o SOURCE /)"
printf 'ROOT_SRC=%s\n' "$ROOT_SRC"
if [ -b "$ROOT_SRC" ]; then
  readlink -f "$ROOT_SRC" || true
  if command -v udevadm >/dev/null 2>&1; then
    udevadm info -q path -n "$ROOT_SRC" || true
    udevadm info -q property -n "$ROOT_SRC" \
      | grep -E '^(ID_BUS|ID_PATH|ID_MODEL|ID_USB|DEVPATH)=' || true
  fi
fi
printf '\n=== USB TREE ===\n'
if command -v lsusb >/dev/null 2>&1; then lsusb -t; lsusb; fi
printf '\n=== MEMORY / SWAP / STORAGE ===\n'
free -m
swapon --show || true
df -h / /tmp /dev/shm
printf '\n=== IO SNAPSHOT (3 s, non-stress) ===\n'
if command -v vmstat >/dev/null 2>&1; then vmstat 1 3; fi
printf '\n=== RECENT KERNEL USB/STORAGE ERRORS ===\n'
if command -v journalctl >/dev/null 2>&1; then
  journalctl -k -b --no-pager -n 300 2>/dev/null \
    | grep -Ei 'usb|uas|reset|I/O error|blk_update_request|ext4|Buffer I/O|disconnect|under-voltage|voltage' \
    | tail -100 || true
fi
REMOTE
```

如果命令缺少 `lsusb` / `udevadm` / `vmstat`，记录缺失，不要因缺少工具立刻在 CM311 上 `apt install`。若确需安装，先解释风险并申请批准。

**Gate U0**：产出一张可审阅的拓扑表：`rootfs block device → USB bus/port/path/speed` 与 `DJI 2ca3:1020 → USB bus/port/path/speed`；标注 shared host/hub、Swap、存储错误情况、未知项。

### 4.3 出现不同结果时的路径

| 发现 | 优先解释 | 行动 |
|---|---|---|
| 系统盘和 DJI 共用 host/hub | 存储 I/O/排队可能干扰实时 USB | 在 P0-3 的输入时间线上标记磁盘 I/O；先无负载基线，再审批受控 A/B |
| 分属不同 host controller | 直接 USB 总线竞争较不可能 | 仍核查供电、DRAM、CPU/I/O wait；**不宣称彻底无影响** |
| 大量 UAS reset / storage I/O error | 存储/线材/桥接/供电可成为系统稳定性风险 | **停止磁盘压力测试**，保存日志，人工检查连接与供电；禁止 agent 重置根盘 |
| 有 Swap 且 live 发生 swap-in/out | 可能造成调度与响应延迟 | 先记录页面换入换出与 RAM 使用；是否更改 swap 需人工审批 |
| `journalctl` 日志没有权限 | 信息不足 | 不静默猜测；向人请求临时读取权限，不扩大权限范围 |
| `/` 为 overlay/LVM 等 | 根盘路径不直观 | 沿 device-mapper/sysfs 只读追踪真实后端；无法确认则询问人 |
| 设备同 controller 但磁盘空闲、日志无错误 | 共享总线不一定构成性能瓶颈 | 不主动迁移系统，转驱动/FFmpeg 审计 |

**不要做的推断**：共享总线 ≠ 必然 USB 丢包；没有日志 ≠ 一定没有丢包；`0xf` ≠ 根盘 I/O 故障。必须靠时间线建立关联。

---

## 5. 第二优先级 U1：上游 `meson-vdec` 补丁审计（先 PC，零设备影响）

### 5.1 审查源

- **主线：** Anand Moon 于 2026-07-13 提交的 `v7 00/19 media: meson: vdec: Fix lifecycles, race conditions, and stability bugs`。
  - 讨论串：<https://lore-kernel.gnuweeb.org/linux-staging/20260713120840.17427-12-linux.amoon%40gmail.com/T/>
  - 包含：M2M device 生命周期、STREAMON/OFF、recycle thread、ISR / esparser IRQ 同步、workqueue、DMA、VIFIFO、DRM/canvas 等。
- **附加研究（不是可直接替换的 GXL 驱动）：** 2026-10-25 社区 Amlogic 新 stateless 解码驱动 `[PATCH 09/11] ... add HEVC decoding on the HEVC core`：<https://lists.openwall.net/linux-kernel/2026/10/25/864>。
  - **该补丁明确针对 S4 `aml_vdec` 路径**，不能直接应用于 GXL/当前 Stateful `meson-vdec`。
  - 研究价值：代码出现 `H265_PADDING_SIZE (16 * 1024)`，以及 HEVC 微码 / NAL / 输入工作缓冲、错误处理；这与本项目的 Packet81 padding 实验有**研究相关性**，但不是证明同一根因，不能照搬其常量。
- **Linux 官方 V4L2 Stateful Decoder 规范**：<https://cdn.kernel.org/doc/html/latest/userspace-api/media/v4l/dev-decoder.html>。

### 5.2 Codex 必做的来源真实性检查

1. 在 Ubuntu PC 获取邮件列表原始 `mbox`/patch 与完整 thread（保存日期、URL、Message-ID、哈希）。
2. 搜索是否存在 v8/v9/替代 series、review objections、reverts、已合入 commit，不能把 v7 当成最终版。
3. 从 **当前 CM311 真正运行的** kernel version/源码 diff 出发，判断本地是否已有等效逻辑；不要仅靠 `uname -r` 判断是否包含某个补丁（发行版可能 backport）。
4. 每个补丁标注：`absent` / `present` / `equivalent` / `conflicting` / `not-applicable` / `unknown`，并给出本地文件和函数行号。
5. 检查是否触及 `codec_hevc.c` 自定义修补、`vdec.c` 生命周期、`esparser.c` queue，以及本地先前的 firmware/debug 逻辑。
6. 邮件列表系列可能存在审查中的正确性风险；**不允许在未审阅前整套自动 cherry-pick**。

### 5.3 按“问题与补丁作用机制”分组

| 分类 | 优先看的模块 | 对应本项目的潜在收益 | 不可直接宣称 |
|---|---|---|---|
| **U1-A P0** | M2M device lifetime、session open/close、stream on/off、teardown | No-copy `POLLERR/EIO` 后重新打开、decoder worker 再建 | **不保证** firmware `0xf` 下降 |
| **U1-B P0** | IRQ/workqueue/recycle thread、ISR UAF、firmware load race | 减少反复 fatal/reopen 的内核竞态和泄漏 | **不等于**修复完整码流 CABAC 错误 |
| **U1-C P1** | esparser / VIFIFO size / OUTPUT 提交边界 | 有助于排查短 slice、边界读、零填充问题 | 不得把旧 padding workaround 全局应用 |
| **U1-D P1** | vb2 DMA 限制、canvas / DRM / buffer lifecycle | CAPTURE 分配、DMA、Source Change | 不保证提高吞吐或兼容性 |
| **U1-E P2** | EOS、LAST 标志、drain、dynamic resolution | 末帧缺失、重配参考释放 | 与 `0xf`、`POLLERR` 应分开验证 |

### 5.4 交付物与 Gate

**交付**：`upstream_patch_matrix.md`、patch 版本与合入状态、风险排序、最小修复候选（最多 2–3 组）、每组冲突区域和回滚方案、是否需要补充人体操作/现场数据。

**Gate U1**：每个推荐改动有**明确的源码位置、预期修复机制、可复现的失效样本、观察指标**。如果只是概念相关而无验证路径，不进入 CM311 编译部署。

---

## 6. 第三优先级 U2：FFmpeg / LibreELEC / RPi 用户态实现比较

### 6.1 参考实现与范围

- 目前使用的自编译 FFmpeg 6.1.1（实际构建版本需重新记录），重点 `libavcodec/v4l2_m2m_dec.c`、`v4l2_m2m.c`、`v4l2_buffers.c`、`v4l2_context.c`。
- `https://github.com/chewitt/ffmpeg`（LibreELEC / Amlogic 相关分支；**必须确认具体当前分支、提交及其支持的 decoder backend**）。
- `https://github.com/jc-kynesim/rpi-ffmpeg`（Raspberry Pi V4L2 M2M 改进，**不预设直接兼容 GXL**）。
- FFmpeg 主线/相关 Source Change 补丁与官方 Stateful V4L2 规范。

### 6.2 必须分离的三个问题

1. `Source Change`：切换 1832×1032 → 1920×1080 时的旧 CAPTURE AVFrame 引用及丢帧。
2. `Fatal decode`：固件 `0xf`、kernel session abort、V4L2 `POLLERR/EIO` 后的 stop/close/reopen。
3. `Copy-Out perf`：每帧 buffer allocation、DMA 映射 CPU 读、`av_frame_copy`、frame props 及 renderer backpressure。

**不能**用解决问题 1 的 Copy-Out，作为问题 2/3 的根本修复证明。

### 6.3 审查要求

- 绘制 AVFrame / AVBufferRef / V4L2 MMAP/DMABUF 所有权与生命期图，精确标出 fd、mmap、VB2 buffer、引用何时释放。
- 确认 `V4L2_BUF_FLAG_LAST` 与 drain/DRC 的处理顺序，明确 EPIPE 和 EIO 对应状态。
- 对比无拷贝 close/reopen、独立 worker 方案，并明确跨进程图像共享时的 buffer lifetime。**不能把进程即将关闭的 MMAP 指针交给显示进程继续使用。**
- 设计 Copy-Out 微基准：分别量 `DQBUF`、`av_frame_get_buffer`、Y/UV plane copy、`av_frame_copy_props`、return buffer、decode submit、queue wait 的 p50/p95/p99；观察 CPU frequency、memory/swap、IO wait。
- **先离线审查和搭建隔离测试**；若需 CM311 上实际运行特定 FFmpeg 版本，必须 R2 审批。

**Gate U2**：提供至少两条技术路线的证据化比较：

- 路线 A：保留 No-copy，错误后彻底释放当前解码实例（同进程或独立 decoder worker）。
- 路线 B：保留 Copy-Out，定位并减少 18.2 ms/frame 总额外开销（池化、同步、映射、Copy 优化）。

必须说明对 `0xf`、`POLLERR` 恢复和实时 FPS 的**不同**影响，不承诺每一条都能解决全部问题。

---

## 7. 第四优先级 U3：复核 HEVC `0xf` 与新开源代码的输入处理

### 7.1 必须利用的已有样本

- `POC35 → POC50 → POC55` 的独立 GOP 测试。
- 原始 Packet81：POC50 在 LCU404/2040 时 `0xf`；插入 512 B 零填充后 firmware 报完成。
- FrameMD5：原始 SW 与 SW+512 38/38 相同；HW+512 与 HW+8192 38/38 相同；SW 与 HW 在最后 2 帧不一致且该处缺参考。
- POC patch、clone payload、GOP1 POC21 boundary 样本。

### 7.2 审查方向

- 现有 GXL ES Parser 提交的是“真实 payload bytesused”、分配区 size、输入头尾 padding、firmware lookahead、安全防越界空间中的哪些值？
- NAL Annex-B 中 trailer zeros 与 VDEC 内部 FIFO padding 是两种不同层的概念，**不能混为一谈**。
- S4 社区补丁的 `H265_PADDING_SIZE 16KiB` 有何实际调用语义？是在 OUTPUT payload 结尾、DMA workspace 还是驱动的 scratch buffer？请阅读全文后再判断与 GXL 的关系。
- `0xf` 是否只在不完整 AU/参考链出现，还是有完整可软件严格解码、参考完整的样本也可复现？
- 如果确属固件死状态，能否由正确关闭重开 session 恢复？若不行，先排查上游生命周期补丁，不允许无限重启 worker。

**Gate U3**：输出 `0xf` 类型表、触发样本、已排除原因、候选修复作用层（USB/VT13→AU、esparser、HEVC firmware/driver、FFmpeg recovery）及仍需证据。缺参考帧的灰色/绿色 concealment 不应当算作成功解码。

---

## 8. 可选 U4：USB 系统盘的受控影响验证（必须先人工批准）

只有 U0 证明存在实际的总线/供电/IO wait 风险，或 P0-3 显示存储事件与 USB/AU 延迟相关时才启动。不要默认必须做。

### 8.1 A/B 实验设计（一次只改变一个因素）

- A：当前 USB 根盘 + 当前日志策略；视频收发、观看、版本、位置固定。
- B1：**只减少非关键高频持久日志写入**（程序安全支持的开关存在才可启用；先确认 CLI、保护原记录），不改系统盘、不停 Swap。
- B2：针对存储输出，把大文件采集放到 Ubuntu PC 或限量 RAM 暂存（先分析 SSH 传输对 CPU 与延迟的影响）；仍不卸载根盘。
- B3：经人许可，改物理 USB 接线/受电条件；不得热拔 USB 根盘。

要求：对相同配置做 A/B/A、各至少 60s，最好每组 3 次；人工先启动采集，再开无线图传；监测 `usb_bulk_errors`、VT13/AU drops、`0xf`、POLLERR、CPU IO wait、磁盘错误、frames/s、latency p50/p95。设备不能在同一时刻作为多个解码程序的独占资源。

### 8.2 决策分支

| 结果 | 结论范围 | 下一步 |
|---|---|---|
| B 的存储 I/O 减少后，AU drop/`0xf` 同步下降 | 存储侧可能加剧输入链路问题 | 优先调整写入策略、I/O 优先级、日志输出；重复并控制 RF |
| I/O wait 很低且 A/B 近似 | 根盘影响当前症状证据不足 | 不迁移系统，继续驱动修复 |
| 有 USB reset/供电问题 | 系统可用性风险极高 | 人工处理供电/线材/接口；停掉压力实验 |
| 只提高离线 FPS，`0xf` 率不变 | 多半是性能与固件/输入两件事 | 按两个独立 Gate 报告，不宣称全部解决 |
| B 导致断连、rootfs 只读、SSH 丢失 | 故障；不允许自动重试高风险步骤 | 终止后续测试，现场人工恢复，保留日志 |

**不建议把根盘迁移至 eMMC 作为早期实验。** 只有具有可比证据、确认板载存储兼容、可验证备份、外部启动救援与人工 R3 批准后才能另立迁移计划。

---

## 9. 代码变更到部署的通道与人工 Approval

### 9.1 Ubuntu PC 先做的工作

- 建立独立目录（例如 `~/cm311_audit/upstream/`），按固定 commit/tag 克隆公开参考代码、下载 patch；不得修改正在使用的 CM311 构建目录。
- 记录 `git remote -v`、`git rev-parse HEAD`、`git status --short`、`sha256sum`、补丁来源和 license 约束。
- 生成 `git diff --check`、静态分析、可编译性检查、最小测试程序；若进行交叉编译，确认 toolchain architecture、kernel headers、`vermagic`、依赖 ABI。
- Ubuntu x86_64 上的“编译成功”**不等于** ARM64 CM311 上的模块可加载，也不等于 VDEC 行为正确。

### 9.2 CM311 前置验证

- 首先核对当前设备内核 build-id/`uname -r`、驱动是 built-in 还是 loadable module、运行二进制/库的真实 hash。
- Candidate 文件经 SSH/rsync 先放独立 staging，校验 SHA256，绝不覆盖 release。
- 普通文件 staged copy 也应控制容量，因为根盘是 USB；若要在 CM311 本地大规模编译、长时日志、部署新模块，先提示影响并申请授权。
- 如果需要更换内核/模块/固件、`rmmod`、`reboot`，**必须 R3 单独申请**：给出精确命令、依赖、预计失联范围、备份与人工救援方法。

### 9.3 每个候选的最小测试矩阵

| 场景 | 必做观测 | 失败分支 |
|---|---|---|
| 正常 HEVC 1832×1032 | FrameMD5、FPS、kernel log | 若回归，禁止进入 live |
| 正常 HEVC 1920×1080 | FrameMD5、CPU/内存、FPS | 若 <72 FPS，优化/回退并说明 workload |
| 1832→1920 Source Change | LAST/EOS、输出数、AVFrame ref 释放 | 丢最后帧/卡 ref → 退回隔离调试 |
| 已知 POC50/POC21 异常 | `0xf`/LCU、错误处理、是否输出 corrupt | 不能用“RC=0”假称图片正确 |
| Fatal `POLLERR/EIO` 重建 | fd close/open、recover time、20 次成功率 | driver 仍 dead → 停止高频重试并审 kernel lifecycle |
| 连续 60s live、随后 10–30min | abort、AU drop、FPS、队列延迟、温度、存储 I/O | 任何失联/USB reset 立即停止并报告 |

正式发布以**安全与像素正确性优先于最高 FPS**：不能用隐藏错误的办法达到性能数字。

---

## 10. 人工无线实验包的交接标准（只在 R2 获批后）

由于现场的正确顺序是**先启动接收程序，之后再打开无线图传**，Agent 必须：

1. 从 `mobile_vt` 源码/`--help`/当前已验证的命令找到真实 release 启动方式，不猜参数。
2. 在每次 R2 请求中提交 **一段完整、可复制粘贴的 SSH / tmux / Bash 命令**；不得写“将 `<command>` 替换为你的程序”而不先确认实际 CLI。
3. 先准备日志文件、超时、安全退出、run_id 和输出路径；在接收进程确认 Ready 后，清楚显示 `READY — 可以开启无线图传`。
4. 由人**亲自开启无线图传**，Agent 不擅自改配对、信道、RF 功率或重启发射端。
5. 测试结束后先按约定停止接收进程；确认用户态与内核错误，没有活动 capture fd 或未结束的子进程。
6. 通过 SSH/rsync 拉回**选择的**日志和样本到 Ubuntu PC；大体积视频文件按容量、风险、带宽限制分批传输，确认校验和。
7. Agent 自动完成汇总报告和异常分支判断；不能自行开始下一轮 R2/R3 实验。

**若未确认实际 CLI、USB topology 或已经存在的 live 进程，Agent 应暂停 live，向人提出最少的明确问题，不要凭猜测构造命令。**

---

## 11. 两份计划的联合执行排程（每一步有 Gate）

| 优先级 | 阶段 | 可与旧计划并行？ | 执行端 | 是否需要现场许可 | Gate / 产物 |
|---|---|---|---|---|---|
| **P0** | U0 USB 根盘/控制器/Swap/日志只读盘点 | 与旧 P0-0 合并 | PC→SSH CM311 | 否 | `usb_rootfs_topology.md` |
| **P0** | U1 补丁版本/合入/本地差异审计 | 是 | Ubuntu PC | 否 | `upstream_patch_matrix.md` |
| **P0** | U2 FFmpeg V4L2 生命周期与 Copy-Out 代码对照 | 是 | Ubuntu PC | 否 | `ffmpeg_lifecycle_comparison.md` |
| **P0** | 旧 P0-1 I-frame ON/OFF 对照 | 与 U1/U2 并行 | CM311 + 人 | **R2** | abort 差异、完整性差异 |
| **P0** | 旧 P0-2/3 RF/AU/POC/`0xf` 证据链 | 是 | PC + CM311 | 部分 R2 | 有根因分类的时间线 |
| **P1** | U3 `0xf`/padding 与新开源 HEVC 代码比较 | 可离线并行 | Ubuntu PC | 否 | `0xf` 层次诊断表 |
| **P1** | 旧 P1-1 Copy-Out 段耗时剖析 | 依赖共同快照 | PC + ARM | CM311 测试 R2 | 18.2 ms 差异分解 |
| **P1** | 旧 P1-2 No-copy 受控实例重建 | U1/U2 后 | CM311 | R2/R3 | ≥95% 恢复、FPS 回归 |
| **P2** | U4 USB 根盘受控 A/B | **仅当 U0 有证据** | CM311 + 人 | R2/R3 | 有/无存储竞争结论 |
| **P2** | 候选 kernel/FFmpeg 小补丁 | 依赖 U1/U2/U3 | PC 构建→CM311 | R2/R3 | 逐候选可复现实验 |
| **P3** | 旧 P2/P3 延迟、长时稳定、发布 | 前述 Gate 后 | CM311 + PC | R2/R3 | 1080p60 全链路验收 |

**禁止合并门槛**：只达到 `fps=200+` 但无法在 `0xf` 后恢复，不能算任务完成；只有 `RC=0` 但末帧错误，不能算图片正确；只解决 No-copy EIO、不降低输入损坏导致的 abort，也不能宣称 live 已稳定。

---

## 12. 当审计出现意外结果时的策略

| 发现 | 改变策略 |
|---|---|
| 19 补丁的大部分已经 backport | 不重复移植，审计本地差异和当前导致 `POLLERR` 的更具体原因 |
| 19 补丁互有冲突、upstream review 否定某些修复 | 记录 review，拒绝套用；挑最小且经过审查的修复或自写等效补丁 |
| S4 stateless 新驱动中存在良好 padding 方案 | 只借鉴输入边界 / 保护空间设计；先证明与 GXL 语义相同，**不直接复制 16KiB** |
| 上游 FFmpeg 已处理 Source Change，但本地仍卡 | 查旧 CAPTURE 引用、显示帧所有权、实验 refcount patch；用 trace 对照 |
| No-copy 独立 worker 重启仍失效 | 可能是 kernel session teardown，而非用户进程寿命；先做 U1-A/B，不无限重试 |
| Copy-Out 最重耗时发生在映射或同步 | 优先分析 DMA API、cache、驱动分配；不要直接更改 cacheability |
| CPU copy 并非主要开销而是 queue block | 优先调帧所有权、释放时序、buffer 数和背压；避免盲目重写 SIMD memcpy |
| USB root disk 与 C5 共用 host，出现 reset/I/O error | 先处理 USB 链路与供电稳定性；禁止 hot-unplug root disk |
| USB root disk 独立且空闲，RF 改善显著 | 将优先级回归旧 P0-1/2，勿盲目迁移系统 |
| 全部样本干净，仍重复 `0xf` | 升级 GXL 固件/ES Parser 方向的最小复现；需 R3 批准变更 |
| 只有 live 1080p60 不稳定，离线正常 | 查 AU 时序、输入积压、发射端 GOP、USB Bulk 读取节奏，不能先宣称硬件不支持 |

---

## 13. Agent 交付报告格式

每个阶段固定产出以下字段，Markdown 中不可缺：

```text
阶段 ID / 时间 / 操作端 / 审批级别
变更前后：kernel + module + FFmpeg + Python + config 哈希
输入：源文件/样本/命令/分辨率/帧率/原始数据哈希
已确认事实（附日志行号/commit/URL）
推断与假设（写明不确定性）
数值指标：分母、时间窗、单位、p50/p95、是否有效
PASS / FAIL / BLOCKED（对照 Gate）
本次写入：完整路径和变更 diff；无写入也明确标注
风险：USB rootfs、SSH、数据、V4L2、HDMI、固件
预期效果与实际效果
若 FAIL：下一条有依据的技术路线，而不是盲目重试
需人提供的信息与需审批的精确操作
回滚方法：命令 + 校验 + 人工现场救援条件
```

## 14. 开始执行时给 Codex 的第一条任务

> 阅读 `AGENTS.md`、`CM311_HEVC_Recovery_Performance_Plan.md` 和本文件。先完成旧 P0-0 与新 U0 的只读盘点，特别确认 rootfs 位于 USB 哪个设备、DJI `2ca3:1020` 是否与其共用 host controller/hub、Swap 和持久写盘情况。随后在 Ubuntu PC 离线完成 U1 的 19 补丁来源/合入/本地差异审计，以及 U2 的 FFmpeg V4L2 生命周期审计。不要提前开启 live、不要改变设备/boot/systemd/kernel/firmware、不要迁移 USB 系统盘，也不要为了实验 reboot。每阶段按 Gate 报告。若需要 live 操作，先从真实 CLI 生成准确完整的可复制命令，说明必须“接收程序先启动、无线图传后开启”，列明 R2/R3 风险并等待我的批准。若信息模糊，提出具体、最少量的问题，不要猜设备或 CLI。

---

## 15. 参考来源与适用性说明

1. Linux V4L2 Stateful Decoder Interface（fatal `-EIO`、关闭重开、source change、buffer semantics）：<https://cdn.kernel.org/doc/html/latest/userspace-api/media/v4l/dev-decoder.html>
2. 2026-07-13 Anand Moon `[PATCH v7 00/19] media: meson: vdec: Fix lifecycles, race conditions, and stability bugs`：<https://lore-kernel.gnuweeb.org/linux-staging/20260713120840.17427-12-linux.amoon%40gmail.com/T/>
3. 2026-10-25 Christian Stefan Kövér-Draxl `[PATCH 09/11] media: amlogic: vdec: add HEVC decoding on the HEVC core`（**S4、新 stateless driver，不能直接替代 GXL**）：<https://lists.openwall.net/linux-kernel/2026/10/25/864>
4. Raspberry Pi FFmpeg V4L2 M2M 分支：<https://github.com/jc-kynesim/rpi-ffmpeg>
5. LibreELEC / Amlogic FFmpeg 参考：<https://github.com/chewitt/ffmpeg>
6. 当前项目根目录 `AGENTS.md` 与 `CM311_HEVC_Recovery_Performance_Plan.md`（以真实 repo 中存在的版本为准）。

> 文档没有对 CM311 发起命令；全部指标和 Gate 要由 Codex 用实际日志确认。本计划不意味着上述外部 patch 已合并或已验证适用于当前 CM311。
