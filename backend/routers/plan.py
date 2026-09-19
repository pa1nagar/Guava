"""
plan.py — GET /api/plan  |  POST /api/farmers/me/plan/generate

Returns the farmer's structured care plan.
Cache hit  → returns immediately (no Gemini call).
Cache miss → deterministic tasks + Gemini explanation, then persists.

All quantities come from the backend. Gemini only phrases them.
"""

import json
import logging
from datetime import datetime, timezone, date as date_type

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from services.auth import get_user_id
from services.cache import compute_profile_hash
from services.db import get_db
from services import planner, stage as stage_service
from services.scaling import scale_stage_quantities

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Response models ───────────────────────────────────────────────────────────

class PlanTask(BaseModel):
    category: str
    title: str
    description: str
    quantity: Optional[float] = None
    unit: Optional[str] = None


class PlanOut(BaseModel):
    stage_id: str
    stage_label: str
    months_elapsed: int
    days_elapsed: int
    is_final_stage: bool
    summary: str
    tasks: List[PlanTask]
    warnings: List[str]
    notes: List[str]
    from_cache: bool


# ── Deterministic task builder (no Gemini) ────────────────────────────────────

def _build_deterministic_tasks(stage: dict, scaled: dict) -> List[PlanTask]:
    tasks: List[PlanTask] = []
    q = stage.get("quantities", {})
    irrign = q.get("irrigation_litres_per_plant_per_day", 0)

    if irrign and irrign > 0:
        tasks.append(PlanTask(
            category="irrigation",
            title="Irrigation",
            description=stage.get("irrigation", ""),
            quantity=round(scaled.get("total_irrigation_litres_per_day", 0), 1),
            unit="litres/day (total for all plants)",
        ))
    elif irrign == 0:
        tasks.append(PlanTask(
            category="irrigation",
            title="Irrigation — Drought Stress Period",
            description=stage.get("irrigation", "Stop all irrigation this week."),
            quantity=0,
            unit="litres/day",
        ))

    fert_grams = q.get("fertilizer_grams_per_plant_per_week", 0)
    if fert_grams and fert_grams > 0:
        tasks.append(PlanTask(
            category="fertilizer",
            title=f"Fertilizer — {q.get('fertilizer_name', 'As recommended')}",
            description=stage.get("fertigation", ""),
            quantity=round(scaled.get("total_fertilizer_kg_per_week", 0), 2),
            unit="kg/week (total for all plants)",
        ))

    for ipm in stage.get("ipm", []):
        tasks.append(PlanTask(
            category="ipm",
            title=f"Check: {ipm['pest']}",
            description=f"{ipm['check']}. {ipm['action']}",
        ))

    return tasks


# ── GET /api/plan ─────────────────────────────────────────────────────────────

@router.get("/plan", response_model=PlanOut)
def get_plan(user_id: str = Depends(get_user_id)) -> PlanOut:
    db = get_db()

    # 1. Fetch farmer row
    try:
        result = (
            db.table("farmers")
            .select(
                "crop, plant_count, state, district, sowing_date, "
                "cached_plan, profile_hash"
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
    sowing_date = (
        date_type.fromisoformat(row["sowing_date"])
        if isinstance(row["sowing_date"], str)
        else row["sowing_date"]
    )

    # 2. Compute stage (fast, no I/O)
    try:
        sr = stage_service.get_stage(row["crop"], sowing_date)
    except HTTPException as exc:
        raise exc
    except KeyError as exc:
        logger.error("Unknown crop: %s", exc)
        raise HTTPException(status_code=422, detail="Crop not supported.")

    # 3. Scale quantities
    scaled = scale_stage_quantities(sr.stage, row["plant_count"])

    # 4. Check cache
    current_hash = compute_profile_hash(
        row["crop"], row["plant_count"], row["state"], row["district"], sowing_date,
    )

    cached_raw = row.get("cached_plan")
    if current_hash == row.get("profile_hash") and cached_raw:
        try:
            cached_data = json.loads(cached_raw)
            return PlanOut(**cached_data, from_cache=True)
        except Exception:
            logger.info("Cached plan is stale format — regenerating.")

    # 5. Build deterministic tasks, then try Gemini for richer text
    det_tasks = _build_deterministic_tasks(sr.stage, scaled)

    gemini_result = None
    try:
        gemini_result = planner.generate_plan_structured(
            stage=sr.stage,
            plant_count=row["plant_count"],
            scaled=scaled,
            state=row["state"],
            district=row["district"],
        )
    except RuntimeError:
        logger.warning("Gemini unavailable — using deterministic plan.")

    if gemini_result and gemini_result.get("tasks"):
        tasks   = [PlanTask(**t) for t in gemini_result["tasks"]]
        summary = gemini_result.get("summary", "")
        warnings = gemini_result.get("warnings", [])
        notes    = gemini_result.get("notes", [])
    else:
        tasks    = det_tasks
        summary  = (
            f"You are in the {sr.stage['label']} stage "
            f"({sr.months_elapsed} months since planting). "
            "Reference tasks are shown below."
        )
        warnings = []
        notes    = ["Plan generated from reference data (AI explanation unavailable)."]

    plan_data = PlanOut(
        stage_id=sr.stage["stage_id"],
        stage_label=sr.stage["label"],
        months_elapsed=sr.months_elapsed,
        days_elapsed=sr.days_elapsed,
        is_final_stage=sr.is_final_stage,
        summary=summary,
        tasks=tasks,
        warnings=warnings,
        notes=notes,
        from_cache=False,
    )

    # 6. Persist cache
    now_utc = datetime.now(timezone.utc).isoformat()
    try:
        db.table("farmers").update(
            {
                "cached_plan": json.dumps(plan_data.model_dump()),
                "profile_hash": current_hash,
                "plan_generated_at": now_utc,
            }
        ).eq("user_id", user_id).execute()
    except Exception as exc:
        logger.error("Failed to persist cached plan: %s", exc)

    return plan_data


# ── POST /api/farmers/me/plan/generate ───────────────────────────────────────

@router.post("/farmers/me/plan/generate", response_model=PlanOut)
def regenerate_plan(user_id: str = Depends(get_user_id)) -> PlanOut:
    """Force-invalidate cache and regenerate plan."""
    db = get_db()
    try:
        db.table("farmers").update(
            {"cached_plan": None, "profile_hash": None}
        ).eq("user_id", user_id).execute()
    except Exception as exc:
        logger.error("Failed to invalidate plan cache: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    return get_plan(user_id=user_id)
