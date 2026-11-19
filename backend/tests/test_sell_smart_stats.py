"""Sell smart statistics."""

from datetime import date, timedelta

import pytest

from services.sell_smart import quality as q
from services.sell_smart import stats as st

TODAY = date(2026, 11, 10)


def _rows(days, base=4000.0, start=None, market="A", step=0.0, skip=()):
    start = start or TODAY - timedelta(days=days - 1)
    rows = []
    for k in range(days):
        if k in skip:
            continue
        d = start + timedelta(days=k)
        rows.append({"id": f"{market}{k}", "state": "Maharashtra", "district": market,
                     "market_name": market, "variety": "", "grade": "",
                     "min_price": base + step * k - 100, "max_price": base + step * k + 100,
                     "modal_price": base + step * k, "arrival_date": d.isoformat()})
    return rows


def _series(rows):
    return st.daily_series(rows)


def test_daily_series_median_and_kg():
    rows = _rows(1, 4000, market="A") + _rows(1, 5000, market="B") + _rows(1, 6000, market="C")
    s = _series(rows)
    assert len(s) == 1 and s[0]["value"] == 50.0 and s[0]["n_mandis"] == 3


def test_daily_series_drops_rejected_and_outlier():
    rows = _rows(1, 4000, market="A") + _rows(1, 4100, market="B") + _rows(1, 0, market="Z")
    rows[-1]["min_price"] = rows[-1]["max_price"] = 0
    out = q.annotate(rows)
    assert len(_series(out)) == 1 and _series(out)[0]["value"] == pytest.approx(40.5)


def test_window_change_ok_flat_rise():
    s = _series(_rows(14, 4000, step=10))
    r = st.window_change(s, 7, TODAY)
    assert r["status"] == "ok"
    # latest k=7..13 -> median 4100 ; previous k=0..6 -> median 4030
    assert r["median_latest"] == pytest.approx(41.0)
    assert r["median_previous"] == pytest.approx(40.3)
    assert r["change_rs_per_kg"] == pytest.approx(0.7)
    assert r["change_pct"] == pytest.approx(0.7 / 40.3 * 100)


def test_window_change_under_seven_days_insufficient_with_more_days():
    s = _series(_rows(5, 4000))
    r = st.window_change(s, 7, TODAY)
    assert r["status"] == "insufficient"
    assert r["needs_params"]["more_days"] == 7 + 3 - 5
    assert "more saved day" in r["needs"]


def test_window_change_empty_series():
    r = st.window_change([], 7, TODAY)
    assert r["status"] == "insufficient" and r["needs_params"]["more_days"] == 10


def test_window_change_missing_days_inside_window():
    # 14 calendar days but only 2 saved in the previous window (past days cannot be added)
    s = _series(_rows(14, 4000, skip=(1, 2, 3, 4, 5)))
    r = st.window_change(s, 7, TODAY)
    assert r["status"] == "insufficient" and r["needs_key"] == "needs_gaps"


def test_window_change_outlier_flagged_row_ignored():
    rows = _rows(14, 4000, market="A") + _rows(14, 4040, market="B") + _rows(14, 4080, market="C")
    base = st.window_change(_series(q.annotate(rows)), 7, TODAY)
    extra = _rows(1, 90000, start=TODAY, market="X")
    rows2 = rows + extra
    out = q.annotate(rows2)
    assert any(r["flags"] and q.OUTLIER in r["flags"] for r in out)
    after = st.window_change(_series(out), 7, TODAY)
    assert after["median_latest"] == base["median_latest"]


@pytest.mark.parametrize("n", [7, 14, 30])
def test_all_windows_need_enough_history(n):
    assert st.window_change(_series(_rows(n + 2, 4000)), n, TODAY)["status"] == "insufficient"
    assert st.window_change(_series(_rows(2 * n, 4000)), n, TODAY)["status"] == "ok"


def test_window_changes_returns_three():
    assert [w["window_days"] for w in st.window_changes([], TODAY)] == [7, 14, 30]


def test_volatility_needs_seven_days():
    r = st.volatility(_series(_rows(6, 4000)), TODAY)
    assert r["status"] == "insufficient" and r["needs_params"]["more_days"] == 1


def test_volatility_flat_is_zero():
    r = st.volatility(_series(_rows(10, 4000)), TODAY)
    assert r["status"] == "ok" and r["relative_mad"] == 0.0


def test_volatility_value():
    r = st.volatility(_series(_rows(7, 4000, step=100)), TODAY)
    # values 40..46 Rs/kg, median 43, deviations 3,2,1,0,1,2,3 -> MAD 2
    assert r["median"] == pytest.approx(43.0) and r["mad"] == pytest.approx(2.0)
    assert r["relative_mad"] == pytest.approx(2 / 43)


def _long(start, end, base=4000.0, per_day=True):
    days = (end - start).days + 1
    return _rows(days, base, start=start)


def test_seasonal_exactly_two_years_ok():
    start = date(2024, 11, 10)
    end = date(2026, 11, 10)
    assert (end - start).days == 730
    r = st.seasonal_view(_series(_long(start, end)), end)
    assert r["status"] == "ok"
    months = {m["month"] for m in r["months"]}
    assert 11 in months and 12 in months  # Nov 2024+2025+2026, Dec 2024+2025


def test_seasonal_one_year_eleven_months_insufficient():
    start = date(2024, 12, 10)
    end = date(2026, 11, 10)
    r = st.seasonal_view(_series(_long(start, end)), end)
    assert r["status"] == "insufficient"
    assert r["first_date"] == "2024-12-10"
    assert r["earliest_meaningful_date"] == "2026-12-10"
    assert r["days_saved"] == (end - start).days + 1


def test_seasonal_no_data():
    assert st.seasonal_view([], TODAY)["status"] == "insufficient"


def test_seasonal_sparse_months_not_shown():
    # Two years span but only 2 observations per month-year -> no month qualifies.
    rows = _rows(1, 4000, start=date(2024, 11, 10))
    rows += _rows(1, 4000, start=date(2026, 11, 10), market="B")
    r = st.seasonal_view(_series(rows), date(2026, 11, 10))
    assert r["status"] == "insufficient" and r["needs_key"] == "needs_seasonal_months"


def test_district_series_groups():
    rows = _rows(2, 4000, market="A") + _rows(2, 4500, market="B")
    out = st.district_series(rows)
    assert [d["district"] for d in out] == ["A", "B"]
    assert all(len(d["series"]) == 2 for d in out)
