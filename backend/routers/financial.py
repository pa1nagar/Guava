"""
financial.py — Financial summary and crop-cycle report endpoints.

GET  /api/farmers/me/financial-summary
POST /api/farmers/me/harvest             (write-once per crop cycle)
GET  /api/farmers/me/report
POST /api/farmers/me/expenses
GET  /api/farmers/me/expenses
"""

# ── Multi-tenant isolation ──────────────────────────────────────────────────
# Security: user_id is always derived from JWT via Depends(get_user_id).
# It is NEVER read from the request body. All DB queries filter by user_id
# or farmer_id IN (SELECT id FROM farmers WHERE user_id = <jwt.sub>).
# IDOR attempts return 404 (not 403) to avoid confirming resource existence.
# Requirements: 3.2, 3.3, 3.4

import csv
import io
import json
import logging
import pathlib
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from services.auth import get_user_id
from services.db import get_db
from services.stage import compute_crop_age_months
from services.financials import (
    total_cost,
    cost_by_activity_type,
    revenue,
    profit_or_loss,
    break_even_price,
    net_realisation,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Crop knowledge loaded once at module level.
_KNOWLEDGE_PATH = pathlib.Path(__file__).parent.parent / "data" / "crop_knowledge.json"
_knowledge_cache: dict | None = None


def _get_knowledge() -> dict:
    global _knowledge_cache
    if _knowledge_cache is None:
        _knowledge_cache = json.loads(_KNOWLEDGE_PATH.read_text(encoding="utf-8"))
    return _knowledge_cache


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_farmer(user_id: str) -> dict:
    db = get_db()
    try:
        result = (
            db.table("farmers")
            .select(
                "id, crop, plant_count, sowing_date, "
                "expected_yield_kg, vendor_recommendation_consent"
            )
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        logger.error("DB select failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")
    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return result.data


def _get_activities(farmer_id: str) -> list[dict]:
    db = get_db()
    try:
        result = (
            db.table("farm_activities")
            .select("*")
            .eq("farmer_id", farmer_id)
            .order("logged_date", desc=False)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.error("DB select activities failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")


def _get_harvest(farmer_id: str) -> Optional[dict]:
    db = get_db()
    try:
        result = (
            db.table("harvests")
            .select("*")
            .eq("farmer_id", farmer_id)
            .maybe_single()
            .execute()
        )
        return result.data if (result and result.data) else None
    except Exception as exc:
        logger.error("DB select harvest failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")


def _get_expenses(user_id: str) -> list[dict]:
    db = get_db()
    try:
        result = (
            db.table("expenses")
            .select("*")
            .eq("user_id", user_id)
            .order("expense_date", desc=False)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.error("DB select expenses failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")


# ── Double-counting prevention ────────────────────────────────────────────────
# If an activity has a linked_expense_id, it means an expense record already
# captures that cost.  To avoid counting it twice, we exclude those activities
# from the total_cost calculation when the linked expense record is present.
def _deduplicated_activities(activities: list[dict], expenses: list[dict]) -> list[dict]:
    """Return activities whose cost should count toward total_cost.

    Activities that have a linked_activity_id referenced by any expense record
    are excluded because the expense record is the canonical cost source.
    Requirements: 10.2
    """
    # Build the set of activity IDs that are already captured by an expense record.
    expense_linked_ids: set[str] = {
        e["linked_activity_id"]
        for e in expenses
        if e.get("linked_activity_id")
    }
    return [a for a in activities if a.get("id") not in expense_linked_ids]


# ── Expenses by category ─────────────────────────────────────────────────────
# Groups expense records by their category field and sums amounts.
# Used by the report endpoint to show total expenses by category.
# Requirement 16.2
def _expenses_by_category(expenses: list[dict]) -> dict[str, float]:
    """Return a dict mapping each expense category to its total amount."""
    result: dict[str, float] = {}
    for e in expenses:
        cat = e.get("category", "other")
        result[cat] = result.get(cat, 0.0) + float(e["amount"])
    return result


# ── Market prices ─────────────────────────────────────────────────────────────
# Fetches market price data points for the farmer's crop and labels any
# data point older than 7 days as stale.
# Requirement 9.6
def _get_market_prices(crop: str) -> list[dict]:
    """Return market price data points for the given crop, each labelled is_stale.

    A data point is stale when its observed_at timestamp is more than 7 days
    before the current UTC time.
    """
    db = get_db()
    try:
        result = (
            db.table("market_prices")
            .select(
                "id, source_name, market_name, commodity, grade, "
                "unit, price, observed_at, ingested_at"
            )
            .eq("commodity", crop.lower())
            .order("observed_at", desc=True)
            .execute()
        )
        prices = result.data or []
    except Exception as exc:
        logger.error("DB select market_prices failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)

    for p in prices:
        observed = p.get("observed_at")
        is_stale = True
        if observed:
            try:
                observed_str = str(observed)
                # Handle both "Z" suffix and explicit offsets.
                if observed_str.endswith("Z"):
                    observed_str = observed_str[:-1] + "+00:00"
                observed_dt = datetime.fromisoformat(observed_str)
                if observed_dt.tzinfo is None:
                    observed_dt = observed_dt.replace(tzinfo=timezone.utc)
                is_stale = observed_dt < seven_days_ago
            except (ValueError, TypeError):
                is_stale = True
        p["is_stale"] = is_stale

    return prices


# ── Models ────────────────────────────────────────────────────────────────────

class FinancialSummaryOut(BaseModel):
    total_cost: float
    cost_by_type: dict
    revenue: Optional[float]
    profit_or_loss: Optional[float]
    net_realisation: Optional[float]
    break_even_price_per_kg: Optional[float]
    has_harvest: bool
    currency: str = "INR"
    break_even_note: Optional[str] = None


# ── Harvest models ─────────────────────────────────────────────────────────

_MARKET_TYPES = {"farm_gate", "mandi", "retail"}
_PAYMENT_STATUSES = {"unpaid", "partial", "paid"}


class HarvestIn(BaseModel):
    # Core fields (v1 — still required)
    sale_quantity_kg: float = Field(gt=0)
    sale_price_per_kg: float = Field(ge=0)

    # Extended fields (v2 — all optional for backward compatibility)
    plot_id: Optional[str] = None
    grade: Optional[str] = None
    damaged_qty: Optional[float] = Field(default=None, ge=0)
    market_type: Optional[str] = None   # farm_gate | mandi | retail
    deductions: float = Field(default=0.0, ge=0)
    transport_cost: float = Field(default=0.0, ge=0)
    payment_status: Optional[str] = None  # unpaid | partial | paid

    def model_post_init(self, __context: object) -> None:  # noqa: ANN001
        if self.market_type and self.market_type not in _MARKET_TYPES:
            raise ValueError(
                f"market_type must be one of {sorted(_MARKET_TYPES)}"
            )
        if self.payment_status and self.payment_status not in _PAYMENT_STATUSES:
            raise ValueError(
                f"payment_status must be one of {sorted(_PAYMENT_STATUSES)}"
            )


class HarvestOut(BaseModel):
    id: str
    sale_quantity_kg: float
    sale_price_per_kg: float
    sale_date: str
    revenue: float
    gross_sales: float
    deductions: float
    net_realisation: float
    transport_cost: float
    payment_status: Optional[str]
    market_type: Optional[str]
    grade: Optional[str]


# ── Expense models ─────────────────────────────────────────────────────────

_EXPENSE_CATEGORIES = {
    "input", "labour", "irrigation_electricity", "machinery",
    "packaging", "transport", "rent_lease", "services", "other",
}


class ExpenseIn(BaseModel):
    category: str
    amount: float = Field(ge=0)
    expense_date: str                  # ISO date string
    description: Optional[str] = None
    farm_id: Optional[str] = None
    plot_id: Optional[str] = None
    linked_activity_id: Optional[str] = None

    def model_post_init(self, __context: object) -> None:  # noqa: ANN001
        if self.category not in _EXPENSE_CATEGORIES:
            raise ValueError(
                f"category must be one of {sorted(_EXPENSE_CATEGORIES)}"
            )
        # Validate date format.
        try:
            date.fromisoformat(self.expense_date)
        except ValueError as exc:
            raise ValueError("expense_date must be a valid ISO date (YYYY-MM-DD).") from exc


class ExpenseOut(BaseModel):
    id: str
    category: str
    amount: float
    expense_date: str
    description: Optional[str]
    farm_id: Optional[str]
    plot_id: Optional[str]
    linked_activity_id: Optional[str]
    created_at: str


# ── Report model ────────────────────────────────────────────────────────────

class ReportOut(BaseModel):
    crop: str
    sowing_date: str
    plant_count: int
    stage_coverage: List[str]
    stages_with_no_activity: List[str]
    total_cost: float
    cost_by_type: dict
    revenue: Optional[float]
    profit_or_loss: Optional[float]
    net_realisation: Optional[float]
    break_even_price_per_kg: Optional[float]
    break_even_note: Optional[str]
    has_harvest: bool
    # Harvest data split by actual vs scenario so the caller can label them.
    harvest_record: Optional[dict]   # actuals only (is_scenario=false)
    scenario_record: Optional[dict]  # scenarios (is_scenario=true)
    activity_history: List[dict]
    # Expenses grouped by category for the financial summary.
    # Requirement 16.2
    expenses_by_category: dict = {}
    # Market price data points with is_stale flag for stale (>7 days) points.
    # Requirement 9.6
    market_prices: List[dict] = []
    currency: str = "INR"


# ── GET /api/farmers/me/financial-summary ────────────────────────────────────

@router.get("/farmers/me/financial-summary", response_model=FinancialSummaryOut)
def financial_summary(user_id: str = Depends(get_user_id)) -> FinancialSummaryOut:
    farmer     = _get_farmer(user_id)
    activities = _get_activities(farmer["id"])
    harvest    = _get_harvest(farmer["id"])
    expenses   = _get_expenses(user_id)

    # Exclude activities already captured by an expense record to avoid double-counting.
    deduped = _deduplicated_activities(activities, expenses)
    tc      = total_cost(deduped)
    by_type = {k: round(v, 2) for k, v in cost_by_activity_type(deduped).items()}

    rev = pol = nr = bep = bep_note = None

    if harvest:
        rev = revenue(
            float(harvest["sale_quantity_kg"]),
            float(harvest["sale_price_per_kg"]),
        )
        pol = profit_or_loss(rev, tc)

        # net_realisation: prefer the stored column if available, else compute on-the-fly.
        stored_nr = harvest.get("net_realisation")
        if stored_nr is not None:
            nr = float(stored_nr)
        else:
            gross = float(harvest.get("gross_sales") or rev)
            deductions_val = float(harvest.get("deductions") or 0)
            nr = net_realisation(gross, deductions_val)

    bep = break_even_price(tc, farmer.get("expected_yield_kg"))
    if bep is None:
        if not farmer.get("expected_yield_kg"):
            bep_note = "Set an expected yield to calculate your break-even price."
        elif tc <= 0:
            bep_note = "No costs logged yet."

    return FinancialSummaryOut(
        total_cost=round(tc, 2),
        cost_by_type=by_type,
        revenue=round(rev, 2) if rev is not None else None,
        profit_or_loss=round(pol, 2) if pol is not None else None,
        net_realisation=round(nr, 2) if nr is not None else None,
        break_even_price_per_kg=round(bep, 2) if bep is not None else None,
        has_harvest=harvest is not None,
        break_even_note=bep_note,
    )


# ── POST /api/farmers/me/harvest ─────────────────────────────────────────────

@router.post("/farmers/me/harvest", response_model=HarvestOut)
def log_harvest(body: HarvestIn, user_id: str = Depends(get_user_id)) -> HarvestOut:
    """Write-once per crop cycle. Returns 409 if already submitted."""
    from services import stage as stage_service  # noqa: PLC0415

    db = get_db()
    farmer = _get_farmer(user_id)

    sowing_date = (
        date.fromisoformat(farmer["sowing_date"])
        if isinstance(farmer["sowing_date"], str)
        else farmer["sowing_date"]
    )

    try:
        sr = stage_service.get_stage(farmer["crop"], sowing_date)
    except (HTTPException, KeyError) as exc:
        raise HTTPException(status_code=422, detail="Cannot determine crop stage.") from exc

    if not sr.is_final_stage:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Harvest can only be logged at the harvest stage. "
                f"Current stage: {sr.stage['label']}."
            ),
        )

    if _get_harvest(farmer["id"]):
        raise HTTPException(
            status_code=409,
            detail="Harvest has already been recorded for this crop cycle.",
        )

    # Compute derived financial columns up front.
    gross = revenue(body.sale_quantity_kg, body.sale_price_per_kg)
    nr    = net_realisation(gross, body.deductions + body.transport_cost)

    payload: dict = {
        "farmer_id":          farmer["id"],
        "sale_quantity_kg":   body.sale_quantity_kg,
        "sale_price_per_kg":  body.sale_price_per_kg,
        "sale_date":          str(date.today()),
        "gross_sales":        round(gross, 6),
        "deductions":         body.deductions,
        "transport_cost":     body.transport_cost,
        "net_realisation":    round(nr, 6),
    }

    # Optional extended fields — only include when provided.
    if body.plot_id:
        payload["plot_id"] = body.plot_id
    if body.grade:
        payload["grade"] = body.grade
    if body.damaged_qty is not None:
        payload["damaged_qty"] = body.damaged_qty
    if body.market_type:
        payload["market_type"] = body.market_type
    if body.payment_status:
        payload["payment_status"] = body.payment_status

    try:
        result = db.table("harvests").insert(payload).execute()
    except Exception as exc:
        logger.error("DB insert harvest failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    row = result.data[0]
    row_rev = revenue(float(row["sale_quantity_kg"]), float(row["sale_price_per_kg"]))
    row_gross = float(row.get("gross_sales") or row_rev)
    row_ded   = float(row.get("deductions") or 0)
    row_tc    = float(row.get("transport_cost") or 0)
    row_nr_stored = row.get("net_realisation")
    row_nr = float(row_nr_stored) if row_nr_stored is not None else net_realisation(row_gross, row_ded)

    return HarvestOut(
        id=row["id"],
        sale_quantity_kg=float(row["sale_quantity_kg"]),
        sale_price_per_kg=float(row["sale_price_per_kg"]),
        sale_date=str(row["sale_date"]),
        revenue=round(row_rev, 2),
        gross_sales=round(row_gross, 2),
        deductions=round(row_ded + row_tc, 2),
        net_realisation=round(row_nr, 2),
        transport_cost=round(row_tc, 2),
        payment_status=row.get("payment_status"),
        market_type=row.get("market_type"),
        grade=row.get("grade"),
    )


# ── POST /api/farmers/me/expenses ────────────────────────────────────────────

@router.post("/farmers/me/expenses", response_model=ExpenseOut)
def log_expense(body: ExpenseIn, user_id: str = Depends(get_user_id)) -> ExpenseOut:
    """Record a standalone expense for the authenticated farmer."""
    db = get_db()

    # Validate plot ownership when plot_id is supplied.
    if body.plot_id:
        try:
            plot_result = (
                db.table("plots")
                .select("id")
                .eq("id", body.plot_id)
                .eq("user_id", user_id)
                .maybe_single()
                .execute()
            )
        except Exception as exc:
            logger.error("DB select plot failed: %s", exc)
            raise HTTPException(status_code=500, detail="Database error.")
        if not plot_result or not plot_result.data:
            raise HTTPException(status_code=404, detail="Plot not found.")

    # Validate activity ownership when linked_activity_id is supplied.
    if body.linked_activity_id:
        # Ownership confirmed via the farmer record (activities belong to farmer).
        farmer = _get_farmer(user_id)
        try:
            act_result = (
                db.table("farm_activities")
                .select("id")
                .eq("id", body.linked_activity_id)
                .eq("farmer_id", farmer["id"])
                .maybe_single()
                .execute()
            )
        except Exception as exc:
            logger.error("DB select activity failed: %s", exc)
            raise HTTPException(status_code=500, detail="Database error.")
        if not act_result or not act_result.data:
            raise HTTPException(status_code=404, detail="Activity not found.")

    payload: dict = {
        "user_id":      user_id,
        "category":     body.category,
        "amount":       body.amount,
        "expense_date": body.expense_date,
    }
    if body.description is not None:
        payload["description"] = body.description
    if body.farm_id is not None:
        payload["farm_id"] = body.farm_id
    if body.plot_id is not None:
        payload["plot_id"] = body.plot_id
    if body.linked_activity_id is not None:
        payload["linked_activity_id"] = body.linked_activity_id

    try:
        result = db.table("expenses").insert(payload).execute()
    except Exception as exc:
        logger.error("DB insert expense failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    row = result.data[0]
    return ExpenseOut(
        id=row["id"],
        category=row["category"],
        amount=float(row["amount"]),
        expense_date=str(row["expense_date"]),
        description=row.get("description"),
        farm_id=row.get("farm_id"),
        plot_id=row.get("plot_id"),
        linked_activity_id=row.get("linked_activity_id"),
        created_at=str(row["created_at"]),
    )


# ── GET /api/farmers/me/expenses ─────────────────────────────────────────────

@router.get("/farmers/me/expenses", response_model=List[ExpenseOut])
def list_expenses(user_id: str = Depends(get_user_id)) -> List[ExpenseOut]:
    """Return all expense records for the authenticated farmer."""
    expenses = _get_expenses(user_id)
    return [
        ExpenseOut(
            id=e["id"],
            category=e["category"],
            amount=float(e["amount"]),
            expense_date=str(e["expense_date"]),
            description=e.get("description"),
            farm_id=e.get("farm_id"),
            plot_id=e.get("plot_id"),
            linked_activity_id=e.get("linked_activity_id"),
            created_at=str(e["created_at"]),
        )
        for e in expenses
    ]


# ── GET /api/farmers/me/report ───────────────────────────────────────────────

@router.get("/farmers/me/report", response_model=ReportOut)
def crop_cycle_report(user_id: str = Depends(get_user_id)) -> ReportOut:
    from services import stage as stage_service  # noqa: PLC0415

    farmer     = _get_farmer(user_id)
    activities = _get_activities(farmer["id"])
    harvest    = _get_harvest(farmer["id"])
    expenses   = _get_expenses(user_id)

    all_stages = _get_knowledge()[farmer["crop"].lower()]["stages"]

    sowing_date = (
        date.fromisoformat(farmer["sowing_date"])
        if isinstance(farmer["sowing_date"], str)
        else farmer["sowing_date"]
    )

    current_month = 0
    try:
        sr = stage_service.get_stage(farmer["crop"], sowing_date)
        current_month = sr.months_elapsed
    except Exception:
        pass

    # Map activity dates to month offsets from sowing date.
    activity_months: set[int] = set()
    for a in activities:
        ld = a.get("logged_date", "")
        if ld:
            try:
                ld_date = date.fromisoformat(str(ld))
                activity_months.add(compute_crop_age_months(sowing_date, ld_date))
            except (ValueError, TypeError):
                pass

    stages_with_activity:    set[str]  = set()
    stages_without_activity: list[str] = []

    for s in all_stages:
        if s["month_start"] > current_month:
            break  # stages are ordered ascending — nothing beyond here is reached
        end = min(s["month_end"] if s["month_end"] != 9999 else current_month, current_month)
        has_log = any(s["month_start"] <= m <= end for m in activity_months)
        if has_log:
            stages_with_activity.add(s["stage_id"])
        else:
            stages_without_activity.append(s["label"])

    # Exclude double-counted activities.
    deduped = _deduplicated_activities(activities, expenses)
    tc      = total_cost(deduped)
    by_type = {k: round(v, 2) for k, v in cost_by_activity_type(deduped).items()}

    rev = pol = nr = bep = bep_note = None

    if harvest and not harvest.get("is_scenario", False):
        rev = revenue(
            float(harvest["sale_quantity_kg"]),
            float(harvest["sale_price_per_kg"]),
        )
        pol = profit_or_loss(rev, tc)

        stored_nr = harvest.get("net_realisation")
        if stored_nr is not None:
            nr = float(stored_nr)
        else:
            gross = float(harvest.get("gross_sales") or rev)
            deductions_val = float(harvest.get("deductions") or 0)
            nr = net_realisation(gross, deductions_val)

    bep = break_even_price(tc, farmer.get("expected_yield_kg"))
    if bep is None and not farmer.get("expected_yield_kg"):
        bep_note = "Set an expected yield to calculate your break-even price."

    history = [
        {
            "date":          str(a["logged_date"]),
            "activity_type": a["activity_type"],
            "quantity":      float(a["quantity"]),
            "unit":          a.get("unit"),
            "cost":          float(a["cost"]),
            "notes":         a.get("notes"),
        }
        for a in activities  # already sorted ascending by logged_date from query
    ]

    # Split harvest into actual vs scenario for distinct labeling (Req 10.4).
    harvest_record = None
    scenario_record = None
    if harvest:
        record = {
            "id":                 harvest["id"],
            "sale_quantity_kg":   float(harvest["sale_quantity_kg"]),
            "sale_price_per_kg":  float(harvest["sale_price_per_kg"]),
            "sale_date":          str(harvest["sale_date"]),
            "revenue":            round(
                revenue(float(harvest["sale_quantity_kg"]), float(harvest["sale_price_per_kg"])), 2
            ),
            "gross_sales":        round(float(harvest.get("gross_sales") or 0), 2),
            "deductions":         round(float(harvest.get("deductions") or 0), 2),
            "net_realisation":    round(float(harvest.get("net_realisation") or 0), 2),
            "transport_cost":     round(float(harvest.get("transport_cost") or 0), 2),
            "market_type":        harvest.get("market_type"),
            "grade":              harvest.get("grade"),
            "payment_status":     harvest.get("payment_status"),
            "record_type":        "scenario" if harvest.get("is_scenario") else "actual",
        }
        if harvest.get("is_scenario"):
            scenario_record = record
        else:
            harvest_record = record

    # Expenses by category for the financial summary (Req 16.2).
    exp_by_cat = {
        k: round(v, 2) for k, v in _expenses_by_category(expenses).items()
    }

    # Market price data points with is_stale label (Req 9.6).
    market_prices = _get_market_prices(farmer["crop"])

    return ReportOut(
        crop=farmer["crop"].title(),
        sowing_date=str(farmer["sowing_date"]),
        plant_count=farmer["plant_count"],
        stage_coverage=list(stages_with_activity),
        stages_with_no_activity=stages_without_activity,
        total_cost=round(tc, 2),
        cost_by_type=by_type,
        revenue=round(rev, 2) if rev is not None else None,
        profit_or_loss=round(pol, 2) if pol is not None else None,
        net_realisation=round(nr, 2) if nr is not None else None,
        break_even_price_per_kg=round(bep, 2) if bep is not None else None,
        break_even_note=bep_note,
        has_harvest=harvest is not None,
        harvest_record=harvest_record,
        scenario_record=scenario_record,
        activity_history=history,
        expenses_by_category=exp_by_cat,
        market_prices=market_prices,
    )


# ── GET /api/farmers/me/report/export ────────────────────────────────────────
# CSV export of farm activities and expenses.
#
# Security:
#   - All records are filtered by the JWT-derived user_id / farmer_id.
#   - An export_audit_log row is inserted BEFORE the CSV is streamed.
#   - GPS coordinates, secrets, and other farmers' data are never included.
#   - Only explicitly selected columns are written — no raw row dumps.
#
# Requirements: 16.3, 16.4

def _filter_by_date_range(
    records: list[dict], date_field: str, date_from: Optional[str], date_to: Optional[str]
) -> list[dict]:
    """Filter records by an inclusive date range on the given date field."""
    if not date_from and not date_to:
        return records
    out = []
    for r in records:
        val = str(r.get(date_field, ""))
        if date_from and val < date_from:
            continue
        if date_to and val > date_to:
            continue
        out.append(r)
    return out


@router.get("/farmers/me/report/export")
def export_report_csv(
    date_from: Optional[str] = Query(None, description="ISO date (YYYY-MM-DD) inclusive lower bound"),
    date_to: Optional[str] = Query(None, description="ISO date (YYYY-MM-DD) inclusive upper bound"),
    user_id: str = Depends(get_user_id),
) -> StreamingResponse:
    """Export farm activities and expenses as a CSV file.

    Every record included is verified server-side to belong to the requesting
    farmer (filtered by JWT-derived user_id / farmer_id). An audit-log row is
    inserted before streaming begins. GPS coordinates, tokens, and any data
    belonging to other farmers are excluded.

    Requirements: 16.3, 16.4
    """
    db = get_db()
    farmer = _get_farmer(user_id)

    # Fetch activities and expenses — already filtered by ownership.
    activities = _get_activities(farmer["id"])
    expenses   = _get_expenses(user_id)

    # Apply optional date-range filtering server-side.
    activities = _filter_by_date_range(activities, "logged_date", date_from, date_to)
    expenses   = _filter_by_date_range(expenses, "expense_date", date_from, date_to)

    record_count = len(activities) + len(expenses)

    # ── Insert audit-log row BEFORE streaming the response ────────────────
    # Requirement 16.3
    audit_payload: dict = {
        "user_id":      user_id,
        "export_type":  "csv",
        "record_count": record_count,
    }
    if date_from:
        audit_payload["date_range_from"] = date_from
    if date_to:
        audit_payload["date_range_to"] = date_to

    try:
        db.table("export_audit_log").insert(audit_payload).execute()
    except Exception as exc:
        logger.error("DB insert export_audit_log failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    # ── Build CSV ──────────────────────────────────────────────────────────
    # Columns:
    #   Activities → date, type, quantity, unit, cost, notes
    #   Expenses   → category, amount, expense_date
    # A leading record_type column distinguishes the two sections so the file
    # is parseable as a single CSV.
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row — union of all columns across both record types.
    writer.writerow([
        "record_type", "date", "type", "quantity", "unit", "cost", "notes",
        "category", "amount", "expense_date",
    ])

    # Activity rows — only selected fields, no GPS or PII.
    for a in activities:
        writer.writerow([
            "activity",
            str(a.get("logged_date", "")),
            a.get("activity_type", ""),
            a.get("quantity", ""),
            a.get("unit", ""),
            a.get("cost", ""),
            a.get("notes", ""),
            "", "", "",
        ])

    # Expense rows — only selected fields.
    for e in expenses:
        writer.writerow([
            "expense",
            "", "", "", "", "", "",
            e.get("category", ""),
            e.get("amount", ""),
            str(e.get("expense_date", "")),
        ])

    csv_bytes = output.getvalue().encode("utf-8")

    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="farm_report.csv"',
        },
    )
