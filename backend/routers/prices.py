"""
prices.py — Real guava mandi prices (Agmarknet / data.gov.in).

GET  /api/market-prices/guava            Latest prices near the farmer's district
GET  /api/market-prices/guava/history    Saved daily history for one mandi
POST /api/admin/market-prices/ingest      Manual ingestion trigger (admin token)

All numbers come from rows saved by services/mandi_prices.py. Nothing is
estimated. Every price carries its source, trade date and a stale flag
(older than 7 days). The farmer's location comes from the JWT user's profile,
never from the request.
"""

# ── Multi-tenant isolation ──────────────────────────────────────────────────
# Security: user_id is always derived from JWT via Depends(get_user_id).
# Market prices are public data; only the farmer's district/state is read from
# their own profile row (filtered by user_id).
# Requirements: 3.2, 3.3, 3.4

import hmac
import logging
import os
from datetime import date, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from services.auth import get_user_id
from services.db import get_db
from services.geo import get_exact_district_coordinates, haversine_km
from services.mandi_prices import (
    COMMODITY,
    MIN_TREND_DAYS,
    SOURCE_NAME,
    is_stale,
    per_kg,
    run_ingestion,
)
from services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

router = APIRouter()

ATTRIBUTION = "Source: Agmarknet / data.gov.in"
LATEST_WINDOW_DAYS = 60       # how far back to look for each mandi's latest price
NEARBY_MAX_KM = 300.0         # district-centre to district-centre distance
_ROW_LIMIT = 5000

_PRICE_COLUMNS = (
    "state, district, market_name, variety, grade, min_price, max_price, "
    "modal_price, arrival_date, source_name, fetched_at"
)

_read_limiter = RateLimiter("market_prices")
_admin_limiter = RateLimiter("admin_ingest")

_TIER_RANK = {"same_district": 0, "nearby": 1, "same_state": 2}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_location(user_id: str) -> dict:
    db = get_db()
    try:
        result = (
            db.table("farmers")
            .select("state, district")
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


def _same(a: Any, b: Any) -> bool:
    return str(a or "").strip().lower() == str(b or "").strip().lower()


def _price_row(r: dict) -> dict:
    return {
        "variety": r.get("variety") or "",
        "grade": r.get("grade") or "",
        "modal_per_kg": per_kg(r.get("modal_price")),
        "min_per_kg": per_kg(r.get("min_price")),
        "max_per_kg": per_kg(r.get("max_price")),
        "modal_per_quintal": r.get("modal_price"),
        "min_per_quintal": r.get("min_price"),
        "max_per_quintal": r.get("max_price"),
    }


def build_mandi_board(
    rows: list[dict],
    state: str,
    district: str,
    limit: int,
    today: Optional[date] = None,
    max_km: float = NEARBY_MAX_KM,
) -> dict:
    """Pick each mandi's latest prices and rank them for a farmer's location.

    Ranking: same district, then mandis whose district centre is within max_km
    (nearest first), then the rest of the same state. Mandis outside the state
    and beyond max_km, or outside the state with no known district location,
    are not shown. Pure function: no I/O.
    """
    today = today or date.today()
    origin = get_exact_district_coordinates(state, district)

    # rows arrive newest first; keep each mandi's newest trade date only.
    latest_date: dict[tuple, str] = {}
    by_mandi: dict[tuple, list[dict]] = {}
    for r in rows:
        trade = r.get("arrival_date")
        if not trade:
            continue
        key = (r.get("state") or "", r.get("district") or "", r.get("market_name") or "")
        if key not in latest_date or trade > latest_date[key]:
            latest_date[key] = trade
            by_mandi[key] = []
        if trade == latest_date[key]:
            by_mandi[key].append(r)

    candidates: list[dict] = []
    for (m_state, m_district, m_market), mrows in by_mandi.items():
        distance = None
        if origin is not None:
            coords = get_exact_district_coordinates(m_state, m_district)
            if coords is not None:
                distance = round(haversine_km(origin, coords), 0)

        if _same(m_state, state) and _same(m_district, district):
            tier = "same_district"
        elif distance is not None and distance <= max_km:
            tier = "nearby"
        elif _same(m_state, state):
            tier = "same_state"
        else:
            continue

        trade_date = date.fromisoformat(latest_date[(m_state, m_district, m_market)])
        mrows = sorted(mrows, key=lambda r: ((r.get("variety") or ""), (r.get("grade") or "")))
        candidates.append({
            "market": m_market,
            "district": m_district,
            "state": m_state,
            "match": tier,
            "distance_km": distance,
            "trade_date": trade_date.isoformat(),
            "is_stale": is_stale(trade_date, today),
            "source": mrows[0].get("source_name") or SOURCE_NAME,
            "fetched_at": max((r.get("fetched_at") or "") for r in mrows) or None,
            "prices": [_price_row(r) for r in mrows],
        })

    candidates.sort(key=lambda c: (
        _TIER_RANK[c["match"]],
        c["distance_km"] if c["distance_km"] is not None else float("inf"),
        c["market"],
    ))
    mandis = candidates[:limit]

    tiers = {m["match"] for m in mandis}
    if not mandis:
        scope, note = "none", "No saved guava prices for your area yet."
    elif "same_state" in tiers:
        scope = "state"
        note = (
            "Not enough mandis with a known location near your district, so some "
            "prices are from other mandis in your state."
        )
    elif "nearby" in tiers:
        scope = "nearby"
        note = (
            "Nearby mandis are ranked by distance between district centres "
            "(approximate; exact mandi locations are not stored)."
        )
    else:
        scope, note = "district", "Prices from mandis in your district."

    as_of = max((m["trade_date"] for m in mandis), default=None)
    return {
        "commodity": COMMODITY,
        "source": SOURCE_NAME,
        "attribution": ATTRIBUTION,
        "unit": "Rs/kg (Agmarknet reports Rs/quintal; divided by 100)",
        "location": {
            "state": state,
            "district": district,
            "district_location_known": origin is not None,
        },
        "scope": scope,
        "scope_note": note,
        "as_of": as_of,
        "has_data": bool(mandis),
        "is_stale": all(m["is_stale"] for m in mandis) if mandis else True,
        "mandis": mandis,
    }


def _select_latest_rows(db: Any, since: date) -> list[dict]:
    try:
        result = (
            db.table("market_prices")
            .select(_PRICE_COLUMNS)
            .eq("commodity", COMMODITY)
            .gte("arrival_date", since.isoformat())
            .order("arrival_date", desc=True)
            .limit(_ROW_LIMIT)
            .execute()
        )
    except Exception as exc:
        logger.error("DB select market_prices failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")
    return result.data or []


def build_history(rows: list[dict], today: Optional[date] = None) -> dict:
    """Aggregate one mandi's saved rows into a per-day series (oldest first).

    Per day: modal is the mean of that day's modal prices across varieties and
    grades, min is the lowest min, max is the highest max.
    """
    today = today or date.today()
    days: dict[str, list[dict]] = {}
    for r in rows:
        if r.get("arrival_date"):
            days.setdefault(r["arrival_date"], []).append(r)

    series = []
    for d in sorted(days):
        drows = days[d]
        modals = [float(r["modal_price"]) for r in drows if r.get("modal_price") is not None]
        mins = [float(r["min_price"]) for r in drows if r.get("min_price") is not None]
        maxs = [float(r["max_price"]) for r in drows if r.get("max_price") is not None]
        series.append({
            "trade_date": d,
            "modal_per_kg": per_kg(sum(modals) / len(modals)) if modals else None,
            "min_per_kg": per_kg(min(mins)) if mins else None,
            "max_per_kg": per_kg(max(maxs)) if maxs else None,
            "rows": len(drows),
        })

    distinct = len(series)
    has_trend = distinct >= MIN_TREND_DAYS
    last = date.fromisoformat(series[-1]["trade_date"]) if series else None
    return {
        "source": SOURCE_NAME,
        "attribution": ATTRIBUTION,
        "series": series,
        "distinct_days": distinct,
        "first_date": series[0]["trade_date"] if series else None,
        "last_date": series[-1]["trade_date"] if series else None,
        "is_stale": is_stale(last, today) if last else True,
        "has_trend": has_trend,
        "min_days_for_trend": MIN_TREND_DAYS,
        "message": None if has_trend else (
            "Not enough price history yet. Prices are saved once a day, so a "
            f"trend appears after {MIN_TREND_DAYS} days of saved data "
            f"({distinct} so far)."
        ),
    }


# ── GET /api/market-prices/guava ──────────────────────────────────────────────

@router.get("/market-prices/guava")
async def get_guava_prices(
    limit: int = Query(5, ge=1, le=20),
    user_id: str = Depends(get_user_id),
    _: None = Depends(_read_limiter),
) -> dict:
    """Latest saved guava mandi prices for the farmer's district and state."""
    loc = _get_location(user_id)
    db = get_db()
    since = date.today() - timedelta(days=LATEST_WINDOW_DAYS)
    rows = _select_latest_rows(db, since)
    return build_mandi_board(rows, loc["state"], loc["district"], limit)


# ── GET /api/market-prices/guava/history ──────────────────────────────────────

@router.get("/market-prices/guava/history")
async def get_guava_price_history(
    market: Optional[str] = Query(None, max_length=120),
    state: Optional[str] = Query(None, max_length=80),
    days: int = Query(90, ge=7, le=730),
    user_id: str = Depends(get_user_id),
    _: None = Depends(_read_limiter),
) -> dict:
    """Saved daily history for one mandi (default: the closest mandi with data)."""
    loc = _get_location(user_id)
    db = get_db()

    if not market:
        since = date.today() - timedelta(days=LATEST_WINDOW_DAYS)
        board = build_mandi_board(
            _select_latest_rows(db, since), loc["state"], loc["district"], 1
        )
        if not board["mandis"]:
            empty = build_history([])
            return {**empty, "market": None, "state": loc["state"]}
        market = board["mandis"][0]["market"]
        state = board["mandis"][0]["state"]

    try:
        query = (
            db.table("market_prices")
            .select(_PRICE_COLUMNS)
            .eq("commodity", COMMODITY)
            .eq("market_name", market)
            .gte("arrival_date", (date.today() - timedelta(days=days)).isoformat())
        )
        if state:
            query = query.eq("state", state)
        result = query.order("arrival_date", desc=False).limit(_ROW_LIMIT).execute()
    except Exception as exc:
        logger.error("DB select market_prices history failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    return {**build_history(result.data or []), "market": market, "state": state}


# ── POST /api/admin/market-prices/ingest ──────────────────────────────────────

@router.post("/admin/market-prices/ingest")
def trigger_ingestion(
    x_admin_token: Optional[str] = Header(None),
    _: None = Depends(_admin_limiter),
) -> dict:
    """Run the mandi ingestion now. Requires header X-Admin-Token.

    The token is read from PRICE_INGEST_ADMIN_TOKEN. When that variable is not
    set the endpoint is disabled (503) rather than open.
    """
    expected = os.environ.get("PRICE_INGEST_ADMIN_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=503, detail="Manual ingestion is not configured.")
    if not x_admin_token or not hmac.compare_digest(x_admin_token.encode(), expected.encode()):
        raise HTTPException(status_code=403, detail="Forbidden.")
    return run_ingestion()
