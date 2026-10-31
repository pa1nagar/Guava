"""
observations.py — Crop health observation endpoints.

GET  /api/farmers/me/observations                          List observations.
POST /api/farmers/me/observations                          Create a new observation.
POST /api/farmers/me/observations/{id}/photos              Upload a photo.
GET  /api/farmers/me/observations/{id}/photos/{photo_id}  Get a signed URL for a photo.

Business rules:
  - ai_analysis_label defaults to "Preliminary observation — not a diagnosis"
    and is never allowed to be empty or None after save (Requirement 7.1).
  - symptom_description has no controlled vocabulary: "unknown / not sure"
    is a valid value (Requirement 7.2).
  - Photo upload validates MIME via magic bytes, rejects > 10 MB, strips EXIF
    GPS metadata, and uses a UUID-based non-guessable storage key (reuses
    the same logic as activities.py — Requirement 7.4).
  - Original photo and AI-processed version are stored as separate rows in
    observation_photos with the is_ai_version flag (Requirement 7.4).
  - All queries filter by user_id = <jwt.sub> — return 404 on mismatch to
    prevent IDOR (Requirement 3.3).

Requirements: 7.1, 7.2, 7.4
"""

# ── Multi-tenant isolation ──────────────────────────────────────────────────
# Security: user_id is always derived from JWT via Depends(get_user_id).
# It is NEVER read from the request body. All DB queries filter by user_id.
# IDOR attempts return 404 (not 403) to avoid confirming resource existence.
# Requirements: 3.2, 3.3, 3.4

import io
import logging
import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator

from services.auth import get_user_id
from services.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Default label (Requirement 7.1) ──────────────────────────────────────────
_DEFAULT_AI_LABEL = "Preliminary observation — not a diagnosis"

# ── Photo upload constants (reused from activities.py — Requirement 7.4) ─────
_MAX_PHOTO_BYTES = 10 * 1024 * 1024

_MIME_SIGNATURES: dict[str, bytes] = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/webp": b"RIFF",
}
_WEBP_TAG = b"WEBP"


def _detect_mime_from_magic_bytes(data: bytes) -> Optional[str]:
    """Detect MIME type from the file's magic bytes.

    Returns 'image/jpeg', 'image/png', 'image/webp', or None.
    Requirement 7.4: verify actual file signature, not extension.
    """
    if len(data) >= 3 and data[:3] == _MIME_SIGNATURES["image/jpeg"]:
        return "image/jpeg"
    if len(data) >= 8 and data[:8] == _MIME_SIGNATURES["image/png"]:
        return "image/png"
    if len(data) >= 12 and data[:4] == _MIME_SIGNATURES["image/webp"] and data[8:12] == _WEBP_TAG:
        return "image/webp"
    return None


def _strip_exif_gps(image_bytes: bytes) -> bytes:
    """Strip EXIF GPS metadata from an image using Pillow.

    Re-encodes without EXIF so GPS coordinates are removed.
    Requirement 7.4: strip EXIF GPS metadata.
    """
    from PIL import Image, ImageOps

    img = Image.open(io.BytesIO(image_bytes))
    img = ImageOps.exif_transpose(img)

    fmt = img.format or "JPEG"
    output = io.BytesIO()
    if fmt == "JPEG":
        img.save(output, format="JPEG", quality=95)
    else:
        img.save(output, format=fmt)
    return output.getvalue()


# ── Models ────────────────────────────────────────────────────────────────────

class ObservationIn(BaseModel):
    """Input model for creating a new observation.

    Requirement 7.2: symptom_description has no controlled vocabulary;
    "unknown / not sure" is explicitly valid.
    """
    observed_date: str = Field(
        description="Date of observation in YYYY-MM-DD format."
    )
    plot_id: Optional[str] = None
    plant_part: Optional[str] = None
    symptom_description: Optional[str] = Field(
        default=None,
        description="Free-text symptom description. 'unknown / not sure' is a valid value.",
    )
    onset_date: Optional[str] = None
    spread_pattern: Optional[str] = None
    severity: Optional[str] = None
    trees_sampled: Optional[int] = Field(default=None, ge=0)
    trees_affected: Optional[int] = Field(default=None, ge=0)
    weather_notes: Optional[str] = None
    recent_input_notes: Optional[str] = None
    observer_name: Optional[str] = None
    ai_analysis: Optional[str] = None
    ai_analysis_label: Optional[str] = Field(
        default=None,
        description=(
            "Label shown alongside ai_analysis. "
            "Defaults to 'Preliminary observation — not a diagnosis' if not provided "
            "or empty. Never stored as empty/None (Requirement 7.1)."
        ),
    )

    @field_validator("ai_analysis_label", mode="before")
    @classmethod
    def coerce_empty_label_to_default(cls, v):
        """Ensure ai_analysis_label is never empty — default to the safety disclaimer.

        Requirement 7.1: never let ai_analysis_label be empty.
        """
        if not v or not str(v).strip():
            return _DEFAULT_AI_LABEL
        return v


class ObservationOut(BaseModel):
    id: str
    user_id: str
    plot_id: Optional[str] = None
    observed_date: str
    plant_part: Optional[str] = None
    symptom_description: Optional[str] = None
    onset_date: Optional[str] = None
    spread_pattern: Optional[str] = None
    severity: Optional[str] = None
    trees_sampled: Optional[int] = None
    trees_affected: Optional[int] = None
    weather_notes: Optional[str] = None
    recent_input_notes: Optional[str] = None
    observer_name: Optional[str] = None
    ai_analysis: Optional[str] = None
    ai_analysis_label: str
    created_at: str


class ObservationPhotoOut(BaseModel):
    id: str
    observation_id: str
    user_id: str
    storage_key: str
    is_ai_version: bool
    created_at: str


class PhotoUploadResponse(BaseModel):
    storage_key: str
    mime_type: str
    size_bytes: int
    is_ai_version: bool


class SignedUrlResponse(BaseModel):
    photo_id: str
    storage_key: str
    # In production this would be a real short-lived signed URL from
    # Supabase Storage. Returned as the key for now since we don't have
    # a live storage bucket in tests/development.
    signed_url: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row_to_observation_out(row: dict) -> ObservationOut:
    """Convert a DB row to ObservationOut, applying the ai_analysis_label default.

    Requirement 7.1: label must never be empty even for legacy rows.
    """
    label = row.get("ai_analysis_label") or _DEFAULT_AI_LABEL
    return ObservationOut(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        plot_id=str(row["plot_id"]) if row.get("plot_id") else None,
        observed_date=str(row["observed_date"]),
        plant_part=row.get("plant_part"),
        symptom_description=row.get("symptom_description"),
        onset_date=str(row["onset_date"]) if row.get("onset_date") else None,
        spread_pattern=row.get("spread_pattern"),
        severity=row.get("severity"),
        trees_sampled=row.get("trees_sampled"),
        trees_affected=row.get("trees_affected"),
        weather_notes=row.get("weather_notes"),
        recent_input_notes=row.get("recent_input_notes"),
        observer_name=row.get("observer_name"),
        ai_analysis=row.get("ai_analysis"),
        ai_analysis_label=label,
        created_at=str(row["created_at"]),
    )


def _get_observation(observation_id: str, user_id: str) -> dict:
    """Fetch a single observation and verify ownership.

    Returns the DB row dict. Raises 404 if not found or not owned by user_id.
    IDOR prevention: 404 (not 403) so the resource's existence isn't confirmed.
    """
    db = get_db()
    try:
        result = (
            db.table("observations")
            .select("*")
            .eq("id", observation_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        logger.error("DB select observation failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Observation not found.")
    return result.data


# ── GET /api/farmers/me/observations ─────────────────────────────────────────

@router.get("/farmers/me/observations", response_model=List[ObservationOut])
def list_observations(
    plot_id: Optional[str] = None,
    user_id: str = Depends(get_user_id),
) -> List[ObservationOut]:
    """List all crop health observations for the authenticated farmer.

    Supports optional filtering by plot_id.

    Multi-tenant isolation: user_id comes from the JWT, never the request body.
    Requirement 7.1: ai_analysis_label is always present in response.
    """
    db = get_db()
    try:
        query = (
            db.table("observations")
            .select("*")
            .eq("user_id", user_id)
            .order("observed_date", desc=False)
        )
        if plot_id is not None:
            query = query.eq("plot_id", plot_id)
        result = query.execute()
        rows = result.data or []
    except Exception as exc:
        logger.error("DB select observations failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    return [_row_to_observation_out(r) for r in rows]


# ── POST /api/farmers/me/observations ────────────────────────────────────────

@router.post("/farmers/me/observations", response_model=ObservationOut, status_code=201)
def create_observation(
    body: ObservationIn,
    user_id: str = Depends(get_user_id),
) -> ObservationOut:
    """Create a new crop health observation.

    Requirement 7.1: ai_analysis_label always stored as the default disclaimer
    when not provided or empty.
    Requirement 7.2: symptom_description has no controlled vocabulary.

    Multi-tenant isolation: user_id comes from the JWT, never the request body.
    """
    db = get_db()

    # ai_analysis_label is normalised by the Pydantic validator — it will
    # never be None or empty by the time we reach here (Requirement 7.1).
    label = body.ai_analysis_label or _DEFAULT_AI_LABEL

    payload = {
        "user_id":              user_id,
        "plot_id":              body.plot_id,
        "observed_date":        body.observed_date,
        "plant_part":           body.plant_part,
        "symptom_description":  body.symptom_description,
        "onset_date":           body.onset_date,
        "spread_pattern":       body.spread_pattern,
        "severity":             body.severity,
        "trees_sampled":        body.trees_sampled,
        "trees_affected":       body.trees_affected,
        "weather_notes":        body.weather_notes,
        "recent_input_notes":   body.recent_input_notes,
        "observer_name":        body.observer_name,
        "ai_analysis":          body.ai_analysis,
        "ai_analysis_label":    label,
    }

    try:
        result = db.table("observations").insert(payload).execute()
    except Exception as exc:
        logger.error("DB insert observation failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    row = result.data[0]
    return _row_to_observation_out(row)


# ── POST /api/farmers/me/observations/{id}/photos ────────────────────────────

@router.post(
    "/farmers/me/observations/{observation_id}/photos",
    response_model=PhotoUploadResponse,
    status_code=201,
)
def upload_observation_photo(
    observation_id: str,
    file: UploadFile = File(...),
    is_ai_version: bool = False,
    user_id: str = Depends(get_user_id),
) -> PhotoUploadResponse:
    """Upload a photo for a crop health observation.

    Requirement 7.4:
      - Validates MIME via magic bytes (not just file extension/Content-Type).
      - Rejects files > 10 MB with HTTP 422.
      - Generates a UUID-based non-guessable storage key.
      - Strips EXIF GPS metadata via Pillow.
      - Original and AI-processed versions stored as separate rows with
        the is_ai_version flag.

    Multi-tenant isolation: ownership of observation_id is verified before
    upload. Mismatch returns 404.
    """
    db = get_db()

    # Verify observation ownership (IDOR prevention).
    _get_observation(observation_id, user_id)

    # Read the uploaded file bytes.
    raw_bytes = file.file.read()

    # Reject files exceeding 10 MB (Requirement 7.4 / 5.6).
    if len(raw_bytes) > _MAX_PHOTO_BYTES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"File exceeds maximum size of 10 MB "
                f"(received {len(raw_bytes)} bytes)."
            ),
        )

    # Validate MIME via magic bytes (Requirement 7.4 / 5.6).
    detected_mime = _detect_mime_from_magic_bytes(raw_bytes)
    if detected_mime is None:
        raise HTTPException(
            status_code=422,
            detail="File must be a JPEG, PNG, or WEBP image (verified by file signature).",
        )

    # Strip EXIF GPS metadata (Requirement 7.4 / 5.6).
    try:
        cleaned_bytes = _strip_exif_gps(raw_bytes)
    except Exception as exc:
        logger.error("EXIF strip failed for observation photo: %s", exc)
        raise HTTPException(
            status_code=422,
            detail="Could not process image file. Ensure it is a valid image.",
        )

    # Generate a UUID-based non-guessable storage key (Requirement 7.4 / 5.6).
    extension_map = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }
    ext = extension_map[detected_mime]
    version_tag = "ai" if is_ai_version else "original"
    storage_key = (
        f"observations/{observation_id}/{version_tag}/{uuid.uuid4().hex}.{ext}"
    )

    # Insert a row in observation_photos for this version.
    # Original and AI-processed versions are separate rows (Requirement 7.4).
    photo_payload = {
        "observation_id": observation_id,
        "user_id":        user_id,
        "storage_key":    storage_key,
        "is_ai_version":  is_ai_version,
    }

    try:
        db.table("observation_photos").insert(photo_payload).execute()
    except Exception as exc:
        logger.error("DB insert observation photo failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    # In production, cleaned_bytes would be uploaded to Supabase Storage at
    # this key. We store the key only; serving is done via the GET endpoint.
    logger.info(
        "Observation photo stored: observation_id=%s is_ai_version=%s key=%s size=%d",
        observation_id,
        is_ai_version,
        storage_key,
        len(cleaned_bytes),
    )

    return PhotoUploadResponse(
        storage_key=storage_key,
        mime_type=detected_mime,
        size_bytes=len(cleaned_bytes),
        is_ai_version=is_ai_version,
    )


# ── GET /api/farmers/me/observations/{id}/photos/{photo_id} ──────────────────

@router.get(
    "/farmers/me/observations/{observation_id}/photos/{photo_id}",
    response_model=SignedUrlResponse,
)
def get_observation_photo_url(
    observation_id: str,
    photo_id: str,
    user_id: str = Depends(get_user_id),
) -> SignedUrlResponse:
    """Return a short-lived signed URL for an observation photo.

    Requirement 7.4: ownership is verified for both the observation and the
    photo before returning the URL. Mismatch returns 404 (IDOR prevention).

    In production this would generate a real short-lived signed URL from
    Supabase Storage. For now the storage_key is returned as the 'signed_url'
    since no live storage bucket exists in development/tests.
    """
    db = get_db()

    # Verify the observation is owned by this user.
    _get_observation(observation_id, user_id)

    # Verify the photo belongs to this observation AND this user.
    try:
        result = (
            db.table("observation_photos")
            .select("*")
            .eq("id", photo_id)
            .eq("observation_id", observation_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        logger.error("DB select observation photo failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Photo not found.")

    photo = result.data

    # In production: generate a short-lived signed URL via Supabase Storage.
    # For now, return the storage key as a placeholder URL.
    storage_key = photo["storage_key"]
    signed_url = storage_key  # placeholder — replace with real signed URL in prod

    return SignedUrlResponse(
        photo_id=str(photo["id"]),
        storage_key=storage_key,
        signed_url=signed_url,
    )
