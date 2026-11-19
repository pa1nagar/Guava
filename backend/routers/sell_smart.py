"""
sell_smart.py - "Where and when to sell" for guava farmers.

GET  /api/sell-smart/settings                 Cost settings and transport suggestion
PUT  /api/sell-smart/settings                 Save cost settings (replaces all fields)
GET  /api/sell-smart/ranking                  Nearby mandis ranked by net Rs/kg
GET  /api/sell-smart/trends                   7/14/30-day change, volatility, seasonal view
GET  /api/sell-smart/quality                  Data quality summary and flagged rows
GET  /api/sell-smart/alerts                   List price alerts
POST /api/sell-smart/alerts                   Create a price alert
PUT  /api/sell-smart/alerts/{id}              Update a price alert
POST /api/sell-smart/alerts/{id}/delete       Remove a price alert (soft delete)
GET  /api/sell-smart/notifications            List notifications
POST /api/sell-smart/notifications/{id}/read  Mark a notification read
GET  /api/sell-smart/fairness                 Compare the logged sale with the market

Every number comes from saved Agmarknet rows or from values the farmer typed.
No AI is used and nothing is forecast. Responses carry i18n keys plus
parameters for display text; coordinates never leave the server (only the
location basis and distances do).
"""

# -- Multi-tenant isolation ---------------------------------------------------
# Security: user_id is always derived from the JWT via Depends(get_user_id),
# never from the request. Every user-data repository call passes it, and alert
# and notification ids are checked against it (404 for another farmer's id).
# Market prices and quality flags are public data.

import logging
from datetime import date, timedelta
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from services.auth import get_user_id
from services.mandi_prices import SOURCE_NAME
from services.rate_limiter import RateLimiter
from services.sell_smart import alerts as alerts_mod
from services.sell_smart import config as cfg
from services.sell_smart import fairness as fairness_mod
from services.sell_smart import locations, quality, ranking, stats
from services.sell_smart.jobs import LOOKBACK_DAYS, annotate_with_stored
from services.sell_smart.repo import RepoError, SellSmartRepo, get_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sell-smart")

ATTRIBUTION = "Source: Agmarknet / data.gov.in"
MAX_ROAD_KM_OVERRIDES = 50   # abuse cap on the size of the road-km map
MAX_FLAGGED_ROWS = 50        # abuse cap on the flagged-row list in /quality
MAX_NOTIFICATIONS = 100      # abuse cap on one notifications page

_read_limiter = RateLimiter("sell_smart_read")
_write_limiter = RateLimiter("sell_smart_write")

_DISTANCE_LABEL_KEYS = {
    ranking.DISTANCE_BASIS_STRAIGHT: "sell_distance_straight",
    ranking.DISTANCE_BASIS_ENTERED: "sell_distance_entered",
}


# -- Models ---------------------------------------------------------------------

class SettingsIn(BaseModel):
    """All fields are replaced on save; null clears a value."""
    transport_mode: Optional[Literal["per_quintal_per_km", "flat_per_quintal"]] = None
    transport_rs_per_quintal_per_km: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    transport_rs_per_quintal_flat: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    handling_rs_per_quintal: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    commission_pct: Optional[float] = Field(default=None, ge=0, le=cfg.MAX_COMMISSION_PCT, allow_inf_nan=False)
    radius_km: Optional[float] = Field(default=None, gt=0, le=cfg.MAX_RADIUS_KM, allow_inf_nan=False)
    road_km_overrides: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check(self):
        if self.transport_mode == "per_quintal_per_km" and self.transport_rs_per_quintal_per_km is None:
            raise ValueError("transport_rs_per_quintal_per_km is required for this transport_mode")
        if self.transport_mode == "flat_per_quintal" and self.transport_rs_per_quintal_flat is None:
            raise ValueError("transport_rs_per_quintal_flat is required for this transport_mode")
        if len(self.road_km_overrides) > MAX_ROAD_KM_OVERRIDES:
            raise ValueError(f"at most {MAX_ROAD_KM_OVERRIDES} road_km_overrides")
        for key, km in self.road_km_overrides.items():
            if not key or len(key) > 3 * cfg.MAX_NAME_LENGTH + 2:
                raise ValueError("invalid road_km_overrides key")
            if not (0 <= km <= cfg.MAX_RADIUS_KM) or km != km:
                raise ValueError("road_km_overrides values must be between 0 and the maximum radius")
        return self


class AlertIn(BaseModel):
    state: str = Field(min_length=1, max_length=cfg.MAX_NAME_LENGTH)
    district: Optional[str] = Field(default=None, max_length=cfg.MAX_NAME_LENGTH)
    market_name: Optional[str] = Field(default=None, max_length=cfg.MAX_NAME_LENGTH)
    target_rs_per_kg: float = Field(gt=0, allow_inf_nan=False)
    direction: Literal["at_or_above", "at_or_below"] = "at_or_above"


class AlertUpdate(BaseModel):
    state: Optional[str] = Field(default=None, min_length=1, max_length=cfg.MAX_NAME_LENGTH)
    district: Optional[str] = Field(default=None, max_length=cfg.MAX_NAME_LENGTH)
    market_name: Optional[str] = Field(default=None, max_length=cfg.MAX_NAME_LENGTH)
    target_rs_per_kg: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)
    direction: Optional[Literal["at_or_above", "at_or_below"]] = None
    is_active: Optional[bool] = None


# -- Helpers --------------------------------------------------------------------

def _db(fn, *args, **kwargs):
    """Call a repository method; a storage failure becomes a generic 500."""
    try:
        return fn(*args, **kwargs)
    except RepoError:
        raise HTTPException(status_code=500, detail="Database error.")


def _today() -> date:
    return date.today()


def _num(value) -> Optional[float]:
    return None if value is None else float(value)


def _require_location(repo: SellSmartRepo, user_id: str) -> dict:
    loc = _db(repo.get_location, user_id)
    if not loc:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return loc


def _origin(loc: Optional[dict]) -> tuple[Optional[tuple[float, float]], Optional[str]]:
    """(lat, lon) and the basis label. The coordinates stay on the server."""
    if not loc:
        return None, None
    if loc.get("farm_lat") is not None and loc.get("farm_lon") is not None:
        return (float(loc["farm_lat"]), float(loc["farm_lon"])), "farm_gps"
    found = locations.resolve_district(loc.get("state"), loc.get("district"))
    if found is not None:
        return (found[0], found[1]), "district_centre"
    return None, None


def _settings_for_ranking(row: Optional[dict]) -> dict:
    row = row or {}
    mode = row.get("transport_mode")
    value = None
    if mode == ranking.MODE_PER_KM:
        value = row.get("transport_rs_per_quintal_per_km")
    elif mode == ranking.MODE_FLAT:
        value = row.get("transport_rs_per_quintal_flat")
    return {
        "transport_mode": mode,
        "transport_value": value,
        "handling_rs_per_quintal": row.get("handling_rs_per_quintal"),
        "commission_pct": row.get("commission_pct"),
        "road_km_overrides": row.get("road_km_overrides") or {},
    }


def _settings_view(row: Optional[dict]) -> dict:
    row = row or {}
    return {
        "transport_mode": row.get("transport_mode"),
        "transport_rs_per_quintal_per_km": _num(row.get("transport_rs_per_quintal_per_km")),
        "transport_rs_per_quintal_flat": _num(row.get("transport_rs_per_quintal_flat")),
        "handling_rs_per_quintal": _num(row.get("handling_rs_per_quintal")),
        "commission_pct": _num(row.get("commission_pct")),
        "radius_km": _num(row.get("radius_km")),
        "road_km_overrides": row.get("road_km_overrides") or {},
    }


def _annotated_rows(repo: SellSmartRepo, **kwargs) -> list[dict]:
    rows = _db(repo.get_price_rows, **kwargs)
    ids = [r["id"] for r in rows if r.get("id")]
    stored = _db(repo.get_quality, ids) if ids else {}
    return annotate_with_stored(rows, stored)


def _alert_view(a: dict) -> dict:
    return {
        "id": str(a.get("id")),
        "state": a.get("state"),
        "district": a.get("district"),
        "market_name": a.get("market_name"),
        "target_rs_per_kg": _num(a.get("target_rs_per_kg")),
        "direction": a.get("direction"),
        "is_active": bool(a.get("is_active")),
        "last_trigger_date": a.get("last_trigger_date"),
        "created_at": a.get("created_at"),
    }


def _notification_view(n: dict) -> dict:
    return {
        "id": str(n.get("id")),
        "kind": n.get("kind"),
        "alert_id": str(n["alert_id"]) if n.get("alert_id") else None,
        "payload": n.get("payload") or {},
        "read_at": n.get("read_at"),
        "created_at": n.get("created_at"),
    }


# -- Settings -------------------------------------------------------------------

@router.get("/settings")
async def get_settings(
    user_id: str = Depends(get_user_id),
    repo: SellSmartRepo = Depends(get_repo),
    _: None = Depends(_read_limiter),
) -> dict:
    row = _db(repo.get_settings, user_id)
    loc = _db(repo.get_location, user_id)
    _, basis = _origin(loc)
    harvests = _db(repo.get_harvests, user_id)
    costs_set = ranking.compute_costs(_settings_for_ranking(row), None, 1.0)["costs_set"]
    return {
        "settings": _settings_view(row),
        "costs_set": costs_set,
        "default_radius_km": cfg.DEFAULT_RADIUS_KM,
        "max_radius_km": cfg.MAX_RADIUS_KM,
        "location_basis": basis,
        "transport_suggestion": ranking.suggest_transport(harvests),
    }


@router.put("/settings")
async def put_settings(
    body: SettingsIn,
    user_id: str = Depends(get_user_id),
    repo: SellSmartRepo = Depends(get_repo),
    _: None = Depends(_write_limiter),
) -> dict:
    values = body.model_dump()
    saved = _db(repo.put_settings, user_id, values)
    costs_set = ranking.compute_costs(_settings_for_ranking(saved), None, 1.0)["costs_set"]
    return {"settings": _settings_view(saved), "costs_set": costs_set}


# -- Ranking --------------------------------------------------------------------

@router.get("/ranking")
async def get_ranking(
    radius_km: Optional[float] = Query(None, gt=0, le=cfg.MAX_RADIUS_KM),
    user_id: str = Depends(get_user_id),
    repo: SellSmartRepo = Depends(get_repo),
    _: None = Depends(_read_limiter),
) -> dict:
    loc = _require_location(repo, user_id)
    row = _db(repo.get_settings, user_id)
    origin, basis = _origin(loc)
    radius = radius_km or _num((row or {}).get("radius_km")) or cfg.DEFAULT_RADIUS_KM
    today = _today()
    rows = _annotated_rows(repo, since=today - timedelta(days=LOOKBACK_DAYS))

    result = ranking.rank_mandis(rows, origin, _settings_for_ranking(row), radius, today)

    flags_by_mandi: dict[tuple, set] = {}
    for r in rows:
        key = (ranking.mandi_id(r), str(r.get("arrival_date")))
        flags_by_mandi.setdefault(key, set()).update(r.get("flags") or [])

    def enrich(entry: dict) -> dict:
        flags = sorted(flags_by_mandi.get((entry["id"], entry["trade_date"]), set()))
        return {
            **entry,
            "is_stale": entry["stale"],
            "source": SOURCE_NAME,
            "quality_flags": flags,
            "distance_label_key": _DISTANCE_LABEL_KEYS.get(entry.get("distance_basis")),
        }

    ranked = [enrich(e) for e in result["ranked"]]
    unranked = [enrich(e) for e in result["unranked"]]
    return {
        **result,
        "ranked": ranked,
        "unranked": unranked,
        "source": SOURCE_NAME,
        "attribution": ATTRIBUTION,
        "unit": "Rs/kg (Agmarknet reports Rs/quintal; divided by 100)",
        "location_basis": basis,
        "has_data": bool(ranked or unranked or result["outside_radius"]),
        "quality": quality.summarise_quality(rows, today),
        "as_of": max((e["trade_date"] for e in ranked + unranked), default=None),
    }


# -- Trends ---------------------------------------------------------------------

@router.get("/trends")
async def get_trends(
    market: Optional[str] = Query(None, max_length=cfg.MAX_NAME_LENGTH),
    state: Optional[str] = Query(None, max_length=cfg.MAX_NAME_LENGTH),
    district: Optional[str] = Query(None, max_length=cfg.MAX_NAME_LENGTH),
    user_id: str = Depends(get_user_id),
    repo: SellSmartRepo = Depends(get_repo),
    _: None = Depends(_read_limiter),
) -> dict:
    if not (market or state or district):
        loc = _require_location(repo, user_id)
        state, district = loc.get("state"), loc.get("district")
    today = _today()
    rows = _annotated_rows(repo, state=state, district=district, market_name=market)
    series = stats.daily_series(rows)
    return {
        "scope": {"market": market, "state": state, "district": district},
        "source": SOURCE_NAME,
        "attribution": ATTRIBUTION,
        "unit": "Rs/kg (Agmarknet reports Rs/quintal; divided by 100)",
        "has_data": bool(series),
        "series": [
            {"trade_date": p["date"].isoformat(), "value_per_kg": p["value"],
             "n_rows": p["n_rows"], "n_mandis": p["n_mandis"]}
            for p in series
        ],
        "windows": stats.window_changes(series, today),
        "volatility": stats.volatility(series, today),
        "seasonal": stats.seasonal_view(series, today),
        "quality": quality.summarise_quality(rows, today),
    }


# -- Quality --------------------------------------------------------------------

@router.get("/quality")
async def get_quality(
    user_id: str = Depends(get_user_id),
    repo: SellSmartRepo = Depends(get_repo),
    _: None = Depends(_read_limiter),
) -> dict:
    today = _today()
    rows = _annotated_rows(repo, since=today - timedelta(days=LOOKBACK_DAYS))
    flagged = [r for r in rows if r.get("flags")]
    flagged.sort(key=lambda r: str(r.get("arrival_date")), reverse=True)
    return {
        "source": SOURCE_NAME,
        "attribution": ATTRIBUTION,
        "window_days": LOOKBACK_DAYS,
        "summary": quality.summarise_quality(rows, today),
        "flagged": [
            {
                "state": r.get("state"), "district": r.get("district"),
                "market_name": r.get("market_name"), "variety": r.get("variety"),
                "grade": r.get("grade"), "trade_date": r.get("arrival_date"),
                "modal_per_quintal": _num(r.get("modal_price")),
                "flags": r.get("flags"), "severity": r.get("severity"),
                "source": r.get("source_name") or SOURCE_NAME,
            }
            for r in flagged[:MAX_FLAGGED_ROWS]
        ],
        "flagged_total": len(flagged),
    }


# -- Alerts ---------------------------------------------------------------------

def _owned_alert(repo: SellSmartRepo, user_id: str, alert_id: UUID) -> dict:
    alert = _db(repo.get_alert, user_id, str(alert_id))
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")
    return alert


@router.get("/alerts")
async def list_alerts(
    user_id: str = Depends(get_user_id),
    repo: SellSmartRepo = Depends(get_repo),
    _: None = Depends(_read_limiter),
) -> dict:
    alerts = [_alert_view(a) for a in _db(repo.list_alerts, user_id)]
    return {
        "alerts": alerts,
        "active_count": sum(1 for a in alerts if a["is_active"]),
        "max_alerts": cfg.MAX_ALERTS_PER_FARMER,
        "directions": list(alerts_mod.DIRECTIONS),
    }


@router.post("/alerts", status_code=201)
async def create_alert(
    body: AlertIn,
    user_id: str = Depends(get_user_id),
    repo: SellSmartRepo = Depends(get_repo),
    _: None = Depends(_write_limiter),
) -> dict:
    if _db(repo.count_active_alerts, user_id) >= cfg.MAX_ALERTS_PER_FARMER:
        raise HTTPException(
            status_code=409,
            detail=f"You can have at most {cfg.MAX_ALERTS_PER_FARMER} active alerts.",
        )
    values = {**body.model_dump(), "is_active": True, "last_state": None}
    return {"alert": _alert_view(_db(repo.create_alert, user_id, values))}


@router.put("/alerts/{alert_id}")
async def update_alert(
    alert_id: UUID,
    body: AlertUpdate,
    user_id: str = Depends(get_user_id),
    repo: SellSmartRepo = Depends(get_repo),
    _: None = Depends(_write_limiter),
) -> dict:
    current = _owned_alert(repo, user_id, alert_id)
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        return {"alert": _alert_view(current)}
    if changes.get("is_active") and not current.get("is_active"):
        if _db(repo.count_active_alerts, user_id) >= cfg.MAX_ALERTS_PER_FARMER:
            raise HTTPException(
                status_code=409,
                detail=f"You can have at most {cfg.MAX_ALERTS_PER_FARMER} active alerts.",
            )
    if "state" in changes and changes["state"] is None:
        raise HTTPException(status_code=422, detail="state cannot be empty.")
    if "target_rs_per_kg" in changes and changes["target_rs_per_kg"] is None:
        raise HTTPException(status_code=422, detail="target_rs_per_kg cannot be empty.")
    if "direction" in changes and changes["direction"] is None:
        raise HTTPException(status_code=422, detail="direction cannot be empty.")
    if "is_active" in changes and changes["is_active"] is None:
        raise HTTPException(status_code=422, detail="is_active cannot be empty.")
    # A changed target, direction or scope re-arms the alert.
    if any(k in changes for k in ("state", "district", "market_name", "target_rs_per_kg", "direction")):
        changes["last_state"] = None
    updated = _db(repo.update_alert, user_id, str(alert_id), changes)
    if not updated:
        raise HTTPException(status_code=404, detail="Alert not found.")
    return {"alert": _alert_view(updated)}


@router.post("/alerts/{alert_id}/delete")
async def delete_alert(
    alert_id: UUID,
    user_id: str = Depends(get_user_id),
    repo: SellSmartRepo = Depends(get_repo),
    _: None = Depends(_write_limiter),
) -> dict:
    if not _db(repo.soft_delete_alert, user_id, str(alert_id)):
        raise HTTPException(status_code=404, detail="Alert not found.")
    return {"deleted": True, "id": str(alert_id)}


# -- Notifications --------------------------------------------------------------

@router.get("/notifications")
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=MAX_NOTIFICATIONS),
    user_id: str = Depends(get_user_id),
    repo: SellSmartRepo = Depends(get_repo),
    _: None = Depends(_read_limiter),
) -> dict:
    rows = _db(repo.list_notifications, user_id, unread_only, limit)
    items = [_notification_view(n) for n in rows]
    return {
        "notifications": items,
        "unread_count": sum(1 for n in items if not n["read_at"]),
    }


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    user_id: str = Depends(get_user_id),
    repo: SellSmartRepo = Depends(get_repo),
    _: None = Depends(_write_limiter),
) -> dict:
    updated = _db(repo.mark_notification_read, user_id, str(notification_id))
    if not updated:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return {"notification": _notification_view(updated)}


# -- Fairness -------------------------------------------------------------------

@router.get("/fairness")
async def get_fairness(
    user_id: str = Depends(get_user_id),
    repo: SellSmartRepo = Depends(get_repo),
    _: None = Depends(_read_limiter),
) -> dict:
    loc = _require_location(repo, user_id)
    origin, basis = _origin(loc)
    row = _db(repo.get_settings, user_id)
    radius = _num((row or {}).get("radius_km")) or cfg.DEFAULT_RADIUS_KM
    harvests = _db(repo.get_harvests, user_id)
    harvest = harvests[0] if harvests else None
    base = {"source": SOURCE_NAME, "attribution": ATTRIBUTION, "location_basis": basis,
            "harvest_count": len(harvests)}

    sale = quality.to_date(harvest.get("sale_date")) if harvest else None
    if harvest is None or sale is None:
        result = fairness_mod.compare(None, [], origin, radius, _today())
    else:
        window = timedelta(days=cfg.STALE_DAYS)
        rows = _annotated_rows(repo, since=sale - window, until=sale + window)
        result = fairness_mod.compare(harvest, rows, origin, radius, _today())
    if result.get("status") != "ok":
        result = {**result, "reason_key": f"sell_fairness_{result.get('reason')}"}
    return {**base, **result}
