"""
main.py â€” FastAPI application entry point.

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

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from routers import plan as plan_router_module
from routers import profile as profile_router_module
from routers import activities as activities_router_module
from routers import financial as financial_router_module
from routers import vendors as vendors_router_module
from routers import insights as insights_router_module
from routers import content as content_router_module
from routers import contact as contact_router_module
from routers import farms as farms_router_module
from routers import tasks as tasks_router_module
from routers import observations as observations_router_module
from routers import inventory as inventory_router_module
from routers import calculators as calculators_router_module
from routers import ai as ai_router_module
from services.rate_limiter import RateLimiter, check_rate_limit, _extract_ip

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Smart Farmer API", version="2.0.0")

# â”€â”€ CORS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

# â”€â”€ Rate-limit middleware â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Applies per-IP sliding-window limits before any router runs.
# Category routing is path-prefix based; individual routers use
# Depends(RateLimiter(...)) for finer-grained control.
# Requirements: 3.8, 3.9

_LOGIN_PREFIXES = ("/api/auth/",)
_FILE_UPLOAD_SUFFIXES = ("/photos", "/label", "/photo")

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next) -> Response:
    """Enforce per-IP rate limits for login and file-upload paths.

    Other categories (ai_query, contact_form) are enforced via
    Depends(RateLimiter(...)) in the respective routers, which gives
    cleaner per-endpoint control and easier testing.

    Any rate-limit breach raises HTTPException(429) with a Retry-After header.
    We convert it to a plain JSON response here so middleware exceptions are
    handled consistently.
    """
    from fastapi import HTTPException
    from fastapi.responses import JSONResponse

    client_ip = _extract_ip(request)
    path = request.url.path

    try:
        # Login paths
        if any(path.startswith(prefix) for prefix in _LOGIN_PREFIXES):
            check_rate_limit("login", client_ip)

        # File upload paths
        elif (
            request.method == "POST"
            and any(path.endswith(suffix) for suffix in _FILE_UPLOAD_SUFFIXES)
        ):
            check_rate_limit("file_upload", client_ip)

    except HTTPException as exc:
        retry_after = exc.headers.get("Retry-After", "900") if exc.headers else "900"
        return JSONResponse(
            status_code=429,
            content={"detail": exc.detail},
            headers={"Retry-After": retry_after},
        )

    return await call_next(request)


# â”€â”€ Routers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
app.include_router(profile_router_module.router, prefix="/api")
app.include_router(plan_router_module.router, prefix="/api")
app.include_router(activities_router_module.router, prefix="/api")
app.include_router(financial_router_module.router, prefix="/api")
app.include_router(vendors_router_module.router, prefix="/api")
app.include_router(insights_router_module.router, prefix="/api")
app.include_router(content_router_module.router)  # prefix already set in router
app.include_router(contact_router_module.router, prefix="/api")
app.include_router(farms_router_module.router, prefix="/api")
app.include_router(tasks_router_module.router, prefix="/api")
app.include_router(observations_router_module.router, prefix="/api")
app.include_router(inventory_router_module.router, prefix="/api")
app.include_router(calculators_router_module.router, prefix="/api")
app.include_router(ai_router_module.router, prefix="/api")


# â”€â”€ Background scheduler (module-level so shutdown event can stop it) â”€â”€â”€â”€â”€â”€â”€â”€
_scheduler = BackgroundScheduler(timezone="Asia/Kolkata")


def _run_expiry_check() -> None:
    """Scheduled job: expire content records whose review_expiry date has passed.

    Runs daily at 00:05 Asia/Kolkata. Errors are logged but never propagate
    to the main thread â€” a scheduler failure must never take down the API.
    Requirement 1.4
    """
    try:
        from services.db import get_db
        from services.content_governance import check_and_expire_records

        db = get_db()
        count = check_and_expire_records(db)
        logger.info("Daily expiry check complete â€” %d record(s) expired.", count)
    except Exception as exc:  # noqa: BLE001
        logger.error("Daily expiry check failed: %s", exc)


# â”€â”€ Startup validation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.on_event("startup")
async def startup_validation() -> None:
    """Validate required environment variables on startup and start the scheduler.

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
            "STARTUP FAILED â€” missing required environment variables: %s. "
            "Set them in the Render dashboard (Environment tab) and redeploy.",
            missing,
        )
        raise RuntimeError(
            f"Missing required environment variables: {missing}. "
            "Set them before starting the server."
        )

    logger.info(
        "Startup OK â€” SUPABASE_URL=%sâ€¦ GEMINI_API_KEY=set",
        os.environ["SUPABASE_URL"][:40],
    )

    # Start the daily content-record expiry scheduler (Requirement 1.4).
    # Runs at 00:05 Asia/Kolkata every day. The scheduler is non-blocking;
    # it runs in a background thread and never delays request handling.
    _scheduler.add_job(
        _run_expiry_check,
        trigger="cron",
        hour=0,
        minute=5,
        id="daily_expiry_check",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("APScheduler started â€” daily expiry check at 00:05 Asia/Kolkata.")


@app.on_event("shutdown")
async def shutdown_scheduler() -> None:
    """Gracefully stop the APScheduler on server shutdown."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped.")


# â”€â”€ Health + readiness endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/health")
def health() -> dict:
    """Render uptime check â€” always returns 200 if the process is running."""
    return {"status": "ok", "version": "2.0.0"}


@app.get("/ready")
def ready() -> dict:
    """Readiness check â€” verifies the DB client can be initialised.

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

