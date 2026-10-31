"""
test_financial_router.py — Unit tests for the financial router endpoints.

Covers subtask 22.3:
  - total_cost does not double-count an activity that has a linked expense
  - break-even displays "Set an expected yield" message when yield not set
  - financial summary / report separates actuals from scenarios

Tests mock the Supabase client via dependency override of get_db and
get_user_id so no live database is required.

Requirements: 10.2, 10.3, 10.4
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from routers import financial as financial_router
from routers.financial import _deduplicated_activities
from services.financials import total_cost, net_realisation

# ---------------------------------------------------------------------------
# Mock helpers (adapted from test_farms.py)
# ---------------------------------------------------------------------------


def _make_chain_mock(data=None):
    """Create a MagicMock simulating the Supabase fluent query chain."""
    mock = MagicMock()
    mock.select.return_value = mock
    mock.insert.return_value = mock
    mock.update.return_value = mock
    mock.delete.return_value = mock
    mock.eq.return_value = mock
    mock.order.return_value = mock
    mock.maybe_single.return_value = mock

    execute_result = MagicMock()
    execute_result.data = data
    mock.execute.return_value = execute_result
    return mock


def _make_db_mock(table_data_map):
    """Create a mock Supabase client returning chain mocks per table name."""
    db = MagicMock()
    chain_mocks = {}
    for table_name, data in table_data_map.items():
        chain_mocks[table_name] = _make_chain_mock(data)

    def table_factory(name):
        if name not in chain_mocks:
            chain_mocks[name] = _make_chain_mock(table_data_map.get(name))
        return chain_mocks[name]

    db.table.side_effect = table_factory
    return db


def _override_user_id(user_id: str):
    """Create a dependency override for get_user_id."""
    async def _mock_get_user_id():
        return user_id
    return _mock_get_user_id


# ===========================================================================
# Subtask 22.3a: total_cost does not double-count linked activity
# Requirement 10.2
# ===========================================================================

class TestDoubleCountingPrevention:
    """An activity with a linked expense record must not be counted in total_cost."""

    def test_activity_without_link_is_counted(self):
        """Activities with no linked expense are included in total_cost."""
        activities = [
            {"id": "act-1", "activity_type": "Fertilizer", "cost": 500},
            {"id": "act-2", "activity_type": "Labour", "cost": 300},
        ]
        expenses = []
        deduped = _deduplicated_activities(activities, expenses)
        assert len(deduped) == 2
        assert total_cost(deduped) == pytest.approx(800.0)

    def test_activity_with_linked_expense_is_excluded(self):
        """An activity whose id appears in an expense's linked_activity_id
        is excluded from total_cost to avoid double-counting.

        Requirement 10.2
        """
        activities = [
            {"id": "act-1", "activity_type": "Fertilizer", "cost": 500},
            {"id": "act-2", "activity_type": "Labour", "cost": 300},
        ]
        expenses = [
            {"id": "exp-1", "linked_activity_id": "act-1", "amount": 500},
        ]
        deduped = _deduplicated_activities(activities, expenses)
        # act-1 is excluded because it's linked to exp-1.
        assert len(deduped) == 1
        assert deduped[0]["id"] == "act-2"
        assert total_cost(deduped) == pytest.approx(300.0)

    def test_all_activities_linked_all_excluded(self):
        """When every activity has a linked expense, total_cost is 0."""
        activities = [
            {"id": "act-1", "activity_type": "Fertilizer", "cost": 500},
            {"id": "act-2", "activity_type": "Labour", "cost": 300},
        ]
        expenses = [
            {"id": "exp-1", "linked_activity_id": "act-1", "amount": 500},
            {"id": "exp-2", "linked_activity_id": "act-2", "amount": 300},
        ]
        deduped = _deduplicated_activities(activities, expenses)
        assert len(deduped) == 0
        assert total_cost(deduped) == pytest.approx(0.0)

    def test_expense_without_link_does_not_exclude_anything(self):
        """An expense with no linked_activity_id does not affect activities."""
        activities = [
            {"id": "act-1", "activity_type": "Fertilizer", "cost": 500},
        ]
        expenses = [
            {"id": "exp-1", "linked_activity_id": None, "amount": 200},
        ]
        deduped = _deduplicated_activities(activities, expenses)
        assert len(deduped) == 1
        assert total_cost(deduped) == pytest.approx(500.0)

    def test_net_realisation_function(self):
        """net_realisation = gross_sales - deductions (unit test for the pure function)."""
        assert net_realisation(10000, 2000) == pytest.approx(8000.0)
        assert net_realisation(500, 0) == pytest.approx(500.0)
        assert net_realisation(0, 0) == pytest.approx(0.0)


# ===========================================================================
# Subtask 22.3b: Break-even shows "Set an expected yield" when yield not set
# Requirement 10.4
# ===========================================================================

class TestBreakEvenMessage:
    """When expected_yield_kg is not set, the summary shows a guidance note."""

    def setup_method(self):
        self._orig = financial_router.get_user_id

    def teardown_method(self):
        app.dependency_overrides.clear()
        financial_router.get_user_id = self._orig

    def test_break_even_note_when_yield_not_set(self):
        """financial-summary returns break_even_note when expected_yield_kg is None.

        Requirement 10.4: display "Set an expected yield..." not a zero value.
        """
        farmer = {
            "id": "farmer-1",
            "crop": "guava",
            "plant_count": 100,
            "sowing_date": "2023-01-01",
            "expected_yield_kg": None,           # not set
            "vendor_recommendation_consent": False,
        }
        activities = [
            {"id": "act-1", "activity_type": "Fertilizer", "cost": 1500,
             "logged_date": "2024-01-01", "quantity": 10, "unit": "kg"},
        ]
        db = _make_db_mock({
            "farmers": farmer,
            "farm_activities": activities,
            "harvests": None,
            "expenses": [],
        })
        app.dependency_overrides[financial_router.get_user_id] = _override_user_id("user-a")

        with patch("routers.financial.get_db", return_value=db):
            response = TestClient(app).get("/api/farmers/me/financial-summary")

        assert response.status_code == 200
        body = response.json()
        assert body["break_even_price_per_kg"] is None
        assert body["break_even_note"] is not None
        assert "expected yield" in body["break_even_note"].lower()

    def test_break_even_price_when_yield_is_set(self):
        """When expected_yield_kg is set and costs exist, break-even price is computed."""
        farmer = {
            "id": "farmer-1",
            "crop": "guava",
            "plant_count": 100,
            "sowing_date": "2023-01-01",
            "expected_yield_kg": 40000,
            "vendor_recommendation_consent": False,
        }
        activities = [
            {"id": "act-1", "activity_type": "Fertilizer", "cost": 120000,
             "logged_date": "2024-01-01", "quantity": 10, "unit": "kg"},
        ]
        db = _make_db_mock({
            "farmers": farmer,
            "farm_activities": activities,
            "harvests": None,
            "expenses": [],
        })
        app.dependency_overrides[financial_router.get_user_id] = _override_user_id("user-a")

        with patch("routers.financial.get_db", return_value=db):
            response = TestClient(app).get("/api/farmers/me/financial-summary")

        assert response.status_code == 200
        body = response.json()
        # 120000 / 40000 = 3.0
        assert body["break_even_price_per_kg"] == pytest.approx(3.0)
        assert body["break_even_note"] is None


# ===========================================================================
# Subtask 22.3c: Financial summary / report separates actuals from scenarios
# Requirement 10.3, 10.4
# ===========================================================================

class TestActualsVsScenarios:
    """The report endpoint must label actual harvests and scenario projections
    distinctly in the response.

    Requirement 9.4, 10.3
    """

    def setup_method(self):
        self._orig = financial_router.get_user_id

    def teardown_method(self):
        app.dependency_overrides.clear()
        financial_router.get_user_id = self._orig

    def _make_farmer(self):
        return {
            "id": "farmer-1",
            "crop": "guava",
            "plant_count": 100,
            "sowing_date": "2023-01-01",
            "expected_yield_kg": 40000,
            "vendor_recommendation_consent": False,
        }

    def test_report_actual_harvest_in_harvest_record(self):
        """A non-scenario harvest (is_scenario=False) appears in harvest_record,
        not scenario_record.

        Requirement 9.4, 10.3
        """
        farmer = self._make_farmer()
        harvest = {
            "id": "h-1",
            "farmer_id": "farmer-1",
            "sale_quantity_kg": 1000,
            "sale_price_per_kg": 50,
            "sale_date": "2024-06-01",
            "gross_sales": 50000,
            "deductions": 5000,
            "net_realisation": 45000,
            "transport_cost": 1000,
            "market_type": "mandi",
            "grade": "A",
            "payment_status": "paid",
            "is_scenario": False,
        }
        db = _make_db_mock({
            "farmers": farmer,
            "farm_activities": [],
            "harvests": harvest,
            "expenses": [],
        })
        app.dependency_overrides[financial_router.get_user_id] = _override_user_id("user-a")

        with patch("routers.financial.get_db", return_value=db):
            response = TestClient(app).get("/api/farmers/me/report")

        assert response.status_code == 200
        body = response.json()
        assert body["harvest_record"] is not None
        assert body["harvest_record"]["record_type"] == "actual"
        assert body["scenario_record"] is None
        # Revenue and profit should reflect the actual harvest.
        assert body["revenue"] == pytest.approx(50000.0)

    def test_report_scenario_harvest_in_scenario_record(self):
        """A scenario harvest (is_scenario=True) appears in scenario_record,
        not harvest_record, and revenue/profit should be None for the summary.

        Requirement 9.4, 10.3
        """
        farmer = self._make_farmer()
        harvest = {
            "id": "h-scenario",
            "farmer_id": "farmer-1",
            "sale_quantity_kg": 2000,
            "sale_price_per_kg": 60,
            "sale_date": "2024-12-01",
            "gross_sales": 120000,
            "deductions": 10000,
            "net_realisation": 110000,
            "transport_cost": 2000,
            "market_type": "retail",
            "grade": "A",
            "payment_status": "unpaid",
            "is_scenario": True,
        }
        db = _make_db_mock({
            "farmers": farmer,
            "farm_activities": [],
            "harvests": harvest,
            "expenses": [],
        })
        app.dependency_overrides[financial_router.get_user_id] = _override_user_id("user-a")

        with patch("routers.financial.get_db", return_value=db):
            response = TestClient(app).get("/api/farmers/me/report")

        assert response.status_code == 200
        body = response.json()
        assert body["harvest_record"] is None
        assert body["scenario_record"] is not None
        assert body["scenario_record"]["record_type"] == "scenario"
        # Revenue/profit are None because only actuals contribute to the summary.
        assert body["revenue"] is None
        assert body["profit_or_loss"] is None
        # has_harvest is still True (a record exists), even if it's a scenario.
        assert body["has_harvest"] is True

    def test_report_no_harvest(self):
        """When no harvest record exists, both harvest_record and scenario_record
        are None, and revenue/profit are None.
        """
        farmer = self._make_farmer()
        db = _make_db_mock({
            "farmers": farmer,
            "farm_activities": [],
            "harvests": None,
            "expenses": [],
        })
        app.dependency_overrides[financial_router.get_user_id] = _override_user_id("user-a")

        with patch("routers.financial.get_db", return_value=db):
            response = TestClient(app).get("/api/farmers/me/report")

        assert response.status_code == 200
        body = response.json()
        assert body["harvest_record"] is None
        assert body["scenario_record"] is None
        assert body["revenue"] is None
        assert body["profit_or_loss"] is None
        assert body["has_harvest"] is False


# ===========================================================================
# Subtask 22.3d: Expense endpoints
# Requirement 10.1
# ===========================================================================

class TestExpenseEndpoints:
    """POST and GET /api/farmers/me/expenses create and list expense records."""

    def setup_method(self):
        self._orig = financial_router.get_user_id

    def teardown_method(self):
        app.dependency_overrides.clear()
        financial_router.get_user_id = self._orig

    def test_list_expenses(self):
        """GET /expenses returns all expense records for the user."""
        expenses = [
            {"id": "e-1", "category": "input", "amount": 500,
             "expense_date": "2024-01-01", "description": "Fertilizer",
             "farm_id": None, "plot_id": None, "linked_activity_id": None,
             "created_at": "2024-01-01T00:00:00"},
            {"id": "e-2", "category": "labour", "amount": 1200,
             "expense_date": "2024-01-05", "description": "Daily wage",
             "farm_id": None, "plot_id": None, "linked_activity_id": None,
             "created_at": "2024-01-05T00:00:00"},
        ]
        db = _make_db_mock({"expenses": expenses})
        app.dependency_overrides[financial_router.get_user_id] = _override_user_id("user-a")

        with patch("routers.financial.get_db", return_value=db):
            response = TestClient(app).get("/api/farmers/me/expenses")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2
        assert body[0]["category"] == "input"
        assert body[1]["category"] == "labour"

    def test_post_expense_stores_record(self):
        """POST /expenses stores the expense with the authenticated user's id."""
        inserted_row = {
            "id": "e-new",
            "category": "input",
            "amount": 750,
            "expense_date": "2024-03-01",
            "description": "Pesticide",
            "farm_id": None,
            "plot_id": None,
            "linked_activity_id": None,
            "created_at": "2024-03-01T00:00:00",
        }
        db = _make_db_mock({"expenses": [inserted_row]})
        # Configure the expenses chain to return the inserted row on execute.
        expenses_chain = db.table("expenses")
        insert_result = MagicMock()
        insert_result.data = [inserted_row]
        expenses_chain.execute.return_value = insert_result

        app.dependency_overrides[financial_router.get_user_id] = _override_user_id("user-a")

        with patch("routers.financial.get_db", return_value=db):
            response = TestClient(app).post(
                "/api/farmers/me/expenses",
                json={
                    "category": "input",
                    "amount": 750,
                    "expense_date": "2024-03-01",
                    "description": "Pesticide",
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["category"] == "input"
        assert body["amount"] == pytest.approx(750.0)

        # Verify the insert payload includes the user_id.
        insert_call = expenses_chain.insert.call_args
        payload = insert_call[0][0]
        assert payload["user_id"] == "user-a"
        assert payload["category"] == "input"
        assert payload["amount"] == 750

    def test_post_expense_invalid_category_rejected(self):
        """An expense with an invalid category is rejected (422)."""
        db = _make_db_mock({"expenses": []})
        app.dependency_overrides[financial_router.get_user_id] = _override_user_id("user-a")

        with patch("routers.financial.get_db", return_value=db):
            response = TestClient(app).post(
                "/api/farmers/me/expenses",
                json={
                    "category": "invalid_category",
                    "amount": 100,
                    "expense_date": "2024-03-01",
                },
            )
        assert response.status_code == 422
