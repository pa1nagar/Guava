"""Sell smart ranking."""

from datetime import date

import pytest

from services.sell_smart import locations as loc
from services.sell_smart import quality as q
from services.sell_smart import ranking as rk

TODAY = date(2026, 11, 10)
PUNE = loc.resolve_district("Maharashtra", "Pune")[:2]


def _row(i, district, modal, day="2026-11-10", state="Maharashtra", variety="", grade="", market=None):
    return {"id": i, "state": state, "district": district, "market_name": market or district,
            "variety": variety, "grade": grade, "min_price": modal - 500, "max_price": modal + 500,
            "modal_price": modal, "arrival_date": day}


PUNE_ROWS = [_row(1, "Pune", 5000), _row(2, "Mumbai", 5600), _row(3, "Nashik", 5200), _row(4, "Solapur", 4800)]
COSTS = {"transport_mode": rk.MODE_PER_KM, "transport_value": 2.0,
         "handling_rs_per_quintal": 100.0, "commission_pct": 2.0}


def _by_name(res):
    return {e["market_name"]: e for e in res["ranked"] + res["unranked"]}


def test_worked_pune_example_net():
    rows = q.annotate(PUNE_ROWS)
    res = rk.rank_mandis(rows, PUNE, COSTS, 300.0, TODAY)
    assert res["status"] == "ok" and res["costs_set"] and res["ranked_by"] == "net"
    e = _by_name(res)
    # Hand formula: net = modal - (2 Rs/quintal/km x km)/100 - 100/100 - modal x 2/100
    for name, modal in (("Pune", 50.0), ("Mumbai", 56.0), ("Nashik", 52.0), ("Solapur", 48.0)):
        km = e[name]["distance_km"]
        expected = modal - 2.0 * km / 100 - 1.0 - modal * 2 / 100
        assert e[name]["gross_per_kg"] == pytest.approx(modal)
        assert e[name]["net_per_kg"] == pytest.approx(expected)
    assert e["Pune"]["distance_km"] == pytest.approx(0.0, abs=1e-6)
    assert e["Pune"]["net_per_kg"] == pytest.approx(48.0)
    assert 115 < e["Mumbai"]["distance_km"] < 125
    assert [x["market_name"] for x in res["ranked"]] == ["Mumbai", "Pune", "Nashik", "Solapur"]
    assert [x["rank"] for x in res["ranked"]] == [1, 2, 3, 4]


def test_no_costs_ranks_by_gross_and_flags_prompt():
    res = rk.rank_mandis(q.annotate(PUNE_ROWS), PUNE, {}, 300.0, TODAY)
    assert res["costs_set"] is False and res["ranked_by"] == "gross"
    assert [x["market_name"] for x in res["ranked"]] == ["Mumbai", "Nashik", "Pune", "Solapur"]
    assert all(x["net_per_kg"] == pytest.approx(x["gross_per_kg"]) for x in res["ranked"])


def test_flat_transport_and_road_km_override():
    s = {"transport_mode": rk.MODE_FLAT, "transport_value": 150.0}
    res = rk.rank_mandis(q.annotate(PUNE_ROWS), PUNE, s, 300.0, TODAY)
    assert _by_name(res)["Nashik"]["net_per_kg"] == pytest.approx(52.0 - 1.5)
    s2 = {"transport_mode": rk.MODE_PER_KM, "transport_value": 2.0,
          "road_km_overrides": {"Maharashtra|Nashik|Nashik": 200.0}}
    e = _by_name(rk.rank_mandis(q.annotate(PUNE_ROWS), PUNE, s2, 300.0, TODAY))["Nashik"]
    assert e["distance_km"] == 200.0 and e["distance_basis"] == rk.DISTANCE_BASIS_ENTERED
    assert e["distance_label"] == rk.DISTANCE_LABEL_ENTERED
    assert e["net_per_kg"] == pytest.approx(52.0 - 4.0)


def test_default_distance_label_is_straight_line():
    e = _by_name(rk.rank_mandis(q.annotate(PUNE_ROWS), PUNE, {}, 300.0, TODAY))["Mumbai"]
    assert "straight-line" in e["distance_label"] and "road distance is longer" in e["distance_label"]


def test_unknown_location_listed_without_net():
    rows = q.annotate(PUNE_ROWS + [_row(9, "Atlantis", 6000)])
    res = rk.rank_mandis(rows, PUNE, COSTS, 300.0, TODAY)
    a = [x for x in res["unranked"] if x["district"] == "Atlantis"][0]
    assert a["distance_km"] is None and a["net_per_kg"] is None and a["rank"] is None
    assert all(x["district"] != "Atlantis" for x in res["ranked"])


def test_rejected_rows_excluded():
    rows = q.annotate(PUNE_ROWS + [_row(9, "Pune", 0, market="Pune2")])
    rows[-1]["min_price"] = rows[-1]["max_price"] = 0
    res = rk.rank_mandis(rows, PUNE, {}, 300.0, TODAY)
    assert "Pune2" not in _by_name(res)


def test_stale_mandi_listed_not_ranked():
    rows = q.annotate(PUNE_ROWS + [_row(9, "Nashik", 9000, day="2026-10-20", market="OldNashik")])
    res = rk.rank_mandis(rows, PUNE, {}, 300.0, TODAY)
    stale = [x for x in res["unranked"] if x["market_name"] == "OldNashik"][0]
    assert stale["stale"] is True and stale["rank"] is None


def test_radius_excludes_and_counts():
    res = rk.rank_mandis(q.annotate(PUNE_ROWS), PUNE, {}, 150.0, TODAY)
    names = [x["market_name"] for x in res["ranked"]]
    assert "Solapur" not in names and res["outside_radius"] >= 1


def test_no_origin_means_no_ranking():
    res = rk.rank_mandis(q.annotate(PUNE_ROWS), None, COSTS, 300.0, TODAY)
    assert res["status"] == "no_origin" and res["ranked"] == [] and len(res["unranked"]) == 4


def test_per_mandi_price_is_median_of_rows_and_lists_varieties():
    rows = q.annotate([_row(1, "Pune", 4000, variety="A", grade="X"), _row(2, "Pune", 5000, variety="B", grade="Y"),
                       _row(3, "Pune", 6000, variety="C", grade="Z"), _row(4, "Mumbai", 5000),
                       _row(5, "Nashik", 5000)])
    e = _by_name(rk.rank_mandis(rows, PUNE, {}, 300.0, TODAY))["Pune"]
    assert e["gross_per_kg"] == pytest.approx(50.0) and e["n_rows"] == 3 and len(e["varieties"]) == 3


def test_per_km_without_distance_gives_no_net():
    c = rk.compute_costs(COSTS, None, 50.0)
    assert c["net_per_kg"] is None and c["costs_set"] is True


def test_compute_costs_values():
    c = rk.compute_costs(COSTS, 100.0, 50.0)
    assert c["transport_per_kg"] == pytest.approx(2.0)
    assert c["handling_per_kg"] == pytest.approx(1.0)
    assert c["commission_per_kg"] == pytest.approx(1.0)
    assert c["net_per_kg"] == pytest.approx(46.0)
    assert rk.compute_costs({}, 100.0, 50.0)["costs_set"] is False


def test_substitution_text_shown():
    e = _by_name(rk.rank_mandis(q.annotate(PUNE_ROWS), PUNE, COSTS, 300.0, TODAY))["Pune"]
    assert e["substitution"] == "Rs 50.00 - Rs 0.00 - Rs 1.00 - Rs 1.00 = Rs 48.00"


def test_suggest_transport():
    assert rk.suggest_transport([]) is None
    assert rk.suggest_transport([{"transport_cost": None, "sale_quantity_kg": 100}]) is None
    s = rk.suggest_transport([{"transport_cost": 600, "sale_quantity_kg": 500},
                              {"transport_cost": None, "sale_quantity_kg": 100}])
    assert s["rs_per_quintal"] == pytest.approx(120.0) and s["n_sales"] == 1
    assert s["label"] == "from 1 logged sale(s)" and s["mode"] == rk.MODE_FLAT
