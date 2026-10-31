"""
auth.py — JWT verification for all protected endpoints.

Verifies Supabase-issued JWTs using the project's JWKS endpoint.
Supports both the current ECC (P-256) signing key and the legacy HS256
shared secret, so it works regardless of which key type the project uses.

Exposes get_user_id() as a FastAPI Depends() dependency.

Security: ALL validation failures return HTTP 401 with the generic detail
"Invalid token" — the specific check that failed is never disclosed to the
caller. This prevents enumeration of which validation step was bypassed.
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

# JWKS endpoint — Supabase publishes public signing keys here.
# PyJWKClient caches the keys so repeated requests do not hit the network.
_JWKS_URL = f"{_SUPABASE_URL}/auth/v1/.well-known/jwks.json"
_jwks_client = PyJWKClient(_JWKS_URL, cache_keys=True)

# Expected issuer — Supabase JWTs set iss to <project-url>/auth/v1.
# Validated explicitly to prevent tokens from other Supabase projects
# (or any other issuer) being accepted.
_EXPECTED_ISSUER = f"{_SUPABASE_URL}/auth/v1"

# Legacy HS256 fallback — only used if SUPABASE_JWT_SECRET is set.
# Leave blank if the project has rotated to ECC keys.
_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")

# Shared validation error — NEVER customise the detail per failure type.
# Returning different messages for "expired", "wrong audience", "bad
# signature", etc. would let an attacker probe which check is failing.
_INVALID_TOKEN = HTTPException(status_code=401, detail="Invalid token")


def get_user_id(authorization: str = Header(...)) -> str:
    """Verify Supabase JWT and return the user_id (sub claim).

    Four mandatory checks are enforced on every path:
      1. Signature   — token is signed by a key in the Supabase JWKS endpoint
                       (asymmetric path) or by SUPABASE_JWT_SECRET (HS256
                       fallback). Tampering with the header or payload raises
                       InvalidSignatureError.
      2. Issuer      — iss claim must equal <SUPABASE_URL>/auth/v1.
                       Tokens from other projects or issuers are rejected.
      3. Audience    — aud claim must contain "authenticated".
                       Service-role tokens (aud="service_role") are rejected.
      4. Expiry      — exp claim must be in the future (PyJWT default).
                       Expired tokens are rejected regardless of signature.

    All failure paths raise HTTPException(status_code=401, detail="Invalid
    token") — the specific check that failed is logged at DEBUG level only
    and is never included in the HTTP response.

    Compatible with FastAPI Depends().
    """
    # Strip "Bearer " prefix; reject empty/malformed Authorization header.
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise _INVALID_TOKEN

    # ── Check 1 + 2 + 3 + 4: JWKS path (asymmetric keys) ────────────────────
    # PyJWT's decode() enforces all four checks automatically when the
    # options below are left at their secure defaults (verify_signature=True,
    # verify_exp=True, verify_aud=True) and issuer is provided explicitly.
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],  # Check 1: signature (JWKS)
            audience="authenticated",        # Check 3: audience == "authenticated"
            issuer=_EXPECTED_ISSUER,         # Check 2: issuer == <supabase-url>/auth/v1
            # Check 4: expiry is enforced by default (options["verify_exp"] = True)
            options={
                "verify_signature": True,    # Check 1: never skip signature
                "verify_exp": True,          # Check 4: never skip expiry
                "verify_aud": True,          # Check 3: never skip audience
                "verify_iss": True,          # Check 2: never skip issuer
            },
        )
        # sub must be present; missing sub means the token is malformed.
        sub = payload.get("sub")
        if not sub:
            logger.debug("JWKS path: 'sub' claim missing from token payload")
            raise _INVALID_TOKEN
        return sub
    except HTTPException:
        raise
    except Exception as jwks_err:
        # Log the specific error internally at DEBUG only — never expose it.
        logger.debug("JWKS verification failed: %s", jwks_err)

    # ── Check 1 + 2 + 3 + 4: HS256 fallback (legacy shared secret) ──────────
    # Only attempted when SUPABASE_JWT_SECRET is configured. The same four
    # checks are applied: PyJWT enforces signature, expiry, and audience;
    # issuer is validated explicitly.
    if _JWT_SECRET:
        try:
            payload = jwt.decode(
                token,
                _JWT_SECRET,
                algorithms=["HS256"],       # Check 1: signature (shared secret)
                audience="authenticated",   # Check 3: audience == "authenticated"
                issuer=_EXPECTED_ISSUER,    # Check 2: issuer == <supabase-url>/auth/v1
                # Check 4: expiry is enforced by default (options["verify_exp"] = True)
                options={
                    "verify_signature": True,  # Check 1: never skip signature
                    "verify_exp": True,         # Check 4: never skip expiry
                    "verify_aud": True,         # Check 3: never skip audience
                    "verify_iss": True,         # Check 2: never skip issuer
                },
            )
            # sub must be present; missing sub means the token is malformed.
            sub = payload.get("sub")
            if not sub:
                logger.debug("HS256 path: 'sub' claim missing from token payload")
                raise _INVALID_TOKEN
            return sub
        except HTTPException:
            raise
        except Exception as hs_err:
            # Log the specific error internally at DEBUG only — never expose it.
            logger.debug("HS256 verification failed: %s", hs_err)

    # All verification paths exhausted — return generic 401.
    raise _INVALID_TOKEN
