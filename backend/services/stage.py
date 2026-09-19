"""
stage.py — Growth stage lookup from crop_knowledge.json.

Stage boundaries come exclusively from crop_knowledge.json — no stage constants
are defined in this module. To change or add stages, edit the JSON file only.
"""

import json
import pathlib
from datetime import date

from fastapi import HTTPException

# Load once at import time — not on every request.
_KNOWLEDGE_PATH = pathlib.Path(__file__).parent.parent / "data" / "crop_knowledge.json"
_knowledge: dict = json.loads(_KNOWLEDGE_PATH.read_text(encoding="utf-8"))


def get_stage(crop: str, sowing_date: date) -> tuple[dict, int]:
    """Return (stage_dict, months_elapsed) for the given crop and sowing date.

    Raises:
        HTTPException 422  if sowing_date is in the future (Req 5.6).
                           Does NOT clamp — rejects explicitly.
        KeyError           if crop is not found in crop_knowledge.json.
                           The calling router should catch this and return 422.
    """
    today = date.today()

    # Reject future sowing dates — do not clamp with max(..., 0).
    if sowing_date > today:
        raise HTTPException(
            status_code=422,
            detail="Planting date cannot be in the future.",
        )

    # Integer complete months elapsed (floor, not round).
    months = (today.year - sowing_date.year) * 12 + (today.month - sowing_date.month)
    if today.day < sowing_date.day:
        months -= 1

    crop_key = crop.lower()
    if crop_key not in _knowledge:
        raise KeyError(f"Crop '{crop}' not found in crop_knowledge.json")

    stages = _knowledge[crop_key]["stages"]

    # Walk in order; keep the last stage whose month_start <= months_elapsed.
    # Falls back to stages[0] when months_elapsed == 0.
    matched = stages[0]
    for stage in stages:
        if stage["month_start"] <= months:
            matched = stage
        else:
            break

    return matched, months
