"""
profile.py — POST /api/profile

Saves or updates the farmer's profile in the farmers table.
Clears the cached plan whenever profile fields change.
"""

import logging
import os
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from supabase import Client, create_client

from services.auth import get_user_id
from services.cache import compute_profile_hash

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Supabase service-role client (bypasses RLS for server-side writes) ────────
_SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
_SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
if not _SUPABASE_URL or not _SUPABASE_SERVICE_KEY:
    raise RuntimeError(
        "SUPABASE_URL or SUPABASE_SERVICE_KEY environment variable is not set. "
        "Add them to your .env file and restart the server."
    )

_db: Client = create_client(_SUPABASE_URL, _SUPABASE_SERVICE_KEY)


# ── Request model ─────────────────────────────────────────────────────────────

class ProfileIn(BaseModel):
    crop: str
    plant_count: int = Field(gt=0, description="Number of plants, must be ≥ 1")
    state: str
    district: str
    sowing_date: date


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/profile")
def save_profile(
    body: ProfileIn,
    user_id: str = Depends(get_user_id),
) -> dict:
    """Upsert the farmer's profile.

    - Validates sowing_date is not in the future (Req 5.6).
    - Computes a profile_hash; if it differs from the stored hash the
      cached_plan is cleared so GET /plan regenerates on next request.
    - Returns {"status": "saved"} on success.
    """
    # ── 1. Validate sowing date (server-side, Req 5.6) ───────────────────────
    if body.sowing_date > date.today():
        raise HTTPException(
            status_code=422,
            detail="Planting date cannot be in the future.",
        )

    # ── 2. Validate crop is known ─────────────────────────────────────────────
    # Import lazily to avoid circular imports; stage module already loaded JSON.
    from services.stage import _knowledge  # noqa: PLC0415
    if body.crop.lower() not in _knowledge:
        raise HTTPException(status_code=422, detail="Crop not supported.")

    # ── 3. Compute profile hash ───────────────────────────────────────────────
    new_hash = compute_profile_hash(
        body.crop,
        body.plant_count,
        body.state,
        body.district,
        body.sowing_date,
    )

    # ── 4. Fetch existing row (to check if hash changed) ─────────────────────
    try:
        existing = (
            _db.table("farmers")
            .select("profile_hash")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        logger.error("Supabase select failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    stored_hash = existing.data.get("profile_hash") if (existing and existing.data) else None
    hash_changed = stored_hash != new_hash

    # ── 5. Build upsert payload ───────────────────────────────────────────────
    payload: dict = {
        "user_id": user_id,
        "crop": body.crop.lower(),
        "plant_count": body.plant_count,
        "state": body.state,
        "district": body.district,
        "sowing_date": str(body.sowing_date),
        "profile_hash": new_hash,
    }
    # Clear cached plan whenever any profile field changes.
    if hash_changed:
        payload["cached_plan"] = None
        payload["plan_generated_at"] = None

    # ── 6. Upsert ─────────────────────────────────────────────────────────────
    try:
        _db.table("farmers").upsert(payload, on_conflict="user_id").execute()
    except Exception as exc:
        logger.error("Supabase upsert failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    return {"status": "saved"}
