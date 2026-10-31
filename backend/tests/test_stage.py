"""
test_stage.py — Tests for services/stage.py

Covers:
  - before any stage (day 0)
  - inside a known stage
  - after last configured stage
  - exact stage boundary (month_start == months_elapsed)
  - future sowing date rejected
  - unknown crop raises KeyError
  - is_final_stage flag
  - days_elapsed calculation
"""

import pytest
from datetime import date, timedelta
from fastapi import HTTPException

from services.stage import get_stage, compute_crop_age_months, StageResult


def _sowing(months_ago: int, days_offset: int = 0) -> date:
    """Return a sowing date that is approximately `months_ago` months before today."""
    today = date.today()
    y = today.year
    m = today.month - months_ago
    while m <= 0:
        m += 12
        y -= 1
    # Clamp day to last day of month.
    import calendar
    last_day = calendar.monthrange(y, m)[1]
    d = min(today.day, last_day) + days_offset
    d = max(1, min(d, last_day))
    return date(y, m, d)


class TestGetStage:

    def test_establishment_at_month_0(self):
        """A crop planted today should be in the first stage."""
        sr = get_stage("guava", date.today())
        assert sr.stage["stage_id"] == "establishment"
        assert sr.months_elapsed == 0
        assert sr.days_elapsed == 0
        assert sr.is_final_stage is False

    def test_vegetative_growth_at_month_4(self):
        sr = get_stage("guava", _sowing(4))
        assert sr.stage["stage_id"] == "vegetative_growth"
        assert sr.months_elapsed == 4

    def test_post_monsoon_at_month_9(self):
        sr = get_stage("guava", _sowing(9))
        assert sr.stage["stage_id"] == "post_monsoon"

    def test_pre_bloom_at_month_11(self):
        sr = get_stage("guava", _sowing(11))
        assert sr.stage["stage_id"] == "pre_bloom"

    def test_bloom_at_month_13(self):
        sr = get_stage("guava", _sowing(13))
        assert sr.stage["stage_id"] == "bloom_fruit_set"

    def test_fruit_development_at_month_15(self):
        sr = get_stage("guava", _sowing(15))
        assert sr.stage["stage_id"] == "fruit_development"

    def test_drought_stress_at_month_16(self):
        sr = get_stage("guava", _sowing(16))
        assert sr.stage["stage_id"] == "drought_stress"

    def test_harvest_at_month_17(self):
        sr = get_stage("guava", _sowing(17))
        assert sr.stage["stage_id"] == "harvest"
        assert sr.is_final_stage is True

    def test_post_harvest_at_month_20(self):
        sr = get_stage("guava", _sowing(20))
        assert sr.stage["stage_id"] == "post_harvest_mature"
        assert sr.is_final_stage is False

    def test_stage_boundary_exact_month_start(self):
        """At exactly month_start == 3 the stage should flip to vegetative_growth."""
        sr = get_stage("guava", _sowing(3))
        assert sr.stage["stage_id"] == "vegetative_growth"

    def test_future_sowing_date_raises_422(self):
        future = date.today() + timedelta(days=1)
        with pytest.raises(HTTPException) as exc_info:
            get_stage("guava", future)
        assert exc_info.value.status_code == 422

    def test_unknown_crop_raises_key_error(self):
        with pytest.raises(KeyError):
            get_stage("mango", date.today())

    def test_days_elapsed_positive(self):
        sowing = date.today() - timedelta(days=90)
        sr = get_stage("guava", sowing)
        assert sr.days_elapsed == 90

    def test_stage_result_type(self):
        sr = get_stage("guava", date.today())
        assert isinstance(sr, StageResult)
        assert isinstance(sr.stage, dict)
        assert "stage_id" in sr.stage
        assert "label" in sr.stage


class TestComputeCropAgeMonths:
    """Unit tests for the pure compute_crop_age_months function."""

    def test_same_day_is_zero(self):
        """Planting today → 0 months elapsed."""
        today = date(2024, 6, 15)
        assert compute_crop_age_months(today, today) == 0

    def test_one_month_same_day(self):
        """Exactly one calendar month later, same day-of-month → 1 month."""
        planting = date(2024, 1, 15)
        today = date(2024, 2, 15)
        assert compute_crop_age_months(planting, today) == 1

    def test_partial_month_floors_to_zero(self):
        """Less than a full month → 0 (floor behaviour)."""
        planting = date(2024, 1, 15)
        today = date(2024, 2, 10)  # 26 days later, day < planting day
        assert compute_crop_age_months(planting, today) == 0

    def test_day_before_planting_day_subtracts_one(self):
        """If today.day < planting_date.day, subtract one month."""
        planting = date(2024, 1, 20)
        today = date(2024, 3, 10)  # Feb→Mar, but day 10 < 20
        # Raw: (2024-2024)*12 + (3-1) = 2, then -1 because 10 < 20 → 1
        assert compute_crop_age_months(planting, today) == 1

    def test_exactly_one_year(self):
        """One year later, same day-of-month → 12 months."""
        planting = date(2023, 6, 15)
        today = date(2024, 6, 15)
        assert compute_crop_age_months(planting, today) == 12

    def test_crosses_year_boundary(self):
        """Planting in November, checking in February of next year."""
        planting = date(2023, 11, 20)
        today = date(2024, 2, 25)  # day 25 >= 20
        # (2024-2023)*12 + (2-11) = 12 - 9 = 3
        assert compute_crop_age_months(planting, today) == 3

    def test_crosses_year_boundary_with_floor(self):
        planting = date(2023, 11, 25)
        today = date(2024, 2, 20)  # day 20 < 25
        # (2024-2023)*12 + (2-11) = 3, then -1 → 2
        assert compute_crop_age_months(planting, today) == 2

    def test_consistent_with_get_stage(self):
        """compute_crop_age_months and get_stage agree on months_elapsed."""
        sowing = _sowing(5)
        sr = get_stage("guava", sowing)
        assert compute_crop_age_months(sowing, date.today()) == sr.months_elapsed

    def test_default_today_uses_timezone(self):
        """When today is None, the function resolves today in the given tz."""
        planting = date.today()
        # Should not raise; returns 0 for today's planting
        result = compute_crop_age_months(planting)
        assert result == 0

    def test_negative_when_today_before_planting(self):
        """A reference date before planting yields a negative result."""
        planting = date(2024, 6, 15)
        today = date(2024, 5, 15)
        assert compute_crop_age_months(planting, today) == -1

    def test_custom_timezone_string(self):
        """A custom timezone string is accepted without error."""
        planting = date(2024, 1, 1)
        today = date(2024, 7, 1)
        result = compute_crop_age_months(planting, today, timezone="UTC")
        assert result == 6
