import json
from datetime import datetime, timedelta, timezone
from io import BytesIO

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.main import create_app
from backend.app.processing import BOUNDS, COLORS, THRESHOLDS, deaccumulate, render_png


def seed(tmp_path):
    run = "ifs-20261110T06Z"
    folder = tmp_path / run
    folder.mkdir()
    lat, lon = np.array([6.0, 5.0]), np.array([65.0, 66.0])
    cube = np.array([[[1.0, 2.0], [3.0, 4.0]], [[5.0, 6.0], [7.0, 8.0]]], dtype=np.float32)
    np.savez_compressed(folder / "grid.npz", precipitation=cube, lat=lat, lon=lon)
    base = datetime(2026, 11, 10, 6, tzinfo=timezone.utc)
    manifest = dict(
        schema_version=1,
        run_id=run,
        model="IFS",
        initialization=base.isoformat(),
        generated_at=base.isoformat(),
        resolution=0.25,
        bounds=BOUNDS,
        units="mm",
        interval_hours=3,
        intervals=[
            dict(
                id=i,
                start=(base + timedelta(hours=3 * i)).isoformat(),
                end=(base + timedelta(hours=3 * (i + 1))).isoformat(),
                image_url=f"/api/v1/forecasts/{run}/frames/{i}.png",
            )
            for i in range(2)
        ],
        thresholds=THRESHOLDS,
        colors=COLORS,
        attribution="ECMWF",
        source="test fixture",
        source_sha256="test",
    )
    (folder / "manifest.json").write_text(json.dumps(manifest))
    for i in range(2):
        (folder / f"{i}.png").write_bytes(render_png(cube[i], lat, lon))
    (tmp_path / "latest").write_text(run)
    return TestClient(create_app(tmp_path)), run


def test_not_ready_and_errors_are_uncached(tmp_path):
    client = TestClient(create_app(tmp_path))
    assert client.get("/healthz").status_code == 200
    response = client.get("/api/v1/forecast/latest")
    assert response.status_code == 503
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
    assert response.headers["cache-control"] == "no-store"


def test_point_and_range(tmp_path):
    client, run = seed(tmp_path)
    assert client.get("/readyz").status_code == 200
    point = client.get(f"/api/v1/forecasts/{run}/point?lat=6&lon=65").json()
    assert [v["amount_mm"] for v in point["intervals"]] == [1, 5]
    response = client.get(f"/api/v1/forecasts/{run}/accumulation.png?start=0&end=2")
    assert response.status_code == 200
    grid, lat, lon = client.app.state.store.grid(run)
    assert response.content == render_png(
        grid.sum(axis=0, dtype=np.float64), lat, lon, accumulated=True
    )
    assert (
        client.get(
            f"/api/v1/forecasts/{run}/accumulation.png?start=0&end=2",
            headers={"If-None-Match": response.headers["etag"]},
        ).status_code
        == 304
    )
    assert client.get(f"/api/v1/forecasts/{run}/frames/99.png").status_code == 404
    assert client.get(f"/api/v1/forecasts/{run}/accumulation.png?start=1&end=1").status_code == 422
    for query in ("lat=0&lon=0", "lat=NaN&lon=65", "lat=91&lon=65"):
        assert client.get(f"/api/v1/forecasts/{run}/point?{query}").status_code == 422
    assert client.get("/api/missing").status_code == 404


def test_missing_never_becomes_zero(tmp_path):
    client, run = seed(tmp_path)
    cube, _, _ = client.app.state.store.grid(run)
    cube[0, 0, 0] = np.nan
    assert (
        client.get(f"/api/v1/forecasts/{run}/point?lat=6&lon=65").json()["intervals"][0][
            "amount_mm"
        ]
        is None
    )


def test_map_north_south_orientation():
    lat, lon = np.array([38.0, 5.0]), np.array([65.0, 100.0])
    image = np.asarray(
        Image.open(BytesIO(render_png(np.array([[40.0, 40.0], [0.0, 0.0]]), lat, lon)))
    )
    assert image[0, 0, 3] > 0
    assert image[-1, 0, 3] == 0
    assert deaccumulate(np.array([1.0]), np.array([0.9999]), 0.001)[0] == 0


def test_failed_refresh_preserves_published_run(tmp_path, monkeypatch):
    import pytest

    from backend.app import ingest

    client, run = seed(tmp_path)

    class UnavailableClient:
        def __init__(self, **kwargs):
            pass

        def latest(self, **kwargs):
            raise ConnectionError("Upstream unavailable")

    monkeypatch.setattr(ingest, "Client", UnavailableClient)
    with pytest.raises(RuntimeError, match="previous dataset retained"):
        ingest.refresh(tmp_path)
    assert (tmp_path / "latest").read_text() == run
    assert client.get("/api/v1/forecast/latest").json()["run_id"] == run
    assert not list(tmp_path.glob(".staging-*"))


def test_upstream_timeout_is_bounded(monkeypatch):
    import requests

    from backend.app.ingest import TimeoutSession

    seen = {}

    def capture(self, *args, **kwargs):
        seen.update(kwargs)
        return None

    monkeypatch.setattr(requests.Session, "request", capture)
    TimeoutSession().get("https://example.invalid")
    assert seen["timeout"] == (10, 45)


def test_corrupt_dataset_returns_service_error(tmp_path):
    client, run = seed(tmp_path)
    (tmp_path / run / "grid.npz").write_bytes(b"not a dataset")
    response = client.get(f"/api/v1/forecasts/{run}/point?lat=6&lon=65")
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"


def test_global_profile_sampling_and_seam(tmp_path):
    from backend.app.coverage import GLOBAL, INDIA

    lat = np.array([89.5, 89.25, -89.5, 5.0])
    lon = np.array([-179.5, -179.5, 179.5, 65.0])
    assert GLOBAL.select(lat, lon).tolist() == [True, False, True, False]
    assert GLOBAL.shape == (180, 360)
    assert INDIA.shape == (133, 141)
    client, old_run = seed(tmp_path)
    folder = tmp_path / old_run
    run = old_run + "-global1"
    manifest = json.loads((folder / "manifest.json").read_text())
    manifest.update(run_id=run, resolution=1, bounds=GLOBAL.bounds)
    (folder / "manifest.json").write_text(json.dumps(manifest))
    cube = np.array([[[1, 20], [1, 20]], [[2, 30], [2, 30]]], dtype=np.float32)
    np.savez_compressed(
        folder / "grid.npz",
        precipitation=cube,
        lat=np.array([0.5, -0.5]),
        lon=np.array([-179.5, 179.5]),
    )
    folder.rename(tmp_path / run)
    (tmp_path / "latest").write_text(run)
    assert client.get("/readyz").status_code == 200
    for longitude, expected in [(-179.9, 1), (179.9, 20), (-180, 1), (180, 1)]:
        result = client.get(f"/api/v1/forecasts/{run}/point?lat=0&lon={longitude}")
        assert result.status_code == 200
        assert result.json()["intervals"][0]["amount_mm"] == expected
    assert client.get(f"/api/v1/forecasts/{run}/point?lat=89&lon=0").status_code == 422
    response = client.get(f"/api/v1/forecasts/{run}/accumulation.png?start=0&end=2")
    pixels = np.asarray(Image.open(BytesIO(response.content)))
    assert not np.array_equal(pixels[0, 0], pixels[0, -1])


def test_coverage_configuration(monkeypatch):
    import pytest

    from backend.app.coverage import GLOBAL, INDIA, configured_coverage

    monkeypatch.delenv("FORECAST_COVERAGE", raising=False)
    assert configured_coverage() == INDIA
    monkeypatch.setenv("FORECAST_COVERAGE", "global1")
    assert configured_coverage() == GLOBAL
    monkeypatch.setenv("FORECAST_COVERAGE", "typo")
    with pytest.raises(ValueError, match="Unknown"):
        configured_coverage()
