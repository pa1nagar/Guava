"""
activities.py — Farm activity ledger endpoints.

GET  /api/farmers/me/activities      List all activities for the farmer (with filters).
POST /api/farmers/me/activities      Log a new activity.
PUT  /api/farmers/me/activities/{id} Edit an activity (writes audit log first).
POST /api/farmers/me/activities/{id}/photo  Upload a photo for an activity.
GET  /api/farmers/me/spending        Total spend + breakdown by type.
GET  /api/farmers/me/gaps            Expected-vs-actual input gaps.
GET  /api/constants/activity-types   Canonical activity type list.

Business rules enforced here:
  - Irrigation has zero cost (water is free). Any submitted cost is overridden to 0.
    The original submitted cost is stored in original_cost and noted in the notes
    field for audit purposes (Requirement 5.3).
  - activity_type must be in the authoritative ACTIVITY_TYPES list.
  - quantity >= 0, cost >= 0.
  - Planned activities are distinct from recorded/completed activities; a planned
    activity is never treated as evidence that an operation was performed (Req 5.7).
  - All edits write an immutable activity_audit_log row before the field changes
    are applied (Requirement 5.4).
  - Photo uploads validate MIME via magic bytes, reject > 10 MB, strip EXIF GPS
    metadata, and use a UUID-based non-guessable storage key (Requirement 5.6).
"""

# ── Multi-tenant isolation ──────────────────────────────────────────────────
# Security: user_id is always derived from JWT via Depends(get_user_id).
# It is NEVER read from the request body. All DB queries filter by user_id
# or farmer_id IN (SELECT id FROM farmers WHERE user_id = <jwt.sub>).
# IDOR attempts return 404 (not 403) to avoid confirming resource existence.
# Requirements: 3.2, 3.3, 3.4

import io
import json
import logging
import pathlib
import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from services.auth import get_user_id
from services.constants import ACTIVITY_TYPES, ZERO_COST_ACTIVITY_TYPES
from services.db import get_db
from services.financials import total_cost, cost_by_activity_type
from services.gap_engine import compute_gaps
from services import stage as stage_service

logger = logging.getLogger(__name__)

router = APIRouter()

# Load crop knowledge once at module level — not on every request.
_KNOWLEDGE_PATH = pathlib.Path(__file__).parent.parent / "data" / "crop_knowledge.json"
_knowledge_cache: dict | None = None


def _get_knowledge() -> dict:
    global _knowledge_cache
    if _knowledge_cache is None:
        _knowledge_cache = json.loads(_KNOWLEDGE_PATH.read_text(encoding="utf-8"))
    return _knowledge_cache


# ── Photo upload constants (Requirement 5.6) ─────────────────────────────────

# Maximum allowed photo size: 10 MB.
_MAX_PHOTO_BYTES = 10 * 1024 * 1024

# Allowed MIME types and their magic-byte signatures.
_MIME_SIGNATURES: dict[str, bytes] = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/webp": b"RIFF",  # WEBP starts with RIFF; WEBP tag at bytes 8-12
}
_WEBP_TAG = b"WEBP"


def _detect_mime_from_magic_bytes(data: bytes) -> Optional[str]:
    """Detect image MIME type from the file's magic bytes.

    This is more reliable than the Content-Type header or file extension, which
    can both be spoofed. Returns one of 'image/jpeg', 'image/png', 'image/webp',
    or None if the bytes do not match any allowed format.

    Requirement 5.6: verify the file's actual file signature.
    """
    if data[:3] == _MIME_SIGNATURES["image/jpeg"]:
        return "image/jpeg"
    if data[:8] == _MIME_SIGNATURES["image/png"]:
        return "image/png"
    if data[:4] == _MIME_SIGNATURES["image/webp"] and data[8:12] == _WEBP_TAG:
        return "image/webp"
    return None


def _strip_exif_gps(image_bytes: bytes) -> bytes:
    """Strip EXIF GPS metadata from an image using Pillow.

    Re-encodes the image without any EXIF data, which removes GPS coordinates,
    camera info, and other metadata. The pixel data is preserved. EXIF-based
    orientation is applied before stripping so the visual orientation is kept.

    Requirement 5.6: strip EXIF GPS metadata unless the Farmer explicitly retains it.
    """
    from PIL import Image, ImageOps

    img = Image.open(io.BytesIO(image_bytes))
    # Apply orientation from EXIF (if any) so the image isn't rotated wrong
    # after we strip the EXIF orientation tag.
    img = ImageOps.exif_transpose(img)

    fmt = img.format or "JPEG"
    output = io.BytesIO()
    # Saving without the exif= parameter drops all metadata including GPS.
    if fmt == "JPEG":
        img.save(output, format="JPEG", quality=95)
    else:
        img.save(output, format=fmt)
    return output.getvalue()


# ── Models ────────────────────────────────────────────────────────────────────

class ActivityIn(BaseModel):
    activity_type: str
    quantity: float = Field(ge=0, description="Quantity applied. Must be >= 0.")
    unit: Optional[str] = None
    cost: float = Field(ge=0, description="Cost in INR. Must be >= 0.")
    notes: Optional[str] = None
    status: str = Field(
        default="recorded",
        description="Activity status: 'planned' or 'recorded'. "
                    "A planned activity is NOT evidence the operation was performed.",
    )
    plot_id: Optional[str] = None
    method: Optional[str] = None
    actor: Optional[str] = None


class ActivityOut(BaseModel):
    id: str
    activity_type: str
    quantity: float
    unit: Optional[str]
    cost: float
    notes: Optional[str]
    status: str
    plot_id: Optional[str] = None
    method: Optional[str] = None
    actor: Optional[str] = None
    photo_storage_key: Optional[str] = None
    logged_date: str
    created_at: str


class ActivityUpdate(BaseModel):
    """Partial update model for PUT /api/farmers/me/activities/{id}.

    Only fields that are present (not None) are updated. Fields absent from the
    request body are left unchanged. Each changed field triggers an audit log
    row before the update is applied (Requirement 5.4).
    """
    activity_type: Optional[str] = None
    quantity: Optional[float] = Field(default=None, ge=0)
    unit: Optional[str] = None
    cost: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = None
    status: Optional[str] = None
    plot_id: Optional[str] = None
    method: Optional[str] = None
    actor: Optional[str] = None


class SpendingOut(BaseModel):
    total_cost: float
    by_type: dict
    currency: str = "INR"


class GapOut(BaseModel):
    activity_type: str
    expected: float
    actual: float
    gap: float
    unit: str
    status: str
    message: Optional[str] = None


class PhotoUploadResponse(BaseModel):
    storage_key: str
    mime_type: str
    size_bytes: int


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_farmer(user_id: str) -> dict:
    db = get_db()
    try:
        result = (
            db.table("farmers")
            .select("id, crop, plant_count, sowing_date")
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


def _get_activities(
    farmer_id: str,
    plot_id: Optional[str] = None,
    activity_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> list[dict]:
    """Fetch activities for a farmer with optional filters.

    Requirement 5.5: support filtering by plot, activity_type, and date range.
    Timeline is always sorted by logged_date ascending (Requirement 5.5).
    """
    db = get_db()
    try:
        query = (
            db.table("farm_activities")
            .select("*")
            .eq("farmer_id", farmer_id)
        )
        if plot_id is not None:
            query = query.eq("plot_id", plot_id)
        if activity_type is not None:
            query = query.eq("activity_type", activity_type)
        if date_from is not None:
            query = query.gte("logged_date", date_from)
        if date_to is not None:
            query = query.lte("logged_date", date_to)

        # Timeline ordering: ascending by logged_date (Requirement 5.5).
        # This ensures the activity history reads chronologically from oldest
        # to newest — the farmer sees a proper timeline, not reverse-chronological.
        result = query.order("logged_date", desc=False).execute()
        return result.data or []
    except Exception as exc:
        logger.error("DB select activities failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")


def _row_to_activity_out(row: dict) -> ActivityOut:
    """Convert a DB row dict to an ActivityOut model."""
    return ActivityOut(
        id=row["id"],
        activity_type=row["activity_type"],
        quantity=float(row["quantity"]),
        unit=row.get("unit"),
        cost=float(row["cost"]),
        notes=row.get("notes"),
        status=row.get("status", "recorded"),
        plot_id=row.get("plot_id"),
        method=row.get("method"),
        actor=row.get("actor"),
        photo_storage_key=row.get("photo_storage_key"),
        logged_date=str(row["logged_date"]),
        created_at=str(row["created_at"]),
    )


def _build_audit_entry(
    activity_id: str,
    user_id: str,
    field_name: str,
    old_value,
    new_value,
) -> dict:
    """Build an activity_audit_log row dict.

    Requirement 5.4: preserve original values in an immutable audit entry.
    """
    return {
        "activity_id": activity_id,
        "user_id": user_id,
        "field_name": field_name,
        "old_value": str(old_value) if old_value is not None else None,
        "new_value": str(new_value) if new_value is not None else None,
    }


# ── GET /api/farmers/me/activities ───────────────────────────────────────────

@router.get("/farmers/me/activities", response_model=List[ActivityOut])
def list_activities(
    plot_id: Optional[str] = None,
    activity_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user_id: str = Depends(get_user_id),
) -> List[ActivityOut]:
    """List activities for the authenticated farmer.

    Supports optional filtering by plot_id, activity_type, and date range
    (date_from / date_to as YYYY-MM-DD). Results are sorted by logged_date
    ascending to form a chronological timeline (Requirement 5.5).

    Multi-tenant isolation: user_id comes from the JWT, never the request body.
    """
    farmer = _get_farmer(user_id)
    activities = _get_activities(
        farmer_id=farmer["id"],
        plot_id=plot_id,
        activity_type=activity_type,
        date_from=date_from,
        date_to=date_to,
    )
    return [_row_to_activity_out(a) for a in activities]


# ── POST /api/farmers/me/activities ──────────────────────────────────────────

@router.post("/farmers/me/activities", response_model=ActivityOut)
def log_activity(
    body: ActivityIn,
    user_id: str = Depends(get_user_id),
) -> ActivityOut:
    """Log a farm activity.

    Business rules:
      - Irrigation cost is always stored as 0 regardless of what was submitted.
        The original submitted cost is preserved in original_cost and noted in
        the notes field for audit purposes (Requirement 5.3).
      - activity_type must be in the ACTIVITY_TYPES controlled vocabulary (Req 5.2).
      - status distinguishes 'planned' from 'recorded' activities (Requirement 5.7).
    """
    db = get_db()

    if body.activity_type not in ACTIVITY_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"activity_type must be one of: {', '.join(ACTIVITY_TYPES)}",
        )

    # Validate status is one of the allowed values.
    if body.status not in ("planned", "recorded"):
        raise HTTPException(
            status_code=422,
            detail="status must be one of: planned, recorded",
        )

    # Enforce zero cost for irrigation — backend rule, not just a frontend hint.
    # Requirement 5.3: record the received value in notes + original_cost for audit.
    is_irrigation = body.activity_type in ZERO_COST_ACTIVITY_TYPES
    effective_cost = 0.0 if is_irrigation else body.cost
    original_cost = body.cost if (is_irrigation and body.cost != 0.0) else None

    # Append an audit note when irrigation cost was overridden (Requirement 5.3).
    notes = body.notes
    if is_irrigation and body.cost > 0.0:
        override_note = (
            f"[Audit] Submitted cost ₹{body.cost:.2f} overridden to ₹0.00 "
            f"(water is free)."
        )
        notes = f"{notes}\n{override_note}" if notes else override_note

    farmer = _get_farmer(user_id)

    payload = {
        "farmer_id":     farmer["id"],
        "activity_type": body.activity_type,
        "quantity":      body.quantity,
        "unit":          body.unit,
        "cost":          effective_cost,
        "notes":         notes,
        "status":        body.status,
        "plot_id":       body.plot_id,
        "method":        body.method,
        "actor":         body.actor,
        "original_cost":  original_cost,
        "logged_date":   str(date.today()),
    }

    try:
        result = db.table("farm_activities").insert(payload).execute()
    except Exception as exc:
        logger.error("DB insert activity failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    row = result.data[0]
    return _row_to_activity_out(row)


# ── PUT /api/farmers/me/activities/{id} ───────────────────────────────────────

# Fields that can be updated via PUT and their normalisation for audit comparison.
_UPDATABLE_FIELDS = [
    "activity_type", "quantity", "unit", "cost", "notes",
    "status", "plot_id", "method", "actor",
]


@router.put("/farmers/me/activities/{activity_id}", response_model=ActivityOut)
def update_activity(
    activity_id: str,
    body: ActivityUpdate,
    user_id: str = Depends(get_user_id),
) -> ActivityOut:
    """Edit an existing activity record.

    Requirement 5.4: For each field that changes, an immutable activity_audit_log
    row is written BEFORE the field update is applied. This preserves the full
    history of changes.

    Multi-tenant isolation: the activity must belong to the authenticated farmer
    (verified via farmer_id → user_id). A mismatch returns 404, not 403, to avoid
    confirming the resource exists (IDOR prevention, Requirement 3.3).

    Requirement 5.3: If activity_type is changed to Irrigation or is already
    Irrigation and cost is updated, the cost is overridden to 0 and the original
    value is recorded.
    """
    db = get_db()

    farmer = _get_farmer(user_id)

    # Fetch the existing activity, verifying ownership via farmer_id.
    try:
        result = (
            db.table("farm_activities")
            .select("*")
            .eq("id", activity_id)
            .eq("farmer_id", farmer["id"])
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        logger.error("DB select activity for update failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    # 404 for non-existent or wrong-owner (IDOR prevention).
    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Activity not found.")

    existing = result.data

    # Validate activity_type if it's being changed.
    update_data = body.model_dump(exclude_unset=True)
    if "activity_type" in update_data and update_data["activity_type"] is not None:
        if update_data["activity_type"] not in ACTIVITY_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"activity_type must be one of: {', '.join(ACTIVITY_TYPES)}",
            )

    # Validate status if it's being changed.
    if "status" in update_data and update_data["status"] is not None:
        if update_data["status"] not in ("planned", "recorded"):
            raise HTTPException(
                status_code=422,
                detail="status must be one of: planned, recorded",
            )

    # Determine the effective activity_type for irrigation cost override.
    effective_activity_type = update_data.get("activity_type", existing["activity_type"])
    is_irrigation = effective_activity_type in ZERO_COST_ACTIVITY_TYPES

    # Irrigation cost override on update (Requirement 5.3).
    if "cost" in update_data and update_data["cost"] is not None:
        if is_irrigation:
            submitted_cost = update_data["cost"]
            if submitted_cost > 0.0:
                override_note = (
                    f"[Audit] Submitted cost ₹{submitted_cost:.2f} overridden to "
                    f"₹0.00 (water is free)."
                )
                existing_notes = update_data.get("notes", existing.get("notes"))
                update_data["notes"] = (
                    f"{existing_notes}\n{override_note}"
                    if existing_notes
                    else override_note
                )
                # Preserve the original cost for audit.
                update_data["original_cost"] = submitted_cost
            update_data["cost"] = 0.0

    # If activity_type is being changed TO irrigation, also override existing cost.
    if (
        "activity_type" in update_data
        and update_data["activity_type"] in ZERO_COST_ACTIVITY_TYPES
        and "cost" not in update_data
    ):
        existing_cost = float(existing.get("cost", 0))
        if existing_cost > 0.0:
            override_note = (
                f"[Audit] Cost ₹{existing_cost:.2f} overridden to ₹0.00 "
                f"(activity type changed to Irrigation — water is free)."
            )
            existing_notes = update_data.get("notes", existing.get("notes"))
            update_data["notes"] = (
                f"{existing_notes}\n{override_note}"
                if existing_notes
                else override_note
            )
            update_data["original_cost"] = existing_cost
            update_data["cost"] = 0.0

    # Build audit log entries for each changed field (Requirement 5.4).
    audit_entries: list[dict] = []
    for field_name in _UPDATABLE_FIELDS:
        if field_name not in update_data:
            continue
        old_val = existing.get(field_name)
        new_val = update_data[field_name]
        # Normalise for comparison — compare as strings to handle numeric types.
        old_str = str(old_val) if old_val is not None else None
        new_str = str(new_val) if new_val is not None else None
        if old_str != new_str:
            audit_entries.append(
                _build_audit_entry(activity_id, user_id, field_name, old_val, new_val)
            )

    # Write audit log rows BEFORE applying the update (Requirement 5.4).
    if audit_entries:
        try:
            db.table("activity_audit_log").insert(audit_entries).execute()
        except Exception as exc:
            logger.error("DB insert audit log failed: %s", exc)
            raise HTTPException(status_code=500, detail="Database error.")

    # Apply the update.
    try:
        update_result = (
            db.table("farm_activities")
            .update(update_data)
            .eq("id", activity_id)
            .eq("farmer_id", farmer["id"])
            .execute()
        )
    except Exception as exc:
        logger.error("DB update activity failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    if not update_result.data:
        raise HTTPException(status_code=404, detail="Activity not found.")

    return _row_to_activity_out(update_result.data[0])


# ── POST /api/farmers/me/activities/{id}/photo ──────────────────────────────

@router.post(
    "/farmers/me/activities/{activity_id}/photo",
    response_model=PhotoUploadResponse,
)
def upload_activity_photo(
    activity_id: str,
    file: UploadFile = File(...),
    user_id: str = Depends(get_user_id),
) -> PhotoUploadResponse:
    """Upload a photo attachment for an activity.

    Requirement 5.6:
      - Validates MIME type via magic bytes (not just file extension/Content-Type).
      - Rejects files larger than 10 MB with HTTP 422.
      - Generates a UUID-based non-guessable storage key.
      - Strips EXIF GPS metadata via Pillow.
      - Stores the storage key on the activity record; the photo is served
        via a short-lived signed URL after an authorisation check.
    """
    db = get_db()

    farmer = _get_farmer(user_id)

    # Verify the activity belongs to the authenticated farmer (IDOR prevention).
    try:
        result = (
            db.table("farm_activities")
            .select("id")
            .eq("id", activity_id)
            .eq("farmer_id", farmer["id"])
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        logger.error("DB select activity for photo upload failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Activity not found.")

    # Read the uploaded file bytes.
    raw_bytes = file.file.read()

    # Reject files exceeding 10 MB (Requirement 5.6).
    if len(raw_bytes) > _MAX_PHOTO_BYTES:
        raise HTTPException(
            status_code=422,
            detail=f"File exceeds maximum size of 10 MB (received {len(raw_bytes)} bytes).",
        )

    # Validate MIME via magic bytes (Requirement 5.6).
    detected_mime = _detect_mime_from_magic_bytes(raw_bytes)
    if detected_mime is None:
        raise HTTPException(
            status_code=422,
            detail="File must be a JPEG, PNG, or WEBP image (verified by file signature).",
        )

    # Strip EXIF GPS metadata (Requirement 5.6).
    try:
        cleaned_bytes = _strip_exif_gps(raw_bytes)
    except Exception as exc:
        logger.error("EXIF strip failed: %s", exc)
        raise HTTPException(
            status_code=422,
            detail="Could not process image file. Ensure it is a valid image.",
        )

    # Generate a UUID-based non-guessable storage key (Requirement 5.6).
    extension_map = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }
    ext = extension_map[detected_mime]
    storage_key = f"activities/{activity_id}/{uuid.uuid4().hex}.{ext}"

    # Persist the storage key on the activity record.
    # In production, cleaned_bytes would be uploaded to object storage (S3/Supabase
    # Storage) at this key. For now, we store the key so a signed URL can be
    # generated later.
    try:
        db.table("farm_activities").update(
            {"photo_storage_key": storage_key}
        ).eq("id", activity_id).eq("farmer_id", farmer["id"]).execute()
    except Exception as exc:
        logger.error("DB update photo key failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    return PhotoUploadResponse(
        storage_key=storage_key,
        mime_type=detected_mime,
        size_bytes=len(cleaned_bytes),
    )


# ── GET /api/farmers/me/spending ─────────────────────────────────────────────

@router.get("/farmers/me/spending", response_model=SpendingOut)
def get_spending(user_id: str = Depends(get_user_id)) -> SpendingOut:
    farmer = _get_farmer(user_id)
    activities = _get_activities(farmer["id"])
    return SpendingOut(
        total_cost=round(total_cost(activities), 2),
        by_type={k: round(v, 2) for k, v in cost_by_activity_type(activities).items()},
    )


# ── GET /api/farmers/me/gaps ─────────────────────────────────────────────────

def _get_plot_by_id(plot_id: str, user_id: str) -> dict:
    """Fetch a plot owned by ``user_id`` for gap computation.

    Requirement 1.8: when a ``plot_id`` is supplied to the gaps endpoint, the
    plant_count (and crop / planting_date) must be sourced from the Plot
    record in the ``plots`` table — never from a hard-coded default such as
    2,100 trees.

    IDOR prevention: the query filters by both ``id`` and ``user_id``; a plot
    belonging to another farmer simply does not match and is reported as
    "not found" (404, not 403).
    """
    db = get_db()
    try:
        result = (
            db.table("plots")
            .select("id, crop, plant_count, planting_date")
            .eq("id", plot_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        logger.error("DB select plot for gaps failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Plot not found.")
    return result.data


@router.get("/farmers/me/gaps", response_model=List[GapOut])
def get_gaps(
    plot_id: Optional[str] = None,
    user_id: str = Depends(get_user_id),
) -> List[GapOut]:
    """Expected-vs-actual input gaps for Fertilizer and Irrigation.

    Requirement 1.8: every farm-specific value used in the calculation —
    including tree count — is derived from the authenticated Farmer's Plot
    record when a ``plot_id`` is supplied, falling back to the flat
    ``farmers`` profile otherwise. A hard-coded default (e.g. 2,100 trees) is
    never used.

    When ``plot_id`` is supplied the crop, planting_date and plant_count come
    from that Plot, and activities are filtered to the plot. Otherwise the
    farmer profile's crop, sowing_date and plant_count are used with all the
    farmer's activities (backward compatible with the legacy single-farmer MVP).
    """
    farmer = _get_farmer(user_id)

    # ── Resolve crop, planting date and plant_count from Plot or farmer ──
    if plot_id is not None:
        plot = _get_plot_by_id(plot_id, user_id)
        crop = plot["crop"]
        planting_date = (
            date.fromisoformat(plot["planting_date"])
            if isinstance(plot["planting_date"], str)
            else plot["planting_date"]
        )
        plant_count = plot["plant_count"]
    else:
        crop = farmer["crop"]
        planting_date = (
            date.fromisoformat(farmer["sowing_date"])
            if isinstance(farmer["sowing_date"], str)
            else farmer["sowing_date"]
        )
        plant_count = farmer["plant_count"]

    try:
        sr = stage_service.get_stage(crop, planting_date)
    except (HTTPException, KeyError) as exc:
        raise HTTPException(status_code=422, detail="Cannot determine crop stage.") from exc

    crop_stages = _get_knowledge()[crop.lower()]["stages"]
    # When a plot is in scope, only its activities are relevant to the gap.
    activities = _get_activities(
        farmer_id=farmer["id"],
        plot_id=plot_id,
    )

    gaps = compute_gaps(
        stages=crop_stages,
        months_elapsed=sr.months_elapsed,
        plant_count=plant_count,
        activities=activities,
    )

    output = []
    for g in gaps:
        message = None
        if g.status == "behind":
            message = f"You may be behind on {g.activity_type.lower()} for this stage."
        output.append(GapOut(
            activity_type=g.activity_type,
            expected=g.expected_kg_or_litres,
            actual=g.actual_kg_or_litres,
            gap=g.gap,
            unit=g.unit,
            status=g.status,
            message=message,
        ))

    return output


# ── GET /api/constants/activity-types ────────────────────────────────────────

@router.get("/constants/activity-types")
def get_activity_types() -> dict:
    """Return the allowed activity types so frontend stays in sync."""
    return {"activity_types": ACTIVITY_TYPES}
