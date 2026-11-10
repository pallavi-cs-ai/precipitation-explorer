# Precipitation Explorer

QUEST Lab application exercise: inspect real ECMWF IFS precipitation before building the web application.

This repository was initialized within the Codex session on 10 November 2026. Synced project sources are untouched.

## Exploration

Create a Python environment and install `requirements.txt`, then run:

```sh
python scripts/explore.py
python -m pytest -q
```

Downloads are stored under ignored `data/`. Small derived evidence is under `reports/`. Forecast data: ECMWF Open Data, CC BY 4.0; derived visualizations are our processing, not ECMWF products.

No frontend, backend service, deployment, or model accuracy claim is included at this milestone.
