# Render deployment

The repository includes a multi-stage Dockerfile and `render.yaml` blueprint. The Node stage builds the frontend; the Python stage serves it with FastAPI and runs an independent ingestion process. One service allows the two processes to share the forecast directory.

The blueprint uses a **Free web service with no persistent disk**, as requested. Forecast files live in `/tmp/pluvia/forecasts` and are rebuilt after every restart or idle spin-down.

1. Connect the public GitHub repository to Render and create a Blueprint using `render.yaml`.
2. Verify the instance type is Free and that no paid disk or other paid resource is listed.
3. Watch build and ingestion logs. `/healthz` can succeed before the first forecast is ready; `/readyz` returns 503 until a run has been validated and published.
4. Verify the public HTTPS application, `/readyz`, a location series, interval switching, and accumulated precipitation.
5. Verify a restart shows the initial loading state and ingestion publishes a fresh run.

Automatic deploys are disabled in the blueprint so verified commits can be deployed deliberately. No ECMWF API credential is needed. Never put account credentials in the repository.

## Operating limits

- Initial startup requires downloading real ECMWF data. Download failures leave a clear unavailable state until ingestion succeeds.
- The worker checks for a new run every 30 minutes; this is polling frequency, not ECMWF forecast production frequency.
- Old runs are retained in a bounded collection. Requests for pruned runs can return 404; reload the latest forecast.
- This prototype uses one instance; there is no external shared publication store.
- OpenFreeMap needs browser network access and MapLibre needs WebGL. The point chart and table remain useful when the basemap fails.
- Render Free spins down after 15 minutes without inbound traffic. Its wake-up delay precedes ingestion, so the first visitor must wait for both. Refresh polling runs only while the service is awake. See [Render free-tier limits](https://render.com/docs/free).

The Docker image must still be built and verified on Render: Docker is not installed in the local development environment. Public deployment and restart checks are pending Render account access. Do not select a paid upgrade to resolve a quota limit without approval.
