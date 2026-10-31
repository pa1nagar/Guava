"""
calculators.py — Deterministic farm calculators.

Endpoints:
    POST /api/calculators/irrigation    Irrigation runtime calculation
    POST /api/calculators/nutrient      Nutrient product mass calculation
    POST /api/calculators/procurement   Scaled procurement quantity

Each calculator accepts all required inputs in the JSON body, validates them
through the pure service function, and returns all inputs echoed back
alongside the intermediates and the final result so the farmer can see every
value transparently (Requirement 11.2).

Invalid inputs raise ValueError in the service layer; the router converts
that into HTTP 422 with the field-specific message (Requirements 11.3, 11.4).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from services.auth import get_user_id
from services.irrigation_calc import (
    FORMULA_VERSION,
    IrrigationInput,
    IrrigationResult,
    compute_irrigation,
)
from services.nutrient_calc import (
    NutrientInput,
    NutrientResult,
    compute_nutrient,
)
from services.procurement_calc import (
    ProcurementInput,
    ProcurementResult,
    compute_procurement,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Irrigation calculator models ──────────────────────────────────────────────

class IrrigationRequest(BaseModel):
    """JSON body for POST /api/calculators/irrigation."""

    et0: float = Field(description="Reference evapotranspiration (mm/day)")
    kc: float = Field(description="Crop coefficient")
    effective_area: float = Field(description="Effective canopy area (m²)")
    system_efficiency: float = Field(description="Drip system efficiency (0 < eff <= 1.0)")
    emitter_count: int = Field(description="Number of working emitters")
    emitter_flow: float = Field(description="Emitter flow rate (litres/hour)")


class IrrigationResponse(BaseModel):
    """Response for POST /api/calculators/irrigation.

    Echoes all inputs and returns every intermediate value alongside the
    final runtime so the farmer can verify the calculation (Requirement 11.2).
    """

    # All inputs echoed back
    et0: float
    kc: float
    effective_area: float
    system_efficiency: float
    emitter_count: int
    emitter_flow: float
    # Intermediates (with units)
    net_water_litres: float
    gross_water_litres: float
    total_flow_litres_per_hour: float
    # Final result
    runtime_hours: float
    formula_version: str


# ── POST /api/calculators/irrigation ──────────────────────────────────────────

@router.post("/calculators/irrigation", response_model=IrrigationResponse)
def irrigation_calculator(
    body: IrrigationRequest,
    user_id: str = Depends(get_user_id),
) -> IrrigationResponse:
    """Compute irrigation runtime from measured field inputs.

    Returns all inputs, intermediates, and the final runtime in hours.
    Validation failures (zero/negative inputs or efficiency out of range)
    return HTTP 422 with a message naming the offending field.
    """
    inp = IrrigationInput(
        et0=body.et0,
        kc=body.kc,
        effective_area=body.effective_area,
        system_efficiency=body.system_efficiency,
        emitter_count=body.emitter_count,
        emitter_flow=body.emitter_flow,
    )

    try:
        result: IrrigationResult = compute_irrigation(inp)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return IrrigationResponse(
        et0=result.et0,
        kc=result.kc,
        effective_area=result.effective_area,
        system_efficiency=result.system_efficiency,
        emitter_count=result.emitter_count,
        emitter_flow=result.emitter_flow,
        net_water_litres=result.net_water_litres,
        gross_water_litres=result.gross_water_litres,
        total_flow_litres_per_hour=result.total_flow_litres_per_hour,
        runtime_hours=result.runtime_hours,
        formula_version=result.formula_version,
    )


# ── Procurement calculator models ─────────────────────────────────────────────

class ProcurementRequest(BaseModel):
    """JSON body for POST /api/calculators/procurement."""

    base_quantity: float = Field(description="Quantity for the reference scenario")
    base_reference: float = Field(description="Reference value for base scenario (plant count or area, > 0)")
    target_reference: float = Field(description="Reference value for target scenario (farmer's own count or area, > 0)")


class ProcurementResponse(BaseModel):
    """Response for POST /api/calculators/procurement.

    Echoes all inputs and returns both the unrounded scaled quantity and the
    purchase-unit rounded quantity, clearly distinguished (Requirement 13.2).
    """

    # All inputs echoed back
    base_quantity: float
    base_reference: float
    target_reference: float
    # Results
    scaled_quantity: float          # full precision (unrounded calculated quantity)
    scaled_quantity_rounded: float  # rounded to 2 decimal places (purchase unit)
    formula_version: str


# ── POST /api/calculators/procurement ─────────────────────────────────────────

@router.post("/calculators/procurement", response_model=ProcurementResponse)
def procurement_calculator(
    body: ProcurementRequest,
    user_id: str = Depends(get_user_id),
) -> ProcurementResponse:
    """Scale a base product quantity to match the farmer's actual plant count or plot area.

    Returns all inputs, the full-precision scaled quantity, and the
    purchase-unit rounded quantity (Requirement 13.2).
    Validation failures (zero or negative references) return HTTP 422
    with a message naming the offending field (Requirement 13.3).
    """
    inp = ProcurementInput(
        base_quantity=body.base_quantity,
        base_reference=body.base_reference,
        target_reference=body.target_reference,
    )

    try:
        result: ProcurementResult = compute_procurement(inp)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ProcurementResponse(
        base_quantity=result.base_quantity,
        base_reference=result.base_reference,
        target_reference=result.target_reference,
        scaled_quantity=result.scaled_quantity,
        scaled_quantity_rounded=result.scaled_quantity_rounded,
        formula_version=result.formula_version,
    )


# ── Nutrient calculator models ────────────────────────────────────────────────

class NutrientRequest(BaseModel):
    """JSON body for POST /api/calculators/nutrient."""

    target_g: float = Field(
        description="Target nutrient mass in grams (> 0)"
    )
    selected_grade: float = Field(
        description=(
            "Grade percentage of the selected nutrient component "
            "(0 < grade <= 100, e.g. 20 for the N component of 20-20-20)"
        )
    )
    source_record_id: str = Field(
        default="",
        description=(
            "ContentRecord.record_uid of the approved source, or "
            "'TEST_DATA' to flag the result as test data"
        ),
    )


class NutrientResponse(BaseModel):
    """Response for POST /api/calculators/nutrient.

    Echoes all inputs and returns the declared fraction alongside the
    final product mass so the farmer can verify the calculation
    (Requirement 12.2).  Full floating-point precision is retained in
    product_mass_g; rounding is a presentation-layer concern (Requirement 12.6).
    """

    # All inputs echoed back
    target_g: float
    selected_grade: float
    source_record_id: str
    # Intermediate
    declared_fraction: float
    # Final result (full precision)
    product_mass_g: float
    # Metadata
    is_test_data: bool
    formula_version: str


# ── POST /api/calculators/nutrient ────────────────────────────────────────────

@router.post("/calculators/nutrient", response_model=NutrientResponse)
def nutrient_calculator(
    body: NutrientRequest,
    user_id: str = Depends(get_user_id),
) -> NutrientResponse:
    """Convert a nutrient target into a product mass using the declared grade.

    Returns all inputs, the declared fraction, and the product mass in grams.
    Validation failures (target <= 0 or grade out of range) return HTTP 422
    with a message naming the offending field (Requirements 12.4, 12.5).
    """
    inp = NutrientInput(
        target_g=body.target_g,
        selected_grade=body.selected_grade,
        source_record_id=body.source_record_id,
    )

    try:
        result: NutrientResult = compute_nutrient(inp)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return NutrientResponse(
        target_g=result.target_g,
        selected_grade=result.selected_grade,
        source_record_id=body.source_record_id,
        declared_fraction=result.declared_fraction,
        product_mass_g=result.product_mass_g,
        is_test_data=result.is_test_data,
        formula_version=result.formula_version,
    )
