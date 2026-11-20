"""
repo.py - storage seam for Sell smart.

SellSmartRepo is the interface the router and the post-ingestion job use.
SupabaseRepo is the production implementation (service-role client). Tests
supply an in-memory implementation of the same interface.

Multi-tenant isolation: every method that touches user data takes the user_id
that the router got from the JWT and filters on it. Market prices and quality
flags are public data.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Optional, Protocol

from services.mandi_prices import COMMODITY
from services.sell_smart import config as cfg

logger = logging.getLogger(__name__)

# Supabase (PostgREST) returns at most 1000 rows per request; pages are walked
# with .range() so a long history is not cut off at one response.
PAGE_SIZE = cfg.PAGE_SIZE
MAX_PAGES = cfg.MAX_PAGES

PRICE_COLUMNS = (
    "id, state, district, market_name, variety, grade, min_price, max_price, "
    "modal_price, arrival_date, source_name, fetched_at"
)
ALERT_COLUMNS = (
    "id, user_id, state, district, market_name, target_rs_per_kg, direction, "
    "is_active, deleted_at, last_state, last_trigger_date, created_at"
)
SETTINGS_COLUMNS = (
    "user_id, transport_mode, transport_rs_per_quintal_per_km, "
    "transport_rs_per_quintal_flat, handling_rs_per_quintal, commission_pct, "
    "radius_km, road_km_overrides, updated_at"
)
NOTIFICATION_COLUMNS = "id, user_id, kind, alert_id, payload, read_at, created_at"


class RepoError(Exception):
    """Raised by a repository when the storage layer fails."""


class SellSmartRepo(Protocol):
    # public price data
    def get_price_rows(
        self,
        since: Optional[date] = None,
        until: Optional[date] = None,
        state: Optional[str] = None,
        district: Optional[str] = None,
        market_name: Optional[str] = None,
    ) -> list[dict]: ...

    def get_quality(self, price_ids: list[str]) -> dict[str, dict]: ...

    def upsert_quality(self, records: list[dict]) -> int: ...

    # farmer data (user_id always from the JWT)
    def get_location(self, user_id: str) -> Optional[dict]: ...

    def get_harvests(self, user_id: str) -> list[dict]: ...

    def get_settings(self, user_id: str) -> Optional[dict]: ...

    def put_settings(self, user_id: str, values: dict) -> dict: ...

    # alerts
    def list_alerts(self, user_id: str) -> list[dict]: ...

    def get_alert(self, user_id: str, alert_id: str) -> Optional[dict]: ...

    def count_active_alerts(self, user_id: str) -> int: ...

    def create_alert(self, user_id: str, values: dict) -> dict: ...

    def update_alert(self, user_id: str, alert_id: str, values: dict) -> Optional[dict]: ...

    def soft_delete_alert(self, user_id: str, alert_id: str) -> bool: ...

    def list_active_alerts_all(self) -> list[dict]: ...

    def set_alert_state(self, alert_id: str, last_state: str, last_trigger_date: Optional[str]) -> None: ...

    # notifications
    def list_notifications(self, user_id: str, unread_only: bool = False, limit: int = 50) -> list[dict]: ...

    def has_notification(self, alert_id: str, trade_date: str) -> bool: ...

    def insert_notification(self, user_id: str, kind: str, alert_id: Optional[str], payload: dict) -> dict: ...

    def mark_notification_read(self, user_id: str, notification_id: str) -> Optional[dict]: ...


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SupabaseRepo:
    """Production repository on the shared service-role Supabase client."""

    def __init__(self, db: Any = None) -> None:
        self._db_override = db

    @property
    def db(self) -> Any:
        if self._db_override is not None:
            return self._db_override
        from services.db import get_db
        return get_db()

    @staticmethod
    def _run(query: Any, what: str) -> Any:
        try:
            return query.execute()
        except Exception as exc:  # supabase/postgrest raise various types
            logger.error("DB %s failed: %s", what, exc)
            raise RepoError(what) from exc

    # -- public price data ---------------------------------------------------

    def get_price_rows(
        self,
        since: Optional[date] = None,
        until: Optional[date] = None,
        state: Optional[str] = None,
        district: Optional[str] = None,
        market_name: Optional[str] = None,
    ) -> list[dict]:
        rows: list[dict] = []
        for page in range(MAX_PAGES):
            q = (
                self.db.table("market_prices")
                .select(PRICE_COLUMNS)
                .eq("commodity", COMMODITY)
            )
            if since is not None:
                q = q.gte("arrival_date", since.isoformat())
            if until is not None:
                q = q.lte("arrival_date", until.isoformat())
            if state:
                q = q.eq("state", state)
            if district:
                q = q.eq("district", district)
            if market_name:
                q = q.eq("market_name", market_name)
            # id is the tie-breaker so pages never overlap or skip rows.
            q = q.order("arrival_date", desc=False).order("id", desc=False)
            q = q.range(page * PAGE_SIZE, (page + 1) * PAGE_SIZE - 1)
            chunk = self._run(q, "select market_prices").data or []
            rows.extend(chunk)
            if len(chunk) < PAGE_SIZE:
                break
        return rows

    def get_quality(self, price_ids: list[str]) -> dict[str, dict]:
        out: dict[str, dict] = {}
        step = 200  # keeps the IN(...) list short enough for a URL
        for i in range(0, len(price_ids), step):
            part = price_ids[i:i + step]
            res = self._run(
                self.db.table("market_price_quality")
                .select("price_id, flags, severity, last_modal, revision_count")
                .in_("price_id", part),
                "select market_price_quality",
            )
            for r in res.data or []:
                out[r["price_id"]] = r
        return out

    def upsert_quality(self, records: list[dict]) -> int:
        if not records:
            return 0
        step = 500
        for i in range(0, len(records), step):
            self._run(
                self.db.table("market_price_quality")
                .upsert(records[i:i + step], on_conflict="price_id"),
                "upsert market_price_quality",
            )
        return len(records)

    # -- farmer data ---------------------------------------------------------

    def get_location(self, user_id: str) -> Optional[dict]:
        """{state, district, farm_lat, farm_lon} for the JWT user, or None."""
        farmer = self._run(
            self.db.table("farmers").select("state, district").eq("user_id", user_id).maybe_single(),
            "select farmers",
        )
        if not farmer or not farmer.data:
            return None
        loc = {
            "state": farmer.data.get("state"),
            "district": farmer.data.get("district"),
            "farm_lat": None,
            "farm_lon": None,
        }
        farm = self._run(
            self.db.table("farms")
            .select("approx_lat, approx_lon")
            .eq("user_id", user_id)
            .eq("is_active", True)
            .order("created_at", desc=False)
            .limit(1),
            "select farms",
        )
        for f in (farm.data or []):
            if f.get("approx_lat") is not None and f.get("approx_lon") is not None:
                loc["farm_lat"], loc["farm_lon"] = f["approx_lat"], f["approx_lon"]
        return loc

    def get_harvests(self, user_id: str) -> list[dict]:
        farmer = self._run(
            self.db.table("farmers").select("id").eq("user_id", user_id).maybe_single(),
            "select farmers",
        )
        if not farmer or not farmer.data:
            return []
        res = self._run(
            self.db.table("harvests").select("*").eq("farmer_id", farmer.data["id"]),
            "select harvests",
        )
        return res.data or []

    def get_settings(self, user_id: str) -> Optional[dict]:
        res = self._run(
            self.db.table("sell_settings").select(SETTINGS_COLUMNS).eq("user_id", user_id).maybe_single(),
            "select sell_settings",
        )
        return res.data if (res and res.data) else None

    def put_settings(self, user_id: str, values: dict) -> dict:
        row = {**values, "user_id": user_id, "updated_at": _now_iso()}
        res = self._run(
            self.db.table("sell_settings").upsert(row, on_conflict="user_id"),
            "upsert sell_settings",
        )
        data = res.data or []
        return data[0] if data else row

    # -- alerts --------------------------------------------------------------

    def list_alerts(self, user_id: str) -> list[dict]:
        res = self._run(
            self.db.table("price_alerts")
            .select(ALERT_COLUMNS)
            .eq("user_id", user_id)
            .is_("deleted_at", "null")
            .order("created_at", desc=False),
            "select price_alerts",
        )
        return res.data or []

    def get_alert(self, user_id: str, alert_id: str) -> Optional[dict]:
        res = self._run(
            self.db.table("price_alerts")
            .select(ALERT_COLUMNS)
            .eq("id", alert_id)
            .eq("user_id", user_id)
            .is_("deleted_at", "null")
            .maybe_single(),
            "select price_alerts by id",
        )
        return res.data if (res and res.data) else None

    def count_active_alerts(self, user_id: str) -> int:
        res = self._run(
            self.db.table("price_alerts")
            .select("id")
            .eq("user_id", user_id)
            .eq("is_active", True)
            .is_("deleted_at", "null"),
            "count price_alerts",
        )
        return len(res.data or [])

    def create_alert(self, user_id: str, values: dict) -> dict:
        res = self._run(
            self.db.table("price_alerts").insert({**values, "user_id": user_id}),
            "insert price_alerts",
        )
        data = res.data or []
        if not data:
            raise RepoError("insert price_alerts returned no row")
        return data[0]

    def update_alert(self, user_id: str, alert_id: str, values: dict) -> Optional[dict]:
        res = self._run(
            self.db.table("price_alerts")
            .update(values)
            .eq("id", alert_id)
            .eq("user_id", user_id)
            .is_("deleted_at", "null"),
            "update price_alerts",
        )
        data = res.data or []
        return data[0] if data else None

    def soft_delete_alert(self, user_id: str, alert_id: str) -> bool:
        res = self._run(
            self.db.table("price_alerts")
            .update({"deleted_at": _now_iso(), "is_active": False})
            .eq("id", alert_id)
            .eq("user_id", user_id)
            .is_("deleted_at", "null"),
            "soft delete price_alerts",
        )
        return bool(res.data)

    def list_active_alerts_all(self) -> list[dict]:
        res = self._run(
            self.db.table("price_alerts")
            .select(ALERT_COLUMNS)
            .eq("is_active", True)
            .is_("deleted_at", "null"),
            "select active price_alerts",
        )
        return res.data or []

    def set_alert_state(self, alert_id: str, last_state: str, last_trigger_date: Optional[str]) -> None:
        values: dict = {"last_state": last_state}
        if last_trigger_date:
            values["last_trigger_date"] = last_trigger_date
        self._run(
            self.db.table("price_alerts").update(values).eq("id", alert_id),
            "update price_alerts state",
        )

    # -- notifications -------------------------------------------------------

    def list_notifications(self, user_id: str, unread_only: bool = False, limit: int = 50) -> list[dict]:
        q = (
            self.db.table("notifications")
            .select(NOTIFICATION_COLUMNS)
            .eq("user_id", user_id)
        )
        if unread_only:
            q = q.is_("read_at", "null")
        res = self._run(q.order("created_at", desc=True).limit(limit), "select notifications")
        return res.data or []

    def has_notification(self, alert_id: str, trade_date: str) -> bool:
        res = self._run(
            self.db.table("notifications")
            .select("id")
            .eq("alert_id", alert_id)
            .eq("kind", "price_alert")
            .eq("payload->>trade_date", trade_date)
            .limit(1),
            "select notifications dedupe",
        )
        return bool(res.data)

    def insert_notification(self, user_id: str, kind: str, alert_id: Optional[str], payload: dict) -> dict:
        res = self._run(
            self.db.table("notifications").insert(
                {"user_id": user_id, "kind": kind, "alert_id": alert_id, "payload": payload}
            ),
            "insert notifications",
        )
        data = res.data or []
        return data[0] if data else {}

    def mark_notification_read(self, user_id: str, notification_id: str) -> Optional[dict]:
        res = self._run(
            self.db.table("notifications")
            .update({"read_at": _now_iso()})
            .eq("id", notification_id)
            .eq("user_id", user_id),
            "update notifications read",
        )
        data = res.data or []
        return data[0] if data else None


def get_repo() -> SellSmartRepo:
    """FastAPI dependency. Tests override it with an in-memory repository."""
    return SupabaseRepo()
