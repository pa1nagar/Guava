"""
db.py — Shared Supabase service-role client (singleton).

All routers import _get_db() rather than creating their own clients.
The client is initialised lazily on first call so that:
  1. Tests that mock DB calls do not need real credentials.
  2. Startup errors (missing env vars) surface as clear RuntimeError,
     not an obscure import-time crash.

Usage:
    from services.db import get_db

    _db = get_db()
    result = _db.table("farmers").select("*").execute()
"""

import os
import logging

from supabase import Client, create_client

logger = logging.getLogger(__name__)

_client: Client | None = None


def get_db() -> Client:
    """Return (and lazily initialise) the shared Supabase service-role client.

    Raises RuntimeError on first call if required env vars are missing.
    Subsequent calls return the cached client.
    """
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL", "").strip()
        key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()

        if not url:
            raise RuntimeError(
                "SUPABASE_URL environment variable is not set. "
                "Add it to your .env file."
            )
        if not key:
            raise RuntimeError(
                "SUPABASE_SERVICE_KEY environment variable is not set. "
                "Add it to your .env file."
            )

        _client = create_client(url, key)
        logger.info("Supabase client initialised (url=%s…)", url[:40])

    return _client
