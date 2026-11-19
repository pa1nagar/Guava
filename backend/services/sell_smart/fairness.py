"""
fairness.py - compare the farmer's logged sale with the market that day. Pure.

The market price is the median across mandis (within the radius) of each
mandi's median modal price on one saved date. The date is the sale date when
enough mandis have a price that day, otherwise the nearest saved date within
STALE_DAYS. Fewer than MIN_ROBUST_N mandis gives no comparison.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from services.sell_smart import config as cfg
from services.sell_smart import locations
from services.sell_smart.quality import mandi_key, to_date, usable


def _insufficient(reason: str, text: str, **extra) -> dict:
    return {"status": "insufficient", "reason": reason, "reason_text_en": text, **extra}


def compare(
    harvest: Optional[dict],
    price_rows: list[dict],
    origin: Optional[tuple[float, float]],
    radius_km: float = cfg.DEFAULT_RADIUS_KM,
    today: Optional[date] = None,
) -> dict:
    harvest = harvest or {}
    sale_date = to_date(harvest.get("sale_date"))
    price = harvest.get("sale_price_per_kg")
    qty = harvest.get("sale_quantity_kg")
    if sale_date is None or price is None:
        return _insufficient("no_sale", "No logged sale with a date and a price.")
    if origin is None:
        return _insufficient("no_origin", "Set your farm location to compare with nearby mandis.")

    # per date -> per mandi -> modal prices (Rs/kg) and labels
    per_date: dict[date, dict[tuple, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in price_rows:
        d = to_date(r.get("arrival_date"))
        if d is None or not usable(r):
            continue
        coords = locations.resolve_district(r.get("state"), r.get("district"))
        if coords is None or locations.distance_km(origin, coords[:2]) > radius_km:
            continue
        per_date[d][mandi_key(r)].append(r)

    best_count = max((len(m) for m in per_date.values()), default=0)
    candidates = [
        d for d, m in per_date.items()
        if len(m) >= cfg.FAIRNESS_MIN_MANDIS and abs((d - sale_date).days) <= cfg.STALE_DAYS
    ]
    if not candidates:
        return _insufficient(
            "not_enough_market_data",
            f"Not enough market data that day: need prices from {cfg.FAIRNESS_MIN_MANDIS} mandis "
            f"within {radius_km:g} km within {cfg.STALE_DAYS} days of your sale.",
            best_mandi_count=best_count,
        )
    chosen = min(candidates, key=lambda d: (abs((d - sale_date).days), d))
    mandis = per_date[chosen]
    mandi_prices = [
        statistics.median(float(r["modal_price"]) for r in rs) / cfg.QUINTAL_KG for rs in mandis.values()
    ]
    market = statistics.median(mandi_prices)
    gap = float(price) - market

    notes = []
    if harvest.get("market_type") and harvest["market_type"] != "mandi":
        notes.append({"key": "fairness_note_market_type",
                      "text_en": f"Your sale was '{harvest['market_type']}', not at a mandi, so it is not like-for-like with mandi prices."})
    grade = (harvest.get("grade") or "").strip()
    labels = {(str(r.get("variety") or ""), str(r.get("grade") or "")) for rs in mandis.values() for r in rs}
    if grade and {g.strip().lower() for _, g in labels} != {grade.lower()}:
        notes.append({"key": "fairness_note_grade",
                      "text_en": f"Mandi prices mix varieties and grades; your grade '{grade}' may differ."})
    elif not grade:
        notes.append({"key": "fairness_note_no_grade",
                      "text_en": "No grade was logged for your sale, so grade differences cannot be checked."})

    return {
        "status": "ok",
        "sale_date": sale_date.isoformat(),
        "price_date": chosen.isoformat(),
        "date_gap_days": (chosen - sale_date).days,
        "n_mandis": len(mandis),
        "radius_km": radius_km,
        "sale_price_per_kg": float(price),
        "market_median_per_kg": market,
        "gap_per_kg": gap,
        "gap_total_rs": gap * float(qty) if qty is not None else None,
        "sale_quantity_kg": float(qty) if qty is not None else None,
        "like_for_like": not notes,
        "notes": notes,
    }
