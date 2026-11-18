# Intersession Transfer: VT13 / CM311

This is a concise handoff, not a full development log. Detailed history remains
in Git and `archive/`.

## Current baseline (2026-11-18)

- Local cleanup commit: `45beef5` (`Clean up dead code, legacy files, and test
  data`).
- The local repository rebuilds the deployed exact worker on CM311:
  `663f75e09e021b3877ee9da70c543b00fa82742c5f108af4ad6a1e69466285dc`.
- The diagnostic build matches
  `6cdb04a327df526c84912c0ee300ae9a1e2a32bea0ed14183cec19c4b17c0217`.
- CM311 `vt13-kiosk.service` remains active, `MainPID=1334328`,
  `NRestarts=0`; the worker socket is live and production binaries/configs are
  unchanged.
- No Git remote is configured, so no push occurred.
- No live USB/V4L2/HDMI run or service restart has been performed after cleanup.
  The running process uses the modules loaded before cleanup; cleaned remote
  sources take effect on the next service start.

## Development summary

- Built a read-only VT13 USB capture and HEVC pipeline with Annex-B parsing,
  access-unit assembly, parameter-set bootstrap, recovery, and recording.
- Added DUML control and recovery diagnostics, then validated offline replay and
  live capture behavior.
- Moved the production display path to the native P128 parallel tiled worker
  with atomic KMS presentation and software 180° rotation.
- Deployed the eMMC-based CM311 appliance, verified cold boot and service
  startup, and preserved the original A worker/config as a fallback.
- Canonicalized the production worker client, kept the instrumented client and
  C worker as separate diagnostic variants, and verified exact rebuild
  provenance.
- Removed dead code, legacy scripts/docs, caches, and test-time data from both
  local and remote trees while preserving runtime state.

## Essential next-session procedure

1. Read `AGENTS.md`, `docs/REMOTE_MACHINE_USAGE.md`, and `README.md`.
2. Check local `git status`, HEAD, and the current task state.
3. Verify CM311 is reachable and idle; record service/device state before
   touching it.
4. Compare local and remote source/binary hashes where the task requires parity.
5. Run local compile, tests, lint, and `git diff --check` for code changes.
6. Build on CM311 with `make exact` or `make instrumented` as appropriate.
7. Deploy only after hash verification; restart the service only with explicit
   approval.
8. Run the approved live validation and preserve evidence.
9. Update `docs/INTERSESSION_TRANSFER.md` with the result, unverified items, and
   next action.
10. Commit only when requested; do not push unless a remote is configured.

## Open validation

- Live USB/V4L2/HDMI acceptance after the cleanup; the cleaned remote sources
  have not yet been exercised by a service restart.
- Formal G8 still requires three independent cold boots plus one supervised
  soft reboot.
- Visual confirmation of the 180° rotation and HDMI picture quality remains
  pending.
- Content-dependent kernel `0xf` aborts, startup bursts, recovery freezes, and
  glass-to-glass latency remain open.

## Key artifacts

- `deploy/P128_BUILD_PROVENANCE.md` — exact/instrumented build recipe and hashes.
- `deploy/PAYLOAD_MANIFEST.md` — CM311 eMMC payload reference.
- `archive/DEVELOPMENT_FLOW_AND_LATENCY.md` — historical development and latency
  analysis.
- `archive/plans/` — archived execution and optimization plans.
- `live_runs/README.md` — tracked validation-evidence index.
- `.codex_tmp/` — local-only evidence and historical mirrors; not tracked.

## Historical detail

Use `git log` for commit history and `archive/` for plans, the development-flow
narrative, and older deployment references. Do not append every command to this
file; keep only decisions, verified results, open risks, and the next handoff.
