"""
weather.py — Open-Meteo weather forecast and farm advisory service.

Open-Meteo is free, requires no API key, and works globally.
API docs: https://open-meteo.com/en/docs/

Uses urllib (standard library) for HTTP — no httpx dependency.
Runs synchronously but is called via asyncio.get_event_loop().run_in_executor
so it does not block FastAPI's event loop.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

WMO_DESCRIPTIONS: dict[int, str] = {
    0:  "Clear sky",
    1:  "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail",
}

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
        "trigger": lambda tmax, tmin, rain_mm, rain_prob: rain_mm > 20,
        "risk": "Elevated",
        "action": "Check root zone for waterlogging. Ensure drainage channels are clear.",
        "colour": "amber",
    },
]


def _wmo_to_text(code: int) -> str:
    return WMO_DESCRIPTIONS.get(code, f"Weather code {code}")


def _disease_risks_for_day(tmax, tmin, rain_mm, rain_prob) -> list[dict]:
    risks = []
    for rule in DISEASE_RISK_RULES:
        try:
            if rule["trigger"](tmax or 25, tmin or 15, rain_mm or 0, rain_prob or 0):
                risks.append({
                    "disease": rule["disease"],
                    "risk":    rule["risk"],
                    "action":  rule["action"],
                    "colour":  rule["colour"],
                })
        except Exception:
            pass
    return risks


def _irrigation_advisory(et0, stage_irrigation_lpd) -> dict:
    if et0 is None:
        return {"status": "unknown", "message": "ET0 data unavailable."}
    kc  = 0.85
    etc = et0 * kc
    if not stage_irrigation_lpd or stage_irrigation_lpd == 0:
        return {"status": "drought_period", "et0": round(et0, 2),
                "message": "Drought stress period — do not irrigate."}
    if etc > 6:
        return {"status": "high_demand", "et0": round(et0, 2), "etc": round(etc, 2),
                "message": f"ET0 is {et0:.1f} mm/day — water demand is high. Do not reduce irrigation today."}
    if etc > 3:
        return {"status": "normal", "et0": round(et0, 2), "etc": round(etc, 2),
                "message": f"ET0 is {et0:.1f} mm/day — normal water demand. Maintain reference schedule."}
    return {"status": "low_demand", "et0": round(et0, 2), "etc": round(etc, 2),
            "message": f"ET0 is {et0:.1f} mm/day — cool/cloudy conditions. You may reduce irrigation by 20%."}


def _fetch_weather_sync(latitude: float, longitude: float,
                        stage_irrigation_lpd: float | None = None) -> dict:
    """Synchronous weather fetch using urllib. Called in a thread executor."""
    params = urllib.parse.urlencode({
        "latitude":   latitude,
        "longitude":  longitude,
        "daily":      "temperature_2m_max,temperature_2m_min,precipitation_sum,"
                      "precipitation_probability_max,windspeed_10m_max,"
                      "et0_fao_evapotranspiration,weathercode",
        "current_weather": "true",
        "timezone":   "Asia/Kolkata",
        "forecast_days": 7,
    })
    url = f"{OPEN_METEO_URL}?{params}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Guavaa-Farm/2.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = json.loads(r.read())
    except Exception as exc:
        logger.warning("Open-Meteo fetch failed: %s", exc)
        return {"fetched": False, "error": "Weather data temporarily unavailable."}

    daily     = raw.get("daily", {})
    times     = daily.get("time", [])
    tmax_list = daily.get("temperature_2m_max", [])
    tmin_list = daily.get("temperature_2m_min", [])
    rain_list = daily.get("precipitation_sum", [])
    rain_prob = daily.get("precipitation_probability_max", [])
    wind_list = daily.get("windspeed_10m_max", [])
    et0_list  = daily.get("et0_fao_evapotranspiration", [])
    wcode_list= daily.get("weathercode", [])

    forecast   = []
    all_risks: list[dict] = []

    for i, date_str in enumerate(times):
        tmax = tmax_list[i] if i < len(tmax_list) else None
        tmin = tmin_list[i] if i < len(tmin_list) else None
        rain = rain_list[i] if i < len(rain_list) else 0.0
        prob = rain_prob[i] if i < len(rain_prob) else 0
        wind = wind_list[i] if i < len(wind_list) else None
        et0  = et0_list[i]  if i < len(et0_list)  else None
        wc   = wcode_list[i]if i < len(wcode_list) else 0

        if i < 3:
            all_risks.extend(_disease_risks_for_day(tmax, tmin, rain, prob))

        forecast.append({
            "date":         date_str,
            "tmax":         tmax,
            "tmin":         tmin,
            "rain_mm":      round(rain or 0, 1),
            "rain_prob":    prob,
            "wind_kmh":     wind,
            "et0":          et0,
            "weather_desc": _wmo_to_text(wc),
            "weathercode":  wc,
        })

    # Deduplicate risks
    seen: set = set()
    unique_risks = []
    for r in all_risks:
        if r["disease"] not in seen:
            seen.add(r["disease"])
            unique_risks.append(r)

    cw = raw.get("current_weather", {})
    current = {
        "temperature":  cw.get("temperature"),
        "windspeed":    cw.get("windspeed"),
        "weather_desc": _wmo_to_text(cw.get("weathercode", 0)),
        "weathercode":  cw.get("weathercode", 0),
        "is_day":       cw.get("is_day", 1),
    }

    today_et0      = et0_list[0] if et0_list else None
    irrigation_adv = _irrigation_advisory(today_et0, stage_irrigation_lpd)

    return {
        "fetched":       True,
        "current":       current,
        "forecast":      forecast,
        "disease_risks": unique_risks,
        "irrigation":    irrigation_adv,
    }


async def get_farm_weather(
    latitude: float,
    longitude: float,
    stage_irrigation_lpd: float | None = None,
) -> dict:
    """Async wrapper — runs the sync fetch in a thread so it doesn't block."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _fetch_weather_sync, latitude, longitude, stage_irrigation_lpd
    )
