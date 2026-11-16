# P128 production build provenance

Recorded: 2026-11-16 19:46 HKT
Status: exact source is canonical; instrumented source is diagnostic only.

## Production artifact

- Source: `tools/d3_probe.c`
- Source SHA256: `230a26046daaed5ce04a780f2aac4773473b864c5553c6a19061cbfe8a8bc779`
- Build host: CM311 `billieguo@10.42.0.253` (armbian, aarch64)
- Compiler: `gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`
- Command: `gcc -O2 -Wall -Wextra -o build/d3/d3_probe_p128_exact tools/d3_probe.c`
- Binary: `build/d3/d3_probe_p128_exact` SHA256
  `663f75e09e021b3877ee9da70c543b00fa82742c5f108af4ad6a1e69466285dc`
- Wrapper: `build/d3/d3_probe_p128` SHA256
  `92d9c17c38de3263e4e2ef778be0df1bc51dac73d0c219dcb61d5158336b7685`
- Production config: `config/vt13_video.kiosk.yaml` SHA256
  `919a30323370a2077201feda0991d40c99f931330df787f59441074aa1b5d7ec`

## Diagnostic artifact

- Source: `tools/d3_probe_instrumented.c`
- Source SHA256: `3a742e533fbcf557e5840feb4395c547e0b45bba6e93b9fb1a35dc72bef7d826`
- Build: `make instrumented`
- Expected binary: `build/d3/d3_probe_p128_instrumented` SHA256
  `6cdb04a327df526c84912c0ee300ae9a1e2a32bea0ed14183cec19c4b17c0217`
  when built on CM311 with GCC 13.3 and a source basename of `d3_probe.c`.
- This binary is for diagnostics; it is not the production default.

## Reproducibility note

The deployed exact binary is unstripped. GCC records the source basename in
`STT_FILE`, so compiling the same content from `d3_exact.c` produces a different
SHA256 (`1a091b6a0a4aea9d14a7d4ca50fd4114f75b5ea543afc961b3b7113d77f6a53a`).
Build from a source file named `d3_probe.c`; `make exact` does this. Rebuild
verified on CM311: `230a2604...` source produced `663f75e0...` binary.

## Remote source tree

- Updated `billieguo@10.42.0.253:~/mobile_vt/tools/d3_probe.c` from old
  `fa9e5d07d4c7b81d36df2ed81f5275d2631206c084f4e59b24f18789621263a2` to exact
  `230a26046daaed5ce04a780f2aac4773473b864c5553c6a19061cbfe8a8bc779`.
- Backup: `~/mobile_vt/.codex_tmp/backup_d3_source_20261116_20261116_194545/d3_probe.c`
  SHA256 `fa9e5d07d4c7b81d36df2ed81f5275d2631206c084f4e59b24f18789621263a2`.
- Remote rebuild from the updated source produced
  `663f75e09e021b3877ee9da70c543b00fa82742c5f108af4ad6a1e69466285dc`.
- The running service and binary were not restarted or replaced.

## Worker client

- Production canonical: `vt13_video/worker_client.py` SHA256
  `518628638a5fa0da0914a5ac38e0c7255e7b801817eb7314a915f149da887279`,
  matching commit `fdd74b3`.
- Diagnostic variant: `vt13_video/worker_client_instrumented.py` SHA256
  `cad4fe2ae0d476b37f36fb45e7e5e9aed7b77001681a854acbee7f19addcd2d2`.
  It adds 9-column latency CSV fields and worker environment plumbing; it is
  not imported by the production pipeline by default.
- Both files were synced to CM311 and passed `py_compile`; the running service
  was not restarted. `tests/test_latency.py` covers the production 6-column and
  diagnostic 9-column schemas.
