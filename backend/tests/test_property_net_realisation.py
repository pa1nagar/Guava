# Feature: smart-farmer-app, Property 17: Net realisation equals gross sales minus deductions
"""
test_property_net_realisation.py — Property-based test for net_realisation().

Validates Property 17: For any harvest record with gross_sales >= 0 and any
list of deductions [d1, d2, ...] where all di >= 0: net_realisation equals
gross_sales minus sum(deductions) exactly (no double-counting).

Uses Hypothesis with @given and @settings(max_examples=200).

Validates: Requirements 9.2
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from services.financials import net_realisation

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Gross sales is non-negative (a sale cannot have negative revenue).
gross_sales_st = st.floats(
    min_value=0,
    max_value=10_000_000,
    allow_nan=False,
    allow_infinity=False,
)

# Each individual deduction is non-negative (deductions reduce, never add).
single_deduction_st = st.floats(
    min_value=0,
    max_value=1_000_000,
    allow_nan=False,
    allow_infinity=False,
)

# A list of 0–10 deductions representing mandi commission, transport, packaging, etc.
deductions_list_st = st.lists(
    single_deduction_st,
    min_size=0,
    max_size=10,
)


# ---------------------------------------------------------------------------
# Property 17: net_realisation == gross_sales - sum(deductions) exactly
# ---------------------------------------------------------------------------

# Feature: smart-farmer-app, Property 17: Net realisation equals gross sales minus deductions
@given(gross_sales=gross_sales_st, deductions_list=deductions_list_st)
@settings(max_examples=200)
def test_net_realisation_equals_gross_minus_sum_of_deductions(
    gross_sales: float, deductions_list: list
):
    """For any gross_sales >= 0 and any list of deductions [d1, d2, ...] where
    all di >= 0: net_realisation == gross_sales - sum(deductions) exactly.

    This is the core financial invariant: the farmer's net realisation is
    gross sales minus every stated deduction, with no double-counting.

    Validates: Requirements 9.2
    """
    total_deductions = sum(deductions_list)
    result = net_realisation(gross_sales, total_deductions)
    expected = gross_sales - total_deductions
    assert result == expected, (
        f"net_realisation({gross_sales}, {total_deductions}) = {result}, "
        f"expected {expected} (gross_sales - sum(deductions))"
    )
