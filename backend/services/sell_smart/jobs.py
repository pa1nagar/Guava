"""
jobs.py - post-ingestion work for Sell smart.

run_post_ingestion(repo, today):
  1. quality check: assess saved rows that have no quality record, or whose
     modal price changed since the stored last_modal (a late correction), and
     upsert market_price_quality;
  2. alerts: evaluate every active alert on the latest fresh, non-rejected
     price for its state / district / mandi, insert a notification when it
     fires, and store the new alert state.

It is idempotent (a rerun creates no duplicate notifications) and never
raises: failures are logged and reported in the returned summary, like
services.mandi_prices.run_ingestion.
"""
from __future__ import annotations

import json
import logging
import statistics
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from services.sell_smart import alerts as alerts_mod
from services.sell_smart import config as cfg
from services.sell_smart import quality
from services.sell_smart.quality import mandi_key, to_date, usable

logger = logging.getLogger(__name__)

# Two windows of the longest trend (30 days): enough rows for the cross-section
# check and for the alert price. Derived from cfg.TREND_WINDOWS, not a new number.
LOOKBACK_DAYS = 2 * max(cfg.TREND_WINDOWS)


def _same(a, b) -> bool:
    return str(a or "").strip().lower() == str(b or "").strip().lower()


def stored_to_annotation(record: dict) -> dict:
    return {"flags": list(record.get("flags") or []), "severity": record.get("severity") or "ok"}


def annotate_with_stored(rows: list[dict], stored: dict[str, dict]) -> list[dict]:
    """Annotate rows: stored quality record when present, else computed now."""
    computed = quality.annotate(rows)
    out = []
    for r, c in zip(rows, computed):
        rec = stored.get(r.get("id"))
        if rec is not None:
            out.append({**r, **stored_to_annotation(rec)})
        else:
            out.append(c)
    return out


def _check_quality(repo, rows: list[dict]) -> dict:
    ids = [r["id"] for r in rows if r.get("id")]
    stored = repo.get_quality(ids)

    def changed(r: dict) -> bool:
        rec = stored.get(r["id"])
        if rec is None:
            return True
        last = rec.get("last_modal")
        try:
            return last is None or abs(float(last) - float(r.get("modal_price"))) > 1e-9
        except (TypeError, ValueError):
            return True

    dirty_dates = {r.get("arrival_date") for r in rows if r.get("id") and changed(r)}
    if not dirty_dates:
        return {"assessed": 0, "revised": 0, "flagged": 0, "written": 0}

    batch = [r for r in rows if r.get("id") and r.get("arrival_date") in dirty_dates]
    previous = {i: rec.get("last_modal") for i, rec in stored.items()}
    assessed = quality.assess_rows(batch, previous)

    records = []
    revised = flagged = 0
    for r, a in zip(batch, assessed):
        old = stored.get(r["id"])
        flags = list(a["flags"])
        severity = a["severity"]
        revision_count = int((old or {}).get("revision_count") or 0)
        if old is not None and quality.REVISED in (old.get("flags") or []) and quality.REVISED not in flags:
            # keep the REVISED mark even though the new modal now equals last_modal
            flags.append(quality.REVISED)
            if severity == "ok":
                severity = "warn"
        if quality.REVISED in flags and (old is None or changed(r)):
            revision_count += 1
            revised += 1
        if flags:
            flagged += 1
        records.append({
            "price_id": r["id"],
            "flags": flags,
            "severity": severity,
            "last_modal": float(r["modal_price"]) if r.get("modal_price") is not None else None,
            "revision_count": revision_count,
        })
    written = repo.upsert_quality(records)
    return {"assessed": len(batch), "revised": revised, "flagged": flagged, "written": written}


def alert_price(rows: list[dict], alert: dict) -> Optional[tuple[float, date]]:
    """Latest usable price (Rs/kg) for the alert scope, and its trade date.

    Scope: state, plus district and market when the alert has them. Each
    matching mandi contributes its latest trade date's median modal; the alert
    price is the median across those mandis, dated by the newest of them.
    """
    per_mandi: dict[tuple, dict[date, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if not usable(r) or not _same(r.get("state"), alert.get("state")):
            continue
        if alert.get("district") and not _same(r.get("district"), alert["district"]):
            continue
        if alert.get("market_name") and not _same(r.get("market_name"), alert["market_name"]):
            continue
        d = to_date(r.get("arrival_date"))
        if d is None:
            continue
        per_mandi[mandi_key(r)][d].append(float(r["modal_price"]) / cfg.QUINTAL_KG)
    if not per_mandi:
        return None
    values, dates = [], []
    for days in per_mandi.values():
        d = max(days)
        values.append(statistics.median(days[d]))
        dates.append(d)
    return statistics.median(values), max(dates)


def _load_state(alert: dict) -> dict:
    raw = alert.get("last_state")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


def _check_alerts(repo, rows: list[dict], today: date) -> dict:
    out = {"checked": 0, "fired": 0, "skipped": 0, "errors": 0}
    for alert in repo.list_active_alerts_all():
        out["checked"] += 1
        try:
            found = alert_price(rows, alert)
            price, trade_date = found if found else (None, None)
            state = _load_state(alert)
            if alert.get("last_trigger_date") and not state.get("last_fired_date"):
                state["last_fired_date"] = str(alert["last_trigger_date"])[:10]
            result = alerts_mod.evaluate(
                {
                    "target_per_kg": alert.get("target_rs_per_kg"),
                    "direction": alert.get("direction") or alerts_mod.AT_OR_ABOVE,
                    "state": state,
                    "deleted_at": alert.get("deleted_at"),
                    "active": alert.get("is_active"),
                },
                price, trade_date, today,
            )
            if result["action"] == "fire":
                td = trade_date.isoformat()
                if not repo.has_notification(alert["id"], td):
                    repo.insert_notification(
                        alert["user_id"], "price_alert", alert["id"],
                        {
                            "trade_date": td,
                            "price_per_kg": price,
                            "target_per_kg": float(alert["target_rs_per_kg"]),
                            "direction": alert.get("direction") or alerts_mod.AT_OR_ABOVE,
                            "state": alert.get("state"),
                            "district": alert.get("district"),
                            "market_name": alert.get("market_name"),
                            "source": "Agmarknet / data.gov.in",
                            "message_key": "sell_notif_price_alert",
                        },
                    )
                out["fired"] += 1
            else:
                out["skipped"] += 1
            new_state = result["state"]
            if new_state != state:
                repo.set_alert_state(
                    alert["id"], json.dumps(new_state), new_state.get("last_fired_date")
                )
        except Exception as exc:  # one bad alert must not stop the others
            logger.error("Sell smart alert %s failed: %s", alert.get("id"), exc)
            out["errors"] += 1
    return out


def run_post_ingestion(repo, today: Optional[date] = None) -> dict:
    """Quality check then alert check. Never raises; returns a summary dict."""
    today = today or date.today()
    summary: dict = {"status": "ok", "rows": 0, "quality": None, "alerts": None}
    try:
        rows = repo.get_price_rows(since=today - timedelta(days=LOOKBACK_DAYS))
    except Exception as exc:
        logger.error("Sell smart job could not read prices: %s", exc)
        summary.update(status="read_failed")
        return summary
    summary["rows"] = len(rows)
    if not rows:
        logger.warning("Sell smart job: no saved guava prices in the last %d days.", LOOKBACK_DAYS)
        summary["status"] = "empty"
        return summary

    try:
        summary["quality"] = _check_quality(repo, rows)
        stored = repo.get_quality([r["id"] for r in rows if r.get("id")])
        annotated = annotate_with_stored(rows, stored)
    except Exception as exc:
        logger.error("Sell smart quality check failed: %s", exc)
        summary.update(status="quality_failed")
        annotated = quality.annotate(rows)

    try:
        summary["alerts"] = _check_alerts(repo, annotated, today)
    except Exception as exc:
        logger.error("Sell smart alert check failed: %s", exc)
        summary["status"] = "alerts_failed" if summary["status"] == "ok" else summary["status"]
    return summary
