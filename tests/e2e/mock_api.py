"""Mocked network for tests/e2e/browser_check.py. No real network is used.

Fixture values are fake test data, not real prices.
"""
import json
import os
from pathlib import Path

FIX = Path(__file__).parent / "fixtures"

SUPABASE_STUB = """
const session = localStorage.getItem("sf_test_anon") === "1" ? null : __SESSION__;
export function createClient() {
  return {
    auth: {
      getSession: async () => ({ data: { session }, error: null }),
      onAuthStateChange: () => ({ data: { subscription: { unsubscribe() {} } } }),
      signOut: async () => ({ error: null }),
      signInWithOAuth: async () => ({ data: {}, error: null }),
    },
  };
}
"""
SESSION = {"access_token": "test", "user": {"id": "u1", "email": "t@example.com",
                                            "user_metadata": {"full_name": "Test Farmer"}}}
CHART_STUB = "window.Chart = function(){ this.destroy=function(){}; };"

# (substring of path, fixture file) - first match wins
ROUTES = [
    ("/api/public/market-prices/guava", "mandi_board.json"),
    ("/api/market-prices/guava", "mandi_board.json"),
    ("/api/farmers/me/farms", "list.json"),
    ("/api/farmers/me/tasks", "list.json"),
    ("/api/farmers/me/inventory", "list.json"),
    ("/api/farmers/me/observations", "list.json"),
    ("/api/farmers/me/activities", "list.json"),
    ("/api/farmers/me/report", "report.json"),
    ("/api/farmers/me", "farmer.json"),
    ("/api/plan", "plan.json"),
    ("/api/constants/activity-types", "list.json"),
    ("/health", "health.json"),
]


def history(days: int | None = None):
    """Price history like build_history(): 3 saved days by default (counter), 8 or more draws the line chart.
    Set SF_HISTORY_DAYS=8 to select the line-chart variant. TEST DATA, not real prices."""
    n = int(days if days is not None else os.environ.get("SF_HISTORY_DAYS", "3"))
    ds = [f"2026-11-{20 - n + 1 + i:02d}" for i in range(n)]
    return {"has_trend": n >= 7, "min_days_for_trend": 7, "distinct_days": n, "market": "Test Mandi One (fake)",
            "first_date": ds[0], "last_date": ds[-1], "source": "Agmarknet (test)",
            "series": [{"trade_date": d, "modal_per_kg": 40 + i, "min_per_kg": 32 + i, "max_per_kg": 48 + i, "rows": 1}
                       for i, d in enumerate(ds)]}


def fixture_for(path: str):
    for needle, name in ROUTES:
        if needle in path:
            return json.loads((FIX / name).read_text(encoding="utf-8"))
    return {}


PUBLIC_NEEDLES = ("/api/public/", "/api/market-prices/", "/api/sell-smart")

# Sell smart fixtures: shapes generated from backend/services/sell_smart/demo.py (TEST DATA, made-up values).
_SELL = None


def _sell():
    global _SELL
    if _SELL is None:
        _SELL = json.loads((FIX / "sell_demo_shapes.json").read_text(encoding="utf-8"))
    return _SELL


def _sell_response(path: str, method: str, body: str, scenario: str):
    """(status, json) for /api/sell-smart/*. Public data follows the scenario too."""
    d = _sell()
    if scenario == "error":
        return 500, {"detail": "Internal error (test)"}
    section = path.split("/api/sell-smart/", 1)[-1].split("?")[0].strip("/")
    first = section.split("/")[0]
    if method == "GET":
        if scenario == "empty":
            empty = {
                "settings": {**d["settings"], "costs_set": False, "settings": {"transport_mode": None}, "transport_suggestion": None},
                "ranking": {**d["ranking"], "has_data": False, "ranked": [], "unranked": [], "status": "no_data"},
                "trends": {**d["trends"], "has_data": False, "series": []},
                "alerts": {**d["alerts"], "alerts": []},
                "notifications": {"notifications": []},
                "fairness": {"status": "insufficient", "reason": "no_origin", "reason_text_en": "x"},
            }
            return 200, empty.get(first, {})
        return 200, d.get(first, {})
    if first == "alerts" and method == "POST" and section == "alerts":
        if '"target_rs_per_kg":999' in body.replace(" ", "").replace("999.0", "999"):
            return 409, {"detail": "You can have at most 20 active alerts."}
        return 201, {"alert": d["alerts"]["alerts"][0]}
    if first == "alerts" and method == "PUT":
        return 200, {"alert": d["alerts"]["alerts"][0]}
    if first == "alerts" and section.endswith("/delete"):
        return 200, {"deleted": True}
    if first == "notifications":
        return 200, {"ok": True}
    if first == "settings" and method == "PUT":
        return 200, {"settings": d["settings"]["settings"]}
    return 200, {}


def _public_board(scenario: str):
    board = json.loads((FIX / "mandi_board.json").read_text(encoding="utf-8"))
    if scenario == "empty":
        return {"has_data": False, "mandis": [], "scope": "none", "as_of": None, "stale_after_days": 3}
    return board


def respond(path: str, method: str = "GET", body: str = "", scenario: str = "ok"):
    """(status, json) for any mocked API call."""
    import fixtures_app  # noqa: PLC0415 - sibling module, path is set up by browser_check.py
    if "/api/sell-smart" in path:
        return _sell_response(path, method, body, scenario)
    if "/api/market-prices/guava/history" in path:
        return (500, {"detail": "Internal error (test)"}) if scenario == "error" else (200, history(0 if scenario == "empty" else None))
    if "/api/public/market-prices" in path or "/api/market-prices/guava" in path and "history" not in path:
        if scenario == "error":
            return 500, {"detail": "Internal error (test)"}
        return 200, _public_board(scenario)
    if any(n in path for n in PUBLIC_NEEDLES):
        return 200, fixture_for(path)
    if path.startswith("/api/profile") and method == "POST" and scenario == "ok":
        if '"plant_count":7777' in body.replace(" ", ""):
            return 422, {"detail": "Number of plants looks too high (test message)."}
    if path.startswith("/api/contact") and scenario == "ok":
        return 200, {"ok": True}
    return fixtures_app.response_for(path, method, body, scenario)

def supabase_stub(anon: bool) -> str:
    return SUPABASE_STUB.replace("__SESSION__", "null" if anon else json.dumps(SESSION))