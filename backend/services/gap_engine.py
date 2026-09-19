"""
gap_engine.py — Expected-vs-actual input gap detection.

All comparisons are deterministic — Gemini is never consulted here.

The engine computes, for Fertilizer and Irrigation:
  expected_cumulative  — what the crop should have received up to today
  actual_cumulative    — what the farmer has actually logged

A gap is flagged as "behind" when:
  actual < expected − one_stage_dose

One stage dose is one week's reference dose × plant_count (for fertilizer)
or one day's reference dose × plant_count (for irrigation).

Public API
----------
compute_gaps(stages, current_stage_idx, plant_count, activities) -> list[GapResult]
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from services.scaling import scale_stage_quantities


@dataclass
class GapResult:
    activity_type: str           # "Fertilizer" | "Irrigation"
    expected_kg_or_litres: float
    actual_kg_or_litres: float
    gap: float                   # expected − actual  (positive = behind)
    unit: str
    status: str                  # "behind" | "on_track" | "ahead"
    one_stage_dose: float        # threshold used for "behind" classification


def _expected_fertilizer_kg(stages: list[dict], up_to_month: int, plant_count: int) -> tuple[float, float]:
    """Return (expected_kg_cumulative, one_stage_dose_kg) for fertilizer.

    Sums weekly dose × 4.33 weeks per month for each completed/current stage.
    """
    total_g = 0.0
    one_dose_g = 0.0
    weeks_per_month = 4.33  # average

    for stage in stages:
        if stage["month_start"] > up_to_month:
            break
        q = stage.get("quantities", {})
        gpw = float(q.get("fertilizer_grams_per_plant_per_week", 0) or 0)
        stage_months = min(
            stage["month_end"] if stage["month_end"] != 9999 else up_to_month,
            up_to_month,
        ) - stage["month_start"] + 1

        total_g += gpw * plant_count * weeks_per_month * stage_months
        # one_dose = the current stage's weekly total
        if stage["month_start"] <= up_to_month:
            one_dose_g = gpw * plant_count

    return total_g / 1000.0, one_dose_g / 1000.0


def _expected_irrigation_litres(stages: list[dict], up_to_month: int, plant_count: int) -> tuple[float, float]:
    """Return (expected_litres_cumulative, one_stage_dose_litres) for irrigation.

    Sums daily litre × 30 days per month for each completed/current stage.
    """
    total_l = 0.0
    one_dose_l = 0.0
    days_per_month = 30

    for stage in stages:
        if stage["month_start"] > up_to_month:
            break
        q = stage.get("quantities", {})
        lpd = float(q.get("irrigation_litres_per_plant_per_day", 0) or 0)
        stage_months = min(
            stage["month_end"] if stage["month_end"] != 9999 else up_to_month,
            up_to_month,
        ) - stage["month_start"] + 1

        total_l += lpd * plant_count * days_per_month * stage_months
        if stage["month_start"] <= up_to_month:
            one_dose_l = lpd * plant_count

    return total_l, one_dose_l


def _actual_by_type(activities: list[dict], activity_type: str) -> float:
    """Sum quantity for a given activity type from logged activities."""
    return sum(
        float(a["quantity"])
        for a in activities
        if a.get("activity_type") == activity_type
    )


def compute_gaps(
    stages: list[dict],
    months_elapsed: int,
    plant_count: int,
    activities: list[dict],
) -> list[GapResult]:
    """Compute expected-vs-actual gaps for Fertilizer and Irrigation.

    Parameters
    ----------
    stages          All stage dicts from crop_knowledge for this crop.
    months_elapsed  Current complete months since sowing.
    plant_count     Farmer's plant count.
    activities      All farm_activity records for this farmer.

    Returns
    -------
    List of GapResult, one per tracked input type.
    """
    results: list[GapResult] = []

    # ── Fertilizer ────────────────────────────────────────────────────────────
    exp_fert_kg, one_fert_dose_kg = _expected_fertilizer_kg(
        stages, months_elapsed, plant_count
    )
    act_fert_kg = _actual_by_type(activities, "Fertilizer")
    fert_gap = max(0.0, exp_fert_kg - act_fert_kg)
    fert_status = _classify(act_fert_kg, exp_fert_kg, one_fert_dose_kg)
    results.append(GapResult(
        activity_type="Fertilizer",
        expected_kg_or_litres=round(exp_fert_kg, 2),
        actual_kg_or_litres=round(act_fert_kg, 2),
        gap=round(fert_gap, 2),
        unit="kg",
        status=fert_status,
        one_stage_dose=round(one_fert_dose_kg, 2),
    ))

    # ── Irrigation ────────────────────────────────────────────────────────────
    exp_irr_l, one_irr_dose_l = _expected_irrigation_litres(
        stages, months_elapsed, plant_count
    )
    act_irr_l = _actual_by_type(activities, "Irrigation")
    irr_gap = max(0.0, exp_irr_l - act_irr_l)
    irr_status = _classify(act_irr_l, exp_irr_l, one_irr_dose_l)
    results.append(GapResult(
        activity_type="Irrigation",
        expected_kg_or_litres=round(exp_irr_l, 1),
        actual_kg_or_litres=round(act_irr_l, 1),
        gap=round(irr_gap, 1),
        unit="litres",
        status=irr_status,
        one_stage_dose=round(one_irr_dose_l, 1),
    ))

    return results


def _classify(actual: float, expected: float, one_dose: float) -> str:
    """Return 'behind', 'on_track', or 'ahead'.

    behind  : actual < expected − one_dose
    ahead   : actual > expected
    on_track: otherwise
    """
    if expected <= 0:
        return "on_track"
    if actual > expected:
        return "ahead"
    if actual < (expected - one_dose):
        return "behind"
    return "on_track"
