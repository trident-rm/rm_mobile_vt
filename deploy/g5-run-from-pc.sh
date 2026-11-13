#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
CM311=${CM311:-billieguo@10.42.0.11}
REMOTE_STAGE=/home/billieguo/mobile_vt/.codex_tmp/emmc_deploy_20261112/g5
LOCAL_ROOT="$REPO_ROOT/.codex_tmp/emmc_deploy_20261112"
WRAPPER_LOCAL="$SCRIPT_DIR/g5-install-wrapper.sh"
EXPECTED_WRAPPER_SHA=1bef8ba4e410d7b54c6c88548de6d6273ad56eff2d0268fec2cbe82d9d34257d
EXPECTED_BOOTLOADER_SHA=f61b153c1ec98ce54ee770be43198af2d2ac60642cc6004500cfbd3b87490262

MODE=${1:-install}
case "$MODE" in
    install|--preflight-only) ;;
    *) printf 'usage: %s [--preflight-only]\n' "$0" >&2; exit 2 ;;
esac

command -v ssh >/dev/null 2>&1 || { echo 'missing ssh' >&2; exit 2; }
command -v scp >/dev/null 2>&1 || { echo 'missing scp' >&2; exit 2; }
command -v script >/dev/null 2>&1 || { echo 'missing script' >&2; exit 2; }
command -v sha256sum >/dev/null 2>&1 || { echo 'missing sha256sum' >&2; exit 2; }
command -v awk >/dev/null 2>&1 || { echo 'missing awk' >&2; exit 2; }
command -v stat >/dev/null 2>&1 || { echo 'missing stat' >&2; exit 2; }
[[ -f "$WRAPPER_LOCAL" ]] || { echo "missing local wrapper: $WRAPPER_LOCAL" >&2; exit 2; }

local_sha=$(sha256sum "$WRAPPER_LOCAL" | awk '{print $1}')
[[ "$local_sha" == "$EXPECTED_WRAPPER_SHA" ]] || {
    printf 'local wrapper hash mismatch: actual=%s expected=%s\n' "$local_sha" "$EXPECTED_WRAPPER_SHA" >&2
    exit 2
}

RUN_ID=$(date +%Y%m%d_%H%M%S)
LOCAL_DIR="$LOCAL_ROOT/g5_pc_$RUN_ID"
mkdir -p "$LOCAL_DIR"
FINALIZED=0

restart_kiosk_on_exit() {
    local rc=$?
    set +e
    if (( rc != 0 && ! FINALIZED )) && [[ "$MODE" == install ]]; then
        printf 'G5 did not finalize; attempting to restart vt13-kiosk on the SG USB system...\n'
        script -q -e -c "ssh -tt -o BatchMode=yes '$CM311' 'sudo systemctl start vt13-kiosk.service'" \
            "$LOCAL_DIR/restart-kiosk-session.log" || true
    fi
    exit "$rc"
}
trap restart_kiosk_on_exit EXIT

ssh -o BatchMode=yes -o ConnectTimeout=8 "$CM311" "mkdir -p '$REMOTE_STAGE'"
scp -q "$WRAPPER_LOCAL" "$CM311:$REMOTE_STAGE/g5-install-wrapper.sh"
remote_sha=$(ssh -o BatchMode=yes "$CM311" "sha256sum '$REMOTE_STAGE/g5-install-wrapper.sh'" | awk '{print $1}')
[[ "$remote_sha" == "$EXPECTED_WRAPPER_SHA" ]] || {
    printf 'remote wrapper hash mismatch: actual=%s expected=%s\n' "$remote_sha" "$EXPECTED_WRAPPER_SHA" >&2
    exit 2
}

printf 'G5 wrapper staged: %s SHA256=%s\n' "$REMOTE_STAGE/g5-install-wrapper.sh" "$remote_sha"
printf 'G5 local evidence directory: %s\n' "$LOCAL_DIR"

if [[ "$MODE" == --preflight-only ]]; then
    script -q -e -c "ssh -tt -o BatchMode=yes '$CM311' 'sudo $REMOTE_STAGE/g5-install-wrapper.sh --preflight-only'" \
        "$LOCAL_DIR/preflight-session.log"
    scp -q "$CM311:$REMOTE_STAGE/g5-latest/preflight.txt" "$LOCAL_DIR/preflight.txt"
    scp -q "$CM311:$REMOTE_STAGE/g5-latest/g5-result.env" "$LOCAL_DIR/g5-result.env"
    (cd "$LOCAL_DIR" && sha256sum preflight-session.log preflight.txt g5-result.env > SHA256SUMS)
    (cd "$LOCAL_DIR" && sha256sum -c SHA256SUMS)
    printf 'G5_PREFLIGHT_SAVED=%s\n' "$LOCAL_DIR"
    exit 0
fi

script -q -e -c "ssh -tt -o BatchMode=yes '$CM311' 'sudo $REMOTE_STAGE/g5-install-wrapper.sh'" \
    "$LOCAL_DIR/install-session.log"

scp -q "$CM311:$REMOTE_STAGE/g5-latest/g5-result.env" "$LOCAL_DIR/g5-result.env"

STATUS=
LOG_PATH=
LOG_SHA256=
EVIDENCE_PATH=
EVIDENCE_SHA256=
BOOTLOADER_BACKUP_PATH=
BOOTLOADER_BACKUP_SHA256=
MBR_BACKUP_PATH=
MBR_BACKUP_SHA256=
BACKUP_SHA256=
source "$LOCAL_DIR/g5-result.env"

[[ "$STATUS" == VALIDATED ]] || {
    printf 'remote G5 status is %s, expected VALIDATED\n' "$STATUS" >&2
    exit 1
}
[[ -n "$LOG_PATH" && -n "$LOG_SHA256" && -n "$EVIDENCE_PATH" && -n "$EVIDENCE_SHA256" && \
   -n "$BOOTLOADER_BACKUP_PATH" && -n "$BOOTLOADER_BACKUP_SHA256" && \
   -n "$MBR_BACKUP_PATH" && -n "$MBR_BACKUP_SHA256" && -n "$BACKUP_SHA256" ]] || {
    echo 'remote G5 result is missing log/evidence/backup fields' >&2
    exit 1
}
[[ "$BACKUP_SHA256" == "$EXPECTED_BOOTLOADER_SHA" ]] || {
    printf 'remote bootloader backup hash is %s, expected %s\n' "$BACKUP_SHA256" "$EXPECTED_BOOTLOADER_SHA" >&2
    exit 1
}
[[ "$BOOTLOADER_BACKUP_SHA256" == "$EXPECTED_BOOTLOADER_SHA" ]] || {
    printf 'remote bootloader export hash is %s, expected %s\n' "$BOOTLOADER_BACKUP_SHA256" "$EXPECTED_BOOTLOADER_SHA" >&2
    exit 1
}

scp -q "$CM311:$LOG_PATH" "$LOCAL_DIR/armbian-install.log"
scp -q "$CM311:$EVIDENCE_PATH" "$LOCAL_DIR/postinstall-evidence.txt"
scp -q "$CM311:$BOOTLOADER_BACKUP_PATH" "$LOCAL_DIR/mybox-bootloader.img"
scp -q "$CM311:$MBR_BACKUP_PATH" "$LOCAL_DIR/mbr-first512.bin"

actual_log_sha=$(sha256sum "$LOCAL_DIR/armbian-install.log" | awk '{print $1}')
actual_evidence_sha=$(sha256sum "$LOCAL_DIR/postinstall-evidence.txt" | awk '{print $1}')
[[ "$actual_log_sha" == "$LOG_SHA256" ]] || {
    printf 'install log hash mismatch: actual=%s expected=%s\n' "$actual_log_sha" "$LOG_SHA256" >&2
    exit 1
}
[[ "$actual_evidence_sha" == "$EVIDENCE_SHA256" ]] || {
    printf 'evidence hash mismatch: actual=%s expected=%s\n' "$actual_evidence_sha" "$EVIDENCE_SHA256" >&2
    exit 1
}
[[ "$(stat -c %s "$LOCAL_DIR/mybox-bootloader.img")" == 4194304 ]] || {
    echo 'local bootloader export size mismatch' >&2
    exit 1
}
[[ "$(stat -c %s "$LOCAL_DIR/mbr-first512.bin")" == 512 ]] || {
    echo 'local MBR export size mismatch' >&2
    exit 1
}
actual_bootloader_sha=$(sha256sum "$LOCAL_DIR/mybox-bootloader.img" | awk '{print $1}')
actual_mbr_sha=$(sha256sum "$LOCAL_DIR/mbr-first512.bin" | awk '{print $1}')
[[ "$actual_bootloader_sha" == "$BOOTLOADER_BACKUP_SHA256" ]] || {
    printf 'bootloader export hash mismatch: actual=%s expected=%s\n' "$actual_bootloader_sha" "$BOOTLOADER_BACKUP_SHA256" >&2
    exit 1
}
[[ "$actual_mbr_sha" == "$MBR_BACKUP_SHA256" ]] || {
    printf 'MBR export hash mismatch: actual=%s expected=%s\n' "$actual_mbr_sha" "$MBR_BACKUP_SHA256" >&2
    exit 1
}

(
    cd "$LOCAL_DIR"
    sha256sum g5-result.env armbian-install.log postinstall-evidence.txt install-session.log \
        mybox-bootloader.img mbr-first512.bin > SHA256SUMS
    sha256sum -c SHA256SUMS
)

printf 'G5_LOG_SAVED_AND_VERIFIED\n'
printf 'G5_LOCAL_LOG=%s\n' "$LOCAL_DIR/armbian-install.log"
printf 'G5_LOCAL_EVIDENCE=%s\n' "$LOCAL_DIR/postinstall-evidence.txt"
printf 'G5_LOCAL_BOOTLOADER_BACKUP=%s\n' "$LOCAL_DIR/mybox-bootloader.img"
printf 'G5_LOCAL_MBR=%s\n' "$LOCAL_DIR/mbr-first512.bin"

printf 'G5_POWEROFF_BEGIN\n'
set +e
script -q -e -c "ssh -tt -o BatchMode=yes '$CM311' 'if sudo -n true 2>/dev/null; then sudo -n sync; sudo -n poweroff; else sudo sync; sudo poweroff; fi'" \
    "$LOCAL_DIR/finalize-session.log"
finalize_rc=$?
set -e

case "$finalize_rc" in
    0|255) ;;
    *)
        printf 'finalization failed rc=%s; system may still be running\n' "$finalize_rc" >&2
        exit "$finalize_rc"
        ;;
esac

FINALIZED=1
printf 'G5_POWEROFF_ISSUED rc=%s\n' "$finalize_rc"
printf 'G5_DONE local=%s\n' "$LOCAL_DIR"
