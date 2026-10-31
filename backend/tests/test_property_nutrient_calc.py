# Feature: smart-farmer-app, Property 13: Nutrient calculator mass balance (round-trip)
# Feature: smart-farmer-app, Property 14: Nutrient calculator rejects invalid inputs
"""
test_property_nutrient_calc.py — Property-based tests for compute_nutrient()

Property 13: Nutrient calculator mass balance (round-trip)
    For any valid nutrient target T > 0 and declared fraction f where 0 < f <= 1:
    the computed product_mass_g × f ≈ T within a tolerance of 0.001 grams.

Property 14: Nutrient calculator rejects invalid inputs
    For any target <= 0 or declared_fraction not in (0, 1], compute_nutrient(inp)
    raises a ValueError with a message naming the invalid field.

Uses Hypothesis with @given and @settings(max_examples=200).

Validates: Requirements 12.1, 12.4, 12.5, 12.8
"""

from hypothesis import given, settings
from hypothesis import strategies as st
import pytest

from services.nutrient_calc import NutrientInput, compute_nutrient


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid ranges:
#   target_g:        > 0 (grams of nutrient element)
#   selected_grade:  (0, 100] (integer percentage of the selected nutrient)

valid_target_st = st.floats(
    min_value=0.001, max_value=10000.0,
    allow_nan=False, allow_infinity=False,
)
valid_grade_st = st.integers(min_value=1, max_value=100)

valid_input_st = st.builds(
    NutrientInput,
    target_g=valid_target_st,
    selected_grade=st.floats(
        min_value=1.0, max_value=100.0,
        allow_nan=False, allow_infinity=False,
    ),
    source_record_id=st.sampled_from(["", "TEST_DATA", "REC-001"]),
)


# ---------------------------------------------------------------------------
# Property 13: Nutrient calculator mass balance (round-trip)
# Validates: Requirements 12.1, 12.8
# ---------------------------------------------------------------------------


# Feature: smart-farmer-app, Property 13: Nutrient calculator mass balance (round-trip)
@given(
    target=valid_target_st,
    grade=valid_grade_st,
)
@settings(max_examples=200)
def test_nutrient_mass_balance(target, grade):
    """For any valid target T > 0 and declared fraction f in (0, 1],
    product_mass_g × f must equal T within 0.001g tolerance.

    Validates: Requirements 12.1, 12.8
    """
    inp = NutrientInput(target_g=target, selected_grade=float(grade))
    result = compute_nutrient(inp)

    fraction = grade / 100.0
    round_trip = result.product_mass_g * fraction

    assert abs(round_trip - target) < 0.001, (
        f"Mass balance violation: product_mass×fraction={round_trip}, "
        f"target={target}, diff={abs(round_trip - target)}"
    )


# Feature: smart-farmer-app, Property 13: Nutrient calculator mass balance (round-trip)
@given(inp=valid_input_st)
@settings(max_examples=200)
def test_nutrient_inputs_echoed_back(inp: NutrientInput):
    """All input values must be echoed back in the result (Requirement 12.2).

    Validates: Requirements 12.2
    """
    result = compute_nutrient(inp)

    assert result.target_g == inp.target_g
    assert result.selected_grade == inp.selected_grade


# Feature: smart-farmer-app, Property 13: Nutrient calculator mass balance (round-trip)
@given(inp=valid_input_st)
@settings(max_examples=200)
def test_nutrient_declared_fraction_matches_grade(inp: NutrientInput):
    """declared_fraction must equal selected_grade / 100 (Requirement 12.3).

    Validates: Requirements 12.3
    """
    result = compute_nutrient(inp)

    assert result.declared_fraction == pytest.approx(inp.selected_grade / 100.0)


# Feature: smart-farmer-app, Property 13: Nutrient calculator mass balance (round-trip)
@given(inp=valid_input_st)
@settings(max_examples=200)
def test_nutrient_product_mass_matches_formula(inp: NutrientInput):
    """product_mass_g must equal target_g / declared_fraction (Requirement 12.1).

    Validates: Requirements 12.1
    """
    result = compute_nutrient(inp)

    expected = inp.target_g / (inp.selected_grade / 100.0)
    assert result.product_mass_g == pytest.approx(expected)


# Feature: smart-farmer-app, Property 13: Nutrient calculator mass balance (round-trip)
@given(inp=valid_input_st)
@settings(max_examples=200)
def test_nutrient_valid_inputs_never_raise(inp: NutrientInput):
    """Valid inputs within their stated ranges must never raise.

    Validates: Requirements 12.1 — positive case ensuring no over-rejection.
    """
    result = compute_nutrient(inp)
    assert result.product_mass_g > 0


# ---------------------------------------------------------------------------
# Property 14: Nutrient calculator rejects invalid inputs
# Validates: Requirements 12.4, 12.5
# ---------------------------------------------------------------------------

# Strategies for invalid values.
invalid_target_st = st.one_of(
    st.floats(max_value=0.0, allow_nan=False, allow_infinity=False),
)
invalid_grade_low_st = st.one_of(
    st.floats(max_value=0.0, allow_nan=False, allow_infinity=False),
)
invalid_grade_high_st = st.floats(
    min_value=100.0001, max_value=10000.0,
    allow_nan=False, allow_infinity=False,
)


# Feature: smart-farmer-app, Property 14: Nutrient calculator rejects invalid inputs
@given(
    target=invalid_target_st,
    grade=st.floats(min_value=1.0, max_value=100.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_invalid_target_rejected(target, grade):
    """target_g <= 0 must raise ValueError naming 'target_g'.

    Validates: Requirements 12.5
    """
    inp = NutrientInput(target_g=target, selected_grade=grade)
    with pytest.raises(ValueError, match="target_g"):
        compute_nutrient(inp)


# Feature: smart-farmer-app, Property 14: Nutrient calculator rejects invalid inputs
@given(
    target=valid_target_st,
    grade=invalid_grade_low_st,
)
@settings(max_examples=200)
def test_invalid_grade_low_rejected(target, grade):
    """selected_grade <= 0 (declared_fraction <= 0) must raise ValueError
    naming 'selected_grade'.

    Validates: Requirements 12.4
    """
    inp = NutrientInput(target_g=target, selected_grade=grade)
    with pytest.raises(ValueError, match="selected_grade"):
        compute_nutrient(inp)


# Feature: smart-farmer-app, Property 14: Nutrient calculator rejects invalid inputs
@given(
    target=valid_target_st,
    grade=invalid_grade_high_st,
)
@settings(max_examples=200)
def test_invalid_grade_high_rejected(target, grade):
    """selected_grade > 100 (declared_fraction > 1.0) must raise ValueError
    naming 'selected_grade'.

    Validates: Requirements 12.4
    """
    inp = NutrientInput(target_g=target, selected_grade=grade)
    with pytest.raises(ValueError, match="selected_grade"):
        compute_nutrient(inp)


# Feature: smart-farmer-app, Property 14: Nutrient calculator rejects invalid inputs
@given(
    target=invalid_target_st,
    grade=invalid_grade_low_st,
)
@settings(max_examples=200)
def test_both_invalid_rejected(target, grade):
    """When both target and grade are invalid, ValueError must still be raised.

    Validates: Requirements 12.4, 12.5
    """
    inp = NutrientInput(target_g=target, selected_grade=grade)
    with pytest.raises(ValueError):
        compute_nutrient(inp)
