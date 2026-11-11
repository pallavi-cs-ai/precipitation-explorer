"""Benchmark configurable India and 1-degree global sampling in fresh processes.

Run with repository Python: python scripts/benchmark_pipeline.py india|global
Input is a real, separately downloaded GRIB under ignored data/benchmark.
"""

import json
import resource
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app import ingest, processing

profile = sys.argv[1]
source = Path("data/benchmark")
metadata = json.loads((source / "source.json").read_text())
run = datetime.fromisoformat(metadata["run"]).replace(tzinfo=timezone.utc)
from backend.app.coverage import PROFILES

coverage = PROFILES["global1" if profile == "global" else "india"]
decode = lambda path, run: ingest.decode(path, run, coverage)
start = time.perf_counter()
cube, lat, lon, records = decode(source / "source.grib2", run)
decoded = time.perf_counter()
out = source / profile
out.mkdir(exist_ok=True)
np.savez_compressed(out / "grid.npz", precipitation=cube, lat=lat, lon=lon)
frames = [processing.render_png(v, lat, lon, bounds=coverage.bounds) for v in cube]
for i, frame in enumerate(frames):
    (out / f"{i}.png").write_bytes(frame)
finished = time.perf_counter()
acc_start = time.perf_counter()
acc = processing.render_png(
    cube.sum(axis=0, dtype=np.float64), lat, lon, accumulated=True, bounds=coverage.bounds
)
report = {
    "profile": profile,
    "source": metadata,
    "shape": list(cube.shape),
    "cube_bytes": cube.nbytes,
    "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    * (1 if sys.platform == "darwin" else 1024),
    "decode_seconds": decoded - start,
    "encode_seconds": finished - decoded,
    "processing_seconds": finished - start,
    "accumulation_seconds": time.perf_counter() - acc_start,
    "accumulation_bytes": len(acc),
    "grid_bytes": (out / "grid.npz").stat().st_size,
    "frames_bytes": sum(map(len, frames)),
    "max_frame_bytes": max(map(len, frames)),
    "png_size": [564, 576],
    "method": "nearest source-grid sample at 1-degree cell centers"
    if profile == "global"
    else "regional crop",
}
Path(f"reports/benchmark-{profile}.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
