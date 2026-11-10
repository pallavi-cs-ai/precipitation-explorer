# Session development log

All commands, edits, verification and commits below were performed in the same Codex session.

## Milestone 1 — project initialization

- Created `precipitation-explorer/` as an isolated Git repository on branch `main`.
- Confirmed synced `sources/` were not modified.
- Verified `git check-ignore` excludes `.env`, `.venv/`, and downloaded GRIB files.
- Commit: `7db2c06` — chore: initialize isolated IFS exploration project.

## Milestone 2 — real IFS data exploration

- Installed and pinned Python dependencies in the project environment (Python 3.12.15).
- Added retrieval, metadata validation, unit normalization, interval derivation and plotting.
- Retrieved four actual global `tp` fields from the 2026-11-10 06 UTC run.
- Recorded metadata and a SHA-256 digest in `reports/sample.json`; raw data remains ignored.
- Verified unit conversion, unsupported-unit rejection, differencing, packing tolerance and reset rejection: `python -m pytest -q` — 2 tests passed.
- Real-data assertions verified steps, run consistency, accumulation origin, absence of missing values and finite values.
- Visually inspected the generated exploration plot.
- AWS discovery returned 503; primary ECMWF retrieval succeeded. No synthetic data substituted.
- Findings and limitations: `reports/FINDINGS.md`.
- Commit identity for this milestone is available in `git log`; this log is committed with the milestone.

No public GitHub repository or deployment has been created at this exploration stage.
