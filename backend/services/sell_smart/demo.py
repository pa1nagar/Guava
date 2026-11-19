"""
demo.py - labelled DEMO dataset and in-memory repository for Sell smart.

THIS IS SYNTHETIC DATA. It is not market data and must never be shown to a
farmer as real prices. It exists so the Sell smart screens can be developed and
checked without a database or an API key. It is used only by
scripts/run_sell_smart_demo.py (local, needs SELL_SMART_ALLOW_DEMO=1) and by
tests/examples. main.py never imports this module, and nothing here imports
services.db.

How the prices are made (all arithmetic, fixed seed, no randomness from the
clock):
    modal Rs/quintal = BASE[mandi] x (1 + SEASON_AMPLITUDE x sin(2 pi (day_of_year - SEASON_PEAK_SHIFT) / 365))
                       x (1 + noise), noise uniform in +-NOISE_PCT, rounded to PRICE_STEP
    min  = modal x (1 - SPREAD_PCT), max = modal x (1 + SPREAD_PCT), rounded to PRICE_STEP
BASE values are round illustrative numbers, not observed prices. noise comes
from random.Random seeded with "SEED|market|date", so the same inputs always
give the same rows. Dates run backwards from `today` for HISTORY_DAYS days;
about MISSING_DAY_PCT % of mandi-days are left out so missing days are visible.
Every row and (through the demo app) every response carries demo = true.
"""
from __future__ import annotations

import itertools
import math
import random
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping, Optional

DEMO_SEED = "sell-smart-demo-v1"
HISTORY_DAYS = 760            # 2 x 365 + 30, so the seasonal view is meaningful
SEASON_AMPLITUDE = 0.10       # +-10 % yearly swing, illustrative
SEASON_PEAK_SHIFT = 100       # day of year where the swing crosses zero going up
NOISE_PCT = 0.03              # daily noise, +-3 %
SPREAD_PCT = 0.12             # min/max around modal
PRICE_STEP = 50               # Agmarknet prices are reported in whole Rs/quintal; demo rounds to 50
MISSING_DAY_PCT = 4           # share of mandi-days left out
DEMO_USER_ID = "demo-user"
SOURCE = "DEMO DATA (synthetic, not Agmarknet)"
ALLOW_ENV = "SELL_SMART_ALLOW_DEMO"

# (state, district, market, base Rs/quintal). Illustrative numbers only.
DEMO_MANDIS = (
    ("Maharashtra", "Pune", "Pune", 4800),
    ("Maharashtra", "Mumbai", "Mumbai", 4800),
    ("Maharashtra", "Nashik", "Nashik", 4400),
    ("Maharashtra", "Solapur", "Solapur", 4000),
    ("Maharashtra", "Satara", "Satara", 4600),
    ("Maharashtra", "Nagpur", "Nagpur", 4200),
    ("Madhya Pradesh", "Indore", "Indore", 4300),
    ("Madhya Pradesh", "Ujjain", "Ujjain", 4100),
    ("Madhya Pradesh", "Bhopal", "Bhopal", 4500),
    ("Madhya Pradesh", "Jabalpur", "Jabalpur", 4000),
)


def assert_demo_allowed(env: Mapping[str, str]) -> None:
    """Raise SystemExit unless the demo may run. Always refuses on Render."""
    if "RENDER" in env:
        raise SystemExit("Refusing to start: RENDER is set. The demo server is local only.")
    if env.get(ALLOW_ENV) != "1":
        raise SystemExit(f"Refusing to start: set {ALLOW_ENV}=1 to run the demo server (synthetic data, local only).")


def _round_step(x: float) -> int:
    return int(round(x / PRICE_STEP) * PRICE_STEP)


def _modal(base: float, market: str, d: date) -> int:
    rng = random.Random(f"{DEMO_SEED}|{market}|{d.isoformat()}")
    season = 1 + SEASON_AMPLITUDE * math.sin(2 * math.pi * (d.timetuple().tm_yday - SEASON_PEAK_SHIFT) / 365)
    noise = 1 + rng.uniform(-NOISE_PCT, NOISE_PCT)
    return _round_step(base * season * noise)


def generate_price_rows(today: Optional[date] = None) -> list[dict]:
    """Deterministic market_prices-shaped rows (Rs/quintal) ending on `today`."""
    today = today or date.today()
    rows: list[dict] = []
    for state, district, market, base in DEMO_MANDIS:
        for back in range(HISTORY_DAYS):
            d = today - timedelta(days=back)
            skip = random.Random(f"{DEMO_SEED}|skip|{market}|{d.isoformat()}").randrange(100)
            if skip < MISSING_DAY_PCT and back > 0:  # the latest day is always present
                continue
            modal = _modal(base, market, d)
            rows.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{DEMO_SEED}/{market}/{d.isoformat()}")),
                "state": state, "district": district, "market_name": market,
                "variety": "Demo", "grade": "FAQ",
                "min_price": _round_step(modal * (1 - SPREAD_PCT)),
                "max_price": _round_step(modal * (1 + SPREAD_PCT)),
                "modal_price": modal,
                "arrival_date": d.isoformat(),
                "source_name": SOURCE,
                "fetched_at": f"{d.isoformat()}T02:00:00+00:00",
                "demo": True,
            })
    rows.sort(key=lambda r: (r["arrival_date"], r["id"]))
    return rows


def demo_harvest(today: date) -> dict:
    """One logged sale (harvests is write-once per farmer). Illustrative values."""
    return {
        "sale_date": (today - timedelta(days=10)).isoformat(),
        "sale_price_per_kg": 36.0,
        "sale_quantity_kg": 500.0,
        "grade": "A",
        "market_type": "farm_gate",
        "transport_cost": 1500.0,
        "demo": True,
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DemoRepo:
    """In-memory SellSmartRepo. No database, no network, resets on restart."""

    def __init__(self, today: Optional[date] = None) -> None:
        self.today = today or date.today()
        self.prices = generate_price_rows(self.today)
        self.quality: dict[str, dict] = {}
        self.settings: dict[str, dict] = {}
        self.alerts: dict[str, dict] = {}
        self.notifications: list[dict] = []
        self._ids = itertools.count(1)
        self._seed_alert_and_notification()

    # -- seeding ------------------------------------------------------------
    def _uuid(self) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{DEMO_SEED}/id/{next(self._ids)}"))

    def _seed_alert_and_notification(self) -> None:
        alert = self.create_alert(DEMO_USER_ID, {
            "state": "Maharashtra", "district": "Pune", "market_name": "Pune",
            "target_rs_per_kg": 70.0, "direction": "at_or_above",
            "is_active": True, "last_state": None,
        })
        self.notifications.append({
            "id": self._uuid(), "user_id": DEMO_USER_ID, "kind": "price_alert",
            "alert_id": alert["id"], "read_at": None, "created_at": _now(),
            "payload": {
                "message_key": "sell_notif_price_alert", "price_per_kg": 52.0, "target_per_kg": 50.0,
                "direction": "at_or_above", "trade_date": (self.today - timedelta(days=3)).isoformat(),
                "state": "Maharashtra", "district": "Pune", "market_name": "Pune",
                "source": SOURCE, "demo": True,
            },
        })

    # -- prices -------------------------------------------------------------
    def get_price_rows(self, since=None, until=None, state=None, district=None, market_name=None):
        out = []
        for r in self.prices:
            d = date.fromisoformat(r["arrival_date"])
            if since and d < since:
                continue
            if until and d > until:
                continue
            if state and r["state"] != state:
                continue
            if district and r["district"] != district:
                continue
            if market_name and r["market_name"] != market_name:
                continue
            out.append(dict(r))
        return out

    def get_quality(self, price_ids):
        return {i: dict(self.quality[i]) for i in price_ids if i in self.quality}

    def upsert_quality(self, records):
        for r in records:
            self.quality[r["price_id"]] = dict(r)
        return len(records)

    # -- farmer data --------------------------------------------------------
    def get_location(self, user_id):
        if user_id != DEMO_USER_ID:
            return None
        return {"state": "Maharashtra", "district": "Pune", "farm_lat": None, "farm_lon": None}

    def get_harvests(self, user_id):
        return [demo_harvest(self.today)] if user_id == DEMO_USER_ID else []

    def get_settings(self, user_id):
        return self.settings.get(user_id)

    def put_settings(self, user_id, values):
        self.settings[user_id] = {**values, "user_id": user_id, "updated_at": _now()}
        return dict(self.settings[user_id])

    # -- alerts -------------------------------------------------------------
    def list_alerts(self, user_id):
        return [dict(a) for a in self.alerts.values() if a["user_id"] == user_id and not a.get("deleted_at")]

    def get_alert(self, user_id, alert_id):
        a = self.alerts.get(alert_id)
        if a and a["user_id"] == user_id and not a.get("deleted_at"):
            return dict(a)
        return None

    def count_active_alerts(self, user_id):
        return sum(1 for a in self.alerts.values()
                   if a["user_id"] == user_id and a.get("is_active") and not a.get("deleted_at"))

    def create_alert(self, user_id, values):
        aid = self._uuid()
        self.alerts[aid] = {
            "id": aid, "user_id": user_id, "deleted_at": None, "last_trigger_date": None,
            "created_at": _now(), **values,
        }
        return dict(self.alerts[aid])

    def update_alert(self, user_id, alert_id, values):
        if not self.get_alert(user_id, alert_id):
            return None
        self.alerts[alert_id].update(values)
        return dict(self.alerts[alert_id])

    def soft_delete_alert(self, user_id, alert_id):
        if not self.get_alert(user_id, alert_id):
            return False
        self.alerts[alert_id].update(deleted_at=_now(), is_active=False)
        return True

    def list_active_alerts_all(self):
        return [dict(a) for a in self.alerts.values() if a.get("is_active") and not a.get("deleted_at")]

    def set_alert_state(self, alert_id, last_state, last_trigger_date):
        self.alerts[alert_id]["last_state"] = last_state
        if last_trigger_date:
            self.alerts[alert_id]["last_trigger_date"] = last_trigger_date

    # -- notifications ------------------------------------------------------
    def list_notifications(self, user_id, unread_only=False, limit=50):
        rows = [n for n in self.notifications if n["user_id"] == user_id
                and (not unread_only or n["read_at"] is None)]
        return [dict(n) for n in rows[::-1][:limit]]

    def has_notification(self, alert_id, trade_date):
        return any(n["alert_id"] == alert_id and n["payload"].get("trade_date") == trade_date
                   for n in self.notifications)

    def insert_notification(self, user_id, kind, alert_id, payload):
        n = {"id": self._uuid(), "user_id": user_id, "kind": kind, "alert_id": alert_id,
             "payload": payload, "read_at": None, "created_at": _now()}
        self.notifications.append(n)
        return dict(n)

    def mark_notification_read(self, user_id, notification_id):
        for n in self.notifications:
            if n["id"] == notification_id and n["user_id"] == user_id:
                n["read_at"] = _now()
                return dict(n)
        return None


def build_demo_app(today: Optional[date] = None) -> Any:
    """A separate FastAPI app with the real sell-smart router on DemoRepo.

    Overrides get_user_id and get_repo, lifts the per-IP rate limits (local use
    only), allows CORS for the local static server, and adds demo=true to every
    JSON object response.
    """
    import json

    from fastapi import FastAPI, Request, Response
    from fastapi.middleware.cors import CORSMiddleware

    from routers import sell_smart as router_module
    from services.auth import get_user_id
    from services.sell_smart.repo import get_repo

    repo = DemoRepo(today)
    app = FastAPI(title="Sell smart DEMO (synthetic data)")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _label_demo(request: Request, call_next):
        response = await call_next(request)
        if "application/json" not in response.headers.get("content-type", ""):
            return response
        body = b"".join([chunk async for chunk in response.body_iterator])
        try:
            data = json.loads(body)
        except ValueError:
            data = None
        if isinstance(data, dict):
            data["demo"] = True
            body = json.dumps(data).encode("utf-8")
        headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
        return Response(content=body, status_code=response.status_code, headers=headers,
                        media_type="application/json")

    app.include_router(router_module.router, prefix="/api")
    app.dependency_overrides[get_user_id] = lambda: DEMO_USER_ID
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[router_module._read_limiter] = lambda: None
    app.dependency_overrides[router_module._write_limiter] = lambda: None
    app.state.repo = repo
    return app
