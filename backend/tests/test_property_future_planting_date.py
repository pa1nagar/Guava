# Feature: smart-farmer-app, Property 5: Future planting date always rejected
"""
test_property_future_planting_date.py — Property-based test for future planting
date rejection.

Validates Property 5: For any planting_date where planting_date > date.today(),
calling _check_planting_date() (or submitting to the plot creation endpoint) must
raise HTTPException with status_code=422.

Uses Hypothesis with @given and @settings(max_examples=200).

Validates: Requirements 4.5
"""

from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from hypothesis import given, settings
from hypothesis import strategies as st

from routers.farms import _check_planting_date

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Generate any date strictly in the future (1 day to ~10 years ahead).
future_date_st = st.integers(min_value=1, max_value=3650).map(
    lambda days_ahead: date.today() + timedelta(days=days_ahead)
)

# Generate any date that is today or in the past (0 to ~50 years back).
past_or_today_date_st = st.integers(min_value=0, max_value=18250).map(
    lambda days_back: date.today() - timedelta(days=days_back)
)


# ---------------------------------------------------------------------------
# Property 5a: Any future planting date is rejected with HTTP 422
# ---------------------------------------------------------------------------

# Feature: smart-farmer-app, Property 5: Future planting date always rejected
@given(future_date=future_date_st)
@settings(max_examples=200)
def test_future_planting_date_always_rejected(future_date: date):
    """For any planting_date strictly after today, _check_planting_date must
    raise HTTPException(status_code=422).

    This is a universal property: no future date should ever be accepted,
    regardless of how far ahead it is.

    Validates: Requirements 4.5
    """
    assert future_date > date.today(), (
        f"Strategy bug: generated date {future_date} is not in the future."
    )

    with pytest.raises(HTTPException) as exc_info:
        _check_planting_date(future_date)

    assert exc_info.value.status_code == 422, (
        f"Expected 422 for future date {future_date}, "
        f"got {exc_info.value.status_code}."
    )
    # The error message must be human-readable (mention "future" or equivalent).
    assert exc_info.value.detail, (
        f"Expected a non-empty detail message for rejected future date {future_date}."
    )


# ---------------------------------------------------------------------------
# Property 5b: Today's date and all past dates are accepted (negative/positive case)
# ---------------------------------------------------------------------------

# Feature: smart-farmer-app, Property 5: Future planting date always rejected
@given(past_or_today_date=past_or_today_date_st)
@settings(max_examples=200)
def test_past_and_today_planting_date_always_accepted(past_or_today_date: date):
    """For any planting_date on or before today, _check_planting_date must NOT
    raise an exception.

    Ensures the validator does not over-block valid historical planting dates.

    Validates: Requirements 4.5
    """
    assert past_or_today_date <= date.today(), (
        f"Strategy bug: generated date {past_or_today_date} is in the future."
    )

    # Should not raise — any past/today date is valid.
    try:
        _check_planting_date(past_or_today_date)
    except HTTPException as exc:
        pytest.fail(
            f"_check_planting_date raised HTTPException({exc.status_code}) "
            f"for valid date {past_or_today_date}: {exc.detail}"
        )
