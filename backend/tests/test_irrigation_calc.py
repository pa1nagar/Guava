"""
test_irrigation_calc.py — Unit tests for services/irrigation_calc.py

Covers:
  - Hand-verified input/output pair (Requirement 11.1, 11.6)
  - Each individual invalid input triggers ValueError naming the field (11.3)
  - system_efficiency boundary values (11.4)
  - Missing/zero/negative inputs return error, not a runtime value (11.3)
  - All inputs and intermediates are echoed back (11.2)

Requirements: 11.1, 11.2, 11.3, 11.4, 11.6, 18.1
"""

import pytest

from services.irrigation_calc import (
    FORMULA_VERSION,
    IrrigationInput,
    IrrigationResult,
    compute_irrigation,
)


def _valid_input(**overrides) -> IrrigationInput:
    """Return a valid IrrigationInput with optional field overrides."""
    defaults = dict(
        et0=5.0,
        kc=0.70,
        effective_area=6.0,
        system_efficiency=0.90,
        emitter_count=2,
        emitter_flow=4.0,
    )
    defaults.update(overrides)
    return IrrigationInput(**defaults)


# ---------------------------------------------------------------------------
# Hand-verified input/output pair (Requirement 11.1, 11.6, 18.1)
# ---------------------------------------------------------------------------


class TestHandVerifiedExample:

    def test_known_result(self):
        """ET0=5.0, Kc=0.70, area=6.0, eff=0.90, count=2, flow=4.0.

        net_water   = 5.0 × 0.70 × 6.0 = 21.0 L
        gross_water = 21.0 / 0.90 = 23.333... L
        total_flow  = 2 × 4.0 = 8.0 L/h
        runtime     = 23.333.../8.0 ≈ 2.9167 hours
        """
        result = compute_irrigation(_valid_input())

        assert result.net_water_litres == pytest.approx(21.0)
        assert result.gross_water_litres == pytest.approx(21.0 / 0.90)
        assert result.total_flow_litres_per_hour == pytest.approx(8.0)
        assert result.runtime_hours == pytest.approx(21.0 / 0.90 / 8.0)
        # Explicit check for the ≈ 2.917 value from the task spec.
        assert result.runtime_hours == pytest.approx(2.9166667, rel=1e-4)

    def test_formula_version_echoed(self):
        result = compute_irrigation(_valid_input())
        assert result.formula_version == FORMULA_VERSION

    def test_all_inputs_echoed_back(self):
        """Requirement 11.2: all input values are echoed in the result."""
        inp = _valid_input()
        result = compute_irrigation(inp)

        assert result.et0 == inp.et0
        assert result.kc == inp.kc
        assert result.effective_area == inp.effective_area
        assert result.system_efficiency == inp.system_efficiency
        assert result.emitter_count == inp.emitter_count
        assert result.emitter_flow == inp.emitter_flow

    def test_all_intermediates_present(self):
        """Requirement 11.2: all intermediate results are returned with units."""
        result = compute_irrigation(_valid_input())

        assert hasattr(result, "net_water_litres")
        assert hasattr(result, "gross_water_litres")
        assert hasattr(result, "total_flow_litres_per_hour")
        assert hasattr(result, "runtime_hours")


# ---------------------------------------------------------------------------
# Formula consistency (Requirement 11.6)
# ---------------------------------------------------------------------------


class TestFormulaConsistency:

    def test_runtime_equals_formula(self):
        """runtime = (ET0 × Kc × area / efficiency) / (count × flow) within 0.001 h."""
        result = compute_irrigation(_valid_input())
        expected = (5.0 * 0.70 * 6.0 / 0.90) / (2 * 4.0)
        assert abs(result.runtime_hours - expected) < 0.001

    def test_runtime_consistency_with_different_inputs(self):
        inp = _valid_input(et0=12.0, kc=1.2, effective_area=50.0,
                           system_efficiency=0.85, emitter_count=10, emitter_flow=8.0)
        result = compute_irrigation(inp)
        expected = (12.0 * 1.2 * 50.0 / 0.85) / (10 * 8.0)
        assert abs(result.runtime_hours - expected) < 0.001


# ---------------------------------------------------------------------------
# Invalid inputs: each field individually (Requirement 11.3)
# ---------------------------------------------------------------------------


class TestInvalidInputs:

    @pytest.mark.parametrize("field,value", [
        ("et0", 0),
        ("et0", -1.0),
        ("kc", 0),
        ("kc", -0.5),
        ("effective_area", 0),
        ("effective_area", -10.0),
        ("emitter_count", 0),
        ("emitter_count", -1),
        ("emitter_flow", 0),
        ("emitter_flow", -2.0),
    ])
    def test_zero_or_negative_raises_value_error(self, field, value):
        """Requirement 11.3: zero or negative required inputs raise ValueError."""
        inp = _valid_input(**{field: value})
        with pytest.raises(ValueError) as exc_info:
            compute_irrigation(inp)
        # The error message must name the offending field.
        assert field in str(exc_info.value)

    def test_invalid_et0_named(self):
        with pytest.raises(ValueError, match="et0"):
            compute_irrigation(_valid_input(et0=-5.0))

    def test_invalid_kc_named(self):
        with pytest.raises(ValueError, match="kc"):
            compute_irrigation(_valid_input(kc=0))

    def test_invalid_effective_area_named(self):
        with pytest.raises(ValueError, match="effective_area"):
            compute_irrigation(_valid_input(effective_area=-1.0))

    def test_invalid_emitter_count_named(self):
        with pytest.raises(ValueError, match="emitter_count"):
            compute_irrigation(_valid_input(emitter_count=0))

    def test_invalid_emitter_flow_named(self):
        with pytest.raises(ValueError, match="emitter_flow"):
            compute_irrigation(_valid_input(emitter_flow=-3.0))


# ---------------------------------------------------------------------------
# system_efficiency boundary (Requirement 11.4)
# ---------------------------------------------------------------------------


class TestSystemEfficiency:

    def test_efficiency_one_is_valid(self):
        """1.0 is the upper bound and must be accepted."""
        result = compute_irrigation(_valid_input(system_efficiency=1.0))
        assert result.runtime_hours > 0

    def test_efficiency_just_above_zero_is_valid(self):
        """A tiny positive efficiency is valid (within range)."""
        result = compute_irrigation(_valid_input(system_efficiency=0.01))
        assert result.runtime_hours > 0

    def test_efficiency_zero_rejected(self):
        """0 is rejected — must be greater than 0."""
        with pytest.raises(ValueError, match="system_efficiency"):
            compute_irrigation(_valid_input(system_efficiency=0))

    def test_efficiency_negative_rejected(self):
        with pytest.raises(ValueError, match="system_efficiency"):
            compute_irrigation(_valid_input(system_efficiency=-0.5))

    def test_efficiency_above_one_rejected(self):
        """> 1.0 is rejected — must be at most 1.0."""
        with pytest.raises(ValueError, match="system_efficiency"):
            compute_irrigation(_valid_input(system_efficiency=1.01))

    def test_efficiency_far_above_one_rejected(self):
        with pytest.raises(ValueError, match="system_efficiency"):
            compute_irrigation(_valid_input(system_efficiency=2.0))

    def test_efficiency_error_message_describes_range(self):
        """Requirement 11.4: message must state efficiency must be > 0 and <= 1.0."""
        with pytest.raises(ValueError) as exc_info:
            compute_irrigation(_valid_input(system_efficiency=1.5))
        msg = str(exc_info.value)
        assert "system_efficiency" in msg
        assert "1.0" in msg
        assert "0" in msg


# ---------------------------------------------------------------------------
# Missing inputs return error, not a runtime value (Requirement 11.3)
# ---------------------------------------------------------------------------


class TestMissingInputs:

    def test_missing_et0_raises(self):
        """A missing required field must raise, not produce a runtime."""
        with pytest.raises(TypeError):
            compute_irrigation(IrrigationInput(
                kc=0.7, effective_area=6.0, system_efficiency=0.9,
                emitter_count=2, emitter_flow=4.0,
            ))

    def test_missing_emitter_count_raises(self):
        with pytest.raises(TypeError):
            compute_irrigation(IrrigationInput(
                et0=5.0, kc=0.7, effective_area=6.0, system_efficiency=0.9,
                emitter_flow=4.0,
            ))


# ---------------------------------------------------------------------------
# Realistic field scenarios
# ---------------------------------------------------------------------------


class TestRealisticScenarios:

    def test_small_orchard(self):
        """Single emitter, small area."""
        result = compute_irrigation(_valid_input(
            et0=4.0, kc=0.50, effective_area=2.0,
            system_efficiency=0.95, emitter_count=1, emitter_flow=2.0,
        ))
        expected = (4.0 * 0.50 * 2.0 / 0.95) / (1 * 2.0)
        assert abs(result.runtime_hours - expected) < 0.001

    def test_large_farm(self):
        """Many emitters, large area."""
        result = compute_irrigation(_valid_input(
            et0=7.0, kc=1.0, effective_area=100.0,
            system_efficiency=0.85, emitter_count=500, emitter_flow=4.0,
        ))
        expected = (7.0 * 1.0 * 100.0 / 0.85) / (500 * 4.0)
        assert abs(result.runtime_hours - expected) < 0.001

    def test_net_water_equals_et0_times_kc_times_area(self):
        """Direct check of the net water intermediate (1mm × 1m² = 1L)."""
        result = compute_irrigation(_valid_input(et0=6.0, kc=0.8, effective_area=10.0))
        assert result.net_water_litres == pytest.approx(6.0 * 0.8 * 10.0)

    def test_gross_water_equals_net_divided_by_efficiency(self):
        result = compute_irrigation(_valid_input(system_efficiency=0.80))
        assert result.gross_water_litres == pytest.approx(
            result.net_water_litres / 0.80
        )

    def test_total_flow_equals_count_times_flow(self):
        result = compute_irrigation(_valid_input(emitter_count=6, emitter_flow=3.5))
        assert result.total_flow_litres_per_hour == pytest.approx(6 * 3.5)
