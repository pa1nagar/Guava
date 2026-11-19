"""
locations.py - resolve a (state, district) to coordinates. Pure apart from reading
one local JSON file.

Order: services.geo.get_exact_district_coordinates, then
data/district_centroids_supplement.json (rows with a public source_url), else
None. Never falls back to a state capital, so no distance is ever invented.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from services.geo import get_exact_district_coordinates, haversine_km

SUPPLEMENT_PATH = Path(__file__).resolve().parents[2] / "data" / "district_centroids_supplement.json"

BASIS_GEO = "district centre (services.geo)"
BASIS_SUPPLEMENT = "district HQ city (public source)"


@lru_cache(maxsize=1)
def load_supplement() -> dict[tuple[str, str], dict]:
    try:
        with open(SUPPLEMENT_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    out = {}
    for row in data.get("rows", []):
        try:
            key = (row["state"].strip().lower(), row["district"].strip().lower())
            out[key] = {"lat": float(row["lat"]), "lon": float(row["lon"]),
                        "source_url": row["source_url"], "kind": row.get("kind", "")}
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    return out


def resolve_district(state: str, district: str) -> Optional[tuple[float, float, str]]:
    """Return (lat, lon, basis) or None when the district is not known."""
    exact = get_exact_district_coordinates(state, district)
    if exact is not None:
        return exact[0], exact[1], BASIS_GEO
    row = load_supplement().get(((state or "").strip().lower(), (district or "").strip().lower()))
    if row is not None:
        return row["lat"], row["lon"], BASIS_SUPPLEMENT
    return None


def distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Straight-line (haversine) distance in km."""
    return haversine_km(a, b)
