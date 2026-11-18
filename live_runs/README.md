# Live-run evidence index

This directory contains compact, tracked text evidence from live VT13 validation.
It is not required to build or run the receiver.

## Contents

- `live_run01.*` through `live_run11.*` — chronological live-session timing and
  event sidecars.
- `relink01.*` — relink/recovery evidence.
- `vt13_params.h265` — known-good parameter sets used for priming and replay.

Each run has a `.times.tsv` sidecar (`elapsed_s`, `chunk_length`,
`wall_time_utc`) and an `.events.tsv` sidecar (`elapsed_s`, `event`, `detail`,
`wall_time_utc`). Raw `.bin` recordings are intentionally Git-ignored; the TSV
sidecars preserve timing and failure evidence without repository bloat.

## Use

Keep these files for regression comparisons, deployment validation, and
evidence of the receiver's live behavior. Do not add generated previews,
`__pycache__`, or raw `.bin` files here. For the narrative behind a run, use Git
history and the archived development documents.
