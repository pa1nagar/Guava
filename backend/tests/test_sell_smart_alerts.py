"""Sell smart alert crossing logic."""

from datetime import date

from services.sell_smart import alerts as al

TODAY = date(2026, 11, 10)


def _alert(target=50.0, direction=al.AT_OR_ABOVE, state=None):
    return {"id": "a1", "target_per_kg": target, "direction": direction, "state": state}


def _run(alert, price, day="2026-11-10", today=TODAY):
    r = al.evaluate(alert, price, day, today)
    alert["state"] = r["state"]
    return r


def test_fires_on_crossing_then_not_again_while_met():
    a = _alert()
    assert _run(a, 48, "2026-11-08")["action"] == "skip"
    r = _run(a, 51, "2026-11-09")
    assert r["action"] == "fire" and r["reason"] == "crossed"
    r = _run(a, 52, "2026-11-10")
    assert r["action"] == "skip" and r["reason"] == "still_met"


def test_rearms_after_not_met():
    a = _alert()
    _run(a, 51, "2026-11-07")
    _run(a, 49, "2026-11-08")
    assert _run(a, 51, "2026-11-09")["action"] == "fire"


def test_at_most_once_per_trade_date():
    a = _alert()
    assert _run(a, 51, "2026-11-10")["action"] == "fire"
    _run(a, 49, "2026-11-10")  # revised down the same day
    r = _run(a, 51, "2026-11-10")
    assert r["action"] == "skip" and r["reason"] == "already_fired_this_trade_date"


def test_rerun_same_row_is_idempotent():
    a = _alert()
    assert _run(a, 51)["action"] == "fire"
    assert _run(a, 51)["action"] == "skip"


def test_at_or_below():
    a = _alert(45, al.AT_OR_BELOW)
    assert _run(a, 46, "2026-11-08")["action"] == "skip"
    assert _run(a, 45, "2026-11-09")["action"] == "fire"


def test_stale_price_never_fires_and_state_unchanged():
    a = _alert(state={"last_met": False, "last_fired_date": None, "last_seen_date": None})
    r = al.evaluate(a, 90, "2026-10-01", TODAY)
    assert r["action"] == "skip" and r["reason"] == "stale" and r["state"] == {**al.INITIAL_STATE, **a["state"]}


def test_no_price_or_inactive():
    assert al.evaluate(_alert(), None, "2026-11-10", TODAY)["reason"] == "no_price"
    b = _alert()
    b["deleted_at"] = "2026-11-01"
    assert al.evaluate(b, 99, "2026-11-10", TODAY)["reason"] == "inactive"


def test_out_of_order_older_date_ignored():
    a = _alert()
    _run(a, 49, "2026-11-10")
    assert _run(a, 99, "2026-11-09")["reason"] == "older_than_last_seen"
