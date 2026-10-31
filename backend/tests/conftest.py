"""
conftest.py — Pytest configuration shared across all test modules.

Loads .env and sets dummy fallback env vars BEFORE any test module imports
services or routers. This is necessary because services/auth.py reads
SUPABASE_URL at import time and would raise RuntimeError without it.
"""

import os
from pathlib import Path

# Try to load the real .env file if it exists (for tests that need real values).
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_file)
    except ImportError:
        pass

# Set placeholder env vars for any that are still unset.
# These values are never used in tests that mock get_db / get_user_id;
# they just prevent the import-time RuntimeError in services/auth.py.
os.environ.setdefault("SUPABASE_URL", "https://test-project.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
