"""
main.py — FastAPI application entry point.

Load order matters:
  1. load_dotenv() must run before any service module is imported,
     because auth.py and planner.py read env vars at module level.
  2. Routers are registered after the app instance is created.
  3. Startup event validates required env vars and DB connectivity.
"""

from dotenv import load_dotenv

# Load .env before importing anything that reads os.environ at module level.
load_dotenv()

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import plan as plan_router_module
from routers import profile as profile_router_module
from routers import activities as activities_router_module
from routers import financial as financial_router_module
from routers import vendors as vendors_router_module
from routers import insights as insights_router_module

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Guava Care API", version="2.0.0")

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://guavaa.netlify.app",
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
    ],
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(profile_router_module.router, prefix="/api")
app.include_router(plan_router_module.router, prefix="/api")
app.include_router(activities_router_module.router, prefix="/api")
app.include_router(financial_router_module.router, prefix="/api")
app.include_router(vendors_router_module.router, prefix="/api")
app.include_router(insights_router_module.router, prefix="/api")


# ── Startup validation ────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_validation() -> None:
    """Validate required environment variables on startup.

    Fails fast with a clear error message rather than letting the first
    request fail with a cryptic Supabase/Gemini exception.

    DB connectivity is intentionally NOT tested here (adds cold-start latency
    and Render's health check would fail). Env var presence is sufficient to
    confirm configuration is correct.
    """
    required = ["SUPABASE_URL", "SUPABASE_SERVICE_KEY", "GEMINI_API_KEY"]
    missing = [k for k in required if not os.environ.get(k, "").strip()]
    if missing:
        logger.critical(
            "STARTUP FAILED — missing required environment variables: %s. "
            "Set them in the Render dashboard (Environment tab) and redeploy.",
            missing,
        )
        raise RuntimeError(
            f"Missing required environment variables: {missing}. "
            "Set them before starting the server."
        )

    logger.info(
        "Startup OK — SUPABASE_URL=%s… GEMINI_API_KEY=set",
        os.environ["SUPABASE_URL"][:40],
    )


# ── Health + readiness endpoints ─────────────────────────────────────────────

@app.get("/health")
def health() -> dict:
    """Render uptime check — always returns 200 if the process is running."""
    return {"status": "ok", "version": "2.0.0"}


@app.get("/ready")
def ready() -> dict:
    """Readiness check — verifies the DB client can be initialised.

    Returns 200 if ready, 503 if the DB client cannot be created
    (missing/invalid credentials). Use this for smoke-testing after deploy.
    """
    try:
        from services.db import get_db
        db = get_db()
        # Perform a minimal, cheap query to confirm credentials work.
        db.table("farmers").select("id").limit(1).execute()
        return {"status": "ready", "db": "ok"}
    except Exception as exc:
        logger.error("Readiness check failed: %s", exc)
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail=f"Database not ready: {type(exc).__name__}",
        )
