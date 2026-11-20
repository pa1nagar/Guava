"""
test_climate_estimates.py - typed-in numbers are labelled as estimates and no
invented default fertilizer price is used.
"""
from services import climate


def _stage(stage_id, fert_name, gpw=10, months=2):
    return {
        "stage_id": stage_id, "label": stage_id,
        "quantities": {"fertilizer_name": fert_name,
                       "fertilizer_grams_per_plant_per_week": gpw,
                       "duration_months": months},
    }


def test_no_default_fertilizer_rate_constant():
    assert not hasattr(climate, "DEFAULT_FERTILIZER_RATE")


def test_unknown_fertilizer_has_no_rate_or_cost():
    items = climate.fertilizer_budget_forecast([_stage("a", "Mystery blend")], "a", 100)
    assert len(items) == 1
    assert items[0]["rate_per_kg"] is None
    assert items[0]["cost_estimate"] is None
    assert items[0]["total_kg"] > 0
    assert items[0]["is_estimate"] is True
    assert items[0]["rate_basis"] == climate.FERTILIZER_RATES_BASIS


def test_known_fertilizer_has_rate_cost_and_basis():
    items = climate.fertilizer_budget_forecast([_stage("a", "Urea (N)")], "a", 100)
    item = items[0]
    assert item["rate_per_kg"] == climate.FERTILIZER_RATES["Urea (N)"]
    assert item["cost_estimate"] == round(item["total_kg"] * item["rate_per_kg"], 0)
    assert item["is_estimate"] is True and item["rate_basis"]


def test_gdd_basis_text_is_set():
    assert "no published source" in climate.GDD_THRESHOLDS_BASIS