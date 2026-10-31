"""
test_auth_edge_cases.py — Auth edge cases for task 3.2.
Requirements: 3.1
"""
import pytest
from fastapi import HTTPException
from unittest.mock import patch, MagicMock

from services.auth import get_user_id


def test_empty_token_raises_401():
    with pytest.raises(HTTPException) as exc:
        get_user_id("Bearer ")
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid token"


def test_missing_bearer_prefix_raises_401():
    with pytest.raises(HTTPException) as exc:
        get_user_id("not-a-bearer-token")
    # The token decode fails -> 401
    assert exc.value.status_code == 401


def test_malformed_jwt_raises_401():
    with pytest.raises(HTTPException) as exc:
        get_user_id("Bearer totally.not.a.jwt")
    assert exc.value.status_code == 401


def test_tampered_jwt_raises_401():
    # A structurally valid JWT but with a tampered signature
    tampered = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEiLCJhdWQiOiJhdXRoZW50aWNhdGVkIn0.TAMPERED_SIGNATURE"
    with pytest.raises(HTTPException) as exc:
        get_user_id(tampered)
    assert exc.value.status_code == 401


def test_all_401_responses_have_same_detail():
    """All auth failures return the same generic 'Invalid token' detail."""
    tokens = [
        "Bearer ",
        "Bearer garbage",
        "Bearer eyJhbGciOiJub25lIn0.eyJzdWIiOiJ0ZXN0In0.",
    ]
    for token in tokens:
        with pytest.raises(HTTPException) as exc:
            get_user_id(token)
        assert exc.value.detail == "Invalid token", (
            f"Token {token!r} returned detail={exc.value.detail!r}, expected 'Invalid token'"
        )
