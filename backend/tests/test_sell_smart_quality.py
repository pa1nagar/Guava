"""Sell smart quality rules."""

from datetime import date

from services.sell_smart import quality as q

TODAY = date(2026, 11, 10)


def _row(i, market, modal, lo=None, hi=None, day="2026-11-10", variety="", grade="", state="Maharashtra"):
    return {
        "id": i, "state": state, "district": market, "market_name": market,
        "variety": variety, "grade": grade,
        "min_price": modal - 500 if lo is None else lo,
        "max_price": modal + 500 if hi is None else hi,
        "modal_price": modal, "arrival_date": day,
    }


def _base(n=6, modal=4000):
    return [_row(i, f"M{i}", modal + i * 10) for i in range(n)]


def _flags(rows, prev=None):
    return {a["id"]: a for a in q.assess_rows(rows, prev)}


def test_clean_rows_are_ok():
    assert all(a["severity"] == "ok" for a in q.assess_rows(_base()))


def test_zero_price_rejected():
    rows = _base() + [_row(99, "Z", 0, lo=0, hi=0)]
    a = _flags(rows)[99]
    assert q.ZERO_PRICE in a["flags"] and a["severity"] == "reject"


def test_modal_above_max_rejected():
    rows = _base() + [_row(99, "Z", 4000, lo=3000, hi=3500)]
    a = _flags(rows)[99]
    assert q.ORDER_VIOLATION in a["flags"] and a["severity"] == "reject"


def test_modal_below_min_rejected():
    a = _flags(_base() + [_row(99, "Z", 2000, lo=3000, hi=5000)])[99]
    assert q.ORDER_VIOLATION in a["flags"]


def test_unit_slip_x100_and_div100():
    rows = _base() + [_row(98, "K", 40, lo=30, hi=50), _row(99, "H", 400000, lo=300000, hi=500000)]
    f = _flags(rows)
    assert q.UNIT_SUSPECT in f[98]["flags"] and f[98]["severity"] == "reject"
    assert q.UNIT_SUSPECT in f[99]["flags"] and f[99]["severity"] == "reject"
    assert all(f[i]["severity"] == "ok" for i in range(6))


def test_mad_zero_day_skips_outlier_but_unit_rule_runs():
    rows = [_row(i, f"M{i}", 4000) for i in range(5)]
    f = _flags(rows + [_row(50, "X", 9000, lo=8000, hi=9500)])
    assert f[50]["severity"] == "ok"  # MAD == 0: no modified-z outlier rule
    f = _flags(rows + [_row(51, "Y", 40, lo=30, hi=50)])
    assert q.UNIT_SUSPECT in f[51]["flags"]


def test_injected_outlier_is_warn_not_reject():
    rows = _base() + [_row(99, "Z", 9000, lo=8000, hi=9500)]
    a = _flags(rows)[99]
    assert q.OUTLIER in a["flags"] and a["severity"] == "warn"


def test_small_group_skips_cross_section():
    rows = [_row(1, "A", 4000), _row(2, "B", 40, lo=30, hi=50)]
    assert all(a["severity"] == "ok" for a in q.assess_rows(rows))


def test_revised_modal_flagged_warn():
    rows = _base()
    f = _flags(rows, {0: 3900.0, 1: rows[1]["modal_price"]})
    assert q.REVISED in f[0]["flags"] and f[0]["severity"] == "warn"
    assert f[1]["severity"] == "ok"


def test_duplicate_values_under_two_labels_counted_once():
    a = _row(1, "P", 4020, variety="Other", grade="FAQ")
    b = _row(2, "P", 4020, variety="", grade="", lo=a["min_price"], hi=a["max_price"])
    f = _flags(_base() + [a, b])
    assert f[1]["severity"] == "ok"
    assert q.DUPLICATE_VALUES in f[2]["flags"] and f[2]["severity"] == "reject"


def test_different_values_same_mandi_not_duplicate():
    a, b = _row(1, "P", 5000), _row(2, "P", 5100)
    f = _flags(_base() + [a, b])
    assert q.DUPLICATE_VALUES not in f[2]["flags"]


def _history(days, n_mandis=4, start=date(2026, 10, 1)):
    from datetime import timedelta
    rows, i = [], 0
    for d in range(days):
        for m in range(n_mandis):
            i += 1
            rows.append(_row(i, f"M{m}", 4000 + m * 50, day=(start + timedelta(days=d)).isoformat()))
    return rows


def test_confidence_high():
    rows = q.annotate(_history(14, start=date(2026, 10, 28)))
    s = q.summarise_quality(rows, TODAY)
    assert s["confidence"] == "High" and s["n_mandis"] == 4 and s["days_saved"] == 14


def test_confidence_medium_when_short_history():
    s = q.summarise_quality(q.annotate(_history(5, start=date(2026, 11, 5))), TODAY)
    assert s["confidence"] == "Medium"


def test_confidence_medium_when_flagged_fresh_row():
    rows = _history(14, start=date(2026, 10, 28))
    rows.append(_row(999, "Z", 0, lo=0, hi=0, day="2026-11-10"))
    s = q.summarise_quality(q.annotate(rows), TODAY)
    assert s["confidence"] == "Medium" and s["rejected"] == 1


def test_confidence_low_when_stale():
    s = q.summarise_quality(q.annotate(_history(14, start=date(2026, 9, 1))), TODAY)
    assert s["confidence"] == "Low" and s["fresh"] is False


def test_confidence_low_when_few_mandis():
    s = q.summarise_quality(q.annotate(_history(14, n_mandis=2, start=date(2026, 10, 28))), TODAY)
    assert s["confidence"] == "Low"


def test_empty_rows():
    s = q.summarise_quality([], TODAY)
    assert s["confidence"] == "Low" and s["last_updated"] is None and s["n_mandis"] == 0
