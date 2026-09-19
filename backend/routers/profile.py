"""
profile.py — POST /api/profile  |  GET /api/farmers/me

Saves or updates the farmer's profile in the farmers table.
Clears the cached plan whenever plan-relevant profile fields change.
"""

import logging
import os
from datetime import date
from typing import Optional

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


# ── Request / response models ─────────────────────────────────────────────────

class ProfileIn(BaseModel):
    crop: str
    plant_count: int = Field(gt=0, description="Number of plants, must be ≥ 1")
    state: str
    district: str
    sowing_date: date
    expected_yield_kg: Optional[float] = Field(
        default=None,
        gt=0,
        description="Optional. Total expected harvest in kg for this crop cycle.",
    )


class ProfileOut(BaseModel):
    id: str
    crop: str
    plant_count: int
    state: str
    district: str
    sowing_date: str
    expected_yield_kg: Optional[float]
    vendor_recommendation_consent: bool


# ── GET /api/farmers/me ───────────────────────────────────────────────────────

@router.get("/farmers/me", response_model=ProfileOut)
def get_profile(user_id: str = Depends(get_user_id)) -> ProfileOut:
    """Return the authenticated farmer's profile.

    Returns 404 if no profile exists (frontend should redirect to onboarding).
    """
    try:
        result = (
            _db.table("farmers")
            .select(
                "id, crop, plant_count, state, district, sowing_date, "
                "expected_yield_kg, vendor_recommendation_consent"
            )
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        logger.error("Supabase select failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    if result is None or not result.data:
        raise HTTPException(status_code=404, detail="Profile not found.")

    row = result.data
    return ProfileOut(
        id=row["id"],
        crop=row["crop"],
        plant_count=row["plant_count"],
        state=row["state"],
        district=row["district"],
        sowing_date=str(row["sowing_date"]),
        expected_yield_kg=row.get("expected_yield_kg"),
        vendor_recommendation_consent=row.get("vendor_recommendation_consent", False),
    )


# ── POST /api/profile  (also accepts PUT via alias) ───────────────────────────

@router.post("/profile")
@router.put("/profile")
def save_profile(
    body: ProfileIn,
    user_id: str = Depends(get_user_id),
) -> dict:
    """Upsert the farmer's profile.

    - Validates sowing_date is not in the future.
    - Computes a profile_hash; if it differs from the stored hash the
      cached_plan is cleared so GET /plan regenerates on next request.
    - Returns {"status": "saved"} on success.
    """
    # ── 1. Validate sowing date ───────────────────────────────────────────────
    if body.sowing_date > date.today():
        raise HTTPException(
            status_code=422,
            detail="Planting date cannot be in the future.",
        )

    # ── 2. Validate crop is known ─────────────────────────────────────────────
    from services.stage import _knowledge  # noqa: PLC0415
    if body.crop.lower() not in _knowledge:
        raise HTTPException(status_code=422, detail="Crop not supported.")

    # ── 3. Compute profile hash (covers plan-relevant fields only) ────────────
    new_hash = compute_profile_hash(
        body.crop,
        body.plant_count,
        body.state,
        body.district,
        body.sowing_date,
    )

    # ── 4. Fetch existing row ─────────────────────────────────────────────────
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
        "expected_yield_kg": body.expected_yield_kg,
        "profile_hash": new_hash,
    }
    # Clear cached plan whenever any plan-relevant profile field changes.
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
