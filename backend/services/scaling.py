"""
scaling.py — Plant-count quantity scaling engine.

All arithmetic that converts per-plant reference doses into
orchard-total quantities lives here. Nothing is calculated in
Gemini — these functions are the only source of scaled numbers.

Public API
----------
scale_stage_quantities(stage, plant_count) -> dict
    Returns a dict of pre-scaled totals for a given stage.

scale_quantity(reference_quantity, plant_count) -> float
    Generic scalar: reference_quantity × plant_count.
"""

from __future__ import annotations


def scale_quantity(reference_quantity: float, plant_count: int) -> float:
    """Return reference_quantity × plant_count.

    Both inputs are validated: negative values raise ValueError.
    """
    if reference_quantity < 0:
        raise ValueError(f"reference_quantity must be >= 0, got {reference_quantity}")
    if plant_count < 0:
        raise ValueError(f"plant_count must be >= 0, got {plant_count}")
    return reference_quantity * plant_count


def scale_stage_quantities(stage: dict, plant_count: int) -> dict:
    """Scale all quantitative fields in a stage for a given plant count.

    Returns a flat dict of scaled totals. All arithmetic is done here —
    never in Gemini, never in the frontend.

    Keys returned:
        plant_count                          int
        total_irrigation_litres_per_day      float
        total_fertilizer_grams_per_week      float
        total_fertilizer_kg_per_week         float
        fertilizer_name                      str
        fertilizer_type                      str
        per_plant_irrigation_lpd             float  (reference, unscaled)
        per_plant_fertilizer_gpw             float  (reference, unscaled)
    """
    q = stage.get("quantities", {})

    irr_lpd = float(q.get("irrigation_litres_per_plant_per_day", 0) or 0)
    fert_gpw = float(q.get("fertilizer_grams_per_plant_per_week", 0) or 0)

    total_irr = scale_quantity(irr_lpd, plant_count)
    total_fert_g = scale_quantity(fert_gpw, plant_count)
    total_fert_kg = total_fert_g / 1000.0

    return {
        "plant_count": plant_count,
        "total_irrigation_litres_per_day": round(total_irr, 1),
        "total_fertilizer_grams_per_week": round(total_fert_g, 1),
        "total_fertilizer_kg_per_week": round(total_fert_kg, 3),
        "fertilizer_name": q.get("fertilizer_name", ""),
        "fertilizer_type": q.get("fertilizer_type", "Fertilizer"),
        "per_plant_irrigation_lpd": irr_lpd,
        "per_plant_fertilizer_gpw": fert_gpw,
    }
