"""Compare corrected production decoding against independently indexed source GRIB."""

import json
import resource
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from eccodes import codes_get, codes_get_array, codes_grib_new_from_file, codes_release

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.coverage import GLOBAL
from backend.app.ingest import decode

root = Path("data/source-audit")
m = json.loads((root / "manifest.json").read_text())
fields = {}
with (root / "source.grib2").open("rb") as stream:
    while (gid := codes_grib_new_from_file(stream)) is not None:
        try:
            assert codes_get(gid, "units") == "m"
            assert codes_get(gid, "longitudeOfFirstGridPointInDegrees") == 180
            fields[int(codes_get(gid, "endStep"))] = (
                codes_get_array(gid, "values").reshape(721, 1440)[2::4, 2::4] * 1000
            )
        finally:
            codes_release(gid)
source = np.stack([fields[s] for s in sorted(fields)])
start = time.perf_counter()
cube, lat, lon, records = decode(
    root / "source.grib2",
    datetime.fromisoformat(m["initialization"].replace("Z", "+00:00")),
    GLOBAL,
)
seconds = time.perf_counter() - start
# Independent vectorized reference for the lower monotonic envelope.
reference = np.minimum.accumulate(source[::-1], axis=0)[::-1]
expected = np.diff(reference, axis=0, prepend=np.zeros_like(reference[:1]))
assert np.array_equal(cube, expected)
assert (cube >= 0).all()
assert np.array_equal(cube.sum(axis=0), source[-1])
assert np.array_equal(lat, 89.5 - np.arange(180))
assert np.array_equal(lon, -179.5 + np.arange(360))
dry = source[-1] == 0
assert (cube[:, dry] == 0).all()
monotonic = (np.diff(source, axis=0) >= 0).all(axis=0)
assert np.array_equal(
    cube[:, monotonic],
    np.diff(source[:, monotonic], axis=0, prepend=np.zeros_like(source[:1, monotonic])),
)
report = {
    "source_run": m["run_id"],
    "source_sha256": m["source_sha256"],
    "grid_points": int(source.shape[1] * source.shape[2]),
    "interval_values": int(cube.size),
    "max_total_difference_mm": float(np.abs(cube.sum(axis=0) - source[-1]).max()),
    "negative_output_intervals": int((cube < 0).sum()),
    "dry_points": int(dry.sum()),
    "dry_points_with_nonzero_intervals": int((cube[:, dry] != 0).any(axis=0).sum()),
    "unchanged_monotonic_points": int(monotonic.sum()),
    "corrected_cumulative_values": int((reference != source).sum()),
    "max_cumulative_adjustment_mm": float((source - reference).max()),
    "decode_seconds": seconds,
    "audit_process_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    * (1 if sys.platform == "darwin" else 1024),
    "note": "RSS includes source arrays and independent reference; not production-only memory.",
}
Path("reports/conservation-fix.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
