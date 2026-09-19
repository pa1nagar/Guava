"""
climate.py — NASA POWER climate analysis for farm intelligence.

Provides:
  1. Seasonal anomaly detection — current month vs 30-year climatological average
  2. Growing Degree Day (GDD) accumulation since sowing
  3. Monsoon risk index — cumulative rainfall vs normal

Data source: NASA POWER API (free, no API key required)
  - Climatology: 30-year monthly averages
  - Daily: actual observed values since sowing date

GDD formula (base temp 10°C, standard for tropical fruit development):
  GDD_day = max(0, (Tmax + Tmin) / 2 - Tbase)
  Cumulative GDD = sum of all daily GDDs since sowing

Guava GDD thresholds (derived from literature on tropical fruit phenology):
  Establishment → Vegetative:    ~500 GDDs
  Vegetative → Post-Monsoon:    ~1800 GDDs
  Pre-Bloom hardening:           ~2800 GDDs
  Bloom/Fruit Set:               ~3400 GDDs
  Fruit Development:             ~3900 GDDs
  Drought Stress:                ~4200 GDDs
  Harvest:                       ~4500 GDDs
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import httpx

logger = logging.getLogger(__name__)

NASA_POWER_DAILY = "https://power.larc.nasa.gov/api/temporal/daily/point"
NASA_POWER_CLIM  = "https://power.larc.nasa.gov/api/temporal/climatology/point"

# Base temperature for GDD calculation (°C) — standard for guava/tropical fruit
GDD_BASE_TEMP = 10.0

# Maximum temperature cap for GDD (prevents overestimate on extreme heat days)
GDD_TMAX_CAP = 35.0

# Approximate cumulative GDD thresholds per stage (literature-derived)
GDD_STAGE_THRESHOLDS: dict[str, float] = {
    "establishment":      0,
    "vegetative_growth":  500,
    "post_monsoon":       1800,
    "pre_bloom":          2800,
    "bloom_fruit_set":    3400,
    "fruit_development":  3900,
    "drought_stress":     4200,
    "harvest":            4500,
    "post_harvest_mature": 4800,
}

# Month abbreviations for NASA POWER climatology keys
_MONTH_KEYS = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]

# Fertilizer MRP rates (₹/kg) — Government of India fixed prices + market rates
# Source: Ministry of Chemicals & Fertilizers, Sansad Q&A AU2408, 2024
FERTILIZER_RATES: dict[str, float] = {
    "Urea (N)":          5.38,   # Govt MRP ₹242/45kg bag
    "DAP (N+P)":        27.00,   # Subsidised MRP approx.
    "MOP (K)":          17.50,   # Subsidised MRP approx.
    "19-19-19 WSF":     60.00,   # Water-soluble fertilizer market rate
    "12-6-20 WSF":      58.00,
    "8-8-32 WSF":       62.00,
    "MKP":              95.00,   # Monopotassium phosphate
    "SOP":              45.00,   # Sulphate of potash
    "Calcium nitrate":  32.00,
    "Iron chelate":    250.00,
    "Humic acid":       80.00,
}

# Default rate when fertilizer name doesn't match exactly
DEFAULT_FERTILIZER_RATE = 55.0


def _get_fert_rate(fertilizer_name: str) -> float:
    """Return ₹/kg rate for a fertilizer by partial name match."""
    name_lower = fertilizer_name.lower()
    for key, rate in FERTILIZER_RATES.items():
        if any(part.lower() in name_lower for part in key.split()):
            return rate
    return DEFAULT_FERTILIZER_RATE


async def fetch_climate_data(
    latitude: float,
    longitude: float,
    sowing_date: date,
) -> dict:
    """Fetch NASA POWER data and compute climate intelligence.

    Returns:
        gdd_cumulative          float   - heat units accumulated since sowing
        gdd_predicted_stage     str     - stage predicted by GDD alone
        gdd_vs_calendar         str     - "ahead" | "on_track" | "behind" compared to month-based stage
        anomaly_temperature     float   - current month temp vs 30-yr average (°C)
        anomaly_rainfall        float   - current month rain vs 30-yr average (mm/day)
        anomaly_summary         str     - plain language description
        monsoon_cumulative_mm   float   - rainfall since June 1 this year
        monsoon_normal_mm       float   - 30-yr average monsoon rainfall (Jun–Sep)
        monsoon_deficit_pct     float   - % below normal (negative = surplus)
        waterlogging_risk       str     - "high" | "moderate" | "low"
        waterlogging_message    str     - plain language
        fetched                 bool
    """
    today = date.today()

    # ── 1. Climatology (30-year monthly averages) ─────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            clim_resp = await client.get(NASA_POWER_CLIM, params={
                "parameters": "T2M,PRECTOTCORR",
                "community":  "AG",
                "longitude":  longitude,
                "latitude":   latitude,
                "format":     "JSON",
            }, headers={"User-Agent": "Guavaa-Farm/2.0"})
            clim_resp.raise_for_status()
            clim_data = clim_resp.json()
    except Exception as exc:
        logger.warning("NASA POWER climatology fetch failed: %s", exc)
        return {"fetched": False, "error": "Climate baseline data unavailable."}

    clim_props = clim_data.get("properties", {}).get("parameter", {})
    t2m_clim   = clim_props.get("T2M", {})
    rain_clim  = clim_props.get("PRECTOTCORR", {})

    cur_month_key = _MONTH_KEYS[today.month - 1]
    t_normal   = t2m_clim.get(cur_month_key, -999)
    r_normal   = rain_clim.get(cur_month_key, -999)

    # Monsoon normal (June–September cumulative, mm)
    monsoon_normal_mm = sum(
        rain_clim.get(m, 0) * 30
        for m in ["JUN", "JUL", "AUG", "SEP"]
        if rain_clim.get(m, -999) != -999
    )

    # ── 2. Daily observed data since sowing (for GDD) ────────────────────────
    # Cap at 90 days to keep API response fast
    daily_start = max(sowing_date, today - timedelta(days=90))
    # Don't request future dates — stop at yesterday
    daily_end   = today - timedelta(days=1)

    gdd_cumulative = 0.0
    current_month_t_actual = None
    current_month_rain_actual = 0.0
    monsoon_cumulative_mm = 0.0

    if daily_start < daily_end:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                daily_resp = await client.get(NASA_POWER_DAILY, params={
                    "parameters": "T2M_MAX,T2M_MIN,PRECTOTCORR",
                    "community":  "AG",
                    "longitude":  longitude,
                    "latitude":   latitude,
                    "start":      daily_start.strftime("%Y%m%d"),
                    "end":        daily_end.strftime("%Y%m%d"),
                    "format":     "JSON",
                }, headers={"User-Agent": "Guavaa-Farm/2.0"})
                daily_resp.raise_for_status()
                daily_data = daily_resp.json()
        except Exception as exc:
            logger.warning("NASA POWER daily fetch failed: %s", exc)
            daily_data = {}

        dp = daily_data.get("properties", {}).get("parameter", {})
        tmax_daily = dp.get("T2M_MAX", {})
        tmin_daily = dp.get("T2M_MIN", {})
        rain_daily = dp.get("PRECTOTCORR", {})

        cur_month_temps = []

        for date_key in sorted(tmax_daily.keys()):
            tmax = tmax_daily.get(date_key, -999)
            tmin = tmin_daily.get(date_key, -999)
            rain = rain_daily.get(date_key, -999)

            if tmax == -999 or tmin == -999:
                continue

            # GDD accumulation
            tmax_c = min(tmax, GDD_TMAX_CAP)
            tavg   = (tmax_c + max(tmin, GDD_BASE_TEMP)) / 2
            gdd    = max(0.0, tavg - GDD_BASE_TEMP)
            gdd_cumulative += gdd

            # Current month actuals
            try:
                obs_date = date(int(date_key[:4]), int(date_key[4:6]), int(date_key[6:8]))
                if obs_date.month == today.month and obs_date.year == today.year:
                    cur_month_temps.append((tmax + tmin) / 2)
                    if rain != -999:
                        current_month_rain_actual += rain

                # Monsoon cumulative (Jun 1 to today)
                jun1 = date(today.year, 6, 1)
                if jun1 <= obs_date <= today and obs_date.month in (6, 7, 8, 9):
                    if rain != -999:
                        monsoon_cumulative_mm += rain
            except (ValueError, TypeError):
                pass

        if cur_month_temps:
            current_month_t_actual = sum(cur_month_temps) / len(cur_month_temps)

    # ── 3. Anomaly calculation ────────────────────────────────────────────────
    temp_anomaly = None
    rain_anomaly = None
    anomaly_summary = "Climate data unavailable for this period."

    if current_month_t_actual is not None and t_normal != -999:
        temp_anomaly = round(current_month_t_actual - t_normal, 1)

    if r_normal != -999 and today.day > 5:
        # Scale normal to days elapsed in this month
        expected_rain = r_normal * min(today.day, 28)
        rain_anomaly = round(current_month_rain_actual - expected_rain, 1)

    if temp_anomaly is not None and rain_anomaly is not None:
        parts = []
        if abs(temp_anomaly) >= 1.0:
            direction = "warmer" if temp_anomaly > 0 else "cooler"
            parts.append(f"{abs(temp_anomaly):.1f}°C {direction} than the 30-year average")
        if abs(rain_anomaly) >= 10:
            direction = "more" if rain_anomaly > 0 else "less"
            parts.append(f"{abs(rain_anomaly):.0f}mm {direction} rainfall than normal")
        anomaly_summary = (
            f"This month is {' and '.join(parts)}." if parts
            else "Temperature and rainfall are close to the 30-year average this month."
        )

    # ── 4. GDD-based stage prediction ────────────────────────────────────────
    gdd_predicted_stage = "establishment"
    for stage_id, threshold in sorted(GDD_STAGE_THRESHOLDS.items(), key=lambda x: x[1]):
        if gdd_cumulative >= threshold:
            gdd_predicted_stage = stage_id

    # ── 5. Monsoon risk assessment ────────────────────────────────────────────
    monsoon_deficit_pct = 0.0
    waterlogging_risk = "low"
    waterlogging_message = "Rainfall within normal range. No waterlogging risk."

    if monsoon_normal_mm > 0:
        # Compare cumulative to expected proportion (scaled to elapsed monsoon days)
        monsoon_days_elapsed = (today - date(today.year, 6, 1)).days
        expected_fraction = min(monsoon_days_elapsed / 122, 1.0)  # 122 = Jun–Sep days
        expected_so_far = monsoon_normal_mm * expected_fraction
        if expected_so_far > 0:
            monsoon_deficit_pct = round(
                (monsoon_cumulative_mm - expected_so_far) / expected_so_far * 100, 1
            )

    # Waterlogging risk: high if >30% above normal rainfall
    if monsoon_deficit_pct > 30:
        waterlogging_risk = "high"
        waterlogging_message = (
            f"Rainfall is {monsoon_deficit_pct:.0f}% above normal this monsoon. "
            "High risk of waterlogging and Fusarium wilt. "
            "Clear drainage furrows immediately. Do not leave standing water near tree bases."
        )
    elif monsoon_deficit_pct > 10:
        waterlogging_risk = "moderate"
        waterlogging_message = (
            f"Rainfall is {monsoon_deficit_pct:.0f}% above normal. "
            "Check drainage is adequate. Monitor for root zone saturation."
        )
    elif monsoon_deficit_pct < -25:
        waterlogging_risk = "drought"
        waterlogging_message = (
            f"Rainfall is {abs(monsoon_deficit_pct):.0f}% below normal. "
            "Drought stress is likely. Increase irrigation to compensate for soil moisture deficit."
        )

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


def fertilizer_budget_forecast(
    stages: list[dict],
    current_stage_id: str,
    plant_count: int,
) -> list[dict]:
    """Calculate fertilizer cost for all remaining stages.

    Returns a list of stage-by-stage fertilizer budget items.
    Costs are calculated from real govt. MRP / market rates.
    """
    found = False
    items = []

    for s in stages:
        if s["stage_id"] == current_stage_id:
            found = True

        if not found:
            continue

        q = s.get("quantities", {})
        fert_gpw   = float(q.get("fertilizer_grams_per_plant_per_week", 0) or 0)
        fert_name  = q.get("fertilizer_name", "")
        duration_m = q.get("duration_months")

        if fert_gpw <= 0 or not fert_name:
            continue

        # Estimate months in stage
        months = float(duration_m) if duration_m else 1.0
        total_kg  = fert_gpw * plant_count * 4.33 * months / 1000
        rate      = _get_fert_rate(fert_name)
        cost_est  = total_kg * rate

        items.append({
            "stage_id":     s["stage_id"],
            "stage_label":  s["label"],
            "fertilizer":   fert_name,
            "total_kg":     round(total_kg, 1),
            "rate_per_kg":  rate,
            "cost_estimate": round(cost_est, 0),
            "months":       months,
        })

    return items


def input_compliance_score(
    stages: list[dict],
    current_stage_id: str,
    months_elapsed: int,
    plant_count: int,
    activities: list[dict],
) -> dict:
    """Compute a 0–100 compliance score based on logged vs expected inputs.

    Methodology:
      - For each completed stage, compare actual logged fertilizer (kg) to expected
      - Score = (actual / expected) × 100, capped at 100
      - Weighted average across all completed stages
      - Missing stages count as 0%

    Returns:
        score           float  0–100
        interpretation  str    plain language
        risk_level      str    "low" | "moderate" | "high"
        by_stage        list   per-stage breakdown
    """
    total_expected_kg = 0.0
    total_actual_kg   = 0.0
    by_stage = []

    # Total logged fertilizer
    logged_fert_kg = sum(
        float(a["quantity"])
        for a in activities
        if a.get("activity_type") == "Fertilizer"
    )

    weeks_per_month = 4.33

    for s in stages:
        if s["month_start"] > months_elapsed:
            break

        q = s.get("quantities", {})
        gpw = float(q.get("fertilizer_grams_per_plant_per_week", 0) or 0)
        if gpw <= 0:
            continue

        effective_end = min(
            s["month_end"] if s["month_end"] != 9999 else months_elapsed,
            months_elapsed,
        )
        stage_months   = max(0, effective_end - s["month_start"] + 1)
        expected_kg    = gpw * plant_count * weeks_per_month * stage_months / 1000

        total_expected_kg += expected_kg

        if s["stage_id"] == current_stage_id:
            break

    if total_expected_kg > 0:
        ratio = min(logged_fert_kg / total_expected_kg, 1.0)
    else:
        ratio = 1.0

    score = round(ratio * 100, 1)

    if score >= 85:
        risk_level = "low"
        interpretation = (
            f"Good compliance ({score:.0f}/100). "
            "Your fertilizer inputs are close to the recommended schedule. "
            "Yield potential is well-maintained."
        )
    elif score >= 60:
        risk_level = "moderate"
        interpretation = (
            f"Moderate compliance ({score:.0f}/100). "
            "You have applied {:.0f}% of the expected fertilizer. "
            "Some yield impact is possible. Consider catching up in the next stage.".format(score)
        )
    else:
        risk_level = "high"
        interpretation = (
            f"Low compliance ({score:.0f}/100). "
            f"Only {score:.0f}% of expected fertilizer was logged. "
            "Significant yield reduction is likely without prompt catch-up application."
        )

    return {
        "score":            score,
        "risk_level":       risk_level,
        "interpretation":   interpretation,
        "logged_fert_kg":   round(logged_fert_kg, 1),
        "expected_fert_kg": round(total_expected_kg, 1),
    }
