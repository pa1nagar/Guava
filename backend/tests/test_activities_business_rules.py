"""
test_activities_business_rules.py — Tests for activity business rules.

Covers:
  - ZERO_COST_ACTIVITY_TYPES constant is correct
  - Irrigation is in the zero-cost set
  - Fertilizer is NOT in the zero-cost set
  - ACTIVITY_TYPES list matches schema expectation
  - Zero-cost enforcement logic (unit test without DB)
"""

import pytest
from services.constants import ACTIVITY_TYPES, ZERO_COST_ACTIVITY_TYPES


class TestActivityConstants:

    def test_irrigation_is_zero_cost(self):
        assert "Irrigation" in ZERO_COST_ACTIVITY_TYPES

    def test_fertilizer_is_not_zero_cost(self):
        assert "Fertilizer" not in ZERO_COST_ACTIVITY_TYPES

    def test_pesticide_is_not_zero_cost(self):
        assert "Pesticide" not in ZERO_COST_ACTIVITY_TYPES

    def test_labour_is_not_zero_cost(self):
        assert "Labour" not in ZERO_COST_ACTIVITY_TYPES

    def test_activity_types_contains_all_expected(self):
        expected = {"Fertilizer", "Irrigation", "Pesticide", "Labour", "Other"}
        assert expected == set(ACTIVITY_TYPES)

    def test_activity_types_is_list(self):
        assert isinstance(ACTIVITY_TYPES, list)

    def test_zero_cost_types_is_subset_of_activity_types(self):
        """Every zero-cost type must be a valid activity type."""
        assert ZERO_COST_ACTIVITY_TYPES.issubset(set(ACTIVITY_TYPES))

    def test_zero_cost_cost_override_logic(self):
        """Simulate what the router does: override cost to 0 for irrigation."""
        def effective_cost(activity_type: str, submitted_cost: float) -> float:
            return 0.0 if activity_type in ZERO_COST_ACTIVITY_TYPES else submitted_cost

        # Irrigation — any submitted cost becomes 0
        assert effective_cost("Irrigation", 500.0) == 0.0
        assert effective_cost("Irrigation", 0.0)   == 0.0
        assert effective_cost("Irrigation", 9999.0) == 0.0

        # Fertilizer — cost is passed through
        assert effective_cost("Fertilizer", 1500.0) == 1500.0
        assert effective_cost("Fertilizer", 0.0)    == 0.0

        # Labour — cost is passed through
        assert effective_cost("Labour", 800.0) == 800.0
