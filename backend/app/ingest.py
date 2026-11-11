"""python -m backend.app.ingest [--watch]: atomic, single-writer forecast publication."""

import argparse
import fcntl
import hashlib
import json
import logging
import os
import shutil
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import requests
from eccodes import codes_get, codes_get_array, codes_grib_new_from_file, codes_release
from ecmwf.opendata import Client

from .coverage import INDIA, Coverage, configured_coverage
from .processing import (
    COLORS,
    THRESHOLDS,
    DataValidationError,
    deaccumulate,
    render_png,
    to_mm,
)

log = logging.getLogger("forecast.ingest")
ROOT = Path(os.getenv("FORECAST_DATA_DIR", "data/forecasts"))


class TimeoutSession(requests.Session):
    def request(self, *args, **kwargs):
        kwargs["timeout"] = (10, 45)
        return super().request(*args, **kwargs)


def decode(path: Path, expected_run: datetime, coverage: Coverage = INDIA):
    arrays, records, coordinates = {}, {}, None
    with path.open("rb") as stream:
        while (gid := codes_grib_new_from_file(stream)) is not None:
            try:
                meta = {
                    key: codes_get(gid, key)
                    for key in [
                        "shortName",
                        "units",
                        "stepType",
                        "startStep",
                        "endStep",
                        "dataDate",
                        "dataTime",
                        "numberOfMissing",
                        "packingError",
                    ]
                }
                step = int(meta["endStep"])
                if (
                    meta["shortName"] != "tp"
                    or meta["stepType"] != "accum"
                    or meta["startStep"] != 0
                ):
                    raise DataValidationError("Expected tp accumulated from initialization")
                if meta["numberOfMissing"] or step in arrays:
                    raise DataValidationError("Missing data or duplicate step")
                if (
                    str(meta["dataDate"]) != expected_run.strftime("%Y%m%d")
                    or meta["dataTime"] != expected_run.hour * 100
                ):
                    raise DataValidationError("Mixed forecast runs")
                lat = codes_get_array(gid, "latitudes")
                lon = (codes_get_array(gid, "longitudes") + 180) % 360 - 180
                if coordinates is None:
                    coordinates = (lat, lon)
                elif not np.array_equal(lat, coordinates[0]) or not np.array_equal(
                    lon, coordinates[1]
                ):
                    raise DataValidationError("Grid changed across forecast steps")
                values = to_mm(codes_get_array(gid, "values"), meta["units"])
                if not np.isfinite(values).all() or values.min() < 0:
                    raise DataValidationError("Invalid precipitation values")
                mask = coverage.select(lat, lon)
                yy, xx = np.unique(lat[mask])[::-1], np.unique(lon[mask])
                if (len(yy), len(xx)) != coverage.shape:
                    raise DataValidationError("Unexpected coverage grid")
                order = np.lexsort((lon[mask], -lat[mask]))
                arrays[step] = values[mask][order].reshape(len(yy), len(xx))
                records[step] = {
                    **meta,
                    "packing_error_mm": float(
                        to_mm(np.array([meta["packingError"]]), meta["units"])[0]
                    ),
                }
            finally:
                codes_release(gid)
    if sorted(arrays) != list(range(3, 73, 3)):
        raise DataValidationError("Incomplete 72-hour forecast")
    previous, previous_error = np.zeros_like(arrays[3]), 0.0
    intervals = []
    for step in sorted(arrays):
        error = records[step]["packing_error_mm"]
        raw_delta = arrays[step] - previous
        records[step]["negative_differences_clipped"] = int((raw_delta < 0).sum())
        intervals.append(deaccumulate(previous, arrays[step], error + previous_error + 1e-8))
        previous, previous_error = arrays[step], error
    return np.stack(intervals), yy, xx, list(records.values())


def refresh(root: Path = ROOT):
    coverage = configured_coverage()
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".ingest.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log.info("Another ingest process holds the lock")
            return
        failure = None
        for source in ("ecmwf", "aws"):
            stage = None
            try:
                client = Client(
                    source=source,
                    model="ifs",
                    resol="0p25",
                    maximum_retries=2,
                    retry_after=2,
                    use_server_retry_after=False,
                )
                client.session = TimeoutSession()
                run = client.latest(type="fc", stream="oper", step=72, param="tp").replace(
                    tzinfo=timezone.utc
                )
                run_id = f"ifs-{run:%Y%m%dT%H}Z{coverage.suffix}"
                target = root / run_id
                current = (
                    (root / "latest").read_text().strip() if (root / "latest").exists() else ""
                )
                if current and current.split("Z")[0] > run_id.split("Z")[0]:
                    log.warning("Ignoring older source run %s; current run is %s", run_id, current)
                    return
                if (target / "manifest.json").exists():
                    # Recover a crash after directory publication but before pointer replacement.
                    pointer = root / ".latest.tmp"
                    pointer.write_text(run_id)
                    os.replace(pointer, root / "latest")
                    log.info("Run already published: %s", run_id)
                    return
                stage = root / f".staging-{uuid.uuid4().hex}"
                stage.mkdir()
                grib = stage / "source.grib2"
                log.info("Fetching %s from %s", run_id, source)
                client.retrieve(
                    date=run.strftime("%Y%m%d"),
                    time=run.hour,
                    stream="oper",
                    type="fc",
                    step=list(range(3, 73, 3)),
                    param="tp",
                    target=str(grib),
                )
                cube, lat, lon, records = decode(grib, run, coverage)
                np.savez_compressed(stage / "grid.npz", precipitation=cube, lat=lat, lon=lon)
                intervals = []
                for i, step in enumerate(range(3, 73, 3)):
                    (stage / f"{i}.png").write_bytes(
                        render_png(cube[i], lat, lon, bounds=coverage.bounds)
                    )
                    intervals.append(
                        {
                            "id": i,
                            "start": (run + timedelta(hours=step - 3)).isoformat(),
                            "end": (run + timedelta(hours=step)).isoformat(),
                            "image_url": f"/api/v1/forecasts/{run_id}/frames/{i}.png",
                        }
                    )
                manifest = {
                    "schema_version": 1,
                    "run_id": run_id,
                    "model": "IFS",
                    "initialization": run.isoformat(),
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "resolution": coverage.resolution,
                    "bounds": coverage.bounds,
                    "units": "mm",
                    "interval_hours": 3,
                    "intervals": intervals,
                    "thresholds": THRESHOLDS,
                    "colors": COLORS,
                    "attribution": "ECMWF Open Data · CC BY 4.0",
                    "source": source,
                    "source_sha256": hashlib.sha256(grib.read_bytes()).hexdigest(),
                }
                (stage / "manifest.json").write_text(json.dumps(manifest))
                (stage / "validation.json").write_text(json.dumps(records))
                # Raw forecast is temporary; processed data and provenance are retained.
                grib.unlink()
                os.replace(stage, target)
                pointer = root / ".latest.tmp"
                pointer.write_text(run_id)
                os.replace(pointer, root / "latest")
                # Retain twelve complete runs; never remove the active run.
                published = sorted(p for p in root.glob("ifs-*") if (p / "manifest.json").is_file())
                for old in published[:-12]:
                    if old.name != run_id:
                        shutil.rmtree(old)
                log.info("Published complete run: %s", run_id)
                return
            except Exception as exc:
                failure = exc
                log.exception("Ingestion failed from %s; existing run unchanged", source)
                if stage and stage.exists():
                    shutil.rmtree(stage)
        raise RuntimeError("All forecast sources failed; previous dataset retained") from failure


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    while True:
        try:
            refresh()
        except Exception:
            log.exception("Refresh failed")
            if not args.watch:
                raise SystemExit(1)
        if not args.watch:
            break
        time.sleep(1800)


if __name__ == "__main__":
    main()
