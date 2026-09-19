"""
auth.py — JWT verification for all protected endpoints.

Verifies Supabase-issued JWTs using the project's JWKS endpoint.
Supports both the current ECC (P-256) signing key and the legacy HS256
shared secret, so it works regardless of which key type the project uses.

Exposes get_user_id() as a FastAPI Depends() dependency.
"""

import os
import logging

import jwt
from jwt import PyJWKClient
from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
_SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
if not _SUPABASE_URL:
    raise RuntimeError(
        "SUPABASE_URL environment variable is not set. "
        "Add it to your .env file and restart the server."
    )

# JWKS endpoint — Supabase publishes public keys here.
_JWKS_URL = f"{_SUPABASE_URL}/auth/v1/.well-known/jwks.json"
_jwks_client = PyJWKClient(_JWKS_URL, cache_keys=True)

# Legacy HS256 fallback — only used if SUPABASE_JWT_SECRET is set.
# Leave blank if you have rotated to ECC keys.
_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")


def get_user_id(authorization: str = Header(...)) -> str:
    """Verify Supabase JWT and return the user_id (sub claim).

    Tries JWKS verification first (works with ECC P-256 and RSA keys).
    Falls back to HS256 shared secret if SUPABASE_JWT_SECRET is set.

    Raises HTTPException 401 on any validation failure.
    Compatible with FastAPI Depends().
    """
    token = authorization.removeprefix("Bearer ").strip()

    # ── Try JWKS (asymmetric) verification first ──────────────────────────────
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
        )
        return payload["sub"]
    except Exception as jwks_err:
        logger.debug("JWKS verification failed: %s", jwks_err)

    # ── Fall back to HS256 shared secret ──────────────────────────────────────
    if _JWT_SECRET:
        try:
            payload = jwt.decode(
                token,
                _JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
            )
            return payload["sub"]
        except jwt.PyJWTError as hs_err:
            logger.debug("HS256 verification failed: %s", hs_err)

    raise HTTPException(status_code=401, detail="Invalid token")
