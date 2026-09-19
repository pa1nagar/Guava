"""
test_financials.py — Tests for services/financials.py

Covers:
  - total_cost: empty, single, multiple activities
  - cost_by_activity_type: grouping and summing
  - revenue: basic multiplication, edge cases
  - profit_or_loss: profit, loss, breakeven
  - break_even_price: normal, missing yield, zero cost, zero yield
"""

import pytest
from services.financials import (
    total_cost,
    cost_by_activity_type,
    revenue,
    profit_or_loss,
    break_even_price,
)


class TestTotalCost:

    def test_empty_activities(self):
        assert total_cost([]) == 0.0

    def test_single_activity(self):
        assert total_cost([{"cost": 1500.0}]) == pytest.approx(1500.0)

    def test_multiple_activities(self):
        activities = [
            {"cost": 1000.0},
            {"cost": 2500.0},
            {"cost": 750.50},
        ]
        assert total_cost(activities) == pytest.approx(4250.50)

    def test_zero_cost_activity(self):
        assert total_cost([{"cost": 0}]) == 0.0

    def test_string_cost_coerced(self):
        """Database may return numeric strings."""
        assert total_cost([{"cost": "1200.50"}]) == pytest.approx(1200.50)


class TestCostByActivityType:

    def test_single_type(self):
        activities = [
            {"activity_type": "Fertilizer", "cost": 500},
            {"activity_type": "Fertilizer", "cost": 300},
        ]
        result = cost_by_activity_type(activities)
        assert result == {"Fertilizer": pytest.approx(800.0)}

    def test_multiple_types(self):
        activities = [
            {"activity_type": "Fertilizer", "cost": 1000},
            {"activity_type": "Irrigation", "cost": 400},
            {"activity_type": "Pesticide",  "cost": 250},
            {"activity_type": "Fertilizer", "cost": 600},
        ]
        result = cost_by_activity_type(activities)
        assert result["Fertilizer"] == pytest.approx(1600.0)
        assert result["Irrigation"] == pytest.approx(400.0)
        assert result["Pesticide"] == pytest.approx(250.0)

    def test_empty_activities(self):
        assert cost_by_activity_type([]) == {}

    def test_missing_type_defaults_to_other(self):
        activities = [{"cost": 100}]  # no activity_type key
        result = cost_by_activity_type(activities)
        assert "Other" in result


class TestRevenue:

    def test_basic_revenue(self):
        assert revenue(1000.0, 65.0) == pytest.approx(65000.0)

    def test_zero_quantity(self):
        assert revenue(0.0, 65.0) == 0.0

    def test_zero_price(self):
        assert revenue(1000.0, 0.0) == 0.0

    def test_negative_quantity_raises(self):
        with pytest.raises(ValueError):
            revenue(-1.0, 65.0)

    def test_negative_price_raises(self):
        with pytest.raises(ValueError):
            revenue(1000.0, -5.0)

    def test_fractional_values(self):
        assert revenue(42000.5, 65.25) == pytest.approx(42000.5 * 65.25)


class TestProfitOrLoss:

    def test_profit(self):
        assert profit_or_loss(100000.0, 60000.0) == pytest.approx(40000.0)

    def test_loss(self):
        assert profit_or_loss(50000.0, 80000.0) == pytest.approx(-30000.0)

    def test_breakeven(self):
        assert profit_or_loss(75000.0, 75000.0) == 0.0


class TestBreakEvenPrice:

    def test_normal_case(self):
        # ₹1,20,000 cost / 40,000 kg = ₹3/kg
        result = break_even_price(120000.0, 40000.0)
        assert result == pytest.approx(3.0)

    def test_missing_yield_returns_none(self):
        assert break_even_price(120000.0, None) is None

    def test_zero_yield_returns_none(self):
        assert break_even_price(120000.0, 0.0) is None

    def test_negative_yield_returns_none(self):
        assert break_even_price(120000.0, -100.0) is None

    def test_zero_cost_returns_none(self):
        """No costs logged yet — should not return ₹0 as a fake break-even."""
        assert break_even_price(0.0, 40000.0) is None

    def test_realistic_guava_scenario(self):
        # 2100 plants, ~₹7.5 lakh costs, 42 tonnes expected yield → ~₹17.86/kg
        result = break_even_price(750000.0, 42000.0)
        assert result == pytest.approx(750000.0 / 42000.0, rel=1e-4)
