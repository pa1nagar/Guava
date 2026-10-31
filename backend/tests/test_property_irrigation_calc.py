# Feature: smart-farmer-app, Property 11: Irrigation calculator formula consistency
# Feature: smart-farmer-app, Property 12: Irrigation calculator rejects invalid inputs
"""
test_property_irrigation_calc.py — Property-based tests for compute_irrigation()

Property 11: Irrigation calculator formula consistency
    For any valid input tuple (ET0, Kc, area, efficiency, emitter_count, emitter_flow)
    within their stated ranges, the computed runtime_hours satisfies:
        runtime_hours × (emitter_count × emitter_flow) ≈ (ET0 × Kc × area / efficiency)
    within a tolerance of 0.001 hours.

Property 12: Irrigation calculator rejects invalid inputs
    For any input set where any required value is <= 0, is missing, or where
    system_efficiency > 1.0 or system_efficiency <= 0, compute_irrigation(inp)
    raises a ValueError with a message naming the invalid field.

Uses Hypothesis with @given and @settings(max_examples=200).

Validates: Requirements 11.1, 11.3, 11.4, 11.6
"""

from hypothesis import assume, given, settings
from hypothesis import strategies as st
import pytest

from services.irrigation_calc import IrrigationInput, compute_irrigation


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid ranges per Requirement 11.1:
#   et0:               0.01–25 mm/day
#   kc:                0.10–2.00
#   effective_area:    0.01–1000 m²
#   system_efficiency: (0, 1.0]
#   emitter_count:     1–10,000
#   emitter_flow:      0.1–100 L/hour

valid_et0_st = st.floats(min_value=0.01, max_value=25.0,
                         allow_nan=False, allow_infinity=False)
valid_kc_st = st.floats(min_value=0.10, max_value=2.00,
                        allow_nan=False, allow_infinity=False)
valid_area_st = st.floats(min_value=0.01, max_value=1000.0,
                           allow_nan=False, allow_infinity=False)
valid_efficiency_st = st.floats(min_value=0.01, max_value=1.0,
                                allow_nan=False, allow_infinity=False)
valid_count_st = st.integers(min_value=1, max_value=10_000)
valid_flow_st = st.floats(min_value=0.1, max_value=100.0,
                          allow_nan=False, allow_infinity=False)

valid_input_st = st.builds(
    IrrigationInput,
    et0=valid_et0_st,
    kc=valid_kc_st,
    effective_area=valid_area_st,
    system_efficiency=valid_efficiency_st,
    emitter_count=valid_count_st,
    emitter_flow=valid_flow_st,
)


# ---------------------------------------------------------------------------
# Property 11: Irrigation calculator formula consistency
# Validates: Requirements 11.1, 11.6
# ---------------------------------------------------------------------------


# Feature: smart-farmer-app, Property 11: Irrigation calculator formula consistency
@given(inp=valid_input_st)
@settings(max_examples=200)
def test_irrigation_formula_consistency(inp: IrrigationInput):
    """For any valid input, runtime_hours × (emitter_count × emitter_flow)
    must equal (ET0 × Kc × area / efficiency) within 0.001 hours tolerance.

    Validates: Requirements 11.1, 11.6
    """
    result = compute_irrigation(inp)

    lhs = result.runtime_hours * (inp.emitter_count * inp.emitter_flow)
    rhs = (inp.et0 * inp.kc * inp.effective_area / inp.system_efficiency)

    assert abs(lhs - rhs) < 0.001, (
        f"Formula inconsistency: runtime×flow={lhs}, "
        f"(ET0×Kc×area/eff)={rhs}, diff={abs(lhs - rhs)}"
    )


# Feature: smart-farmer-app, Property 11: Irrigation calculator formula consistency
@given(inp=valid_input_st)
@settings(max_examples=200)
def test_irrigation_intermediates_match_formula(inp: IrrigationInput):
    """Each intermediate must match its defining formula.

    Validates: Requirements 11.1
    """
    result = compute_irrigation(inp)

    assert result.net_water_litres == pytest.approx(inp.et0 * inp.kc * inp.effective_area)
    assert result.gross_water_litres == pytest.approx(
        result.net_water_litres / inp.system_efficiency
    )
    assert result.total_flow_litres_per_hour == pytest.approx(
        inp.emitter_count * inp.emitter_flow
    )
    assert result.runtime_hours == pytest.approx(
        result.gross_water_litres / result.total_flow_litres_per_hour
    )


# Feature: smart-farmer-app, Property 11: Irrigation calculator formula consistency
@given(inp=valid_input_st)
@settings(max_examples=200)
def test_irrigation_inputs_echoed_back(inp: IrrigationInput):
    """All input values must be echoed back in the result (Requirement 11.2).

    Validates: Requirements 11.2
    """
    result = compute_irrigation(inp)

    assert result.et0 == inp.et0
    assert result.kc == inp.kc
    assert result.effective_area == inp.effective_area
    assert result.system_efficiency == inp.system_efficiency
    assert result.emitter_count == inp.emitter_count
    assert result.emitter_flow == inp.emitter_flow


# ---------------------------------------------------------------------------
# Property 12: Irrigation calculator rejects invalid inputs
# Validates: Requirements 11.3, 11.4
# ---------------------------------------------------------------------------

# Strategies for invalid values (zero or negative).
invalid_float_st = st.one_of(
    st.floats(max_value=0.0, allow_nan=False, allow_infinity=False),
)
invalid_int_st = st.integers(max_value=0)


# Feature: smart-farmer-app, Property 12: Irrigation calculator rejects invalid inputs
@given(
    et0=invalid_float_st,
    kc=valid_kc_st,
    area=valid_area_st,
    eff=valid_efficiency_st,
    count=valid_count_st,
    flow=valid_flow_st,
)
@settings(max_examples=200)
def test_invalid_et0_rejected(et0, kc, area, eff, count, flow):
    """ET0 <= 0 must raise ValueError naming 'et0'.

    Validates: Requirements 11.3
    """
    inp = IrrigationInput(et0=et0, kc=kc, effective_area=area,
                          system_efficiency=eff, emitter_count=count,
                          emitter_flow=flow)
    with pytest.raises(ValueError, match="et0"):
        compute_irrigation(inp)


# Feature: smart-farmer-app, Property 12: Irrigation calculator rejects invalid inputs
@given(
    et0=valid_et0_st,
    kc=invalid_float_st,
    area=valid_area_st,
    eff=valid_efficiency_st,
    count=valid_count_st,
    flow=valid_flow_st,
)
@settings(max_examples=200)
def test_invalid_kc_rejected(et0, kc, area, eff, count, flow):
    """Kc <= 0 must raise ValueError naming 'kc'.

    Validates: Requirements 11.3
    """
    inp = IrrigationInput(et0=et0, kc=kc, effective_area=area,
                          system_efficiency=eff, emitter_count=count,
                          emitter_flow=flow)
    with pytest.raises(ValueError, match="kc"):
        compute_irrigation(inp)


# Feature: smart-farmer-app, Property 12: Irrigation calculator rejects invalid inputs
@given(
    et0=valid_et0_st,
    kc=valid_kc_st,
    area=invalid_float_st,
    eff=valid_efficiency_st,
    count=valid_count_st,
    flow=valid_flow_st,
)
@settings(max_examples=200)
def test_invalid_area_rejected(et0, kc, area, eff, count, flow):
    """effective_area <= 0 must raise ValueError naming 'effective_area'.

    Validates: Requirements 11.3
    """
    inp = IrrigationInput(et0=et0, kc=kc, effective_area=area,
                          system_efficiency=eff, emitter_count=count,
                          emitter_flow=flow)
    with pytest.raises(ValueError, match="effective_area"):
        compute_irrigation(inp)


# Feature: smart-farmer-app, Property 12: Irrigation calculator rejects invalid inputs
@given(
    et0=valid_et0_st,
    kc=valid_kc_st,
    area=valid_area_st,
    eff=valid_efficiency_st,
    count=invalid_int_st,
    flow=valid_flow_st,
)
@settings(max_examples=200)
def test_invalid_emitter_count_rejected(et0, kc, area, eff, count, flow):
    """emitter_count <= 0 must raise ValueError naming 'emitter_count'.

    Validates: Requirements 11.3
    """
    inp = IrrigationInput(et0=et0, kc=kc, effective_area=area,
                          system_efficiency=eff, emitter_count=count,
                          emitter_flow=flow)
    with pytest.raises(ValueError, match="emitter_count"):
        compute_irrigation(inp)


# Feature: smart-farmer-app, Property 12: Irrigation calculator rejects invalid inputs
@given(
    et0=valid_et0_st,
    kc=valid_kc_st,
    area=valid_area_st,
    eff=valid_efficiency_st,
    count=valid_count_st,
    flow=invalid_float_st,
)
@settings(max_examples=200)
def test_invalid_emitter_flow_rejected(et0, kc, area, eff, count, flow):
    """emitter_flow <= 0 must raise ValueError naming 'emitter_flow'.

    Validates: Requirements 11.3
    """
    inp = IrrigationInput(et0=et0, kc=kc, effective_area=area,
                          system_efficiency=eff, emitter_count=count,
                          emitter_flow=flow)
    with pytest.raises(ValueError, match="emitter_flow"):
        compute_irrigation(inp)


# Feature: smart-farmer-app, Property 12: Irrigation calculator rejects invalid inputs
@given(
    et0=valid_et0_st,
    kc=valid_kc_st,
    area=valid_area_st,
    # efficiency > 1.0 or <= 0
    eff=st.one_of(
        st.floats(min_value=1.0001, max_value=10.0, allow_nan=False, allow_infinity=False),
        st.floats(max_value=0.0, allow_nan=False, allow_infinity=False),
    ),
    count=valid_count_st,
    flow=valid_flow_st,
)
@settings(max_examples=200)
def test_invalid_system_efficiency_rejected(et0, kc, area, eff, count, flow):
    """system_efficiency > 1.0 or <= 0 must raise ValueError naming 'system_efficiency'.

    Validates: Requirements 11.4
    """
    inp = IrrigationInput(et0=et0, kc=kc, effective_area=area,
                          system_efficiency=eff, emitter_count=count,
                          emitter_flow=flow)
    with pytest.raises(ValueError, match="system_efficiency"):
        compute_irrigation(inp)


# Feature: smart-farmer-app, Property 12: Irrigation calculator rejects invalid inputs
@given(
    et0=valid_et0_st,
    kc=valid_kc_st,
    area=valid_area_st,
    eff=valid_efficiency_st,
    count=valid_count_st,
    flow=valid_flow_st,
)
@settings(max_examples=200)
def test_valid_inputs_never_raise(et0, kc, area, eff, count, flow):
    """Valid inputs within their stated ranges must never raise.

    Validates: Requirements 11.1 — positive case ensuring no over-rejection.
    """
    inp = IrrigationInput(et0=et0, kc=kc, effective_area=area,
                          system_efficiency=eff, emitter_count=count,
                          emitter_flow=flow)
    result = compute_irrigation(inp)
    assert result.runtime_hours > 0
