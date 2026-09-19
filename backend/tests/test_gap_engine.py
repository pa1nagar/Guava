"""
test_gap_engine.py — Tests for services/gap_engine.py

Covers:
  - actual < expected → "behind"
  - actual == expected → "on_track"
  - actual > expected → "ahead"
  - zero expected (drought stage) → "on_track"
  - empty activities → full gap
  - both fertilizer and irrigation gaps returned
"""

import pytest
from services.gap_engine import compute_gaps, _classify, GapResult


# ── Minimal stage fixtures ────────────────────────────────────────────────────

def _stage(stage_id, month_start, month_end, irr_lpd, fert_gpw):
    return {
        "stage_id": stage_id,
        "month_start": month_start,
        "month_end": month_end,
        "quantities": {
            "irrigation_litres_per_plant_per_day": irr_lpd,
            "fertilizer_grams_per_plant_per_week": fert_gpw,
        },
    }


SIMPLE_STAGES = [
    _stage("s1", 0, 2,  3, 5),
    _stage("s2", 3, 7,  4, 7),
    _stage("s3", 8, 10, 3, 9),
]


class TestClassify:

    def test_actual_zero_expected_nonzero_behind(self):
        assert _classify(0, 100, 20) == "behind"

    def test_actual_equals_expected_on_track(self):
        assert _classify(100, 100, 20) == "on_track"

    def test_actual_greater_ahead(self):
        assert _classify(150, 100, 20) == "ahead"

    def test_actual_slightly_below_but_within_one_dose_on_track(self):
        # expected=100, one_dose=20, actual=85 → 100-20=80, 85>80 → on_track
        assert _classify(85, 100, 20) == "on_track"

    def test_actual_more_than_one_dose_behind(self):
        # expected=100, one_dose=20, actual=70 → 100-20=80, 70<80 → behind
        assert _classify(70, 100, 20) == "behind"

    def test_zero_expected_always_on_track(self):
        assert _classify(0, 0, 0) == "on_track"


class TestComputeGaps:

    def test_no_activities_full_gap(self):
        """With no logged activities, actual should be 0 for both types."""
        gaps = compute_gaps(SIMPLE_STAGES, months_elapsed=4, plant_count=100, activities=[])
        fert_gap = next(g for g in gaps if g.activity_type == "Fertilizer")
        irr_gap  = next(g for g in gaps if g.activity_type == "Irrigation")

        assert fert_gap.actual_kg_or_litres == 0.0
        assert fert_gap.expected_kg_or_litres > 0
        assert fert_gap.gap > 0

        assert irr_gap.actual_kg_or_litres == 0.0
        assert irr_gap.expected_kg_or_litres > 0

    def test_adequate_fertilizer_on_track(self):
        """Logging enough fertilizer should result in on_track status."""
        gaps = compute_gaps(SIMPLE_STAGES, months_elapsed=4, plant_count=100, activities=[])
        fert_gap = next(g for g in gaps if g.activity_type == "Fertilizer")
        # Log slightly more than expected.
        sufficient = fert_gap.expected_kg_or_litres + 1
        activities = [{"activity_type": "Fertilizer", "quantity": sufficient}]
        gaps2 = compute_gaps(SIMPLE_STAGES, months_elapsed=4, plant_count=100, activities=activities)
        fert_gap2 = next(g for g in gaps2 if g.activity_type == "Fertilizer")
        assert fert_gap2.status in ("on_track", "ahead")

    def test_over_logged_ahead(self):
        activities = [{"activity_type": "Fertilizer", "quantity": 999999}]
        gaps = compute_gaps(SIMPLE_STAGES, months_elapsed=4, plant_count=100, activities=activities)
        fert_gap = next(g for g in gaps if g.activity_type == "Fertilizer")
        assert fert_gap.status == "ahead"

    def test_returns_two_gap_results(self):
        gaps = compute_gaps(SIMPLE_STAGES, months_elapsed=2, plant_count=100, activities=[])
        types = {g.activity_type for g in gaps}
        assert "Fertilizer" in types
        assert "Irrigation" in types

    def test_gap_result_fields(self):
        gaps = compute_gaps(SIMPLE_STAGES, months_elapsed=2, plant_count=100, activities=[])
        for g in gaps:
            assert isinstance(g, GapResult)
            assert g.gap >= 0
            assert g.status in ("behind", "on_track", "ahead")
            assert g.unit in ("kg", "litres")

    def test_month_zero_single_plant(self):
        """At month 0 with one plant the expected amounts should match stage rates."""
        gaps = compute_gaps(SIMPLE_STAGES, months_elapsed=0, plant_count=1, activities=[])
        fert = next(g for g in gaps if g.activity_type == "Fertilizer")
        # One month of s1: 5 gpw/plant × 4.33 weeks = 21.65g = ~0.022 kg
        assert fert.expected_kg_or_litres == pytest.approx(5 * 4.33 / 1000, abs=0.01)
