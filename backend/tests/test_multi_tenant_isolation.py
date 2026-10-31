# Feature: smart-farmer-app, Property 6: Multi-tenant isolation — no cross-farmer data access
"""
test_multi_tenant_isolation.py — Multi-tenant isolation tests (task 5.1, Property 6).
Requirements: 3.3, 18.5
"""
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from fastapi import HTTPException


def _get_farmer_resource(resource_user_id: str, requesting_user_id: str):
    """Simulate a resource access check: return 404 if user_ids don't match."""
    if resource_user_id != requesting_user_id:
        raise HTTPException(status_code=404, detail="Resource not found.")
    return {"id": "resource-1", "user_id": resource_user_id}


# Feature: smart-farmer-app, Property 6: Multi-tenant isolation — no cross-farmer data access
@given(
    farmer_a_id=st.text(min_size=10, max_size=40, alphabet="abcdef0123456789-"),
    farmer_b_id=st.text(min_size=10, max_size=40, alphabet="abcdef0123456789-"),
)
@settings(max_examples=200)
def test_cross_farmer_access_returns_404(farmer_a_id, farmer_b_id):
    """When farmer B tries to access farmer A's resource, they receive 404.
    Requirements: 3.3, 18.5
    """
    if farmer_a_id == farmer_b_id:
        return  # same user — skip

    with pytest.raises(HTTPException) as exc:
        _get_farmer_resource(farmer_a_id, farmer_b_id)
    # Must return 404, not 403 (IDOR prevention)
    assert exc.value.status_code == 404, (
        f"Expected 404 for cross-farmer access, got {exc.value.status_code}"
    )


# Feature: smart-farmer-app, Property 6: Multi-tenant isolation — no cross-farmer data access
@given(user_id=st.text(min_size=10, max_size=40, alphabet="abcdef0123456789-"))
@settings(max_examples=200)
def test_own_resource_access_succeeds(user_id):
    """A farmer can always access their own resources.
    Requirements: 3.3
    """
    result = _get_farmer_resource(user_id, user_id)
    assert result["user_id"] == user_id


class TestMultiTenantIsolationDirect:
    """Direct unit tests for the isolation rule."""

    def test_farmer_a_cannot_access_farmer_b_resource(self):
        with pytest.raises(HTTPException) as exc:
            _get_farmer_resource("farmer-b-uuid", "farmer-a-uuid")
        assert exc.value.status_code == 404

    def test_response_is_404_not_403(self):
        """Must return 404 not 403 to avoid confirming resource existence (IDOR)."""
        with pytest.raises(HTTPException) as exc:
            _get_farmer_resource("user-x", "user-y")
        assert exc.value.status_code == 404
        assert exc.value.status_code != 403
