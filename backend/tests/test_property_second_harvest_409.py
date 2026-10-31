# Feature: smart-farmer-app, Property 18: Second harvest record for same crop cycle returns 409
"""
test_property_second_harvest_409.py — Property-based test for second-harvest
rejection.

Validates Property 18: For any farmer who already has a harvest record for a
crop cycle, a second POST /api/farmers/me/harvest returns HTTP 409.

Uses Hypothesis with @given and @settings(max_examples=200) to generate varied
valid harvest inputs; every one must be rejected with 409 when a harvest
already exists.

Validates: Requirements 9.3
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from main import app
from routers import financial as financial_router
from services.stage import StageResult

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


# ---------------------------------------------------------------------------
# Shared fixture data
# ---------------------------------------------------------------------------

FARMER_DATA = {
    "id": "farmer-1",
    "crop": "guava",
    "plant_count": 100,
    "sowing_date": "2023-01-01",
    "expected_yield_kg": 40000,
    "vendor_recommendation_consent": False,
}

EXISTING_HARVEST = {
    "id": "harvest-existing",
    "farmer_id": "farmer-1",
    "sale_quantity_kg": 1000,
    "sale_price_per_kg": 50,
    "sale_date": "2024-06-01",
    "is_scenario": False,
}

FINAL_STAGE_RESULT = StageResult(
    stage={"stage_id": "harvest", "label": "Harvest",
           "month_start": 17, "month_end": 17},
    months_elapsed=17,
    days_elapsed=510,
    is_final_stage=True,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid harvest input fields — any non-negative values.
sale_quantity_st = st.floats(
    min_value=0.01, max_value=100_000, allow_nan=False, allow_infinity=False
)
sale_price_st = st.floats(
    min_value=0, max_value=10_000, allow_nan=False, allow_infinity=False
)
deductions_st = st.floats(
    min_value=0, max_value=50_000, allow_nan=False, allow_infinity=False
)
transport_cost_st = st.floats(
    min_value=0, max_value=50_000, allow_nan=False, allow_infinity=False
)


# ---------------------------------------------------------------------------
# Property 18: Second harvest for same crop cycle returns 409
# ---------------------------------------------------------------------------

# Feature: smart-farmer-app, Property 18: Second harvest record for same crop cycle returns 409
@given(
    sale_quantity=sale_quantity_st,
    sale_price=sale_price_st,
    deductions=deductions_st,
    transport_cost=transport_cost_st,
)
@settings(max_examples=200)
def test_second_harvest_returns_409(
    sale_quantity: float, sale_price: float,
    deductions: float, transport_cost: float,
):
    """For any farmer who already has a harvest record for a crop cycle, a
    second POST /api/farmers/me/harvest returns HTTP 409.

    The harvest is write-once per crop cycle. No matter what valid sale data
    the farmer submits, if a harvest already exists the response is 409.

    Validates: Requirements 9.3
    """
    db = _make_db_mock({"farmers": FARMER_DATA, "harvests": EXISTING_HARVEST})

    app.dependency_overrides[financial_router.get_user_id] = _override_user_id("user-a")

    try:
        with patch("routers.financial.get_db", return_value=db), \
             patch("services.stage.get_stage", return_value=FINAL_STAGE_RESULT):
            response = TestClient(app).post(
                "/api/farmers/me/harvest",
                json={
                    "sale_quantity_kg": sale_quantity,
                    "sale_price_per_kg": sale_price,
                    "deductions": deductions,
                    "transport_cost": transport_cost,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409, (
        f"Expected 409 for second harvest with qty={sale_quantity}, "
        f"price={sale_price}, got {response.status_code}: {response.text}"
    )
    detail = response.json()["detail"].lower()
    assert "already" in detail or "recorded" in detail, (
        f"Expected 'already recorded' message, got: {response.json()['detail']}"
    )
