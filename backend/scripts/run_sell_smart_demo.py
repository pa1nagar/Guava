"""
run_sell_smart_demo.py - serve the Sell smart API on SYNTHETIC demo data.

    cd backend
    set SELL_SMART_ALLOW_DEMO=1        (PowerShell: $env:SELL_SMART_ALLOW_DEMO = "1")
    python scripts/run_sell_smart_demo.py

Serves http://127.0.0.1:8001/api/sell-smart/... with the real router on an
in-memory DemoRepo. Then serve the frontend from the repo root with
`python -m http.server 5500` and open http://127.0.0.1:5500/sell-smart.html?demo=1

Refuses to start unless SELL_SMART_ALLOW_DEMO=1, and always refuses when the
RENDER environment variable exists. It talks to no database and needs no keys.
"""
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

PORT = 8001


def main() -> None:
    from services.sell_smart.demo import assert_demo_allowed

    assert_demo_allowed(os.environ)
    # services.auth reads SUPABASE_URL at import. The demo never verifies a token
    # (get_user_id is overridden), so a placeholder is enough.
    os.environ.setdefault("SUPABASE_URL", "https://demo.invalid")

    import uvicorn

    from services.sell_smart.demo import build_demo_app

    print("SELL SMART DEMO: synthetic data, local only, port", PORT)
    uvicorn.run(build_demo_app(), host="127.0.0.1", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
