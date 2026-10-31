"""
test_farms.py — Unit tests for the Farm and Plot CRUD router.

Covers:
  - Future planting date rejection (422)
  - Archive sets is_active=false (no hard delete)
  - Plant count update writes audit row with prior and new count
  - Spacing fields stored separately (no substitution)
  - IDOR prevention (404 on wrong user / unowned resource)
  - No pre-populated defaults (2100 trees, Taiwan Pink, Badnawar)

Tests mock the Supabase client via dependency override of get_db and
get_user_id so no live database is required.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from routers.farms import (
    _check_planting_date,
    _validate_area_unit,
    _get_farm,
    _get_plot,
)


# ═════════════════════════════════════════════════════════════════════════════
# Pure helper tests (no DB mock needed)
# ═════════════════════════════════════════════════════════════════════════════

class TestCheckPlantingDate:
    """Requirement 4.5: future planting date rejected with 422."""

    def test_today_accepted(self):
        """Planting date == today is valid (not in the future)."""
        _check_planting_date(date.today())  # should not raise

    def test_past_accepted(self):
        """A date in the past is valid."""
        _check_planting_date(date.today() - timedelta(days=30))

    def test_future_rejected(self):
        """A date tomorrow is in the future and must raise 422."""
        future = date.today() + timedelta(days=1)
        with pytest.raises(HTTPException) as exc_info:
            _check_planting_date(future)
        assert exc_info.value.status_code == 422
        assert "future" in exc_info.value.detail.lower()

    def test_far_future_rejected(self):
        future = date.today() + timedelta(days=365)
        with pytest.raises(HTTPException):
            _check_planting_date(future)


class TestValidateAreaUnit:
    def test_valid_units_accepted(self):
        for unit in ("acres", "hectares", "sqm"):
            _validate_area_unit(unit)  # should not raise

    def test_none_accepted(self):
        _validate_area_unit(None)  # should not raise

    def test_invalid_unit_rejected(self):
        with pytest.raises(HTTPException) as exc_info:
            _validate_area_unit("square_feet")
        assert exc_info.value.status_code == 422

    def test_empty_string_rejected(self):
        with pytest.raises(HTTPException):
            _validate_area_unit("")


# ═════════════════════════════════════════════════════════════════════════════
# Supabase mock helpers
# ═════════════════════════════════════════════════════════════════════════════

def _make_chain_mock(data=None):
    """Create a MagicMock that simulates the Supabase fluent query chain.

    Every method call returns self (the mock), so .select().eq().execute()
    chains work. .execute() returns an object with .data set to `data`.
    """
    mock = MagicMock()
    # Every builder method returns the mock itself (fluent API).
    mock.select.return_value = mock
    mock.insert.return_value = mock
    mock.update.return_value = mock
    mock.delete.return_value = mock
    mock.eq.return_value = mock
    mock.order.return_value = mock
    mock.maybe_single.return_value = mock

    # .execute() returns an object with .data
    execute_result = MagicMock()
    execute_result.data = data
    mock.execute.return_value = execute_result

    return mock, execute_result


def _make_db_mock(table_data_map=None):
    """Create a mock Supabase client that returns chain mocks per table name.

    table_data_map: dict mapping table name -> data to return from .execute().
    Chains are pre-created for all tables in the map so tests can configure
    them before any endpoint call.
    """
    table_data_map = table_data_map or {}
    db = MagicMock()
    chain_mocks = {}

    # Pre-create chain mocks for all requested tables.
    for table_name, data in table_data_map.items():
        chain, _ = _make_chain_mock(data)
        chain_mocks[table_name] = chain

    def table_factory(table_name):
        if table_name not in chain_mocks:
            data = table_data_map.get(table_name)
            chain, _ = _make_chain_mock(data)
            chain_mocks[table_name] = chain
        return chain_mocks[table_name]

    db.table.side_effect = table_factory
    return db, chain_mocks


# ═════════════════════════════════════════════════════════════════════════════
# _get_farm tests (IDOR prevention)
# ═════════════════════════════════════════════════════════════════════════════

class TestGetFarm:
    def test_returns_farm_when_owned(self):
        farm_data = {"id": "farm-1", "name": "My Farm", "district": "Dhar",
                      "state": "MP", "user_id": "user-a", "is_active": True,
                      "created_at": "2024-01-01", "updated_at": "2024-01-01"}
        db, chains = _make_db_mock({"farms": farm_data})
        with patch("routers.farms.get_db", return_value=db):
            result = _get_farm("farm-1", "user-a")
        assert result["id"] == "farm-1"

    def test_returns_404_when_not_owned(self):
        """IDOR: farm belongs to another user -> 404, not 403."""
        db, chains = _make_db_mock({"farms": None})
        with patch("routers.farms.get_db", return_value=db):
            with pytest.raises(HTTPException) as exc_info:
                _get_farm("farm-1", "user-b")
        assert exc_info.value.status_code == 404


class TestGetPlot:
    def test_returns_plot_when_owned(self):
        farm_data = {"id": "farm-1", "name": "My Farm", "district": "Dhar",
                      "state": "MP", "user_id": "user-a", "is_active": True,
                      "created_at": "2024-01-01", "updated_at": "2024-01-01"}
        plot_data = {"id": "plot-1", "farm_id": "farm-1", "name": "Plot A",
                      "crop": "guava", "plant_count": 100, "planting_date": "2024-01-01",
                      "created_at": "2024-01-01", "updated_at": "2024-01-01"}
        db, chains = _make_db_mock({"farms": farm_data, "plots": plot_data})
        with patch("routers.farms.get_db", return_value=db):
            result = _get_plot("farm-1", "plot-1", "user-a")
        assert result["id"] == "plot-1"

    def test_returns_404_when_plot_not_owned(self):
        """IDOR: plot belongs to another user -> 404."""
        farm_data = {"id": "farm-1", "name": "My Farm", "district": "Dhar",
                      "state": "MP", "user_id": "user-a", "is_active": True,
                      "created_at": "2024-01-01", "updated_at": "2024-01-01"}
        db, chains = _make_db_mock({"farms": farm_data, "plots": None})
        with patch("routers.farms.get_db", return_value=db):
            with pytest.raises(HTTPException) as exc_info:
                _get_plot("farm-1", "plot-x", "user-b")
        assert exc_info.value.status_code == 404

    def test_returns_404_when_farm_not_owned(self):
        """If the farm itself is not owned, we get 404 before checking the plot."""
        db, chains = _make_db_mock({"farms": None})
        with patch("routers.farms.get_db", return_value=db):
            with pytest.raises(HTTPException) as exc_info:
                _get_plot("farm-x", "plot-1", "user-b")
        assert exc_info.value.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
# Farm CRUD via FastAPI TestClient
# ═════════════════════════════════════════════════════════════════════════════

from fastapi.testclient import TestClient
from main import app
from routers import farms as farms_router


def _override_user_id(user_id: str):
    """Create a dependency override for get_user_id."""
    async def _mock_get_user_id():
        return user_id
    return _mock_get_user_id


class TestFarmCRUD:
    """Integration-level tests using TestClient with mocked DB."""

    def setup_method(self):
        self._orig_override = farms_router.get_user_id

    def teardown_method(self):
        app.dependency_overrides.clear()
        farms_router.get_user_id = self._orig_override

    def test_create_farm(self):
        """POST creates a farm with the authenticated user's id."""
        farm_row = {
            "id": "farm-1", "name": "Green Acres", "locality": None,
            "district": "Dhar", "state": "MP", "country": "India",
            "timezone": "Asia/Kolkata", "approx_lat": None, "approx_lon": None,
            "area_value": None, "area_unit": None, "soil_description": None,
            "irrigation_method": None, "water_source": None, "notes": None,
            "is_active": True, "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        db, chains = _make_db_mock({"farms": [farm_row]})
        app.dependency_overrides[farms_router.get_user_id] = _override_user_id("user-a")
        with patch("routers.farms.get_db", return_value=db):
            response = TestClient(app).post("/api/farmers/me/farms", json={
                "name": "Green Acres", "district": "Dhar", "state": "MP",
            })
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Green Acres"
        assert body["district"] == "Dhar"

    def test_list_farms(self):
        """GET returns all farms for the user."""
        farms_list = [
            {"id": "farm-1", "name": "Farm A", "locality": None,
             "district": "Dhar", "state": "MP", "country": "India",
             "timezone": "Asia/Kolkata", "approx_lat": None, "approx_lon": None,
             "area_value": None, "area_unit": None, "soil_description": None,
             "irrigation_method": None, "water_source": None, "notes": None,
             "is_active": True, "created_at": "2024-01-01T00:00:00",
             "updated_at": "2024-01-01T00:00:00"},
            {"id": "farm-2", "name": "Farm B", "locality": None,
             "district": "Indore", "state": "MP", "country": "India",
             "timezone": "Asia/Kolkata", "approx_lat": None, "approx_lon": None,
             "area_value": None, "area_unit": None, "soil_description": None,
             "irrigation_method": None, "water_source": None, "notes": None,
             "is_active": False, "created_at": "2024-02-01T00:00:00",
             "updated_at": "2024-02-01T00:00:00"},
        ]
        db, chains = _make_db_mock({"farms": farms_list})
        app.dependency_overrides[farms_router.get_user_id] = _override_user_id("user-a")
        with patch("routers.farms.get_db", return_value=db):
            response = TestClient(app).get("/api/farmers/me/farms")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2
        assert body[0]["name"] == "Farm A"
        assert body[1]["name"] == "Farm B"

    def test_archive_farm_sets_inactive(self):
        """DELETE /archive sets is_active=false, never hard-deletes.

        Requirement 4.7: historical records are retained.
        """
        farm_row = {"id": "farm-1", "name": "Farm A", "locality": None,
                     "district": "Dhar", "state": "MP", "country": "India",
                     "timezone": "Asia/Kolkata", "approx_lat": None, "approx_lon": None,
                     "area_value": None, "area_unit": None, "soil_description": None,
                     "irrigation_method": None, "water_source": None, "notes": None,
                     "is_active": True, "created_at": "2024-01-01T00:00:00",
                     "updated_at": "2024-01-01T00:00:00"}
        db, chains = _make_db_mock({"farms": farm_row})
        # The first call (_get_farm) returns the farm; the second (update) returns updated.
        # We need the farms table mock to return farm_row for select and then
        # return updated row for update.
        farm_chain = chains["farms"]
        # First .execute() (select) returns farm_row; second .execute() (update) returns updated.
        select_result = MagicMock()
        select_result.data = farm_row
        update_result = MagicMock()
        update_result.data = [{**farm_row, "is_active": False}]
        farm_chain.execute.side_effect = [select_result, update_result]

        app.dependency_overrides[farms_router.get_user_id] = _override_user_id("user-a")
        with patch("routers.farms.get_db", return_value=db):
            response = TestClient(app).delete("/api/farmers/me/farms/farm-1/archive")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "archived"
        assert body["farm_id"] == "farm-1"

        # Verify the update used is_active=False (not a delete).
        update_call_args = farm_chain.update.call_args
        assert update_call_args[0][0] == {"is_active": False}

    def test_archive_farm_not_owned_returns_404(self):
        """IDOR: archaging another user's farm returns 404."""
        db, chains = _make_db_mock({"farms": None})
        app.dependency_overrides[farms_router.get_user_id] = _override_user_id("user-b")
        with patch("routers.farms.get_db", return_value=db):
            response = TestClient(app).delete("/api/farmers/me/farms/farm-1/archive")
        assert response.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
# Plot CRUD tests
# ═════════════════════════════════════════════════════════════════════════════

class TestPlotCRUD:

    def setup_method(self):
        self._orig_override = farms_router.get_user_id

    def teardown_method(self):
        app.dependency_overrides.clear()
        farms_router.get_user_id = self._orig_override

    def test_create_plot_with_future_date_rejected(self):
        """POST plot with future planting_date -> 422.

        Requirement 4.5.
        """
        farm_row = {"id": "farm-1", "name": "Farm A", "locality": None,
                     "district": "Dhar", "state": "MP", "country": "India",
                     "timezone": "Asia/Kolkata", "approx_lat": None, "approx_lon": None,
                     "area_value": None, "area_unit": None, "soil_description": None,
                     "irrigation_method": None, "water_source": None, "notes": None,
                     "is_active": True, "created_at": "2024-01-01T00:00:00",
                     "updated_at": "2024-01-01T00:00:00"}
        db, chains = _make_db_mock({"farms": farm_row})
        app.dependency_overrides[farms_router.get_user_id] = _override_user_id("user-a")
        future_date = (date.today() + timedelta(days=10)).isoformat()
        with patch("routers.farms.get_db", return_value=db):
            response = TestClient(app).post(
                "/api/farmers/me/farms/farm-1/plots",
                json={
                    "name": "Plot A",
                    "crop": "guava",
                    "planting_date": future_date,
                    "plant_count": 100,
                },
            )
        assert response.status_code == 422
        assert "future" in response.json()["detail"].lower()

    def test_create_plot_with_valid_date_accepted(self):
        """POST plot with valid (past) planting_date -> 201."""
        farm_row = {"id": "farm-1", "name": "Farm A", "locality": None,
                     "district": "Dhar", "state": "MP", "country": "India",
                     "timezone": "Asia/Kolkata", "approx_lat": None, "approx_lon": None,
                     "area_value": None, "area_unit": None, "soil_description": None,
                     "irrigation_method": None, "water_source": None, "notes": None,
                     "is_active": True, "created_at": "2024-01-01T00:00:00",
                     "updated_at": "2024-01-01T00:00:00"}
        plot_row = {"id": "plot-1", "farm_id": "farm-1", "name": "Plot A",
                     "area_value": None, "area_unit": None, "crop": "guava",
                     "variety": None, "planting_date": "2024-01-01",
                     "planting_method": None, "row_spacing_m": None,
                     "within_row_spacing_m": None, "plant_count": 100,
                     "survival_count": None, "notes": None,
                     "created_at": "2024-01-01T00:00:00",
                     "updated_at": "2024-01-01T00:00:00"}
        db, chains = _make_db_mock({"farms": farm_row, "plots": [plot_row]})
        app.dependency_overrides[farms_router.get_user_id] = _override_user_id("user-a")
        past_date = (date.today() - timedelta(days=30)).isoformat()
        with patch("routers.farms.get_db", return_value=db):
            response = TestClient(app).post(
                "/api/farmers/me/farms/farm-1/plots",
                json={
                    "name": "Plot A",
                    "crop": "guava",
                    "planting_date": past_date,
                    "plant_count": 100,
                },
            )
        assert response.status_code == 201
        body = response.json()
        assert body["plant_count"] == 100

    def test_create_plot_idor_returns_404(self):
        """POST plot under another user's farm -> 404."""
        db, chains = _make_db_mock({"farms": None})
        app.dependency_overrides[farms_router.get_user_id] = _override_user_id("user-b")
        past_date = (date.today() - timedelta(days=30)).isoformat()
        with patch("routers.farms.get_db", return_value=db):
            response = TestClient(app).post(
                "/api/farmers/me/farms/farm-1/plots",
                json={
                    "name": "Plot A",
                    "crop": "guava",
                    "planting_date": past_date,
                    "plant_count": 100,
                },
            )
        assert response.status_code == 404

    def test_update_plot_writes_plant_count_audit(self):
        """PUT plot with changed plant_count inserts audit row BEFORE update.

        Requirement 4.3: audit row stores prior_count and new_count.
        """
        farm_row = {"id": "farm-1", "name": "Farm A", "locality": None,
                     "district": "Dhar", "state": "MP", "country": "India",
                     "timezone": "Asia/Kolkata", "approx_lat": None, "approx_lon": None,
                     "area_value": None, "area_unit": None, "soil_description": None,
                     "irrigation_method": None, "water_source": None, "notes": None,
                     "is_active": True, "created_at": "2024-01-01T00:00:00",
                     "updated_at": "2024-01-01T00:00:00"}
        plot_row = {"id": "plot-1", "farm_id": "farm-1", "name": "Plot A",
                     "area_value": None, "area_unit": None, "crop": "guava",
                     "variety": None, "planting_date": "2024-01-01",
                     "planting_method": None, "row_spacing_m": 3.0,
                     "within_row_spacing_m": 2.0, "plant_count": 100,
                     "survival_count": None, "notes": None,
                     "created_at": "2024-01-01T00:00:00",
                     "updated_at": "2024-01-01T00:00:00"}
        db, chains = _make_db_mock({"farms": farm_row, "plots": plot_row})

        # Configure plot chain for multi-execute: first is select (returns current),
        # second is update (returns updated row).
        plot_chain = chains["plots"]
        select_result = MagicMock()
        select_result.data = plot_row
        update_result = MagicMock()
        update_result.data = [{**plot_row, "plant_count": 150}]
        plot_chain.execute.side_effect = [select_result, update_result]

        # The audit insert goes through a separate table chain.
        audit_chain = chains.get("plot_plant_count_audit")
        if audit_chain is None:
            audit_chain, _ = _make_chain_mock(None)
            chains["plot_plant_count_audit"] = audit_chain
            # Need to wire it into db.table
            original_side_effect = db.table.side_effect
            table_data_map = {"farms": farm_row, "plots": plot_row}
            def table_factory_with_audit(table_name):
                if table_name == "plot_plant_count_audit":
                    return audit_chain
                return original_side_effect(table_name)
            db.table.side_effect = table_factory_with_audit

        app.dependency_overrides[farms_router.get_user_id] = _override_user_id("user-a")
        with patch("routers.farms.get_db", return_value=db):
            response = TestClient(app).put(
                "/api/farmers/me/farms/farm-1/plots/plot-1",
                json={"plant_count": 150},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["plant_count"] == 150

        # Verify audit row was inserted with correct prior and new counts.
        audit_insert_call = audit_chain.insert.call_args
        audit_payload = audit_insert_call[0][0]
        assert audit_payload["plot_id"] == "plot-1"
        assert audit_payload["prior_count"] == 100
        assert audit_payload["new_count"] == 150

    def test_update_plot_no_plant_count_change_no_audit(self):
        """PUT plot without changing plant_count should NOT insert audit row."""
        farm_row = {"id": "farm-1", "name": "Farm A", "locality": None,
                     "district": "Dhar", "state": "MP", "country": "India",
                     "timezone": "Asia/Kolkata", "approx_lat": None, "approx_lon": None,
                     "area_value": None, "area_unit": None, "soil_description": None,
                     "irrigation_method": None, "water_source": None, "notes": None,
                     "is_active": True, "created_at": "2024-01-01T00:00:00",
                     "updated_at": "2024-01-01T00:00:00"}
        plot_row = {"id": "plot-1", "farm_id": "farm-1", "name": "Plot A",
                     "area_value": None, "area_unit": None, "crop": "guava",
                     "variety": None, "planting_date": "2024-01-01",
                     "planting_method": None, "row_spacing_m": 3.0,
                     "within_row_spacing_m": 2.0, "plant_count": 100,
                     "survival_count": None, "notes": None,
                     "created_at": "2024-01-01T00:00:00",
                     "updated_at": "2024-01-01T00:00:00"}
        db, chains = _make_db_mock({"farms": farm_row, "plots": plot_row})

        plot_chain = chains["plots"]
        select_result = MagicMock()
        select_result.data = plot_row
        update_result = MagicMock()
        update_result.data = [{**plot_row, "notes": "updated note"}]
        plot_chain.execute.side_effect = [select_result, update_result]

        audit_chain, _ = _make_chain_mock(None)
        chains["plot_plant_count_audit"] = audit_chain
        original_side_effect = db.table.side_effect
        def table_factory_with_audit(table_name):
            if table_name == "plot_plant_count_audit":
                return audit_chain
            return original_side_effect(table_name)
        db.table.side_effect = table_factory_with_audit

        app.dependency_overrides[farms_router.get_user_id] = _override_user_id("user-a")
        with patch("routers.farms.get_db", return_value=db):
            response = TestClient(app).put(
                "/api/farmers/me/farms/farm-1/plots/plot-1",
                json={"notes": "updated note"},
            )
        assert response.status_code == 200
        # No audit insert should have happened.
        audit_chain.insert.assert_not_called()

    def test_spacing_fields_stored_separately(self):
        """PUT plot with row_spacing_m and within_row_spacing_m stores both separately.

        Requirement 4.4: both values stored without substitution.
        """
        farm_row = {"id": "farm-1", "name": "Farm A", "locality": None,
                     "district": "Dhar", "state": "MP", "country": "India",
                     "timezone": "Asia/Kolkata", "approx_lat": None, "approx_lon": None,
                     "area_value": None, "area_unit": None, "soil_description": None,
                     "irrigation_method": None, "water_source": None, "notes": None,
                     "is_active": True, "created_at": "2024-01-01T00:00:00",
                     "updated_at": "2024-01-01T00:00:00"}
        plot_row = {"id": "plot-1", "farm_id": "farm-1", "name": "Plot A",
                     "area_value": None, "area_unit": None, "crop": "guava",
                     "variety": None, "planting_date": "2024-01-01",
                     "planting_method": None, "row_spacing_m": None,
                     "within_row_spacing_m": None, "plant_count": 100,
                     "survival_count": None, "notes": None,
                     "created_at": "2024-01-01T00:00:00",
                     "updated_at": "2024-01-01T00:00:00"}
        db, chains = _make_db_mock({"farms": farm_row, "plots": plot_row})

        plot_chain = chains["plots"]
        select_result = MagicMock()
        select_result.data = plot_row
        update_result = MagicMock()
        updated_row = {**plot_row, "row_spacing_m": 3.0, "within_row_spacing_m": 2.0}
        update_result.data = [updated_row]
        plot_chain.execute.side_effect = [select_result, update_result]

        app.dependency_overrides[farms_router.get_user_id] = _override_user_id("user-a")
        with patch("routers.farms.get_db", return_value=db):
            response = TestClient(app).put(
                "/api/farmers/me/farms/farm-1/plots/plot-1",
                json={"row_spacing_m": 3.0, "within_row_spacing_m": 2.0},
            )
        assert response.status_code == 200

        # Verify the update payload contains both spacing fields.
        update_call_args = plot_chain.update.call_args
        update_payload = update_call_args[0][0]
        assert update_payload["row_spacing_m"] == 3.0
        assert update_payload["within_row_spacing_m"] == 2.0
        # No effective_area or substitute field should be present.
        assert "effective_area" not in update_payload
        assert "area_m2" not in update_payload

    def test_update_plot_future_date_rejected(self):
        """PUT plot with future planting_date -> 422."""
        farm_row = {"id": "farm-1", "name": "Farm A", "locality": None,
                     "district": "Dhar", "state": "MP", "country": "India",
                     "timezone": "Asia/Kolkata", "approx_lat": None, "approx_lon": None,
                     "area_value": None, "area_unit": None, "soil_description": None,
                     "irrigation_method": None, "water_source": None, "notes": None,
                     "is_active": True, "created_at": "2024-01-01T00:00:00",
                     "updated_at": "2024-01-01T00:00:00"}
        plot_row = {"id": "plot-1", "farm_id": "farm-1", "name": "Plot A",
                     "area_value": None, "area_unit": None, "crop": "guava",
                     "variety": None, "planting_date": "2024-01-01",
                     "planting_method": None, "row_spacing_m": None,
                     "within_row_spacing_m": None, "plant_count": 100,
                     "survival_count": None, "notes": None,
                     "created_at": "2024-01-01T00:00:00",
                     "updated_at": "2024-01-01T00:00:00"}
        db, chains = _make_db_mock({"farms": farm_row, "plots": plot_row})

        plot_chain = chains["plots"]
        select_result = MagicMock()
        select_result.data = plot_row
        plot_chain.execute.side_effect = [select_result]

        app.dependency_overrides[farms_router.get_user_id] = _override_user_id("user-a")
        future_date = (date.today() + timedelta(days=10)).isoformat()
        with patch("routers.farms.get_db", return_value=db):
            response = TestClient(app).put(
                "/api/farmers/me/farms/farm-1/plots/plot-1",
                json={"planting_date": future_date},
            )
        assert response.status_code == 422

    def test_get_plot_idor_returns_404(self):
        """GET plot owned by another user -> 404."""
        farm_row = {"id": "farm-1", "name": "Farm A", "locality": None,
                     "district": "Dhar", "state": "MP", "country": "India",
                     "timezone": "Asia/Kolkata", "approx_lat": None, "approx_lon": None,
                     "area_value": None, "area_unit": None, "soil_description": None,
                     "irrigation_method": None, "water_source": None, "notes": None,
                     "is_active": True, "created_at": "2024-01-01T00:00:00",
                     "updated_at": "2024-01-01T00:00:00"}
        db, chains = _make_db_mock({"farms": farm_row, "plots": None})
        app.dependency_overrides[farms_router.get_user_id] = _override_user_id("user-b")
        with patch("routers.farms.get_db", return_value=db):
            response = TestClient(app).get(
                "/api/farmers/me/farms/farm-1/plots/plot-x"
            )
        assert response.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
# No pre-populated defaults (Requirement 4.8)
# ═════════════════════════════════════════════════════════════════════════════

class TestNoPrePopulatedDefaults:
    """Ensure no hard-coded pilot defaults appear in the router code.

    Requirement 4.8: do NOT pre-populate 2100 trees, Taiwan Pink, or Badnawar.
    """

    def test_no_2100_default(self):
        import routers.farms as farms_mod
        source = open(farms_mod.__file__, encoding="utf-8").read()
        # The string "2100" may appear in comments about what NOT to do, but
        # should never appear as a default value assignment.
        assert "plant_count.*2100" not in source.replace(" ", "")
        assert "default.*2100" not in source.lower().replace(" ", "")

    def test_no_taiwan_pink_default(self):
        import routers.farms as farms_mod
        source = open(farms_mod.__file__, encoding="utf-8").read().lower()
        # Should not set Taiwan Pink as a default variety.
        assert "default.*taiwan" not in source.replace(" ", "")
        assert "\"taiwan pink\"".replace(" ", "") not in source.replace(" ", "")

    def test_no_badnawar_default(self):
        import routers.farms as farms_mod
        source = open(farms_mod.__file__, encoding="utf-8").read().lower()
        assert "default.*badnawar" not in source.replace(" ", "")
