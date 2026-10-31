"""
procurement_calc.py — Deterministic procurement scaling calculator.

Pure function; no database access.  All arithmetic that touches procurement
scales happens here so it is trivially unit-testable.

Formula (Requirement 13.1):
    scaled_quantity = base_quantity × (target_reference / base_reference)

Validation (Requirement 13.3):
    - base_reference must be > 0.
    - target_reference must be > 0.
    - Any violation raises ValueError naming the offending field.

Rounding (Requirement 13.2):
    - scaled_quantity is returned at full floating-point precision.
    - scaled_quantity_rounded is rounded to 2 decimal places (purchase unit).

Functions
---------
compute_procurement(inp: ProcurementInput) -> ProcurementResult
"""

from __future__ import annotations

from dataclasses import dataclass


FORMULA_VERSION = "1.0"


@dataclass
class ProcurementInput:
    """Inputs for the procurement scaling calculation.

    Field ranges (Requirement 13.1):
        base_quantity      Quantity for the reference scenario
        base_reference     Reference value for base scenario (> 0; plant count or area)
        target_reference   Reference value for target scenario (> 0; farmer's own count or area)
    """

    base_quantity: float      # Quantity for the reference scenario
    base_reference: float     # Reference value for base scenario (> 0)
    target_reference: float   # Reference value for target scenario (> 0)
    formula_version: str = FORMULA_VERSION


@dataclass
class ProcurementResult:
    """Result of the procurement scaling calculation.

    All inputs are echoed back alongside the unrounded scaled quantity and
    the purchase-unit rounded quantity so the caller can display every value
    transparently (Requirement 13.2).
    """

    # All inputs echoed back
    base_quantity: float
    base_reference: float
    target_reference: float
    # Results
    scaled_quantity: float          # base_quantity × (target_reference / base_reference), full precision
    scaled_quantity_rounded: float  # rounded to 2 decimal places (purchase unit)
    formula_version: str


def compute_procurement(inp: ProcurementInput) -> ProcurementResult:
    """Compute scaled procurement quantity from a base dose and reference values.

    Raises ValueError when base_reference or target_reference is zero or
    negative (Requirement 13.3).
    The error message always names the offending field.
    """
    # ── Validate references (Requirement 13.3) ───────────────────────────────
    # base_reference and target_reference must be > 0; zero or negative is
    # rejected and no scaled output is produced.
    if inp.base_reference <= 0:
        raise ValueError("base_reference must be greater than 0")
    if inp.target_reference <= 0:
        raise ValueError("target_reference must be greater than 0")

    # ── Compute scaled quantity (Requirement 13.1) ──────────────────────────
    # scaled_quantity = base_quantity × (target_reference / base_reference)
    scaled_quantity = inp.base_quantity * (inp.target_reference / inp.base_reference)

    # ── Round to purchase unit (Requirement 13.2) ─────────────────────────────
    # Full precision is retained in scaled_quantity; the rounded value is
    # provided separately for the final procurement step.
    scaled_quantity_rounded = round(scaled_quantity, 2)

    return ProcurementResult(
        base_quantity=inp.base_quantity,
        base_reference=inp.base_reference,
        target_reference=inp.target_reference,
        scaled_quantity=scaled_quantity,
        scaled_quantity_rounded=scaled_quantity_rounded,
        formula_version=inp.formula_version,
    )
