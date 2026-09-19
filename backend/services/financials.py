"""
financials.py — Deterministic financial calculation functions.

All arithmetic that touches money happens here — never in Gemini,
never in the frontend. Each function takes plain Python types and
returns plain Python types so they are trivially unit-testable.

Functions
---------
total_cost(activities)               -> float
cost_by_activity_type(activities)    -> dict[str, float]
revenue(sale_qty, sale_price)        -> float
profit_or_loss(revenue, total_cost)  -> float
break_even_price(total_cost, expected_yield_kg) -> float | None
"""

from __future__ import annotations
from typing import Optional


def total_cost(activities: list[dict]) -> float:
    """Sum the cost field of all activity records.

    Each record must have a numeric 'cost' key.
    Returns 0.0 for an empty list.
    """
    return sum(float(a["cost"]) for a in activities)


def cost_by_activity_type(activities: list[dict]) -> dict[str, float]:
    """Group activities by type and sum costs within each group.

    Returns a dict: { activity_type: total_cost }.
    """
    result: dict[str, float] = {}
    for a in activities:
        atype = a.get("activity_type", "Other")
        result[atype] = result.get(atype, 0.0) + float(a["cost"])
    return result


def revenue(sale_quantity_kg: float, sale_price_per_kg: float) -> float:
    """Return total revenue from a sale.

    revenue = sale_quantity_kg × sale_price_per_kg
    """
    if sale_quantity_kg < 0:
        raise ValueError("sale_quantity_kg must be >= 0")
    if sale_price_per_kg < 0:
        raise ValueError("sale_price_per_kg must be >= 0")
    return sale_quantity_kg * sale_price_per_kg


def profit_or_loss(total_revenue: float, total_expenses: float) -> float:
    """Return profit (positive) or loss (negative).

    profit_or_loss = revenue − total_cost
    """
    return total_revenue - total_expenses


def break_even_price(
    total_expenses: float,
    expected_yield_kg: Optional[float],
) -> Optional[float]:
    """Return the minimum price per kg needed to break even.

    break_even = total_cost / expected_yield_kg

    Returns None when:
      - expected_yield_kg is None (farmer did not set it)
      - expected_yield_kg is zero or negative (invalid)
      - total_expenses is zero (no data yet)

    Never returns ₹0 as a fake break-even.
    """
    if expected_yield_kg is None:
        return None
    if expected_yield_kg <= 0:
        return None
    if total_expenses <= 0:
        return None
    return total_expenses / expected_yield_kg
