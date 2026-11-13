#!/usr/bin/env bash
set -Eeuo pipefail

TARGET=/dev/mmcblk2
TARGET_BYTES=7474249728
STAGE=/home/billieguo/mobile_vt/.codex_tmp/emmc_deploy_20261112/g5
INSTALLER="$STAGE/armbian-install-final.sh"
INSTALLER_PATCH="$STAGE/armbian-install-final.patch"
EXCLUDE_FILE="$STAGE/emmc-exclude.txt"
SERVICE_FILE="$STAGE/vt13-kiosk.service"

EXPECTED_INSTALLER_SHA=90cb03905726b2aa3cfa5f2948f552694ab992642c750c1938cacd1bad5b5c12
EXPECTED_INSTALLER_PATCH_SHA=175920b50b288a597d98e8209e0b575b067531042163756fbf7ff6bc2c2c5bf2
EXPECTED_EXCLUDE_SHA=58b8fe241085f4cd996ea84340148aea2f5919bfca55e234542b28ca1fc6b88a
EXPECTED_SERVICE_SHA=3ed774081ba0e95f57fff253ae2c5fb5b76f0c5f2a65d00405741fded65149f1
EXPECTED_BOOTLOADER_SHA=f61b153c1ec98ce54ee770be43198af2d2ac60642cc6004500cfbd3b87490262
EXPECTED_WORKER_SHA=eb1dbb67f3193ddcbc5f37f7793f30b7b117c00e9626fb6a4ab68fbc19a95008
EXPECTED_CONFIG_SHA=1a6160d1ff9f7949c71a2c4670bf3776d41e9f9d7919f260c991dbc7eee2d37b
EXPECTED_KIOSK_YAML_SHA=d4d155f2c683ccb93870baea1ca1790e2f60bb228ff644378874c990448ebaa1
EXPECTED_KMS_RENDER_SHA=a071cfed7cc6ec026730286ef1f987b518838b2559605756822d9ef49ee74ecd
EXPECTED_KMS_RENDER_C_SHA=fbd8c4390075235eccce675573c7a6ec4344f41c0ce9fe9532ded5911fe2c6b2
EXPECTED_JOURNALD_SHA=f39e019b8374cb5f5f95d03993681a9cb61a72b360bddb4264f2caff6a1984f0
EXPECTED_UDEV_SHA=9509a4c1c2be9e0d393fb82b61afcf4a891de7f581a8b913f76b9d0acfaa81dc
EXPECTED_MODULE_SHA=ca46798328e0975290151c40e1ddbf191a277b563a9694344aca910507aacdab
EXPECTED_FIRMWARE_SHA=f13362950539e9e1594625908540dee54c143432b7900ee198d5ef17a62c58d1

EXPECTED_BOOT_SCR_SHA=051b13f6f5f85624a253198d3048ed6e0d00fa65654a049ed77d5ab2a054478e
EXPECTED_BOOT_CMD_SHA=6a1d2600e5b82fe80a7133c9f540d0d7618d9250e53a9300c89024d5a6e168be
EXPECTED_BOOT_INI_SHA=2e5a4a6312cf7de56157660a29a09fe7b9142eb5ef7a2c21063aacbde96f6d4f
EXPECTED_ZIMAGE_SHA=4b7b888285d3798140feff5b2fb62c104ed6ca513e0bc735ff4b71f8ffb8a465
EXPECTED_UINITRD_SHA=61bf87252575cbc7c69f6af67ecf8a0da89f24416c33134ad7222277a2d05b92
EXPECTED_DTB_SHA=6bdcf618ab89aea116778b9e97a0ae50e72d167ba0303fc884554e2411e051ed
EXPECTED_UBOOT_BIN_SHA=207cdbe16145bea4602d62cde4c5e1083f30c5742beef714bec259d15c94545c

MODE=${1:-install}
case "$MODE" in
    install|--preflight-only) ;;
    *) printf 'usage: %s [--preflight-only]\n' "$0" >&2; exit 2 ;;
esac

if [[ $EUID -ne 0 ]]; then
    printf 'ERROR: run this wrapper as root (sudo %s)\n' "$0" >&2
    exit 2
fi

RUN_ID=$(date +%Y%m%d_%H%M%S)
RUN_DIR="$STAGE/run_$RUN_ID"
LOG_FILE="$RUN_DIR/armbian-install.log"
EVIDENCE_FILE="$RUN_DIR/postinstall-evidence.txt"
RESULT_FILE="$RUN_DIR/g5-result.env"
MOUNT_BASE="$RUN_DIR/mounts"
BOOT_MNT="$MOUNT_BASE/boot"
ROOT_MNT="$MOUNT_BASE/root"
BOOTLOADER_EXPORT="$RUN_DIR/mybox-bootloader.img"
MBR_EXPORT="$RUN_DIR/mbr-first512.bin"
KIOSK_STOPPED=0
BOOT_MOUNTED=0
ROOT_MOUNTED=0

mkdir -p "$RUN_DIR"
ln -sfn "$RUN_DIR" "$STAGE/g5-latest"

write_result() {
    local status=$1
    {
        printf 'STATUS=%s\n' "$status"
        printf 'TIMESTAMP=%s\n' "$(date -Is)"
        printf 'TARGET=%s\n' "$TARGET"
        printf 'LOG_PATH=%s\n' "$LOG_FILE"
        printf 'EVIDENCE_PATH=%s\n' "$EVIDENCE_FILE"
    } > "$RESULT_FILE"
}

die() {
    printf 'G5_ERROR: %s\n' "$*" >&2
    write_result FAILED
    exit 1
}

on_exit() {
    local rc=$?
    set +e
    if (( ROOT_MOUNTED )); then umount "$ROOT_MNT"; fi
    if (( BOOT_MOUNTED )); then umount "$BOOT_MNT"; fi
    rmdir "$ROOT_MNT" "$BOOT_MNT" "$MOUNT_BASE" 2>/dev/null || true
    if (( rc != 0 && KIOSK_STOPPED )); then
        systemctl start vt13-kiosk.service || true
    fi
    chown -R billieguo:billieguo "$RUN_DIR" 2>/dev/null || true
    exit "$rc"
}
trap on_exit EXIT

sha256_of() {
    sha256sum "$1" | awk '{print $1}'
}

expect_sha() {
    local path=$1
    local expected=$2
    local actual
    [[ -f "$path" ]] || die "missing file: $path"
    actual=$(sha256_of "$path")
    [[ "$actual" == "$expected" ]] || die "hash mismatch: $path actual=$actual expected=$expected"
}

expect_regular() {
    local path=$1
    [[ -f "$path" ]] || die "missing file: $path"
}

preflight() {
    local first4m_sha boot0_sha boot1_sha

    for tool in sha256sum head awk grep stat findmnt lsblk blockdev parted blkid mount umount df cmp od \
        systemctl script tar install partprobe udevadm sfdisk cp readlink cut tr cat ln date hostname id \
        mkdir rmdir chown hexdump mkfs.vfat mkfs.ext4 mkfs.btrfs losetup fdisk dbus-uuidgen; do
        command -v "$tool" >/dev/null 2>&1 || die "missing command: $tool"
    done

    [[ -d "$STAGE" ]] || die "missing staging directory: $STAGE"
    expect_sha "$INSTALLER" "$EXPECTED_INSTALLER_SHA"
    expect_sha "$INSTALLER_PATCH" "$EXPECTED_INSTALLER_PATCH_SHA"
    expect_sha "$EXCLUDE_FILE" "$EXPECTED_EXCLUDE_SHA"
    expect_sha "$SERVICE_FILE" "$EXPECTED_SERVICE_SHA"

    [[ -b "$TARGET" ]] || die "target is not a block device: $TARGET"
    [[ "$(blockdev --getsize64 "$TARGET")" == "$TARGET_BYTES" ]] || die "unexpected target size"

    [[ "$(findmnt -no SOURCE /)" == /dev/sda2 ]] || die "source / is not /dev/sda2"
    [[ "$(findmnt -no SOURCE /boot)" == /dev/sda1 ]] || die "source /boot is not /dev/sda1"
    [[ "$(findmnt -no FSTYPE /)" == ext4 ]] || die "source / is not ext4"
    [[ "$(findmnt -no FSTYPE /boot)" == vfat ]] || die "source /boot is not vfat"

    expect_sha /boot/boot-emmc.scr "$EXPECTED_BOOT_SCR_SHA"
    expect_sha /boot/boot-emmc.cmd "$EXPECTED_BOOT_CMD_SHA"
    expect_sha /boot/boot-emmc.ini "$EXPECTED_BOOT_INI_SHA"
    expect_sha /boot/zImage "$EXPECTED_ZIMAGE_SHA"
    expect_sha /boot/uInitrd "$EXPECTED_UINITRD_SHA"
    expect_sha /boot/u-boot-s905x-s912.bin "$EXPECTED_UBOOT_BIN_SHA"
    expect_sha /boot/dtb/amlogic/meson-gxl-s905l3b-m302a-gxl-test.dtb "$EXPECTED_DTB_SHA"
    expect_sha /home/billieguo/mobile_vt/.codex_tmp/kiosk_20261110/kms_render "$EXPECTED_KMS_RENDER_SHA"
    expect_sha /home/billieguo/mobile_vt/.codex_tmp/kiosk_20261110/kms_render.c "$EXPECTED_KMS_RENDER_C_SHA"

    mapfile -t emmc_disks < <(lsblk -dn -o NAME,TYPE | awk '$2 == "disk" && $1 ~ /^mmcblk[0-9]+$/ {print "/dev/" $1}')
    [[ ${#emmc_disks[@]} -eq 1 ]] || die "expected exactly one eMMC disk, found ${#emmc_disks[@]}"
    [[ "${emmc_disks[0]}" == "$TARGET" ]] || die "unexpected eMMC target: ${emmc_disks[0]}"

    [[ -b "${TARGET}boot0" && -b "${TARGET}boot1" ]] || die "missing eMMC boot partitions"
    [[ "$(blockdev --getsize64 "${TARGET}boot0")" == 4194304 ]] || die "unexpected boot0 size"
    [[ "$(blockdev --getsize64 "${TARGET}boot1")" == 4194304 ]] || die "unexpected boot1 size"
    [[ "$(cat /sys/block/mmcblk2boot0/force_ro)" == 1 ]] || die "boot0 force_ro is not 1"
    [[ "$(cat /sys/block/mmcblk2boot1/force_ro)" == 1 ]] || die "boot1 force_ro is not 1"

    if [[ -n "$(lsblk -ln -o MOUNTPOINTS "$TARGET")" ]]; then
        die "target or a target child is mounted"
    fi

    first4m_sha=$(head -c 4194304 "$TARGET" | sha256sum | awk '{print $1}')
    [[ "$first4m_sha" == "$EXPECTED_BOOTLOADER_SHA" ]] || die "eMMC first 4 MiB changed before G5"
    boot0_sha=$(head -c 4194304 "${TARGET}boot0" | sha256sum | awk '{print $1}')
    boot1_sha=$(head -c 4194304 "${TARGET}boot1" | sha256sum | awk '{print $1}')
    [[ "$boot0_sha" == "$EXPECTED_BOOTLOADER_SHA" ]] || die "boot0 hash changed before G5"
    [[ "$boot1_sha" == "$EXPECTED_BOOTLOADER_SHA" ]] || die "boot1 hash changed before G5"
    head -c 1024 "$TARGET" | grep -a -q '@AML' || die "missing @AML vendor bootloader header"

    if [[ -e /usr/lib/u-boot/mybox-bootloader.img ]]; then
        [[ "$(sha256_of /usr/lib/u-boot/mybox-bootloader.img)" == "$EXPECTED_BOOTLOADER_SHA" ]] || \
            die "existing mybox-bootloader.img does not match the current eMMC first 4 MiB"
    fi

    {
        printf 'G5_PREFLIGHT\n'
        date -Is
        printf 'TARGET=%s\n' "$TARGET"
        printf 'TARGET_BYTES=%s\n' "$TARGET_BYTES"
        printf 'SOURCE_ROOT=%s\n' "$(findmnt -no SOURCE /)"
        printf 'SOURCE_BOOT=%s\n' "$(findmnt -no SOURCE /boot)"
        printf 'EMMC_FIRST4M_SHA256=%s\n' "$first4m_sha"
        printf 'BOOT0_SHA256=%s\n' "$boot0_sha"
        printf 'BOOT1_SHA256=%s\n' "$boot1_sha"
        printf 'MYBOX_BOOTLOADER_EXISTS=%s\n' "$([[ -e /usr/lib/u-boot/mybox-bootloader.img ]] && echo yes || echo no)"
        printf 'KIOSK_STATE=%s\n' "$(systemctl is-active vt13-kiosk.service 2>/dev/null || true)"
        printf '\n--- source boot hashes ---\n'
        sha256sum /boot/boot-emmc.scr /boot/boot-emmc.cmd /boot/boot-emmc.ini \
            /boot/zImage /boot/uInitrd /boot/u-boot-s905x-s912.bin \
            /boot/dtb/amlogic/meson-gxl-s905l3b-m302a-gxl-test.dtb
        printf '\n--- source kms hashes ---\n'
        sha256sum /home/billieguo/mobile_vt/.codex_tmp/kiosk_20261110/kms_render \
            /home/billieguo/mobile_vt/.codex_tmp/kiosk_20261110/kms_render.c
        printf '\n--- lsblk ---\n'
        lsblk -b -o NAME,PATH,START,SIZE,TYPE,FSTYPE,LABEL,UUID,MOUNTPOINTS "$TARGET"
        printf '\n--- staging hashes ---\n'
        sha256sum "$INSTALLER" "$INSTALLER_PATCH" "$EXCLUDE_FILE" "$SERVICE_FILE"
    } > "$RUN_DIR/preflight.txt"

    printf 'G5_PREFLIGHT_OK\n'
    printf 'G5_PREFLIGHT=%s\n' "$RUN_DIR/preflight.txt"
    write_result PREFLIGHT_OK
}

validate_install() {
    local p1_start p1_size p1_fstype p1_label
    local p2_start p2_size p2_fstype p2_label
    local root_uuid layout ampart_status
    local backup_source backup_target target4m_sha boot0_sha boot1_sha mbr_sig
    local bootloader_export_sha mbr_export_sha
    local root_avail root_inodes boot_avail boot_inodes
    local service_hash repo_service_hash journald_hash udev_hash module_hash firmware_hash
    local log_sha evidence_sha

    grep -q 'Detected eMMC device: \[ /dev/mmcblk2 \]' "$LOG_FILE" || die "installer log lacks target detection"
    grep -q 'Installation completed successfully' "$LOG_FILE" || die "installer log lacks success marker"

    partprobe "$TARGET" 2>/dev/null || true
    udevadm settle 2>/dev/null || true
    sync

    [[ -b "${TARGET}p1" && -b "${TARGET}p2" ]] || die "eMMC partitions p1/p2 are missing"

    read -r p1_start p1_size p1_fstype p1_label < <(lsblk -bno START,SIZE,FSTYPE,LABEL "${TARGET}p1")
    read -r p2_start p2_size p2_fstype p2_label < <(lsblk -bno START,SIZE,FSTYPE,LABEL "${TARGET}p2")

    [[ "$p1_fstype" == vfat && "$p1_label" == BOOT_EMMC ]] || die "unexpected p1 filesystem/label"
    [[ "$p2_fstype" == ext4 && "$p2_label" == ROOTFS_EMMC ]] || die "unexpected p2 filesystem/label"
    (( p1_size >= 500 * 1024 * 1024 && p1_size <= 540 * 1024 * 1024 )) || die "unexpected p1 size: $p1_size"

    if (( p2_start == 659554304 && p2_size >= 6814695424 - 1048576 && p2_size <= 6814695424 + 1048576 )); then
        layout=ampart
        (( p1_start == 122683392 )) || die "ampart p1 start mismatch: $p1_start"
    elif (( p2_start == 1426063360 && p2_size >= 6048186368 - 1048576 && p2_size <= 6048186368 + 1048576 )); then
        layout=fallback
        (( p1_start == 134217728 )) || die "fallback p1 start mismatch: $p1_start"
    else
        die "unexpected eMMC layout: p1_start=$p1_start p2_start=$p2_start p2_size=$p2_size"
    fi

    [[ -z "$(lsblk -ln -o MOUNTPOINTS "${TARGET}p1" "${TARGET}p2")" ]] || die "eMMC partitions are unexpectedly mounted"

    mkdir -p "$BOOT_MNT" "$ROOT_MNT"
    mount -o ro "${TARGET}p1" "$BOOT_MNT" || die "failed to mount eMMC boot partition read-only"
    BOOT_MOUNTED=1
    mount -o ro "${TARGET}p2" "$ROOT_MNT" || die "failed to mount eMMC root partition read-only"
    ROOT_MOUNTED=1

    expect_sha "$BOOT_MNT/boot.scr" "$EXPECTED_BOOT_SCR_SHA"
    expect_sha "$BOOT_MNT/boot.cmd" "$EXPECTED_BOOT_CMD_SHA"
    expect_sha "$BOOT_MNT/boot.ini" "$EXPECTED_BOOT_INI_SHA"
    expect_sha "$BOOT_MNT/zImage" "$EXPECTED_ZIMAGE_SHA"
    expect_sha "$BOOT_MNT/uInitrd" "$EXPECTED_UINITRD_SHA"
    expect_sha "$BOOT_MNT/u-boot-s905x-s912.bin" "$EXPECTED_UBOOT_BIN_SHA"
    expect_sha "$BOOT_MNT/dtb/amlogic/meson-gxl-s905l3b-m302a-gxl-test.dtb" "$EXPECTED_DTB_SHA"

    root_uuid=$(lsblk -no UUID "${TARGET}p2")
    [[ -n "$root_uuid" ]] || die "target root UUID is empty"
    grep -q '^FDT=/dtb/amlogic/meson-gxl-s905l3b-m302a-gxl-test.dtb$' "$BOOT_MNT/uEnv.txt" || \
        die "target uEnv.txt does not select the -gxl-test DTB"
    grep -q "root=UUID=$root_uuid" "$BOOT_MNT/uEnv.txt" || die "target uEnv.txt does not use the target root UUID"
    grep -q '^LINUX=/zImage$' "$BOOT_MNT/uEnv.txt" || die "target uEnv.txt LINUX mismatch"
    grep -q '^INITRD=/uInitrd$' "$BOOT_MNT/uEnv.txt" || die "target uEnv.txt INITRD mismatch"

    grep -Eq "^UUID=$root_uuid[[:space:]]+/[[:space:]]+ext4" "$ROOT_MNT/etc/fstab" || die "target fstab root UUID mismatch"
    grep -Eq '^LABEL=BOOT_EMMC[[:space:]]+/boot[[:space:]]+vfat' "$ROOT_MNT/etc/fstab" || die "target fstab boot entry mismatch"

    expect_sha "$ROOT_MNT/home/billieguo/mobile_vt/build/d3/d3_probe" "$EXPECTED_WORKER_SHA"
    expect_sha "$ROOT_MNT/home/billieguo/mobile_vt/vt13_video/config.py" "$EXPECTED_CONFIG_SHA"
    expect_sha "$ROOT_MNT/home/billieguo/mobile_vt/config/vt13_video.kiosk.yaml" "$EXPECTED_KIOSK_YAML_SHA"
    expect_sha "$ROOT_MNT/home/billieguo/mobile_vt/.codex_tmp/kiosk_20261110/kms_render" "$EXPECTED_KMS_RENDER_SHA"
    expect_sha "$ROOT_MNT/home/billieguo/mobile_vt/.codex_tmp/kiosk_20261110/kms_render.c" "$EXPECTED_KMS_RENDER_C_SHA"
    [[ -x "$ROOT_MNT/home/billieguo/mobile_vt/.codex_tmp/kiosk_20261110/kms_render" ]] || die "target kms_render is not executable"
    expect_sha "$ROOT_MNT/etc/systemd/system/vt13-kiosk.service" "$EXPECTED_SERVICE_SHA"
    expect_sha "$ROOT_MNT/home/billieguo/mobile_vt/deploy/vt13-kiosk.service" "$EXPECTED_SERVICE_SHA"
    expect_sha "$ROOT_MNT/etc/systemd/journald@vt13-kiosk.conf" "$EXPECTED_JOURNALD_SHA"
    expect_sha "$ROOT_MNT/etc/udev/rules.d/99-vt13.rules" "$EXPECTED_UDEV_SHA"
    expect_sha "$ROOT_MNT/usr/lib/modules/6.18.59-ophub/kernel/drivers/staging/media/meson/vdec/meson-vdec.ko" "$EXPECTED_MODULE_SHA"
    expect_sha "$ROOT_MNT/usr/lib/firmware/meson/vdec/gxl_hevc.bin" "$EXPECTED_FIRMWARE_SHA"
    expect_sha "$ROOT_MNT/usr/lib/u-boot/mybox-bootloader.img" "$EXPECTED_BOOTLOADER_SHA"

    expect_regular "$ROOT_MNT/usr/bin/python3"
    [[ -x "$ROOT_MNT/usr/bin/python3" ]] || die "target /usr/bin/python3 is not executable"
    [[ -d "$ROOT_MNT/usr/lib/python3/dist-packages/av" ]] || die "target system PyAV directory is missing"
    expect_regular "$ROOT_MNT/usr/lib/aarch64-linux-gnu/libavcodec.so.60"

    [[ "$(cat "$ROOT_MNT/etc/modules-load.d/vt13-vdec.conf")" == meson_vdec ]] || die "target modules-load config mismatch"
    [[ -s "$ROOT_MNT/etc/machine-id" ]] || die "target machine-id is empty"
    cmp -s "$ROOT_MNT/etc/machine-id" "$ROOT_MNT/var/lib/dbus/machine-id" || die "target machine-id copies differ"

    grep -q "^MODEL_ID='127'$" "$ROOT_MNT/etc/ophub-release" || die "target MODEL_ID mismatch"
    grep -q "^FDTFILE='meson-gxl-s905l3b-m302a-gxl-test.dtb'$" "$ROOT_MNT/etc/ophub-release" || die "target FDTFILE mismatch"
    grep -q "^DISK_TYPE='emmc'$" "$ROOT_MNT/etc/ophub-release" || die "target DISK_TYPE mismatch"
    grep -q "^ROOTFS_TYPE='ext4'$" "$ROOT_MNT/etc/ophub-release" || die "target ROOTFS_TYPE mismatch"
    grep -q "^UBOOT_OVERLOAD='u-boot-s905x-s912.bin'$" "$ROOT_MNT/etc/ophub-release" || die "target UBOOT_OVERLOAD mismatch"
    grep -Eq "^AMPART_STATUS='(yes|no)'$" "$ROOT_MNT/etc/ophub-release" || die "target AMPART_STATUS missing"
    ampart_status=$(grep '^AMPART_STATUS=' "$ROOT_MNT/etc/ophub-release" | cut -d= -f2 | tr -d "'")

    [[ -L "$ROOT_MNT/etc/systemd/system/multi-user.target.wants/vt13-kiosk.service" ]] || die "target service enable symlink missing"
    [[ "$(readlink "$ROOT_MNT/etc/systemd/system/multi-user.target.wants/vt13-kiosk.service")" == /etc/systemd/system/vt13-kiosk.service ]] || \
        die "target service enable symlink mismatch"
    [[ "$(systemctl --root="$ROOT_MNT" is-enabled vt13-kiosk.service 2>/dev/null)" == enabled ]] || \
        die "target service is not enabled"
    grep -q '^ExecStart=/usr/bin/python3 -u -m vt13_video stream --config /home/billieguo/mobile_vt/config/vt13_video.kiosk.yaml --headless$' \
        "$ROOT_MNT/etc/systemd/system/vt13-kiosk.service" || die "target service ExecStart mismatch"
    grep -q '^Environment=VT13_ASYNC_USB=0$' "$ROOT_MNT/etc/systemd/system/vt13-kiosk.service" || die "target service environment mismatch"
    grep -q '^User=billieguo$' "$ROOT_MNT/etc/systemd/system/vt13-kiosk.service" || die "target service user mismatch"
    grep -q '^Restart=always$' "$ROOT_MNT/etc/systemd/system/vt13-kiosk.service" || die "target service restart policy mismatch"
    grep -q '^WantedBy=multi-user.target$' "$ROOT_MNT/etc/systemd/system/vt13-kiosk.service" || die "target service install target mismatch"

    [[ -d /ddbr ]] || die "source /ddbr is missing after install"
    expect_sha /ddbr/armbian-install-final.sh "$EXPECTED_INSTALLER_SHA"
    expect_sha /ddbr/armbian-install-final.patch "$EXPECTED_INSTALLER_PATCH_SHA"
    expect_sha /ddbr/emmc-exclude.txt "$EXPECTED_EXCLUDE_SHA"
    expect_sha /ddbr/vt13-kiosk.service "$EXPECTED_SERVICE_SHA"
    expect_sha /boot/boot-emmc.scr "$EXPECTED_BOOT_SCR_SHA"
    expect_sha /boot/boot-emmc.cmd "$EXPECTED_BOOT_CMD_SHA"
    expect_sha /boot/boot-emmc.ini "$EXPECTED_BOOT_INI_SHA"
    expect_sha /boot/zImage "$EXPECTED_ZIMAGE_SHA"
    expect_sha /boot/uInitrd "$EXPECTED_UINITRD_SHA"
    expect_sha /boot/u-boot-s905x-s912.bin "$EXPECTED_UBOOT_BIN_SHA"
    expect_sha /boot/dtb/amlogic/meson-gxl-s905l3b-m302a-gxl-test.dtb "$EXPECTED_DTB_SHA"
    expect_sha /home/billieguo/mobile_vt/.codex_tmp/kiosk_20261110/kms_render "$EXPECTED_KMS_RENDER_SHA"
    expect_sha /home/billieguo/mobile_vt/.codex_tmp/kiosk_20261110/kms_render.c "$EXPECTED_KMS_RENDER_C_SHA"

    backup_source=/usr/lib/u-boot/mybox-bootloader.img
    backup_target="$ROOT_MNT/usr/lib/u-boot/mybox-bootloader.img"
    expect_sha "$backup_source" "$EXPECTED_BOOTLOADER_SHA"
    [[ "$(stat -c %s "$backup_source")" == 4194304 ]] || die "source bootloader backup size mismatch"
    [[ "$(stat -c %s "$backup_target")" == 4194304 ]] || die "target bootloader backup size mismatch"

    cmp -n 444 <(head -c 444 "$TARGET") <(head -c 444 "$backup_source") || die "target bootloader bytes 0-443 differ from backup"
    cmp -n $((4194304 - 512)) -i 512:512 "$TARGET" "$backup_source" || die "target bootloader bytes 512-4194303 differ from backup"
    mbr_sig=$(od -An -tx1 -j 510 -N 2 "$TARGET" | tr -d ' \n')
    [[ "$mbr_sig" == 55aa ]] || die "target MBR signature missing: $mbr_sig"
    head -c 1024 "$TARGET" | grep -a -q '@AML' || die "target @AML header missing after install"

    cp "$backup_source" "$BOOTLOADER_EXPORT"
    head -c 512 "$TARGET" > "$MBR_EXPORT"
    expect_sha "$BOOTLOADER_EXPORT" "$EXPECTED_BOOTLOADER_SHA"
    [[ "$(stat -c %s "$BOOTLOADER_EXPORT")" == 4194304 ]] || die "bootloader export size mismatch"
    [[ "$(stat -c %s "$MBR_EXPORT")" == 512 ]] || die "MBR export size mismatch"
    bootloader_export_sha=$(sha256_of "$BOOTLOADER_EXPORT")
    mbr_export_sha=$(sha256_of "$MBR_EXPORT")

    target4m_sha=$(head -c 4194304 "$TARGET" | sha256sum | awk '{print $1}')
    boot0_sha=$(head -c 4194304 "${TARGET}boot0" | sha256sum | awk '{print $1}')
    boot1_sha=$(head -c 4194304 "${TARGET}boot1" | sha256sum | awk '{print $1}')
    [[ "$boot0_sha" == "$EXPECTED_BOOTLOADER_SHA" ]] || die "boot0 changed during G5"
    [[ "$boot1_sha" == "$EXPECTED_BOOTLOADER_SHA" ]] || die "boot1 changed during G5"

    root_avail=$(df -B1 --output=avail "$ROOT_MNT" | tail -n 1)
    root_inodes=$(df -i --output=iavail "$ROOT_MNT" | tail -n 1)
    boot_avail=$(df -B1 --output=avail "$BOOT_MNT" | tail -n 1)
    boot_inodes=$(df -i --output=iavail "$BOOT_MNT" | tail -n 1)
    (( root_avail >= 1024 * 1024 * 1024 )) || die "target root has less than 1 GiB free: $root_avail"
    (( root_inodes >= 10000 )) || die "target root has too few free inodes: $root_inodes"

    service_hash=$(sha256_of "$ROOT_MNT/etc/systemd/system/vt13-kiosk.service")
    repo_service_hash=$(sha256_of "$ROOT_MNT/home/billieguo/mobile_vt/deploy/vt13-kiosk.service")
    journald_hash=$(sha256_of "$ROOT_MNT/etc/systemd/journald@vt13-kiosk.conf")
    udev_hash=$(sha256_of "$ROOT_MNT/etc/udev/rules.d/99-vt13.rules")
    module_hash=$(sha256_of "$ROOT_MNT/usr/lib/modules/6.18.59-ophub/kernel/drivers/staging/media/meson/vdec/meson-vdec.ko")
    firmware_hash=$(sha256_of "$ROOT_MNT/usr/lib/firmware/meson/vdec/gxl_hevc.bin")

    {
        printf 'G5_POSTINSTALL_EVIDENCE\n'
        date -Is
        printf 'TARGET=%s\n' "$TARGET"
        printf 'LAYOUT=%s\n' "$layout"
        printf 'AMPART_STATUS=%s\n' "$ampart_status"
        printf 'P1_START=%s\n' "$p1_start"
        printf 'P1_SIZE=%s\n' "$p1_size"
        printf 'P2_START=%s\n' "$p2_start"
        printf 'P2_SIZE=%s\n' "$p2_size"
        printf 'ROOT_UUID=%s\n' "$root_uuid"
        printf 'ROOT_AVAIL_BYTES=%s\n' "$root_avail"
        printf 'ROOT_FREE_INODES=%s\n' "$root_inodes"
        printf 'BOOT_AVAIL_BYTES=%s\n' "$boot_avail"
        printf 'BOOT_FREE_INODES=%s\n' "$boot_inodes"
        printf 'BACKUP_SOURCE_SHA256=%s\n' "$(sha256_of "$backup_source")"
        printf 'BACKUP_TARGET_SHA256=%s\n' "$(sha256_of "$backup_target")"
        printf 'BOOTLOADER_EXPORT_SHA256=%s\n' "$bootloader_export_sha"
        printf 'MBR_EXPORT_SHA256=%s\n' "$mbr_export_sha"
        printf 'TARGET_FIRST4M_SHA256=%s\n' "$target4m_sha"
        printf 'BOOT0_SHA256=%s\n' "$boot0_sha"
        printf 'BOOT1_SHA256=%s\n' "$boot1_sha"
        printf 'MBR_SIGNATURE=%s\n' "$mbr_sig"
        printf 'SERVICE_SHA256=%s\n' "$service_hash"
        printf 'REPO_SERVICE_SHA256=%s\n' "$repo_service_hash"
        printf 'JOURNALD_SHA256=%s\n' "$journald_hash"
        printf 'UDEV_SHA256=%s\n' "$udev_hash"
        printf 'MODULE_SHA256=%s\n' "$module_hash"
        printf 'FIRMWARE_SHA256=%s\n' "$firmware_hash"
        printf '\n--- lsblk ---\n'
        lsblk -b -o NAME,PATH,START,SIZE,TYPE,FSTYPE,LABEL,UUID,MOUNTPOINTS "$TARGET"
        printf '\n--- parted ---\n'
        parted -s "$TARGET" unit MiB print
        printf '\n--- sfdisk ---\n'
        sfdisk -d "$TARGET" 2>/dev/null || true
        printf '\n--- mbr first 512 ---\n'
        od -Ax -tx1z -N 512 "$MBR_EXPORT"
        printf '\n--- source mounts ---\n'
        findmnt -no SOURCE,FSTYPE,TARGET /
        findmnt -no SOURCE,FSTYPE,TARGET /boot
        printf '\n--- target usage ---\n'
        df -hT "$ROOT_MNT" "$BOOT_MNT"
        df -i "$ROOT_MNT" "$BOOT_MNT"
        printf '\n--- boot hashes ---\n'
        sha256sum "$BOOT_MNT/boot.scr" "$BOOT_MNT/boot.cmd" "$BOOT_MNT/boot.ini" \
            "$BOOT_MNT/zImage" "$BOOT_MNT/uInitrd" "$BOOT_MNT/u-boot-s905x-s912.bin" \
            "$BOOT_MNT/dtb/amlogic/meson-gxl-s905l3b-m302a-gxl-test.dtb"
        printf '\n--- uEnv.txt ---\n'
        cat "$BOOT_MNT/uEnv.txt"
        printf '\n--- fstab ---\n'
        cat "$ROOT_MNT/etc/fstab"
        printf '\n--- ophub-release selected ---\n'
        grep -E '^(MODEL_ID|FDTFILE|MAINLINE_UBOOT|BOOTLOADER_IMG|UBOOT_OVERLOAD|ROOTFS_TYPE|DISK_TYPE|AMPART_STATUS)=' \
            "$ROOT_MNT/etc/ophub-release" || true
        printf '\n--- service ---\n'
        cat "$ROOT_MNT/etc/systemd/system/vt13-kiosk.service"
        printf '\n--- modules-load ---\n'
        cat "$ROOT_MNT/etc/modules-load.d/vt13-vdec.conf"
    } > "$EVIDENCE_FILE"

    log_sha=$(sha256_of "$LOG_FILE")
    evidence_sha=$(sha256_of "$EVIDENCE_FILE")
    {
        printf 'STATUS=VALIDATED\n'
        printf 'TIMESTAMP=%s\n' "$(date -Is)"
        printf 'TARGET=%s\n' "$TARGET"
        printf 'LAYOUT=%s\n' "$layout"
        printf 'AMPART_STATUS=%s\n' "$ampart_status"
        printf 'P1_START=%s\n' "$p1_start"
        printf 'P1_SIZE=%s\n' "$p1_size"
        printf 'P2_START=%s\n' "$p2_start"
        printf 'P2_SIZE=%s\n' "$p2_size"
        printf 'ROOT_UUID=%s\n' "$root_uuid"
        printf 'BACKUP_SHA256=%s\n' "$EXPECTED_BOOTLOADER_SHA"
        printf 'TARGET_FIRST4M_SHA256=%s\n' "$target4m_sha"
        printf 'LOG_PATH=%s\n' "$LOG_FILE"
        printf 'LOG_SHA256=%s\n' "$log_sha"
        printf 'EVIDENCE_PATH=%s\n' "$EVIDENCE_FILE"
        printf 'EVIDENCE_SHA256=%s\n' "$evidence_sha"
        printf 'BOOTLOADER_BACKUP_PATH=%s\n' "$BOOTLOADER_EXPORT"
        printf 'BOOTLOADER_BACKUP_SHA256=%s\n' "$bootloader_export_sha"
        printf 'MBR_BACKUP_PATH=%s\n' "$MBR_EXPORT"
        printf 'MBR_BACKUP_SHA256=%s\n' "$mbr_export_sha"
    } > "$RESULT_FILE"

    sync
    printf 'G5_VALIDATED\n'
    printf 'G5_RESULT=%s\n' "$RESULT_FILE"
    printf 'G5_LOG=%s\n' "$LOG_FILE"
    printf 'G5_LOG_SHA256=%s\n' "$log_sha"
    printf 'G5_EVIDENCE=%s\n' "$EVIDENCE_FILE"
    printf 'G5_EVIDENCE_SHA256=%s\n' "$evidence_sha"
    printf 'G5_NEXT: copy log/evidence to Ubuntu PC, verify SHA256, then sync and poweroff.\n'
}

printf 'G5 wrapper mode=%s host=%s user=%s\n' "$MODE" "$(hostname)" "$(id -un)"
printf 'G5 run directory=%s\n' "$RUN_DIR"

preflight

if [[ "$MODE" == --preflight-only ]]; then
    printf 'G5_PREFLIGHT_ONLY_COMPLETE\n'
    exit 0
fi

install -d -m 0755 /ddbr
install -m 0755 "$INSTALLER" /ddbr/armbian-install-final.sh
install -m 0644 "$INSTALLER_PATCH" /ddbr/armbian-install-final.patch
install -m 0644 "$EXCLUDE_FILE" /ddbr/emmc-exclude.txt
install -m 0644 "$SERVICE_FILE" /ddbr/vt13-kiosk.service

printf '%s  %s\n' \
    "$EXPECTED_INSTALLER_SHA" /ddbr/armbian-install-final.sh \
    "$EXPECTED_EXCLUDE_SHA" /ddbr/emmc-exclude.txt \
    "$EXPECTED_SERVICE_SHA" /ddbr/vt13-kiosk.service | sha256sum -c - || die "staged /ddbr hashes do not match"

if systemctl is-active --quiet vt13-kiosk.service; then
    systemctl stop vt13-kiosk.service
    KIOSK_STOPPED=1
fi
if systemctl is-active --quiet vt13-kiosk.service; then
    die "vt13-kiosk.service did not stop"
fi

printf 'G5_INSTALLER_START log=%s\n' "$LOG_FILE"
set +e
script -q -e -c "/ddbr/armbian-install-final.sh" "$LOG_FILE"
installer_rc=$?
set -e
printf 'G5_INSTALLER_RC=%s\n' "$installer_rc"

if (( installer_rc != 0 )); then
    write_result INSTALL_FAILED
    printf 'G5_INSTALL_FAILED rc=%s log=%s\n' "$installer_rc" "$LOG_FILE" >&2
    exit "$installer_rc"
fi

validate_install
printf 'G5_INSTALL_COMPLETE_WAITING_FOR_PC_LOG_COPY\n'
