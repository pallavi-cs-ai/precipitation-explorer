"""Independent source audit. No application processing helpers are imported.

Uses GRIB scan metadata, row/column arithmetic and ecCodes nearest-point lookup.
Run after saving the live manifest and its pinned 24-field GRIB to data/source-audit.
"""

import hashlib
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen

import numpy as np
from eccodes import (
    codes_get,
    codes_get_array,
    codes_grib_find_nearest,
    codes_grib_new_from_file,
    codes_release,
)

ROOT = Path("data/source-audit")
BASE = "https://pluvia-precipitation.onrender.com"
manifest = json.loads((ROOT / "manifest.json").read_text())
run = datetime.fromisoformat(manifest["initialization"].replace("Z", "+00:00"))
raw_file = ROOT / "source.grib2"
assert hashlib.sha256(raw_file.read_bytes()).hexdigest() == manifest["source_sha256"]
assert manifest["resolution"] == 1.0
fields, metadata = {}, []
with raw_file.open("rb") as stream:
    while (gid := codes_grib_new_from_file(stream)) is not None:
        try:
            keys = [
                "shortName",
                "units",
                "stepType",
                "startStep",
                "endStep",
                "dataDate",
                "dataTime",
                "validityDate",
                "validityTime",
                "Ni",
                "Nj",
                "iScansNegatively",
                "jScansPositively",
                "jPointsAreConsecutive",
                "latitudeOfFirstGridPointInDegrees",
                "longitudeOfFirstGridPointInDegrees",
                "iDirectionIncrementInDegrees",
                "jDirectionIncrementInDegrees",
                "packingError",
            ]
            meta = {k: codes_get(gid, k) for k in keys}
            assert meta["shortName"] == "tp" and meta["stepType"] == "accum"
            assert meta["startStep"] == 0 and meta["units"] == "m"
            assert (meta["Ni"], meta["Nj"]) == (1440, 721)
            assert (
                meta["iScansNegatively"],
                meta["jScansPositively"],
                meta["jPointsAreConsecutive"],
            ) == (0, 0, 0)
            assert meta["latitudeOfFirstGridPointInDegrees"] == 90
            assert meta["longitudeOfFirstGridPointInDegrees"] == 180
            assert (
                meta["iDirectionIncrementInDegrees"] == meta["jDirectionIncrementInDegrees"] == 0.25
            )
            assert (
                meta["dataDate"] == int(run.strftime("%Y%m%d"))
                and meta["dataTime"] == run.hour * 100
            )
            step = int(meta["endStep"])
            assert step not in fields
            valid = run + timedelta(hours=step)
            assert (
                meta["validityDate"] == int(valid.strftime("%Y%m%d"))
                and meta["validityTime"] == valid.hour * 100
            )
            # Scan starts at 90N, 180E. Row 2 = 89.5N; column 2 = 180.5E = 179.5W.
            # Every fourth native cell gives 1-degree sampling; no application mask/order used.
            native = codes_get_array(gid, "values").reshape(721, 1440)
            fields[step] = native[2::4, 2::4].copy() * 1000.0  # metres -> millimetres
            metadata.append(meta)
        finally:
            codes_release(gid)
assert sorted(fields) == list(range(3, 73, 3))
latitudes = 89.5 - np.arange(180)
longitudes = -179.5 + np.arange(360)
last = fields[72]
points = [
    ("São Paulo", -23.5505, -46.6333),
    ("Fort William", 56.8198, -5.1052),
    ("Chennai", 13.0827, 80.2707),
    ("Sydney", -33.8688, 151.2093),
    ("Dateline east", 0.5, 179.5),
    ("Dateline west", 0.5, -179.5),
]
# Pick real high-rainfall and dry points directly from source data in each hemisphere quadrant.
for north in (True, False):
    for east in (True, False):
        eligible = ((latitudes[:, None] > 0) == north) & ((longitudes[None, :] > 0) == east)
        eligible &= np.abs(latitudes[:, None]) < 85
        for wet in (True, False):
            idx = (
                np.argmax(np.where(eligible, last, -np.inf))
                if wet
                else np.argmin(np.where(eligible, last, np.inf))
            )
            i, j = np.unravel_index(idx, last.shape)
            name = ("High " if wet else "Dry ") + ("N" if north else "S") + ("E" if east else "W")
            points.append((name, float(latitudes[i]), float(longitudes[j])))
results = []
discrepancies = []
for name, y, x in points:
    # These test locations avoid midpoint ties; derive nearest 1-degree cell arithmetically.
    sy = math.floor(y) + 0.5
    sx = math.floor(x) + 0.5
    row = round(89.5 - sy)
    col = round(sx + 179.5)
    snapshot = ROOT / (name.replace(" ", "_") + ".json")
    if "--cached" in sys.argv:
        api = json.loads(snapshot.read_text())
    else:
        with urlopen(
            f"{BASE}/api/v1/forecasts/{manifest['run_id']}/point?lat={y}&lon={x}", timeout=45
        ) as response:
            api = json.load(response)
        snapshot.write_text(json.dumps(api))
    checks = {
        "sampled_coordinates": api["sampled"] == {"lat": sy, "lon": sx},
        "run_id": api["run_id"] == manifest["run_id"],
        "units": api["units"] == "mm",
        "interval_count": len(api["intervals"]) == 24,
    }
    previous = 0.0
    diffs = []
    clipped = []
    timeline = []
    details = []
    for step in range(3, 73, 3):
        cumulative = float(fields[step][row, col])
        delta = cumulative - previous
        expected = max(0.0, delta)
        actual = api["intervals"][step // 3 - 1]
        diffs.append(abs(actual["amount_mm"] - expected))
        if delta < 0:
            clipped.append({"step": step, "raw_negative_mm": delta})
        start = run + timedelta(hours=step - 3)
        end = run + timedelta(hours=step)
        timeline.append(
            actual["id"] == step // 3 - 1
            and datetime.fromisoformat(actual["start"].replace("Z", "+00:00")) == start
            and datetime.fromisoformat(actual["end"].replace("Z", "+00:00")) == end
        )
        details.append(
            {
                "step_hours": step,
                "source_cumulative_mm": cumulative,
                "raw_difference_mm": delta,
                "expected_nonnegative_mm": expected,
                "served_mm": actual["amount_mm"],
                "start_utc": actual["start"],
                "end_utc": actual["end"],
            }
        )
        previous = cumulative
    checks["utc_boundaries"] = all(timeline)
    checks["interval_values"] = max(diffs) <= 1e-5
    total = sum(i["amount_mm"] for i in api["intervals"])
    result = {
        "name": name,
        "requested": {"lat": y, "lon": x},
        "sampled": {"lat": sy, "lon": sx},
        "source_72h_mm": previous,
        "served_interval_sum_mm": total,
        "total_difference_mm": total - previous,
        "max_interval_difference_mm": max(diffs),
        "negative_differences_clipped": clipped,
        "checks": checks,
        "intervals": details,
    }
    results.append(result)
    if not all(checks.values()):
        discrepancies.append(name)
# Independent ecCodes geospatial lookup confirms scan arithmetic at every selected cell in all fields.
nearest_max_error = 0.0
with raw_file.open("rb") as stream:
    while (gid := codes_grib_new_from_file(stream)) is not None:
        try:
            step = int(codes_get(gid, "endStep"))
            for result in results:
                y, x = result["sampled"]["lat"], result["sampled"]["lon"]
                point = codes_grib_find_nearest(gid, y, x)[0]
                longitude = point["lon"] if point["lon"] < 180 else point["lon"] - 360
                assert abs(point["lat"] - y) < 1e-8 and abs(longitude - x) < 1e-8
                expected = fields[step][round(89.5 - y), round(x + 179.5)]
                nearest_max_error = max(nearest_max_error, abs(point["value"] * 1000 - expected))
        finally:
            codes_release(gid)
assert nearest_max_error < 1e-8
# Quantify any packing-related cumulative decreases across the entire retained grid.
previous = np.zeros_like(last)
negatives = 0
clipped_excess = np.zeros_like(last)
largest_negative = 0.0
previous_error = 0.0
metadata.sort(key=lambda m: m["endStep"])
for meta in metadata:
    current = fields[meta["endStep"]]
    delta = current - previous
    error = meta["packingError"] * 1000
    assert delta.min() >= -(error + previous_error + 1e-8)
    negatives += int((delta < 0).sum())
    largest_negative = min(largest_negative, float(delta.min()))
    clipped_excess += np.maximum(-delta, 0)
    previous = current
    previous_error = error
report = {
    "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    "run_id": manifest["run_id"],
    "source_sha256": manifest["source_sha256"],
    "source_hash_matches": True,
    "source_units": "m",
    "conversion": "1 metre water-equivalent = 1000 millimetres",
    "source_grid": {"shape": [721, 1440], "scan_start": [90, 180], "spacing_degrees": 0.25},
    "sampled_grid": {
        "shape": [180, 360],
        "spacing_degrees": 1,
        "method": "native-cell subsampling; not area averaging",
    },
    "grib_fields": metadata,
    "results": results,
    "nearest_lookup_max_difference_mm": nearest_max_error,
    "all_grid_packing_effects": {
        "negative_differences": negatives,
        "most_negative_mm": largest_negative,
        "max_72h_clamping_excess_mm": float(clipped_excess.max()),
    },
    "failed_conversion_checks": discrepancies,
    "total_discrepancies": [
        {
            "name": r["name"],
            "difference_mm": r["total_difference_mm"],
            "cause": "Clamping negative packing differences breaks telescoping cumulative totals",
        }
        for r in results
        if abs(r["total_difference_mm"]) > 1e-5
    ],
    "response_source": "saved live response snapshots from this audit"
    if "--cached" in sys.argv
    else BASE,
}

Path("reports/source-grib-audit.json").write_text(json.dumps(report, indent=2) + "\n")
for r in results:
    print(
        r["name"],
        r["sampled"],
        round(r["source_72h_mm"], 6),
        r["max_interval_difference_mm"],
        r["total_difference_mm"],
    )
print("Packing effects:", report["all_grid_packing_effects"])
print("Failed checks:", discrepancies)
assert not discrepancies
