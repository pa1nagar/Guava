"""
test_scaling.py — Tests for services/scaling.py

Covers:
  - scale_quantity basic arithmetic
  - scale_quantity edge cases (zero, large numbers)
  - scale_quantity negative values raise ValueError
  - scale_stage_quantities returns correct totals
  - scale_stage_quantities with zero irrigation stage (drought)
  - unit conversion: grams → kg
"""

import pytest
from services.scaling import scale_quantity, scale_stage_quantities


class TestScaleQuantity:

    def test_basic_multiplication(self):
        assert scale_quantity(50.0, 2100) == pytest.approx(105000.0)

    def test_zero_reference(self):
        assert scale_quantity(0.0, 2100) == 0.0

    def test_zero_plant_count(self):
        assert scale_quantity(5.0, 0) == 0.0

    def test_single_plant(self):
        assert scale_quantity(7.0, 1) == 7.0

    def test_negative_quantity_raises(self):
        with pytest.raises(ValueError):
            scale_quantity(-1.0, 100)

    def test_negative_plant_count_raises(self):
        with pytest.raises(ValueError):
            scale_quantity(5.0, -1)

    def test_fractional_reference(self):
        result = scale_quantity(0.005, 2100)
        assert result == pytest.approx(10.5)


class TestScaleStageQuantities:

    def _make_stage(self, irr_lpd, fert_gpw, fert_name="Test WSF"):
        return {
            "quantities": {
                "irrigation_litres_per_plant_per_day": irr_lpd,
                "fertilizer_grams_per_plant_per_week": fert_gpw,
                "fertilizer_name": fert_name,
                "fertilizer_type": "Fertilizer",
            }
        }

    def test_establishment_stage_2100_plants(self):
        stage = self._make_stage(3, 5)
        result = scale_stage_quantities(stage, 2100)
        assert result["total_irrigation_litres_per_day"] == pytest.approx(6300.0)
        assert result["total_fertilizer_grams_per_week"] == pytest.approx(10500.0)
        assert result["total_fertilizer_kg_per_week"] == pytest.approx(10.5)

    def test_vegetative_growth_2100_plants(self):
        stage = self._make_stage(4, 7)
        result = scale_stage_quantities(stage, 2100)
        assert result["total_irrigation_litres_per_day"] == pytest.approx(8400.0)
        assert result["total_fertilizer_kg_per_week"] == pytest.approx(14.7)

    def test_drought_stress_zero_values(self):
        stage = self._make_stage(0, 0, "None — drought stress period")
        result = scale_stage_quantities(stage, 2100)
        assert result["total_irrigation_litres_per_day"] == 0.0
        assert result["total_fertilizer_kg_per_week"] == 0.0

    def test_plant_count_in_result(self):
        stage = self._make_stage(3, 5)
        result = scale_stage_quantities(stage, 500)
        assert result["plant_count"] == 500

    def test_per_plant_fields_preserved(self):
        stage = self._make_stage(14, 13)
        result = scale_stage_quantities(stage, 2100)
        assert result["per_plant_irrigation_lpd"] == 14
        assert result["per_plant_fertilizer_gpw"] == 13

    def test_fertilizer_name_preserved(self):
        stage = self._make_stage(10, 10, "MKP + Calcium nitrate")
        result = scale_stage_quantities(stage, 100)
        assert result["fertilizer_name"] == "MKP + Calcium nitrate"

    def test_missing_quantities_key(self):
        """Stage without 'quantities' key should return zeros without error."""
        result = scale_stage_quantities({}, 2100)
        assert result["total_irrigation_litres_per_day"] == 0.0
        assert result["total_fertilizer_kg_per_week"] == 0.0
