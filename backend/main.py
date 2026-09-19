"""
main.py — FastAPI application entry point.

Load order matters:
  1. load_dotenv() must run before any service module is imported,
     because auth.py and planner.py read env vars at module level.
  2. Routers are registered after the app instance is created.
"""

from dotenv import load_dotenv

# Load .env before importing anything that reads os.environ at module level.
load_dotenv()

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import plan as plan_router_module
from routers import profile as profile_router_module
from routers import activities as activities_router_module
from routers import financial as financial_router_module
from routers import vendors as vendors_router_module

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(title="Guava Care API", version="2.0.0")

# ── CORS ─────────────────────────────────────────────────────────────────────
# Allow the production Netlify site and local dev origins.
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


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health")
def health() -> dict:
    """Render free-tier uptime check endpoint."""
    return {"status": "ok", "version": "2.0.0"}
