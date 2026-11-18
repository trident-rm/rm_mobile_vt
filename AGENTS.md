# AGENTS.md — Implementation Protocol

This file is the operating contract for coding agents working on `mobile_vt`.
It describes how to inspect, change, verify, deploy, and report. It is not a
changelog: historical detail belongs in Git and `archive/`.

## 1. Mission

Maintain the VT13 USB HEVC receiver, its native CM311 worker, and the CM311
kiosk deployment without regressing the verified production path. Optimize for
correctness, recoverability, and traceable evidence before latency or
convenience.

## 2. Authority and source of truth

1. The user's current instruction overrides this document.
2. The local Git repository is the authoritative source for code, build rules,
   configs, tests, and documentation.
3. CM311 `~/mobile_vt` is a deployment copy, not the development source of
   truth. It is not a Git repository; verify parity with SHA256 manifests.
4. Production runtime state on CM311 is authoritative for what is currently
   deployed. Do not infer it from the local tree.
5. If local and remote differ, report the difference and resolve it explicitly.
   Never overwrite either side wholesale.

## 3. Safety and approvals

Use these risk levels:

- **R0** — read-only inspection. No approval needed.
- **R1** — local edits, tests, builds, and temporary files. No approval needed
  unless the user requested otherwise.
- **R2** — reversible remote test process, source copy, or isolated output
  directory. Confirm the device is idle first.
- **R3** — service restart, binary/config replacement, reboot, kernel-module
  reload, eMMC write, or any action that can interrupt USB/V4L2/HDMI or SSH.
  Requires explicit approval for the exact command and window.

Rules:

- Never restart `vt13-kiosk.service`, replace a production binary/config, reboot
  CM311, or run a live USB/HDMI test unless the user approved it.
- Approval is scoped to the named command, host, and time window. Re-ask when
  the command, scope, or risk changes.
- Preserve the deployed binaries, configs, live socket, and logs until the
  replacement has been verified.
- Use bounded commands and `timeout` for remote diagnostics.
- Do not store secrets in logs or new tracked files. Prefer SSH key auth.

## 4. Required context

Before changing code or deploying, read:

- `README.md`
- `AGENTS.md` (this file)
- `docs/REMOTE_MACHINE_USAGE.md`
- `docs/INTERSESSION_TRANSFER.md`
- relevant archived plans under `archive/plans/` when the task touches their
  subject

Confirm the actual environment instead of trusting old snapshots: host identity,
architecture, kernel, project paths, service state, device ownership, and source
hashes.

## 5. Implementation workflow

1. **Inspect** — read the relevant code and tests; check `git status`, local
   HEAD, and remote service/device state.
2. **Plan** — state the goal, files, hosts, risks, rollback, and verification
   criteria. Keep the change minimal and reversible.
3. **Change** — edit the smallest necessary surface. Do not refactor unrelated
   code or reformat whole files.
4. **Verify locally** — compile, run targeted tests, then the broader suite when
   practical; check formatting and `git diff --check`.
5. **Verify remotely** — compare hashes, compile/import on CM311, and run only
   the approved checks. Do not assume a successful copy proves correctness.
6. **Document** — update the affected docs and `README.md` links. Record exact
   commands, hashes, evidence paths, unverified items, and next action.
7. **Report** — give the user a concise result, evidence, risk, and rollback.

## 6. Build and deployment rules

- Build the native worker on CM311 with `make exact` and `make instrumented`.
- Production source is `tools/d3_probe.c`; the diagnostic variant is
  `tools/d3_probe_instrumented.c`. Keep both.
- Production client is `vt13_video/worker_client.py`; the diagnostic variant is
  `vt13_video/worker_client_instrumented.py`. Keep both.
- The exact worker is unstripped and records the source basename. Build it from
  a source named `d3_probe.c`; `make exact` handles this.
- Verified exact worker hash is
  `663f75e09e021b3877ee9da70c543b00fa82742c5f108af4ad6a1e69466285dc`.
- The local repository plus its `Makefile` and C sources are sufficient to
  rebuild the ARM worker; a local ARM binary cache is not required.
- Do not mix the exact and instrumented artifacts. The instrumented worker is
  for diagnostics, not the production default.
- Before deploying, verify source and binary hashes. After deployment, verify
  the service, worker, socket, device ownership, and logs.

## 7. Verification standards

Local baseline:

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m compileall -q vt13_video tests tools examples
PYTHONPATH= python3 -m pytest -q -p no:cacheprovider
ruff check --select F401,F841
git diff --check
```

Record pass/fail counts and RC values. For live work, distinguish:

- build success from runtime success;
- USB byte flow from decodable video;
- decoder RC=0 from correct picture content;
- service `active` from actual HDMI output;
- a hash match from a live acceptance test.

Do not claim a live test passed if USB/V4L2/HDMI was not exercised.

## 8. Data and documentation rules

- Track `live_runs/*.tsv`, `live_runs/vt13_params.h265`, and the cold-start
  golden capture as compact validation evidence.
- Ignore raw `live_runs/*.bin`, generated frames, build outputs, caches, and
  `__pycache__`.
- Keep `.codex_tmp/` as local evidence, not tracked repository content.
- Keep documentation concise. Put long historical narratives in `archive/` or
  rely on Git history; keep current operational instructions in the three
  maintenance documents.
- Do not add machine-specific snapshots to general instructions without
  labelling their scope.

## 9. Remote operation rules

- CM311 is reachable at the current DHCP address `10.42.0.253` as
  `billieguo`; the old `10.42.0.11` lease is historical.
- Check that CM311 is idle before a live test: no competing `vt13_video` or
  `ffmpeg` process and no unexpected opener on `/dev/video0`.
- `vt13-kiosk.service` owns USB, V4L2, and DRM while active. Do not run a second
  pipeline against the same devices.
- Prefer read-only status checks and journal inspection. Use the documented
  service commands only when approved.
- Preserve the live socket, production binaries, configs, and provenance
  backup during cleanup.

## 10. Live USB/HDMI handoff

The human controls the wireless transmitter; the agent cannot assume control.
The required order is:

1. Start the receiver and confirm it is waiting for data.
2. Give the human the exact CM311 command and expected READY evidence.
3. The human enables the wireless link and reports the time/result.
4. Collect and analyze logs, counters, and device state.

Do not report `0 packets` before the transmitter is enabled as a receiver
failure. Provide copy-pasteable commands with host, preconditions, expected
output, stop method, and log path.

## 11. Reporting format

For substantial work, report:

```text
Goal:
Changed:
Verified:
Evidence:
Unverified / limits:
Rollback:
Next action:
```

Be explicit about what was not tested. Do not use “should work” as evidence.

## 12. Current baseline (2026-11-18)

- Local cleanup commit: `45beef5` (`Clean up dead code, legacy files, and test
  data`); no Git remote is configured, so no push has occurred.
- CM311 service is active with `MainPID=1334328`, `NRestarts=0`; the worker
  socket is live and production binaries/configs are unchanged.
- The exact worker was rebuilt from local sources and matched
  `663f75e0…`; the instrumented variant matched `6cdb04a3…`.
- Cleaned remote sources take effect on the next service start. No live
  USB/V4L2/HDMI acceptance run or service restart has been performed after the
  cleanup.
