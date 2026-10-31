# Feature: smart-farmer-app, Property 4: Crop age computation from planting date
"""
test_property_crop_age.py — Property-based tests for compute_crop_age_months()

Validates Property 4: Crop age computation from planting date.

For any (planting_date, today) pair where today >= planting_date:
  - compute_crop_age_months returns a non-negative integer.
  - The result matches the floor-based calendar-month formula:
      months = (today.year - planting.year) * 12 + (today.month - planting.month)
      if today.day < planting.day: months -= 1

Universal property: the function is consistent, deterministic, and never
returns a negative value when today >= planting_date.

Uses Hypothesis with @given and @settings(max_examples=200).

Validates: Requirements 1.7, 4.6
"""

from datetime import date

from hypothesis import given, settings
from hypothesis import strategies as st

from services.stage import compute_crop_age_months

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Generate a planting date from 50 years ago to today.
planting_date_st = st.dates(
    min_value=date(1975, 1, 1),
    max_value=date.today(),
)


@st.composite
def planting_and_today_st(draw):
    """Generate a (planting_date, today) pair where today >= planting_date."""
    planting = draw(planting_date_st)
    today = draw(st.dates(min_value=planting, max_value=date(2075, 12, 31)))
    return planting, today


# ---------------------------------------------------------------------------
# Property 4a: Result is always non-negative when today >= planting_date
# ---------------------------------------------------------------------------


# Feature: smart-farmer-app, Property 4: Crop age computation from planting date
@given(pair=planting_and_today_st())
@settings(max_examples=200)
def test_crop_age_non_negative_for_past_planting(pair):
    """For any today >= planting_date, compute_crop_age_months must return >= 0.

    A farmer can never have a negative crop age — if the crop was planted today
    or in the past the age is zero or more.

    Validates: Requirements 1.7, 4.6
    """
    planting, today = pair
    assert today >= planting  # strategy invariant

    result = compute_crop_age_months(planting, today)
    assert result >= 0, (
        f"compute_crop_age_months returned negative {result} "
        f"for planting={planting}, today={today}"
    )


# ---------------------------------------------------------------------------
# Property 4b: Result matches the floor-based calendar-month formula exactly
# ---------------------------------------------------------------------------


# Feature: smart-farmer-app, Property 4: Crop age computation from planting date
@given(pair=planting_and_today_st())
@settings(max_examples=200)
def test_crop_age_matches_floor_formula(pair):
    """The returned value must equal the floor-based calendar-month formula.

    formula:
        months = (today.year - planting.year) * 12 + (today.month - planting.month)
        if today.day < planting.day: months -= 1

    This ensures the function is deterministic and consistent with its
    documented algorithm — no hidden rounding or timezone drift when
    ``today`` is supplied explicitly.

    Validates: Requirements 1.7, 4.6
    """
    planting, today = pair

    # Replicate the floor-month formula in the test.
    expected = (today.year - planting.year) * 12 + (today.month - planting.month)
    if today.day < planting.day:
        expected -= 1

    result = compute_crop_age_months(planting, today)
    assert result == expected, (
        f"compute_crop_age_months({planting}, {today}) = {result}, "
        f"expected {expected} from formula"
    )


# ---------------------------------------------------------------------------
# Property 4c: Same-day planting always yields zero months
# ---------------------------------------------------------------------------


# Feature: smart-farmer-app, Property 4: Crop age computation from planting date
@given(today=st.dates(min_value=date(1975, 1, 1), max_value=date(2075, 12, 31)))
@settings(max_examples=200)
def test_crop_age_same_day_is_zero(today: date):
    """When planting_date == today, the crop age is always zero.

    This is the boundary identity property: at the moment of planting the
    crop is exactly 0 months old.

    Validates: Requirements 1.7, 4.6
    """
    result = compute_crop_age_months(today, today)
    assert result == 0, (
        f"compute_crop_age_months({today}, {today}) = {result}, expected 0"
    )


# ---------------------------------------------------------------------------
# Property 4d: One full calendar month later (same day-of-month) yields exactly 1
# ---------------------------------------------------------------------------


# Feature: smart-farmer-app, Property 4: Crop age computation from planting date
@given(
    planting=st.dates(min_value=date(1975, 1, 1), max_value=date(2075, 11, 28)).filter(
        lambda d: d.day <= 28
    )
)
@settings(max_examples=200)
def test_crop_age_one_full_month_is_one(planting: date):
    """Adding exactly one calendar month yields 1 when the next month has the
    same day-of-month available (i.e. no short-month clamping needed).

    Only tests planting days 1–28 so that the same day always exists in
    the following month (February always has at least 28 days).

    Validates: Requirements 1.7, 4.6
    """
    # Advance one month, keeping the same day-of-month.
    next_month = planting.month + 1
    next_year = planting.year
    if next_month > 12:
        next_month -= 12
        next_year += 1

    # For days 1-28 the same day always exists in any month.
    one_month_later = date(next_year, next_month, planting.day)

    result = compute_crop_age_months(planting, one_month_later)
    assert result == 1, (
        f"compute_crop_age_months({planting}, {one_month_later}) = {result}, "
        f"expected 1 (exactly one calendar month later, same day-of-month)"
    )
