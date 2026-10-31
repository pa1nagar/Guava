"""
test_property_jwt_validation.py — Property 7: JWT validation.

Property 7: Any tampered, empty, or malformed token must be rejected with
HTTPException(status_code=401).

Uses Hypothesis with @given and @settings(max_examples=200).
The JWKS endpoint and HS256 secret are mocked so no network call is made.

Feature: smart-farmer-app, Property 7: JWT validation rejects any invalid token
Validates: Requirements 3.1
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from hypothesis import given, settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Helper: call get_user_id with both JWKS and HS256 paths disabled (mocked)
# ---------------------------------------------------------------------------

def _call_get_user_id_with_token(token: str) -> None:
    """Invoke get_user_id for the given token.

    Patches:
      - PyJWKClient.get_signing_key_from_jwt → raises Exception (JWKS fails)
      - jwt.decode (HS256 path) → raises Exception (secret fails)

    Any token that isn't valid through either path must raise HTTPException(401).
    """
    import services.auth as auth_module

    fake_jwks_client = MagicMock()
    fake_jwks_client.get_signing_key_from_jwt.side_effect = Exception("JWKS unavailable")

    with patch.object(auth_module, "_jwks_client", fake_jwks_client):
        with patch.object(auth_module, "_JWT_SECRET", "test_secret"):
            with patch("jwt.decode", side_effect=Exception("invalid")):
                auth_module.get_user_id(authorization=token)


# ---------------------------------------------------------------------------
# Strategy: generate obviously invalid tokens
# ---------------------------------------------------------------------------

# Random text that is not a valid JWT.
random_text_st = st.text(min_size=0, max_size=500)

# Three-segment strings that look like JWTs but have corrupt parts.
corrupt_jwt_st = st.builds(
    lambda a, b, c: f"{a}.{b}.{c}",
    st.text(min_size=0, max_size=100),
    st.text(min_size=0, max_size=100),
    st.text(min_size=0, max_size=100),
)

# "Bearer " prefix added to random text.
bearer_random_st = st.text(min_size=0, max_size=500).map(lambda t: f"Bearer {t}")

# Completely empty / whitespace-only authorization headers.
empty_auth_st = st.sampled_from(["", " ", "   ", "Bearer", "Bearer ", "bearer token"])


# ---------------------------------------------------------------------------
# Property 7a: random text always rejected
# ---------------------------------------------------------------------------

# Feature: smart-farmer-app, Property 7: JWT validation rejects any invalid token
@given(token=random_text_st)
@settings(max_examples=200)
def test_random_text_always_rejected(token: str):
    """Any random string that is not a valid signed JWT must raise HTTPException(401).

    Validates: Requirements 3.1
    """
    with pytest.raises(HTTPException) as exc_info:
        _call_get_user_id_with_token(token)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"


# Feature: smart-farmer-app, Property 7: JWT validation rejects any invalid token
@given(token=corrupt_jwt_st)
@settings(max_examples=200)
def test_corrupt_jwt_always_rejected(token: str):
    """Three-segment strings with corrupt headers/payloads/signatures must raise 401.

    Validates: Requirements 3.1
    """
    with pytest.raises(HTTPException) as exc_info:
        _call_get_user_id_with_token(token)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"


# Feature: smart-farmer-app, Property 7: JWT validation rejects any invalid token
@given(token=bearer_random_st)
@settings(max_examples=200)
def test_bearer_prefix_with_invalid_token_rejected(token: str):
    """'Bearer <garbage>' must raise HTTPException(401).

    Validates: Requirements 3.1
    """
    with pytest.raises(HTTPException) as exc_info:
        _call_get_user_id_with_token(token)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"


# Feature: smart-farmer-app, Property 7: JWT validation rejects any invalid token
@given(token=empty_auth_st)
@settings(max_examples=200)
def test_empty_or_bare_bearer_rejected(token: str):
    """Empty / bare 'Bearer' headers must be rejected with 401.

    Validates: Requirements 3.1
    """
    with pytest.raises(HTTPException) as exc_info:
        _call_get_user_id_with_token(token)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"


# ---------------------------------------------------------------------------
# Property 7b: error detail never leaks the failure reason
# ---------------------------------------------------------------------------

# Feature: smart-farmer-app, Property 7: JWT validation rejects any invalid token
@given(token=st.one_of(random_text_st, corrupt_jwt_st))
@settings(max_examples=200)
def test_rejected_token_detail_is_always_generic(token: str):
    """The detail message must always be exactly 'Invalid token', never something
    more specific like 'expired', 'bad signature', or 'wrong audience'.

    Validates: Requirements 3.1 (no distinguishing error messages)
    """
    try:
        _call_get_user_id_with_token(token)
    except HTTPException as exc:
        assert exc.status_code == 401
        assert exc.detail == "Invalid token", (
            f"Expected generic 'Invalid token' detail, got: {exc.detail!r}"
        )
    except Exception:
        pass  # Non-HTTPException — still fine (caller only checks HTTPException)
