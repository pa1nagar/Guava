"""
vendors.py — Vendor recommendation endpoints.

GET  /api/farmers/me/vendor-recommendations   Consent-gated, gap-driven.
PUT  /api/farmers/me/vendor-consent           Opt in or opt out.
"""

import json
import logging
import pathlib
from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from services.auth import get_user_id
from services.db import get_db
from services.gap_engine import compute_gaps

logger = logging.getLogger(__name__)

router = APIRouter()

_KNOWLEDGE_PATH = pathlib.Path(__file__).parent.parent / "data" / "crop_knowledge.json"
_knowledge_cache: dict | None = None


def _get_knowledge() -> dict:
    global _knowledge_cache
    if _knowledge_cache is None:
        _knowledge_cache = json.loads(_KNOWLEDGE_PATH.read_text(encoding="utf-8"))
    return _knowledge_cache


# ── Models ────────────────────────────────────────────────────────────────────

class VendorCard(BaseModel):
    vendor_name: str
    district: str
    state: str
    phone: str
    contact_method: str
    product_types: List[str]
    input_needed: str
    quantity_needed: float
    unit: str


class ConsentIn(BaseModel):
    consent: bool


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_farmer(user_id: str) -> dict:
    db = get_db()
    try:
        result = (
            db.table("farmers")
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
    db = get_db()
    try:
        result = (
            db.table("farm_activities")
            .select("*")
            .eq("farmer_id", farmer_id)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.error("DB select activities failed: %s", exc)
        return []


def _find_vendors(district: str, product_type: str) -> list[dict]:
    db = get_db()
    try:
        result = (
            db.table("vendors")
            .select("*")
            .eq("district", district)
            .execute()
        )
        vendors = result.data or []
        return [
            v for v in vendors
            if product_type in (v.get("product_types") or [])
        ][:3]
    except Exception as exc:
        logger.error("DB select vendors failed: %s", exc)
        return []


# ── GET /api/farmers/me/vendor-recommendations ───────────────────────────────

@router.get("/farmers/me/vendor-recommendations", response_model=List[VendorCard])
def vendor_recommendations(user_id: str = Depends(get_user_id)) -> List[VendorCard]:
    """Return vendor cards matched to actual input gaps.

    Returns empty list (not 403) when consent is not given.
    """
    farmer = _get_farmer(user_id)

    if not farmer.get("vendor_recommendation_consent", False):
        return []

    sowing_date = (
        date.fromisoformat(farmer["sowing_date"])
        if isinstance(farmer["sowing_date"], str)
        else farmer["sowing_date"]
    )

    try:
        from services import stage as stage_service  # noqa: PLC0415
        sr = stage_service.get_stage(farmer["crop"], sowing_date)
    except Exception as exc:
        logger.warning("Could not determine stage for vendor matching: %s", exc)
        return []

    crop_stages = _get_knowledge()[farmer["crop"].lower()]["stages"]
    activities  = _get_activities(farmer["id"])

    gaps = compute_gaps(
        stages=crop_stages,
        months_elapsed=sr.months_elapsed,
        plant_count=farmer["plant_count"],
        activities=activities,
    )

    cards: list[VendorCard] = []
    seen_ids: set = set()

    for gap in gaps:
        if gap.status != "behind":
            continue
        for v in _find_vendors(farmer["district"], gap.activity_type):
            if v["id"] in seen_ids:
                continue
            seen_ids.add(v["id"])
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

    return cards[:3]


# ── PUT /api/farmers/me/vendor-consent ──────────────────────────────────────

@router.put("/farmers/me/vendor-consent")
def update_vendor_consent(
    body: ConsentIn,
    user_id: str = Depends(get_user_id),
) -> dict:
    """Update vendor recommendation consent.

    Withdrawing consent stops recommendations immediately.
    """
    db = get_db()
    now_utc = datetime.now(timezone.utc).isoformat()
    update_payload: dict = {"vendor_recommendation_consent": body.consent}
    if body.consent:
        update_payload["vendor_recommendation_consent_at"] = now_utc

    try:
        db.table("farmers").update(update_payload).eq("user_id", user_id).execute()
    except Exception as exc:
        logger.error("DB update consent failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    return {"status": "saved", "consent": body.consent}
