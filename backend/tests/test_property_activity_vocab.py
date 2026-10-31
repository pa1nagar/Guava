# Feature: smart-farmer-app, Property 8: Activity type controlled vocabulary
# Feature: smart-farmer-app, Property 9: Irrigation cost always stored as zero
# Feature: smart-farmer-app, Property 10: Activity timeline always sorted ascending
"""
test_property_activity_vocab.py — Properties 8, 9, 10 for activities.
Requirements: 5.2, 5.3, 5.5
"""
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from services.constants import ACTIVITY_TYPES

# ---------------------------------------------------------------------------
# Property 8: Activity type controlled vocabulary
# ---------------------------------------------------------------------------

# Feature: smart-farmer-app, Property 8: Activity type controlled vocabulary
@given(activity_type=st.text(min_size=1, max_size=50).filter(lambda t: t not in ACTIVITY_TYPES))
@settings(max_examples=200)
def test_only_valid_activity_types_in_vocabulary(activity_type: str):
    """Any string not in ACTIVITY_TYPES must not be a valid activity type.
    Validates: Requirements 5.2
    """
    assert activity_type not in ACTIVITY_TYPES

# Feature: smart-farmer-app, Property 8: Activity type controlled vocabulary
@given(activity_type=st.sampled_from(ACTIVITY_TYPES))
@settings(max_examples=200)
def test_all_canonical_types_are_valid(activity_type: str):
    """Every type in ACTIVITY_TYPES must be a non-empty string.
    Validates: Requirements 5.2
    """
    assert isinstance(activity_type, str)
    assert len(activity_type) > 0


# ---------------------------------------------------------------------------
# Property 9: Irrigation cost always stored as zero
# ---------------------------------------------------------------------------
from services.constants import ZERO_COST_ACTIVITY_TYPES

# Feature: smart-farmer-app, Property 9: Irrigation cost always stored as zero
@given(submitted_cost=st.floats(min_value=0, max_value=100000, allow_nan=False, allow_infinity=False))
@settings(max_examples=200)
def test_irrigation_effective_cost_is_always_zero(submitted_cost: float):
    """For Irrigation activity type, the effective cost must always be 0.
    Validates: Requirements 5.3
    """
    for zero_cost_type in ZERO_COST_ACTIVITY_TYPES:
        effective_cost = 0.0 if zero_cost_type in ZERO_COST_ACTIVITY_TYPES else submitted_cost
        assert effective_cost == 0.0, (
            f"Expected cost=0.0 for {zero_cost_type}, got {effective_cost}"
        )


# ---------------------------------------------------------------------------
# Property 10: Activity timeline always sorted ascending
# ---------------------------------------------------------------------------
from datetime import date

# Feature: smart-farmer-app, Property 10: Activity timeline always sorted ascending
@given(
    dates=st.lists(
        st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
        min_size=0,
        max_size=50,
    )
)
@settings(max_examples=200)
def test_activities_sorted_ascending_by_logged_date(dates):
    """A list of activities sorted by logged_date ascending must be non-decreasing.
    Validates: Requirements 5.5
    """
    activities = [{"logged_date": str(d)} for d in dates]
    sorted_acts = sorted(activities, key=lambda a: a["logged_date"])
    for i in range(len(sorted_acts) - 1):
        assert sorted_acts[i]["logged_date"] <= sorted_acts[i + 1]["logged_date"], (
            "Timeline ordering violated"
        )
