# Render deployment

The repository includes a multi-stage Dockerfile and `render.yaml` blueprint. The Node stage builds the frontend; the Python stage serves it with FastAPI and runs an independent ingestion process. One service allows the two processes to share the forecast directory.

The blueprint requests a **paid Starter service and 1 GB persistent disk**. Review the current cost in Render before approving creation. No paid resource is created by committing this configuration.

1. Connect the public GitHub repository to Render and create a Blueprint using `render.yaml`.
2. Review the service, region, disk, and displayed recurring cost before approving deployment.
3. Watch build and ingestion logs. `/healthz` can succeed before the first forecast is ready; `/readyz` returns 503 until a run has been validated and published.
4. Verify the public HTTPS application, `/readyz`, a location series, interval switching, and accumulated precipitation.
5. Check that a service restart preserves the published run on `/var/data`.

Automatic deploys are disabled in the blueprint so verified commits can be deployed deliberately. No ECMWF API credential is needed. Never put account credentials in the repository.

## Operating limits

- Initial startup requires downloading real ECMWF data. Download failures leave a clear unavailable state until ingestion succeeds.
- The worker checks for a new run every 30 minutes; this is polling frequency, not ECMWF forecast production frequency.
- Old runs are retained in a bounded collection. Requests for pruned runs can return 404; reload the latest forecast.
- A persistent disk binds the service to a single instance. This prototype does not support horizontal replicas sharing publication state.
- OpenFreeMap needs browser network access and MapLibre needs WebGL. The point chart and table remain useful when the basemap fails.
- A free ephemeral service would lose its cache on restart and may sleep. It is not equivalent to this persistent deployment configuration.

The Docker image must still be built and verified on Render: Docker is not installed in the local development environment. Public deployment and restart checks are pending until account access and any paid charge are approved.
