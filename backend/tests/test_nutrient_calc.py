"""
test_nutrient_calc.py — Unit tests for services/nutrient_calc.py

Covers:
  - Hand-verified single-nutrient example: 100g target, grade=20 → 500.0g
  - Full floating-point precision retained until display rounding (12.6)
  - is_test_data flag set correctly for TEST_DATA source (12.9)
  - Each individual invalid input triggers ValueError naming the field (12.4, 12.5)
  - All inputs and intermediates echoed back (12.2)

Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.8, 12.9, 18.2
"""

import pytest

from services.nutrient_calc import (
    FORMULA_VERSION,
    NutrientInput,
    NutrientResult,
    compute_nutrient,
)


def _valid_input(**overrides) -> NutrientInput:
    """Return a valid NutrientInput with optional field overrides."""
    defaults = dict(
        target_g=100.0,
        selected_grade=20.0,
        source_record_id="",
    )
    defaults.update(overrides)
    return NutrientInput(**defaults)


# ---------------------------------------------------------------------------
# Hand-verified single-nutrient example (Requirement 12.1, 18.2)
# ---------------------------------------------------------------------------


class TestHandVerifiedExample:

    def test_100g_target_grade_20(self):
        """100g N target, grade=20 → declared_fraction=0.2, product_mass_g=500.0.

        declared_fraction = 20 / 100 = 0.2
        product_mass_g     = 100 / 0.2 = 500.0
        """
        result = compute_nutrient(_valid_input())

        assert result.declared_fraction == pytest.approx(0.2)
        assert result.product_mass_g == pytest.approx(500.0)

    def test_formula_version_echoed(self):
        result = compute_nutrient(_valid_input())
        assert result.formula_version == FORMULA_VERSION

    def test_all_inputs_echoed_back(self):
        """Requirement 12.2: all input values are echoed in the result."""
        inp = _valid_input()
        result = compute_nutrient(inp)

        assert result.target_g == inp.target_g
        assert result.selected_grade == inp.selected_grade

    def test_declared_fraction_present(self):
        """Requirement 12.2: the declared fraction is returned."""
        result = compute_nutrient(_valid_input())
        assert hasattr(result, "declared_fraction")
        assert result.declared_fraction == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# Full floating-point precision (Requirement 12.6)
# ---------------------------------------------------------------------------


class TestFloatingPointPrecision:

    def test_precision_retained_in_result(self):
        """Requirement 12.6: full precision retained in product_mass_g.

        Using values that produce a non-terminating decimal:
        target=10g, grade=3 → fraction=0.03, product=333.33333...
        """
        result = compute_nutrient(_valid_input(target_g=10.0, selected_grade=3.0))
        # 10 / 0.03 = 333.333...
        assert result.product_mass_g == pytest.approx(10.0 / 0.03)

    def test_round_trip_precision(self):
        """Requirement 12.8: product_mass × fraction ≈ target within 0.001g."""
        result = compute_nutrient(_valid_input(target_g=7.0, selected_grade=19.0))
        round_trip = result.product_mass_g * result.declared_fraction
        assert abs(round_trip - 7.0) < 0.001

    def test_large_target_precision(self):
        """Large targets should also maintain precision."""
        result = compute_nutrient(_valid_input(target_g=5000.0, selected_grade=50.0))
        assert result.product_mass_g == pytest.approx(10000.0)
        assert result.product_mass_g * result.declared_fraction == pytest.approx(5000.0)


# ---------------------------------------------------------------------------
# is_test_data flag (Requirement 12.9)
# ---------------------------------------------------------------------------


class TestTestDataFlag:

    def test_test_data_source_sets_flag_true(self):
        """source_record_id == 'TEST_DATA' → is_test_data=True."""
        result = compute_nutrient(_valid_input(source_record_id="TEST_DATA"))
        assert result.is_test_data is True

    def test_non_test_data_source_sets_flag_false(self):
        """Any other source_record_id → is_test_data=False."""
        result = compute_nutrient(_valid_input(source_record_id="REC-123"))
        assert result.is_test_data is False

    def test_empty_source_sets_flag_false(self):
        """Empty source → is_test_data=False."""
        result = compute_nutrient(_valid_input(source_record_id=""))
        assert result.is_test_data is False

    def test_test_data_exact_match_only(self):
        """Only the exact string 'TEST_DATA' sets the flag — case-sensitive."""
        result_lower = compute_nutrient(_valid_input(source_record_id="test_data"))
        assert result_lower.is_test_data is False

    def test_test_data_still_computes_correctly(self):
        """TEST_DATA flag does not alter the calculation."""
        result = compute_nutrient(_valid_input(
            target_g=100.0, selected_grade=20.0, source_record_id="TEST_DATA"
        ))
        assert result.product_mass_g == pytest.approx(500.0)
        assert result.is_test_data is True


# ---------------------------------------------------------------------------
# Invalid inputs: target_g (Requirement 12.5)
# ---------------------------------------------------------------------------


class TestInvalidTarget:

    @pytest.mark.parametrize("value", [0, -1.0, -0.001, -100.0])
    def test_zero_or_negative_target_raises(self, value):
        """Requirement 12.5: target <= 0 raises ValueError naming 'target_g'."""
        inp = _valid_input(target_g=value)
        with pytest.raises(ValueError, match="target_g"):
            compute_nutrient(inp)

    def test_invalid_target_named(self):
        with pytest.raises(ValueError, match="target_g"):
            compute_nutrient(_valid_input(target_g=0))


# ---------------------------------------------------------------------------
# Invalid inputs: selected_grade (Requirement 12.4)
# ---------------------------------------------------------------------------


class TestInvalidGrade:

    @pytest.mark.parametrize("value", [0, -1.0, -50.0])
    def test_zero_or_negative_grade_raises(self, value):
        """Requirement 12.4: grade <= 0 (declared_fraction <= 0) raises ValueError."""
        inp = _valid_input(selected_grade=value)
        with pytest.raises(ValueError, match="selected_grade"):
            compute_nutrient(inp)

    @pytest.mark.parametrize("value", [100.01, 101.0, 150.0, 200.0])
    def test_grade_above_100_raises(self, value):
        """Requirement 12.4: grade > 100 (declared_fraction > 1.0) raises ValueError."""
        inp = _valid_input(selected_grade=value)
        with pytest.raises(ValueError, match="selected_grade"):
            compute_nutrient(inp)

    def test_grade_100_is_valid(self):
        """100% grade → declared_fraction=1.0 is the upper bound and is valid."""
        result = compute_nutrient(_valid_input(selected_grade=100.0, target_g=50.0))
        assert result.declared_fraction == pytest.approx(1.0)
        assert result.product_mass_g == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Missing inputs return error, not a product mass (Requirement 12.5)
# ---------------------------------------------------------------------------


class TestMissingInputs:

    def test_missing_target_raises(self):
        """A missing required field must raise, not produce a product mass."""
        with pytest.raises(TypeError):
            compute_nutrient(NutrientInput(selected_grade=20.0))

    def test_missing_grade_raises(self):
        with pytest.raises(TypeError):
            compute_nutrient(NutrientInput(target_g=100.0))


# ---------------------------------------------------------------------------
# Realistic scenarios
# ---------------------------------------------------------------------------


class TestRealisticScenarios:

    def test_19_19_19_grade_n_component(self):
        """A 19-19-19 grade, computing the N component: target=50g, grade=19."""
        result = compute_nutrient(_valid_input(target_g=50.0, selected_grade=19.0))
        assert result.declared_fraction == pytest.approx(0.19)
        assert result.product_mass_g == pytest.approx(50.0 / 0.19)

    def test_low_grade_requires_more_product(self):
        """A lower grade means more product mass for the same target."""
        low = compute_nutrient(_valid_input(target_g=100.0, selected_grade=10.0))
        high = compute_nutrient(_valid_input(target_g=100.0, selected_grade=50.0))
        assert low.product_mass_g > high.product_mass_g

    def test_grade_equals_target_gives_unity(self):
        """If grade=100 (fraction=1.0), product_mass equals target."""
        result = compute_nutrient(_valid_input(target_g=75.0, selected_grade=100.0))
        assert result.product_mass_g == pytest.approx(75.0)

    def test_result_type_is_nutrient_result(self):
        result = compute_nutrient(_valid_input())
        assert isinstance(result, NutrientResult)
