"""
alerts.py - price alert crossing logic. Pure.

evaluate() decides whether one alert fires for one (fresh, non-rejected) price.
It fires only on a not-met -> met transition and at most once per trade date.
It then re-arms only after the price goes back to "not met".

Stored state (kept by the caller, e.g. in price_alerts):
    {"last_met": bool, "last_fired_date": iso|None, "last_seen_date": iso|None}
A new alert starts with last_met False, so a target that is already met at the
first evaluation counts as a crossing and fires once.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from services.sell_smart import config as cfg
from services.sell_smart.quality import to_date

AT_OR_ABOVE = "at_or_above"
AT_OR_BELOW = "at_or_below"
DIRECTIONS = (AT_OR_ABOVE, AT_OR_BELOW)

INITIAL_STATE = {"last_met": False, "last_fired_date": None, "last_seen_date": None}


def is_met(direction: str, price: float, target: float) -> bool:
    if direction == AT_OR_BELOW:
        return price <= target
    return price >= target


def evaluate(
    alert: dict,
    current_price: Optional[float],
    trade_date,
    today: Optional[date] = None,
) -> dict:
    """Return {"action": "fire"|"skip", "reason": str, "state": dict}.

    current_price is Rs/kg from a non-rejected row; None means no usable price.
    The state is returned unchanged whenever the price cannot be used.
    """
    today = today or date.today()
    state = {**INITIAL_STATE, **(alert.get("state") or {})}
    d = to_date(trade_date)

    def skip(reason: str, new_state: Optional[dict] = None) -> dict:
        return {"action": "skip", "reason": reason, "state": new_state or state}

    if alert.get("deleted_at") or alert.get("active") is False:
        return skip("inactive")
    if current_price is None or d is None or current_price <= 0:
        return skip("no_price")
    if cfg.is_stale(d, today):
        return skip("stale")
    seen = to_date(state.get("last_seen_date"))
    if seen is not None and d < seen:
        return skip("older_than_last_seen")
    target = alert.get("target_per_kg")
    if target is None:
        return skip("no_target")

    met = is_met(alert.get("direction") or AT_OR_ABOVE, float(current_price), float(target))
    new_state = {**state, "last_met": met, "last_seen_date": d.isoformat()}
    if met and not state["last_met"]:
        if to_date(state.get("last_fired_date")) == d:
            return skip("already_fired_this_trade_date", new_state)
        new_state["last_fired_date"] = d.isoformat()
        return {"action": "fire", "reason": "crossed", "state": new_state}
    return skip("still_met" if met else "not_met", new_state)
