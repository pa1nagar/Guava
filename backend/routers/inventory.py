"""
inventory.py — Inventory management endpoints.

GET  /api/farmers/me/inventory            List all inventory items.
POST /api/farmers/me/inventory            Create a new inventory item.
PUT  /api/farmers/me/inventory/{id}       Update an inventory item.
POST /api/farmers/me/inventory/{id}/consume  Consume inventory (reduce quantity_on_hand).

Business rules enforced here:
  - quantity_on_hand cannot go below zero: consuming more than on-hand returns 422.
  - If activity_id is provided on consume, the activity must belong to the same user;
    otherwise 404 is returned (IDOR prevention — Requirement 3.3).
  - Crop approval is NEVER inferred from product_name or active_ingredient.
    These fields are stored as farmer-entered text only (Requirement 8.3, 8.4).
  - All queries filter by user_id = <jwt.sub>; mismatches return 404 (Requirement 3.2).

Multi-tenant isolation
----------------------
  user_id is always derived from JWT via Depends(get_user_id).
  It is NEVER read from the request body.
  Requirements: 3.2, 3.3, 3.4, 8.1, 8.2, 8.3, 8.4
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from services.auth import get_user_id
from services.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


# ═════════════════════════════════════════════════════════════════════════════
# Models
# ═════════════════════════════════════════════════════════════════════════════

class InventoryItemIn(BaseModel):
    """Input model for creating a new inventory item.

    Requirement 8.1: farmer-entered product catalogue fields.
    Note: product_name and active_ingredient are stored as plain text.
    Crop approval is NEVER inferred from these fields (Requirement 8.3, 8.4).
    """
    product_name: str = Field(min_length=1, max_length=500, description="Product name (required).")
    active_ingredient: Optional[str] = Field(default=None, max_length=500)
    formulation: Optional[str] = Field(default=None, max_length=200)
    manufacturer: Optional[str] = Field(default=None, max_length=500)
    batch_number: Optional[str] = Field(default=None, max_length=200)
    expiry_date: Optional[str] = Field(default=None, description="ISO date string YYYY-MM-DD.")
    quantity_on_hand: float = Field(default=0.0, ge=0, description="Current quantity in hand.")
    unit: str = Field(min_length=1, max_length=50, description="Unit of measurement (required).")
    purchase_price: Optional[float] = Field(default=None, ge=0)
    label_photo_key: Optional[str] = None
    safety_doc_ref: Optional[str] = None
    supplier_name: Optional[str] = Field(default=None, max_length=500)
    farm_id: Optional[str] = None


class InventoryItemUpdate(BaseModel):
    """Partial update model — only provided fields are changed.

    Requirement 8.2: supports updating any field including quantity_on_hand.
    Crop approval is NEVER inferred from updated product_name or active_ingredient.
    """
    product_name: Optional[str] = Field(default=None, min_length=1, max_length=500)
    active_ingredient: Optional[str] = Field(default=None, max_length=500)
    formulation: Optional[str] = Field(default=None, max_length=200)
    manufacturer: Optional[str] = Field(default=None, max_length=500)
    batch_number: Optional[str] = Field(default=None, max_length=200)
    expiry_date: Optional[str] = None
    quantity_on_hand: Optional[float] = Field(default=None, ge=0)
    unit: Optional[str] = Field(default=None, min_length=1, max_length=50)
    purchase_price: Optional[float] = Field(default=None, ge=0)
    label_photo_key: Optional[str] = None
    safety_doc_ref: Optional[str] = None
    supplier_name: Optional[str] = Field(default=None, max_length=500)
    farm_id: Optional[str] = None


class InventoryItemOut(BaseModel):
    id: str
    product_name: str
    active_ingredient: Optional[str]
    formulation: Optional[str]
    manufacturer: Optional[str]
    batch_number: Optional[str]
    expiry_date: Optional[str]
    quantity_on_hand: float
    unit: str
    purchase_price: Optional[float]
    label_photo_key: Optional[str]
    safety_doc_ref: Optional[str]
    supplier_name: Optional[str]
    farm_id: Optional[str]
    created_at: str
    updated_at: str


class ConsumeIn(BaseModel):
    """Input model for consuming inventory.

    Requirement 8.2: links consumption to an activity; reduces quantity_on_hand.
    """
    quantity_consumed: float = Field(
        gt=0,
        description="Amount to consume. Must be positive.",
    )
    activity_id: Optional[str] = Field(
        default=None,
        description="Optional: link consumption to a farm activity owned by this user.",
    )


class ConsumeOut(BaseModel):
    id: str
    product_name: str
    quantity_on_hand: float
    unit: str
    quantity_consumed: float
    activity_id: Optional[str]


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════

_ITEM_FIELDS = (
    "id, product_name, active_ingredient, formulation, manufacturer, batch_number, "
    "expiry_date, quantity_on_hand, unit, purchase_price, label_photo_key, "
    "safety_doc_ref, supplier_name, farm_id, created_at, updated_at"
)


def _row_to_out(row: dict) -> InventoryItemOut:
    """Convert a DB row dict to an InventoryItemOut model."""
    return InventoryItemOut(
        id=row["id"],
        product_name=row["product_name"],
        active_ingredient=row.get("active_ingredient"),
        formulation=row.get("formulation"),
        manufacturer=row.get("manufacturer"),
        batch_number=row.get("batch_number"),
        expiry_date=str(row["expiry_date"]) if row.get("expiry_date") else None,
        quantity_on_hand=float(row["quantity_on_hand"]),
        unit=row["unit"],
        purchase_price=float(row["purchase_price"]) if row.get("purchase_price") is not None else None,
        label_photo_key=row.get("label_photo_key"),
        safety_doc_ref=row.get("safety_doc_ref"),
        supplier_name=row.get("supplier_name"),
        farm_id=row.get("farm_id"),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _get_item(item_id: str, user_id: str) -> dict:
    """Fetch an inventory item owned by user_id. Raises 404 on mismatch.

    IDOR prevention: query filters by both item_id AND user_id so items
    belonging to other users are never exposed (Requirement 3.3).
    """
    db = get_db()
    try:
        result = (
            db.table("inventory_items")
            .select(_ITEM_FIELDS)
            .eq("id", item_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        logger.error("DB select inventory item failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Inventory item not found.")
    return result.data


def _get_farmer_activity(activity_id: str, user_id: str) -> dict:
    """Verify an activity belongs to the requesting user.

    Returns the activity row or raises 404 (IDOR prevention — Requirement 3.3).
    Uses the farmer lookup via farmers.user_id join to confirm ownership.
    """
    db = get_db()
    try:
        # First get the farmer record to confirm user exists.
        farmer_result = (
            db.table("farmers")
            .select("id")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        logger.error("DB select farmer for activity check failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    if not farmer_result or not farmer_result.data:
        raise HTTPException(status_code=404, detail="Activity not found.")

    farmer_id = farmer_result.data["id"]

    try:
        activity_result = (
            db.table("farm_activities")
            .select("id, farmer_id")
            .eq("id", activity_id)
            .eq("farmer_id", farmer_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        logger.error("DB select activity for consumption link failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    if not activity_result or not activity_result.data:
        raise HTTPException(status_code=404, detail="Activity not found.")

    return activity_result.data


# ═════════════════════════════════════════════════════════════════════════════
# Endpoints
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/farmers/me/inventory", response_model=List[InventoryItemOut])
def list_inventory(user_id: str = Depends(get_user_id)) -> List[InventoryItemOut]:
    """List all inventory items for the authenticated farmer.

    Requirement 8.1: returns the full product catalogue for the user.
    Results are ordered by product_name ascending for consistent display.

    Multi-tenant isolation: only items with user_id == jwt.sub are returned.
    """
    db = get_db()
    try:
        result = (
            db.table("inventory_items")
            .select(_ITEM_FIELDS)
            .eq("user_id", user_id)
            .order("product_name", desc=False)
            .execute()
        )
    except Exception as exc:
        logger.error("DB list inventory failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    return [_row_to_out(r) for r in (result.data or [])]


@router.post("/farmers/me/inventory", response_model=InventoryItemOut, status_code=201)
def create_inventory_item(
    body: InventoryItemIn,
    user_id: str = Depends(get_user_id),
) -> InventoryItemOut:
    """Create a new inventory item for the authenticated farmer.

    Requirement 8.1: farmer adds a product to their inventory catalogue.
    Requirement 8.3: product_name and active_ingredient are stored as
    farmer-entered text — crop approval is NEVER inferred from them.
    Requirement 8.4: no controlled vocabulary restriction on product fields.

    Multi-tenant isolation: user_id is always injected from JWT, never from body.
    """
    db = get_db()

    # Build payload from non-None fields; always inject user_id from JWT.
    payload = body.model_dump(exclude_none=True)
    payload["user_id"] = user_id

    try:
        result = db.table("inventory_items").insert(payload).execute()
    except Exception as exc:
        logger.error("DB insert inventory item failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    row = result.data[0]
    return _row_to_out(row)


@router.put("/farmers/me/inventory/{item_id}", response_model=InventoryItemOut)
def update_inventory_item(
    item_id: str,
    body: InventoryItemUpdate,
    user_id: str = Depends(get_user_id),
) -> InventoryItemOut:
    """Update an inventory item. Only provided fields are changed (partial update).

    Requirement 8.2: supports partial field updates.
    Requirement 8.3: updating product_name or active_ingredient NEVER triggers
    crop approval inference — they remain plain text fields.

    Returns 404 if the item is not owned by the caller (IDOR prevention).
    """
    # Verify ownership — raises 404 if not found or not owned.
    _get_item(item_id, user_id)

    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        # Nothing to update — return current state.
        row = _get_item(item_id, user_id)
        return _row_to_out(row)

    db = get_db()
    try:
        result = (
            db.table("inventory_items")
            .update(update_data)
            .eq("id", item_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as exc:
        logger.error("DB update inventory item failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    if not result.data:
        raise HTTPException(status_code=404, detail="Inventory item not found.")

    return _row_to_out(result.data[0])


@router.post("/farmers/me/inventory/{item_id}/consume", response_model=ConsumeOut)
def consume_inventory(
    item_id: str,
    body: ConsumeIn,
    user_id: str = Depends(get_user_id),
) -> ConsumeOut:
    """Consume inventory — reduce quantity_on_hand by quantity_consumed.

    Business rules:
      - quantity_consumed must be > 0 (enforced by Pydantic Field(gt=0)).
      - quantity_consumed must not exceed quantity_on_hand: returns 422 if it does.
      - If activity_id is provided, the activity must belong to the same user;
        returns 404 if not found or not owned (IDOR prevention — Requirement 3.3).
      - Crop approval is NEVER inferred from the item's product_name or
        active_ingredient during consumption (Requirement 8.3, 8.4).

    Requirement 8.2: reduces quantity_on_hand; links consumption to an activity.
    """
    # Fetch and verify ownership of the inventory item.
    item = _get_item(item_id, user_id)

    current_qty = float(item["quantity_on_hand"])

    # Reject if quantity_consumed exceeds quantity_on_hand.
    if body.quantity_consumed > current_qty:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Cannot consume {body.quantity_consumed} {item['unit']}: "
                f"only {current_qty} {item['unit']} on hand."
            ),
        )

    # Verify the linked activity belongs to the same user (IDOR prevention).
    if body.activity_id is not None:
        _get_farmer_activity(body.activity_id, user_id)

    new_qty = round(current_qty - body.quantity_consumed, 6)

    db = get_db()
    try:
        result = (
            db.table("inventory_items")
            .update({"quantity_on_hand": new_qty})
            .eq("id", item_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as exc:
        logger.error("DB update inventory quantity failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    if not result.data:
        raise HTTPException(status_code=404, detail="Inventory item not found.")

    return ConsumeOut(
        id=item_id,
        product_name=item["product_name"],
        quantity_on_hand=float(result.data[0]["quantity_on_hand"]),
        unit=item["unit"],
        quantity_consumed=body.quantity_consumed,
        activity_id=body.activity_id,
    )
