"""
farms.py — Farm and Plot CRUD endpoints.

Endpoints
---------
Farms:
  GET    /api/farmers/me/farms                          List farms
  POST   /api/farmers/me/farms                          Create farm
  GET    /api/farmers/me/farms/{farm_id}                Get farm
  PUT    /api/farmers/me/farms/{farm_id}                Update farm
  DELETE /api/farmers/me/farms/{farm_id}/archive        Archive farm (soft delete)

Plots:
  GET    /api/farmers/me/farms/{farm_id}/plots          List plots
  POST   /api/farmers/me/farms/{farm_id}/plots          Create plot
  GET    /api/farmers/me/farms/{farm_id}/plots/{plot_id}          Get plot
  PUT    /api/farmers/me/farms/{farm_id}/plots/{plot_id}          Update plot
  GET    /api/farmers/me/farms/{farm_id}/plots/{plot_id}/plant-count-history

Business rules
--------------
  - planting_date in the future is rejected with HTTP 422.
  - When plant_count is updated, a plot_plant_count_audit row is inserted
    (with prior and new count) BEFORE the change is applied.
  - Archive sets is_active = false; never hard-deletes.
  - No defaults are pre-populated (no 2100 trees, Taiwan Pink, or Badnawar).

Multi-tenant isolation
----------------------
  user_id is always derived from the JWT via Depends(get_user_id).
  It is NEVER read from the request body. Every query filters by user_id
  AND the resource id. IDOR attempts return 404 (not 403) to avoid
  confirming resource existence.
  Requirements: 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4, 4.5, 4.7, 4.8
"""

import logging
from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from services.auth import get_user_id
from services.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


# ═════════════════════════════════════════════════════════════════════════════
# Models — Farms
# ═════════════════════════════════════════════════════════════════════════════

class FarmIn(BaseModel):
    name: str = Field(min_length=1, max_length=200, description="Farm name (required).")
    locality: Optional[str] = Field(default=None, max_length=200)
    district: str = Field(min_length=1, max_length=200, description="District (required).")
    state: str = Field(min_length=1, max_length=200, description="State (required).")
    country: str = Field(default="India", max_length=100)
    timezone: str = Field(default="Asia/Kolkata", max_length=100)
    approx_lat: Optional[float] = Field(default=None, ge=-90, le=90)
    approx_lon: Optional[float] = Field(default=None, ge=-180, le=180)
    area_value: Optional[float] = Field(default=None, ge=0)
    area_unit: Optional[str] = Field(default=None, description="One of: acres, hectares, sqm")
    soil_description: Optional[str] = None
    irrigation_method: Optional[str] = None
    water_source: Optional[str] = None
    notes: Optional[str] = None


class FarmUpdate(BaseModel):
    """All fields optional for partial updates."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    locality: Optional[str] = Field(default=None, max_length=200)
    district: Optional[str] = Field(default=None, min_length=1, max_length=200)
    state: Optional[str] = Field(default=None, min_length=1, max_length=200)
    country: Optional[str] = Field(default=None, max_length=100)
    timezone: Optional[str] = Field(default=None, max_length=100)
    approx_lat: Optional[float] = Field(default=None, ge=-90, le=90)
    approx_lon: Optional[float] = Field(default=None, ge=-180, le=180)
    area_value: Optional[float] = Field(default=None, ge=0)
    area_unit: Optional[str] = None
    soil_description: Optional[str] = None
    irrigation_method: Optional[str] = None
    water_source: Optional[str] = None
    notes: Optional[str] = None


class FarmOut(BaseModel):
    id: str
    name: str
    locality: Optional[str]
    district: str
    state: str
    country: str
    timezone: str
    approx_lat: Optional[float]
    approx_lon: Optional[float]
    area_value: Optional[float]
    area_unit: Optional[str]
    soil_description: Optional[str]
    irrigation_method: Optional[str]
    water_source: Optional[str]
    notes: Optional[str]
    is_active: bool
    created_at: str
    updated_at: str


# ═════════════════════════════════════════════════════════════════════════════
# Models — Plots
# ═════════════════════════════════════════════════════════════════════════════

class PlotIn(BaseModel):
    name: str = Field(min_length=1, max_length=200, description="Plot name/code (required).")
    area_value: Optional[float] = Field(default=None, ge=0)
    area_unit: Optional[str] = None
    crop: str = Field(min_length=1, max_length=200, description="Crop (required).")
    variety: Optional[str] = None
    planting_date: date = Field(description="Planting date (required, must not be in the future).")
    planting_method: Optional[str] = None
    row_spacing_m: Optional[float] = Field(default=None, ge=0)
    within_row_spacing_m: Optional[float] = Field(default=None, ge=0)
    plant_count: int = Field(gt=0, description="Number of plants (must be ≥ 1).")
    survival_count: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = None


class PlotUpdate(BaseModel):
    """All fields optional for partial updates. plant_count triggers audit."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    area_value: Optional[float] = Field(default=None, ge=0)
    area_unit: Optional[str] = None
    crop: Optional[str] = Field(default=None, min_length=1, max_length=200)
    variety: Optional[str] = None
    planting_date: Optional[date] = None
    planting_method: Optional[str] = None
    row_spacing_m: Optional[float] = Field(default=None, ge=0)
    within_row_spacing_m: Optional[float] = Field(default=None, ge=0)
    plant_count: Optional[int] = Field(default=None, gt=0)
    survival_count: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = None


class PlotOut(BaseModel):
    id: str
    farm_id: str
    name: str
    area_value: Optional[float]
    area_unit: Optional[str]
    crop: str
    variety: Optional[str]
    planting_date: str
    planting_method: Optional[str]
    row_spacing_m: Optional[float]
    within_row_spacing_m: Optional[float]
    plant_count: int
    survival_count: Optional[int]
    notes: Optional[str]
    created_at: str
    updated_at: str


class PlantCountAuditOut(BaseModel):
    id: str
    plot_id: str
    prior_count: int
    new_count: int
    changed_at: str


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════

_FARM_FIELDS = (
    "id, name, locality, district, state, country, timezone, approx_lat, approx_lon, "
    "area_value, area_unit, soil_description, irrigation_method, water_source, notes, "
    "is_active, created_at, updated_at"
)

_PLOT_FIELDS = (
    "id, farm_id, name, area_value, area_unit, crop, variety, planting_date, "
    "planting_method, row_spacing_m, within_row_spacing_m, plant_count, survival_count, "
    "notes, created_at, updated_at"
)

_VALID_AREA_UNITS = {"acres", "hectares", "sqm"}


def _validate_area_unit(area_unit: Optional[str]) -> None:
    """Raise 422 if area_unit is provided but not in the allowed set."""
    if area_unit is not None and area_unit not in _VALID_AREA_UNITS:
        raise HTTPException(
            status_code=422,
            detail=f"area_unit must be one of: {', '.join(sorted(_VALID_AREA_UNITS))}",
        )


def _check_planting_date(planting_date: date) -> None:
    """Reject planting dates in the future (Requirement 4.5)."""
    if planting_date > date.today():
        raise HTTPException(
            status_code=422,
            detail="Planting date cannot be in the future.",
        )


def _farm_row_to_out(row: dict) -> FarmOut:
    return FarmOut(
        id=row["id"],
        name=row["name"],
        locality=row.get("locality"),
        district=row["district"],
        state=row["state"],
        country=row.get("country", "India"),
        timezone=row.get("timezone", "Asia/Kolkata"),
        approx_lat=row.get("approx_lat"),
        approx_lon=row.get("approx_lon"),
        area_value=row.get("area_value"),
        area_unit=row.get("area_unit"),
        soil_description=row.get("soil_description"),
        irrigation_method=row.get("irrigation_method"),
        water_source=row.get("water_source"),
        notes=row.get("notes"),
        is_active=row.get("is_active", True),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _plot_row_to_out(row: dict) -> PlotOut:
    return PlotOut(
        id=row["id"],
        farm_id=row["farm_id"],
        name=row["name"],
        area_value=row.get("area_value"),
        area_unit=row.get("area_unit"),
        crop=row["crop"],
        variety=row.get("variety"),
        planting_date=str(row["planting_date"]),
        planting_method=row.get("planting_method"),
        row_spacing_m=row.get("row_spacing_m"),
        within_row_spacing_m=row.get("within_row_spacing_m"),
        plant_count=row["plant_count"],
        survival_count=row.get("survival_count"),
        notes=row.get("notes"),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _get_farm(farm_id: str, user_id: str) -> dict:
    """Fetch a farm owned by user_id. Returns the row dict or raises 404.

    IDOR prevention: the query filters by both farm_id AND user_id.
    A farm belonging to another user simply does not match and is
    returned as "not found" (404, not 403).
    """
    db = get_db()
    try:
        result = (
            db.table("farms")
            .select(_FARM_FIELDS)
            .eq("id", farm_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        logger.error("DB select farm failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Farm not found.")
    return result.data


def _get_plot(farm_id: str, plot_id: str, user_id: str) -> dict:
    """Fetch a plot owned by user_id under the given farm. Returns row or 404."""
    # First verify the farm belongs to the user (404 if not).
    _get_farm(farm_id, user_id)

    db = get_db()
    try:
        result = (
            db.table("plots")
            .select(_PLOT_FIELDS)
            .eq("id", plot_id)
            .eq("farm_id", farm_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        logger.error("DB select plot failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Plot not found.")
    return result.data


# ═════════════════════════════════════════════════════════════════════════════
# Farm endpoints
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/farmers/me/farms", response_model=List[FarmOut])
def list_farms(user_id: str = Depends(get_user_id)) -> List[FarmOut]:
    """List all farms for the authenticated farmer.

    Archived (is_active=false) farms are included so the farmer can see
    their full history. Active farms are returned first.
    """
    db = get_db()
    try:
        result = (
            db.table("farms")
            .select(_FARM_FIELDS)
            .eq("user_id", user_id)
            .order("is_active", desc=True)   # active farms first
            .order("created_at", desc=False)
            .execute()
        )
    except Exception as exc:
        logger.error("DB list farms failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    return [_farm_row_to_out(r) for r in (result.data or [])]


@router.post("/farmers/me/farms", response_model=FarmOut, status_code=201)
def create_farm(body: FarmIn, user_id: str = Depends(get_user_id)) -> FarmOut:
    """Create a new farm for the authenticated farmer.

    No defaults are pre-populated — the farmer must supply their own values.
    Requirement 4.8: do NOT pre-populate 2100 trees, Taiwan Pink, or Badnawar.
    """
    _validate_area_unit(body.area_unit)

    db = get_db()
    payload = body.model_dump(exclude_none=True)
    payload["user_id"] = user_id

    try:
        result = db.table("farms").insert(payload).execute()
    except Exception as exc:
        logger.error("DB insert farm failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    row = result.data[0]
    return _farm_row_to_out(row)


@router.get("/farmers/me/farms/{farm_id}", response_model=FarmOut)
def get_farm(farm_id: str, user_id: str = Depends(get_user_id)) -> FarmOut:
    """Get a specific farm. Returns 404 if not owned (IDOR prevention)."""
    row = _get_farm(farm_id, user_id)
    return _farm_row_to_out(row)


@router.put("/farmers/me/farms/{farm_id}", response_model=FarmOut)
def update_farm(
    farm_id: str,
    body: FarmUpdate,
    user_id: str = Depends(get_user_id),
) -> FarmOut:
    """Update farm details. Only provided fields are updated (partial update).

    Returns 404 if the farm is not owned by the caller (IDOR prevention).
    """
    # Verify ownership first (raises 404 if not found / not owned).
    _get_farm(farm_id, user_id)

    _validate_area_unit(body.area_unit)

    # Build update payload from non-None fields only.
    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        # Nothing to update — return current state.
        row = _get_farm(farm_id, user_id)
        return _farm_row_to_out(row)

    db = get_db()
    try:
        result = (
            db.table("farms")
            .update(update_data)
            .eq("id", farm_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as exc:
        logger.error("DB update farm failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    if not result.data:
        raise HTTPException(status_code=404, detail="Farm not found.")

    return _farm_row_to_out(result.data[0])


@router.delete("/farmers/me/farms/{farm_id}/archive")
def archive_farm(farm_id: str, user_id: str = Depends(get_user_id)) -> dict:
    """Archive a farm — sets is_active = false, never hard-deletes.

    Requirement 4.7: all historical records are retained.
    Returns 404 if the farm is not owned by the caller (IDOR prevention).
    """
    # Verify ownership first (raises 404 if not found / not owned).
    _get_farm(farm_id, user_id)

    db = get_db()
    try:
        result = (
            db.table("farms")
            .update({"is_active": False})
            .eq("id", farm_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as exc:
        logger.error("DB archive farm failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    if not result.data:
        raise HTTPException(status_code=404, detail="Farm not found.")

    return {"status": "archived", "farm_id": farm_id}


# ═════════════════════════════════════════════════════════════════════════════
# Plot endpoints
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/farmers/me/farms/{farm_id}/plots", response_model=List[PlotOut])
def list_plots(farm_id: str, user_id: str = Depends(get_user_id)) -> List[PlotOut]:
    """List all plots for a farm owned by the authenticated farmer."""
    # Verify farm ownership (raises 404 if not owned).
    _get_farm(farm_id, user_id)

    db = get_db()
    try:
        result = (
            db.table("plots")
            .select(_PLOT_FIELDS)
            .eq("farm_id", farm_id)
            .eq("user_id", user_id)
            .order("created_at", desc=False)
            .execute()
        )
    except Exception as exc:
        logger.error("DB list plots failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    return [_plot_row_to_out(r) for r in (result.data or [])]


@router.post("/farmers/me/farms/{farm_id}/plots", response_model=PlotOut, status_code=201)
def create_plot(
    farm_id: str,
    body: PlotIn,
    user_id: str = Depends(get_user_id),
) -> PlotOut:
    """Create a plot under a farm owned by the authenticated farmer.

    Requirement 4.5: planting_date in the future is rejected with 422.
    Requirement 4.8: no defaults are pre-populated.
    """
    # Verify farm ownership (raises 404 if not owned).
    _get_farm(farm_id, user_id)

    _check_planting_date(body.planting_date)
    _validate_area_unit(body.area_unit)

    db = get_db()
    payload = body.model_dump(exclude_none=True)
    payload["farm_id"] = farm_id
    payload["user_id"] = user_id

    try:
        result = db.table("plots").insert(payload).execute()
    except Exception as exc:
        logger.error("DB insert plot failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    row = result.data[0]
    return _plot_row_to_out(row)


@router.get("/farmers/me/farms/{farm_id}/plots/{plot_id}", response_model=PlotOut)
def get_plot(
    farm_id: str,
    plot_id: str,
    user_id: str = Depends(get_user_id),
) -> PlotOut:
    """Get a specific plot. Returns 404 if not owned (IDOR prevention)."""
    row = _get_plot(farm_id, plot_id, user_id)
    return _plot_row_to_out(row)


@router.put("/farmers/me/farms/{farm_id}/plots/{plot_id}", response_model=PlotOut)
def update_plot(
    farm_id: str,
    plot_id: str,
    body: PlotUpdate,
    user_id: str = Depends(get_user_id),
) -> PlotOut:
    """Update a plot. Only provided fields are updated (partial update).

    Requirement 4.3: when plant_count changes, insert a plot_plant_count_audit
    row (with prior and new count) BEFORE applying the change.
    Requirement 4.5: planting_date in the future is rejected with 422.
    Requirement 4.4: row_spacing_m and within_row_spacing_m are stored
    separately — never substituted with a hard-coded effective area.
    """
    # Fetch current plot (raises 404 if not found / not owned).
    current = _get_plot(farm_id, plot_id, user_id)

    # Validate planting_date if provided.
    if body.planting_date is not None:
        _check_planting_date(body.planting_date)

    _validate_area_unit(body.area_unit)

    update_data = body.model_dump(exclude_none=True)

    # ── Plant count audit trail (Requirement 4.3) ───────────────────────────
    # Insert the audit row BEFORE applying the change so that historical
    # calculations referencing the earlier count remain correct.
    if "plant_count" in update_data and update_data["plant_count"] != current["plant_count"]:
        db = get_db()
        try:
            db.table("plot_plant_count_audit").insert({
                "plot_id": plot_id,
                "user_id": user_id,
                "prior_count": current["plant_count"],
                "new_count": update_data["plant_count"],
            }).execute()
        except Exception as exc:
            logger.error("DB insert plant count audit failed: %s", exc)
            raise HTTPException(status_code=500, detail="Database error.")

    if not update_data:
        return _plot_row_to_out(current)

    db = get_db()
    try:
        result = (
            db.table("plots")
            .update(update_data)
            .eq("id", plot_id)
            .eq("farm_id", farm_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as exc:
        logger.error("DB update plot failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    if not result.data:
        raise HTTPException(status_code=404, detail="Plot not found.")

    return _plot_row_to_out(result.data[0])


@router.get(
    "/farmers/me/farms/{farm_id}/plots/{plot_id}/plant-count-history",
    response_model=List[PlantCountAuditOut],
)
def get_plant_count_history(
    farm_id: str,
    plot_id: str,
    user_id: str = Depends(get_user_id),
) -> List[PlantCountAuditOut]:
    """Return the plot_plant_count_audit rows for a plot (Requirement 4.3).

    Rows are ordered by changed_at ascending so the oldest change is first.
    Returns 404 if the plot is not owned by the caller (IDOR prevention).
    """
    # Verify plot ownership (raises 404 if not found / not owned).
    _get_plot(farm_id, plot_id, user_id)

    db = get_db()
    try:
        result = (
            db.table("plot_plant_count_audit")
            .select("id, plot_id, prior_count, new_count, changed_at")
            .eq("plot_id", plot_id)
            .eq("user_id", user_id)
            .order("changed_at", desc=False)
            .execute()
        )
    except Exception as exc:
        logger.error("DB select plant count history failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    return [
        PlantCountAuditOut(
            id=r["id"],
            plot_id=r["plot_id"],
            prior_count=r["prior_count"],
            new_count=r["new_count"],
            changed_at=str(r["changed_at"]),
        )
        for r in (result.data or [])
    ]
