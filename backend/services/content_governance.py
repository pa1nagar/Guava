"""
content_governance.py — ContentRecord lifecycle and safety enforcement.

All functions here are pure (no side-effects) except check_and_expire_records,
which writes to the database. This makes the business-logic functions fully
unit-testable without mocking.

Requirements covered: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.9
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Avoid a hard import of supabase at module load time so the service can be
    # imported in unit tests without a live Supabase connection.
    from supabase import Client

# ---------------------------------------------------------------------------
# Permanently blocked content identifiers (Requirement 1.1)
# These records must NEVER be displayed as actionable items, regardless of
# their Content_Status. Stored here so both the router and tests can reference
# the same source of truth.
# ---------------------------------------------------------------------------

PERMANENTLY_BLOCKED_CONTENT_IDENTIFIERS: frozenset[str] = frozenset([
    "frac_irac_rotation_calendar",
    "azoxystrobin_neem_oil_spray",
    "imidacloprid_stem_drench",
    "fixed_weekly_wsf_fertigation",
    "phosphoric_acid_drip_injection",
    "chlorine_dosing_instruction",
    "fixed_per_tree_chemical_dose",
])

# ---------------------------------------------------------------------------
# Required fields for every ContentRecord (Requirement 1.3, 1.5)
# ---------------------------------------------------------------------------

_BASE_REQUIRED_FIELDS: tuple[str, ...] = (
    "record_uid",
    "risk_level",
    "source_org",
    "source_title",
    "source_url",
    "source_section",
    "source_pub_date",
    "review_expiry",
)

# Additional fields required when risk_level == 'HIGH' (Requirement 1.3, 1.6)
_HIGH_RISK_REQUIRED_FIELDS: tuple[str, ...] = (
    "reviewer_name",
    "reviewer_credential",
)

# Fields whose presence is required for a chemical compatibility record to be
# considered fully verified (Requirement 1.9)
_COMPATIBILITY_REQUIRED_FIELDS: tuple[str, ...] = (
    "formulation",        # formulation name and concentration of each constituent
    "ph_ec_range",        # documented water pH and EC range
    "reviewer_name",      # full name of reviewer with HIGH-risk credentials
    "reviewer_credential",
)


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def is_actionable(record: dict) -> bool:
    """Return True only when the record's status is APPROVED.

    Permanently-blocked identifiers are treated as non-actionable regardless
    of their status.

    Property 1: For any record with status != 'APPROVED', this returns False.
    Requirement 1.2
    """
    if record.get("record_uid") in PERMANENTLY_BLOCKED_CONTENT_IDENTIFIERS:
        return False
    return record.get("status") == "APPROVED"


def validate_content_record(record: dict) -> list[str]:
    """Return a list of missing required field names.

    An empty list means the record is valid. A non-empty list contains the
    names of every required field that is absent, None, a non-string type,
    or an empty/whitespace-only string.

    HIGH-risk records additionally require reviewer_name and
    reviewer_credential.

    Property 2: For any record missing any required field, returns a
    non-empty list. Requirement 1.5, 1.6
    """
    missing: list[str] = []

    for field in _BASE_REQUIRED_FIELDS:
        value = record.get(field)
        # Reject None, non-string types, and empty/whitespace-only strings.
        if value is None or not isinstance(value, str) or not value.strip():
            missing.append(field)

    if record.get("risk_level") == "HIGH":
        for field in _HIGH_RISK_REQUIRED_FIELDS:
            value = record.get(field)
            if value is None or not isinstance(value, str) or not value.strip():
                missing.append(field)

    return missing


def should_show_compatibility_warning(record: dict) -> bool:
    """Return True when a chemical compatibility record cannot be trusted.

    Returns True if:
    - status is not APPROVED, OR
    - formulation name/concentration is missing, OR
    - water pH+EC range is missing, OR
    - reviewer name or credential is missing

    Returns False only when ALL of the above conditions are satisfied (i.e.
    the record is fully verified). If the record does not describe chemical
    compatibility the caller should not invoke this function, but it will
    conservatively return True for non-APPROVED records.

    Requirement 1.9
    """
    if record.get("status") != "APPROVED":
        return True

    for field in _COMPATIBILITY_REQUIRED_FIELDS:
        value = record.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            return True

    return False


# ---------------------------------------------------------------------------
# Scheduler-integrated function (requires database access)
# ---------------------------------------------------------------------------


def check_and_expire_records(db: "Client") -> int:
    """Set status = 'EXPIRED' for all APPROVED records past their review_expiry.

    Designed to be called once per day by APScheduler or a Render cron job.
    Returns the count of records that were expired in this run.

    Requirement 1.4
    """
    today_str = date.today().isoformat()  # 'YYYY-MM-DD'

    # Fetch all APPROVED records whose expiry date is strictly before today.
    response = (
        db.table("content_records")
        .select("id")
        .eq("status", "APPROVED")
        .lt("review_expiry", today_str)
        .execute()
    )

    expired_ids: list[str] = [row["id"] for row in (response.data or [])]

    if not expired_ids:
        return 0

    # Bulk-update to EXPIRED.
    db.table("content_records").update({"status": "EXPIRED"}).in_(
        "id", expired_ids
    ).execute()

    # Insert audit log entries.
    audit_rows = [
        {
            "content_record_id": record_id,
            "old_status": "APPROVED",
            "new_status": "EXPIRED",
            "changed_by": "scheduler",
            "reason": "review_expiry date passed",
        }
        for record_id in expired_ids
    ]
    db.table("content_audit_log").insert(audit_rows).execute()

    return len(expired_ids)
