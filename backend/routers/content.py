"""
routers/content.py — Admin-only content governance endpoints.

Endpoints:
  POST /api/admin/run-expiry-check
      Triggers the daily expiry scheduler on demand.
      Guarded by the X-Service-Secret header.

Requirements: 1.3, 1.4
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Header, HTTPException

from services.content_governance import check_and_expire_records
from services.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["content-admin"])


@router.post("/run-expiry-check")
def run_expiry_check(
    x_service_secret: str | None = Header(default=None, alias="X-Service-Secret"),
) -> dict:
    """Trigger the content-record expiry scheduler on demand.

    Called by a Render cron job (or any trusted service) using the shared
    SERVICE_SECRET environment variable. No JWT auth is used here — the
    secret header is the sole access control.

    Returns the number of records expired in this run.

    Security:
    - Requires X-Service-Secret header matching SERVICE_SECRET env var.
    - Returns 401 (not 403) on mismatch to avoid confirming the endpoint
      exists to unauthenticated callers.
    """
    expected_secret = os.environ.get("SERVICE_SECRET", "").strip()

    # Require the env var to be set; an empty secret is never accepted.
    if not expected_secret:
        logger.error(
            "run-expiry-check called but SERVICE_SECRET is not configured."
        )
        raise HTTPException(
            status_code=503,
            detail="Expiry check is not configured.",
        )

    if x_service_secret != expected_secret:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
        )

    db = get_db()
    try:
        expired_count = check_and_expire_records(db)
    except Exception as exc:
        logger.error("Expiry check failed: %s", exc)
        raise HTTPException(status_code=500, detail="Internal error.")

    logger.info("Expiry check complete — %d record(s) expired.", expired_count)
    return {"expired_count": expired_count}
