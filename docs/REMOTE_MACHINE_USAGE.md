# Remote Machine Usage Reference

**Scope:** CM311-specific deployment and diagnostics reference. It is useful for
another CM311-like deployment, but it is not required for local-only use.

## 1. Access

### Direct access

CM311 can be used directly with a keyboard and HDMI display. This is the safest
way to recover the kiosk, inspect HDMI output, or work when SSH is unavailable.
Physical power cycling is the final recovery step.

### From the Ubuntu PC

The current DHCP lease is `10.42.0.253`; the historical `10.42.0.11` lease is no
longer current. Confirm the address before assuming it is stable.

```bash
ssh billieguo@10.42.0.253
```

The documented account password is `020816`; sudo uses the same password. Prefer
SSH key authentication when publishing the repository, because the plaintext
password is currently tracked in this file.

For a PTY or interactive sudo:

```bash
ssh -tt billieguo@10.42.0.253
sudo -v
```

For non-interactive commands, use a key, `ssh -tt`, or an askpass helper. Do not
put the password on the command line if it will be echoed into logs.

## 2. Machine profile

- Identity: `armbian`, `aarch64`, kernel `6.18.59-ophub`, Armbian OS 26.11.0
  noble, four cores, about 1.7 GiB RAM.
- Root storage: eMMC (`/dev/mmcblk2p2`); boot partition `/dev/mmcblk2p1`.
- Receiver: DJI VT13 `2ca3:1020`, video endpoint on `/dev/video0`.
- Display: HDMI-A-1, DRM/KMS `/dev/dri/card0`; the kiosk worker takes DRM master
  itself.
- Decoder: custom `meson-vdec.ko` (ca46) plus `gxl_hevc.bin`; the stock module
  does not provide the verified HEVC path.
- Runtime: `vt13-kiosk.service`, native P128 worker, production client, and
  config under `~/mobile_vt`.
- Remote tree is a deployment copy, not a Git repository. Use SHA256 manifests
  for parity checks.

## 3. Important paths

```text
~/mobile_vt/                         project and runtime tree
~/mobile_vt/config/                  kiosk, P128, and fallback configs
~/mobile_vt/build/d3/                deployed native workers
~/mobile_vt/tools/d3_probe.c         canonical production worker source
~/mobile_vt/tools/d3_probe_instrumented.c  diagnostic source
~/mobile_vt/vt13_video/worker_client.py    production client
~/mobile_vt/vt13_video/worker_client_instrumented.py  diagnostic client
~/mobile_vt/.codex_tmp/d3_worker.sock       live worker socket
~/mobile_vt/.codex_tmp/backup_d3_source_... provenance backup
~/mobile_vt/captures/                runtime/test evidence
~/mobile_vt/live_runs/               compact validation evidence
```

## 4. Safe status checks

```bash
hostname; uname -m; uname -r; cat /etc/os-release | head -5
systemctl status vt13-kiosk.service --no-pager
journalctl -u vt13-kiosk.service -n 100 --no-pager
journalctl -k -n 100 --no-pager
lsusb -d 2ca3:1020
ls -l /dev/video0 /dev/dri/card0
fuser /dev/video0 /dev/dri/card0
sha256sum ~/mobile_vt/build/d3/d3_probe ~/mobile_vt/build/d3/d3_probe_p128 \
  ~/mobile_vt/build/d3/d3_probe_p128_exact
```

Do not run a second pipeline while `vt13-kiosk.service` owns the USB/V4L2/DRM
devices.

## 5. Build and deploy

The local repository is sufficient to rebuild the worker on CM311:

```bash
cd ~/mobile_vt
make exact
make instrumented
sha256sum build/d3/d3_probe_p128_exact build/d3/d3_probe_p128_instrumented
```

Verified production hash:

```text
663f75e09e021b3877ee9da70c543b00fa82742c5f108af4ad6a1e69466285dc
```

Diagnostic hash:

```text
6cdb04a327df526c84912c0ee300ae9a1e2a32bea0ed14183cec19c4b17c0217
```

The exact worker must be built from a source named `d3_probe.c`; the unstripped
binary records that basename. Keep the exact and instrumented variants separate.

Deployment rules:

- Copy source, binary, or config only after recording the current hashes.
- Verify the replacement hash before changing the service.
- Do not replace a running production binary or restart the service without
  explicit approval.
- Preserve `config/vt13_video.kiosk.a.yaml` as the tested fallback.
- After an approved restart, verify service state, worker PID, socket, device
  ownership, and journal output.

## 6. Common diagnostics

```bash
# USB and service state
systemctl status vt13-kiosk.service --no-pager
journalctl -u vt13-kiosk.service -f

# Kernel decoder messages
sudo dmesg -T | tail -100

# Device ownership
fuser -v /dev/video0 /dev/dri/card0

# Worker socket
ls -l ~/mobile_vt/.codex_tmp/d3_worker.sock

# Hash comparison with a local copy
sha256sum ~/mobile_vt/tools/d3_probe.c
```

For a live USB/HDMI test, ensure the service is stopped or otherwise not owning
the devices; otherwise the manual pipeline and kiosk will compete for
`/dev/video0` and `/dev/dri/card0`.

## 7. Troubleshooting

- `Permission denied (publickey,password)` — confirm user/address and use key
  auth or the documented password; `ssh-copy-id` is the durable fix.
- `sudo: a terminal is required` — use `ssh -tt` or `sudo -S` with a password
  source that does not echo into logs.
- No video device — check `lsusb -d 2ca3:1020`, USB permissions, and whether the
  kiosk already owns the device.
- Service active but no picture — inspect HDMI-A-1 state, DRM master ownership,
  worker journal lines, and whether the transmitter is enabled after READY.
- Decoder errors — distinguish USB/transport failures from kernel `0xf` aborts;
  preserve the journal and relevant capture before restarting.
- SSH unreachable after a reboot — use direct HDMI/keyboard access or the
  documented physical recovery path; DHCP leases can change.

## 8. Current state (2026-11-18)

- `vt13-kiosk.service` is active, `MainPID=1334328`, `NRestarts=0`; worker
  socket is live.
- Production binaries/configs were not replaced during cleanup.
- The running process still uses modules loaded before cleanup; cleaned sources
  take effect on the next service start.
- No live USB/V4L2/HDMI acceptance run or service restart was performed after
  cleanup.

## 9. Related references

- `deploy/P128_BUILD_PROVENANCE.md` — CM311-specific exact/instrumented build
  provenance.
- `deploy/PAYLOAD_MANIFEST.md` — CM311 eMMC payload reference.
- `archive/plans/CM311_eMMC_Deployment_Runbook.md` — historical deployment
  runbook.
- `docs/INTERSESSION_TRANSFER.md` — concise development handoff.
