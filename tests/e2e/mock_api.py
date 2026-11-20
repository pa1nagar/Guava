"""Mocked network for tests/e2e/browser_check.py. No real network is used.

Fixture values are fake test data, not real prices.
"""
import json
from pathlib import Path

FIX = Path(__file__).parent / "fixtures"

SUPABASE_STUB = """
const session = __SESSION__;
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
    ("/api/market-prices/guava/history", "mandi_history.json"),
    ("/api/market-prices/guava", "mandi_board.json"),
    ("/api/sell-smart", "sell_smart.json"),
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


def fixture_for(path: str):
    for needle, name in ROUTES:
        if needle in path:
            return json.loads((FIX / name).read_text(encoding="utf-8"))
    return {}


def supabase_stub(anon: bool) -> str:
    return SUPABASE_STUB.replace("__SESSION__", "null" if anon else json.dumps(SESSION))