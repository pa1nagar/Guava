"""
nutrient_calc.py — Deterministic nutrient product mass calculator.

Pure function; no database access.  All arithmetic that converts a nutrient
target into a product quantity happens here so it is trivially unit-testable.

Formula (Requirement 12.1):
    declared_fraction = selected_grade / 100
    product_mass_g    = target_g / declared_fraction

Validation (Requirements 12.4, 12.5):
    - target_g must be greater than 0.
    - declared_fraction must be in the open-closed interval (0, 1.0]
      (equivalently, selected_grade must be in (0, 100]).
    - Any violation raises ValueError naming the offending field.

Test-data handling (Requirement 12.9):
    When source_record_id == 'TEST_DATA', the result carries is_test_data=True
    so the caller can display the prominent "TEST DATA" warning label.

Functions
---------
compute_nutrient(inp: NutrientInput) -> NutrientResult
"""

from __future__ import annotations

from dataclasses import dataclass


FORMULA_VERSION = "1.0"


@dataclass
class NutrientInput:
    """Inputs for the nutrient product mass calculation.

    Field ranges (Requirement 12.1):
        target_g          > 0          (target nutrient mass in grams)
        selected_grade    (0, 100]     (grade percentage of the selected nutrient
                                       component, e.g. 20 for a 20-20-20 grade
                                       when computing the N component)
        source_record_id  str          (ContentRecord.record_uid or 'TEST_DATA')
    """

    target_g: float               # Target nutrient mass in grams (> 0)
    selected_grade: float         # Grade percentage (0 < grade <= 100)
    source_record_id: str = ""    # If 'TEST_DATA', sets is_test_data=True
    formula_version: str = FORMULA_VERSION


@dataclass
class NutrientResult:
    """Result of the nutrient product mass calculation.

    All inputs are echoed back alongside the intermediate (declared_fraction)
    and the final product mass so the caller can display every value
    transparently (Requirement 12.2).

    Full floating-point precision is retained in product_mass_g; rounding to
    a display value happens only at the presentation layer (Requirement 12.6).
    """

    # All inputs echoed back
    target_g: float
    selected_grade: float
    # Intermediate (Requirement 12.3: grade / 100)
    declared_fraction: float      # selected_grade / 100
    # Final result (full precision)
    product_mass_g: float         # target_g / declared_fraction
    # Metadata
    is_test_data: bool
    formula_version: str


def compute_nutrient(inp: NutrientInput) -> NutrientResult:
    """Compute the product mass needed to deliver a target nutrient amount.

    Raises ValueError when target_g is <= 0 or when the declared fraction
    (selected_grade / 100) is outside the interval (0, 1.0].
    The error message always names the offending field (Requirements 12.4, 12.5).
    """
    # ── Validate target (Requirement 12.5) ────────────────────────────────────
    if inp.target_g <= 0:
        raise ValueError("target_g must be greater than 0")

    # ── Compute and validate declared fraction (Requirements 12.3, 12.4) ───────
    # Grade percentages are converted to fractions by dividing by 100 (12.3).
    # The declared fraction must be in (0, 1.0] (12.4).
    declared_fraction = inp.selected_grade / 100.0

    if inp.selected_grade <= 0:
        raise ValueError("selected_grade must be greater than 0")
    if inp.selected_grade > 100:
        raise ValueError("selected_grade must be at most 100")

    # ── Compute product mass (Requirement 12.1) ────────────────────────────────
    # product_mass = target / declared_fraction
    product_mass_g = inp.target_g / declared_fraction

    # ── Determine test-data flag (Requirement 12.9) ────────────────────────────
    is_test_data = inp.source_record_id == "TEST_DATA"

    return NutrientResult(
        target_g=inp.target_g,
        selected_grade=inp.selected_grade,
        declared_fraction=declared_fraction,
        product_mass_g=product_mass_g,
        is_test_data=is_test_data,
        formula_version=inp.formula_version,
    )
