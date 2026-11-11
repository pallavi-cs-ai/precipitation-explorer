# Global overview benchmark and rollout

Measured locally on 11 November 2026 using real IFS run `20261111T06Z`, all 24 three-hour fields. Input: 10,273,421 bytes (9.80 MiB), download 14.26 seconds. Both profiles download exactly the same global source; only the retained grid differs. These are single-run measurements on the development Mac, not a Render performance SLA.

| Metric | Original India implementation | Configurable India | Global 1° |
|---|---:|---:|---:|
| Grid | 133 × 141 × 24 | same | 180 × 360 × 24 |
| Numeric cube | 1.72 MiB | same | 5.93 MiB |
| Peak ingestion RSS | 153.91 MiB | 154.44 MiB | 167.61 MiB |
| Decode + encode | 1.47 s | 2.11 s | 2.53 s |
| Compressed grid | 176.7 KiB | same | 697.8 KiB |
| All 24 PNGs | 197.5 KiB | same | 591.6 KiB |
| Largest frame | 9.9 KiB | same | 25.6 KiB |
| Full-period PNG | 10.4 KiB | same | 28.0 KiB |
| Full-period render | 10 ms | 10 ms | 16 ms |

Original measurements were taken before the profile refactor. Current-profile evidence is in `reports/benchmark-india.json` and `reports/benchmark-global.json`. Images retain the existing 564 × 576 Web Mercator raster shape; screen interpolation remains nearest-neighbour. Global numeric output is 1° sampled; image pixel size is a display choice, not scientific resolution.

## Render estimate and decision

The API was exercised in a fresh process with eight simultaneous clients and 40 different accumulation requests, filling the bounded cache. Unrestricted parallel rendering peaked at 187.2 MiB. A per-store render lock reduces that to 78.0 MiB (0.59 s for the local request batch). This simple bound prevents temporary raster buffers multiplying with concurrent requests. API calls do not download or decode GRIB.

Adding separate ingestion and API peak RSS gives approximately 246 MiB. Budget approximately **300 MiB** including supervisor and runtime headroom, below Render Free's 512 MiB limit. This sum is an estimate, not a measured container peak; OS/allocator behaviour and traffic differ. The grid cache holds at most two runs and accumulation cache at most 32 PNGs.

Render Free has 0.1 CPU. A rough planning allowance is **25–60 seconds for processing**, plus network download and platform cold start; do not extrapolate laptop wall-clock time as a guarantee. Global processing is only modestly larger than the existing pipeline, and output storage is roughly 1.26 MiB/run (about 15 MiB for 12 runs), excluding temporary raw input and small metadata. Global source decoding already occurs in the current deployed pipeline.

Decision: proceed with the global implementation and local verification. Keep the deployed India service and its environment unchanged. No extra Render service is created (free service hours are shared). A production switch can use `FORECAST_COVERAGE=global1` after deploying the tested code; `india` remains the default and rollback profile.

## Scientific and compatibility choices

- Global cells sample native 0.25° IFS values at 1° centers (±0.5, ±1.5, ...). This is **not averaging or a new model resolution**. Small/local rain systems may be missed. Do not use this overview as a replacement for a high-resolution regional view.
- Full numeric grid contains latitudes ±89.5°. The map and point endpoint support displayed bounds ±85.0511° because Web Mercator cannot display the poles. This limit is stated in About the data.
- No endpoint or JSON field was removed. Global run IDs append `-global1`, separating immutable URLs and browser cache keys from India runs. Existing IDs still work. Consumers must treat run IDs as opaque identifiers.
- Bounds and resolution drive the UI; the same timeline, chart, range controls and CSV export are used for both profiles. All time labels now use UTC; CSV timestamps are UTC.
- `backend/app/coverage.py` owns profile definitions; `FORECAST_COVERAGE` selects one. Ingestion, rendering and API sampling share those definitions/manifest bounds. No tile server, database or new service is required.

## Reproduce

Download a pinned 24-step `tp` GRIB with `ecmwf.opendata.Client` to ignored `data/benchmark/source.grib2`; put its `run` ISO timestamp, `download_seconds` and `bytes` in `data/benchmark/source.json`. Then:

```sh
.venv/bin/python scripts/benchmark_pipeline.py india
.venv/bin/python scripts/benchmark_pipeline.py global
FORECAST_COVERAGE=global1 FORECAST_DATA_DIR=data/global .venv/bin/python -m backend.app.ingest
.venv/bin/python scripts/benchmark_api.py
npm --prefix frontend run build
FORECAST_DATA_DIR=data/global .venv/bin/python -m uvicorn backend.app.main:app --port 8001
```

The `data/global` directory keeps local global exploration separate from the India cache. Raw data and generated datasets remain excluded from Git. Benchmark scripts report full-process high-water RSS, not only array allocation.
