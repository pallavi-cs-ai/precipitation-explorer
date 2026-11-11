"""Small, explicit coverage profiles; source data always uses the native 0.25° grid."""

import os
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Coverage:
    name: str
    resolution: float
    bounds: tuple[float, float, float, float]
    centers: tuple[float, float, float, float]  # W, S, E, N
    suffix: str = ""

    def select(self, lat, lon):
        w, s, e, n = self.centers
        mask = (lat >= s) & (lat <= n) & (lon >= w) & (lon <= e)
        mask &= np.isclose((lat - s) % self.resolution, 0)
        mask &= np.isclose((lon - w) % self.resolution, 0)
        return mask

    @property
    def shape(self):
        w, s, e, n = self.centers
        return round((n - s) / self.resolution) + 1, round((e - w) / self.resolution) + 1


INDIA = Coverage("India region", 0.25, (64.875, 4.875, 100.125, 38.125), (65, 5, 100, 38))
GLOBAL = Coverage(
    "Global overview",
    1.0,
    (-180, -85.05112878, 180, 85.05112878),
    (-179.5, -89.5, 179.5, 89.5),
    "-global1",
)
PROFILES = {"india": INDIA, "global1": GLOBAL}


def configured_coverage():
    name = os.getenv("FORECAST_COVERAGE", "india")
    if name not in PROFILES:
        raise ValueError(f"Unknown FORECAST_COVERAGE: {name}")
    return PROFILES[name]
