"""Scientific transforms shared by ingestion and API. Amounts are water equivalent."""

from io import BytesIO

import numpy as np
from PIL import Image

BOUNDS = (64.875, 4.875, 100.125, 38.125)  # pixel edges: W, S, E, N
THRESHOLDS = [0.1, 1, 2, 5, 10, 20, 40]
COLORS = ["#b8e3e2", "#82cecf", "#43b6bb", "#1e929e", "#256db1", "#5349a3", "#9b4299"]


class DataValidationError(ValueError):
    """A forecast cannot be published safely."""


def to_mm(values: np.ndarray, units: str) -> np.ndarray:
    if units == "m":
        return values * 1000.0
    if units in ("kg m**-2", "kg m-2", "mm"):
        return values.copy()
    raise DataValidationError(f"Unsupported precipitation units: {units}")


def deaccumulate(previous: np.ndarray, current: np.ndarray, tolerance: float) -> np.ndarray:
    if previous.shape != current.shape or not np.isfinite(current).all():
        raise DataValidationError("Nonfinite values or inconsistent grid")
    delta = current - previous
    if float(delta.min()) < -tolerance:
        raise DataValidationError("Accumulation decreased beyond packing tolerance")
    return np.maximum(delta, 0).astype(np.float32)


def render_png(values: np.ndarray, lat: np.ndarray, lon: np.ndarray, *, accumulated=False) -> bytes:
    """Nearest-neighbour sample into Web Mercator; no visual spatial precision invented."""
    west, south, east, north = BOUNDS
    width, height = 564, 576
    xs = np.linspace(west, east, width, endpoint=False) + (east - west) / (2 * width)

    def merc(degrees):
        return np.log(np.tan(np.pi / 4 + np.deg2rad(degrees) / 2))

    top, bottom = merc(north), merc(south)
    yy = top - (np.arange(height) + 0.5) * (top - bottom) / height
    ys = np.rad2deg(2 * np.arctan(np.exp(yy)) - np.pi / 2)
    ix = np.abs(lon[:, None] - xs).argmin(axis=0)
    iy = np.abs(lat[:, None] - ys).argmin(axis=0)
    projected = values[iy[:, None], ix]
    thresholds = np.array(THRESHOLDS) * (3 if accumulated else 1)
    index = np.searchsorted(thresholds, projected, side="right")
    palette = np.array(
        [[0, 0, 0, 0]] + [[int(c[i : i + 2], 16) for i in (1, 3, 5)] + [225] for c in COLORS],
        dtype=np.uint8,
    )
    rgba = palette[index]
    rgba[~np.isfinite(projected)] = 0
    buffer = BytesIO()
    Image.fromarray(rgba).save(buffer, format="PNG")
    return buffer.getvalue()
