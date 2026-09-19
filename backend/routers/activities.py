"""
activities.py — Farm activity ledger endpoints.

GET  /api/farmers/me/activities      List all activities for the farmer.
POST /api/farmers/me/activities      Log a new activity.
GET  /api/farmers/me/spending        Total spend + breakdown by type.
GET  /api/farmers/me/gaps            Expected-vs-actual input gaps.
GET  /api/constants/activity-types   Canonical activity type list.

Business rules enforced here:
  - Irrigation has zero cost (water is free). Any submitted cost is overridden to 0.
  - activity_type must be in the authoritative ACTIVITY_TYPES list.
  - quantity >= 0, cost >= 0.
"""

import json
import logging
import pathlib
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from services.auth import get_user_id
from services.constants import ACTIVITY_TYPES, ZERO_COST_ACTIVITY_TYPES
from services.db import get_db
from services.financials import total_cost, cost_by_activity_type
from services.gap_engine import compute_gaps
from services import stage as stage_service

logger = logging.getLogger(__name__)

router = APIRouter()

# Load crop knowledge once at module level — not on every request.
_KNOWLEDGE_PATH = pathlib.Path(__file__).parent.parent / "data" / "crop_knowledge.json"
_knowledge_cache: dict | None = None


def _get_knowledge() -> dict:
    global _knowledge_cache
    if _knowledge_cache is None:
        _knowledge_cache = json.loads(_KNOWLEDGE_PATH.read_text(encoding="utf-8"))
    return _knowledge_cache


# ── Models ────────────────────────────────────────────────────────────────────

class ActivityIn(BaseModel):
    activity_type: str
    quantity: float = Field(ge=0, description="Quantity applied. Must be >= 0.")
    unit: Optional[str] = None
    cost: float = Field(ge=0, description="Cost in INR. Must be >= 0.")
    notes: Optional[str] = None


class ActivityOut(BaseModel):
    id: str
    activity_type: str
    quantity: float
    unit: Optional[str]
    cost: float
    notes: Optional[str]
    logged_date: str
    created_at: str


class SpendingOut(BaseModel):
    total_cost: float
    by_type: dict
    currency: str = "INR"


class GapOut(BaseModel):
    activity_type: str
    expected: float
    actual: float
    gap: float
    unit: str
    status: str
    message: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_farmer(user_id: str) -> dict:
    db = get_db()
    try:
        result = (
            db.table("farmers")
            .select("id, crop, plant_count, sowing_date")
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
            .order("logged_date", desc=False)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.error("DB select activities failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")


# ── GET /api/farmers/me/activities ───────────────────────────────────────────

@router.get("/farmers/me/activities", response_model=List[ActivityOut])
def list_activities(user_id: str = Depends(get_user_id)) -> List[ActivityOut]:
    farmer = _get_farmer(user_id)
    activities = _get_activities(farmer["id"])
    return [
        ActivityOut(
            id=a["id"],
            activity_type=a["activity_type"],
            quantity=float(a["quantity"]),
            unit=a.get("unit"),
            cost=float(a["cost"]),
            notes=a.get("notes"),
            logged_date=str(a["logged_date"]),
            created_at=str(a["created_at"]),
        )
        for a in activities
    ]


# ── POST /api/farmers/me/activities ──────────────────────────────────────────

@router.post("/farmers/me/activities", response_model=ActivityOut)
def log_activity(
    body: ActivityIn,
    user_id: str = Depends(get_user_id),
) -> ActivityOut:
    """Log a farm activity.

    Irrigation cost is always stored as 0 regardless of what was submitted.
    This enforces the product rule: water has no cost.
    """
    db = get_db()

    if body.activity_type not in ACTIVITY_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"activity_type must be one of: {', '.join(ACTIVITY_TYPES)}",
        )

    # Enforce zero cost for irrigation — backend rule, not just a frontend hint.
    effective_cost = 0.0 if body.activity_type in ZERO_COST_ACTIVITY_TYPES else body.cost

    farmer = _get_farmer(user_id)

    payload = {
        "farmer_id":     farmer["id"],
        "activity_type": body.activity_type,
        "quantity":      body.quantity,
        "unit":          body.unit,
        "cost":          effective_cost,
        "notes":         body.notes,
        "logged_date":   str(date.today()),
    }

    try:
        result = db.table("farm_activities").insert(payload).execute()
    except Exception as exc:
        logger.error("DB insert activity failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    row = result.data[0]
    return ActivityOut(
        id=row["id"],
        activity_type=row["activity_type"],
        quantity=float(row["quantity"]),
        unit=row.get("unit"),
        cost=float(row["cost"]),
        notes=row.get("notes"),
        logged_date=str(row["logged_date"]),
        created_at=str(row["created_at"]),
    )


# ── GET /api/farmers/me/spending ─────────────────────────────────────────────

@router.get("/farmers/me/spending", response_model=SpendingOut)
def get_spending(user_id: str = Depends(get_user_id)) -> SpendingOut:
    farmer = _get_farmer(user_id)
    activities = _get_activities(farmer["id"])
    return SpendingOut(
        total_cost=round(total_cost(activities), 2),
        by_type={k: round(v, 2) for k, v in cost_by_activity_type(activities).items()},
    )


# ── GET /api/farmers/me/gaps ─────────────────────────────────────────────────

@router.get("/farmers/me/gaps", response_model=List[GapOut])
def get_gaps(user_id: str = Depends(get_user_id)) -> List[GapOut]:
    farmer = _get_farmer(user_id)

    sowing_date = (
        date.fromisoformat(farmer["sowing_date"])
        if isinstance(farmer["sowing_date"], str)
        else farmer["sowing_date"]
    )

    try:
        sr = stage_service.get_stage(farmer["crop"], sowing_date)
    except (HTTPException, KeyError) as exc:
        raise HTTPException(status_code=422, detail="Cannot determine crop stage.") from exc

    crop_stages = _get_knowledge()[farmer["crop"].lower()]["stages"]
    activities = _get_activities(farmer["id"])

    gaps = compute_gaps(
        stages=crop_stages,
        months_elapsed=sr.months_elapsed,
        plant_count=farmer["plant_count"],
        activities=activities,
    )

    output = []
    for g in gaps:
        message = None
        if g.status == "behind":
            message = f"You may be behind on {g.activity_type.lower()} for this stage."
        output.append(GapOut(
            activity_type=g.activity_type,
            expected=g.expected_kg_or_litres,
            actual=g.actual_kg_or_litres,
            gap=g.gap,
            unit=g.unit,
            status=g.status,
            message=message,
        ))

    return output


# ── GET /api/constants/activity-types ────────────────────────────────────────

@router.get("/constants/activity-types")
def get_activity_types() -> dict:
    """Return the allowed activity types so frontend stays in sync."""
    return {"activity_types": ACTIVITY_TYPES}
