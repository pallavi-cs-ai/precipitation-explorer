"""Measure global API peak RSS with filled caches and concurrent range requests."""

import json
import resource
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from backend.app.main import create_app

client = TestClient(create_app(Path("data/global")))
run = client.get("/api/v1/forecast/latest").json()["run_id"]
start = time.perf_counter()
paths = [
    f"/api/v1/forecasts/{run}/accumulation.png?start={i}&end={j}"
    for i in range(8)
    for j in range(i + 1, i + 6)
]


def request(path):
    response = client.get(path)
    assert response.status_code == 200
    return len(response.content)


with ThreadPoolExecutor(max_workers=8) as pool:
    sizes = list(pool.map(request, paths))
report = {
    "concurrent_clients": 8,
    "requests": len(paths),
    "seconds": time.perf_counter() - start,
    "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    * (1 if sys.platform == "darwin" else 1024),
    "note": "API process only; local TestClient threads, not Render throughput; cache limit 32",
}
Path("reports/benchmark-api.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
