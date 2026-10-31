# Feature: smart-farmer-app, Property 15: Procurement calculator scaling invariant
# Feature: smart-farmer-app, Property 16: Procurement calculator rejects zero or negative references
"""
test_property_procurement_calc.py — Property-based tests for compute_procurement()

Property 15: Procurement calculator scaling invariant
    For any valid inputs (base_reference > 0 and target_reference > 0):
    scaled_quantity == base_quantity × (target_reference / base_reference).

Property 16: Procurement calculator rejects zero or negative references
    For base_reference <= 0 or target_reference <= 0, compute_procurement(inp)
    raises a ValueError with a message naming the offending field.

Uses Hypothesis with @given and @settings(max_examples=200).

Validates: Requirements 13.1, 13.3
"""

from hypothesis import given, settings
from hypothesis import strategies as st
import pytest

from services.procurement_calc import (
    FORMULA_VERSION,
    ProcurementInput,
    ProcurementResult,
    compute_procurement,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid ranges:
#   base_quantity:     any positive quantity (grams, litres, units, …)
#   base_reference:    > 0 (plant count or area for the reference scenario)
#   target_reference:  > 0 (farmer's own plant count or area)

valid_base_quantity_st = st.floats(
    min_value=0.001, max_value=1000000.0,
    allow_nan=False, allow_infinity=False,
)
valid_base_reference_st = st.floats(
    min_value=0.001, max_value=1000000.0,
    allow_nan=False, allow_infinity=False,
)
valid_target_reference_st = st.floats(
    min_value=0.001, max_value=1000000.0,
    allow_nan=False, allow_infinity=False,
)

valid_input_st = st.builds(
    ProcurementInput,
    base_quantity=valid_base_quantity_st,
    base_reference=valid_base_reference_st,
    target_reference=valid_target_reference_st,
)

# Invalid reference values: zero or negative.
invalid_reference_st = st.one_of(
    st.floats(
        min_value=-1000000.0, max_value=0.0,
        allow_nan=False, allow_infinity=False,
    ),
    st.just(0),
    st.just(-1.0),
)


# ---------------------------------------------------------------------------
# Property 15: Procurement calculator scaling invariant
# Validates: Requirements 13.1
# ---------------------------------------------------------------------------


# Feature: smart-farmer-app, Property 15: Procurement calculator scaling invariant
@given(
    base_quantity=valid_base_quantity_st,
    base_reference=valid_base_reference_st,
    target_reference=valid_target_reference_st,
)
@settings(max_examples=200)
def test_procurement_scaling_invariant(base_quantity, base_reference, target_reference):
    """For any valid inputs, scaled_quantity must equal
    base_quantity × (target_reference / base_reference).

    Validates: Requirements 13.1
    """
    inp = ProcurementInput(
        base_quantity=base_quantity,
        base_reference=base_reference,
        target_reference=target_reference,
    )
    result = compute_procurement(inp)

    expected = base_quantity * (target_reference / base_reference)
    assert result.scaled_quantity == pytest.approx(expected), (
        f"Scaling invariant violation: got {result.scaled_quantity}, "
        f"expected {expected}"
    )


# Feature: smart-farmer-app, Property 15: Procurement calculator scaling invariant
@given(inp=valid_input_st)
@settings(max_examples=200)
def test_procurement_inputs_echoed_back(inp: ProcurementInput):
    """All input values must be echoed back in the result (Requirement 13.2).

    Validates: Requirements 13.2
    """
    result = compute_procurement(inp)

    assert result.base_quantity == inp.base_quantity
    assert result.base_reference == inp.base_reference
    assert result.target_reference == inp.target_reference


# Feature: smart-farmer-app, Property 15: Procurement calculator scaling invariant
@given(inp=valid_input_st)
@settings(max_examples=200)
def test_procurement_result_type(inp: ProcurementInput):
    """compute_procurement must return a ProcurementResult for valid inputs.

    Validates: Requirements 13.1 — positive case ensuring the result is produced.
    """
    result = compute_procurement(inp)
    assert isinstance(result, ProcurementResult)


# Feature: smart-farmer-app, Property 15: Procurement calculator scaling invariant
@given(inp=valid_input_st)
@settings(max_examples=200)
def test_procurement_formula_version_echoed(inp: ProcurementInput):
    """The formula_version must be echoed back in the result.

    Validates: Requirements 13.1
    """
    result = compute_procurement(inp)
    assert result.formula_version == FORMULA_VERSION


# Feature: smart-farmer-app, Property 15: Procurement calculator scaling invariant
@given(inp=valid_input_st)
@settings(max_examples=200)
def test_procurement_valid_inputs_never_raise(inp: ProcurementInput):
    """Valid inputs within their stated ranges must never raise.

    Validates: Requirements 13.1 — positive case ensuring no over-rejection.
    """
    result = compute_procurement(inp)
    assert result.scaled_quantity > 0


# ---------------------------------------------------------------------------
# Property 16: Procurement calculator rejects zero or negative references
# Validates: Requirements 13.3
# ---------------------------------------------------------------------------


# Feature: smart-farmer-app, Property 16: Procurement calculator rejects zero or negative references
@given(
    base_quantity=valid_base_quantity_st,
    base_reference=invalid_reference_st,
    target_reference=valid_target_reference_st,
)
@settings(max_examples=200)
def test_invalid_base_reference_rejected(base_quantity, base_reference, target_reference):
    """base_reference <= 0 must raise ValueError naming 'base_reference'.

    Validates: Requirements 13.3
    """
    inp = ProcurementInput(
        base_quantity=base_quantity,
        base_reference=base_reference,
        target_reference=target_reference,
    )
    with pytest.raises(ValueError, match="base_reference"):
        compute_procurement(inp)


# Feature: smart-farmer-app, Property 16: Procurement calculator rejects zero or negative references
@given(
    base_quantity=valid_base_quantity_st,
    base_reference=valid_base_reference_st,
    target_reference=invalid_reference_st,
)
@settings(max_examples=200)
def test_invalid_target_reference_rejected(base_quantity, base_reference, target_reference):
    """target_reference <= 0 must raise ValueError naming 'target_reference'.

    Validates: Requirements 13.3
    """
    inp = ProcurementInput(
        base_quantity=base_quantity,
        base_reference=base_reference,
        target_reference=target_reference,
    )
    with pytest.raises(ValueError, match="target_reference"):
        compute_procurement(inp)


# Feature: smart-farmer-app, Property 16: Procurement calculator rejects zero or negative references
@given(
    base_quantity=valid_base_quantity_st,
    invalid_reference=invalid_reference_st,
)
@settings(max_examples=200)
def test_both_references_invalid_rejected(base_quantity, invalid_reference):
    """When both references are invalid, ValueError must still be raised.

    Validates: Requirements 13.3
    """
    inp = ProcurementInput(
        base_quantity=base_quantity,
        base_reference=invalid_reference,
        target_reference=invalid_reference,
    )
    with pytest.raises(ValueError):
        compute_procurement(inp)


# Feature: smart-farmer-app, Property 16: Procurement calculator rejects zero or negative references
@given(base_quantity=valid_base_quantity_st)
@settings(max_examples=200)
def test_base_reference_zero_rejected(base_quantity):
    """A base_reference of exactly zero must raise ValueError naming the field.

    Validates: Requirements 13.3
    """
    inp = ProcurementInput(
        base_quantity=base_quantity,
        base_reference=0,
        target_reference=100.0,
    )
    with pytest.raises(ValueError, match="base_reference"):
        compute_procurement(inp)


# Feature: smart-farmer-app, Property 16: Procurement calculator rejects zero or negative references
@given(base_quantity=valid_base_quantity_st)
@settings(max_examples=200)
def test_target_reference_zero_rejected(base_quantity):
    """A target_reference of exactly zero must raise ValueError naming the field.

    Validates: Requirements 13.3
    """
    inp = ProcurementInput(
        base_quantity=base_quantity,
        base_reference=100.0,
        target_reference=0,
    )
    with pytest.raises(ValueError, match="target_reference"):
        compute_procurement(inp)
