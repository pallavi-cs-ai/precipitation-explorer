# Precipitation explorer architecture

Status: product and technology direction accepted in this Codex session. Implementation defaults below keep delivery small; hosting provider and basemap provider remain to be verified.

## Product and scope

React + TypeScript + Vite, Tailwind CSS, shadcn/ui, MapLibre GL JS, Apache ECharts, TanStack Query; Python + FastAPI.

First deliver synchronized map, timeline and point precipitation bars. Add selected-period accumulation only after the core is verified. No domain-specific advice, probabilities, model training or AIFS in the initial release.

Initial implementation target: India-region coverage at 0.25 degrees, IFS tp, forecast hours 0–72 from initialization, 24 three-hour intervals. State available coverage and time limits explicitly; initial frame is the available interval containing now, otherwise the closest available interval. The horizon is not a promise of 72 hours remaining from page load.

## Visual contract

- Map: projected precipitation raster, fixed documented interval color scale, mm per labelled three-hour interval. Labels above precipitation; no point-density heatmap.
- Primary chart: vertical bars, one per interval, y-axis mm per interval. Tooltips include start/end time, amount and run identity. Selected bar and timeline agree. Missing is null, never zero. No smoothing or hourly interpolation.
- Timeline: play/pause, previous/next, keyboard control. It is a time selector, not a separate aggregate rainfall chart.
- Summary: selected interval amount at the chosen grid cell, forecast-window total and wettest interval; derived from the same series.
- Phase two: brush selection snaps to interval boundaries; totals update at location and on map. Clearly separate accumulated-period scale/legend from interval scale. No dual-axis cumulative curve in MVP.
- Desktop: dominant map, location panel and bottom timeline. Mobile: map and bottom sheet. Include textual values and keyboard alternatives to canvas interactions; respect reduced motion.

## Shared state and request consistency

A single React reducer/context owns run ID, requested location, selected interval, mode, selected range and playback. TanStack Query owns remote data, not UI selection. No Redux dependency initially.

Query keys include run ID and requested coordinates. Responses include sampled grid coordinates. Abort obsolete requests, reject mismatched results, dispose chart/map listeners on unmount. Map image loads are also keyed by run and interval/range; only the latest intended selection may commit. During loading, explicitly indicate that the displayed image is the previous interval, or delay the synchronized selection until the next image is ready.

Do not replace the active run while a user is exploring. Notify when a newer complete run is available and switch all views together on acceptance.

## API contract

- GET /api/v1/forecast/latest: small complete-run manifest: schema version, run ID, initialization UTC, generated UTC, model, resolution, geographic bounds, interval IDs/start/end UTC, unit, legend thresholds, image URLs, attribution and freshness metadata.
- GET /api/v1/forecasts/{run_id}/point?lat=...&lon=...: requested coordinates, nearest sampled coordinates, intervals with amount_mm or null and coverage flags. Client can calculate summaries from this small series.
- GET /api/v1/forecasts/{run_id}/frames/{interval_id}.png: immutable projected raster; manifest provides geographic corners. All point values come from arrays, never image colors.
- Phase two GET /api/v1/forecasts/{run_id}/accumulation.png?start=...&end=...: allowed interval boundary IDs, start inclusive/end exclusive; sum precisely the same validated intervals as point totals. Validate bounds and range; bounded on-demand image cache, no eager generation of every combination.
- GET /healthz: process health. GET /readyz: complete dataset available.

Pydantic response/request models; OpenAPI-generated frontend types; consistent JSON error envelope for API errors. 422 invalid parameters, 404 unavailable run/interval, 503 no complete forecast. Never silently fall back to a different run.

## Data and cache architecture

Scheduled Python ingestion -> downloaded GRIB -> metadata/unit/time/grid validation -> interval arrays -> regional crop -> projected PNGs and manifest -> atomic publication -> FastAPI.

Fetch outside request handlers. Limit retries and timeouts; preserve last complete run on failure. Validate per-field coordinates and accumulation ranges, units, missing values, finite/nonnegative values and packing tolerances. Persist interval arrays as the canonical representation so map and point accumulation use the same arithmetic. Avoid grid data as JSON. Keep forecast initialization, valid intervals and processing timestamps distinct and UTC in APIs; format timezone explicitly in the browser.

Three cache layers:
1. Server: immutable per-run arrays/images on persistent disk. Small bounded in-process cache; no Redis or SQL database initially.
2. HTTP/browser: run-specific successful responses can use long immutable caching, with ETags; latest manifest uses short TTL/revalidation. CDN optional. Retain at least two complete runs and handle expired run URLs explicitly.
3. TanStack Query: explicit staleTime for latest (e.g. 5 minutes); immutable run data treated as fresh. Limit inactive cache lifetime, retries and prefetch. MapLibre/browser handles image caching separately; prefetch only adjacent frames.

Use one container serving FastAPI and compiled frontend on the same origin initially. A separate scheduled invocation runs ingestion with a single-writer lock on the same persistent dataset. Verify hosting supports disk and scheduling before selection. Production must start with a real complete dataset or report not ready; never substitute fabricated weather. Basemap provider needs verified attribution, usage terms, CORS and any browser-key restrictions.

## Programming and verification standards

Separate ingestion, scientific transforms, storage, API routes and frontend features. TypeScript strict, ESLint, formatting; typed Python/Pydantic, Ruff and formatting. Pin dependency lockfiles; configuration through validated settings and an example environment file. No secrets, raw GRIB or generated runtime caches in Git. Structured logs record run and request identity, not secrets.

Tests should cover unit conversion, packing tolerance/reset rejection, missing data, grid lookup, coordinate orientation, UTC intervals, range sum consistency, API validation and stale-response protection. Verify scientific point values against decoded GRIB. Integration test a real-data artifact. Browser smoke test must prove map click -> point series, bar/timeline -> matching frame, mobile layout, loading/errors and phase-two range totals. Run typecheck, lint, production build and appropriate tests before milestone commits. CI runs these checks; it must not depend on live ECMWF availability.

Deliver in order: (1) full horizon ingestion + API contract/tests, (2) synchronized responsive frontend, (3) deployed vertical slice and refresh, (4) range selection if stable, (5) final verification and walkthrough. Every milestone committed within this session.
