"""
weather.py — Open-Meteo weather forecast and farm advisory service.

Open-Meteo is free, requires no API key, and works globally.
API docs: https://open-meteo.com/en/docs/

This module:
  1. Fetches a 7-day daily forecast for any lat/lon.
  2. Calculates disease risk score based on temperature, humidity, and rainfall.
  3. Returns a structured advisory object.

All calculations are deterministic — Gemini is not used here.
"""

from __future__ import annotations

import logging
import httpx

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# WMO Weather Code → human description mapping (subset relevant to farming)
WMO_DESCRIPTIONS: dict[int, str] = {
    0:  "Clear sky",
    1:  "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    77: "Snow grains",
    80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}

# Guava disease risk thresholds (based on NIPHM IPM research for guava)
# Source: NIPHM AESA-based IPM package for guava, govt.in
DISEASE_RISK_RULES = [
    {
        "disease": "Anthracnose / Fruit rot",
        "trigger": lambda tmax, tmin, rain_mm, rain_prob: (
            tmax >= 25 and tmax <= 32 and rain_mm > 3 and rain_prob > 60
        ),
        "risk": "High",
        "action": "Apply copper oxychloride (3g/litre) spray within 48 hours.",
        "colour": "red",
    },
    {
        "disease": "Fruit fly",
        "trigger": lambda tmax, tmin, rain_mm, rain_prob: (
            tmax >= 28 and rain_mm < 5
        ),
        "risk": "High",
        "action": "Check methyl eugenol traps daily. Replace lure if older than 15 days.",
        "colour": "red",
    },
    {
        "disease": "Powdery mildew",
        "trigger": lambda tmax, tmin, rain_mm, rain_prob: (
            tmax >= 22 and tmax <= 28 and tmin >= 15 and rain_mm < 1
        ),
        "risk": "Moderate",
        "action": "Monitor young shoots. Apply wettable sulphur (3g/litre) if white powder appears.",
        "colour": "amber",
    },
    {
        "disease": "Stem / Bark borer",
        "trigger": lambda tmax, tmin, rain_mm, rain_prob: (
            tmax >= 30 and rain_mm < 2
        ),
        "risk": "Moderate",
        "action": "Inspect shoot tips for wilting or entry holes. Remove affected shoots immediately.",
        "colour": "amber",
    },
    {
        "disease": "Guava wilt (Fusarium)",
        "trigger": lambda tmax, tmin, rain_mm, rain_prob: (
            rain_mm > 20
        ),
        "risk": "Elevated",
        "action": "Check root zone for waterlogging. Ensure drainage channels are clear.",
        "colour": "amber",
    },
]


def _wmo_to_text(code: int) -> str:
    return WMO_DESCRIPTIONS.get(code, f"Weather code {code}")


def _disease_risks_for_day(tmax: float, tmin: float, rain_mm: float, rain_prob: float) -> list[dict]:
    """Return list of active disease risk advisories for given weather conditions."""
    risks = []
    for rule in DISEASE_RISK_RULES:
        try:
            if rule["trigger"](tmax, tmin, rain_mm, rain_prob):
                risks.append({
                    "disease": rule["disease"],
                    "risk":    rule["risk"],
                    "action":  rule["action"],
                    "colour":  rule["colour"],
                })
        except Exception:
            pass
    return risks


def _irrigation_advisory(et0: float, stage_irrigation_lpd: float | None) -> dict:
    """
    Compare Open-Meteo ET0 (evapotranspiration) with crop reference requirement.

    et0: mm/day from Open-Meteo (proxy for crop water demand)
    stage_irrigation_lpd: reference litres/plant/day from crop knowledge
    """
    if et0 is None:
        return {"status": "unknown", "message": "ET0 data unavailable."}

    # Kc (crop coefficient) for guava ≈ 0.85 during active growth
    kc = 0.85
    etc = et0 * kc  # mm/day actual crop evapotranspiration

    if stage_irrigation_lpd and stage_irrigation_lpd > 0:
        # Convert lpd to mm: assuming 1 m² spacing contribution per plant
        # This is a directional indicator, not an exact calculation
        if etc > 6:
            status = "high_demand"
            msg = f"ET0 is {et0:.1f} mm/day — water demand is high. Do not reduce irrigation today."
        elif etc > 3:
            status = "normal"
            msg = f"ET0 is {et0:.1f} mm/day — normal water demand. Maintain reference schedule."
        else:
            status = "low_demand"
            msg = f"ET0 is {et0:.1f} mm/day — cool/cloudy conditions. You may reduce irrigation by 20%."
        return {"status": status, "et0": round(et0, 2), "etc": round(etc, 2), "message": msg}
    else:
        return {
            "status": "drought_period",
            "et0": round(et0, 2),
            "message": "Drought stress period — do not irrigate.",
        }


async def get_farm_weather(
    latitude: float,
    longitude: float,
    stage_irrigation_lpd: float | None = None,
) -> dict:
    """Fetch 7-day forecast and return structured farm advisory.

    Returns a dict with:
      current       — current conditions
      forecast      — list of 7 day objects
      disease_risks — list of active risk advisories for the next 3 days
      irrigation    — ET0-based irrigation advisory for today
      fetched       — bool, True on success

    On failure returns fetched=False with an error message.
    No exception is raised — callers get degraded but valid data.
    """
    params = {
        "latitude":   latitude,
        "longitude":  longitude,
        "daily": ",".join([
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "precipitation_probability_max",
            "windspeed_10m_max",
            "et0_fao_evapotranspiration",
            "weathercode",
        ]),
        "current_weather": "true",
        "timezone":    "Asia/Kolkata",
        "forecast_days": 7,
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(OPEN_METEO_URL, params=params)
            resp.raise_for_status()
            raw = resp.json()
    except Exception as exc:
        logger.warning("Open-Meteo fetch failed: %s", exc)
        return {"fetched": False, "error": "Weather data temporarily unavailable."}

    daily = raw.get("daily", {})
    times     = daily.get("time", [])
    tmax_list = daily.get("temperature_2m_max", [])
    tmin_list = daily.get("temperature_2m_min", [])
    rain_list = daily.get("precipitation_sum", [])
    rain_prob = daily.get("precipitation_probability_max", [])
    wind_list = daily.get("windspeed_10m_max", [])
    et0_list  = daily.get("et0_fao_evapotranspiration", [])
    wcode_list= daily.get("weathercode", [])

    forecast = []
    all_risks: list[dict] = []

    for i, date_str in enumerate(times):
        tmax = tmax_list[i] if i < len(tmax_list) else None
        tmin = tmin_list[i] if i < len(tmin_list) else None
        rain = rain_list[i] if i < len(rain_list) else 0.0
        prob = rain_prob[i] if i < len(rain_prob) else 0
        wind = wind_list[i] if i < len(wind_list) else None
        et0  = et0_list[i]  if i < len(et0_list)  else None
        wc   = wcode_list[i]if i < len(wcode_list) else 0

        day_risks = _disease_risks_for_day(
            tmax or 25, tmin or 15, rain or 0, prob or 0
        ) if i < 3 else []  # only compute risk for next 3 days

        if i < 3:
            all_risks.extend(day_risks)

        forecast.append({
            "date":        date_str,
            "tmax":        tmax,
            "tmin":        tmin,
            "rain_mm":     round(rain or 0, 1),
            "rain_prob":   prob,
            "wind_kmh":    wind,
            "et0":         et0,
            "weather_desc": _wmo_to_text(wc),
            "weathercode": wc,
        })

    # Deduplicate risks by disease name
    seen = set()
    unique_risks = []
    for r in all_risks:
        if r["disease"] not in seen:
            seen.add(r["disease"])
            unique_risks.append(r)

    # Current conditions
    cw = raw.get("current_weather", {})
    current = {
        "temperature":   cw.get("temperature"),
        "windspeed":     cw.get("windspeed"),
        "weather_desc":  _wmo_to_text(cw.get("weathercode", 0)),
        "weathercode":   cw.get("weathercode", 0),
        "is_day":        cw.get("is_day", 1),
    }

    # ET0 advisory for today
    today_et0 = et0_list[0] if et0_list else None
    irrigation_adv = _irrigation_advisory(today_et0, stage_irrigation_lpd)

    return {
        "fetched":        True,
        "current":        current,
        "forecast":       forecast,
        "disease_risks":  unique_risks,
        "irrigation":     irrigation_adv,
    }
