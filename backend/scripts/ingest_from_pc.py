"""
ingest_from_pc.py - Fetch today's guava mandi prices and save them to Supabase.

Why this exists: api.data.gov.in refuses connections from Render's servers
(Connection refused, Nov 2026), but answers from an Indian home connection.
Until an India-hosted fetcher replaces it, Windows Task Scheduler runs this
script on the owner's PC twice a day (07:30 and 19:30 IST).

Reads DATA_GOV_IN_API_KEY, SUPABASE_URL and SUPABASE_SERVICE_KEY from
backend/.env. Never prints secrets. Appends one line per run to
backend/logs/ingest_from_pc.log. Exit code 0 on success, 1 otherwise.

Run by hand:  python backend/scripts/ingest_from_pc.py
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND / ".env")

from services.mandi_prices import run_ingestion  # noqa: E402

LOG_DIR = BACKEND / "logs"


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    summary = run_ingestion()
    LOG_DIR.mkdir(exist_ok=True)
    line = json.dumps({"at": datetime.now().isoformat(timespec="seconds"), **summary})
    with open(LOG_DIR / "ingest_from_pc.log", "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    print(line)
    return 0 if summary.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
