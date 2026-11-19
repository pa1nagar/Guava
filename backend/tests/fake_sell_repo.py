"""
fake_sell_repo.py - in-memory SellSmartRepo for tests. No DB, no network.
"""
import itertools
import uuid
from datetime import date
from typing import Optional

from services.sell_smart.repo import RepoError


def price_row(state, district, market, trade, modal, mn=None, mx=None,
              variety="Other", grade="FAQ", row_id=None):
    """A market_prices-shaped row (Rs/quintal, ISO arrival_date)."""
    return {
        "id": row_id or str(uuid.uuid4()),
        "state": state, "district": district, "market_name": market,
        "variety": variety, "grade": grade,
        "min_price": mn if mn is not None else modal - 200,
        "max_price": mx if mx is not None else modal + 200,
        "modal_price": modal, "arrival_date": trade,
        "source_name": "Agmarknet / data.gov.in",
        "fetched_at": "2026-11-12T02:00:00+00:00",
    }


class FakeRepo:
    def __init__(self):
        self.prices: list[dict] = []
        self.quality: dict[str, dict] = {}
        self.locations: dict[str, dict] = {}
        self.harvests: dict[str, list[dict]] = {}
        self.settings: dict[str, dict] = {}
        self.alerts: dict[str, dict] = {}
        self.notifications: list[dict] = []
        self.fail = False
        self._ids = itertools.count(1)

    def _check(self):
        if self.fail:
            raise RepoError("forced failure")

    @staticmethod
    def _uuid(n: int) -> str:
        return str(uuid.UUID(int=n))

    # prices
    def get_price_rows(self, since=None, until=None, state=None, district=None, market_name=None):
        self._check()
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
        return sorted(out, key=lambda r: (r["arrival_date"], r["id"]))

    def get_quality(self, price_ids):
        self._check()
        return {i: dict(self.quality[i]) for i in price_ids if i in self.quality}

    def upsert_quality(self, records):
        self._check()
        for r in records:
            self.quality[r["price_id"]] = dict(r)
        return len(records)

    # farmer data
    def get_location(self, user_id):
        self._check()
        return self.locations.get(user_id)

    def get_harvests(self, user_id):
        self._check()
        return list(self.harvests.get(user_id, []))

    def get_settings(self, user_id):
        self._check()
        return self.settings.get(user_id)

    def put_settings(self, user_id, values):
        self._check()
        self.settings[user_id] = {**values, "user_id": user_id}
        return dict(self.settings[user_id])

    # alerts
    def list_alerts(self, user_id):
        self._check()
        return [dict(a) for a in self.alerts.values()
                if a["user_id"] == user_id and not a.get("deleted_at")]

    def get_alert(self, user_id, alert_id):
        self._check()
        a = self.alerts.get(alert_id)
        if a and a["user_id"] == user_id and not a.get("deleted_at"):
            return dict(a)
        return None

    def count_active_alerts(self, user_id):
        self._check()
        return sum(1 for a in self.alerts.values()
                   if a["user_id"] == user_id and a.get("is_active") and not a.get("deleted_at"))

    def create_alert(self, user_id, values):
        self._check()
        aid = self._uuid(next(self._ids))
        self.alerts[aid] = {
            "id": aid, "user_id": user_id, "deleted_at": None, "last_trigger_date": None,
            "created_at": "2026-11-12T00:00:00+00:00", **values,
        }
        return dict(self.alerts[aid])

    def update_alert(self, user_id, alert_id, values):
        self._check()
        a = self.get_alert(user_id, alert_id)
        if not a:
            return None
        self.alerts[alert_id].update(values)
        return dict(self.alerts[alert_id])

    def soft_delete_alert(self, user_id, alert_id):
        self._check()
        if not self.get_alert(user_id, alert_id):
            return False
        self.alerts[alert_id].update(deleted_at="2026-11-12T00:00:00+00:00", is_active=False)
        return True

    def list_active_alerts_all(self):
        self._check()
        return [dict(a) for a in self.alerts.values()
                if a.get("is_active") and not a.get("deleted_at")]

    def set_alert_state(self, alert_id, last_state, last_trigger_date):
        self._check()
        self.alerts[alert_id]["last_state"] = last_state
        if last_trigger_date:
            self.alerts[alert_id]["last_trigger_date"] = last_trigger_date

    # notifications
    def list_notifications(self, user_id, unread_only=False, limit=50):
        self._check()
        rows = [n for n in self.notifications if n["user_id"] == user_id
                and (not unread_only or n["read_at"] is None)]
        return [dict(n) for n in rows[::-1][:limit]]

    def has_notification(self, alert_id, trade_date):
        self._check()
        return any(n["alert_id"] == alert_id and n["payload"].get("trade_date") == trade_date
                   for n in self.notifications)

    def insert_notification(self, user_id, kind, alert_id, payload):
        self._check()
        n = {"id": self._uuid(1000 + next(self._ids)), "user_id": user_id, "kind": kind,
             "alert_id": alert_id, "payload": payload, "read_at": None,
             "created_at": "2026-11-12T00:00:00+00:00"}
        self.notifications.append(n)
        return dict(n)

    def mark_notification_read(self, user_id, notification_id):
        self._check()
        for n in self.notifications:
            if n["id"] == notification_id and n["user_id"] == user_id:
                n["read_at"] = "2026-11-12T01:00:00+00:00"
                return dict(n)
        return None
