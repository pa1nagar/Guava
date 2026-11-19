"""
stats.py - trend, volatility and seasonal statistics from saved prices. Pure.

Input rows are quality-annotated market_prices rows (see quality.annotate); rows
that are rejected or flagged OUTLIER are left out. Prices are Rs/kg (modal
Rs/quintal / QUINTAL_KG, unrounded). Nothing here forecasts. Every function
returns status "ok" or "insufficient" and, when insufficient, says what is
missing in `needs` (plain English) plus `needs_key` / `needs_params` for i18n.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from services.sell_smart import config as cfg
from services.sell_smart.quality import mandi_key, to_date, usable_for_stats


def daily_series(rows: list[dict]) -> list[dict]:
    """One point per trade date: median modal (Rs/kg) of usable rows that day."""
    by_day: dict[date, list[float]] = defaultdict(list)
    mandis: dict[date, set] = defaultdict(set)
    for r in rows:
        d = to_date(r.get("arrival_date"))
        if d is None or not usable_for_stats(r):
            continue
        by_day[d].append(float(r["modal_price"]) / cfg.QUINTAL_KG)
        mandis[d].add(mandi_key(r))
    return [
        {"date": d, "value": statistics.median(v), "n_rows": len(v), "n_mandis": len(mandis[d])}
        for d, v in sorted(by_day.items())
    ]


def district_series(rows: list[dict]) -> list[dict]:
    """daily_series per (state, district), sorted by name."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r.get("state"), r.get("district"))].append(r)
    return [
        {"state": s, "district": d, "series": daily_series(rs)}
        for (s, d), rs in sorted(groups.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1])))
    ]


def _insufficient(base: dict, text: str, key: str, params: dict) -> dict:
    return {**base, "status": "insufficient", "needs": text, "needs_key": key, "needs_params": params}


def _days_saved(series: list[dict]) -> int:
    return len(series)


def window_change(series: list[dict], n: int, today: Optional[date] = None) -> dict:
    """Median of the latest n-day window vs the previous n-day window."""
    today = today or date.today()
    latest_lo = today - timedelta(days=n - 1)
    prev_lo = today - timedelta(days=2 * n - 1)
    latest = [p["value"] for p in series if latest_lo <= p["date"] <= today]
    prev = [p["value"] for p in series if prev_lo <= p["date"] < latest_lo]
    base = {
        "window_days": n,
        "days_saved": _days_saved(series),
        "observations": {"latest": len(latest), "previous": len(prev)},
        "median_latest": None, "median_previous": None,
        "change_rs_per_kg": None, "change_pct": None,
        "needs": None, "needs_key": None, "needs_params": None,
    }
    need = cfg.MIN_ROBUST_N
    if len(latest) >= need and len(prev) >= need:
        m1, m0 = statistics.median(latest), statistics.median(prev)
        return {**base, "status": "ok", "median_latest": m1, "median_previous": m0,
                "change_rs_per_kg": m1 - m0,
                "change_pct": (m1 - m0) / m0 * 100 if m0 else None}

    first = series[0]["date"] if series else None
    span = (today - first).days + 1 if first else 0
    more = max(0, n + need - span, need - len(latest))
    if more == 0:
        # The calendar span is long enough, so missing days inside the windows cause it.
        return _insufficient(
            base,
            f"Not enough saved days inside the two {n}-day windows "
            f"(need {need} in each, have {len(latest)} and {len(prev)}). Missing days cannot be added later.",
            "needs_gaps", {"window": n, "need": need, "latest": len(latest), "previous": len(prev)},
        )
    return _insufficient(
        base,
        f"About {more} more saved day(s) are needed for a {n}-day change "
        f"(need {need} saved days in each of two {n}-day windows).",
        "needs_more_days", {"window": n, "more_days": more, "need": need},
    )


def window_changes(series: list[dict], today: Optional[date] = None) -> list[dict]:
    return [window_change(series, n, today) for n in cfg.TREND_WINDOWS]


def volatility(series: list[dict], today: Optional[date] = None) -> dict:
    """Relative MAD (MAD / median) of daily prices over the last 30 days."""
    today = today or date.today()
    lo = today - timedelta(days=cfg.VOLATILITY_WINDOW_DAYS - 1)
    vals = [p["value"] for p in series if lo <= p["date"] <= today]
    base = {"window_days": cfg.VOLATILITY_WINDOW_DAYS, "observations": len(vals),
            "days_saved": _days_saved(series), "median": None, "mad": None,
            "relative_mad": None, "relative_mad_pct": None,
            "needs": None, "needs_key": None, "needs_params": None}
    if len(vals) < cfg.MIN_TREND_DAYS:
        more = cfg.MIN_TREND_DAYS - len(vals)
        return _insufficient(
            base,
            f"About {more} more saved day(s) are needed to describe how much prices move "
            f"(need {cfg.MIN_TREND_DAYS} saved days in the last {cfg.VOLATILITY_WINDOW_DAYS}).",
            "needs_more_days_volatility", {"more_days": more, "need": cfg.MIN_TREND_DAYS},
        )
    med = statistics.median(vals)
    mad = statistics.median([abs(v - med) for v in vals])
    rel = mad / med if med else None
    return {**base, "status": "ok", "median": med, "mad": mad, "relative_mad": rel,
            "relative_mad_pct": rel * 100 if rel is not None else None}


def seasonal_view(series: list[dict], today: Optional[date] = None) -> dict:
    """Median price by calendar month, only with 2+ years of saved data."""
    base = {"days_saved": _days_saved(series), "first_date": None,
            "last_date": None, "earliest_meaningful_date": None, "months": [],
            "needs": None, "needs_key": None, "needs_params": None}
    if not series:
        return _insufficient(base, "No saved prices yet.", "needs_no_data", {})
    first, last = series[0]["date"], series[-1]["date"]
    earliest = first + timedelta(days=cfg.SEASONAL_MIN_SPAN_DAYS)
    base.update(first_date=first.isoformat(), last_date=last.isoformat(),
                earliest_meaningful_date=earliest.isoformat())
    if (last - first).days < cfg.SEASONAL_MIN_SPAN_DAYS:
        return _insufficient(
            base,
            f"A seasonal view needs {cfg.SEASONAL_MIN_YEARS} years of saved prices. "
            f"Saved so far: {base['days_saved']} day(s) since {first.isoformat()}. "
            f"Earliest date it can be shown: {earliest.isoformat()}.",
            "needs_seasonal_span",
            {"days_saved": base["days_saved"], "first_date": first.isoformat(),
             "earliest": earliest.isoformat()},
        )
    per: dict[int, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    for p in series:
        per[p["date"].month][p["date"].year].append(p["value"])
    months = []
    for month in range(1, 13):
        good = {y: v for y, v in per[month].items() if len(v) >= cfg.MIN_ROBUST_N}
        if len(good) >= cfg.SEASONAL_MIN_YEARS:
            allv = [x for v in good.values() for x in v]
            months.append({"month": month, "median": statistics.median(allv),
                           "years": sorted(good), "observations": len(allv),
                           "year_medians": {y: statistics.median(v) for y, v in sorted(good.items())}})
    if not months:
        return _insufficient(
            base,
            f"The saved span is long enough, but no calendar month has {cfg.MIN_ROBUST_N} saved days "
            f"in each of {cfg.SEASONAL_MIN_YEARS} different years yet.",
            "needs_seasonal_months", {"need": cfg.MIN_ROBUST_N, "years": cfg.SEASONAL_MIN_YEARS},
        )
    return {**base, "status": "ok", "months": months}
