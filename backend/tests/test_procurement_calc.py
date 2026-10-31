"""
test_procurement_calc.py — Unit tests for services/procurement_calc.py

Covers:
  - Hand-verified scale-up input/output pair (Requirement 13.1, 18.2)
  - Hand-verified scale-down input/output pair (Requirement 13.1, 18.2)
  - Invalid inputs raise ValueError naming the offending field (13.3)
  - All inputs echoed back in the result (Requirement 13.2)
  - scaled_quantity_rounded rounded to 2 decimal places (Requirement 13.2)

Requirements: 13.1, 13.2, 13.3, 18.2
"""

import pytest

from services.procurement_calc import (
    FORMULA_VERSION,
    ProcurementInput,
    ProcurementResult,
    compute_procurement,
)


def _valid_input(**overrides) -> ProcurementInput:
    """Return a valid ProcurementInput with optional field overrides."""
    defaults = dict(
        base_quantity=10.0,
        base_reference=100.0,
        target_reference=2100.0,
    )
    defaults.update(overrides)
    return ProcurementInput(**defaults)


# ---------------------------------------------------------------------------
# Hand-verified examples (Requirement 13.1, 18.2)
# ---------------------------------------------------------------------------


class TestHandVerifiedExamples:

    def test_scale_up_known_result(self):
        """base_qty=10, base_ref=100, target_ref=2100 → scaled=210.0

        scaled_quantity = 10 × (2100 / 100) = 210.0
        """
        result = compute_procurement(_valid_input())

        assert result.scaled_quantity == pytest.approx(210.0)
        assert result.scaled_quantity_rounded == pytest.approx(210.0)

    def test_scale_down_known_result(self):
        """base_qty=210, base_ref=2100, target_ref=100 → scaled=10.0

        scaled_quantity = 210 × (100 / 2100) = 10.0
        """
        result = compute_procurement(_valid_input(
            base_quantity=210.0,
            base_reference=2100.0,
            target_reference=100.0,
        ))

        assert result.scaled_quantity == pytest.approx(10.0)
        assert result.scaled_quantity_rounded == pytest.approx(10.0)

    def test_formula_version_echoed(self):
        result = compute_procurement(_valid_input())
        assert result.formula_version == FORMULA_VERSION


# ---------------------------------------------------------------------------
# Formula consistency (Requirement 13.1)
# ---------------------------------------------------------------------------


class TestFormulaConsistency:

    def test_scaled_quantity_equals_formula(self):
        """scaled_quantity must equal base_quantity × (target_reference / base_reference)."""
        result = compute_procurement(_valid_input())
        expected = 10.0 * (2100.0 / 100.0)
        assert abs(result.scaled_quantity - expected) < 0.001

    def test_scaled_quantity_consistency_with_different_inputs(self):
        inp = _valid_input(
            base_quantity=50.0,
            base_reference=250.0,
            target_reference=5000.0,
        )
        result = compute_procurement(inp)
        expected = 50.0 * (5000.0 / 250.0)
        assert abs(result.scaled_quantity - expected) < 0.001

    def test_equal_references_yield_base_quantity(self):
        """When target_reference == base_reference, scaled_quantity == base_quantity."""
        result = compute_procurement(_valid_input(
            base_quantity=42.5,
            base_reference=300.0,
            target_reference=300.0,
        ))
        assert result.scaled_quantity == pytest.approx(42.5)


# ---------------------------------------------------------------------------
# All inputs echoed back (Requirement 13.2)
# ---------------------------------------------------------------------------


class TestInputsEchoed:

    def test_all_inputs_echoed_back(self):
        """Requirement 13.2: all input values are echoed in the result."""
        inp = _valid_input(
            base_quantity=15.0,
            base_reference=200.0,
            target_reference=800.0,
        )
        result = compute_procurement(inp)

        assert result.base_quantity == inp.base_quantity
        assert result.base_reference == inp.base_reference
        assert result.target_reference == inp.target_reference


# ---------------------------------------------------------------------------
# Rounding to purchase unit (Requirement 13.2)
# ---------------------------------------------------------------------------


class TestRounding:

    def test_scaled_quantity_rounded_to_two_decimals(self):
        """scaled_quantity_rounded must be rounded to 2 decimal places.

        Using inputs that produce an irrational-looking result:
        base_qty=1, base_ref=3, target_ref=10 → 10/3 = 3.3333...
        rounded to 2 dp → 3.33
        """
        result = compute_procurement(_valid_input(
            base_quantity=1.0,
            base_reference=3.0,
            target_reference=10.0,
        ))
        assert result.scaled_quantity == pytest.approx(10.0 / 3.0)
        assert result.scaled_quantity_rounded == pytest.approx(3.33)

    def test_scaled_quantity_full_precision_retained(self):
        """scaled_quantity retains full floating-point precision (Requirement 13.2)."""
        result = compute_procurement(_valid_input(
            base_quantity=1.0,
            base_reference=7.0,
            target_reference=22.0,
        ))
        # 22/7 is a repeating decimal; full precision must be retained.
        assert result.scaled_quantity == pytest.approx(22.0 / 7.0)
        assert result.scaled_quantity_rounded == round(22.0 / 7.0, 2)

    def test_rounded_value_matches_round_function(self):
        """scaled_quantity_rounded must equal round(scaled_quantity, 2)."""
        result = compute_procurement(_valid_input(
            base_quantity=33.0,
            base_reference=99.0,
            target_reference=7.0,
        ))
        expected_rounded = round(result.scaled_quantity, 2)
        assert result.scaled_quantity_rounded == pytest.approx(expected_rounded)


# ---------------------------------------------------------------------------
# Invalid inputs: each reference field individually (Requirement 13.3)
# ---------------------------------------------------------------------------


class TestInvalidInputs:

    @pytest.mark.parametrize("value", [0, -1.0, -100.0, -0.001])
    def test_base_reference_zero_or_negative_raises(self, value):
        """Requirement 13.3: base_reference <= 0 raises ValueError."""
        inp = _valid_input(base_reference=value)
        with pytest.raises(ValueError) as exc_info:
            compute_procurement(inp)
        assert "base_reference" in str(exc_info.value)

    @pytest.mark.parametrize("value", [0, -1.0, -100.0, -0.001])
    def test_target_reference_zero_or_negative_raises(self, value):
        """Requirement 13.3: target_reference <= 0 raises ValueError."""
        inp = _valid_input(target_reference=value)
        with pytest.raises(ValueError) as exc_info:
            compute_procurement(inp)
        assert "target_reference" in str(exc_info.value)

    def test_invalid_base_reference_named(self):
        with pytest.raises(ValueError, match="base_reference"):
            compute_procurement(_valid_input(base_reference=0))

    def test_invalid_base_reference_negative_named(self):
        with pytest.raises(ValueError, match="base_reference"):
            compute_procurement(_valid_input(base_reference=-5.0))

    def test_invalid_target_reference_named(self):
        with pytest.raises(ValueError, match="target_reference"):
            compute_procurement(_valid_input(target_reference=0))

    def test_invalid_target_reference_negative_named(self):
        with pytest.raises(ValueError, match="target_reference"):
            compute_procurement(_valid_input(target_reference=-50.0))

    def test_both_references_invalid_raises(self):
        """When both references are invalid, ValueError must still be raised."""
        with pytest.raises(ValueError):
            compute_procurement(_valid_input(base_reference=0, target_reference=0))

    def test_error_for_base_reference_mentions_greater_than_zero(self):
        """The error message should explain that the reference must be > 0."""
        with pytest.raises(ValueError) as exc_info:
            compute_procurement(_valid_input(base_reference=-10.0))
        msg = str(exc_info.value)
        assert "base_reference" in msg
        assert "0" in msg


# ---------------------------------------------------------------------------
# Missing inputs return error, not a scaled value (Requirement 13.3)
# ---------------------------------------------------------------------------


class TestMissingInputs:

    def test_missing_base_reference_raises(self):
        """A missing required field must raise, not produce a scaled quantity."""
        with pytest.raises(TypeError):
            compute_procurement(ProcurementInput(
                base_quantity=10.0,
                target_reference=2100.0,
            ))

    def test_missing_target_reference_raises(self):
        with pytest.raises(TypeError):
            compute_procurement(ProcurementInput(
                base_quantity=10.0,
                base_reference=100.0,
            ))

    def test_missing_base_quantity_raises(self):
        with pytest.raises(TypeError):
            compute_procurement(ProcurementInput(
                base_reference=100.0,
                target_reference=2100.0,
            ))


# ---------------------------------------------------------------------------
# Realistic field scenarios
# ---------------------------------------------------------------------------


class TestRealisticScenarios:

    def test_plant_count_scaling(self):
        """Scale from a reference orchard (100 plants) to farmer's orchard (2100 plants).

        base_qty=5 kg of fertilizer per 100 plants → 105 kg for 2100 plants.
        """
        result = compute_procurement(_valid_input(
            base_quantity=5.0,
            base_reference=100.0,
            target_reference=2100.0,
        ))
        assert result.scaled_quantity == pytest.approx(105.0)
        assert result.scaled_quantity_rounded == pytest.approx(105.0)

    def test_area_based_scaling(self):
        """Scale by area: 10 litres per acre reference → 25 litres for 2.5 acres."""
        result = compute_procurement(_valid_input(
            base_quantity=10.0,
            base_reference=1.0,
            target_reference=2.5,
        ))
        assert result.scaled_quantity == pytest.approx(25.0)

    def test_fractional_scale_down(self):
        """Scale from 2100 plants down to a single plant."""
        result = compute_procurement(_valid_input(
            base_quantity=2100.0,
            base_reference=2100.0,
            target_reference=1.0,
        ))
        assert result.scaled_quantity == pytest.approx(1.0)
