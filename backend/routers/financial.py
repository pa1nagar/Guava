"""
financial.py — Financial summary and crop-cycle report endpoints.

GET  /api/farmers/me/financial-summary   Spending + revenue + P&L + break-even.
POST /api/farmers/me/harvest             Log harvest/sale (write-once per cycle).
GET  /api/farmers/me/report              Full crop-cycle report.
"""

import logging
import os
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from supabase import Client, create_client

from services.auth import get_user_id
from services.financials import (
    total_cost,
    cost_by_activity_type,
    revenue,
    profit_or_loss,
    break_even_price,
)

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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_farmer(user_id: str) -> dict:
    try:
        result = (
            _db.table("farmers")
            .select(
                "id, crop, plant_count, sowing_date, "
                "expected_yield_kg, vendor_recommendation_consent"
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
            .order("logged_date", desc=False)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.error("DB select activities failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")


def _get_harvest(farmer_id: str) -> Optional[dict]:
    try:
        result = (
            _db.table("harvests")
            .select("*")
            .eq("farmer_id", farmer_id)
            .maybe_single()
            .execute()
        )
        return result.data if (result and result.data) else None
    except Exception as exc:
        logger.error("DB select harvest failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")


# ── Models ────────────────────────────────────────────────────────────────────

class FinancialSummaryOut(BaseModel):
    total_cost: float
    cost_by_type: dict
    revenue: Optional[float]
    profit_or_loss: Optional[float]
    break_even_price_per_kg: Optional[float]
    has_harvest: bool
    currency: str = "INR"
    break_even_note: Optional[str] = None


class HarvestIn(BaseModel):
    sale_quantity_kg: float = Field(gt=0, description="Quantity sold in kg.")
    sale_price_per_kg: float = Field(ge=0, description="Price per kg in INR.")


class HarvestOut(BaseModel):
    id: str
    sale_quantity_kg: float
    sale_price_per_kg: float
    sale_date: str
    revenue: float


class ActivitySummaryItem(BaseModel):
    activity_type: str
    total_quantity: float
    total_cost: float
    unit: Optional[str]
    entry_count: int


class ReportOut(BaseModel):
    crop: str
    sowing_date: str
    plant_count: int
    stage_coverage: List[str]      # stages that had at least one activity logged
    stages_with_no_activity: List[str]  # stages with no logged activities
    total_cost: float
    cost_by_type: dict
    revenue: Optional[float]
    profit_or_loss: Optional[float]
    break_even_price_per_kg: Optional[float]
    break_even_note: Optional[str]
    has_harvest: bool
    activity_history: List[dict]   # raw sorted activity list
    currency: str = "INR"


# ── GET /api/farmers/me/financial-summary ─────────────────────────────────────

@router.get("/farmers/me/financial-summary", response_model=FinancialSummaryOut)
def financial_summary(user_id: str = Depends(get_user_id)) -> FinancialSummaryOut:
    farmer = _get_farmer(user_id)
    activities = _get_activities(farmer["id"])
    harvest = _get_harvest(farmer["id"])

    tc = total_cost(activities)
    by_type = {k: round(v, 2) for k, v in cost_by_activity_type(activities).items()}

    rev = None
    pol = None
    bep = None
    bep_note = None

    if harvest:
        rev = revenue(
            float(harvest["sale_quantity_kg"]),
            float(harvest["sale_price_per_kg"]),
        )
        pol = profit_or_loss(rev, tc)

    bep = break_even_price(tc, farmer.get("expected_yield_kg"))
    if bep is None:
        if not farmer.get("expected_yield_kg"):
            bep_note = "Set an expected yield to calculate your break-even price."
        elif tc <= 0:
            bep_note = "No costs logged yet."

    return FinancialSummaryOut(
        total_cost=round(tc, 2),
        cost_by_type=by_type,
        revenue=round(rev, 2) if rev is not None else None,
        profit_or_loss=round(pol, 2) if pol is not None else None,
        break_even_price_per_kg=round(bep, 2) if bep is not None else None,
        has_harvest=harvest is not None,
        break_even_note=bep_note,
    )


# ── POST /api/farmers/me/harvest ──────────────────────────────────────────────

@router.post("/farmers/me/harvest", response_model=HarvestOut)
def log_harvest(
    body: HarvestIn,
    user_id: str = Depends(get_user_id),
) -> HarvestOut:
    """Log harvest and sale. Write-once per crop cycle.

    A second submission is rejected with 409 Conflict.
    """
    from services import stage as stage_service

    farmer = _get_farmer(user_id)

    # ── Verify farmer is at the harvest stage ─────────────────────────────────
    sowing_date = (
        date.fromisoformat(farmer["sowing_date"])
        if isinstance(farmer["sowing_date"], str)
        else farmer["sowing_date"]
    )
    try:
        sr = stage_service.get_stage(farmer["crop"], sowing_date)
    except (HTTPException, KeyError) as exc:
        raise HTTPException(status_code=422, detail="Cannot determine crop stage.") from exc

    if not sr.is_final_stage:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Harvest can only be logged once the crop reaches the harvest stage. "
                f"Current stage: {sr.stage['label']}."
            ),
        )

    # ── Reject duplicate submission ───────────────────────────────────────────
    existing = _get_harvest(farmer["id"])
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Harvest has already been recorded for this crop cycle.",
        )

    # ── Insert ────────────────────────────────────────────────────────────────
    payload = {
        "farmer_id": farmer["id"],
        "sale_quantity_kg": body.sale_quantity_kg,
        "sale_price_per_kg": body.sale_price_per_kg,
        "sale_date": str(date.today()),
    }
    try:
        result = _db.table("harvests").insert(payload).execute()
    except Exception as exc:
        logger.error("DB insert harvest failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    row = result.data[0]
    rev = revenue(
        float(row["sale_quantity_kg"]),
        float(row["sale_price_per_kg"]),
    )
    return HarvestOut(
        id=row["id"],
        sale_quantity_kg=float(row["sale_quantity_kg"]),
        sale_price_per_kg=float(row["sale_price_per_kg"]),
        sale_date=str(row["sale_date"]),
        revenue=round(rev, 2),
    )


# ── GET /api/farmers/me/report ────────────────────────────────────────────────

@router.get("/farmers/me/report", response_model=ReportOut)
def crop_cycle_report(user_id: str = Depends(get_user_id)) -> ReportOut:
    """Return the full crop-cycle financial report."""
    farmer = _get_farmer(user_id)
    activities = _get_activities(farmer["id"])
    harvest = _get_harvest(farmer["id"])

    # Load stage list.
    knowledge = json.loads(_KNOWLEDGE_PATH.read_text(encoding="utf-8"))
    all_stages = knowledge[farmer["crop"].lower()]["stages"]

    # Determine which stages have at least one activity.
    sowing_date = (
        date.fromisoformat(farmer["sowing_date"])
        if isinstance(farmer["sowing_date"], str)
        else farmer["sowing_date"]
    )
    sr = None
    try:
        from services import stage as stage_service
        sr = stage_service.get_stage(farmer["crop"], sowing_date)
    except Exception:
        pass

    current_month = sr.months_elapsed if sr else 0

    # Which stages are "reached" (month_start <= current_month)?
    reached_stage_ids = {
        s["stage_id"] for s in all_stages
        if s["month_start"] <= current_month
    }

    # Which reached stages have logged activities?
    # Group activity logged_dates to month offsets.
    activity_months = set()
    for a in activities:
        ld = a.get("logged_date", "")
        if ld:
            try:
                ld_date = date.fromisoformat(str(ld))
                m = (ld_date.year - sowing_date.year) * 12 + (ld_date.month - sowing_date.month)
                activity_months.add(m)
            except ValueError:
                pass

    stages_with_activity = set()
    stages_without_activity = []

    for s in all_stages:
        if s["month_start"] > current_month:
            continue
        # Check if any activity falls within this stage's month range.
        end = s["month_end"] if s["month_end"] != 9999 else current_month
        has = any(s["month_start"] <= m <= end for m in activity_months)
        if has:
            stages_with_activity.add(s["stage_id"])
        else:
            stages_without_activity.append(s["label"])

    tc = total_cost(activities)
    by_type = {k: round(v, 2) for k, v in cost_by_activity_type(activities).items()}

    rev = None
    pol = None
    bep = None
    bep_note = None

    if harvest:
        rev = revenue(
            float(harvest["sale_quantity_kg"]),
            float(harvest["sale_price_per_kg"]),
        )
        pol = profit_or_loss(rev, tc)

    bep = break_even_price(tc, farmer.get("expected_yield_kg"))
    if bep is None and not farmer.get("expected_yield_kg"):
        bep_note = "Set an expected yield to calculate your break-even price."

    # Build chronological activity history.
    history = [
        {
            "date": str(a["logged_date"]),
            "activity_type": a["activity_type"],
            "quantity": float(a["quantity"]),
            "unit": a.get("unit"),
            "cost": float(a["cost"]),
            "notes": a.get("notes"),
        }
        for a in sorted(activities, key=lambda x: x.get("logged_date", ""))
    ]

    return ReportOut(
        crop=farmer["crop"].title(),
        sowing_date=str(farmer["sowing_date"]),
        plant_count=farmer["plant_count"],
        stage_coverage=list(stages_with_activity),
        stages_with_no_activity=stages_without_activity,
        total_cost=round(tc, 2),
        cost_by_type=by_type,
        revenue=round(rev, 2) if rev is not None else None,
        profit_or_loss=round(pol, 2) if pol is not None else None,
        break_even_price_per_kg=round(bep, 2) if bep is not None else None,
        break_even_note=bep_note,
        has_harvest=harvest is not None,
        activity_history=history,
    )
