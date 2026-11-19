"""
test_sell_smart_router.py - /api/sell-smart endpoints.
The repository is an in-memory fake; get_user_id and get_repo are overridden.
No database and no network.
"""
from datetime import date

import pytest
from fastapi.testclient import TestClient

import services.rate_limiter as rl_module
from main import app
from routers import sell_smart as router_mod
from services.auth import get_user_id
from services.sell_smart.repo import get_repo
from tests.fake_sell_repo import FakeRepo, price_row

TODAY = date(2026, 11, 12)
USER = "11111111-1111-1111-1111-111111111111"
OTHER = "22222222-2222-2222-2222-222222222222"
MH = "Maharashtra"
BASE = "/api/sell-smart"
COORD_KEYS = {"lat", "lon", "lng", "latitude", "longitude", "farm_lat", "farm_lon",
              "approx_lat", "approx_lon", "coords", "coordinates"}


def _seed(repo, with_gps=False):
    repo.locations[USER] = {"state": MH, "district": "Pune",
                            "farm_lat": 18.6 if with_gps else None,
                            "farm_lon": 73.9 if with_gps else None}
    repo.prices = [
        price_row(MH, "Pune", "Pune", "2026-11-12", 5000, row_id="p1"),
        price_row(MH, "Nashik", "Nashik", "2026-11-12", 4200, row_id="p2"),
        price_row(MH, "Mumbai", "Mumbai", "2026-11-12", 3900, row_id="p3"),
        price_row(MH, "Solapur", "Solapur", "2026-11-12", 4600, row_id="p4"),
    ]


@pytest.fixture(autouse=True)
def _reset_limiter():
    rl_module._reset_store()
    yield
    rl_module._reset_store()


@pytest.fixture
def repo(monkeypatch):
    r = FakeRepo()
    monkeypatch.setattr(router_mod, "_today", lambda: TODAY)
    app.dependency_overrides[get_user_id] = lambda: USER
    app.dependency_overrides[get_repo] = lambda: r
    yield r
    app.dependency_overrides.pop(get_user_id, None)
    app.dependency_overrides.pop(get_repo, None)


@pytest.fixture
def client():
    return TestClient(app)


def _keys(obj, found=None):
    found = set() if found is None else found
    if isinstance(obj, dict):
        for k, v in obj.items():
            found.add(str(k).lower())
            _keys(v, found)
    elif isinstance(obj, list):
        for v in obj:
            _keys(v, found)
    return found


class TestAuth:
    @pytest.mark.parametrize("method,path", [
        ("get", "/settings"), ("put", "/settings"), ("get", "/ranking"), ("get", "/trends"),
        ("get", "/quality"), ("get", "/alerts"), ("post", "/alerts"), ("get", "/notifications"),
        ("get", "/fairness"),
    ])
    def test_no_token_is_rejected(self, client, method, path):
        app.dependency_overrides.pop(get_user_id, None)
        # No Authorization header: services.auth declares it as a required
        # Header, so FastAPI answers 422 before any handler runs (never 200).
        r = getattr(client, method)(BASE + path)
        assert r.status_code in (401, 403, 422)
        # An empty bearer token reaches get_user_id and is rejected with 401
        # (no network: the empty token is refused before the JWKS lookup).
        r = getattr(client, method)(BASE + path, headers={"Authorization": "Bearer "})
        assert r.status_code == 401


class TestSettings:
    def test_empty_state(self, client, repo):
        repo.locations[USER] = {"state": MH, "district": "Pune", "farm_lat": None, "farm_lon": None}
        body = client.get(BASE + "/settings").json()
        assert body["costs_set"] is False
        assert body["transport_suggestion"] is None
        assert body["settings"]["transport_mode"] is None
        assert body["location_basis"] == "district_centre"
        assert body["default_radius_km"] == 300.0

    def test_roundtrip_and_costs_set(self, client, repo):
        payload = {"transport_mode": "flat_per_quintal", "transport_rs_per_quintal_flat": 100,
                   "handling_rs_per_quintal": 50, "commission_pct": 2, "radius_km": 250,
                   "road_km_overrides": {"Maharashtra|Nashik|Nashik": 210}}
        put = client.put(BASE + "/settings", json=payload)
        assert put.status_code == 200 and put.json()["costs_set"] is True
        got = client.get(BASE + "/settings").json()
        assert got["settings"]["radius_km"] == 250
        assert got["settings"]["road_km_overrides"] == {"Maharashtra|Nashik|Nashik": 210}

    def test_transport_suggestion_from_harvest(self, client, repo):
        repo.harvests[USER] = [{"sale_quantity_kg": 500, "transport_cost": 600,
                                "sale_price_per_kg": 40, "sale_date": "2026-11-10"}]
        s = client.get(BASE + "/settings").json()["transport_suggestion"]
        assert s["mode"] == "flat_per_quintal"
        assert s["rs_per_quintal"] == pytest.approx(120.0)
        assert s["n_sales"] == 1

    @pytest.mark.parametrize("payload", [
        {"handling_rs_per_quintal": -1},
        {"transport_mode": "flat_per_quintal", "transport_rs_per_quintal_flat": -5},
        {"transport_rs_per_quintal_per_km": -0.1},
        {"commission_pct": 101},
        {"commission_pct": -1},
        {"radius_km": 0},
        {"radius_km": 1501},
        {"transport_mode": "per_quintal_per_km"},
        {"transport_mode": "teleport"},
        {"road_km_overrides": {"a|b|c": -3}},
        {"road_km_overrides": {"a|b|c": 99999}},
    ])
    def test_422_on_bad_input(self, client, repo, payload):
        assert client.put(BASE + "/settings", json=payload).status_code == 422


class TestRanking:
    def test_requires_profile(self, client, repo):
        assert client.get(BASE + "/ranking").status_code == 404

    def test_gross_ranking_when_no_costs(self, client, repo):
        _seed(repo)
        b = client.get(BASE + "/ranking").json()
        assert b["status"] == "ok" and b["costs_set"] is False and b["ranked_by"] == "gross"
        assert [m["market_name"] for m in b["ranked"]] == ["Pune", "Solapur", "Nashik", "Mumbai"]
        for m in b["ranked"]:
            assert m["source"] == "Agmarknet / data.gov.in"
            assert m["trade_date"] == "2026-11-12"
            assert m["is_stale"] is False
            assert m["quality_flags"] == []
            assert m["distance_label_key"] == "sell_distance_straight"
        assert b["attribution"] == "Source: Agmarknet / data.gov.in"
        assert b["location_basis"] == "district_centre"

    def test_net_ranking_uses_formula(self, client, repo):
        _seed(repo)
        client.put(BASE + "/settings", json={
            "transport_mode": "flat_per_quintal", "transport_rs_per_quintal_flat": 100,
            "handling_rs_per_quintal": 50, "commission_pct": 2})
        b = client.get(BASE + "/ranking").json()
        pune = next(m for m in b["ranked"] if m["market_name"] == "Pune")
        assert b["ranked_by"] == "net" and b["costs_set"] is True
        assert pune["net_per_kg"] == pytest.approx(50 - 1 - 0.5 - 1)

    def test_entered_road_km_is_labelled(self, client, repo):
        _seed(repo)
        client.put(BASE + "/settings", json={
            "transport_mode": "per_quintal_per_km", "transport_rs_per_quintal_per_km": 1,
            "road_km_overrides": {"Maharashtra|Nashik|Nashik": 200}})
        b = client.get(BASE + "/ranking").json()
        nashik = next(m for m in b["ranked"] if m["market_name"] == "Nashik")
        assert nashik["distance_km"] == 200
        assert nashik["distance_label_key"] == "sell_distance_entered"
        assert nashik["net_per_kg"] == pytest.approx(42 - 1 * 200 / 100)

    def test_rejected_rows_are_excluded(self, client, repo):
        _seed(repo)
        repo.prices.append(price_row(MH, "Nagpur", "Nagpur", "2026-11-12", 0, mn=0, mx=0, row_id="z"))
        repo.prices.append(price_row(MH, "Pune", "Pune", "2026-11-12", 9000, mn=9500, mx=9600,
                                     variety="Bad", row_id="bad"))
        b = client.get(BASE + "/ranking").json()
        names = [m["market_name"] for m in b["ranked"] + b["unranked"]]
        assert "Nagpur" not in names
        pune = next(m for m in b["ranked"] if m["market_name"] == "Pune")
        assert pune["gross_per_kg"] == 50.0

    def test_empty_state(self, client, repo):
        repo.locations[USER] = {"state": MH, "district": "Pune", "farm_lat": None, "farm_lon": None}
        b = client.get(BASE + "/ranking").json()
        assert b["has_data"] is False and b["ranked"] == [] and b["unranked"] == []

    def test_no_origin_when_location_unknown(self, client, repo):
        _seed(repo)
        repo.locations[USER]["district"] = "Nowhereville"
        b = client.get(BASE + "/ranking").json()
        assert b["status"] == "no_origin" and b["location_basis"] is None
        assert b["ranked"] == [] and len(b["unranked"]) == 4

    def test_farm_gps_basis_used_but_never_returned(self, client, repo):
        _seed(repo, with_gps=True)
        b = client.get(BASE + "/ranking").json()
        assert b["location_basis"] == "farm_gps"
        assert not (_keys(b) & COORD_KEYS)
        assert "18.6" not in client.get(BASE + "/ranking").text

    @pytest.mark.parametrize("q", ["radius_km=0", "radius_km=-5", "radius_km=1501", "radius_km=abc"])
    def test_radius_bounds(self, client, repo, q):
        _seed(repo)
        assert client.get(BASE + "/ranking?" + q).status_code == 422

    def test_small_radius_hides_far_mandis(self, client, repo):
        _seed(repo)
        b = client.get(BASE + "/ranking?radius_km=50").json()
        assert [m["market_name"] for m in b["ranked"]] == ["Pune"]
        assert b["outside_radius"] == 3


class TestTrendsQualityFairness:
    def test_trends_empty_state_says_what_is_missing(self, client, repo):
        repo.locations[USER] = {"state": MH, "district": "Pune", "farm_lat": None, "farm_lon": None}
        b = client.get(BASE + "/trends").json()
        assert b["has_data"] is False and b["series"] == []
        assert all(w["status"] == "insufficient" for w in b["windows"])
        assert b["seasonal"]["status"] == "insufficient"

    def test_trends_with_explicit_scope(self, client, repo):
        _seed(repo)
        b = client.get(BASE + "/trends?market=Pune&state=Maharashtra").json()
        assert b["has_data"] is True
        assert b["series"] == [{"trade_date": "2026-11-12", "value_per_kg": 50.0,
                                "n_rows": 1, "n_mandis": 1}]
        assert b["source"] == "Agmarknet / data.gov.in"

    def test_trends_profile_missing(self, client, repo):
        assert client.get(BASE + "/trends").status_code == 404

    def test_quality_lists_flagged_rows(self, client, repo):
        _seed(repo)
        repo.prices.append(price_row(MH, "Nagpur", "Nagpur", "2026-11-12", 0, mn=0, mx=0, row_id="z"))
        b = client.get(BASE + "/quality").json()
        assert b["summary"]["rejected"] == 1
        assert b["flagged_total"] == 1 and b["flagged"][0]["flags"] == ["ZERO_PRICE"]
        assert b["summary"]["confidence"] in ("High", "Medium", "Low")

    def test_fairness_without_sale(self, client, repo):
        _seed(repo)
        b = client.get(BASE + "/fairness").json()
        assert b["status"] == "insufficient" and b["reason"] == "no_sale"
        assert b["reason_key"] == "sell_fairness_no_sale"

    def test_fairness_with_sale(self, client, repo):
        _seed(repo)
        repo.harvests[USER] = [{"sale_date": "2026-11-10", "sale_price_per_kg": 40,
                                "sale_quantity_kg": 100, "grade": "FAQ", "market_type": "mandi",
                                "farmer_id": "secret-farmer-id"}]
        b = client.get(BASE + "/fairness").json()
        assert b["status"] == "ok" and b["n_mandis"] == 4
        assert b["market_median_per_kg"] == pytest.approx(44.0)
        assert b["gap_per_kg"] == pytest.approx(-4.0)
        assert b["gap_total_rs"] == pytest.approx(-400.0)
        assert "secret-farmer-id" not in client.get(BASE + "/fairness").text


class TestAlerts:
    def _body(self, **kw):
        return {"state": MH, "district": "Pune", "market_name": "Pune",
                "target_rs_per_kg": 45, **kw}

    def test_create_list_update_delete(self, client, repo):
        created = client.post(BASE + "/alerts", json=self._body())
        assert created.status_code == 201
        a = created.json()["alert"]
        assert a["direction"] == "at_or_above" and a["is_active"] is True
        listed = client.get(BASE + "/alerts").json()
        assert listed["active_count"] == 1 and listed["max_alerts"] == 20
        upd = client.put(f"{BASE}/alerts/{a['id']}", json={"target_rs_per_kg": 55})
        assert upd.status_code == 200 and upd.json()["alert"]["target_rs_per_kg"] == 55
        assert repo.alerts[a["id"]]["last_state"] is None  # re-armed
        gone = client.post(f"{BASE}/alerts/{a['id']}/delete")
        assert gone.status_code == 200 and gone.json()["deleted"] is True
        assert client.get(BASE + "/alerts").json()["alerts"] == []
        assert repo.alerts[a["id"]]["deleted_at"] is not None  # soft delete

    @pytest.mark.parametrize("payload", [
        {"target_rs_per_kg": 0}, {"target_rs_per_kg": -3}, {"state": ""},
        {"direction": "sideways"}, {"state": "x" * 500},
    ])
    def test_422_on_bad_alert(self, client, repo, payload):
        assert client.post(BASE + "/alerts", json=self._body(**payload)).status_code == 422

    def test_other_farmers_alert_is_404(self, client, repo):
        theirs = repo.create_alert(OTHER, {"state": MH, "target_rs_per_kg": 40,
                                           "direction": "at_or_above", "is_active": True})
        assert client.put(f"{BASE}/alerts/{theirs['id']}", json={"target_rs_per_kg": 1}).status_code == 404
        assert client.post(f"{BASE}/alerts/{theirs['id']}/delete").status_code == 404
        assert repo.alerts[theirs["id"]]["target_rs_per_kg"] == 40
        assert repo.alerts[theirs["id"]]["deleted_at"] is None
        assert client.get(BASE + "/alerts").json()["alerts"] == []

    def test_unknown_or_malformed_id(self, client, repo):
        assert client.post(f"{BASE}/alerts/33333333-3333-3333-3333-333333333333/delete").status_code == 404
        assert client.put(f"{BASE}/alerts/not-a-uuid", json={"is_active": False}).status_code == 422

    def test_409_above_twenty_active_alerts(self, client, repo):
        for i in range(20):
            repo.create_alert(USER, {"state": MH, "target_rs_per_kg": 40 + i,
                                     "direction": "at_or_above", "is_active": True})
        r = client.post(BASE + "/alerts", json=self._body())
        assert r.status_code == 409

    def test_reactivating_above_the_cap_is_409(self, client, repo):
        paused = repo.create_alert(USER, {"state": MH, "target_rs_per_kg": 40,
                                          "direction": "at_or_above", "is_active": False})
        for i in range(20):
            repo.create_alert(USER, {"state": MH, "target_rs_per_kg": 41 + i,
                                     "direction": "at_or_above", "is_active": True})
        r = client.put(f"{BASE}/alerts/{paused['id']}", json={"is_active": True})
        assert r.status_code == 409

    def test_null_required_field_is_422(self, client, repo):
        a = client.post(BASE + "/alerts", json=self._body()).json()["alert"]
        assert client.put(f"{BASE}/alerts/{a['id']}", json={"state": None}).status_code == 422


class TestNotifications:
    def test_list_and_mark_read(self, client, repo):
        mine = repo.insert_notification(USER, "price_alert", None, {"trade_date": "2026-11-12"})
        repo.insert_notification(OTHER, "price_alert", None, {"trade_date": "2026-11-12"})
        listed = client.get(BASE + "/notifications").json()
        assert [n["id"] for n in listed["notifications"]] == [mine["id"]]
        assert listed["unread_count"] == 1
        done = client.post(f"{BASE}/notifications/{mine['id']}/read")
        assert done.status_code == 200 and done.json()["notification"]["read_at"]
        assert client.get(BASE + "/notifications?unread_only=true").json()["notifications"] == []

    def test_other_farmers_notification_is_404(self, client, repo):
        theirs = repo.insert_notification(OTHER, "price_alert", None, {})
        assert client.post(f"{BASE}/notifications/{theirs['id']}/read").status_code == 404
        assert repo.notifications[0]["read_at"] is None

    def test_empty_state(self, client, repo):
        b = client.get(BASE + "/notifications").json()
        assert b == {"notifications": [], "unread_count": 0}

    @pytest.mark.parametrize("q", ["limit=0", "limit=101"])
    def test_limit_bounds(self, client, repo, q):
        assert client.get(BASE + "/notifications?" + q).status_code == 422


class TestNoCoordinatesAnywhere:
    def test_no_coordinate_keys_in_any_get_response(self, client, repo):
        _seed(repo, with_gps=True)
        repo.harvests[USER] = [{"sale_date": "2026-11-10", "sale_price_per_kg": 40,
                                "sale_quantity_kg": 100, "grade": "FAQ", "market_type": "mandi"}]
        client.post(BASE + "/alerts", json={"state": MH, "target_rs_per_kg": 45})
        for path in ("/settings", "/ranking", "/trends", "/quality", "/alerts",
                     "/notifications", "/fairness"):
            r = client.get(BASE + path)
            assert r.status_code == 200, path
            assert not (_keys(r.json()) & COORD_KEYS), path


class TestRateLimitAndErrors:
    def test_read_limit_then_429(self, client, repo):
        limit = rl_module.CATEGORY_LIMITS["sell_smart_read"]
        assert limit == 60
        for _ in range(limit):
            assert client.get(BASE + "/alerts").status_code == 200
        r = client.get(BASE + "/alerts")
        assert r.status_code == 429 and "Retry-After" in r.headers

    def test_write_limit_then_429(self, client, repo):
        limit = rl_module.CATEGORY_LIMITS["sell_smart_write"]
        assert limit == 20
        for _ in range(limit):
            assert client.put(BASE + "/settings", json={}).status_code == 200
        assert client.put(BASE + "/settings", json={}).status_code == 429

    def test_storage_failure_is_generic_500(self, client, repo):
        repo.fail = True
        r = client.get(BASE + "/alerts")
        assert r.status_code == 500 and r.json()["detail"] == "Database error."
