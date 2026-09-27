"""
climate.py — NASA POWER climate analysis for farm intelligence.

Uses urllib (standard library) — no httpx dependency.
All HTTP calls are synchronous and run via asyncio.run_in_executor
so they do not block FastAPI's event loop.
"""

import json
import logging
import urllib.parse
import urllib.request
from datetime import date, timedelta

logger = logging.getLogger(__name__)

NASA_POWER_DAILY = "https://power.larc.nasa.gov/api/temporal/daily/point"
NASA_POWER_CLIM  = "https://power.larc.nasa.gov/api/temporal/climatology/point"

GDD_BASE_TEMP = 10.0
GDD_TMAX_CAP  = 35.0

GDD_STAGE_THRESHOLDS: dict[str, float] = {
    "establishment":       0,
    "vegetative_growth":   500,
    "post_monsoon":        1800,
    "pre_bloom":           2800,
    "bloom_fruit_set":     3400,
    "fruit_development":   3900,
    "drought_stress":      4200,
    "harvest":             4500,
    "post_harvest_mature": 4800,
}

_MONTH_KEYS = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]

FERTILIZER_RATES: dict[str, float] = {
    "Urea (N)":        5.38,
    "DAP (N+P)":      27.00,
    "MOP (K)":        17.50,
    "19-19-19 WSF":   60.00,
    "12-6-20 WSF":    58.00,
    "8-8-32 WSF":     62.00,
    "MKP":            95.00,
    "SOP":            45.00,
    "Calcium nitrate":32.00,
    "Iron chelate":  250.00,
    "Humic acid":     80.00,
}
DEFAULT_FERTILIZER_RATE = 55.0


def _get_fert_rate(fertilizer_name: str) -> float:
    name_lower = fertilizer_name.lower()
    for key, rate in FERTILIZER_RATES.items():
        if any(part.lower() in name_lower for part in key.split()):
            return rate
    return DEFAULT_FERTILIZER_RATE


def _nasa_get(url: str, params: dict) -> dict:
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(full_url, headers={"User-Agent": "Guavaa-Farm/2.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _fetch_climate_sync(latitude: float, longitude: float, sowing_date: date) -> dict:
    """Synchronous climate fetch. Called via run_in_executor."""
    today = date.today()

    # 1. 30-year climatology
    try:
        clim_data = _nasa_get(NASA_POWER_CLIM, {
            "parameters": "T2M,PRECTOTCORR",
            "community":  "AG",
            "longitude":  longitude,
            "latitude":   latitude,
            "format":     "JSON",
        })
    except Exception as exc:
        logger.warning("NASA POWER climatology fetch failed: %s", exc)
        return {"fetched": False, "error": "Climate baseline data unavailable."}

    clim_props = clim_data.get("properties", {}).get("parameter", {})
    t2m_clim   = clim_props.get("T2M", {})
    rain_clim  = clim_props.get("PRECTOTCORR", {})

    cur_month_key     = _MONTH_KEYS[today.month - 1]
    t_normal          = t2m_clim.get(cur_month_key, -999)
    r_normal          = rain_clim.get(cur_month_key, -999)
    monsoon_normal_mm = sum(
        rain_clim.get(m, 0) * 30
        for m in ["JUN","JUL","AUG","SEP"]
        if rain_clim.get(m, -999) != -999
    )

    # 2. Daily data for GDD
    daily_start = max(sowing_date, today - timedelta(days=90))
    daily_end   = today - timedelta(days=1)

    gdd_cumulative            = 0.0
    current_month_t_actual    = None
    current_month_rain_actual = 0.0
    monsoon_cumulative_mm     = 0.0

    if daily_start < daily_end:
        try:
            daily_data = _nasa_get(NASA_POWER_DAILY, {
                "parameters": "T2M_MAX,T2M_MIN,PRECTOTCORR",
                "community":  "AG",
                "longitude":  longitude,
                "latitude":   latitude,
                "start":      daily_start.strftime("%Y%m%d"),
                "end":        daily_end.strftime("%Y%m%d"),
                "format":     "JSON",
            })
        except Exception as exc:
            logger.warning("NASA POWER daily fetch failed: %s", exc)
            daily_data = {}

        dp         = daily_data.get("properties", {}).get("parameter", {})
        tmax_daily = dp.get("T2M_MAX", {})
        tmin_daily = dp.get("T2M_MIN", {})
        rain_daily = dp.get("PRECTOTCORR", {})
        cur_month_temps: list[float] = []

        for date_key in sorted(tmax_daily.keys()):
            tmax = tmax_daily.get(date_key, -999)
            tmin = tmin_daily.get(date_key, -999)
            rain = rain_daily.get(date_key, -999)
            if tmax == -999 or tmin == -999:
                continue
            tmax_c = min(tmax, GDD_TMAX_CAP)
            gdd_cumulative += max(0.0, (tmax_c + max(tmin, GDD_BASE_TEMP)) / 2 - GDD_BASE_TEMP)
            try:
                obs = date(int(date_key[:4]), int(date_key[4:6]), int(date_key[6:8]))
                if obs.month == today.month and obs.year == today.year:
                    cur_month_temps.append((tmax + tmin) / 2)
                    if rain != -999:
                        current_month_rain_actual += rain
                jun1 = date(today.year, 6, 1)
                if jun1 <= obs <= today and obs.month in (6,7,8,9) and rain != -999:
                    monsoon_cumulative_mm += rain
            except (ValueError, TypeError):
                pass

        if cur_month_temps:
            current_month_t_actual = sum(cur_month_temps) / len(cur_month_temps)

    # 3. Anomaly
    temp_anomaly    = round(current_month_t_actual - t_normal, 1) \
                      if current_month_t_actual is not None and t_normal != -999 else None
    rain_anomaly    = round(current_month_rain_actual - r_normal * min(today.day, 28), 1) \
                      if r_normal != -999 and today.day > 5 else None

    if temp_anomaly is not None and rain_anomaly is not None:
        parts = []
        if abs(temp_anomaly) >= 1.0:
            parts.append(f"{abs(temp_anomaly):.1f}°C {'warmer' if temp_anomaly > 0 else 'cooler'} than the 30-year average")
        if abs(rain_anomaly) >= 10:
            parts.append(f"{abs(rain_anomaly):.0f}mm {'more' if rain_anomaly > 0 else 'less'} rainfall than normal")
        anomaly_summary = f"This month is {' and '.join(parts)}." if parts \
                          else "Temperature and rainfall are close to the 30-year average this month."
    else:
        anomaly_summary = "Climate data unavailable for this period."

    # 4. GDD stage
    gdd_predicted_stage = "establishment"
    for sid, thresh in sorted(GDD_STAGE_THRESHOLDS.items(), key=lambda x: x[1]):
        if gdd_cumulative >= thresh:
            gdd_predicted_stage = sid

    # 5. Monsoon risk
    monsoon_deficit_pct  = 0.0
    waterlogging_risk    = "low"
    waterlogging_message = "Rainfall within normal range. No waterlogging risk."

    if monsoon_normal_mm > 0:
        elapsed   = (today - date(today.year, 6, 1)).days
        expected  = monsoon_normal_mm * min(elapsed / 122, 1.0)
        if expected > 0:
            monsoon_deficit_pct = round((monsoon_cumulative_mm - expected) / expected * 100, 1)

    if monsoon_deficit_pct > 30:
        waterlogging_risk    = "high"
        waterlogging_message = (f"Rainfall is {monsoon_deficit_pct:.0f}% above normal. "
                                 "High risk of waterlogging and Fusarium wilt. Clear drainage furrows.")
    elif monsoon_deficit_pct > 10:
        waterlogging_risk    = "moderate"
        waterlogging_message = f"Rainfall is {monsoon_deficit_pct:.0f}% above normal. Check drainage."
    elif monsoon_deficit_pct < -25:
        waterlogging_risk    = "drought"
        waterlogging_message = (f"Rainfall is {abs(monsoon_deficit_pct):.0f}% below normal. "
                                 "Increase irrigation to compensate.")

    return {
        "fetched":               True,
        "gdd_cumulative":        round(gdd_cumulative, 0),
        "gdd_predicted_stage":   gdd_predicted_stage,
        "gdd_thresholds":        GDD_STAGE_THRESHOLDS,
        "anomaly_temperature":   temp_anomaly,
        "anomaly_rainfall_mm":   rain_anomaly,
        "anomaly_summary":       anomaly_summary,
        "monsoon_cumulative_mm": round(monsoon_cumulative_mm, 0),
        "monsoon_normal_mm":     round(monsoon_normal_mm, 0),
        "monsoon_deficit_pct":   monsoon_deficit_pct,
        "waterlogging_risk":     waterlogging_risk,
        "waterlogging_message":  waterlogging_message,
    }


async def fetch_climate_data(latitude: float, longitude: float, sowing_date: date) -> dict:
    """Async wrapper — runs sync fetch in a thread executor."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_climate_sync, latitude, longitude, sowing_date)


def fertilizer_budget_forecast(stages: list[dict], current_stage_id: str, plant_count: int) -> list[dict]:
    """Calculate fertilizer cost for all remaining stages."""
    found = False
    items = []
    for s in stages:
        if s["stage_id"] == current_stage_id:
            found = True
        if not found:
            continue
        q          = s.get("quantities", {})
        fert_gpw   = float(q.get("fertilizer_grams_per_plant_per_week", 0) or 0)
        fert_name  = q.get("fertilizer_name", "")
        duration_m = q.get("duration_months")
        if fert_gpw <= 0 or not fert_name:
            continue
        months    = float(duration_m) if duration_m else 1.0
        total_kg  = fert_gpw * plant_count * 4.33 * months / 1000
        rate      = _get_fert_rate(fert_name)
        items.append({
            "stage_id":      s["stage_id"],
            "stage_label":   s["label"],
            "fertilizer":    fert_name,
            "total_kg":      round(total_kg, 1),
            "rate_per_kg":   rate,
            "cost_estimate": round(total_kg * rate, 0),
            "months":        months,
        })
    return items


def input_compliance_score(
    stages: list[dict],
    current_stage_id: str,
    months_elapsed: int,
    plant_count: int,
    activities: list[dict],
) -> dict:
    """Compute a 0–100 input compliance score."""
    logged_fert_kg    = sum(float(a["quantity"]) for a in activities
                            if a.get("activity_type") == "Fertilizer")
    total_expected_kg = 0.0
    weeks_per_month   = 4.33

    for s in stages:
        if s["month_start"] > months_elapsed:
            break
        q   = s.get("quantities", {})
        gpw = float(q.get("fertilizer_grams_per_plant_per_week", 0) or 0)
        if gpw <= 0:
            continue
        end          = min(s["month_end"] if s["month_end"] != 9999 else months_elapsed, months_elapsed)
        stage_months = max(0, end - s["month_start"] + 1)
        total_expected_kg += gpw * plant_count * weeks_per_month * stage_months / 1000
        if s["stage_id"] == current_stage_id:
            break

    ratio = min(logged_fert_kg / total_expected_kg, 1.0) if total_expected_kg > 0 else 1.0
    score = round(ratio * 100, 1)

    if score >= 85:
        risk_level     = "low"
        interpretation = (f"Good compliance ({score:.0f}/100). Fertilizer inputs are close to the "
                           "recommended schedule. Yield potential is well-maintained.")
    elif score >= 60:
        risk_level     = "moderate"
        interpretation = (f"Moderate compliance ({score:.0f}/100). Consider catching up on "
                           "fertilizer in the next stage to protect yield.")
    else:
        risk_level     = "high"
        interpretation = (f"Low compliance ({score:.0f}/100). Only {score:.0f}% of expected "
                           "fertilizer was logged. Significant yield reduction is likely.")

    return {
        "score":            score,
        "risk_level":       risk_level,
        "interpretation":   interpretation,
        "logged_fert_kg":   round(logged_fert_kg, 1),
        "expected_fert_kg": round(total_expected_kg, 1),
    }
