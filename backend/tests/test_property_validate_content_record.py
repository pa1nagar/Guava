# Feature: smart-farmer-app, Property 2: validate_content_record rejects structurally invalid records
"""
test_property_validate_content_record.py — Property-based tests for validate_content_record()

Validates Property 2: Content record save rejects incomplete records.
For any ContentRecord where any required field is absent, None, or an empty/whitespace
string, validate_content_record(record) must return a non-empty list of error messages.

Uses Hypothesis with @given and @settings(max_examples=200).

Validates: Requirements 1.3, 1.5, 1.6
"""

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from services.content_governance import (
    PERMANENTLY_BLOCKED_CONTENT_IDENTIFIERS,
    validate_content_record,
)
from services.constants import CONTENT_STATUSES, RISK_LEVELS

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Non-empty, non-whitespace text for required string fields.
nonempty_text_st = st.text(min_size=1, max_size=200).map(str.strip).filter(bool)

# ISO date strings (YYYY-MM-DD).
date_str_st = st.dates().map(lambda d: d.isoformat())

# A record_uid that is NOT in the permanently-blocked list.
safe_uid_st = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_"),
    min_size=1,
    max_size=80,
).filter(lambda uid: uid not in PERMANENTLY_BLOCKED_CONTENT_IDENTIFIERS)

# All base required field names (non-HIGH-risk).
BASE_REQUIRED_FIELDS = [
    "record_uid",
    "risk_level",
    "source_org",
    "source_title",
    "source_url",
    "source_section",
    "source_pub_date",
    "review_expiry",
]

# Additional required fields for HIGH-risk records.
HIGH_RISK_REQUIRED_FIELDS = ["reviewer_name", "reviewer_credential"]


def _make_valid_record(risk_level: str = "LOW") -> dict:
    """Return a minimal fully-valid ContentRecord dict for the given risk level."""
    record = {
        "record_uid": "test_record_001",
        "risk_level": risk_level,
        "source_org": "ICAR",
        "source_title": "Guava Crop Production Guide",
        "source_url": "https://icar.org.in/guava-guide",
        "source_section": "Section 3.2",
        "source_pub_date": "2023-01-15",
        "review_expiry": "2025-12-31",
    }
    if risk_level == "HIGH":
        record["reviewer_name"] = "Dr. A. Sharma"
        record["reviewer_credential"] = "PhD Agronomy, IARI"
    return record


# A Hypothesis strategy that builds a fully valid base record.
valid_base_record_st = st.fixed_dictionaries(
    {
        "record_uid": safe_uid_st,
        "risk_level": st.sampled_from(RISK_LEVELS),
        "source_org": nonempty_text_st,
        "source_title": nonempty_text_st,
        "source_url": nonempty_text_st,
        "source_section": nonempty_text_st,
        "source_pub_date": date_str_st,
        "review_expiry": date_str_st,
    }
)

# A strategy that builds a fully valid HIGH-risk record (including reviewer fields).
valid_high_risk_record_st = st.fixed_dictionaries(
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
# Property 2a: Removing any single required base field always produces errors
# Validates: Requirements 1.5
# ---------------------------------------------------------------------------


# Feature: smart-farmer-app, Property 2: validate_content_record rejects structurally invalid records
@given(
    record=valid_base_record_st,
    field_to_remove=st.sampled_from(BASE_REQUIRED_FIELDS),
)
@settings(max_examples=200)
def test_missing_base_field_is_rejected(record: dict, field_to_remove: str):
    """Removing ANY single required base field must yield a non-empty error list
    that names the missing field.

    Validates: Requirements 1.5
    """
    record.pop(field_to_remove)
    errors = validate_content_record(record)

    assert len(errors) > 0, (
        f"Expected validation to fail when '{field_to_remove}' is absent, "
        f"but got an empty error list. Record: {record}"
    )
    assert field_to_remove in errors, (
        f"Expected '{field_to_remove}' to appear in the error list, "
        f"but got: {errors}"
    )


# ---------------------------------------------------------------------------
# Property 2b: Setting any required base field to None always produces errors
# Validates: Requirements 1.5
# ---------------------------------------------------------------------------


# Feature: smart-farmer-app, Property 2: validate_content_record rejects structurally invalid records
@given(
    record=valid_base_record_st,
    field_to_null=st.sampled_from(BASE_REQUIRED_FIELDS),
)
@settings(max_examples=200)
def test_null_base_field_is_rejected(record: dict, field_to_null: str):
    """Setting any required base field to None must yield a non-empty error list.

    Validates: Requirements 1.5
    """
    record[field_to_null] = None
    errors = validate_content_record(record)

    assert len(errors) > 0, (
        f"Expected validation to fail when '{field_to_null}' is None, "
        f"but got an empty error list."
    )
    assert field_to_null in errors, (
        f"Expected '{field_to_null}' to appear in the error list, "
        f"but got: {errors}"
    )


# ---------------------------------------------------------------------------
# Property 2c: Setting any required string field to empty / whitespace is rejected
# Validates: Requirements 1.5
# ---------------------------------------------------------------------------

# String-typed required fields (excludes date fields which are also strings but
# have different input mechanics; we include all for maximum coverage).
_STRING_FIELDS = [
    "record_uid",
    "risk_level",
    "source_org",
    "source_title",
    "source_url",
    "source_section",
    "source_pub_date",
    "review_expiry",
]

# Generate whitespace-only strings of varying lengths.
whitespace_st = st.text(alphabet=" \t\n\r", min_size=1, max_size=20)


# Feature: smart-farmer-app, Property 2: validate_content_record rejects structurally invalid records
@given(
    record=valid_base_record_st,
    blank_field=st.sampled_from(_STRING_FIELDS),
    blank_value=whitespace_st,
)
@settings(max_examples=200)
def test_whitespace_only_field_is_rejected(record: dict, blank_field: str, blank_value: str):
    """A required field set to any whitespace-only string must be rejected.

    Validates: Requirements 1.5
    """
    record[blank_field] = blank_value
    errors = validate_content_record(record)

    assert len(errors) > 0, (
        f"Expected validation to fail when '{blank_field}' is whitespace-only "
        f"({blank_value!r}), but got an empty error list."
    )
    assert blank_field in errors, (
        f"Expected '{blank_field}' to appear in the error list, "
        f"but got: {errors}"
    )


# ---------------------------------------------------------------------------
# Property 2d: Setting any required string field to a non-string type is rejected
# Validates: Requirements 1.5 (structural integrity — wrong types treated as absent)
# ---------------------------------------------------------------------------

# Non-string scalars that should not be accepted as valid string field values.
non_string_values_st = st.one_of(
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.booleans(),
    st.lists(st.text(), min_size=0, max_size=3),
    st.dictionaries(st.text(min_size=1), st.text(min_size=1), min_size=0, max_size=2),
)

# Only test non-string types on the text fields (not date fields which could
# theoretically accept numeric representations in some locales).
_TEXT_ONLY_FIELDS = [
    "record_uid",
    "source_org",
    "source_title",
    "source_url",
    "source_section",
]


# Feature: smart-farmer-app, Property 2: validate_content_record rejects structurally invalid records
@given(
    record=valid_base_record_st,
    bad_field=st.sampled_from(_TEXT_ONLY_FIELDS),
    bad_value=non_string_values_st,
)
@settings(max_examples=200)
def test_wrong_type_for_required_field_is_rejected(record: dict, bad_field: str, bad_value):
    """Setting a required text field to a non-string type (int, float, bool, list,
    dict) must be rejected — the field is treated as absent or invalid.

    Validates: Requirements 1.5
    """
    record[bad_field] = bad_value
    errors = validate_content_record(record)

    assert len(errors) > 0, (
        f"Expected validation to fail when '{bad_field}' is {type(bad_value).__name__} "
        f"({bad_value!r}), but got an empty error list."
    )
    assert bad_field in errors, (
        f"Expected '{bad_field}' to appear in the error list when value is "
        f"{type(bad_value).__name__}, but got: {errors}"
    )


# ---------------------------------------------------------------------------
# Property 2e: HIGH-risk records missing reviewer_name or reviewer_credential
#              are always rejected
# Validates: Requirements 1.6
# ---------------------------------------------------------------------------


# Feature: smart-farmer-app, Property 2: validate_content_record rejects structurally invalid records
@given(
    record=valid_high_risk_record_st,
    field_to_remove=st.sampled_from(HIGH_RISK_REQUIRED_FIELDS),
)
@settings(max_examples=200)
def test_high_risk_missing_reviewer_field_is_rejected(record: dict, field_to_remove: str):
    """HIGH-risk records missing reviewer_name or reviewer_credential must be rejected.

    Validates: Requirements 1.6
    """
    record.pop(field_to_remove)
    errors = validate_content_record(record)

    assert len(errors) > 0, (
        f"Expected validation to fail for HIGH-risk record missing "
        f"'{field_to_remove}', but got an empty error list."
    )
    assert field_to_remove in errors, (
        f"Expected '{field_to_remove}' in the error list, but got: {errors}"
    )


# Feature: smart-farmer-app, Property 2: validate_content_record rejects structurally invalid records
@given(
    record=valid_high_risk_record_st,
    field_to_null=st.sampled_from(HIGH_RISK_REQUIRED_FIELDS),
    blank_value=whitespace_st,
)
@settings(max_examples=200)
def test_high_risk_blank_reviewer_field_is_rejected(
    record: dict, field_to_null: str, blank_value: str
):
    """HIGH-risk records with whitespace-only reviewer_name or reviewer_credential
    must be rejected.

    Validates: Requirements 1.6
    """
    record[field_to_null] = blank_value
    errors = validate_content_record(record)

    assert len(errors) > 0, (
        f"Expected validation to fail for HIGH-risk record with blank "
        f"'{field_to_null}', but got an empty error list."
    )
    assert field_to_null in errors, (
        f"Expected '{field_to_null}' in the error list, but got: {errors}"
    )


# ---------------------------------------------------------------------------
# Property 2f: Completely empty dict is always rejected
# Validates: Requirements 1.5
# ---------------------------------------------------------------------------


# Feature: smart-farmer-app, Property 2: validate_content_record rejects structurally invalid records
def test_empty_record_is_rejected():
    """An empty dict must produce a non-empty error list listing all required fields.

    Validates: Requirements 1.5
    """
    errors = validate_content_record({})

    assert len(errors) > 0, "Expected validation errors for an empty record."
    for field in BASE_REQUIRED_FIELDS:
        assert field in errors, (
            f"Expected '{field}' in error list for empty record, but got: {errors}"
        )


# ---------------------------------------------------------------------------
# Positive cases: well-formed records pass validation
# ---------------------------------------------------------------------------


# Feature: smart-farmer-app, Property 2: validate_content_record rejects structurally invalid records
@given(record=valid_base_record_st)
@settings(max_examples=200)
def test_complete_low_risk_record_passes_validation(record: dict):
    """A fully populated LOW-risk record must pass validation (empty error list).

    Validates: Requirements 1.5 — positive case ensuring no over-rejection.
    """
    # Ensure risk_level is LOW for this test — no reviewer needed.
    record["risk_level"] = "LOW"
    record.pop("reviewer_name", None)
    record.pop("reviewer_credential", None)
    errors = validate_content_record(record)

    assert errors == [], (
        f"Expected no validation errors for a complete LOW-risk record, "
        f"but got: {errors}. Record: {record}"
    )


# Feature: smart-farmer-app, Property 2: validate_content_record rejects structurally invalid records
@given(record=valid_high_risk_record_st)
@settings(max_examples=200)
def test_complete_high_risk_record_passes_validation(record: dict):
    """A fully populated HIGH-risk record (with reviewer credentials) must pass.

    Validates: Requirements 1.6 — positive case.
    """
    errors = validate_content_record(record)

    assert errors == [], (
        f"Expected no validation errors for a complete HIGH-risk record, "
        f"but got: {errors}. Record: {record}"
    )


# Feature: smart-farmer-app, Property 2: validate_content_record rejects structurally invalid records
def test_medium_risk_record_without_reviewer_passes_validation():
    """MEDIUM-risk records do not require reviewer credentials.

    Validates: Requirements 1.5 — MEDIUM risk is not HIGH.
    """
    record = _make_valid_record(risk_level="MEDIUM")
    errors = validate_content_record(record)

    assert errors == [], (
        f"Expected no validation errors for a complete MEDIUM-risk record, "
        f"but got: {errors}"
    )
