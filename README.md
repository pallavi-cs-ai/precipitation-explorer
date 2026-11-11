# Pluvia · Precipitation Explorer

Hosted URL: https://pluvia-precipitation.onrender.com (Render Free; cold starts can take time).

An interactive ECMWF IFS forecast explorer for the QUEST Lab application exercise. MapLibre precipitation maps, an ECharts time series, and a shared timeline stay synchronized. Click a location, advance or play forecast intervals, or select a period to see accumulated precipitation. Includes city presets, CSV export, and an accessible values table.

## Run locally

Requires Python 3.12 and Node 22.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m backend.app.ingest
python -m uvicorn backend.app.main:app --reload
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev -- --port 3000
```

Open http://127.0.0.1:3000. Vite proxies `/api` to port 8000. Ingestion fetches real forecasts; without a published dataset the application shows a retryable unavailable state. Run `python -m backend.app.ingest --watch` for periodic refresh.

For a production-style local process, run `npm run build` in `frontend`, then `python -m backend.app.serve` from the repository root. FastAPI serves the compiled frontend and the supervisor runs ingestion separately.

## Optional global overview

The deployed service remains on the India profile. A tested 1° sampled global profile is available locally with `FORECAST_COVERAGE=global1` and a separate `FORECAST_DATA_DIR`. See [benchmark, limitations and rollout](docs/GLOBAL_BENCHMARK.md). API fields and interactions are shared between profiles.

## Scientific scope

- ECMWF IFS total precipitation, cropped to grid centers 5–38°N and 65–100°E at 0.25° resolution.
- 24 three-hour intervals covering 72 hours **from model initialization**.
- Source cumulative precipitation is converted to millimetres and differenced into interval amounts. Only negative differences within GRIB packing tolerance are clamped; larger inconsistencies reject publication.
- Precipitation includes water-equivalent frozen precipitation. It is not a probability, observation, flood forecast, or street-level prediction.
- Point inspection samples the nearest grid center. Maps use nearest-neighbour raster rendering; displayed detail does not imply a finer forecast resolution.
- All displayed times use IST; API timestamps use UTC. The UI identifies older forecasts and offers new runs without mixing data across initialization times.

## Architecture and reliability

Python ingestion validates GRIB metadata and arrays, stages compressed interval grids and PNG frames, then atomically publishes a run. FastAPI supplies the manifest, nearest-grid point series, frames, and selected-period accumulation. Immutable run URLs, bounded server caches, HTTP caching, and TanStack Query reduce repeated work. Forecast downloads never run inside an API request.

API errors use structured responses and request IDs. The frontend has bounded retries, cancellation, loading states, layer retry, stale-data labels, and a rendering error boundary. Failed refreshes preserve the last valid run. `/healthz` checks the process; `/readyz` checks data availability; `/docs` exposes the API.

See [architecture](docs/ARCHITECTURE.md), [deployment](docs/DEPLOYMENT.md), and [development log](DEVELOPMENT_LOG.md).

## Verification

```sh
.venv/bin/python -m pytest -q
.venv/bin/ruff check backend tests
cd frontend
npm run lint
npm test
npm run build
```

GitHub Actions runs backend checks and frontend lint, tests, and build. Browser checks are recorded in `reports/application-checks.json`; these supplement automated processing/API/state tests.

## Data, attribution, and session history

Forecast source: ECMWF Open Data (CC BY 4.0). Visualizations are derived processing, not ECMWF products. Basemap: OpenFreeMap / OpenMapTiles / OpenStreetMap contributors, attributed on the map.

The repository was initialized on 10 November 2026 inside the same Codex session used for exploration and implementation. Meaningful milestones are committed after verification. Raw GRIB, processed forecast datasets, local environments, and credentials are excluded from Git. Original exploration remains in `scripts/explore.py` and `reports/`.
