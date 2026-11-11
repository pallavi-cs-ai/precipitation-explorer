"""Read-only forecast API. No request path calls ECMWF."""

import hashlib
import logging
import os
import re
import time
import uuid
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from threading import Lock

import numpy as np
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from .processing import render_png

log = logging.getLogger("forecast.api")


class Interval(BaseModel):
    id: int
    start: datetime
    end: datetime
    image_url: str


class Manifest(BaseModel):
    schema_version: int
    run_id: str
    model: str
    initialization: datetime
    generated_at: datetime
    resolution: float
    bounds: tuple[float, float, float, float]
    units: str
    interval_hours: int
    intervals: list[Interval]
    thresholds: list[float]
    colors: list[str]
    attribution: str
    source: str
    source_sha256: str


class Coordinates(BaseModel):
    lat: float
    lon: float


class PointInterval(BaseModel):
    id: int
    start: datetime
    end: datetime
    amount_mm: float | None


class PointForecast(BaseModel):
    run_id: str
    requested: Coordinates
    sampled: Coordinates
    units: str = "mm"
    intervals: list[PointInterval]


class ForecastStore:
    def __init__(self, root: Path):
        self.root = root
        self.render_lock = Lock()

    def directory(self, run_id: str) -> Path:
        if not re.fullmatch(r"ifs-\d{8}T\d{2}Z(?:-global1)?", run_id):
            raise HTTPException(404, "Forecast run not found")
        path = self.root / run_id
        if not (path / "manifest.json").is_file():
            raise HTTPException(404, "Forecast run unavailable; refresh to select the latest run")
        return path

    @lru_cache(maxsize=2)
    def manifest(self, run_id: str) -> Manifest:
        try:
            return Manifest.model_validate_json(
                (self.directory(run_id) / "manifest.json").read_text()
            )
        except (OSError, ValueError) as exc:
            raise HTTPException(503, "Forecast metadata is unavailable") from exc

    def latest(self) -> Manifest:
        try:
            run_id = (self.root / "latest").read_text().strip()
        except OSError as exc:
            raise HTTPException(503, "Forecast is being prepared. Please retry shortly.") from exc
        return self.manifest(run_id)

    @lru_cache(maxsize=2)
    def grid(self, run_id: str):
        try:
            with np.load(self.directory(run_id) / "grid.npz", allow_pickle=False) as data:
                cube, lat, lon = data["precipitation"], data["lat"], data["lon"]
            if cube.shape != (len(self.manifest(run_id).intervals), len(lat), len(lon)):
                raise ValueError("Invalid array shape")
            return cube, lat, lon
        except (OSError, ValueError, KeyError) as exc:
            raise HTTPException(503, "Forecast values are temporarily unavailable") from exc

    @lru_cache(maxsize=32)
    def accumulated_image(self, run_id: str, start: int, end: int):
        # Bound temporary rendering allocations when multiple users scrub ranges.
        with self.render_lock:
            cube, lat, lon = self.grid(run_id)
            return render_png(
                cube[start:end].sum(axis=0, dtype=np.float64),
                lat,
                lon,
                accumulated=True,
                bounds=self.manifest(run_id).bounds,
            )


def create_app(root: Path | None = None) -> FastAPI:
    app = FastAPI(title="Pluvia precipitation API", version="0.1.0")
    store = ForecastStore(root or Path(os.getenv("FORECAST_DATA_DIR", "data/forecasts")))
    app.state.store = store

    @app.middleware("http")
    async def requests(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex[:12]
        started = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("request_failed request_id=%s", request.state.request_id)
            response = JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "Something went wrong. Please retry.",
                        "request_id": request.state.request_id,
                    }
                },
            )
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        if response.status_code >= 400:
            response.headers["Cache-Control"] = "no-store"
        log.info(
            "request_id=%s method=%s path=%s status=%d duration_ms=%.1f",
            request.state.request_id,
            request.method,
            request.url.path,
            response.status_code,
            (time.monotonic() - started) * 1000,
        )
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": str(exc.detail),
                    "request_id": request.state.request_id,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Check the requested coordinates, interval or range.",
                    "request_id": request.state.request_id,
                }
            },
        )

    @app.get("/healthz")
    def health():
        return {"status": "ok"}

    @app.get("/readyz")
    def ready():
        manifest = store.latest()
        store.grid(manifest.run_id)
        return {"status": "ready", "run_id": manifest.run_id}

    @app.get("/api/v1/forecast/latest", response_model=Manifest)
    def latest(response: Response):
        response.headers["Cache-Control"] = "public, max-age=60, must-revalidate"
        return store.latest()

    @app.get("/api/v1/forecasts/{run_id}/point", response_model=PointForecast)
    def point(
        run_id: str,
        response: Response,
        lat: float = Query(ge=-90, le=90, allow_inf_nan=False),
        lon: float = Query(ge=-180, le=180, allow_inf_nan=False),
    ):
        manifest = store.manifest(run_id)
        w, s, e, n = manifest.bounds
        if not (w <= lon <= e and s <= lat <= n):
            raise HTTPException(422, "This location is outside the displayed forecast coverage")
        cube, yy, xx = store.grid(run_id)
        iy, ix = int(np.abs(yy - lat).argmin()), int(np.abs((xx - lon + 180) % 360 - 180).argmin())
        values = cube[:, iy, ix]
        response.headers["Cache-Control"] = "public, max-age=86400, immutable"
        return PointForecast(
            run_id=run_id,
            requested=Coordinates(lat=lat, lon=lon),
            sampled=Coordinates(lat=float(yy[iy]), lon=float(xx[ix])),
            intervals=[
                PointInterval(
                    id=i.id,
                    start=i.start,
                    end=i.end,
                    amount_mm=float(v) if np.isfinite(v) else None,
                )
                for i, v in zip(manifest.intervals, values, strict=True)
            ],
        )

    @app.get("/api/v1/forecasts/{run_id}/frames/{interval_id}.png")
    def frame(run_id: str, interval_id: int):
        manifest = store.manifest(run_id)
        if not 0 <= interval_id < len(manifest.intervals):
            raise HTTPException(404, "Forecast interval not found")
        path = store.directory(run_id) / f"{interval_id}.png"
        if not path.is_file():
            raise HTTPException(503, "Map image is temporarily unavailable")
        return FileResponse(
            path,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=86400, immutable"},
        )

    @app.get("/api/v1/forecasts/{run_id}/accumulation.png")
    def accumulation(
        run_id: str, request: Request, start: int = Query(ge=0), end: int = Query(ge=1)
    ):
        manifest = store.manifest(run_id)
        if not 0 <= start < end <= len(manifest.intervals):
            raise HTTPException(422, "Select a nonempty range within available forecast intervals")
        png = store.accumulated_image(run_id, start, end)
        etag = '"' + hashlib.sha256(png).hexdigest()[:24] + '"'
        headers = {"Cache-Control": "public, max-age=86400, immutable", "ETag": etag}
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        return Response(png, media_type="image/png", headers=headers)

    # Unknown API routes must remain JSON 404s, not an HTML SPA fallback.
    @app.get("/api/{path:path}")
    def unknown_api(path: str):
        raise HTTPException(404, "API endpoint not found")

    dist = Path(os.getenv("FRONTEND_DIST", "frontend/dist"))
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app


app = create_app()
