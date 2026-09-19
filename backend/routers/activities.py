"""
activities.py — Farm activity ledger endpoints.

GET  /api/farmers/me/activities        List all activities for the farmer.
POST /api/farmers/me/activities        Log a new activity.
GET  /api/farmers/me/spending          Total spend + breakdown by type.
GET  /api/farmers/me/gaps              Expected-vs-actual input gaps.
"""

import logging
import os
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from supabase import Client, create_client

from services.auth import get_user_id
from services.constants import ACTIVITY_TYPES
from services.financials import total_cost, cost_by_activity_type
from services.gap_engine import compute_gaps
from services import stage as stage_service

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


# ── Request / response models ─────────────────────────────────────────────────

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
    status: str       # "behind" | "on_track" | "ahead"
    message: Optional[str] = None


# ── Helper: resolve farmer_id from user_id ────────────────────────────────────

def _get_farmer(user_id: str) -> dict:
    """Return the farmer row or raise 404."""
    try:
        result = (
            _db.table("farmers")
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
    try:
        result = (
            _db.table("farm_activities")
            .select("*")
            .eq("farmer_id", farmer_id)
            .order("logged_date", desc=False)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.error("DB select activities failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")


# ── GET /api/farmers/me/activities ────────────────────────────────────────────

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


# ── POST /api/farmers/me/activities ───────────────────────────────────────────

@router.post("/farmers/me/activities", response_model=ActivityOut)
def log_activity(
    body: ActivityIn,
    user_id: str = Depends(get_user_id),
) -> ActivityOut:
    """Log a farm activity for the authenticated farmer."""
    # Validate activity type against the authoritative list.
    if body.activity_type not in ACTIVITY_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"activity_type must be one of: {', '.join(ACTIVITY_TYPES)}",
        )

    farmer = _get_farmer(user_id)

    payload = {
        "farmer_id": farmer["id"],
        "activity_type": body.activity_type,
        "quantity": body.quantity,
        "unit": body.unit,
        "cost": body.cost,
        "notes": body.notes,
        "logged_date": str(date.today()),
    }

    try:
        result = _db.table("farm_activities").insert(payload).execute()
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


# ── GET /api/farmers/me/spending ──────────────────────────────────────────────

@router.get("/farmers/me/spending", response_model=SpendingOut)
def get_spending(user_id: str = Depends(get_user_id)) -> SpendingOut:
    """Return total spend and breakdown by activity type."""
    farmer = _get_farmer(user_id)
    activities = _get_activities(farmer["id"])
    return SpendingOut(
        total_cost=round(total_cost(activities), 2),
        by_type={k: round(v, 2) for k, v in cost_by_activity_type(activities).items()},
    )


# ── GET /api/farmers/me/gaps ─────────────────────────────────────────────────

@router.get("/farmers/me/gaps", response_model=List[GapOut])
def get_gaps(user_id: str = Depends(get_user_id)) -> List[GapOut]:
    """Return expected-vs-actual gaps for this farmer."""
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

    knowledge = json.loads(_KNOWLEDGE_PATH.read_text(encoding="utf-8"))
    crop_stages = knowledge[farmer["crop"].lower()]["stages"]

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
    """Return the allowed activity types. Frontend uses this to stay in sync."""
    return {"activity_types": ACTIVITY_TYPES}
