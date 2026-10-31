"""
test_content_governance_properties.py — Property-based tests for content_governance.py

Uses Hypothesis to verify universal properties across a wide range of inputs.
Each test is tagged with the feature and property it validates.
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from services.content_governance import (
    PERMANENTLY_BLOCKED_CONTENT_IDENTIFIERS,
    is_actionable,
    validate_content_record,
)
from services.constants import CONTENT_STATUSES, RISK_LEVELS

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

# All statuses that are NOT APPROVED — records in these states must never
# be actionable regardless of any other field value.
_NON_APPROVED_STATUSES = [s for s in CONTENT_STATUSES if s != "APPROVED"]

non_approved_status_st = st.sampled_from(_NON_APPROVED_STATUSES)

# A plausible record_uid that is NOT in the permanently-blocked list.
safe_uid_st = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_"),
    min_size=1,
    max_size=80,
).filter(lambda uid: uid not in PERMANENTLY_BLOCKED_CONTENT_IDENTIFIERS)

# Generic non-empty text for source fields.
nonempty_text_st = st.text(min_size=1, max_size=200).map(str.strip).filter(bool)

# ISO date string strategy (YYYY-MM-DD).
date_str_st = st.dates().map(lambda d: d.isoformat())

# A fully valid base record (all required fields present, any risk level).
def valid_base_record_st(risk_level: str | None = None) -> st.SearchStrategy:
    risk_st = st.just(risk_level) if risk_level else st.sampled_from(RISK_LEVELS)
    return st.fixed_dictionaries(
        {
            "record_uid": safe_uid_st,
            "risk_level": risk_st,
            "source_org": nonempty_text_st,
            "source_title": nonempty_text_st,
            "source_url": nonempty_text_st,
            "source_section": nonempty_text_st,
            "source_pub_date": date_str_st,
            "review_expiry": date_str_st,
        }
    )


def valid_high_risk_record_st() -> st.SearchStrategy:
    """A fully valid HIGH-risk record including reviewer credentials."""
    return st.fixed_dictionaries(
        {
            "record_uid": safe_uid_st,
            "risk_level": st.just("HIGH"),
            "source_org": nonempty_text_st,
            "source_title": nonempty_text_st,
            "source_url": nonempty_text_st,
            "source_section": nonempty_text_st,
            "source_pub_date": date_str_st,
            "review_expiry": date_str_st,
            "reviewer_name": nonempty_text_st,
            "reviewer_credential": nonempty_text_st,
        }
    )


# ---------------------------------------------------------------------------
# Property 1: Non-APPROVED content records are never actionable
# Feature: smart-farmer-app, Property 1: Non-APPROVED content records are never actionable
# Validates: Requirements 1.2
# ---------------------------------------------------------------------------


# Feature: smart-farmer-app, Property 1: Non-APPROVED content records are never actionable
@given(record=valid_base_record_st(), status=non_approved_status_st)
@settings(max_examples=200)
def test_non_approved_records_are_never_actionable(record: dict, status: str):
    """For ANY record whose status is not APPROVED, is_actionable must return False.

    This holds regardless of all other field values (risk level, source fields,
    reviewer credentials, etc.).

    Validates: Requirements 1.2
    """
    record["status"] = status
    assert is_actionable(record) is False, (
        f"Expected is_actionable to be False for status={status!r}, got True. "
        f"Record uid={record.get('record_uid')!r}"
    )


# Feature: smart-farmer-app, Property 1: Non-APPROVED content records are never actionable
@given(record=valid_base_record_st())
@settings(max_examples=200)
def test_approved_records_are_actionable(record: dict):
    """A record with status APPROVED and no blocked uid must be actionable.

    This is the positive counterpart: ensures we don't over-block legitimate
    APPROVED records.

    Validates: Requirements 1.2
    """
    record["status"] = "APPROVED"
    # Safe uid strategy guarantees no blocked uid is generated.
    assert is_actionable(record) is True, (
        f"Expected is_actionable to be True for APPROVED record, got False. "
        f"Record uid={record.get('record_uid')!r}"
    )


# Feature: smart-farmer-app, Property 1: Non-APPROVED content records are never actionable
@given(status=non_approved_status_st)
@settings(max_examples=200)
def test_permanently_blocked_identifiers_always_non_actionable(status: str):
    """Every permanently-blocked uid must be non-actionable even if status is APPROVED.

    Validates: Requirements 1.1, 1.2
    """
    for uid in PERMANENTLY_BLOCKED_CONTENT_IDENTIFIERS:
        record = {"record_uid": uid, "status": status}
        assert is_actionable(record) is False

    # Also test with APPROVED status — blocked uids must still fail.
    for uid in PERMANENTLY_BLOCKED_CONTENT_IDENTIFIERS:
        record = {"record_uid": uid, "status": "APPROVED"}
        assert is_actionable(record) is False, (
            f"Blocked uid {uid!r} was reported actionable even with APPROVED status."
        )


# ---------------------------------------------------------------------------
# Property 2: Content record save rejects incomplete records
# Feature: smart-farmer-app, Property 2: Content record save rejects incomplete records
# Validates: Requirements 1.5, 1.6
# ---------------------------------------------------------------------------

# All required base field names — we'll drop one at a time to trigger failures.
_BASE_REQUIRED_FIELD_NAMES = [
    "record_uid",
    "risk_level",
    "source_org",
    "source_title",
    "source_url",
    "source_section",
    "source_pub_date",
    "review_expiry",
]

_HIGH_RISK_FIELD_NAMES = ["reviewer_name", "reviewer_credential"]


# Feature: smart-farmer-app, Property 2: Content record save rejects incomplete records
@given(
    record=valid_base_record_st(),
    field_to_omit=st.sampled_from(_BASE_REQUIRED_FIELD_NAMES),
)
@settings(max_examples=200)
def test_missing_base_required_field_is_rejected(record: dict, field_to_omit: str):
    """Removing ANY single required base field must produce a non-empty error list.

    Validates: Requirements 1.5
    """
    record["status"] = "APPROVED"
    # Remove (or null-out) one required field.
    record.pop(field_to_omit, None)
    errors = validate_content_record(record)
    assert len(errors) > 0, (
        f"Expected validation errors when {field_to_omit!r} is missing, "
        f"but got an empty error list."
    )
    assert field_to_omit in errors, (
        f"Expected {field_to_omit!r} to appear in the error list, "
        f"but got: {errors}"
    )


# Feature: smart-farmer-app, Property 2: Content record save rejects incomplete records
@given(
    record=valid_high_risk_record_st(),
    field_to_omit=st.sampled_from(_HIGH_RISK_FIELD_NAMES),
)
@settings(max_examples=200)
def test_high_risk_record_missing_reviewer_credential_is_rejected(
    record: dict, field_to_omit: str
):
    """HIGH-risk records missing reviewer_name or reviewer_credential must be rejected.

    Validates: Requirements 1.6
    """
    record.pop(field_to_omit, None)
    errors = validate_content_record(record)
    assert len(errors) > 0, (
        f"Expected validation errors for HIGH-risk record missing {field_to_omit!r}, "
        f"but got an empty error list."
    )
    assert field_to_omit in errors, (
        f"Expected {field_to_omit!r} in error list, got: {errors}"
    )


# Feature: smart-farmer-app, Property 2: Content record save rejects incomplete records
@given(record=valid_high_risk_record_st())
@settings(max_examples=200)
def test_complete_high_risk_record_is_valid(record: dict):
    """A fully populated HIGH-risk record must produce no validation errors.

    Validates: Requirements 1.5, 1.6 (positive case)
    """
    errors = validate_content_record(record)
    assert errors == [], (
        f"Expected no validation errors for a complete HIGH-risk record, "
        f"but got: {errors}"
    )


# Feature: smart-farmer-app, Property 2: Content record save rejects incomplete records
@given(
    record=valid_base_record_st(risk_level="LOW"),
)
@settings(max_examples=200)
def test_low_risk_record_without_reviewer_is_valid(record: dict):
    """LOW-risk records do not require reviewer credentials.

    Validates: Requirements 1.5 (no reviewer required for non-HIGH risk)
    """
    # Ensure no reviewer fields are present.
    record.pop("reviewer_name", None)
    record.pop("reviewer_credential", None)
    errors = validate_content_record(record)
    assert errors == [], (
        f"Expected no validation errors for a complete LOW-risk record "
        f"without reviewer credentials, but got: {errors}"
    )


# Feature: smart-farmer-app, Property 2: Content record save rejects incomplete records
@given(
    record=valid_base_record_st(),
    blank_field=st.sampled_from(_BASE_REQUIRED_FIELD_NAMES),
)
@settings(max_examples=200)
def test_blank_string_required_field_is_rejected(record: dict, blank_field: str):
    """A required field set to an empty or whitespace-only string must be rejected.

    Validates: Requirements 1.5
    """
    record[blank_field] = "   "  # whitespace-only — treated as absent
    errors = validate_content_record(record)
    assert len(errors) > 0, (
        f"Expected validation errors when {blank_field!r} is blank, "
        f"but got an empty error list."
    )
