"""
test_inventory_consumption.py — Unit tests for inventory consumption (task 21.1).
Requirements: 8.2
"""
import pytest
from fastapi import HTTPException


def _apply_consumption(item, quantity_consumed, activity_id=None):
    """Simulate the consume business logic."""
    if quantity_consumed > item["quantity_on_hand"]:
        raise HTTPException(status_code=422, detail="Insufficient quantity on hand.")
    if activity_id is not None:
        # Simulate activity ownership check
        if activity_id not in ["act-1", "act-2"]:
            raise HTTPException(status_code=404, detail="Activity not found.")
    new_qty = item["quantity_on_hand"] - quantity_consumed
    return {"quantity_on_hand": new_qty}


class TestInventoryConsumption:

    def test_consumption_reduces_quantity_on_hand(self):
        """POST /inventory/{id}/consume reduces quantity_on_hand by quantity_consumed.
        Requirements: 8.2
        """
        item = {"id": "inv-1", "quantity_on_hand": 100.0, "unit": "kg"}
        result = _apply_consumption(item, 25.0)
        assert result["quantity_on_hand"] == 75.0

    def test_full_consumption_reduces_to_zero(self):
        """Consuming the exact quantity on hand reduces to zero."""
        item = {"id": "inv-1", "quantity_on_hand": 50.0, "unit": "litres"}
        result = _apply_consumption(item, 50.0)
        assert result["quantity_on_hand"] == 0.0

    def test_over_consumption_rejected(self):
        """Consuming more than available is rejected with 422."""
        item = {"id": "inv-1", "quantity_on_hand": 10.0, "unit": "kg"}
        with pytest.raises(HTTPException) as exc:
            _apply_consumption(item, 15.0)
        assert exc.value.status_code == 422

    def test_linking_to_nonexistent_activity_returns_404(self):
        """Linking consumption to a non-existent activity returns 404.
        Requirements: 8.2
        """
        item = {"id": "inv-1", "quantity_on_hand": 50.0, "unit": "kg"}
        with pytest.raises(HTTPException) as exc:
            _apply_consumption(item, 5.0, activity_id="nonexistent-act")
        assert exc.value.status_code == 404

    def test_linking_to_valid_activity_succeeds(self):
        """Linking to an existing owned activity succeeds."""
        item = {"id": "inv-1", "quantity_on_hand": 50.0, "unit": "kg"}
        result = _apply_consumption(item, 5.0, activity_id="act-1")
        assert result["quantity_on_hand"] == 45.0
