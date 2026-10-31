"""
routers/contact.py — Public contact / join-pilot form endpoint.

Endpoints:
  POST /api/contact
      Stores a contact submission with an explicit consent flag and a
      server-side timestamp. Rate-limited via the `contact_form` category
      (20 submissions / 15 min / IP).

This endpoint is intentionally public (no JWT required) so that visitors
who are not yet farmers can request to join the pilot. All inserts go
through the service-role Supabase client, which bypasses RLS; the table's
RLS policies still deny public reads (see schema.sql).

Requirements: 2.3
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from services.db import get_db
from services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["contact"])


# ── Validation helpers (no external dependency) ──────────────────────────────

# Minimal RFC-5322-ish shape: local@domain.tld with no spaces around "@".
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Phone: an optional leading "+" followed by digits, spaces, hyphens, and
# parentheses — must contain at least 7 digits to be plausible.
_PHONE_RE = re.compile(r"^(?:\+?[\d][\d\s\-()]{6,}\d|[\d]{7,})$")


def _count_digits(value: str) -> int:
    return sum(1 for ch in value if ch.isdigit())


# ── Request model ─────────────────────────────────────────────────────────────

class ContactIn(BaseModel):
    """Contact / join-pilot form payload.

    At least one of ``email`` or ``phone`` must be provided (validated in a
    model validator). ``consent`` defaults to ``True`` — the form's checkbox
    must be checked before submission, and the value is stored verbatim so the
    audit trail records exactly what the visitor agreed to.
    """

    name: str = Field(..., max_length=100)
    email: Optional[str] = None
    phone: Optional[str] = None
    consent: bool = True

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Name is required.")
        return v.strip()

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if v == "":
            return None
        if not _EMAIL_RE.match(v):
            raise ValueError("Email address is not valid.")
        return v

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if v == "":
            return None
        if not _PHONE_RE.match(v) or _count_digits(v) < 7:
            raise ValueError("Phone number is not valid.")
        return v

    @model_validator(mode="after")
    def _at_least_one_contact_method(self) -> "ContactIn":
        if not self.email and not self.phone:
            raise ValueError(
                "At least one contact method (email or phone) is required."
            )
        return self


# ── POST /api/contact ─────────────────────────────────────────────────────────

@router.post("/contact")
def submit_contact(
    body: ContactIn,
    _: None = Depends(RateLimiter("contact_form")),
) -> dict:
    """Store a contact / join-pilot form submission with an explicit consent flag.

    Returns 200 on success and 422 on validation failure (handled by Pydantic).
    Rate-limited to 20 submissions per 15-minute window per IP
    (Requirement 3.8 / 3.9).

    When both an email and a phone are supplied, each is stored as a separate
    row so the full contact detail is preserved in the audit trail.
    """
    db = get_db()

    rows: list[dict] = []
    if body.email:
        rows.append(
            {
                "name": body.name,
                "contact_value": body.email,
                "contact_type": "email",
                "consent": body.consent,
            }
        )
    if body.phone:
        rows.append(
            {
                "name": body.name,
                "contact_value": body.phone,
                "contact_type": "phone",
                "consent": body.consent,
            }
        )

    try:
        db.table("contact_submissions").insert(rows).execute()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to store contact submission: %s", exc)
        raise HTTPException(status_code=500, detail="Could not submit form.")

    logger.info(
        "Contact submission stored for '%s' (%d contact method(s)).",
        body.name,
        len(rows),
    )
    return {"status": "ok", "message": "Thank you — we'll be in touch."}
