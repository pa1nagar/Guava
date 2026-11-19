"""
ranking.py - rank mandis by net price per kg. Pure.

Net Rs/kg = modal - transport - handling - modal x commission_pct / 100
  transport Rs/kg = (rs_per_quintal_per_km x km) / 100   (mode per_quintal_per_km)
                  = flat_rs_per_quintal / 100            (mode flat_per_quintal)
  handling  Rs/kg = handling_rs_per_quintal / 100

Every cost is entered by the farmer. With none entered, mandis are ranked by
gross modal price and costs_set is False so the UI can ask for the farmer's own
costs. Distances are straight-line (haversine) to the mandi's district centre
unless the farmer entered road km. Rows are quality-annotated; rejected rows
never count. Stale mandis are listed but not ranked.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date
from typing import Optional

from services.sell_smart import config as cfg
from services.sell_smart import locations
from services.sell_smart.quality import mandi_key, to_date, usable

MODE_PER_KM = "per_quintal_per_km"
MODE_FLAT = "flat_per_quintal"

DISTANCE_LABEL_STRAIGHT = "straight-line distance to the mandi district centre; road distance is longer"
DISTANCE_LABEL_ENTERED = "your entered road km"
DISTANCE_BASIS_STRAIGHT = "straight_line"
DISTANCE_BASIS_ENTERED = "entered_road_km"

FORMULA = {
    "template_key": "sell_formula_net",
    "text_en": "Net Rs/kg = modal price - transport - handling - (modal price x commission % / 100)",
    "transport_text_en": {
        MODE_PER_KM: "transport Rs/kg = (Rs per quintal per km x km) / 100",
        MODE_FLAT: "transport Rs/kg = flat Rs per quintal / 100",
    },
    "handling_text_en": "handling Rs/kg = handling Rs per quintal / 100",
}


def mandi_id(row: dict) -> str:
    """Stable id used for road_km_overrides: 'state|district|market'."""
    return "|".join(str(x or "") for x in mandi_key(row))


def _f(value) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def suggest_transport(harvest_rows: list[dict]) -> Optional[dict]:
    """Flat Rs/quintal from the farmer's logged sales (never auto-applied)."""
    cost = qty_kg = 0.0
    n = 0
    for h in harvest_rows or []:
        c, q = _f(h.get("transport_cost")), _f(h.get("sale_quantity_kg"))
        if c is None or q is None or c < 0 or q <= 0:
            continue
        cost += c
        qty_kg += q
        n += 1
    if n == 0:
        return None
    return {
        "mode": MODE_FLAT,
        "rs_per_quintal": cost / (qty_kg / cfg.QUINTAL_KG),
        "n_sales": n,
        "label": f"from {n} logged sale(s)",
    }


def compute_costs(settings: Optional[dict], km: Optional[float], modal_per_kg: float) -> dict:
    """Costs and net price for one mandi. net_per_kg is None when per-km transport
    is chosen but the distance is unknown."""
    s = settings or {}
    mode = s.get("transport_mode")
    tv = _f(s.get("transport_value"))
    handling_q = _f(s.get("handling_rs_per_quintal"))
    commission = _f(s.get("commission_pct"))
    costs_set = (mode in (MODE_PER_KM, MODE_FLAT) and tv is not None) or handling_q is not None or commission is not None

    transport = 0.0
    if mode == MODE_PER_KM and tv is not None:
        transport = None if km is None else tv * km / cfg.QUINTAL_KG
    elif mode == MODE_FLAT and tv is not None:
        transport = tv / cfg.QUINTAL_KG
    handling = (handling_q or 0.0) / cfg.QUINTAL_KG
    commission_kg = modal_per_kg * (commission or 0.0) / 100.0
    net = None if transport is None else modal_per_kg - transport - handling - commission_kg
    return {
        "costs_set": bool(costs_set),
        "transport_per_kg": transport,
        "handling_per_kg": handling,
        "commission_per_kg": commission_kg,
        "net_per_kg": net,
    }


def _substitution(modal: float, c: dict) -> Optional[str]:
    if c["net_per_kg"] is None:
        return None
    return (f"Rs {modal:.2f} - Rs {c['transport_per_kg']:.2f} - Rs {c['handling_per_kg']:.2f} "
            f"- Rs {c['commission_per_kg']:.2f} = Rs {c['net_per_kg']:.2f}")


def _latest_per_mandi(rows: list[dict]) -> dict[tuple, dict]:
    by_mandi: dict[tuple, dict[date, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        d = to_date(r.get("arrival_date"))
        if d is None or not usable(r):
            continue
        by_mandi[mandi_key(r)][d].append(r)
    out = {}
    for key, days in by_mandi.items():
        d = max(days)
        rs = days[d]
        mods = [float(r["modal_price"]) for r in rs]
        out[key] = {
            "trade_date": d,
            "modal_per_kg": statistics.median(mods) / cfg.QUINTAL_KG,
            "n_rows": len(rs),
            "varieties": sorted({(str(r.get("variety") or ""), str(r.get("grade") or "")) for r in rs}),
            "sample": rs[0],
        }
    return out


def rank_mandis(
    rows: list[dict],
    origin: Optional[tuple[float, float]],
    settings: Optional[dict],
    radius_km: float = cfg.DEFAULT_RADIUS_KM,
    today: Optional[date] = None,
) -> dict:
    """Rank mandis within radius_km of origin by net (or gross when no costs entered)."""
    today = today or date.today()
    settings = settings or {}
    overrides = settings.get("road_km_overrides") or {}
    latest = _latest_per_mandi(rows)

    entries: list[dict] = []
    for key, info in latest.items():
        sample = info["sample"]
        modal = info["modal_per_kg"]
        coords = locations.resolve_district(sample.get("state"), sample.get("district"))
        mid = mandi_id(sample)
        km = basis = label = None
        if origin is not None and coords is not None:
            km = locations.distance_km(origin, coords[:2])
            basis, label = DISTANCE_BASIS_STRAIGHT, DISTANCE_LABEL_STRAIGHT
        entered = _f(overrides.get(mid))
        if entered is not None and entered >= 0 and coords is not None:
            km, basis, label = entered, DISTANCE_BASIS_ENTERED, DISTANCE_LABEL_ENTERED
        c = compute_costs(settings, km, modal)
        stale = cfg.is_stale(info["trade_date"], today)
        entries.append({
            "id": mid, "state": sample.get("state"), "district": sample.get("district"),
            "market_name": sample.get("market_name"),
            "trade_date": info["trade_date"].isoformat(), "stale": stale,
            "gross_per_kg": modal, "n_rows": info["n_rows"],
            "varieties": [{"variety": v, "grade": g} for v, g in info["varieties"]],
            "location_known": coords is not None,
            "location_basis": coords[2] if coords else None,
            "distance_km": km, "distance_basis": basis, "distance_label": label,
            "transport_per_kg": c["transport_per_kg"] if c["net_per_kg"] is not None else None,
            "handling_per_kg": c["handling_per_kg"] if c["net_per_kg"] is not None else None,
            "commission_per_kg": c["commission_per_kg"] if c["net_per_kg"] is not None else None,
            "net_per_kg": c["net_per_kg"],
            "substitution": _substitution(modal, c),
            "rank": None,
        })
    costs_set = compute_costs(settings, None, 1.0)["costs_set"]
    result = {
        "status": "ok", "costs_set": costs_set, "radius_km": radius_km,
        "ranked_by": "net" if costs_set else "gross",
        "formula": FORMULA, "ranked": [], "unranked": [], "outside_radius": 0,
    }

    if origin is None:
        result["status"] = "no_origin"
        result["unranked"] = sorted(entries, key=lambda e: (-e["gross_per_kg"], str(e["market_name"])))
        return result

    eligible = []
    for e in entries:
        if e["stale"] or not e["location_known"] or e["distance_km"] is None:
            result["unranked"].append(e)
        elif e["distance_km"] > radius_km:
            result["outside_radius"] += 1
        elif costs_set and e["net_per_kg"] is None:
            result["unranked"].append(e)
        else:
            eligible.append(e)

    metric = "net_per_kg" if costs_set else "gross_per_kg"
    eligible.sort(key=lambda e: (-e[metric], str(e["market_name"])))
    for i, e in enumerate(eligible, 1):
        e["rank"] = i
    result["ranked"] = eligible
    result["unranked"].sort(key=lambda e: (-e["gross_per_kg"], str(e["market_name"])))
    return result
