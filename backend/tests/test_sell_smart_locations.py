"""Sell smart location resolution."""

import json

import pytest

from services.sell_smart import locations as loc


def test_supplement_rows_have_source_and_kind():
    data = json.loads(loc.SUPPLEMENT_PATH.read_text(encoding="utf-8"))
    assert data["rows"]
    for row in data["rows"]:
        assert row["source_url"].startswith("https://")
        assert row["kind"] == "district HQ city"
        assert -90 <= row["lat"] <= 90 and -180 <= row["lon"] <= 180


@pytest.mark.parametrize("state,district", [
    ("Maharashtra", "Pune"), ("Maharashtra", "Nashik"),
    ("Maharashtra", "Mumbai"), ("Maharashtra", "Solapur"),
    ("Madhya Pradesh", "Indore"),
])
def test_feed_districts_resolve(state, district):
    r = loc.resolve_district(state, district)
    assert r is not None
    lat, lon, basis = r
    assert 8 < lat < 36 and 68 < lon < 98 and basis


def test_case_insensitive_and_unknown():
    assert loc.resolve_district("maharashtra", "SOLAPUR") is not None
    assert loc.resolve_district("Maharashtra", "Nowhereville") is None
    assert loc.resolve_district("", "") is None


def test_supplement_basis_label(monkeypatch):
    # Mumbai is now in services.geo too; hide it there to exercise the supplement path.
    monkeypatch.setattr(loc, "get_exact_district_coordinates", lambda s, d: None)
    assert loc.resolve_district("Maharashtra", "Mumbai")[2] == loc.BASIS_SUPPLEMENT
    assert loc.resolve_district("Maharashtra", "Solapur")[2] == loc.BASIS_SUPPLEMENT


def test_pune_mumbai_distance_plausible():
    p = loc.resolve_district("Maharashtra", "Pune")
    m = loc.resolve_district("Maharashtra", "Mumbai")
    d = loc.distance_km(p[:2], m[:2])
    assert 110 < d < 130
