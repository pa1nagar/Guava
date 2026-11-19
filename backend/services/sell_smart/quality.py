"""
quality.py - data-quality rules for saved mandi price rows. Pure: no DB, no network.

A row is a market_prices-shaped dict: id, state, district, market_name, variety,
grade, min_price, max_price, modal_price (Rs/quintal), arrival_date (ISO string
or date). Every rule and number is documented in config.THRESHOLDS.

Severity: "reject" rows are excluded from ranking and statistics, "warn" rows
stay visible, "ok" rows are clean. OUTLIER rows (warn) are additionally kept out
of the medians used for statistics (see stats.py).
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Optional

from services.sell_smart import config as cfg

ZERO_PRICE = "ZERO_PRICE"
ORDER_VIOLATION = "ORDER_VIOLATION"
UNIT_SUSPECT = "UNIT_SUSPECT"
OUTLIER = "OUTLIER"
DUPLICATE_VALUES = "DUPLICATE_VALUES"
REVISED = "REVISED"

REJECT_FLAGS = frozenset({ZERO_PRICE, ORDER_VIOLATION, UNIT_SUSPECT, DUPLICATE_VALUES})
WARN_FLAGS = frozenset({OUTLIER, REVISED})

_MAD_SCALE = 0.6745  # Iglewicz and Hoaglin constant


def to_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def mandi_key(row: dict) -> tuple:
    return (row.get("state"), row.get("district"), row.get("market_name"))


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _median_mad(values: list[float]) -> tuple[float, float]:
    med = statistics.median(values)
    mad = statistics.median([abs(v - med) for v in values])
    return med, mad


def _in_band(x: float, med: float, mad: float) -> bool:
    """True when x is inside the same-day band (modified z <= threshold).

    When MAD is 0 the band collapses to the median itself."""
    if mad == 0:
        return math.isclose(x, med, rel_tol=1e-9)
    return abs(_MAD_SCALE * (x - med) / mad) <= cfg.OUTLIER_MODIFIED_Z


def assess_rows(
    rows: list[dict], previous_by_id: Optional[dict] = None
) -> list[dict]:
    """Return one {id, flags, severity} per input row, in input order."""
    previous_by_id = previous_by_id or {}
    flags: list[list[str]] = [[] for _ in rows]

    # 1. Per-row logic rules.
    for i, r in enumerate(rows):
        modal = _num(r.get("modal_price"))
        if modal is None or modal <= 0:
            flags[i].append(ZERO_PRICE)
            continue
        lo, hi = _num(r.get("min_price")), _num(r.get("max_price"))
        if (lo is not None and lo > modal) or (hi is not None and hi < modal):
            flags[i].append(ORDER_VIOLATION)

    # 2. Same values under different labels in one mandi on one day: count once.
    seen: set[tuple] = set()
    for i, r in enumerate(rows):
        if flags[i]:
            continue
        key = (mandi_key(r), to_date(r.get("arrival_date")),
               _num(r.get("min_price")), _num(r.get("max_price")), _num(r.get("modal_price")))
        if key in seen:
            flags[i].append(DUPLICATE_VALUES)
        else:
            seen.add(key)

    # 3. Same-day cross-section across all states: unit slip, then outlier.
    groups: dict[Optional[date], list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        if not flags[i]:
            groups[to_date(r.get("arrival_date"))].append(i)
    for idxs in groups.values():
        if len(idxs) < cfg.MIN_ROBUST_N:
            continue
        vals = [float(rows[i]["modal_price"]) for i in idxs]
        med, mad = _median_mad(vals)
        for i in idxs:
            x = float(rows[i]["modal_price"])
            if _in_band(x, med, mad):
                continue
            slip = (x * cfg.UNIT_FACTOR, x / cfg.UNIT_FACTOR)
            if any(_in_band(alt, med, mad) for alt in slip):
                flags[i].append(UNIT_SUSPECT)
            elif mad != 0:
                flags[i].append(OUTLIER)

    # 4. Late correction of a stored price.
    for i, r in enumerate(rows):
        prev = _num(previous_by_id.get(r.get("id")))
        modal = _num(r.get("modal_price"))
        if prev is not None and modal is not None and not math.isclose(prev, modal, rel_tol=1e-9):
            flags[i].append(REVISED)

    out = []
    for r, f in zip(rows, flags):
        if any(x in REJECT_FLAGS for x in f):
            sev = "reject"
        elif f:
            sev = "warn"
        else:
            sev = "ok"
        out.append({"id": r.get("id"), "flags": f, "severity": sev})
    return out


def annotate(rows: list[dict], previous_by_id: Optional[dict] = None) -> list[dict]:
    """Copies of rows with 'flags' and 'severity' added."""
    return [{**r, "flags": a["flags"], "severity": a["severity"]}
            for r, a in zip(rows, assess_rows(rows, previous_by_id))]


def usable(row: dict) -> bool:
    """Not rejected and has a positive modal price (ranking, fairness)."""
    m = _num(row.get("modal_price"))
    return row.get("severity", "ok") != "reject" and m is not None and m > 0


def usable_for_stats(row: dict) -> bool:
    """usable() and not flagged OUTLIER (statistics medians)."""
    return usable(row) and OUTLIER not in (row.get("flags") or ())


def summarise_quality(rows: list[dict], today: Optional[date] = None) -> dict:
    """Summary of annotated rows: coverage, flags and a confidence label."""
    today = today or date.today()
    total = len(rows)
    ok_rows = [r for r in rows if usable(r)]
    dates = [d for d in (to_date(r.get("arrival_date")) for r in ok_rows) if d]
    last = max(dates) if dates else None
    fresh = last is not None and not cfg.is_stale(last, today)
    fresh_rows = [r for r in ok_rows if (d := to_date(r.get("arrival_date"))) and not cfg.is_stale(d, today)]
    n_mandis = len({mandi_key(r) for r in fresh_rows})
    days_saved = len(set(dates))

    counts: dict[str, int] = defaultdict(int)
    for r in rows:
        for f in r.get("flags") or ():
            counts[f] += 1
    rejected = sum(1 for r in rows if r.get("severity") == "reject")
    warned = sum(1 for r in rows if r.get("severity") == "warn")
    fresh_flagged = sum(1 for r in fresh_rows if r.get("severity") == "warn") + sum(
        1 for r in rows
        if r.get("severity") == "reject" and (d := to_date(r.get("arrival_date"))) and not cfg.is_stale(d, today)
    )

    if not fresh or n_mandis < cfg.MIN_ROBUST_N:
        confidence = "Low"
    elif days_saved >= 2 * cfg.MIN_TREND_DAYS and fresh_flagged == 0:
        confidence = "High"
    else:
        confidence = "Medium"

    return {
        "total_rows": total,
        "n_mandis": n_mandis,
        "last_updated": last.isoformat() if last else None,
        "days_saved": days_saved,
        "fresh": fresh,
        "flag_counts": dict(counts),
        "rejected": rejected,
        "warned": warned,
        "confidence": confidence,
    }
