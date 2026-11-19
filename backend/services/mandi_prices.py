"""
mandi_prices.py — Guava mandi price ingestion and lookup (Agmarknet / data.gov.in).

Source
------
Dataset  : "Current daily price of various commodities from various markets (Mandi)"
Publisher: Ministry of Agriculture & Farmers Welfare via the Open Government Data
           Platform India (data.gov.in). Government Open Data License - India;
           attribution is shown to farmers as "Source: Agmarknet / data.gov.in".
Resource : 9ef84268-d588-465a-a308-a864a43d0070
Endpoint : https://api.data.gov.in/resource/<resource id>
           query: api-key, format=json, limit, offset, filters[commodity]=Guava
Fields   : state, district, market, commodity, variety, grade, arrival_date
           (DD/MM/YYYY), min_price, max_price, modal_price. Prices are Rs per
           quintal (100 kg), delivered as strings.

The feed keeps only recent days, so history exists only because this module
saves each day's records. Everything here is deterministic: no estimates, no
model output. If the feed fails, changes shape or is empty, ingestion logs the
reason and returns a summary; it never raises into the scheduler or the API.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Optional

import httpx

logger = logging.getLogger(__name__)

RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"
API_URL = f"https://api.data.gov.in/resource/{RESOURCE_ID}"
SOURCE_NAME = "Agmarknet / data.gov.in"
COMMODITY_FEED_NAME = "Guava"      # value of the feed's commodity field
COMMODITY = "guava"                # value stored in market_prices.commodity
UNIT = "Rs/Quintal"
QUINTAL_KG = 100.0

PAGE_LIMIT = 100                   # 500-row pages timed out on the live server (Nov 2026)
MAX_PAGES = 100                    # hard stop: 10,000 records for one commodity
HTTP_TIMEOUT_S = 60.0
FETCH_ATTEMPTS = 3                 # per page; the feed is often slow or briefly down
RETRY_BACKOFF_S = 3.0
RETRY_STATUSES = (502, 503, 504)
# data.gov.in stalls requests that carry the default python-httpx User-Agent
# (verified 19 Nov 2026: default UA timed out, any other UA answered in ~1 s).
USER_AGENT = "SmartFarmerGuava/1.0 (mandi price sync)"
UPSERT_CHUNK = 200
MIN_TREND_DAYS = 7                 # distinct saved days needed before showing a trend
# Single source of truth for "old price". routers/financial.py uses it, and the
# price endpoints send it to the UI as stale_after_days (the UI never hard-codes it).
STALE_DAYS = 7

# Columns that identify one price row. Must match the unique index in schema.sql.
CONFLICT_COLUMNS = (
    "source_name,state,district,market_name,commodity,variety,grade,arrival_date"
)

_REQUIRED_FIELDS = ("state", "market", "arrival_date", "modal_price")


class MandiFetchError(Exception):
    """Raised when the data.gov.in call fails or returns an unusable payload."""


# ── Parsing ───────────────────────────────────────────────────────────────────

def _norm_key(key: Any) -> str:
    return str(key).strip().lower().replace(" ", "_")


def _parse_price(value: Any) -> Optional[float]:
    """Return a non-negative float, or None for blank / non-numeric / negative."""
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text.upper() in {"NA", "N/A", "NULL", "-"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if number != number or number < 0:  # NaN or negative
        return None
    return number


def _parse_date(value: Any) -> Optional[date]:
    """Parse the feed's DD/MM/YYYY (also accepts ISO YYYY-MM-DD)."""
    if value is None:
        return None
    text = str(value).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_record(raw: dict, fetched_at: Optional[datetime] = None) -> Optional[dict]:
    """Convert one feed record into a market_prices row, or None if unusable.

    Returns None (and logs at debug level) when the record is not Guava, is
    missing a required field, or has an unreadable date or modal price. Field
    names are matched case-insensitively so a casing change in the feed does
    not break ingestion.
    """
    if not isinstance(raw, dict):
        return None
    rec = {_norm_key(k): v for k, v in raw.items()}

    commodity = str(rec.get("commodity", "")).strip().lower()
    if commodity != COMMODITY:
        return None

    for field in _REQUIRED_FIELDS:
        if rec.get(field) in (None, ""):
            logger.debug("Skipping record without %s: %r", field, raw)
            return None

    trade_date = _parse_date(rec["arrival_date"])
    modal = _parse_price(rec["modal_price"])
    if trade_date is None or modal is None:
        logger.debug("Skipping record with bad date/modal price: %r", raw)
        return None

    fetched = fetched_at or datetime.now(timezone.utc)
    return {
        "source_name": SOURCE_NAME,
        "state": str(rec["state"]).strip(),
        "district": str(rec.get("district") or "").strip(),
        "market_name": str(rec["market"]).strip(),
        "commodity": COMMODITY,
        "variety": str(rec.get("variety") or "").strip(),
        "grade": str(rec.get("grade") or "").strip(),
        "unit": UNIT,
        "min_price": _parse_price(rec.get("min_price")),
        "max_price": _parse_price(rec.get("max_price")),
        "modal_price": modal,
        "price": modal,  # legacy NOT NULL column read by financial.py
        "arrival_date": trade_date.isoformat(),
        "observed_at": f"{trade_date.isoformat()}T00:00:00+05:30",
        "fetched_at": fetched.isoformat(),
    }


def parse_records(
    records: Iterable[dict], fetched_at: Optional[datetime] = None
) -> tuple[list[dict], int]:
    """Parse and de-duplicate a feed page set.

    Returns (rows, skipped). Rows sharing the same conflict key within one batch
    are collapsed (last one wins) because Postgres rejects an upsert that touches
    the same row twice.
    """
    keyed: dict[tuple, dict] = {}
    skipped = 0
    for raw in records:
        row = parse_record(raw, fetched_at)
        if row is None:
            skipped += 1
            continue
        key = tuple(row[c] for c in CONFLICT_COLUMNS.split(","))
        keyed[key] = row
    return list(keyed.values()), skipped


# ── Fetch ─────────────────────────────────────────────────────────────────────

def _get_with_retry(http: httpx.Client, params: dict) -> httpx.Response:
    """GET one page, retrying timeouts, network errors and 502/503/504.

    data.gov.in is often slow or briefly unavailable. Other statuses (400, 403,
    500, ...) are returned at once so the caller reports them without retrying.
    """
    last_error = "no attempt made"
    for attempt in range(1, FETCH_ATTEMPTS + 1):
        try:
            resp = http.get(API_URL, params=params)
        except httpx.HTTPError as exc:
            last_error = f"request failed: {type(exc).__name__}"
        else:
            if resp.status_code not in RETRY_STATUSES:
                return resp
            last_error = f"HTTP {resp.status_code} from data.gov.in"
        if attempt < FETCH_ATTEMPTS:
            logger.warning("Mandi fetch attempt %d/%d failed (%s); retrying.",
                           attempt, FETCH_ATTEMPTS, last_error)
            time.sleep(RETRY_BACKOFF_S * attempt)
    raise MandiFetchError(f"{last_error} (after {FETCH_ATTEMPTS} attempts)")


def fetch_guava_records(
    api_key: str, client: Optional[httpx.Client] = None
) -> list[dict]:
    """Download every Guava record currently in the feed (paginated).

    Raises MandiFetchError on network errors, non-200 responses, invalid JSON
    or a payload without a "records" list.
    """
    own_client = client is None
    http = client or httpx.Client(
        timeout=HTTP_TIMEOUT_S, headers={"User-Agent": USER_AGENT}
    )
    records: list[dict] = []
    try:
        offset = 0
        for _page in range(MAX_PAGES):
            params = {
                "api-key": api_key,
                "format": "json",
                "limit": PAGE_LIMIT,
                "offset": offset,
                "filters[commodity]": COMMODITY_FEED_NAME,
            }
            resp = _get_with_retry(http, params)
            if resp.status_code == 400:
                raise MandiFetchError("HTTP 400 from data.gov.in (bad request parameters)")
            if resp.status_code == 403:
                raise MandiFetchError("HTTP 403 from data.gov.in (API key missing, invalid or not allowed)")
            if resp.status_code != 200:
                raise MandiFetchError(f"HTTP {resp.status_code} from data.gov.in")
            try:
                payload = resp.json()
            except ValueError as exc:
                raise MandiFetchError("response was not valid JSON") from exc
            batch = payload.get("records") if isinstance(payload, dict) else None
            if not isinstance(batch, list):
                raise MandiFetchError("response has no 'records' list (format changed?)")
            records.extend(r for r in batch if isinstance(r, dict))
            # The server may cap rows per call below our limit (the public sample
            # key returns 10), so page until an empty batch instead of a short one.
            if not batch:
                break
            offset += len(batch)
        else:
            logger.warning("Mandi fetch stopped at MAX_PAGES=%d; feed may be truncated.", MAX_PAGES)
    finally:
        if own_client:
            http.close()
    return records


# ── Store ─────────────────────────────────────────────────────────────────────

def upsert_prices(db: Any, rows: list[dict]) -> int:
    """Upsert rows into market_prices; re-running the same day never duplicates."""
    stored = 0
    for i in range(0, len(rows), UPSERT_CHUNK):
        chunk = rows[i : i + UPSERT_CHUNK]
        db.table("market_prices").upsert(chunk, on_conflict=CONFLICT_COLUMNS).execute()
        stored += len(chunk)
    return stored


def run_ingestion(
    db: Any = None,
    client: Optional[httpx.Client] = None,
    api_key: Optional[str] = None,
) -> dict:
    """Fetch Guava prices and save them. Never raises; returns a summary dict.

    status is one of: ok, empty, no_api_key, fetch_failed, unusable, store_failed.
    """
    key = (api_key if api_key is not None else os.environ.get("DATA_GOV_IN_API_KEY", "")).strip()
    summary = {"status": "ok", "fetched": 0, "parsed": 0, "skipped": 0, "upserted": 0}
    if not key:
        logger.warning("DATA_GOV_IN_API_KEY is not set; mandi price ingestion skipped.")
        summary["status"] = "no_api_key"
        return summary

    try:
        records = fetch_guava_records(key, client)
    except MandiFetchError as exc:
        logger.error("Mandi price fetch failed: %s", exc)
        summary.update(status="fetch_failed", error=str(exc))
        return summary
    summary["fetched"] = len(records)

    if not records:
        logger.warning("Mandi feed returned no Guava records today; nothing stored.")
        summary["status"] = "empty"
        return summary

    rows, skipped = parse_records(records)
    summary.update(parsed=len(rows), skipped=skipped)
    if not rows:
        logger.error(
            "Mandi feed returned %d record(s) but none were usable; field names "
            "may have changed. First record keys: %s",
            len(records), sorted(records[0].keys()),
        )
        summary["status"] = "unusable"
        return summary
    if skipped:
        logger.warning("Skipped %d unusable mandi record(s) of %d.", skipped, len(records))

    try:
        if db is None:
            from services.db import get_db
            db = get_db()
        summary["upserted"] = upsert_prices(db, rows)
    except Exception as exc:  # noqa: BLE001
        logger.error("Saving mandi prices failed: %s", exc)
        summary.update(status="store_failed", error=type(exc).__name__)
        return summary

    logger.info("Mandi ingestion complete: %s", summary)
    return summary


# ── Presentation helpers (used by routers/prices.py and insights) ─────────────

def is_stale(trade_date: date, today: Optional[date] = None) -> bool:
    """True when the trade date is more than STALE_DAYS before today."""
    return (today or date.today()) - trade_date > timedelta(days=STALE_DAYS)


def per_kg(rs_per_quintal: Optional[float]) -> Optional[float]:
    """Convert Rs/quintal to Rs/kg (2 decimals). None stays None."""
    if rs_per_quintal is None:
        return None
    return round(float(rs_per_quintal) / QUINTAL_KG, 2)


def summarise_saved_prices(rows: list[dict], month: int) -> dict:
    """Summarise saved (arrival_date, modal_price) rows for one state.

    Returns the number of distinct saved days, first and last date, and how
    many saved days fall in the given calendar month with their average modal
    price (Rs/quintal; None when there are none).
    """
    dates: set[str] = set()
    month_dates: set[str] = set()
    month_modals: list[float] = []
    for r in rows:
        d = _parse_date(r.get("arrival_date"))
        if d is None:
            continue
        dates.add(d.isoformat())
        if d.month == month:
            month_dates.add(d.isoformat())
            if r.get("modal_price") is not None:
                month_modals.append(float(r["modal_price"]))
    ordered = sorted(dates)
    return {
        "distinct_days": len(ordered),
        "first_date": ordered[0] if ordered else None,
        "last_date": ordered[-1] if ordered else None,
        "harvest_month_days": len(month_dates),
        "harvest_month_avg_quintal": (
            sum(month_modals) / len(month_modals) if month_modals else None
        ),
    }
