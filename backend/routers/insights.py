"""
insights.py — Farm intelligence and forward-looking advisory endpoints.

GET  /api/farmers/me/insights   Full advisory bundle:
                                  - 7-day weather forecast (Open-Meteo)
                                  - Disease risk alerts (weather-driven)
                                  - ET0 irrigation advisory
                                  - Seasonal price outlook
                                  - Next 3 stages planner
                                  - Harvest timing recommendation
                                  - NASA POWER seasonal climate anomaly
                                  - Growing Degree Day (GDD) accumulation
                                  - Monsoon risk index
                                  - Input compliance score
                                  - Fertilizer cost forecast for remaining stages

All calculations are deterministic. Gemini is not used in this module.
Weather: Open-Meteo (free, no API key, 7-day forecast)
Climate: NASA POWER (free, no API key, 30-year history + daily observations)
"""

import json
import logging
import pathlib
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from services.auth import get_user_id
from services.db import get_db
from services.geo import get_coordinates
from services.weather import get_farm_weather
from services.climate import (
    fetch_climate_data,
    fertilizer_budget_forecast,
    input_compliance_score,
)
from services import stage as stage_service

logger = logging.getLogger(__name__)

router = APIRouter()

_KNOWLEDGE_PATH = pathlib.Path(__file__).parent.parent / "data" / "crop_knowledge.json"
_knowledge_cache: dict | None = None


def _get_knowledge() -> dict:
    global _knowledge_cache
    if _knowledge_cache is None:
        _knowledge_cache = json.loads(_KNOWLEDGE_PATH.read_text(encoding="utf-8"))
    return _knowledge_cache


# ── Seasonal price data ───────────────────────────────────────────────────────
_MONTHLY_PRICE_OUTLOOK: dict[int, dict] = {
    1:  {"modal": 35, "min": 20, "max": 55, "demand": "moderate", "score": 6,
         "note": "Winter supply moderate, steady demand"},
    2:  {"modal": 28, "min": 15, "max": 45, "demand": "low",      "score": 4,
         "note": "Peak winter supply — prices weak"},
    3:  {"modal": 22, "min": 12, "max": 38, "demand": "low",      "score": 3,
         "note": "Maximum arrivals, lowest prices of year"},
    4:  {"modal": 38, "min": 22, "max": 60, "demand": "moderate", "score": 6,
         "note": "Supply falling, prices recovering"},
    5:  {"modal": 55, "min": 35, "max": 80, "demand": "high",     "score": 8,
         "note": "Pre-monsoon gap, good prices"},
    6:  {"modal": 65, "min": 40, "max": 90, "demand": "high",     "score": 8,
         "note": "Monsoon gap — very limited supply"},
    7:  {"modal": 70, "min": 45, "max": 95, "demand": "very_high","score": 9,
         "note": "Peak price window — minimal competition"},
    8:  {"modal": 60, "min": 38, "max": 85, "demand": "high",     "score": 8,
         "note": "Rainy season harvest premium holds"},
    9:  {"modal": 50, "min": 30, "max": 75, "demand": "moderate", "score": 7,
         "note": "Supply increasing, prices easing"},
    10: {"modal": 42, "min": 25, "max": 65, "demand": "moderate", "score": 6,
         "note": "Hasta Bahar arrivals begin"},
    11: {"modal": 30, "min": 18, "max": 50, "demand": "low",      "score": 4,
         "note": "Winter supply builds, prices fall"},
    12: {"modal": 28, "min": 15, "max": 45, "demand": "low",      "score": 3,
         "note": "Peak winter arrivals, weakest prices"},
}


def _get_future_stages(all_stages: list[dict], current_stage_id: str, plant_count: int) -> list[dict]:
    found = False
    future = []
    for s in all_stages:
        if found and len(future) < 3:
            q = s.get("quantities", {})
            fert_gpw = float(q.get("fertilizer_grams_per_plant_per_week", 0) or 0)
            irr_lpd  = float(q.get("irrigation_litres_per_plant_per_day", 0) or 0)
            future.append({
                "stage_id":                  s["stage_id"],
                "label":                     s["label"],
                "month_start":               s["month_start"],
                "description":               s.get("description", ""),
                "key_activity":              s.get("activities", []),
                "fertilizer_name":           q.get("fertilizer_name", ""),
                "fertilizer_kg_per_month":   round(fert_gpw * plant_count * 4.33 / 1000, 1),
                "irrigation_litres_per_day": round(irr_lpd * plant_count, 0),
                "ipm_checks":                [i["pest"] for i in s.get("ipm", [])],
            })
        if s["stage_id"] == current_stage_id:
            found = True
    return future


def _harvest_timing_advice(sowing_date: date) -> dict:
    harvest_date  = sowing_date + timedelta(days=17 * 30)
    harvest_month = harvest_date.month
    price_data    = _MONTHLY_PRICE_OUTLOOK.get(harvest_month, _MONTHLY_PRICE_OUTLOOK[7])
    return {
        "estimated_harvest_date": str(harvest_date),
        "harvest_month_name":     harvest_date.strftime("%B %Y"),
        "modal_price_per_kg":     price_data["modal"],
        "price_range":            f"₹{price_data['min']}–₹{price_data['max']}/kg",
        "market_demand":          price_data["demand"],
        "attractiveness_score":   price_data["score"],
        "market_note":            price_data["note"],
    }


# ── GET /api/farmers/me/insights ─────────────────────────────────────────────

@router.get("/farmers/me/insights")
async def get_insights(user_id: str = Depends(get_user_id)) -> dict:
    """Return the full farm intelligence bundle.

    Both Open-Meteo and NASA POWER fetches are done in parallel.
    If either fails, that section degrades gracefully — the rest is returned.
    """
    import asyncio

    db = get_db()

    # ── Load farmer profile ───────────────────────────────────────────────────
    try:
        result = (
            db.table("farmers")
            .select("crop, plant_count, state, district, sowing_date")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        logger.error("DB select failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Profile not found.")

    row = result.data
    sowing_date = (
        date.fromisoformat(row["sowing_date"])
        if isinstance(row["sowing_date"], str)
        else row["sowing_date"]
    )

    # ── Stage ─────────────────────────────────────────────────────────────────
    try:
        sr = stage_service.get_stage(row["crop"], sowing_date)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Cannot determine crop stage.") from exc

    # ── Coordinates ───────────────────────────────────────────────────────────
    lat, lon = get_coordinates(row["state"], row["district"])

    # ── Load activities for compliance score ──────────────────────────────────
    try:
        act_result = (
            db.table("farm_activities")
            .select("activity_type, quantity")
            .eq("farmer_id",
                db.table("farmers").select("id").eq("user_id", user_id)
                .maybe_single().execute().data["id"])
            .execute()
        )
        activities = act_result.data or []
    except Exception:
        activities = []

    # ── Parallel API fetches ──────────────────────────────────────────────────
    q = sr.stage.get("quantities", {})
    irr_lpd_ref = float(q.get("irrigation_litres_per_plant_per_day", 0) or 0)

    weather_task = get_farm_weather(lat, lon, stage_irrigation_lpd=irr_lpd_ref)
    climate_task = fetch_climate_data(lat, lon, sowing_date)

    weather, climate = await asyncio.gather(weather_task, climate_task)

    # ── Deterministic calculations ────────────────────────────────────────────
    knowledge  = _get_knowledge()
    all_stages = knowledge[row["crop"].lower()]["stages"]

    future_stages   = _get_future_stages(all_stages, sr.stage["stage_id"], row["plant_count"])
    fert_forecast   = fertilizer_budget_forecast(all_stages, sr.stage["stage_id"], row["plant_count"])
    compliance      = input_compliance_score(
        all_stages, sr.stage["stage_id"], sr.months_elapsed,
        row["plant_count"], activities,
    )

    current_month   = date.today().month
    current_price   = _MONTHLY_PRICE_OUTLOOK.get(current_month, _MONTHLY_PRICE_OUTLOOK[7])
    harvest_timing  = _harvest_timing_advice(sowing_date)

    price_calendar  = [
        {
            "month":      m,
            "month_name": date(2024, m, 1).strftime("%b"),
            "modal":      d["modal"],
            "score":      d["score"],
            "demand":     d["demand"],
            "note":       d["note"],
            "is_current": m == current_month,
        }
        for m, d in _MONTHLY_PRICE_OUTLOOK.items()
    ]

    # GDD comparison vs calendar-based stage
    gdd_stage = climate.get("gdd_predicted_stage", sr.stage["stage_id"])
    stage_order = [s["stage_id"] for s in all_stages]
    gdd_idx = stage_order.index(gdd_stage) if gdd_stage in stage_order else 0
    cal_idx = stage_order.index(sr.stage["stage_id"]) if sr.stage["stage_id"] in stage_order else 0

    if gdd_idx > cal_idx:
        gdd_vs_calendar = "ahead"
        gdd_note = "Heat accumulation suggests your crop may be developing faster than the calendar month indicates."
    elif gdd_idx < cal_idx:
        gdd_vs_calendar = "behind"
        gdd_note = "Cooler-than-normal temperatures may be slowing crop development relative to calendar months."
    else:
        gdd_vs_calendar = "on_track"
        gdd_note = "Heat accumulation is consistent with the calendar-based stage."

    return {
        "location": {
            "state":    row["state"],
            "district": row["district"],
            "latitude":  lat,
            "longitude": lon,
        },
        "current_stage": {
            "stage_id":       sr.stage["stage_id"],
            "label":          sr.stage["label"],
            "months_elapsed": sr.months_elapsed,
            "days_elapsed":   sr.days_elapsed,
        },
        "weather":  weather,
        "climate": {
            **climate,
            "gdd_vs_calendar": gdd_vs_calendar,
            "gdd_note":        gdd_note,
        },
        "compliance":        compliance,
        "fertilizer_forecast": fert_forecast,
        "future_stages":     future_stages,
        "market": {
            "current_month_outlook": current_price,
            "harvest_timing":        harvest_timing,
            "price_calendar":        price_calendar,
        },
    }
