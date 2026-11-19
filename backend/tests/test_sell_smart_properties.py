"""Sell smart property tests (hypothesis)."""

from datetime import date, timedelta

import pytest
from hypothesis import given, settings, strategies as st

from services.sell_smart import alerts as al
from services.sell_smart import locations as loc
from services.sell_smart import quality as q
from services.sell_smart import ranking as rk
from services.sell_smart import stats as sts

TODAY = date(2026, 11, 10)
PUNE = loc.resolve_district("Maharashtra", "Pune")[:2]
DISTRICTS = ["Pune", "Mumbai", "Nashik", "Solapur"]

price = st.floats(min_value=500, max_value=20000, allow_nan=False, allow_infinity=False)
cost = st.floats(min_value=0, max_value=500, allow_nan=False, allow_infinity=False)


def _rows(prices):
    return [{"id": i, "state": "Maharashtra", "district": d, "market_name": d, "variety": "", "grade": "",
             "min_price": p, "max_price": p, "modal_price": p, "arrival_date": "2026-11-10"}
            for i, (d, p) in enumerate(zip(DISTRICTS, prices))]


def _settings(rate, handling=0.0, commission=0.0):
    return {"transport_mode": rk.MODE_PER_KM, "transport_value": rate,
            "handling_rs_per_quintal": handling, "commission_pct": commission}


@given(st.lists(price, min_size=4, max_size=4), cost, cost, cost)
@settings(max_examples=80, deadline=None)
def test_a_higher_transport_never_raises_net_or_changes_gross(prices, r1, extra, handling):
    rows = _rows(prices)
    lo = {e["market_name"]: e for e in
          (lambda r: r["ranked"] + r["unranked"])(rk.rank_mandis(rows, PUNE, _settings(r1, handling), 1500, TODAY))}
    hi = {e["market_name"]: e for e in
          (lambda r: r["ranked"] + r["unranked"])(rk.rank_mandis(rows, PUNE, _settings(r1 + extra, handling), 1500, TODAY))}
    for name in DISTRICTS:
        assert hi[name]["gross_per_kg"] == lo[name]["gross_per_kg"]
        assert hi[name]["net_per_kg"] <= lo[name]["net_per_kg"] + 1e-9


@given(st.lists(price, min_size=4, max_size=4))
@settings(max_examples=80, deadline=None)
def test_b_zero_costs_preserve_gross_order(prices):
    rows = _rows(prices)
    zero = rk.rank_mandis(rows, PUNE, _settings(0.0, 0.0, 0.0), 1500, TODAY)
    none = rk.rank_mandis(rows, PUNE, {}, 1500, TODAY)
    assert [e["market_name"] for e in zero["ranked"]] == [e["market_name"] for e in none["ranked"]]
    assert all(e["net_per_kg"] == e["gross_per_kg"] for e in zero["ranked"])


def _series_rows(values, k=1.0):
    return [{"id": i, "state": "S", "district": "D", "market_name": "M", "variety": "", "grade": "",
             "min_price": v * k, "max_price": v * k, "modal_price": v * k,
             "arrival_date": (TODAY - timedelta(days=len(values) - 1 - i)).isoformat()}
            for i, v in enumerate(values)]


@given(st.lists(st.integers(min_value=1000, max_value=9000), min_size=14, max_size=14),
       st.sampled_from([0.5, 2, 3, 10]))
@settings(max_examples=80, deadline=None)
def test_c_scaling_prices_scales_rs_change_not_percent(values, k):
    a = sts.window_change(sts.daily_series(_series_rows(values)), 7, TODAY)
    b = sts.window_change(sts.daily_series(_series_rows(values, k)), 7, TODAY)
    assert a["status"] == b["status"] == "ok"
    assert b["change_rs_per_kg"] == pytest.approx(a["change_rs_per_kg"] * k, rel=1e-9, abs=1e-9)
    assert b["change_pct"] == pytest.approx(a["change_pct"], rel=1e-9, abs=1e-9)


@given(st.lists(st.integers(min_value=3800, max_value=4200), min_size=14, max_size=14),
       st.integers(min_value=50000, max_value=500000))
@settings(max_examples=60, deadline=None)
def test_d_flagged_outlier_does_not_move_window_change(values, spike):
    # three mandis with the same shape each day so the day cross-section has a stable band
    def build(extra):
        rows = []
        for m, off in enumerate((0, 10, 20)):
            for i, v in enumerate(values):
                rows.append({"id": f"{m}-{i}", "state": "S", "district": f"D{m}", "market_name": f"M{m}",
                             "variety": "", "grade": "", "min_price": v + off, "max_price": v + off,
                             "modal_price": v + off,
                             "arrival_date": (TODAY - timedelta(days=13 - i)).isoformat()})
        return rows + extra
    spike_row = [{"id": "x", "state": "S", "district": "DX", "market_name": "MX", "variety": "", "grade": "",
                  "min_price": spike, "max_price": spike, "modal_price": spike,
                  "arrival_date": TODAY.isoformat()}]
    base = sts.window_change(sts.daily_series(q.annotate(build([]))), 7, TODAY)
    with_spike_rows = q.annotate(build(spike_row))
    flagged = [r for r in with_spike_rows if r["id"] == "x"][0]
    if flagged["severity"] == "ok":
        return  # not flagged by the rules: property only concerns flagged rows
    after = sts.window_change(sts.daily_series(with_spike_rows), 7, TODAY)
    assert after["median_latest"] == base["median_latest"]
    assert after["change_rs_per_kg"] == base["change_rs_per_kg"]


@given(st.lists(st.tuples(st.integers(min_value=0, max_value=3), price), min_size=1, max_size=40),
       price)
@settings(max_examples=100, deadline=None)
def test_e_fired_equals_crossings_with_one_per_trade_date(steps, target):
    alert = {"id": "a", "target_per_kg": target, "direction": al.AT_OR_ABOVE, "state": None}
    day = 0
    fired = 0
    met_prev = False
    fired_day = None
    expected = 0
    for inc, p in steps:
        day += inc
        d = (TODAY + timedelta(days=day)).isoformat()
        r = al.evaluate(alert, p, d, TODAY)
        alert["state"] = r["state"]
        fired += r["action"] == "fire"
        met = p >= target
        if met and not met_prev and fired_day != day:
            expected += 1
            fired_day = day
        met_prev = met
    assert fired == expected
