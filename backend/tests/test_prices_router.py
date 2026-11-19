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
from routers.prices import build_history, build_mandi_board, build_public_board

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
    _row("Madhya Pradesh", "Unlisted District", "Rewa", "2026-11-09", 3000),  # same state, no coords
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

def _chain(data, max_rows=None):
    """Query-builder fake. With a list, .range(a, b) pages through it and the
    server-side row cap (max_rows, like PostgREST max-rows) is applied."""
    m = MagicMock()
    for name in ("select", "eq", "gte", "order", "limit", "maybe_single"):
        getattr(m, name).return_value = m
    window = {}

    def _range(a, b):
        window["r"] = (a, b)
        return m

    def _execute():
        rows = data
        if isinstance(data, list):
            if "r" in window:
                a, b = window["r"]
                rows = data[a:b + 1]
            if max_rows is not None:
                rows = rows[:max_rows]
        return MagicMock(data=rows)

    m.range.side_effect = _range
    m.execute.side_effect = _execute
    return m


def _db(farmer, prices, max_rows=None):
    db = MagicMock()
    tables = {"farmers": _chain(farmer), "market_prices": _chain(prices, max_rows)}
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


# ── Stale threshold: one source of truth ──────────────────────────────────────

class TestStaleThresholdSource:
    def test_board_and_history_send_the_backend_threshold(self):
        from services.mandi_prices import STALE_DAYS
        assert build_mandi_board(ROWS, "Madhya Pradesh", "Indore", 5, TODAY)["stale_after_days"] == STALE_DAYS
        assert build_history([], TODAY)["stale_after_days"] == STALE_DAYS
        assert build_public_board(ROWS, TODAY)["stale_after_days"] == STALE_DAYS

    def test_is_stale_flag_follows_the_threshold_exactly(self):
        from datetime import timedelta
        from services.mandi_prices import STALE_DAYS
        on_edge = (TODAY - timedelta(days=STALE_DAYS)).isoformat()
        past_edge = (TODAY - timedelta(days=STALE_DAYS + 1)).isoformat()
        rows = [
            _row("Madhya Pradesh", "Indore", "Edge", on_edge, 3000),
            _row("Madhya Pradesh", "Indore", "Past", past_edge, 3000),
        ]
        by = {m["market"]: m for m in build_mandi_board(rows, "Madhya Pradesh", "Indore", 5, TODAY)["mandis"]}
        assert by["Edge"]["is_stale"] is False
        assert by["Past"]["is_stale"] is True

    def test_financial_uses_the_same_constant(self):
        import inspect
        from routers import financial
        from services.mandi_prices import STALE_DAYS
        assert financial.STALE_DAYS == STALE_DAYS
        assert "days=7" not in inspect.getsource(financial._get_market_prices)


# ── District / state aliases in the board ─────────────────────────────────────

class TestBoardAliases:
    def test_renamed_district_matches_profile_spelling(self):
        rows = [_row("Maharashtra", "Ahilyanagar", "APMC Rahata", "2026-11-11", 3000)]
        b = build_mandi_board(rows, "Maharashtra", "Ahmednagar", 5, TODAY)
        assert [m["match"] for m in b["mandis"]] == ["same_district"]

    def test_profile_with_new_name_matches_old_feed_name(self):
        rows = [_row("Maharashtra", "Osmanabad", "Osmanabad", "2026-11-11", 3000)]
        b = build_mandi_board(rows, "Maharashtra", "Dharashiv", 5, TODAY)
        assert [m["match"] for m in b["mandis"]] == ["same_district"]

    def test_feed_spelling_chattrapati_sambhajinagar(self):
        rows = [_row("Maharashtra", "Chattrapati Sambhajinagar", "APMC Chattrapati Sambhajinagar", "2026-11-11", 2500)]
        b = build_mandi_board(rows, "Maharashtra", "Aurangabad", 5, TODAY)
        assert b["mandis"][0]["match"] == "same_district"

    def test_state_alias_keralam_and_chattisgarh(self):
        rows = [
            _row("Keralam", "Ernakulam", "Kochi", "2026-11-11", 4000),
            _row("Chattisgarh", "Raipur", "Raipur", "2026-11-11", 3000),
        ]
        k = build_mandi_board(rows, "Kerala", "Ernakulam", 5, TODAY)
        assert k["mandis"][0]["match"] == "same_district"
        c = build_mandi_board(rows, "Chhattisgarh", "Raipur", 5, TODAY)
        assert c["mandis"][0]["market"] == "Raipur" and c["mandis"][0]["match"] == "same_district"

    def test_mandis_in_known_districts_rank_as_nearby(self):
        rows = [
            _row("Maharashtra", "Nashik", "APMC Nasik", "2026-11-11", 6000),
            _row("Maharashtra", "Mumbai", "Mumbai- Fruit Market", "2026-11-11", 8000),
            _row("Maharashtra", "Sangli", "Sangli(Phale, Bhajipala Market)", "2026-11-11", 5000),
            _row("Maharashtra", "Amarawati", "Amrawati(Frui & Veg. Market)", "2026-11-11", 4000),
        ]
        b = build_mandi_board(rows, "Maharashtra", "Pune", 10, TODAY)
        by = {m["market"]: m for m in b["mandis"]}
        assert by["APMC Nasik"]["match"] == "nearby"
        assert by["Mumbai- Fruit Market"]["match"] == "nearby"
        assert by["Sangli(Phale, Bhajipala Market)"]["match"] == "nearby"
        assert 100 <= by["APMC Nasik"]["distance_km"] <= 200
        assert by["Amrawati(Frui & Veg. Market)"]["distance_km"] is not None


# ── Row cap: the latest price per mandi is correct whatever the server cap ────

def _many_rows():
    """2,300 rows for Indore on the newest day, then Ujjain's only row last."""
    rows = [
        _row("Madhya Pradesh", "Indore", "Indore", "2026-11-11", 3800, variety=f"V{i}")
        for i in range(2300)
    ]
    rows.append(_row("Madhya Pradesh", "Ujjain", "Ujjain", "2026-11-10", 3400))
    return rows


class TestRowCapPaging:
    @pytest.mark.parametrize("cap", [1000, 300, 5000])
    def test_mandi_beyond_the_server_row_cap_is_still_found(self, client, cap):
        db = _db(FARMER, _many_rows(), max_rows=cap)
        with patch("routers.prices.get_db", return_value=db):
            r = client.get("/api/market-prices/guava?limit=5")
        assert r.status_code == 200
        markets = [m["market"] for m in r.json()["mandis"]]
        assert markets == ["Indore", "Ujjain"]
        indore = r.json()["mandis"][0]
        assert len(indore["prices"]) == 2300          # nothing from the newest day lost

    def test_requests_are_paged_not_one_big_limit(self, client):
        db = _db(FARMER, _many_rows(), max_rows=1000)
        with patch("routers.prices.get_db", return_value=db):
            client.get("/api/market-prices/guava")
        calls = db._tables["market_prices"].range.call_args_list
        assert len(calls) >= 3
        assert calls[0].args == (0, prices_router._PAGE_SIZE - 1)
        assert calls[1].args[0] == 1000                # offset advances by rows received

    def test_ordering_is_deterministic_for_paging(self, client):
        db = _db(FARMER, [])
        with patch("routers.prices.get_db", return_value=db):
            client.get("/api/market-prices/guava")
        ordered = [c.args[0] for c in db._tables["market_prices"].order.call_args_list]
        assert ordered[0] == "arrival_date" and "market_name" in ordered

    def test_history_is_paged_too(self, client):
        base = date(2025, 1, 1).toordinal()
        rows = [
            _row("Madhya Pradesh", "Indore", "Indore", date.fromordinal(base + i).isoformat(), 3000)
            for i in range(1500)
        ]
        db = _db(FARMER, rows, max_rows=1000)
        with patch("routers.prices.get_db", return_value=db):
            r = client.get("/api/market-prices/guava/history?market=Indore&state=Madhya%20Pradesh")
        assert r.status_code == 200
        assert r.json()["distinct_days"] == 1500
        assert r.json()["last_date"] == date.fromordinal(base + 1499).isoformat()


# ── Public (logged-out) board ─────────────────────────────────────────────────

class TestPublicBoard:
    def test_only_public_states_freshest_first_and_capped(self):
        rows = ROWS + [
            _row("Maharashtra", "Nashik", "APMC Nasik", "2026-11-11", 6000),
            _row("Maharashtra", "Mumbai", "Mumbai- Fruit Market", "2026-11-10", 8000),
        ]
        b = build_public_board(rows, TODAY, per_state=2)
        assert {m["state"] for m in b["mandis"]} == {"Madhya Pradesh", "Maharashtra"}
        mp = [m["market"] for m in b["mandis"] if m["state"] == "Madhya Pradesh"]
        assert mp == ["Indore", "Ujjain"]            # freshest two of three
        assert b["scope"] == "public" and b["location"] is None
        assert all(m["match"] == "public" and m["distance_km"] is None for m in b["mandis"])
        assert "Jaipur" not in [m["market"] for m in b["mandis"]]

    def test_empty(self):
        b = build_public_board([], TODAY)
        assert b["has_data"] is False and b["scope"] == "none"


class TestPublicEndpoint:
    @pytest.fixture(autouse=True)
    def _fresh_cache(self):
        prices_router._public_cache.update(at=None, data=None)
        app.dependency_overrides.clear()
        yield
        prices_router._public_cache.update(at=None, data=None)

    def test_works_without_login_and_reads_no_farmer_data(self):
        db = _db(None, ROWS)
        with patch("routers.prices.get_db", return_value=db):
            r = TestClient(app).get("/api/public/market-prices/guava")
        assert r.status_code == 200
        body = r.json()
        assert body["has_data"] is True and body["location"] is None
        assert body["attribution"] == "Source: Agmarknet / data.gov.in"
        assert {c.args[0] for c in db.table.call_args_list} == {"market_prices"}

    def test_result_is_cached(self):
        db = _db(None, ROWS)
        with patch("routers.prices.get_db", return_value=db):
            c = TestClient(app)
            c.get("/api/public/market-prices/guava")
            first = db.table.call_count
            c.get("/api/public/market-prices/guava")
        assert db.table.call_count == first

    def test_db_error_is_500_without_details(self):
        db = _db(None, [])
        db._tables["market_prices"].execute.side_effect = RuntimeError("secret detail")
        with patch("routers.prices.get_db", return_value=db):
            r = TestClient(app).get("/api/public/market-prices/guava")
        assert r.status_code == 500 and "secret" not in r.text

    def test_private_endpoint_still_requires_login(self):
        assert TestClient(app).get("/api/market-prices/guava").status_code in (401, 403, 422)
