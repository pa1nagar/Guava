"""
vendors.py — Vendor recommendation endpoints.

GET  /api/farmers/me/vendor-recommendations   Return matched vendors (consent-gated).
PUT  /api/farmers/me/vendor-consent           Update vendor recommendation consent.

Vendor matching is based on actual computed input gaps — not generic advertising.
Only farmers who have opted in can receive vendor cards.
"""

import logging
import os
from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import Client, create_client

from services.auth import get_user_id
from services.gap_engine import compute_gaps

import json
import pathlib

logger = logging.getLogger(__name__)

router = APIRouter()

_SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
_SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
if not _SUPABASE_URL or not _SUPABASE_SERVICE_KEY:
    raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_KEY not set.")

_db: Client = create_client(_SUPABASE_URL, _SUPABASE_SERVICE_KEY)

_KNOWLEDGE_PATH = pathlib.Path(__file__).parent.parent / "data" / "crop_knowledge.json"


# ── Models ────────────────────────────────────────────────────────────────────

class VendorCard(BaseModel):
    vendor_name: str
    district: str
    state: str
    phone: str
    contact_method: str      # "call" | "whatsapp" | "both"
    product_types: List[str]
    input_needed: str        # the specific input gap that triggered this match
    quantity_needed: float
    unit: str


class ConsentIn(BaseModel):
    consent: bool


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_farmer(user_id: str) -> dict:
    try:
        result = (
            _db.table("farmers")
            .select(
                "id, crop, plant_count, sowing_date, district, state, "
                "vendor_recommendation_consent"
            )
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        logger.error("DB select failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")
    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return result.data


def _get_activities(farmer_id: str) -> list[dict]:
    try:
        result = (
            _db.table("farm_activities")
            .select("*")
            .eq("farmer_id", farmer_id)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.error("DB select activities failed: %s", exc)
        return []


def _find_vendors(district: str, product_type: str) -> list[dict]:
    """Query vendors table for matching district + product_type."""
    try:
        result = (
            _db.table("vendors")
            .select("*")
            .eq("district", district)
            .execute()
        )
        vendors = result.data or []
        # Filter by product_type membership in the product_types array.
        return [
            v for v in vendors
            if product_type in (v.get("product_types") or [])
        ][:3]  # Show at most 3 vendors.
    except Exception as exc:
        logger.error("DB select vendors failed: %s", exc)
        return []


# ── GET /api/farmers/me/vendor-recommendations ────────────────────────────────

@router.get("/farmers/me/vendor-recommendations", response_model=List[VendorCard])
def vendor_recommendations(user_id: str = Depends(get_user_id)) -> List[VendorCard]:
    """Return vendor cards based on actual computed input gaps.

    Only runs if:
      1. Farmer has explicitly opted in to vendor recommendations.
      2. There is an actual "behind" gap for a trackable input type.

    Returns an empty list (not 403) if consent is not given.
    """
    farmer = _get_farmer(user_id)

    # ── Consent gate — return empty silently if not opted in ─────────────────
    if not farmer.get("vendor_recommendation_consent", False):
        return []

    # ── Compute gaps ──────────────────────────────────────────────────────────
    sowing_date = (
        date.fromisoformat(farmer["sowing_date"])
        if isinstance(farmer["sowing_date"], str)
        else farmer["sowing_date"]
    )

    try:
        from services import stage as stage_service
        sr = stage_service.get_stage(farmer["crop"], sowing_date)
    except Exception as exc:
        logger.warning("Could not determine stage for vendor matching: %s", exc)
        return []

    knowledge = json.loads(_KNOWLEDGE_PATH.read_text(encoding="utf-8"))
    crop_stages = knowledge[farmer["crop"].lower()]["stages"]
    activities = _get_activities(farmer["id"])

    gaps = compute_gaps(
        stages=crop_stages,
        months_elapsed=sr.months_elapsed,
        plant_count=farmer["plant_count"],
        activities=activities,
    )

    # ── Match vendors for each "behind" gap ───────────────────────────────────
    cards: List[VendorCard] = []
    seen_vendor_ids: set = set()

    for gap in gaps:
        if gap.status != "behind":
            continue

        vendors = _find_vendors(farmer["district"], gap.activity_type)
        for v in vendors:
            if v["id"] in seen_vendor_ids:
                continue
            seen_vendor_ids.add(v["id"])
            cards.append(VendorCard(
                vendor_name=v["vendor_name"],
                district=v["district"],
                state=v["state"],
                phone=v["phone"],
                contact_method=v.get("contact_method", "call"),
                product_types=v.get("product_types", []),
                input_needed=gap.activity_type,
                quantity_needed=gap.gap,
                unit=gap.unit,
            ))

    return cards[:3]  # Cap total cards shown at 3.


# ── PUT /api/farmers/me/vendor-consent ───────────────────────────────────────

@router.put("/farmers/me/vendor-consent")
def update_vendor_consent(
    body: ConsentIn,
    user_id: str = Depends(get_user_id),
) -> dict:
    """Update vendor recommendation consent.

    When consent is withdrawn (false), vendor recommendations stop immediately.
    """
    now_utc = datetime.now(timezone.utc).isoformat()
    update_payload: dict = {"vendor_recommendation_consent": body.consent}
    if body.consent:
        update_payload["vendor_recommendation_consent_at"] = now_utc

    try:
        _db.table("farmers").update(update_payload).eq("user_id", user_id).execute()
    except Exception as exc:
        logger.error("DB update consent failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    return {"status": "saved", "consent": body.consent}
