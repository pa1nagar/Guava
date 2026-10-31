"""
stage.py — Growth stage lookup from crop_knowledge.json.

Stage boundaries come exclusively from crop_knowledge.json — no stage constants
are defined in this module. To change or add stages, edit the JSON file only.

Public API
----------
compute_crop_age_months(planting_date, today=None, timezone="Asia/Kolkata") -> int
    Pure function returning complete calendar months elapsed since the
    planting date.  Timezone-aware via ``zoneinfo`` (Python 3.9+ stdlib).
    The same floor-based logic that ``get_stage`` uses internally.

get_stage(crop, sowing_date) -> StageResult
    Returns a StageResult dataclass with stage dict, timing fields, and
    is_final_stage flag.  Internally delegates month computation to
    ``compute_crop_age_months``.

StageResult fields:
    stage           dict  — full stage object from crop_knowledge.json
    months_elapsed  int   — complete months since sowing (floor)
    days_elapsed    int   — calendar days since sowing
    is_final_stage  bool  — True when current stage is the configured final stage
"""

import json
import pathlib
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException

# Load once at import time — not on every request.
_KNOWLEDGE_PATH = pathlib.Path(__file__).parent.parent / "data" / "crop_knowledge.json"
_knowledge: dict = json.loads(_KNOWLEDGE_PATH.read_text(encoding="utf-8"))


@dataclass
class StageResult:
    stage: dict
    months_elapsed: int
    days_elapsed: int
    is_final_stage: bool


def compute_crop_age_months(
    planting_date: date,
    today: Optional[date] = None,
    timezone: str = "Asia/Kolkata",
) -> int:
    """Return complete calendar months elapsed since ``planting_date``.

    Uses a floor-based calendar month difference — a partial month counts
    only once the day-of-month of the planting date has been reached.
    This is the same logic ``get_stage`` relies on, extracted as a pure
    function so it can be called independently and tested in isolation.

    Timezone-aware: when ``today`` is *not* supplied the current date is
    resolved in ``timezone`` (IANA name, default ``"Asia/Kolkata"``).
    When ``today`` is supplied it is used as-is, making the function
    deterministic and easy to test.

    Args:
        planting_date: The date the crop was planted / sown.
        today: Reference date; defaults to today in ``timezone``.
        timezone: IANA timezone name, used only when ``today`` is None.

    Returns:
        Complete months elapsed (floor).  May be negative when ``today``
        predates ``planting_date`` — callers should validate as needed.
    """
    if today is None:
        today = datetime.now(ZoneInfo(timezone)).date()

    months = (today.year - planting_date.year) * 12 + (today.month - planting_date.month)
    if today.day < planting_date.day:
        months -= 1
    return months


def get_stage(crop: str, sowing_date: date) -> StageResult:
    """Return a StageResult for the given crop and sowing date.

    Raises:
        HTTPException 422  if sowing_date is in the future.
                           Does NOT clamp — rejects explicitly.
        KeyError           if crop is not found in crop_knowledge.json.
                           The calling router should catch this and return 422.
    """
    today = date.today()

    # Reject future sowing dates.
    if sowing_date > today:
        raise HTTPException(
            status_code=422,
            detail="Planting date cannot be in the future.",
        )

    # Days elapsed (calendar days).
    days_elapsed = (today - sowing_date).days

    # Integer complete months elapsed (floor, not round).
    # Delegates to the pure function so the logic lives in one place.
    months = compute_crop_age_months(sowing_date, today)

    crop_key = crop.lower()
    if crop_key not in _knowledge:
        raise KeyError(f"Crop '{crop}' not found in crop_knowledge.json")

    crop_data = _knowledge[crop_key]
    stages = crop_data["stages"]
    final_stage_id = crop_data.get("is_final_stage_id")

    # Walk in order; keep the last stage whose month_start <= months_elapsed.
    # Falls back to stages[0] when months_elapsed == 0.
    matched = stages[0]
    for stage in stages:
        if stage["month_start"] <= months:
            matched = stage
        else:
            break

    is_final = (matched["stage_id"] == final_stage_id) if final_stage_id else False

    return StageResult(
        stage=matched,
        months_elapsed=months,
        days_elapsed=days_elapsed,
        is_final_stage=is_final,
    )
