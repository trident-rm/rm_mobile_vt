
# CM311-1S：VT13 USB 图传系统部署到 eMMC — 完整执行计划

版本： v2.1 — 2026-11-12\
当前状态： `G0–G4 AUDIT COMPLETE — G3 FINAL MINIMAL PAYLOAD — G4 RECOMMENDED PASS_WITH_APPROVED_RISK — G5 READY, AWAITING EXPLICIT APPROVAL`\
目标硬件： CM311-1S / Amlogic S905L3B\
目标系统： Armbian / 内部 eMMC\
当前系统： SG USB 启动的 Armbian\
执行者： Worker\
人工审批： 设备持有人

## 0. 部署目标与核心原则

### 0.1 最终目标

将已经运行成功的 VT13 USB 图传接收、硬件解码和 HDMI 显示系统，从当前 SG USB 启动环境部署到 CM311-1S 的内部 eMMC。

最终系统应满足：

1. CM311-1S 不需要插入系统 USB 即可启动。
2. 开机自动加载 ca46 `meson-vdec` 模块。
3. 开机自动运行 `vt13-kiosk.service`。
4. Worker 保持非 root 用户运行。
5. DJI USB 图传设备插入后能够正常接收 HEVC 视频。
6. 使用 V4L2 硬件解码及 DMA-BUF / KMS 显示链路。
7. 维持约 60 FPS 的正常显示能力。
8. 保留 USB hotplug 自动恢复能力。
9. 保持现有可接受的画面质量。
10. 保留完整日志和故障分析能力。
11. 支持现场故障恢复和系统回滚。

本次工作是系统迁移，不是重新设计图传系统。

除迁移必需的修改外，不允许 Worker 擅自更换 kernel、FFmpeg、PyAV、VDEC 或 Worker 版本。

### 0.2 当前已知状态

| 项目          | 当前状态                                 |
| ----------- | ------------------------------------ |
| 硬件          | CM311-1S / S905L3B                   |
| 系统          | Armbian，USB SG 启动                    |
| Worker      | Native C worker，候选版本 `eb1dbb67`      |
| 解码模块        | ca46 source-built meson-vdec         |
| 显示          | V4L2 stateful decode → DMA-BUF → KMS |
| systemd     | `vt13-kiosk.service`                 |
| 服务权限        | Non-root                             |
| 自动启动        | 已验证                                  |
| USB hotplug | 已验证                                  |
| 最佳历史 FPS    | 约 60.4                               |
| eMMC 根分区    | ampart 成功约 6.347 GiB；fallback 约 5.633 GiB |
| 选择性 payload | 精确 2,853,710,642 B（约 2.658 GiB） |
| G3/G4 状态     | G3 最终最小 payload 建议通过；G4 建议受控风险通过；G5 待明确批准 |
| 系统 Python 服务 | 静态 import/config 检查通过；eMMC 实机启动待 G6 |
| 当前验收状态   | `K3 ACCEPTED_WITH_LIMITATION`        |

这些信息来自之前 Worker 的报告。实际部署前必须重新核对运行中的版本、二进制文件、模块和配置哈希。

### 0.3 尚未解决的问题

以下问题必须继续保留在最终报告中：

- 内容相关 `0xf` abort。
- `0xf` 恢复时约 217–283 ms 的画面冻结。
- 偶发启动阶段 `0xf` burst。
- 曾出现一次 soft reboot 卡死。
- Glass-to-glass latency 尚未完成测量。
- 最终 `eb1dbb67 + ca46` 组合尚未完成新的 30 分钟 Soak。
- 当前 journald 可能仍为 volatile。
- 远程 parity 验证仅达到 hash 层面。
- 上游 VDEC audit 尚未完整部署。
- 新 `vt13-kiosk.service` 改用 `/usr/bin/python3`，静态导入已通过，但尚未在 eMMC 上作为服务实机启动。
- 系统 PyAV 保留用于诊断，但不在 worker 热路径；不得把“系统 av 可导入”当作硬件解码验收。

成功迁移到 eMMC 不代表上述问题已经解决，也不能自动将 K3 升级为完全生产验收。

# 1. 系统部署架构

## 1.1 硬件分工

本次采用两台设备完成部署。

### Ubuntu PC：主要备份与部署控制端

Ubuntu PC 已经有一份 VT13 图传部署代码仓库。

Ubuntu PC 负责：

- 保存 CM311 的完整离机备份。
- 检查 PC 仓库与 CM311 当前代码是否一致。
- 保存 Kernel 和 VDEC 驱动。
- 保存 FFmpeg 和 PyAV 环境。
- 保存 Worker binary、配置和 systemd service。
- 保存 boot、DTB、启动参数。
- 保存需要保留的 captures 和调试数据。
- 准备精简后的 eMMC 部署文件。
- 保存安装和测试日志。
- 记录部署版本、SHA256 和验收结果。

### 当前 SG USB：已验证的系统回滚介质

保留当前已经跑通的 USB 系统。

原则上不允许：

- 格式化。
- 重新分区。
- 删除唯一的原始文件。
- 为了节省 eMMC 空间直接清理源 USB。
- 未审批修改 bootloader。
- 未审批修改 kernel 或运行环境。

需要注意，某些安装脚本可能对当前正在运行的 SG USB 写入少量状态。因此不能在未审查安装器的情况下保证源 USB 字节级完全不变。

### CM311-1S 内部 eMMC：最终部署目标

用于安装精简后的 Armbian 系统和运行时环境。

目标是脱离 SG USB 完成冷启动并运行图传。

### 第二只 Staging USB：可选

只有以下情况才考虑使用：

- 无法保证安装器不会对当前 SG USB 造成不可接受的修改。
- 无法安全验证 DTB。
- 无法在不破坏当前系统的前提下测试精简安装。
- 没有可靠的回滚或救援方法。

不要求现在准备第二只 USB。

## 1.2 部署结构

```
Ubuntu PC
│
├── Existing VT13 Repository
│
├── CM311 Backup
│   ├── System files
│   ├── Boot / DTB
│   ├── Kernel / VDEC
│   ├── FFmpeg / PyAV
│   ├── Native C Worker
│   ├── systemd / udev
│   ├── Captures
│   └── Logs
│
├── Deployment Payload
│   └── Reduced eMMC Runtime
│
├── SHA256 Manifests
│
└── Deployment Reports
         │
         │ SSH / SCP / rsync
         │
         ▼
     CM311-1S
         │
         ├── SG USB
         │   └── Verified Boot Fallback
         │
         └── Internal eMMC
             └── Final Deployment
```

# 2. 严格执行顺序：G0–G8

Worker 必须采用 Gate 机制，每个阶段通过后才能进入下一阶段。

| Gate | 阶段          | 必须完成的内容                          |
| ---- | ----------- | -------------------------------- |
| G0   | 硬件与连接检查     | 确认 PC、CM311、USB、eMMC、SSH 和物理恢复方式 |
| G1   | 冻结运行环境      | 记录所有实际运行版本、配置和性能基线               |
| G2   | 完整备份        | 将所有必要文件备份到 Ubuntu PC，并验证         |
| G3   | eMMC 容量精简   | 制定安全的选择性安装方案，确认容量足够              |
| G4   | DTB、驱动及启动审计 | 确认兼容策略和故障恢复能力                    |
| G5   | eMMC 安装     | 取得明确人工批准后执行                      |
| G6   | eMMC 独立启动   | 拔掉 SG USB，确认系统真正从 eMMC 启动        |
| G7   | 图传功能回归      | 测试 USB、VDEC、KMS、FPS 和热插拔         |
| G8   | 最终验收        | 冷启动、重启、30 分钟 Soak、交接报告           |

### 强制执行规则

G0–G4 全部完成前，不允许写入 eMMC。

Worker 不得自动：

- 执行 `armbian-install`。
- 执行写磁盘的 `dd`。
- 格式化 eMMC。
- 修改 bootloader。
- 删除 SG USB 文件。
- 升级系统或 kernel。
- 修改当前运行服务配置。

如果某一 Gate 无法完成，必须报告 `BLOCKED`，而不是跳过。

# 3. G0：部署前硬件与系统审计

## 3.1 确认两台机器

Worker 首先确认：

- Ubuntu PC 与 CM311 的 SSH 连接。
- Ubuntu PC 可用磁盘容量。
- CM311 当前启动介质。
- SG USB 的实际磁盘设备、序列号、UUID。
- eMMC 的实际磁盘设备和容量。
- 当前 bootloader 的启动优先级。
- HDMI 是否能够观察启动状态。
- 是否能够现场断电。
- eMMC 失败后如何再次从 SG USB 启动。

特别注意：

eMMC 写入可能改变设备启动优先级，因此“USB 还在”并不等于“插回 USB 就一定可以恢复”。

Worker 必须给出经验证的启动回滚方法。无法确认时，不得进行 G5。

## 3.2 CM311 只读检查命令

```
hostnamectl

uname -a

cat /proc/cmdline

findmnt -no SOURCE,FSTYPE,UUID,TARGET /

findmnt -no SOURCE,FSTYPE,UUID,TARGET /boot

lsblk -o NAME,PATH,TRAN,TYPE,SIZE,MODEL,SERIAL,FSTYPE,UUID,MOUNTPOINTS

blkid

cat /proc/device-tree/model | tr '\0' ' '
echo

cat /proc/device-tree/compatible | tr '\0' ' '
echo

lsusb
lsusb -t

df -hT
df -i
```

输出保存到 Ubuntu PC：

```
reports/00_preflight.md
```

G0 必须记录：

```
Current boot device:
SG USB identity:
SG USB root UUID:
eMMC device:
eMMC capacity:
Current kernel:
Current DTB:
Ubuntu PC backup path:
Ubuntu PC available space:
SSH connectivity:
Physical recovery method:
G0 status:
```

# 4. G1：冻结当前正常运行系统

这是部署前最重要的步骤之一。

不能只备份 Git 仓库。必须找到 CM311 实际正在运行的全部组件。

## 4.1 必须记录的系统信息

| 组件       | 必须记录（Record）                | 必须备份（Backup）       |
| -------- | --------------------------- | ------------------ |
| Linux    | Kernel、发行版、启动参数             | `/boot`、必要的系统文件    |
| DTB      | 路径、文件名、SHA256               | 实际使用的 DTB 文件       |
| VDEC     | ca46 版本、vermagic、安装路径       | `.ko`、源码、补丁        |
| Worker   | Git commit、binary hash、启动参数 | 源码、运行 binary、配置    |
| FFmpeg   | 版本、configure、动态库依赖          | 自定义 `install/`     |
| PyAV     | 版本、Python、库链接               | `.venv-v4l2`       |
| systemd  | 用户、组、ExecStart、启动条件         | service、drop-ins   |
| udev     | USB 和 DRM 权限                | udev rules         |
| 性能       | FPS、sessions、errors、0xf     | 日志与必要诊断数据          |
| Boot     | 启动盘、UUID、DTB 配置             | `uEnv.txt`、boot 文件 |
| Captures | 大小、内容、用途                    | 需要保留的原始数据          |

## 4.2 Kernel 与 VDEC

必须记录：

```
uname -r

lsmod

modinfo meson_vdec

find /lib/modules/"$(uname -r)" \
    -iname '*vdec*.ko*' -print
```

实际模块名如果不同，以设备为准。

还需要记录：

```
Kernel version
Kernel source path
Kernel .config
Kernel Module.symvers
ca46 source commit
ca46 patch
ca46 .ko exact path
ca46 .ko SHA256
ca46 vermagic
Module autoload configuration
VDEC build command
```

### 特别要求：恢复可重复构建能力

之前 Worker 没有完整记录 ca46 的历史构建命令。

因此本次必须核查：

- 实际源码与补丁。
- Kernel source 和 headers。
- `Module.symvers`。
- 构建目录。
- 编译器及相关 flags。
- 模块安装和 `depmod` 流程。

历史示例：

```
make -j4 M=drivers/staging/media/meson/vdec modules
```

这不是已确认的实际构建命令。

必须在隔离环境中验证，不得为了测试覆盖当前已工作的 `.ko`。

## 4.3 FFmpeg 和 PyAV

需要记录以下内容：

```
FFmpeg version
FFmpeg source commit/version
Configure flags
Shared library paths
Runtime linker paths
PyAV version
Python version
Virtual environment path
ldd/readelf results
```

已知可能需要保留：

```
~/ffmpeg-6.1.1-v4l2-shared/install

.venv-v4l2
```

但 Worker 必须以 systemd 和进程实际使用的路径为准。

不能仅因为某个目录存在，就认定它是正在使用的环境。

## 4.4 Worker 和 systemd

执行：

```
systemctl cat vt13-kiosk.service

systemctl show vt13-kiosk.service \
    -p User \
    -p Group \
    -p ExecStart \
    -p WorkingDirectory \
    -p Environment \
    -p Restart \
    -p After

systemctl is-enabled vt13-kiosk.service

systemctl is-active vt13-kiosk.service
```

必须确认：

- 实际 `ExecStart`。
- 实际 worker binary。
- 实际 config。
- 运行用户和所属组。
- 共享库依赖。
- 是否使用额外 environment file。
- 是否依赖 udev、DRM 或 USB 权限。
- 自动重启和启动依赖关系。

应结合 `/proc/<pid>/exe` 和 `/proc/<pid>/maps` 核对实际运行文件，而不是只检查仓库中的候选 binary。

## 4.5 Ubuntu PC 仓库与 CM311 一致性审计

Ubuntu PC 已经有图传部署仓库，但是必须核查是否与当前 CM311 一致。

在两个仓库中分别执行：

```
git rev-parse --show-toplevel
git rev-parse HEAD
git branch --show-current
git status --porcelain=v1

git diff --binary HEAD
git diff --cached --binary

git ls-files --others --exclude-standard

git submodule status
```

需要比较：

1. Git commit 是否一致。
2. 是否有未提交代码。
3. 是否有未追踪的重要文件。
4. `build/d3` 是否一致。
5. 配置文件是否一致。
6. VDEC 模块是否一致。
7. FFmpeg / PyAV 是否一致。
8. 实际 systemd 服务和运行路径是否一致。

生成：

```
manifests/repository_parity.md
```

一致性状态定义：

| 状态       | 意义                   |
| -------- | -------------------- |
| MATCH    | 必需的源码、补丁、配置和运行产物均已核对 |
| PARTIAL  | Git 一致，但缺运行时文件或依赖    |
| MISMATCH | 存在代码、配置或 binary 差异   |

如果不是 `MATCH`，必须把缺失项目备份补齐。

G1 阶段不允许为追求一致而自动 `git pull`、`git reset --hard`、重新编译或升级依赖。

# 5. G2：备份到 Ubuntu PC

## 5.1 PC 备份目录结构

建议采用：

```
~/cm311-deployment/
│
├── repository/
│   └── Existing VT13 source reference
│
├── backups/
│   └── cm311-sg-YYYYMMDD-HHMM/
│       ├── sg-rootfs.tar
│       ├── sg-boot.tar
│       ├── runtime/
│       ├── kernel/
│       ├── ffmpeg/
│       ├── python/
│       ├── systemd/
│       ├── captures/
│       ├── logs/
│       ├── usb-disk.img.zst
│       └── SHA256SUMS
│
├── runtime-artifacts/
│
├── manifests/
│   ├── environment.txt
│   ├── repository_parity.md
│   ├── backup_manifest.md
│   ├── capacity_budget.md
│   └── SHA256SUMS
│
├── deployment-payload/
│
└── reports/
```

其中 `usb-disk.img.zst` 是可选的完整 USB 离线镜像。如果没有制作，必须明确标记 `NOT TAKEN`，不能保留空文件冒充备份。

## 5.2 Backup 和 Record 的区别

### Backup：必须真实保存文件

例如：

```
ca46.ko
worker binary
vt13_video source
FFmpeg install directory
Python venv
DTB
uEnv.txt
systemd service
udev rules
runtime configuration
```

这些文件必须真正存在于 Ubuntu PC 的备份目录。

### Record：记录如何恢复和验证

例如：

```
Source path
Destination path
Version
Git commit
SHA256
Owner / permissions
Dependencies
Build command
Systemd ExecStart
Runtime environment
```

记录 SHA256 并不代表已经备份文件。

### 独立保存未提交代码

Git 仓库的未提交修改、未追踪的关键代码、手工补丁和构建脚本也必须备份。

不能依赖 Git HEAD 自动恢复这些内容。

## 5.3 从 CM311 备份到 Ubuntu PC

以下命令示例在 Ubuntu PC 上执行。

先设置：

```
set -o pipefail

CM311_SSH='user@cm311-host-or-ip'

BACKUP_ROOT="$HOME/cm311-deployment/backups/cm311-sg-YYYYMMDD-HHMM"

mkdir -p "$BACKUP_ROOT"
mkdir -p "$BACKUP_ROOT/logs"
mkdir -p "$BACKUP_ROOT/runtime"
```

替换真实 SSH 地址和备份目录后，检查 sudo：

```
ssh "$CM311_SSH" 'sudo -n true'
```

如果返回失败，停止并确认授权方式。

不要直接进入下一步，也不要在二进制传输流中混入交互式终端输出。

### 备份主要 rootfs 内容

```
ssh "$CM311_SSH" \
  'sudo -n tar \
  --numeric-owner \
  --acls \
  --xattrs \
  --one-file-system \
  -C / \
  -cpf - \
  etc home opt root usr var' \
  > "$BACKUP_ROOT/sg-rootfs.tar"
```

这里是主要目录的文件级备份示例，不等于整盘镜像。

Worker 必须先用 `findmnt -R /` 检查实际挂载结构。对于被排除的独立分区、额外挂载点和必要系统目录，需要单独备份。

正在运行的系统可能存在持续修改的数据，因此这种备份不应声称具有块级一致性。

### 备份 Boot

```
ssh "$CM311_SSH" \
  'sudo -n tar \
  --numeric-owner \
  --acls \
  --xattrs \
  -C /boot \
  -cpf - .' \
  > "$BACKUP_ROOT/sg-boot.tar"
```

### 备份系统信息

```
ssh "$CM311_SSH" \
  'uname -a; cat /proc/cmdline; lsblk -f; df -hT' \
  > "$BACKUP_ROOT/runtime/system-identity.txt"
```

### 备份 systemd 配置

```
ssh "$CM311_SSH" \
  'systemctl cat vt13-kiosk.service' \
  > "$BACKUP_ROOT/runtime/vt13-kiosk.service.txt"
```

### 保存服务日志

```
ssh "$CM311_SSH" \
  'sudo -n journalctl -b -u vt13-kiosk.service --no-pager' \
  > "$BACKUP_ROOT/logs/service-before.txt"
```

### 验证压缩包

```
tar -tf "$BACKUP_ROOT/sg-rootfs.tar" >/dev/null
tar -tf "$BACKUP_ROOT/sg-boot.tar" >/dev/null
```

生成校验值：

```
sha256sum "$BACKUP_ROOT"/sg-*.tar \
  > "$BACKUP_ROOT/archives.sha256"

sha256sum -c "$BACKUP_ROOT/archives.sha256"
```

如果源端 tar 失败、SSH 断连或归档不完整，必须重新备份。

不能仅凭目标文件存在就认为操作成功。

## 5.4 必须单独提取的关键运行环境

除了 rootfs 归档，Worker 应另外提取关键文件，方便以后从 Ubuntu PC 恢复。

### VT13 Worker

```
vt13_video/
config/vt13_video.kiosk.yaml
build/d3/
native worker binary
startup scripts
Git patches
untracked runtime files
```

### FFmpeg

```
ffmpeg-6.1.1-v4l2-shared/install/
FFmpeg configure logs
custom patches
shared libraries
```

### PyAV

```
.venv-v4l2/
pip freeze
Python version
PyAV version
linked libraries
```

### ca46 VDEC

```
ca46 .ko
VDEC source
source patches
kernel .config
Module.symvers
module auto-load configuration
build instructions
```

### Boot

```
/boot/
/boot/uEnv.txt
actual DTB
/etc/fstab
/etc/ophub-release
/etc/model_database.conf
```

### 系统集成

```
vt13-kiosk.service
service drop-ins
udev rules
user/group permissions
journald configuration
module-load rules
```

### 用户数据

```
captures/
.codex_tmp/
```

需要特别检查 `.codex_tmp` 是否含有独有代码、补丁或调试材料。不能简单认为都是可以删除的缓存。

## 5.5 可选：完整 SG USB 磁盘镜像

如果需要最高级别的可恢复性，可以：

1. 正常关闭 CM311。
2. 拔下 SG USB。
3. 将 SG USB 接到 Ubuntu PC。
4. 确认 USB 设备的物理身份和序列号。
5. 确认源分区均已卸载。
6. 对整盘做只读镜像。
7. 计算镜像 SHA256。
8. 验证镜像可读取并能够解析分区。

首先使用：

```
lsblk -o NAME,PATH,TRAN,SIZE,MODEL,SERIAL,MOUNTPOINTS

ls -l /dev/disk/by-id/
```

不得猜测 `/dev/sda` 或 `/dev/sdb` 就是 SG USB。

如果使用 `dd` 或其他镜像工具，必须核实读取源设备与输出文件路径；绝不能把输出目标指向原 USB。

完整盘镜像是推荐的额外保护，但本次并不强制要求第二只启动 USB。

## 5.6 是否备份原 eMMC？

如果 eMMC 内部仍有 Android 或其他原系统，必须先决定是否有保留价值。

若需要保留：

- 在正式写入 eMMC 前制作原系统镜像。
- 保存必要的分区和 bootloader 信息。
- 将镜像转移至 Ubuntu PC。
- 校验镜像。
- 记录恢复方式。

若不需要保留：

- 记录明确的放弃保留决定。
- 不得把未备份的原系统标记为可以恢复。

## 5.7 SHA256 和恢复测试

进入备份目录：

```
cd "$BACKUP_ROOT"
```

生成文件清单：

```
find . -type f ! -name SHA256SUMS -print0 \
  | sort -z \
  | xargs -0 sha256sum \
  > SHA256SUMS
```

验证：

```
sha256sum -c SHA256SUMS \
  > VERIFY_SHA256.txt
```

必须确认：

```
Failed files: 0
```

另外需要做抽样恢复测试：

- 从归档中提取某个 worker binary。
- 提取一份配置文件。
- 提取 ca46 模块。
- 提取一个 service 文件。
- 对照原始 SHA256。
- 核对权限、属主和符号链接。

如果备份中包含数据库、运行时状态或频繁写入的文件，必须另行证明其备份一致性。

### G2 通过条件

- Ubuntu PC 上真实存在备份文件。
- 必须保留的关键文件已全部覆盖。
- SHA256 校验通过。
- 抽样恢复成功。
- 已记录缺失或无法备份的内容。
- SG USB 没有不可逆修改。

如果 G2 不通过，不得进入 eMMC 安装阶段。

# 6. G3：eMMC 容量精简与部署文件准备

这是本次迁移最关键的技术问题之一。

## 6.1 当前容量问题

已知：

```
Current source data: ~15.3 GiB
Target eMMC root:    ~6.3 GiB
```

不能把当前整个系统直接复制到内部 eMMC。

即使已经把 15.3 GiB 数据备份到 Ubuntu PC，当前 SG USB 的实际占用也不会自动减少。

因此，Worker 必须制定选择性安装方案。

### 原则

只精简将要写入 eMMC 的文件集，不在现有 SG USB 上删除原始数据。

## 6.2 必须审查实际安装器

Worker 应先确认：

```
command -v armbian-install
```

并计算实际脚本哈希：

```
sha256sum "$(command -v armbian-install)"
```

需要阅读安装器完整实现，特别是：

- Source rootfs 的复制范围。
- 目标设备识别方法。
- 格式化和分区操作。
- Bootloader 写入行为。
- DTB 更换行为。
- `fstab` 和 root UUID 修改。
- 是否生成新的 `machine-id`。
- 是否修改当前 SG USB。
- 是否支持排除目录。
- 是否支持指定 rootfs source。
- 是否支持 dry-run。

目前检查过的 ophub 上游安装器可能复制：

```
COPY_SRC="etc home opt root selinux srv usr var"
```

也可能在安装过程中修改源系统中的：

```
/etc/machine-id
/ddbr/install
/usr/lib/u-boot
```

因此：

禁止未经审核直接在现有 SG USB 系统上执行原版 `sudo armbian-install`。

实际行为必须以 CM311 上安装器的版本为准。

## 6.3 确认哪些文件可以从 eMMC 中排除

Worker 必须首先统计目录大小，并检查运行时引用。

候选如下。

| 文件或目录                     | 是否放入 eMMC | 处理方式      |
| ------------------------- | --------- | --------- |
| Kernel 和启动文件              | 必须        | 保留        |
| ca46 `.ko`                | 必须        | 保留        |
| Native C worker           | 必须        | 保留        |
| Kiosk 配置                  | 必须        | 保留        |
| systemd / udev            | 必须        | 保留        |
| 必要的共享库                    | 必须        | 保留        |
| 系统 Python 3.12 / dist-packages | 必须 | 保留；worker 控制面使用 `/usr/bin/python3` |
| 系统 FFmpeg 共享库         | 必须 | 保留 `/usr/lib/aarch64-linux-gnu` 下的运行库 |
| FFmpeg runtime `install/` | 不需要（当前 worker 后端） | PC 保存；不作为 eMMC payload |
| `.venv-v4l2`              | 不需要（当前 worker 后端） | PC 保存；不作为 eMMC payload |
| FFmpeg source/build       | 通常不需要     | PC 保存     |
| Kernel source/build       | 通常不需要     | PC 保存     |
| captures                  | 不需要运行时常驻  | PC 保存     |
| `.codex_tmp`              | 通常不需要     | 审计后 PC 保存 |
| 历史测试录屏                    | 不需要       | PC 保存     |
| 历史调试日志                    | 不需要常驻     | PC 保存     |
| 无运行时引用的构建缓存               | 不需要       | PC 保存或排除  |

特别说明：

当前 Native C worker 只依赖 libc；Python 仅负责 USB/DUML 控制面和 AU 投递，生产服务使用系统 `/usr/bin/python3`。系统 PyAV 11.0.0 仍保留用于诊断，但不在 worker 热路径。`.venv-v4l2` 和自定义 `ffmpeg-6.1.1-v4l2-shared/install` 已从 eMMC payload 排除；这不是“按文件名猜测”，而是由实际进程、`ldd`、系统导入和静态 service 检查支持。

## 6.4 Ubuntu PC 构建精简部署文件集

建议目录：

```
~/cm311-deployment/deployment-payload/
├── boot/
├── etc/
├── home/
├── opt/
├── usr/
├── var/
└── manifest.sha256
```

实际文件布局必须根据原系统、安装器和目标分区确定。

此目录不能简单视为完整可启动 rootfs。

Worker 需要：

1. 使用 PC 上的备份构建精简文件集。
2. 保留系统启动、图传运行所需的所有文件。
3. 排除大体积历史数据、源码构建目录和不必要缓存。
4. 保留文件 UID/GID、ACL、xattr、符号链接和必要的特殊文件。
5. 确认所有运行时绝对路径。
6. 确认共享库和动态链接路径。
7. 对精简文件集计算 SHA256。
8. 测量其实际展开后的容量。

## 6.5 生成逐路径排除清单

Worker 必须生成：

```
manifests/capacity_budget.md
```

并至少包含：

| Source Path         | Size        | Action              | Backup Location | Reason |
| ------------------- | ----------- | ------------------- | --------------- | ------ |
| captures            | 4.2 GB（待核实） | Exclude             | Ubuntu PC       | 历史采集   |
| .codex_tmp          | 3.2 GB（待核实） | Exclude after audit | Ubuntu PC       | 调试数据   |
| FFmpeg source/build | 待测量         | Exclude if safe     | Ubuntu PC       | 不需要常驻  |
| Kernel source/build | 待测量         | Exclude if safe     | Ubuntu PC       | 不需要常驻  |
| FFmpeg install      | 待测量         | Include if required | eMMC            | 运行时依赖  |
| ca46 module         | 待测量         | Include             | eMMC            | 硬解驱动   |
| Native worker       | 待测量         | Include             | eMMC            | 主程序    |

对于每个被排除的目录，必须记录：

```
Original source path:
Size:
Backup location:
Backup SHA256:
Reason for exclusion:
Runtime dependency check:
Restore procedure:
```

## 6.6 选择性安装的两种实现路线

### 路线 A1：从 SG USB 选择性复制到 eMMC

保留当前 SG USB 作为源系统。

经过审查的安装流程负责：

- 正确分区与挂载 eMMC。
- 只复制指定文件。
- 在复制阶段排除历史数据。
- 正确生成目标 `fstab` 和启动参数。
- 正确安装 bootloader 和 DTB。
- 不清理原始 SG USB。

可以通过经过审核的 `tar --exclude` 或 `rsync --exclude-from` 实现文件过滤。

但需要强调：

这是候选实施方式，并不代表现有 `armbian-install` 原生支持此功能。

Worker 必须提供脚本 patch 和验证结果。

### 路线 A2：从 Ubuntu PC 恢复精简文件到 eMMC

在 CM311 上完成经审核的分区和挂载准备。

然后从 Ubuntu PC 把精简文件复制到指定的 eMMC root 分区。

这种方式需要特别验证：

- 实际目标分区。
- 目标挂载点。
- 权限和文件属性。
- 网络断连后的恢复。
- `fstab`。
- Bootloader。
- DTB。
- Kernel module。
- Root UUID。
- 正确生成或恢复 `machine-id`。

不能仅复制文件就认定 eMMC 可启动。

### 实现路线的选择

Worker 必须选择一种路线，并在 G5 之前固定：

```
Selected approach:
Installer path:
Installer SHA256:
Source root:
Target root:
Copy mechanism:
Exclude manifest:
Expected target size:
Bootloader strategy:
DTB strategy:
Rollback mechanism:
```

禁止没有审计就直接覆盖系统中的原版安装器。

## 6.7 容量验收标准

以 eMMC 实测的根分区容量计算。

建议：

```
Target eMMC root: ~6.3 GiB
Suggested post-install free space: >= 1 GiB
```

如果实际根分区更小，应根据实测重新计算预算。

必须考虑：

- Rootfs 本身。
- 文件系统元数据。
- Inode。
- Kernel module。
- Worker 运行时。
- systemd journal。
- 临时文件。
- 后续配置与更新空间。

压缩后的 tar 文件大小不能作为 eMMC 实际占用空间。

至少应在 Ubuntu PC 上进行一次离线展开预演，确认精简文件集的容量、属性及文件完整性。

### G3 通过条件

- 安装器已完整审计。
- 明确源 SG USB 可能发生的写入副作用。
- 已生成逐路径排除清单。
- 已完成安装文件集容量预算。
- 所有必要 runtime 文件均被保留。
- 已形成经过审核的选择性复制方案。
- PC 上已保存安装脚本、patch、diff 和 SHA256。
- 不需要删除当前 SG USB 数据。

如果无法安全实现选择性复制：

G3 = BLOCKED。

此时应考虑第二只 Staging USB，而不是跳过验证。

## 6.8 最终最小运行时 payload 决策（2026-11-12 18:25 HKT）

本节覆盖早期“保留 venv/自定义 FFmpeg”的中间方案；旧 `3,685,431,296 B` 数字不再作为最终 payload。

```text
Selected approach: audited selective copy from the running SG USB system
Final root payload: 2,853,710,642 B (2.6577 GiB)
Tar stream before installer post-copy: 2,853,621,760 B, 61,468 members
Post-copy additions: kiosk helper 88,621 B + service replacement 250 B + modules-load 11 B
Exclude manifest: deploy/emmc-exclude.txt
Exclude SHA256: 58b8fe241085f4cd996ea84340148aea2f5919bfca55e234542b28ca1fc6b88a
Installer: .codex_tmp/emmc_deploy_20261112/g3/armbian-install-final.sh
Installer SHA256: 90cb03905726b2aa3cfa5f2948f552694ab992642c750c1938cacd1bad5b5c12
Target device: /dev/mmcblk2
Target rootfs: ext4
Target DTB: meson-gxl-s905l3b-m302a-gxl-test.dtb
```

最终 include/exclude、依赖、容量、changed paths 和证据见 `deploy/PAYLOAD_MANIFEST.md`。要点：

- 排除 `.venv-v4l2`、自定义 FFmpeg shared 树、captures/live_runs/.codex_tmp、kernel/FFmpeg 源码、toolchains、apt cache/lists、历史日志、文档/man/locale/src 和旧 build 产物。
- 保留 ca46 `meson-vdec.ko`、`gxl_hevc.bin`、Native worker、`vt13_video` 源码/配置、systemd/udev/journald、系统 Python 及 dist-packages、系统 FFmpeg 共享库、DRM/KMS 运行依赖。
- ampart-success root `6,814,695,424 B`，安装前预计余 `3,960,984,782 B`（3.6890 GiB）；fallback root `6,048,186,368 B`，预计余 `3,194,475,726 B`（2.9751 GiB）。两者均未计 ext4 元数据/inode，G6 必须实测。
- 远端 G5 staging `~/mobile_vt/.codex_tmp/emmc_deploy_20261112/g5/` 中 installer/exclude/service 哈希已核对一致，`bash -n` 通过；尚未写 eMMC。

# 7. G4：DTB、VDEC、Kernel 与启动链检查

## 7.1 DTB 兼容性

已知当前系统可能使用：

```
-gxl-test.dtb
```

而标准 ophub `MODEL_ID=127` 对应：

```
meson-gxl-s905l3b-m302a.dtb
```

Worker 必须确认：

1. 当前实际使用的 DTB 文件。
2. 实际 DTB 的 SHA256。
3. 安装器准备写入的 DTB。
4. 两者的差异。
5. 哪些差异可能影响 VDEC。
6. 哪些差异可能影响 USB。
7. 哪些差异可能影响 HDMI / DRM / KMS。
8. 哪些差异可能影响 eMMC 启动。

重点关注：

```
VDEC / HEVC
IRQ
Clock
Reserved memory
DRM / KMS
HDMI
USB
Pinctrl
eMMC / MMC
```

可以通过 `dtc` 反编译和比较 DTB。

但要注意：

DTB 静态文件比较不能代替实机启动验证。

## 7.2 优先考虑沿用已经验证的 DTB

如果当前测试 DTB 已经实现：

- USB 正常。
- VDEC 正常。
- KMS 正常。
- HDMI 正常。
- Worker 正常。

应优先评估是否可以将它用于 eMMC 系统。

但必须检查 eMMC 控制器、启动参数、root UUID 和 bootloader 兼容性。

如果使用标准 m302a DTB，也必须说明其兼容性依据。

不能仅凭 `MODEL_ID=127` 就宣布所有功能一定可以正常运行。

## 7.3 ca46 模块兼容性

必须核查：

```
uname -r
```

以及：

```
modinfo -F vermagic /path/to/actual/ca46.ko
```

这里的 `.ko` 路径必须是实际安装路径。

确认：

```
Kernel version
Module vermagic
Module SHA256
Module dependency
Module autoload
depmod status
```

在没有 ABI 兼容性依据的情况下，不能强行加载旧模块。

## 7.4 Worker 运行依赖

必须验证：

```
Native worker binary
Worker config
Shared libraries
System Python 3.12 (/usr/bin/python3)
System dist-packages: cv2, numpy, yaml, usb, av
System FFmpeg shared libraries
USB device permissions
DRM access
Systemd user/group
```

对于实际 ELF binary，应使用：

```
ldd /path/to/worker
```

必要时通过 `readelf` 检查动态依赖。

不能有：

```
not found
```

当前生产路径的实际结论：Native worker 仅依赖 libc；Python 控制面使用系统 `/usr/bin/python3`；系统 PyAV 11.0.0 可导入但不在 worker 热路径；自定义 `ffmpeg-6.1.1-v4l2-shared/install` 和 `.venv-v4l2` 不再是 eMMC 必需依赖。G6 仍必须用实际 service、`ldd` 和运行时日志复核，不能仅凭静态路径推断。

## 7.5 启动链和恢复能力

Worker 必须记录：

```
Current bootloader:
Current USB boot method:
Current boot priority:
Target eMMC boot method:
Target DTB:
Target root UUID:
Expected boot configuration:
Recovery method:
```

如果 eMMC 安装失败：

```
Power off
    ↓
Use verified USB / serial recovery path
    ↓
Boot original SG USB
    ↓
Confirm root filesystem source
    ↓
Load ca46
    ↓
Start vt13-kiosk
    ↓
Verify HDMI video
```

必须提前确认这条路径确实可执行。

### G4 状态定义

| 状态                      | 意义                          |
| ----------------------- | --------------------------- |
| PASS_VERIFIED           | 关键组合已通过等价实机动态验证             |
| PASS_WITH_APPROVED_RISK | 无法完全动态验证，但有静态审计、可靠救援和明确风险批准 |
| BLOCKED                 | 存在无法确认的启动或兼容性风险             |

如果缺少 Staging USB，G4 也不是必然不能通过，但必须明确哪些地方尚未动态验证。

只有 `PASS_VERIFIED` 或经人工批准的 `PASS_WITH_APPROVED_RISK` 才能提交 G5 审批。

## 7.6 G3/G4 执行记录与 G5 固定决策（2026-11-12 18:25 HKT）

| Gate | 当前结论 | 说明 |
| --- | --- | --- |
| G3 | **建议通过（RECOMMENDED PASS）** | 最终最小 payload `2,853,710,642 B`、61,468 tar 成员、排除清单、容量预算和最终 installer 已固定；尚未在 eMMC 上执行。 |
| G4 | **建议以受控风险通过（PASS_WITH_APPROVED_RISK 建议）** | 静态启动链、DTB、ca46、固件、service、udev 和系统 Python/系统 FFmpeg 运行时依赖已核实；eMMC 动态启动与 system-Python service 待 G6。 |
| G5 | **未执行** | 必须取得设备持有人明确批准。 |
| G6 | **待实测** | 拔掉 SG USB 后的 eMMC-only 冷启动、HDMI、ca46 自动加载、service 和 SSH 均未验证。 |

固定决策：

```text
Selected approach: audited selective copy from the running SG USB system
Installer path: /ddbr/armbian-install-final.sh
Installer SHA256: 90cb03905726b2aa3cfa5f2948f552694ab992642c750c1938cacd1bad5b5c12
Installer patch SHA256: 175920b50b288a597d98e8209e0b575b067531042163756fbf7ff6bc2c2c5bf2
Original installer: /usr/sbin/armbian-install
Original SHA256: defc9646cd0aee8d33afcad04441a91f12eed7b82e8d1e6833c38401bd68f6f4
Exclude manifest: /ddbr/emmc-exclude.txt
Exclude SHA256: 58b8fe241085f4cd996ea84340148aea2f5919bfca55e234542b28ca1fc6b88a
Reviewed service: /ddbr/vt13-kiosk.service
Service SHA256: 3ed774081ba0e95f57fff253ae2c5fb5b76f0c5f2a65d00405741fded65149f1
Target device: /dev/mmcblk2
Target rootfs: ext4
Target DTB: meson-gxl-s905l3b-m302a-gxl-test.dtb
Selective payload: 2,853,710,642 B (2.6577 GiB)
ampart-success root budget: 6,814,695,424 B; free before metadata 3,960,984,782 B
ampart-fallback root budget: 6,048,186,368 B; free before metadata 3,194,475,726 B
Bootloader strategy: installer backs up first 4 MiB to /usr/lib/u-boot/mybox-bootloader.img, then writes it back
Bootloader backup SHA256: f61b153c1ec98ce54ee770be43198af2d2ac60642cc6004500cfbd3b87490262
G5 wrapper: deploy/g5-install-wrapper.sh
G5 wrapper SHA256: 1bef8ba4e410d7b54c6c88548de6d6273ad56eff2d0268fec2cbe82d9d34257d
G5 PC runner: deploy/g5-run-from-pc.sh
G5 PC runner SHA256: c3ef51f004f44b6ed257d83a7481b4aff32a9335abaae2a18d2c6ba727ef9af8
Rollback: keep SG USB untouched; poweroff, reinsert SG USB, cold boot; physical reset/USB Burning Tool if needed
```

安装器预期源盘副作用：重新生成 `/etc/machine-id` 和 `/var/lib/dbus/machine-id`；重建 `/ddbr/install`；创建 `/usr/lib/u-boot/mybox-bootloader.img`（eMMC 前 4 MiB 备份）。不会修改源 `/boot` 内容；依赖包仅在缺失时安装。G3 附注：没有在 PC 上整包展开全部 61,468 个成员，而是使用远端实际未压缩 tar 流字节数和成员审计；安装器对关键运行时文件做 fail-closed 检查。该附注不阻止 G5，但 G6 必须实测 ext4 可用空间和 inode。

审计报告：`.codex_tmp/emmc_deploy_20261112/g3g4/G3G4_REPORT.md` SHA256 `82ee6c50…`；证据清单 `EVIDENCE_SHA256.txt`（30/30 OK，清单自身哈希见 `G3G4_REPORT.md.sha256`）。G5 staging 证据：`.codex_tmp/emmc_deploy_20261112/g5/STAGING.txt`。旧 17:16 报告保留为 `G3G4_REPORT_20261112_1716_superseded.md`，不能沿用旧 `1d54fbfa…`/`711d9a82…`。

# 8. G5：正式安装 eMMC

G5 是唯一允许执行破坏性 eMMC 写入的阶段。

## 8.1 安装前审批清单

Worker 必须确认：

- G0 PASS。
- G1 PASS。
- G2 PASS。
- G3 PASS。
- G4 PASS 或取得明确的受控风险批准。
- Ubuntu PC 备份完整。
- SHA256 全部通过。
- 抽样恢复测试成功。
- 现有 SG USB 被保留。
- eMMC 实际设备已确认。
- 选择性安装脚本已审计。
- 精简文件集容量满足要求。
- DTB 策略已确定。
- ca46 和 Kernel 兼容性已审查。
- 回滚方式已确认。
- 原 eMMC 数据保留决策已记录。
- 设备持有人已明确批准安装。

审批必须写入：

```
APPROVED FOR R3 eMMC FLASH

Target device:
Hardware model:
Installer path:
Installer SHA256:
Exclude SHA256:
Service SHA256:
Selective payload:
Target DTB:
Target rootfs:
Rollback method:
Approval timestamp:
```

没有明确批准，不允许执行安装。

## 8.2 安装命令与执行要求

不能直接把：

```
sudo armbian-install
```

作为本次无条件执行的安装命令。

因为现有系统的体积已经超过 eMMC 容量，而且未经审查的安装器可能修改 SG USB 上的文件。

Worker 必须展示：

```
Reviewed installer:
Full absolute path:
SHA256:
Target block device:
Expected partitions:
Filesystem:
Copy exclusions:
Source-side modifications:
Bootloader changes:
DTB changes:
```

确认后才能执行审核过的安装命令。

执行期间：

1. 保存完整终端日志。
2. 记录每一步退出码。
3. 核对实际目标磁盘。
4. 不允许无人值守自动重试刷盘。
5. 如发生未预期的分区、格式化或源盘修改，立即停止。
6. 若网络中断，必须依赖现场终端或串口确认状态。
7. 安装失败后不能反复盲刷。

安装结束后：

```
sync
```

然后记录目标分区状态、启动参数和安装结果。

正常关机，拔下 SG USB，准备 eMMC-only 启动。

## 8.3 本次审核后的最终 G5 命令（待明确执行授权）

主机：Ubuntu PC；通过 SSH 操作 CM311。前提：G0–G4 已完成；G5 已获明确执行授权；SG USB 仍是当前 `/` 和 `/boot`；VT 已关闭；CM311 SSH 可达；PC 仓库存在最终 wrapper/runner。以下命令会写入 `/dev/mmcblk2`，执行前不得无人值守自动重试。

### 固定目标布局

| 区域 | ampart 成功 | ampart fallback |
| --- | --- | --- |
| vendor bootloader | 0–4 MiB | 0–4 MiB |
| p1 `BOOT_EMMC` FAT32 | 117–628 MiB（512 MiB） | 128–639 MiB（512 MiB） |
| p2 `ROOTFS_EMMC` ext4 | 629 MiB–100%，`6,814,695,424 B` | 1360 MiB–100%，`6,048,186,368 B` |
| root payload | `2,853,710,642 B` | `2,853,710,642 B` |
| 预计 root 空闲（未计 ext4 元数据） | `3,960,984,782 B`（3.6890 GiB） | `3,194,475,726 B`（2.9751 GiB） |

安装器会创建 MBR/FAT32 boot 分区和 ext4 root，写入 vendor bootloader 前 4 MiB 备份，更新 `uEnv.txt` 的 root UUID 和 `meson-gxl-s905l3b-m302a-gxl-test.dtb`，并复制 `/boot` 到 eMMC boot 分区。boot 分区固定 512 MiB，root 空闲量以 G6 的 `df -hT /`/`df -i` 为准。

### 最终命令与固定 SHA256

```bash
cd /home/billieguo/billie_guo/src/rm/mobile_vt
bash deploy/g5-run-from-pc.sh
```

固定哈希：

```text
Wrapper: 1bef8ba4e410d7b54c6c88548de6d6273ad56eff2d0268fec2cbe82d9d34257d
PC runner: c3ef51f004f44b6ed257d83a7481b4aff32a9335abaae2a18d2c6ba727ef9af8
Installer: 90cb03905726b2aa3cfa5f2948f552694ab992642c750c1938cacd1bad5b5c12
Installer patch: 175920b50b288a597d98e8209e0b575b067531042163756fbf7ff6bc2c2c5bf2
Exclude: 58b8fe241085f4cd996ea84340148aea2f5919bfca55e234542b28ca1fc6b88a
Reviewed service: 3ed774081ba0e95f57fff253ae2c5fb5b76f0c5f2a65d00405741fded65149f1
Bootloader backup: f61b153c1ec98ce54ee770be43198af2d2ac60642cc6004500cfbd3b87490262
```

runner 会先在 PC 校验 Wrapper 哈希，再通过 SSH 上传到 CM311 staging 并在远端重新校验；Wrapper 会再次校验 installer/patch/exclude/service、源 `/boot` 七项启动文件、KMS helper、目标盘身份与 eMMC 前 4 MiB/boot0/boot1，全部通过后才停止 kiosk 并执行 installer。安装成功后，Wrapper 先验证 eMMC 分区、`BOOT_EMMC`/`ROOTFS_EMMC`、boot 文件、root UUID/fstab、rootfs 关键文件、service unit/启用 symlink、KMS helper、ca46 模块与固件；随后导出 `mybox-bootloader.img` 和安装后 MBR 首 512 B。runner 再把完整安装日志、post-install evidence 和两个备份文件回传 PC，逐文件校验 SHA256/尺寸，**只有全部通过才执行 `sync` 和 `poweroff`**。

### 交互输入

必须按顺序手工输入，不能把多个值预填成一行：

1. runner 通过交互式 SSH 执行 `sudo` 时，输入 CM311 账户的 sudo 密码。
2. `Please Input ID:` 输入 `127`。
3. `Please Input ID (1/2):` 输入 `1`（ext4；不要选择 `2`/btrfs）。

### 安装后验证与失败处理

Wrapper 在 `poweroff` 前检查目标分区、boot 文件、rootfs、service、KMS helper、ca46 模块、固件和启动参数；任何一项不符即 fail-closed，不报告 `VALIDATED`。PC runner 只有在日志/evidence/备份全部回传并校验后才关机。若 installer、验证或日志回传失败，不执行 `poweroff`；源 SG USB 系统仍可用，wrapper/runner 会尝试恢复 `vt13-kiosk.service`。检查日志后重新审批，不得自动重跑。

### `mybox-bootloader.img` 恢复语义

该文件是**同一台 CM311 当前 eMMC 用户区前 4 MiB 的 vendor bootloader 备份**，不是通用 U-Boot，也不是完整磁盘镜像。当前 SHA256 为 `f61b153c…90262`；用户区 `0x200` 有 `@AML`/`gxl` 头。它同时包含备份时的旧 MBR/分区表（字节 444–511）。安装器回写语义是只恢复 0–443 和 512–4194303，保留新分区表：

```bash
# CM311；恢复前确认 /dev/mmcblk2 未挂载，并使用经 SHA256 核验的备份文件。
sudo dd if=/path/to/mybox-bootloader.img of=/dev/mmcblk2 bs=1 count=444 conv=fsync
sudo dd if=/path/to/mybox-bootloader.img of=/dev/mmcblk2 bs=512 skip=1 seek=1 count=8191 conv=fsync
sudo partprobe /dev/mmcblk2
```

不要无条件使用 `dd bs=1M count=4` 作为通用恢复命令：它会把备份时的旧 MBR/分区表一并覆盖。runner 回传的 `mbr-first512.bin` 是安装后新 MBR 的证据；正常 bootloader 恢复不需要重写它，除非新分区表本身丢失。`mybox-bootloader.img` 只适用于这台 CM311 的当前 eMMC/vendor bootloader；换 eMMC 或 bootloader 变化后必须重新验证。

### 预期关键日志

```text
Dependency check completed. Proceeding installation...
Detected eMMC device: [ /dev/mmcblk2 ]
Deployment DTB override: [ meson-gxl-s905l3b-m302a-gxl-test.dtb ]
Start backing up the default bootloader.
Successfully repartitioned eMMC with ampart.
Copying [ home ] (selective) ...
Installation completed successfully. Run [ poweroff ], remove the installation media...
G5_VALIDATED
G5_LOG_SAVED_AND_VERIFIED
G5_POWEROFF_ISSUED
```

若没有 `Successfully repartitioned eMMC with ampart.`，说明 ampart 未成功，安装器会走 fallback 布局继续；root 仍为 `6,048,186,368 B`，预计余量仍高于 1 GiB。若出现 `Selective copy missing critical file`、分区/格式化错误、目标盘身份不符或哈希不符，立即停止，不要盲刷。

### 最终只读 preflight 证据

本地 `.codex_tmp/emmc_deploy_20261112/g5_pc_20261112_213308/`：`preflight.txt` SHA256 `41f62d3beadc5482428b9c969a94cf425742f0a20b019da733c84f3d0df0ba51`，`g5-result.env` SHA256 `8921c5a88163fdad30e09e74c69bf97cdf05ee1e3d4b25ef4d6e2feafd8157d0`，`preflight-session.log` SHA256 `2df2bae72162f0871844e2e16ec7c817882be94040a776c20a6e68755242ec40`。远端 `~/mobile_vt/.codex_tmp/emmc_deploy_20261112/g5/run_20261112_213343/` 的 `preflight.txt`/`g5-result.env` 与本地 SHA256 相同；远端 Wrapper 哈希 `1bef8ba4…`；`/ddbr` 仍不存在，eMMC 无挂载，kiosk active。该 preflight 未写 eMMC、未停服务、未 reboot、未重载模块、未启动 USB/HDMI/无线。

G5 成功后正常 `poweroff`。**G6 首次启动必须先拔掉 SG USB，再冷启动**；确认 `/` 为 `/dev/mmcblk2p2`、`/boot` 为 `/dev/mmcblk2p1`。不要插着 SG USB 启动后把正常运行当作 eMMC 成功。

# 9. G6：eMMC 独立启动与系统恢复

## 9.1 第一次 eMMC-only Cold Boot

必须拔掉 SG USB。

观察设备从内部 eMMC 启动。

启动后执行：

```
findmnt -no SOURCE,FSTYPE,UUID,TARGET /

findmnt -no SOURCE,FSTYPE,UUID,TARGET /boot

lsblk -o NAME,PATH,TRAN,SIZE,FSTYPE,UUID,MOUNTPOINTS

cat /proc/cmdline

uname -r

cat /proc/device-tree/model | tr '\0' ' '
echo

systemctl --failed

df -hT
```

Worker 必须提供证据，证明：

```
Root filesystem = Internal eMMC
```

不能插着 SG USB 启动，然后将正常运行当作 eMMC 部署成功。

## 9.2 严格分层检查顺序

### Layer 1 — Boot / Rootfs

检查：

- eMMC root。
- `fstab`。
- Root UUID。
- SSH。
- 时间和网络。
- 文件系统可写。
- 剩余空间（`df -hT /`、`df -hT /boot`、`df -i /`）。

### Layer 2 — Kernel / DTB

检查：

- Kernel version。
- DTB。
- IRQ。
- Clock。
- HDMI。
- USB。
- DRM/KMS。
- VDEC。

### Layer 3 — ca46

检查：

- `.ko` 文件完整。
- SHA256。
- Vermagic。
- 模块加载。
- 依赖。
- 自动加载。
- `/etc/modules-load.d/vt13-vdec.conf` 内容为 `meson_vdec`。
- 重新冷启动后仍可用。

### Layer 4 — 系统 Python / FFmpeg / 动态依赖

检查：

- `/usr/bin/python3` 存在且版本正确。
- 系统 `cv2`、`numpy`、`yaml`、`usb` 可导入；系统 PyAV 可导入但不要求在 worker 热路径使用。
- 系统 FFmpeg 共享库存在：`libavcodec.so.60`、`libavutil.so.58`、`libswscale.so.7`。
- `ldd /home/billieguo/mobile_vt/build/d3/d3_probe` 无 `not found`，且只依赖 libc。
- 不存在对 `.venv-v4l2` 或 `~/ffmpeg-6.1.1-v4l2-shared/install` 的运行时依赖。

检查命令：

```bash
/usr/bin/python3 - <<'PY'
import cv2, numpy, usb, yaml
print('system python imports OK')
try:
    import av
    print('system av', av.__version__)
except Exception as exc:
    print('system av unavailable:', exc)
PY
ldd /home/billieguo/mobile_vt/build/d3/d3_probe
readelf -d /home/billieguo/mobile_vt/build/d3/d3_probe | grep -E 'NEEDED|RUNPATH' || true
```

系统 PyAV 不是硬件解码路径；不得用 `import av` 成功代替 V4L2/KMS 验收。

### Layer 5 — Native VT13 Worker

检查：

- 实际 binary。
- Config。
- Binary SHA256。
- USB 设备访问。
- DRM/KMS 权限。
- 启动参数。

### Layer 6 — systemd

```
systemctl status vt13-kiosk.service

systemctl is-enabled vt13-kiosk.service

systemctl is-active vt13-kiosk.service

systemctl cat vt13-kiosk.service

journalctl -b -u vt13-kiosk.service
```

确认服务：

- 非 root。
- 自动启动。
- `ExecStart` 使用 `/usr/bin/python3`，不是 `.venv-v4l2/bin/python`。
- 无关键报错。
- 能按预期重启。
- 能在 USB 热插拔后恢复。

### Layer 7 — 完整视频链路

验证：

```
DJI USB Video
      ↓
Native C Worker
      ↓
V4L2 Stateful HEVC Decoder
      ↓
ca46 meson-vdec
      ↓
DMA-BUF
      ↓
KMS Overlay
      ↓
HDMI Display
```

不得使用软件解码 fallback 的成功结果代替硬件解码验收。

## 9.3 Journald 持久化

目前已有 volatile journal 的问题。

建议在 eMMC 空间允许时配置：

```
# /etc/systemd/journald.conf.d/20-vt13-persistent.conf

[Journal]
Storage=persistent
SystemMaxUse=100M
SystemKeepFree=1G
MaxRetentionSec=7day
```

实际修改由 Worker 按目标系统环境执行。

需要控制：

- 每帧日志写入量。
- Journal 最大容量。
- eMMC 剩余空间。
- 文件系统写入压力。

修改后冷启动验证：

```
journalctl -b -1
```

应能够读取上一轮启动的记录。

如果 eMMC 空间压力大，可以将详细 Soak 日志持续复制到 Ubuntu PC，但必须明确本地与远程日志的保存策略。

# 10. G7–G8：功能验收与稳定性测试

eMMC 能启动只是第一步。

完整验收必须证明系统具备与原 SG USB 环境相同的图传能力，且没有引入新的严重问题。

## 10.1 冷启动测试

执行三次独立 Cold Boot。

每次必须：

1. 保持 SG USB 拔出。
2. 断电并重新上电。
3. 确认 eMMC root。
4. 确认 ca46 自动加载。
5. 确认 `vt13-kiosk.service` 自动启动。
6. 确认 DJI USB 图传正常。
7. 确认 HDMI 输出。
8. 记录 FPS、sessions、errors、`0xf`。

结果格式：

```
Cold Boot #1:
  Root filesystem:
  Kernel:
  DTB:
  VDEC loaded:
  Service active:
  Service user:
  USB detected:
  HDMI display:
  FPS:
  Sessions:
  Errors:
  0xf count:
  Result: PASS / FAIL
```

三次均需要保存独立结果。

## 10.2 Soft Reboot 测试

此前曾发生一次软重启卡死，因此必须单独测试。

在现场具备断电恢复能力的前提下执行一次：

```
sudo reboot
```

记录：

```
Reboot started:
Reboot completed:
SSH recovered:
HDMI recovered:
Worker recovered:
VDEC recovered:
Result:
```

如果发生卡死：

- 保存能够取得的日志。
- 记录失败发生阶段。
- 通过现场冷断电恢复。
- 将问题保留为 OPEN。

硬断电恢复成功不能算作 soft reboot PASS。

## 10.3 30 分钟 Soak

目标配置：

```
CM311-1S
eMMC boot
ca46 meson-vdec
eb1dbb67 native worker
KMS kiosk
Real DJI USB video
```

执行连续 30 分钟测试。

需要记录：

| 指标                 | 要求         |
| ------------------ | ---------- |
| Duration           | 30 分钟      |
| FPS mean           | 目标约 60 FPS |
| FPS low percentile | 必须记录       |
| Sessions           | 记录实际数量     |
| Decoder errors     | 记录实际数量     |
| `0xf` aborts       | 记录次数和触发情形  |
| Recovery freeze    | 记录最长时间     |
| HDMI black screen  | 记录次数和持续时间  |
| CPU                | 记录         |
| Memory             | 记录         |
| Temperature        | 记录         |
| Disk space         | 记录         |
| Service restarts   | 记录         |
| USB reconnects     | 记录         |

必须关注长时间画面表现，而不只是 FPS 平均值。

特别是：

- 是否存在可见卡顿。
- 是否有周期性冻结。
- 是否发生意外重启。
- 是否有画面闪烁。
- 是否出现明显图传延迟。

历史最佳 60.4 FPS 不能作为这次 Soak 的实际结果。

## 10.4 分辨率变化测试

已知系统曾修复：

```
1832x1032 → 1920x1080
```

需要在部署后重新验证该路径。

检查：

- 分辨率切换。
- V4L2 buffer 处理。
- KMS plane 更新。
- 无异常裁剪。
- 无永久冻结。
- 无严重画面错误。

## 10.5 USB Hotplug 测试

在服务运行状态下断开并重新连接 DJI USB 设备。

预期：

```
USB disconnected
      ↓
Worker detects disconnect
      ↓
USB reconnected
      ↓
Device reinitialization
      ↓
Video recovery
```

要求：

- 不需要人工重新启动服务。
- 不需要系统重启。
- 恢复后正常硬件解码。
- 记录恢复时间。
- 保留日志。

## 10.6 `0xf` Abort 验证

现有系统仍存在内容相关 `0xf` abort。

必须记录：

```
Test duration:
Content / scenario:
0xf count:
Timestamp:
Freeze duration:
Recovery result:
Service restart:
Video restored:
```

如果再次出现约 217–283 ms 的冻结，应保留原始证据。

不能因为平均 FPS 正常就忽略冻结。

这次迁移原则上不要求同时修复所有 `0xf` 问题，但如果 eMMC 版本明显劣于 SG USB 基线，应标记为回归。

## 10.7 Glass-to-glass Latency

这个问题仍属于 L1 OPEN。

建议在条件允许时进行实际延迟测量。

可以使用同步可见事件和高速拍摄方式，记录：

- 测量方法。
- 帧率。
- 样本数量。
- 平均延迟。
- 延迟分布。
- 最大延迟。
- 测量不确定性。

如果没有条件测量：

```
L1 = OPEN
Glass-to-glass latency = NOT MEASURED
```

不能以解码时间或处理队列时间冒充端到端图传延迟。

# 11. 故障处理与回滚

## 11.1 安装前失败

| 故障            | 处理方式                   |
| ------------- | ---------------------- |
| 备份失败          | 重新备份，禁止刷写              |
| SHA256 不匹配    | 重新验证源文件及备份             |
| PC 仓库版本不一致    | 保存差异，补齐运行文件            |
| 精简后仍超过 eMMC   | 修改文件集，不删除 SG USB       |
| 安装器无法安全修改     | 停止，改进脚本或使用 Staging USB |
| DTB 不兼容风险无法控制 | 停止安装                   |
| eMMC 设备不明确    | 停止安装                   |
| Boot 恢复方案不可靠  | 停止安装                   |

## 11.2 eMMC 安装失败

如果安装过程中失败：

1. 立即停止后续写入。
2. 保存安装日志。
3. 记录已完成的分区及 bootloader 修改。
4. 不要反复运行安装器。
5. 根据提前验证的恢复方式，尝试恢复 SG USB 启动。
6. 验证 SG USB 系统仍可运行。
7. 分析失败原因。
8. 形成新的安装方案并重新审批。

## 11.3 eMMC 无法启动

优先：

```
Power off
    ↓
Apply verified USB/serial rescue procedure
    ↓
Boot SG USB
    ↓
Check root source
    ↓
Check kernel and ca46
    ↓
Start kiosk
    ↓
Verify video
```

注意，若 eMMC 安装改变了启动优先级或 bootloader，可能需要串口或其他救援流程。

不能假定插回 USB 就必然启动。

## 11.4 eMMC 启动但图传失败

严格按照以下顺序排查：

```
Boot / Rootfs
      ↓
Kernel / DTB
      ↓
ca46 module
      ↓
USB device
      ↓
V4L2 Decoder
      ↓
Worker binary / dependencies
      ↓
DMA-BUF / KMS
      ↓
HDMI
      ↓
systemd integration
```

不得未经分析直接升级 Kernel 或替换 FFmpeg。

## 11.5 回滚验收

如果需要回滚，必须真正启动原 SG USB 并检查：

```
Root filesystem = SG USB
ca46 module loaded
vt13-kiosk active
Non-root service
DJI USB detected
Video decoding working
HDMI output working
FPS recorded
Errors recorded
```

必须记录是否需要额外的 bootloader 或串口恢复步骤。

# 12. Worker 最终必须提交的资料

## 12.1 文档目录

所有完整备份和原始证据保存在 Ubuntu PC。

建议将脱敏后的审计与交接文档提交到图传仓库：

```
docs/
└── deployments/
    └── cm311-emmc-YYYYMMDD/
        ├── 00_preflight.md
        ├── 01_baseline.md
        ├── 02_repository_parity.md
        ├── 03_backup_manifest.md
        ├── 04_storage_budget.md
        ├── 05_installer_audit.md
        ├── 06_dtb_ca46_boot.md
        ├── 07_r3_approval.md
        ├── 08_installation_log.md
        ├── 09_postboot.md
        ├── 10_soak.md
        ├── 11_rollback.md
        ├── 12_final_handoff.md
        └── manifest.sha256
```

不应将完整磁盘镜像、私钥或敏感采集数据直接提交 Git 仓库。

### 00_preflight.md

包含：

- 设备型号。
- SG USB 和 eMMC 身份。
- 网络及 SSH。
- PC 空间。
- 启动方式。
- 物理恢复方式。
- G0 状态。

### 01_baseline.md

包含：

- Kernel。
- DTB。
- ca46。
- Worker。
- FFmpeg。
- PyAV。
- systemd。
- 运行用户。
- FPS、errors、`0xf` 基线。
- 对应二进制 SHA256。

### 02_repository_parity.md

包含：

- Ubuntu PC 仓库版本。
- CM311 仓库版本。
- 未提交差异。
- 未追踪文件。
- 构建产物比较。
- 配置差异。
- 最终 MATCH / PARTIAL / MISMATCH。

### 03_backup_manifest.md

对每项备份记录：

```
Source path:
PC backup path:
Backup time:
File size:
SHA256:
Permissions:
Owner:
Verification:
Restore test:
```

### 04_storage_budget.md

包含：

- eMMC 实际容量。
- 待复制文件集合。
- Include / Exclude。
- 精简前后容量。
- 目标可用空间。
- 被排除文件的 PC 备份路径。

### 05_installer_audit.md

包含：

- 安装器路径和版本。
- 原始脚本 SHA256。
- 审核后脚本 SHA256。
- Patch 和 diff。
- 所有源 SG USB 写入副作用。
- 所有目标 eMMC 写入操作。
- 分区、bootloader 和 DTB 策略。

### 06_dtb_ca46_boot.md

包含：

- 当前 DTB。
- 目标 DTB。
- DTB 差异。
- Kernel 和 module ABI。
- 静态与动态验证证据。
- 启动恢复方法。
- G4 状态。

### 07_r3_approval.md

包含：

- 审批人。
- 审批时间。
- 真实目标磁盘。
- 安装器 SHA256。
- 批准的安装流程。
- 保留风险。

### 08_installation_log.md

包含：

- 完整执行命令。
- 开始和结束时间。
- 退出码。
- 分区变化。
- 文件复制结果。
- Bootloader 和 DTB 安装。
- 错误及处理方式。

### 09_postboot.md

包含：

- eMMC-only 启动证明。
- Kernel。
- DTB。
- ca46。
- USB。
- HDMI。
- systemd。
- 运行环境。
- 剩余空间。

### 10_soak.md

包含：

- 三次 cold boot。
- 一次 soft reboot。
- 30 分钟 Soak。
- FPS。
- Sessions。
- Errors。
- `0xf`。
- Freeze。
- Hotplug。
- Latency 状态。

### 11_rollback.md

包含：

- 恢复介质。
- Bootloader / 串口恢复条件。
- 可执行回滚步骤。
- 回滚后验证结果。

### 12_final_handoff.md

包含所有部署结果和仍未解决的问题。

## 12.2 最终交接 YAML 模板

Worker 应在最终交接文件中填入实际数据。

```
deployment:
  project: VT13 USB Video Kiosk
  hardware: CM311-1S
  soc: s905l3b
  model_id: 127

  installation:
    target: internal_emmc
    filesystem: ext4
    status: PENDING

  backup:
    host: Ubuntu_PC
    directory: <actual_pc_path>
    validation: PENDING
    rootfs_archive: <path_and_sha256>
    boot_archive: <path_and_sha256>
    usb_disk_image: <path_or_not_taken>
    emmc_original: <path_or_not_required>

  repository:
    pc_commit: <actual>
    cm311_commit: <actual>
    parity: MATCH_OR_PARTIAL_OR_MISMATCH
    uncommitted_changes: <actual>

  source_usb:
    identity: <actual_serial_uuid>
    preserved: true
    source_writes: <none_or_approved_changes>
    rollback_tested: false

  installer:
    strategy: <reviewed_selective_installer>
    path: <actual_path>
    sha256: <actual_hash>
    exclude_manifest: <path>
    source_side_effects: <audited_result>

  emmc:
    block_device: <verified_device>
    root_capacity_gib: <measured>
    root_free_gib: <measured>
    dtb: <actual_dtb>
    dtb_sha256: <actual_hash>

  kernel:
    version: <uname_r>
    ca46_module: <actual_path>
    ca46_sha256: <actual_hash>
    ca46_vermagic: <actual>
    auto_load: <pass_or_fail>

  runtime:
    worker_commit: eb1dbb67
    worker_binary_sha256: <actual>
    ffmpeg_path: <actual>
    pyav_venv_path: <actual_or_not_required>
    service: vt13-kiosk.service
    non_root: <verified>
    enabled: <verified>

  tests:
    emmc_only_boot: PENDING
    cold_boot_passes: 0
    cold_boot_required: 3
    soft_reboot: NOT_RUN
    usb_hotplug: NOT_RUN
    resolution_change: NOT_RUN

  soak:
    duration_minutes: 0
    fps_mean: null
    fps_low_percentile: null
    sessions: null
    errors: null
    abort_0xf_count: null
    max_freeze_ms: null
    glass_to_glass_ms: null

  approvals:
    r3_flash: NOT_APPROVED
    approval_reference: null

  acceptance:
    deployment: PENDING
    k3: ACCEPTED_WITH_LIMITATION

  open_issues:
    - R1_0xf_abort
    - L1_glass_to_glass_latency
    - soft_reboot_if_unresolved
    - upstream_vdec_audit
```

# 13. 最终验收标准与状态

## 13.1 可以认定为部署成功的条件

满足：

- eMMC 可以独立冷启动。
- Root 文件系统确实来自内部 eMMC。
- Kernel 和 DTB 正常。
- ca46 正常加载。
- Native Worker 正常。
- KMS 和 HDMI 正常。
- systemd 非 root 自动启动。
- DJI USB 图传正常。
- USB Hotplug 正常。
- 30 分钟 Soak 完成。
- 三次冷启动通过。
- Soft reboot 已测试并如实记录结果。
- 已知故障和新增回归均有完整记录。
- Ubuntu PC 备份有效。
- 回滚步骤明确且可执行。

如果核心部署条件满足，但已有 `0xf`、延迟或重启问题仍存在，可以采用：

```
DEPLOYMENT_ACCEPTED_WITH_LIMITATION
```

如果出现关键功能失败或新的严重回归：

```
DEPLOYMENT_FAILED
```

只有单独完成相关问题的后续验收，才可以考虑更高等级的生产状态。

# 14. 给 Worker 的最终执行指令

下面这一段可以直接复制给 Worker。

# CM311-1S eMMC Deployment — Mandatory Worker Instructions

## Objective

Migrate the existing verified VT13 native C worker + ca46 meson-vdec + KMS kiosk system from the SG USB boot environment to the CM311-1S internal eMMC.

The Ubuntu PC already contains a mirror of the VT13 repository and will serve as the primary backup and deployment control host.

The existing SG USB must be preserved as the verified boot fallback. A second staging USB is optional, not mandatory.

## Mandatory execution sequence

Follow the G0–G8 deployment gates strictly:

- G0: Hardware, disk identity, SSH, physical recovery preflight.
- G1: Freeze and record the exact live system.
- G2: Complete offline backup to the Ubuntu PC, SHA256 verification, and representative restore tests.
- G3: Audit installer behavior and prepare a size-verified selective eMMC deployment.
- G4: Verify DTB, ca46 ABI, bootloader compatibility, and recovery feasibility.
- G5: Install to eMMC only after explicit R3 approval.
- G6: Boot from eMMC without the SG USB and restore/verify every runtime layer.
- G7: Run the full video pipeline regression tests.
- G8: Complete cold-boot, reboot, 30-minute soak, acceptance, and handoff.

## Backup requirements

The Ubuntu PC must receive real copies of:

- Current VT13 source and uncommitted modifications.
- Actual native worker binary and configuration.
- ca46 VDEC module, source, patches, and build dependencies.
- Kernel and boot artifacts.
- Actual DTB, uEnv.txt, and boot configuration.
- Custom FFmpeg runtime and required shared libraries.
- PyAV virtual environment and dependencies where required.
- systemd services, drop-ins, udev rules, permissions, and module-loading configuration.
- Required captures, debug artifacts, and logs.
- Root filesystem archive, with supplementary archives for other mounted filesystems as necessary.
- SHA256 manifests and restore-test evidence.

The existing Ubuntu PC Git repository must be compared against the actual CM311 deployed runtime. Do not assume Git parity means runtime parity.

Backups and records are different. A recorded SHA256 does not constitute a backup.

## Installation requirements

The current source installation is approximately 15.3 GiB, while the target eMMC root is approximately 6.3 GiB.

Do not install the original full rootfs directly.

Audit the exact target-board `armbian-install` implementation, including:

- Source-side writes.
- Rootfs copy paths.
- Target block device discovery.
- Partitioning and formatting.
- Bootloader changes.
- DTB selection.
- Root UUID and fstab modification.

Prepare and review a selective installation plan without deleting the original SG USB contents.

Preserve all runtime dependencies and verify the deployment payload size before writing to eMMC.

Do not silently modify or replace the system installer.

## Safety rules

**During the initial assignment, execute G0–G2 only.**

Do not perform any eMMC write, destructive partition operation, SG USB cleanup, kernel upgrade, DTB replacement, or bootloader modification.

After G0–G2, submit an audit and backup report.

G3–G4 must be completed and reviewed before requesting R3 installation approval.

If any gate is BLOCKED, stop and report the exact reason.

If the direct SG USB + Ubuntu PC installation route cannot be made safe, recommend a staging USB instead.

## Acceptance requirements

After authorized installation:

1. Remove the SG USB.
2. Verify internal eMMC root filesystem.
3. Verify ca46 auto-load and correct kernel ABI.
4. Verify the native worker and its exact runtime dependencies.
5. Verify non-root systemd startup.
6. Verify the complete hardware decode and KMS display pipeline.
7. Test USB hotplug and resolution changes.
8. Perform three cold boots and one supervised soft reboot.
9. Perform a fresh 30-minute soak on the final worker + ca46 combination.
10. Record FPS, sessions, errors, 0xf aborts, freeze duration, latency status, and regressions.
11. Produce complete deployment and rollback documentation.

Do not claim that glass-to-glass latency or 0xf abort issues have been solved without actual measurements and evidence.

Retain the current K3 status as `ACCEPTED_WITH_LIMITATION` until separately justified.

## Required immediate deliverables

Before requesting installation approval, deliver:

- `00_preflight.md`
- `01_baseline.md`
- `02_repository_parity.md`
- `03_backup_manifest.md`
- Backup SHA256 verification results
- Representative restore-test results
- `04_storage_budget.md`
- `05_installer_audit.md`
- `06_dtb_ca46_boot.md`
- Explicit PASS / FAIL / BLOCKED status for each gate

**Do not proceed to eMMC installation without explicit authorization.**

## 15. 参考资料与执行边界

Worker 需要同时参考仓库中已有的：

```
docs/REMOTE_MACHINE_USAGE.md
```

特别是原有 Phase 0–7 的部署内容。若新旧流程存在冲突，必须写入决策记录，并以实际运行环境及审批后的安装方案为准。

上游参考：

- ophub Armbian 项目
- 上游 armbian-install 脚本
- ophub 中文文档

上述安装器信息属于上游参考，目标设备的实际脚本可能不同。所有安装命令、磁盘设备和启动配置均必须经过实机审计。

最后的执行边界： 当前计划不代表 eMMC、目标 DTB 或选择性安装脚本已经完成测试。Worker 必须用实际运行证据确认每个 Gate，不能将计划中的预期结果填写为已通过。
