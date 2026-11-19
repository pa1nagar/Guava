"""
test_prices_router.py — Mandi price endpoints (board ranking, history, admin trigger).

The database is mocked; get_user_id is overridden. No network calls.
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from routers import prices as prices_router
from routers.prices import build_history, build_mandi_board

TODAY = date(2026, 11, 12)


def _row(state, district, market, trade, modal, mn=None, mx=None, variety="", grade=""):
    return {
        "state": state, "district": district, "market_name": market,
        "variety": variety, "grade": grade,
        "min_price": mn if mn is not None else modal - 500,
        "max_price": mx if mx is not None else modal + 500,
        "modal_price": modal, "arrival_date": trade,
        "source_name": "Agmarknet / data.gov.in",
        "fetched_at": "2026-11-12T02:00:00+00:00",
    }


ROWS = [  # newest first, like the endpoint query
    _row("Madhya Pradesh", "Indore", "Indore", "2026-11-11", 3800, 3000, 4500, "Other", "FAQ"),
    _row("Madhya Pradesh", "Indore", "Indore", "2026-11-04", 3500),   # older, ignored
    _row("Madhya Pradesh", "Ujjain", "Ujjain", "2026-11-10", 3400),
    _row("Madhya Pradesh", "Rewa", "Rewa", "2026-11-09", 3000),       # same state, no coords
    _row("Maharashtra", "Pune", "Pune", "2026-11-02", 5000),           # far, stale
    _row("Rajasthan", "Jaipur", "Jaipur", "2026-11-10", 2500),         # other state, unknown coords
]


# ── build_mandi_board ─────────────────────────────────────────────────────────

class TestBuildMandiBoard:
    def test_same_district_first_then_nearby_then_state(self):
        b = build_mandi_board(ROWS, "Madhya Pradesh", "Indore", 10, TODAY)
        assert [m["market"] for m in b["mandis"]] == ["Indore", "Ujjain", "Rewa"]
        assert [m["match"] for m in b["mandis"]] == ["same_district", "nearby", "same_state"]
        assert b["scope"] == "state"
        assert b["scope_note"]

    def test_latest_price_per_mandi_only(self):
        b = build_mandi_board(ROWS, "Madhya Pradesh", "Indore", 10, TODAY)
        indore = b["mandis"][0]
        assert indore["trade_date"] == "2026-11-11"
        assert len(indore["prices"]) == 1
        p = indore["prices"][0]
        assert (p["min_per_kg"], p["modal_per_kg"], p["max_per_kg"]) == (30.0, 38.0, 45.0)
        assert p["modal_per_quintal"] == 3800

    def test_every_price_has_source_date_and_stale_flag(self):
        b = build_mandi_board(ROWS, "Madhya Pradesh", "Indore", 10, TODAY)
        for m in b["mandis"]:
            assert m["source"] == "Agmarknet / data.gov.in"
            assert m["trade_date"]
            assert isinstance(m["is_stale"], bool)
        assert b["attribution"] == "Source: Agmarknet / data.gov.in"

    def test_stale_flag_after_seven_days(self):
        b = build_mandi_board(ROWS, "Madhya Pradesh", "Indore", 10, TODAY)
        by = {m["market"]: m for m in b["mandis"]}
        assert by["Indore"]["is_stale"] is False
        assert by["Rewa"]["is_stale"] is False  # 3 days old
        # recompute with a later "today" to prove the boundary moves
        b2 = build_mandi_board(ROWS, "Madhya Pradesh", "Indore", 10, date(2026, 11, 25))
        assert all(m["is_stale"] for m in b2["mandis"])
        assert b2["is_stale"] is True

    def test_distance_uses_district_centres(self):
        b = build_mandi_board(ROWS, "Madhya Pradesh", "Indore", 10, TODAY)
        ujjain = next(m for m in b["mandis"] if m["market"] == "Ujjain")
        assert 30 <= ujjain["distance_km"] <= 60
        assert next(m for m in b["mandis"] if m["market"] == "Rewa")["distance_km"] is None

    def test_limit_applies(self):
        b = build_mandi_board(ROWS, "Madhya Pradesh", "Indore", 2, TODAY)
        assert len(b["mandis"]) == 2

    def test_district_scope_when_only_district_mandis(self):
        b = build_mandi_board(ROWS[:2], "Madhya Pradesh", "Indore", 5, TODAY)
        assert b["scope"] == "district"

    def test_unknown_district_falls_back_to_same_state_only(self):
        b = build_mandi_board(ROWS, "Madhya Pradesh", "Nowhere", 10, TODAY)
        assert b["location"]["district_location_known"] is False
        assert {m["match"] for m in b["mandis"]} == {"same_state"}
        assert all(m["state"] == "Madhya Pradesh" for m in b["mandis"])

    def test_other_state_beyond_distance_excluded(self):
        b = build_mandi_board(ROWS, "Madhya Pradesh", "Indore", 10, TODAY)
        assert "Pune" not in [m["market"] for m in b["mandis"]]   # ~480 km away
        assert "Jaipur" not in [m["market"] for m in b["mandis"]]  # location unknown

    def test_empty(self):
        b = build_mandi_board([], "Madhya Pradesh", "Indore", 5, TODAY)
        assert b["has_data"] is False and b["mandis"] == [] and b["scope"] == "none"
        assert b["as_of"] is None and b["is_stale"] is True


class TestBuildHistory:
    def test_not_enough_history_message(self):
        rows = [_row("MP", "Indore", "Indore", f"2026-11-0{d}", 3000) for d in range(1, 4)]
        h = build_history(rows, TODAY)
        assert h["distinct_days"] == 3
        assert h["has_trend"] is False
        assert "not enough price history" in h["message"].lower()

    def test_trend_after_seven_days_and_daily_aggregation(self):
        rows = [_row("MP", "Indore", "Indore", f"2026-11-0{d}", 3000 + d * 100) for d in range(1, 8)]
        rows.append(_row("MP", "Indore", "Indore", "2026-11-07", 4000, 3500, 5000))
        h = build_history(rows, TODAY)
        assert h["distinct_days"] == 7 and h["has_trend"] is True and h["message"] is None
        last = h["series"][-1]
        assert last["trade_date"] == "2026-11-07"
        assert last["modal_per_kg"] == round((3700 + 4000) / 2 / 100, 2)
        assert last["rows"] == 2
        assert h["first_date"] == "2026-11-01" and h["last_date"] == "2026-11-07"

    def test_empty(self):
        h = build_history([], TODAY)
        assert h["series"] == [] and h["has_trend"] is False and h["is_stale"] is True


# ── HTTP endpoints ────────────────────────────────────────────────────────────

def _chain(data):
    m = MagicMock()
    for name in ("select", "eq", "gte", "order", "limit", "maybe_single"):
        getattr(m, name).return_value = m
    m.execute.return_value = MagicMock(data=data)
    return m


def _db(farmer, prices):
    db = MagicMock()
    tables = {"farmers": _chain(farmer), "market_prices": _chain(prices)}
    db.table.side_effect = lambda n: tables[n]
    db._tables = tables
    return db


@pytest.fixture
def client():
    async def _uid():
        return "user-a"

    app.dependency_overrides[prices_router.get_user_id] = _uid
    yield TestClient(app)
    app.dependency_overrides.clear()


FARMER = {"state": "Madhya Pradesh", "district": "Indore"}


class TestPriceEndpoint:
    def test_returns_board_for_farmer_location(self, client):
        fixed = [dict(r, arrival_date=r["arrival_date"]) for r in ROWS]
        db = _db(FARMER, fixed)
        with patch("routers.prices.get_db", return_value=db):
            r = client.get("/api/market-prices/guava?limit=3")
        assert r.status_code == 200
        body = r.json()
        assert body["location"]["district"] == "Indore"
        assert body["attribution"] == "Source: Agmarknet / data.gov.in"
        assert body["mandis"][0]["market"] == "Indore"
        # query is scoped to guava
        db._tables["market_prices"].eq.assert_any_call("commodity", "guava")

    def test_empty_table_gives_empty_state_not_error(self, client):
        with patch("routers.prices.get_db", return_value=_db(FARMER, [])):
            r = client.get("/api/market-prices/guava")
        assert r.status_code == 200
        assert r.json()["has_data"] is False

    def test_missing_profile_is_404(self, client):
        with patch("routers.prices.get_db", return_value=_db(None, [])):
            assert client.get("/api/market-prices/guava").status_code == 404

    def test_requires_auth(self):
        app.dependency_overrides.clear()
        r = TestClient(app).get("/api/market-prices/guava")
        assert r.status_code in (401, 403, 422)  # no bearer token: never 200

    def test_limit_validated(self, client):
        with patch("routers.prices.get_db", return_value=_db(FARMER, [])):
            assert client.get("/api/market-prices/guava?limit=0").status_code == 422

    def test_db_error_is_500_without_details(self, client):
        db = _db(FARMER, [])
        db._tables["market_prices"].execute.side_effect = RuntimeError("secret detail")
        with patch("routers.prices.get_db", return_value=db):
            r = client.get("/api/market-prices/guava")
        assert r.status_code == 500
        assert "secret" not in r.text


class TestHistoryEndpoint:
    def test_explicit_market(self, client):
        rows = [_row("Madhya Pradesh", "Indore", "Indore", "2026-11-0%d" % d, 3000) for d in range(1, 4)]
        db = _db(FARMER, rows)
        with patch("routers.prices.get_db", return_value=db):
            r = client.get("/api/market-prices/guava/history?market=Indore&state=Madhya%20Pradesh")
        body = r.json()
        assert r.status_code == 200
        assert body["market"] == "Indore" and body["distinct_days"] == 3
        assert body["has_trend"] is False and "not enough" in body["message"].lower()
        db._tables["market_prices"].eq.assert_any_call("market_name", "Indore")

    def test_default_market_with_no_data(self, client):
        with patch("routers.prices.get_db", return_value=_db(FARMER, [])):
            r = client.get("/api/market-prices/guava/history")
        assert r.status_code == 200
        assert r.json()["series"] == [] and r.json()["market"] is None


class TestAdminTrigger:
    def test_disabled_without_token_env(self, client, monkeypatch):
        monkeypatch.delenv("PRICE_INGEST_ADMIN_TOKEN", raising=False)
        r = client.post("/api/admin/market-prices/ingest", headers={"X-Admin-Token": "x"})
        assert r.status_code == 503

    def test_wrong_or_missing_token_forbidden(self, client, monkeypatch):
        monkeypatch.setenv("PRICE_INGEST_ADMIN_TOKEN", "s3cret")
        assert client.post("/api/admin/market-prices/ingest").status_code == 403
        r = client.post("/api/admin/market-prices/ingest", headers={"X-Admin-Token": "nope"})
        assert r.status_code == 403

    def test_correct_token_runs_ingestion(self, client, monkeypatch):
        monkeypatch.setenv("PRICE_INGEST_ADMIN_TOKEN", "s3cret")
        with patch("routers.prices.run_ingestion", return_value={"status": "ok", "upserted": 3}) as run:
            r = client.post("/api/admin/market-prices/ingest", headers={"X-Admin-Token": "s3cret"})
        assert r.status_code == 200 and r.json()["upserted"] == 3
        run.assert_called_once()
