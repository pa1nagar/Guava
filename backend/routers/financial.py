"""
financial.py — Financial summary and crop-cycle report endpoints.

GET  /api/farmers/me/financial-summary
POST /api/farmers/me/harvest             (write-once per crop cycle)
GET  /api/farmers/me/report
"""

import json
import logging
import pathlib
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from services.auth import get_user_id
from services.db import get_db
from services.financials import (
    total_cost,
    cost_by_activity_type,
    revenue,
    profit_or_loss,
    break_even_price,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Crop knowledge loaded once at module level.
_KNOWLEDGE_PATH = pathlib.Path(__file__).parent.parent / "data" / "crop_knowledge.json"
_knowledge_cache: dict | None = None


def _get_knowledge() -> dict:
    global _knowledge_cache
    if _knowledge_cache is None:
        _knowledge_cache = json.loads(_KNOWLEDGE_PATH.read_text(encoding="utf-8"))
    return _knowledge_cache


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_farmer(user_id: str) -> dict:
    db = get_db()
    try:
        result = (
            db.table("farmers")
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


def _get_harvest(farmer_id: str) -> Optional[dict]:
    db = get_db()
    try:
        result = (
            db.table("harvests")
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
    sale_quantity_kg: float = Field(gt=0)
    sale_price_per_kg: float = Field(ge=0)


class HarvestOut(BaseModel):
    id: str
    sale_quantity_kg: float
    sale_price_per_kg: float
    sale_date: str
    revenue: float


class ReportOut(BaseModel):
    crop: str
    sowing_date: str
    plant_count: int
    stage_coverage: List[str]
    stages_with_no_activity: List[str]
    total_cost: float
    cost_by_type: dict
    revenue: Optional[float]
    profit_or_loss: Optional[float]
    break_even_price_per_kg: Optional[float]
    break_even_note: Optional[str]
    has_harvest: bool
    activity_history: List[dict]
    currency: str = "INR"


# ── GET /api/farmers/me/financial-summary ────────────────────────────────────

@router.get("/farmers/me/financial-summary", response_model=FinancialSummaryOut)
def financial_summary(user_id: str = Depends(get_user_id)) -> FinancialSummaryOut:
    farmer     = _get_farmer(user_id)
    activities = _get_activities(farmer["id"])
    harvest    = _get_harvest(farmer["id"])

    tc     = total_cost(activities)
    by_type = {k: round(v, 2) for k, v in cost_by_activity_type(activities).items()}

    rev = pol = bep = bep_note = None

    if harvest:
        rev = revenue(float(harvest["sale_quantity_kg"]), float(harvest["sale_price_per_kg"]))
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


# ── POST /api/farmers/me/harvest ─────────────────────────────────────────────

@router.post("/farmers/me/harvest", response_model=HarvestOut)
def log_harvest(body: HarvestIn, user_id: str = Depends(get_user_id)) -> HarvestOut:
    """Write-once per crop cycle. Returns 409 if already submitted."""
    from services import stage as stage_service  # noqa: PLC0415

    db = get_db()
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

    if not sr.is_final_stage:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Harvest can only be logged at the harvest stage. "
                f"Current stage: {sr.stage['label']}."
            ),
        )

    if _get_harvest(farmer["id"]):
        raise HTTPException(
            status_code=409,
            detail="Harvest has already been recorded for this crop cycle.",
        )

    payload = {
        "farmer_id":          farmer["id"],
        "sale_quantity_kg":   body.sale_quantity_kg,
        "sale_price_per_kg":  body.sale_price_per_kg,
        "sale_date":          str(date.today()),
    }
    try:
        result = db.table("harvests").insert(payload).execute()
    except Exception as exc:
        logger.error("DB insert harvest failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    row = result.data[0]
    rev = revenue(float(row["sale_quantity_kg"]), float(row["sale_price_per_kg"]))
    return HarvestOut(
        id=row["id"],
        sale_quantity_kg=float(row["sale_quantity_kg"]),
        sale_price_per_kg=float(row["sale_price_per_kg"]),
        sale_date=str(row["sale_date"]),
        revenue=round(rev, 2),
    )


# ── GET /api/farmers/me/report ───────────────────────────────────────────────

@router.get("/farmers/me/report", response_model=ReportOut)
def crop_cycle_report(user_id: str = Depends(get_user_id)) -> ReportOut:
    from services import stage as stage_service  # noqa: PLC0415

    farmer     = _get_farmer(user_id)
    activities = _get_activities(farmer["id"])
    harvest    = _get_harvest(farmer["id"])

    all_stages = _get_knowledge()[farmer["crop"].lower()]["stages"]

    sowing_date = (
        date.fromisoformat(farmer["sowing_date"])
        if isinstance(farmer["sowing_date"], str)
        else farmer["sowing_date"]
    )

    current_month = 0
    try:
        sr = stage_service.get_stage(farmer["crop"], sowing_date)
        current_month = sr.months_elapsed
    except Exception:
        pass

    # Map activity dates to month offsets from sowing date.
    activity_months: set[int] = set()
    for a in activities:
        ld = a.get("logged_date", "")
        if ld:
            try:
                ld_date = date.fromisoformat(str(ld))
                m = (
                    (ld_date.year - sowing_date.year) * 12
                    + (ld_date.month - sowing_date.month)
                )
                activity_months.add(m)
            except (ValueError, TypeError):
                pass

    stages_with_activity:    set[str]  = set()
    stages_without_activity: list[str] = []

    for s in all_stages:
        if s["month_start"] > current_month:
            break  # stages are ordered ascending — nothing beyond here is reached
        end = min(s["month_end"] if s["month_end"] != 9999 else current_month, current_month)
        has_log = any(s["month_start"] <= m <= end for m in activity_months)
        if has_log:
            stages_with_activity.add(s["stage_id"])
        else:
            stages_without_activity.append(s["label"])

    tc     = total_cost(activities)
    by_type = {k: round(v, 2) for k, v in cost_by_activity_type(activities).items()}

    rev = pol = bep = bep_note = None

    if harvest:
        rev = revenue(float(harvest["sale_quantity_kg"]), float(harvest["sale_price_per_kg"]))
        pol = profit_or_loss(rev, tc)

    bep = break_even_price(tc, farmer.get("expected_yield_kg"))
    if bep is None and not farmer.get("expected_yield_kg"):
        bep_note = "Set an expected yield to calculate your break-even price."

    history = [
        {
            "date":          str(a["logged_date"]),
            "activity_type": a["activity_type"],
            "quantity":      float(a["quantity"]),
            "unit":          a.get("unit"),
            "cost":          float(a["cost"]),
            "notes":         a.get("notes"),
        }
        for a in activities  # already sorted ascending by logged_date from query
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
