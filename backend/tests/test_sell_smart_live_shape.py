"""Rank the live-shape feed fixture end to end. No network, no DB."""
import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sell_smart_examples", BACKEND / "scripts" / "sell_smart_examples.py")
examples = importlib.util.module_from_spec(spec)
spec.loader.exec_module(examples)


def test_fixture_is_guava_only_and_has_no_secret():
    text = examples.FIXTURE.read_text(encoding="utf-8")
    data = json.loads(text)
    assert all(r["commodity"] == "Guava" for r in data["records"])
    assert "api-key" not in text.lower() and "api_key" not in text.lower()


def test_ranks_the_four_pune_area_mandis_by_net():
    result = examples.rank_pune(examples.fixture_rows())
    assert result["status"] == "ok" and result["costs_set"] and result["ranked_by"] == "net"
    ranked = {e["market_name"]: e for e in result["ranked"]}
    assert set(ranked) == {"Pune", "Mumbai", "Nashik", "Solapur"}
    nets = [e["net_per_kg"] for e in result["ranked"]]
    assert nets == sorted(nets, reverse=True)
    # Pune: two feed rows share one conflict key on the latest day; parse_records keeps the last (5200 Rs/quintal).
    pune = ranked["Pune"]
    assert pune["gross_per_kg"] == pytest.approx(52.0)
    assert pune["distance_km"] == pytest.approx(0.0, abs=0.01)
    # net = modal - 0 - 40/100 - modal*4/100
    assert pune["net_per_kg"] == pytest.approx(52.0 - 0.4 - 52.0 * 0.04)


def test_hand_computed_mumbai_net():
    result = examples.rank_pune(examples.fixture_rows())
    m = next(e for e in result["ranked"] if e["market_name"] == "Mumbai")
    expected = 57.0 - 2.5 * m["distance_km"] / 100 - 0.4 - 57.0 * 0.04
    assert m["net_per_kg"] == pytest.approx(expected)


def test_stale_when_run_much_later():
    result = examples.rank_pune(examples.fixture_rows(), date(2026, 12, 31))
    assert result["ranked"] == [] and all(e["stale"] for e in result["unranked"])
