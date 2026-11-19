"""Tests for the Sell smart DEMO dataset, DemoRepo and demo app. No network, no DB."""
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from services.sell_smart import demo, quality, stats
from services.sell_smart.demo import DemoRepo, assert_demo_allowed, build_demo_app, generate_price_rows

TODAY = date(2026, 11, 12)
BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def rows():
    return generate_price_rows(TODAY)


@pytest.fixture(scope="module")
def client():
    app = build_demo_app(TODAY)
    with patch("routers.sell_smart._today", return_value=TODAY):
        yield TestClient(app)


def test_dataset_is_deterministic(rows):
    assert generate_price_rows(TODAY) == rows


def test_every_row_is_flagged_demo_and_labelled(rows):
    assert rows and all(r["demo"] is True for r in rows)
    assert all("DEMO" in r["source_name"] for r in rows)


def test_covers_required_mandis_and_two_years(rows):
    markets = {r["market_name"] for r in rows}
    assert {"Pune", "Mumbai", "Nashik", "Solapur", "Indore", "Ujjain"} <= markets
    dates = sorted({r["arrival_date"] for r in rows})
    first, last = date.fromisoformat(dates[0]), date.fromisoformat(dates[-1])
    assert (last - first).days >= 730
    assert last == TODAY


def test_demo_data_passes_quality_layer(rows):
    annotated = quality.annotate(rows, {})
    flagged = [r for r in annotated if r["flags"]]
    assert flagged == []


def test_seasonal_view_is_available(rows):
    annotated = quality.annotate([r for r in rows if r["market_name"] == "Pune"], {})
    seasonal = stats.seasonal_view(stats.daily_series(annotated), TODAY)
    assert seasonal["status"] == "ok"


def test_assert_demo_allowed():
    with pytest.raises(SystemExit):
        assert_demo_allowed({})
    with pytest.raises(SystemExit):
        assert_demo_allowed({"SELL_SMART_ALLOW_DEMO": "0"})
    with pytest.raises(SystemExit):
        assert_demo_allowed({"SELL_SMART_ALLOW_DEMO": "1", "RENDER": "true"})
    assert_demo_allowed({"SELL_SMART_ALLOW_DEMO": "1"})


def test_responses_carry_demo_true_and_never_touch_db(client):
    def boom(*a, **k):
        raise AssertionError("get_db must not be called on the demo path")

    with patch("services.db.get_db", boom):
        for path in ("/api/sell-smart/settings", "/api/sell-smart/ranking", "/api/sell-smart/trends",
                     "/api/sell-smart/alerts", "/api/sell-smart/notifications", "/api/sell-smart/fairness",
                     "/api/sell-smart/quality"):
            r = client.get(path)
            assert r.status_code == 200, path
            assert r.json()["demo"] is True, path


def test_ranking_on_demo_repo(client):
    body = client.get("/api/sell-smart/ranking").json()
    names = {e["market_name"] for e in body["ranked"]}
    assert {"Pune", "Mumbai", "Nashik", "Solapur"} <= names
    assert body["costs_set"] is False and body["ranked_by"] == "gross"


def test_trends_and_fairness_on_demo_repo(client):
    t = client.get("/api/sell-smart/trends").json()
    assert t["has_data"] and t["seasonal"]["status"] == "ok"
    f = client.get("/api/sell-smart/fairness").json()
    assert f["status"] == "ok" and f["gap_total_rs"] is not None


def test_alert_lifecycle_on_demo_repo(client):
    created = client.post("/api/sell-smart/alerts", json={
        "state": "Maharashtra", "district": "Nashik", "target_rs_per_kg": 55}).json()["alert"]
    assert client.post(f"/api/sell-smart/alerts/{created['id']}/delete").json()["deleted"] is True


def test_cors_allows_local_static_server(client):
    r = client.options("/api/sell-smart/ranking", headers={
        "Origin": "http://127.0.0.1:5500", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "http://127.0.0.1:5500"


def test_main_never_imports_demo():
    text = (BACKEND / "main.py").read_text(encoding="utf-8", errors="replace")
    assert "sell_smart.demo" not in text and "run_sell_smart_demo" not in text


def test_run_script_refuses_without_flag(monkeypatch):
    monkeypatch.delenv("SELL_SMART_ALLOW_DEMO", raising=False)
    monkeypatch.setattr(sys, "path", [str(BACKEND)] + sys.path)
    import importlib.util
    spec = importlib.util.spec_from_file_location("run_demo", BACKEND / "scripts" / "run_sell_smart_demo.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with pytest.raises(SystemExit):
        mod.main()
