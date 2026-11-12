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

## Milestone 3 — publish exploration repository

- On user request, created public repository https://github.com/pallavi-cs-ai/precipitation-explorer using GitHub CLI in this same session.
- Pushed initialization commit `7db2c06` and exploration commit `dc78685` to `main`.
- Reviewed tracked files before publication; credentials, environments, raw forecasts and temporary logs remain excluded.
- Application deployment has not yet been created.

## Architecture checkpoint

- User locked the precipitation explorer product and map/timeline/chart interactions.
- Recorded chart behavior, API contracts, three cache layers, data correctness requirements and delivery standards in `docs/ARCHITECTURE.md`.
- Documentation validation: `git diff --check`. No runtime code changed at this checkpoint.

## Milestone 4 — complete ingestion and read-only API

- Downloaded and validated 24 real IFS precipitation fields covering 72 forecast hours; generated India-region numeric arrays and Web Mercator image overlays.
- Added bounded upstream timeouts/retries, source fallback, single-writer locking, atomic run publication, previous-run preservation and run retention.
- Added typed FastAPI endpoints for metadata, point series, frames, accumulated images, readiness and health; consistent uncached error responses include request IDs.
- Verification: 9 Python tests passed, including upstream failure preservation, missing/corrupt data, invalid coordinates, image orientation and accumulation consistency. Ruff lint/format passed.
- Real-data integration verified all 24 PNG frames, one point series, accumulation and successful frontend HTTP serving; evidence in `reports/application-checks.json`.

## Milestone 5 — interactive explorer

- Built React/TypeScript UI with MapLibre, ECharts, TanStack Query, Tailwind and shadcn-style button primitives.
- Added synchronized map clicks, city selection, chart selection, timeline playback, accumulated-period brush and selectors, CSV export and values table.
- Added request cancellation, bounded retries, loading/error states, stale-run labels and a rendering error boundary.
- Browser verification exercised real IFS data, including bar-to-map synchronization, map clicks, playback and range brushing. Corrected timeline range labels and registered ECharts toolbox dependency found during browser QA.
- At 390px, document scroll width equals viewport width; desktop screenshot saved in reports/explorer-preview.jpg.
- Verification: 9 backend tests, 3 frontend tests, Ruff, ESLint and TypeScript/Vite production build passed.

## Deployment preparation

- Added Docker build, Render blueprint, CI and local/deployment instructions.
- Paid Render service creation remains pending cost approval. Local Docker executable is unavailable; container build and public deployment are not yet verified.

## Free-hosting decision

- User explicitly selected free hosting. Changed Render blueprint to Free, removed disk, and set temporary forecast storage.
- Documented idle spin-down, cache loss, re-ingestion and awake-only polling. No paid resource authorized.
- GitHub Actions for ac1ada5 passed both frontend and backend jobs on Linux.
- Configuration validation: reviewed blueprint for no disk and Free plan; git diff --check. Public deployment remains pending account access.

## Milestone 6 — public Render deployment

- Used the existing precipitation_forecast / Production environment after user sign-in. Created pluvia-precipitation from the public repository, main branch, Dockerfile at repo root.
- Matched committed configuration: Free, Frankfurt, no disk, temporary forecast directory, /healthz, auto-deploy off. No additional GitHub access or credentials required.
- Deployed d96df11583008995b8b405683193968a401aa128 after GitHub CI passed. Docker build succeeded on Render.
- Public URL: https://pluvia-precipitation.onrender.com. Same-origin relative API paths require no host rewrite or CORS change.
- Verified HTTPS frontend, health and readiness, real run ifs-20261111T06Z, point series, PNG frame, accumulation image and structured invalid-coordinate response.
- Browser verified map/chart rendering, next-interval synchronization, full-period selection and no console errors. Evidence: reports/deployment-checks.json and reports/deployed-preview.jpg.
- Idle wake-up/re-ingestion timing remains unmeasured. Documentation-only follow-up commit does not require redeploying the verified application.

## Milestone 7 — benchmark and configurable global overview

- User authorized benchmarking and conditional global implementation while keeping the deployed India service stable.
- Benchmarked the original India pipeline and 1° global sampling using the same real 24-field IFS run. Input download is unchanged; global processed grid plus frames is 1.26 MiB.
- Added explicit india/global1 coverage profiles, bounds-driven PNG rendering, profile-separated immutable run IDs, circular longitude sampling and a bounded accumulation renderer.
- Global ingestion peak RSS 167.61 MiB; API stress peak 77.98 MiB after serialization of image renders. Combined approximate 300 MiB budget includes runtime headroom; Render timing/peak remains unmeasured. Details and caveats: docs/GLOBAL_BENCHMARK.md.
- Updated shared UI for manifest coverage/resolution, global presets and correct hemisphere labels. Retained IST labels and existing API fields/interactions. Fixed false basemap timeout observed in browser verification.
- Verification: 11 backend tests and 4 frontend tests passed; Ruff, ESLint, TypeScript/Vite build passed. Local real-data global ingestion and browser interval/range/city checks passed; no console errors.
- Preview: http://127.0.0.1:8001. Evidence: reports/global-preview.jpg and benchmark JSON files.
- Production is still d96df11 / India. No Render environment changes, new paid resources or extra free service were created.

## Milestone 8 — correctness and interaction audit

- Converted every UI time/date formatter, chart tooltip, timeline and range label to UTC; explicit next-day labels handle midnight boundaries. Reused Intl formatters to avoid repeated construction.
- Fixed accent/whitespace matching, keyboard Enter selection and empty filtered search results. Search remains explicitly limited to city presets; any displayed map location can still be selected. Off-screen selected locations pan into view.
- Added a background-refresh error/retry notice and a minute clock so freshness/expiry labels update even without user interaction. Active runs remain pinned until the user selects an available newer run.
- Bounded reversed/out-of-range chart brush selections; removed hardcoded interval count in mode selection. Added an accessible label to the mobile About button.
- API refuses negative/infinite precipitation and invalid coordinate axes in stored grids. Added a latest-pointer refresh test preserving access to previous run URLs.
- Independently compared all 24 decoded source GRIB intervals at four global locations (both hemispheres and both sides of the date line). Every interval and the source 72-hour totals matched; reports/correctness-audit.json.
- Verification: 13 backend tests, 7 frontend tests, Ruff, ESLint and production build passed. Browser verified UTC midnight crossover, normalized search/Enter, global accumulation, 390px no horizontal overflow and 1280px layout; no console errors observed.
- Evidence screenshot: reports/utc-audit-preview.jpg. Production India deployment remains unchanged per user instruction; audited global build is available locally at port 8001.

## Heading clarification

- User requested map heading: 3-HOUR PRECIPITATION for interval mode, TOTAL PRECIPITATION for selected-period accumulation.
- Updated the existing mode-dependent label. Verification: TypeScript/Vite production build and git diff --check passed.

## Global default location

- User requested a UK default location with useful precipitation data. Compared eight UK locations against the live ifs-20261111T12Z-global1 run.
- Selected Fort William, UK: approximately 3.54 mm over 72 hours, with 11 intervals >=0.1 mm. This is a forecast-grid sample, not an observation or a guarantee of future rainfall.
- Global mode initially selects Fort William; India retains Chennai, and existing location search/map selection remain available.
- ESLint and TypeScript/Vite production build passed.

## Independent source GRIB validation

- Resumed the user-requested source-data audit; original 12Z source download was complete and matched its recorded SHA, but that run was no longer served. Pinned and fetched live 18Z run instead, verified exact source hash.
- Independent ecCodes audit uses scan metadata and separate geographic nearest-point lookup; imports no application processing helpers. Compared 336 intervals at 14 source-selected/city/date-line points.
- Units, sampled coordinates, grid indexing, UTC boundaries and clipped-interval values match. Found real nonzero-total artifacts at three source-dry points due to clipping negative packing differences; full-grid maximum total excess 0.213623046875 mm.
- Detailed report: reports/SOURCE_GRIB_VALIDATION.md; machine-readable field and interval evidence: reports/source-grib-audit.json.
- No application or deployment changes made. This milestone records both passing checks and the unresolved cumulative-consistency discrepancy.

## Processing v2 — fix cumulative consistency

- Replaced per-interval clipping in ingestion with a packing-bounded backward cumulative minimum anchored to the final source total; intervals are differences of the corrected sequence. Stored float64 preserves source precision.
- Larger decreases still reject publication; validation records corrected-cell counts and maximum adjustments, and publication asserts total conservation.
- Versioned processed run IDs with -v2 to force regeneration and isolate immutable caches; legacy IDs remain supported.
- Verified all 1,555,200 interval values against an independent reconstruction from original 18Z GRIB: no negative intervals, zero maximum horizon-total discrepancy, all 7,904 source-dry points dry, 57,353 monotonic series unchanged.
- 15 backend tests and Ruff checks passed. Fresh production decode peak RSS 204.375 MiB; local decode 1.89 s. No frontend feature or API-field changes.
- Full evidence in reports/CONSERVATION_FIX.md and conservation-fix.json; Render deployment still required.
