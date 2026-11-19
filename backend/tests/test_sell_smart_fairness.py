"""Sell smart fairness comparison."""

from datetime import date

import pytest

from services.sell_smart import fairness as fr
from services.sell_smart import locations as loc
from services.sell_smart import quality as q

TODAY = date(2026, 11, 10)
PUNE = loc.resolve_district("Maharashtra", "Pune")[:2]


def _row(i, district, modal, day, grade="", variety=""):
    return {"id": i, "state": "Maharashtra", "district": district, "market_name": district,
            "variety": variety, "grade": grade, "min_price": modal - 500, "max_price": modal + 500,
            "modal_price": modal, "arrival_date": day}


def _day(day, prices=(("Pune", 5000), ("Mumbai", 5600), ("Nashik", 5200)), start=0, grade=""):
    return [_row(start + i, d, m, day, grade) for i, (d, m) in enumerate(prices)]


HARVEST = {"sale_date": "2026-11-08", "sale_price_per_kg": 45.0, "sale_quantity_kg": 200,
           "market_type": "mandi", "grade": ""}


def test_gap_same_day():
    rows = q.annotate(_day("2026-11-08"))
    r = fr.compare({**HARVEST, "grade": "A"}, rows, PUNE, 300.0, TODAY)
    assert r["status"] == "ok" and r["date_gap_days"] == 0 and r["n_mandis"] == 3
    assert r["market_median_per_kg"] == pytest.approx(52.0)
    assert r["gap_per_kg"] == pytest.approx(-7.0)
    assert r["gap_total_rs"] == pytest.approx(-1400.0)


def test_nearest_saved_date_within_stale_days():
    rows = q.annotate(_day("2026-11-05") + _day("2026-11-12", start=10))
    r = fr.compare(HARVEST, rows, PUNE, 300.0, TODAY)
    assert r["status"] == "ok" and r["price_date"] == "2026-11-05" and r["date_gap_days"] == -3


def test_date_beyond_stale_days_not_used():
    rows = q.annotate(_day("2026-10-25"))
    r = fr.compare(HARVEST, rows, PUNE, 300.0, TODAY)
    assert r["status"] == "insufficient" and r["reason"] == "not_enough_market_data"


def test_fewer_than_three_mandis_insufficient():
    rows = q.annotate(_day("2026-11-08", prices=(("Pune", 5000), ("Mumbai", 5600))))
    r = fr.compare(HARVEST, rows, PUNE, 300.0, TODAY)
    assert r["status"] == "insufficient" and r["best_mandi_count"] == 2


def test_radius_limits_mandis():
    rows = q.annotate(_day("2026-11-08", prices=(("Pune", 5000), ("Mumbai", 5600), ("Solapur", 4800))))
    assert fr.compare(HARVEST, rows, PUNE, 300.0, TODAY)["status"] == "ok"
    assert fr.compare(HARVEST, rows, PUNE, 150.0, TODAY)["status"] == "insufficient"


def test_no_origin_and_no_sale():
    assert fr.compare(HARVEST, [], None, 300.0, TODAY)["reason"] == "no_origin"
    assert fr.compare({}, [], PUNE, 300.0, TODAY)["reason"] == "no_sale"


def test_farm_gate_and_grade_are_not_like_for_like():
    rows = q.annotate(_day("2026-11-08", grade="FAQ"))
    r = fr.compare({**HARVEST, "market_type": "farm_gate", "grade": "A"}, rows, PUNE, 300.0, TODAY)
    keys = {n["key"] for n in r["notes"]}
    assert r["like_for_like"] is False
    assert {"fairness_note_market_type", "fairness_note_grade"} <= keys


def test_like_for_like_when_grades_match():
    rows = q.annotate(_day("2026-11-08", grade="FAQ"))
    r = fr.compare({**HARVEST, "grade": "faq"}, rows, PUNE, 300.0, TODAY)
    assert r["like_for_like"] is True and r["notes"] == []


def test_rejected_rows_ignored():
    rows = _day("2026-11-08", prices=(("Pune", 5000), ("Mumbai", 5600), ("Nashik", 0)))
    rows[2]["min_price"] = rows[2]["max_price"] = 0
    assert fr.compare(HARVEST, q.annotate(rows), PUNE, 300.0, TODAY)["status"] == "insufficient"
