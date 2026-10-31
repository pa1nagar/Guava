"""
test_content_governance_unit.py — Unit tests for content_governance.py.

Covers task 1.3:
  - is_actionable returns False for DRAFT, NEEDS_REVIEW, EXPIRED, WITHDRAWN
  - is_actionable returns True only for APPROVED with a non-blocked uid
  - validate_content_record rejects records missing each required field
  - validate_content_record rejects HIGH-risk records missing reviewer credentials
  - should_show_compatibility_warning returns True for non-APPROVED and missing fields

Requirements: 1.2, 1.5, 1.6, 1.9
"""

import pytest

from services.content_governance import (
    PERMANENTLY_BLOCKED_CONTENT_IDENTIFIERS,
    is_actionable,
    validate_content_record,
    should_show_compatibility_warning,
)
from services.constants import CONTENT_STATUSES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _complete_base_record(**overrides) -> dict:
    """Return a complete valid LOW-risk record, with optional field overrides."""
    record = {
        "record_uid": "test_uid_123",
        "risk_level": "LOW",
        "source_org": "ICAR",
        "source_title": "Guava Cultivation Guide",
        "source_url": "https://example.org/guide",
        "source_section": "Section 3",
        "source_pub_date": "2023-01-01",
        "review_expiry": "2025-12-31",
        "status": "APPROVED",
    }
    record.update(overrides)
    return record


def _complete_high_risk_record(**overrides) -> dict:
    """Return a complete valid HIGH-risk record, with optional field overrides."""
    record = _complete_base_record(
        risk_level="HIGH",
        reviewer_name="Dr. A. Sharma",
        reviewer_credential="PhD Plant Pathology, ICAR",
    )
    record.update(overrides)
    return record


def _complete_compatibility_record(**overrides) -> dict:
    """Return a complete valid compatibility record."""
    record = _complete_high_risk_record(
        formulation="1% Copper Hydroxide 50WP + Neem Oil 0.5%",
        ph_ec_range="pH 6.0–7.0, EC < 0.8 mS/cm",
    )
    record.update(overrides)
    return record


# ---------------------------------------------------------------------------
# is_actionable — non-APPROVED statuses
# ---------------------------------------------------------------------------

class TestIsActionableNonApproved:
    """Non-APPROVED statuses must never be actionable (Requirement 1.2)."""

    @pytest.mark.parametrize("status", ["DRAFT", "NEEDS_REVIEW", "EXPIRED", "WITHDRAWN"])
    def test_non_approved_status_returns_false(self, status: str):
        record = _complete_base_record(status=status)
        assert is_actionable(record) is False, (
            f"is_actionable should be False for status={status!r}"
        )

    def test_unknown_status_returns_false(self):
        record = _complete_base_record(status="PENDING_ESCALATION")
        assert is_actionable(record) is False

    def test_empty_status_returns_false(self):
        record = _complete_base_record(status="")
        assert is_actionable(record) is False

    def test_none_status_returns_false(self):
        record = _complete_base_record(status=None)
        assert is_actionable(record) is False

    def test_lowercase_approved_is_not_actionable(self):
        """Status comparison is case-sensitive — 'approved' is not 'APPROVED'."""
        record = _complete_base_record(status="approved")
        assert is_actionable(record) is False


# ---------------------------------------------------------------------------
# is_actionable — APPROVED with non-blocked uid
# ---------------------------------------------------------------------------

class TestIsActionableApproved:
    """APPROVED status with a non-blocked uid must be actionable (Requirement 1.2)."""

    def test_approved_non_blocked_returns_true(self):
        record = _complete_base_record(status="APPROVED", record_uid="safe_uid_abc")
        assert is_actionable(record) is True

    def test_approved_high_risk_returns_true(self):
        record = _complete_high_risk_record(status="APPROVED")
        assert is_actionable(record) is True

    @pytest.mark.parametrize("blocked_uid", list(PERMANENTLY_BLOCKED_CONTENT_IDENTIFIERS))
    def test_permanently_blocked_uid_never_actionable_even_when_approved(
        self, blocked_uid: str
    ):
        """Permanently-blocked uids must never be actionable regardless of status.

        Requirement 1.1
        """
        record = _complete_base_record(status="APPROVED", record_uid=blocked_uid)
        assert is_actionable(record) is False, (
            f"Blocked uid {blocked_uid!r} should not be actionable even when APPROVED."
        )

    @pytest.mark.parametrize("blocked_uid", list(PERMANENTLY_BLOCKED_CONTENT_IDENTIFIERS))
    def test_permanently_blocked_uid_non_actionable_for_all_statuses(
        self, blocked_uid: str
    ):
        """Permanently-blocked uids non-actionable for every status."""
        for status in CONTENT_STATUSES:
            record = {"record_uid": blocked_uid, "status": status}
            assert is_actionable(record) is False


# ---------------------------------------------------------------------------
# validate_content_record — required base fields
# ---------------------------------------------------------------------------

_BASE_REQUIRED_FIELDS = [
    "record_uid",
    "risk_level",
    "source_org",
    "source_title",
    "source_url",
    "source_section",
    "source_pub_date",
    "review_expiry",
]


class TestValidateContentRecordBaseFields:
    """Missing any required base field must return a non-empty error list (Req 1.5)."""

    def test_complete_low_risk_record_is_valid(self):
        record = _complete_base_record()
        errors = validate_content_record(record)
        assert errors == [], f"Expected no errors, got: {errors}"

    @pytest.mark.parametrize("field", _BASE_REQUIRED_FIELDS)
    def test_missing_required_field_produces_error(self, field: str):
        record = _complete_base_record()
        del record[field]
        errors = validate_content_record(record)
        assert len(errors) > 0, (
            f"Expected validation error when {field!r} is missing."
        )
        assert field in errors, (
            f"Expected {field!r} in errors list, got: {errors}"
        )

    @pytest.mark.parametrize("field", _BASE_REQUIRED_FIELDS)
    def test_none_required_field_produces_error(self, field: str):
        record = _complete_base_record()
        record[field] = None
        errors = validate_content_record(record)
        assert len(errors) > 0
        assert field in errors

    @pytest.mark.parametrize("field", _BASE_REQUIRED_FIELDS)
    def test_empty_string_required_field_produces_error(self, field: str):
        record = _complete_base_record()
        record[field] = ""
        errors = validate_content_record(record)
        assert len(errors) > 0
        assert field in errors

    @pytest.mark.parametrize("field", _BASE_REQUIRED_FIELDS)
    def test_whitespace_only_required_field_produces_error(self, field: str):
        record = _complete_base_record()
        record[field] = "   "
        errors = validate_content_record(record)
        assert len(errors) > 0
        assert field in errors

    @pytest.mark.parametrize("field", _BASE_REQUIRED_FIELDS)
    def test_non_string_required_field_produces_error(self, field: str):
        record = _complete_base_record()
        record[field] = 12345  # integer — not a valid string field
        errors = validate_content_record(record)
        assert len(errors) > 0
        assert field in errors


# ---------------------------------------------------------------------------
# validate_content_record — HIGH-risk reviewer fields
# ---------------------------------------------------------------------------

class TestValidateContentRecordHighRisk:
    """HIGH-risk records require reviewer_name and reviewer_credential (Req 1.6)."""

    def test_complete_high_risk_record_is_valid(self):
        record = _complete_high_risk_record()
        errors = validate_content_record(record)
        assert errors == [], f"Expected no errors for complete HIGH-risk record, got: {errors}"

    def test_high_risk_missing_reviewer_name_rejected(self):
        record = _complete_high_risk_record()
        del record["reviewer_name"]
        errors = validate_content_record(record)
        assert len(errors) > 0
        assert "reviewer_name" in errors

    def test_high_risk_missing_reviewer_credential_rejected(self):
        record = _complete_high_risk_record()
        del record["reviewer_credential"]
        errors = validate_content_record(record)
        assert len(errors) > 0
        assert "reviewer_credential" in errors

    def test_high_risk_empty_reviewer_name_rejected(self):
        record = _complete_high_risk_record(reviewer_name="")
        errors = validate_content_record(record)
        assert len(errors) > 0
        assert "reviewer_name" in errors

    def test_high_risk_whitespace_reviewer_name_rejected(self):
        record = _complete_high_risk_record(reviewer_name="   ")
        errors = validate_content_record(record)
        assert len(errors) > 0
        assert "reviewer_name" in errors

    def test_low_risk_does_not_require_reviewer_fields(self):
        """LOW/MEDIUM-risk records do not need reviewer credentials."""
        for risk in ("LOW", "MEDIUM"):
            record = _complete_base_record(risk_level=risk)
            # Ensure reviewer fields are absent.
            record.pop("reviewer_name", None)
            record.pop("reviewer_credential", None)
            errors = validate_content_record(record)
            assert errors == [], (
                f"Expected no errors for {risk}-risk record without reviewer, got: {errors}"
            )


# ---------------------------------------------------------------------------
# should_show_compatibility_warning
# ---------------------------------------------------------------------------

class TestShouldShowCompatibilityWarning:
    """Requirement 1.9: return True when compatibility record lacks full verification."""

    def test_fully_verified_record_returns_false(self):
        record = _complete_compatibility_record(status="APPROVED")
        assert should_show_compatibility_warning(record) is False

    @pytest.mark.parametrize(
        "status", ["DRAFT", "NEEDS_REVIEW", "EXPIRED", "WITHDRAWN"]
    )
    def test_non_approved_status_returns_true(self, status: str):
        record = _complete_compatibility_record(status=status)
        assert should_show_compatibility_warning(record) is True, (
            f"Expected warning for status={status!r}"
        )

    def test_missing_formulation_returns_true(self):
        record = _complete_compatibility_record(status="APPROVED")
        del record["formulation"]
        assert should_show_compatibility_warning(record) is True

    def test_empty_formulation_returns_true(self):
        record = _complete_compatibility_record(status="APPROVED", formulation="")
        assert should_show_compatibility_warning(record) is True

    def test_missing_ph_ec_range_returns_true(self):
        record = _complete_compatibility_record(status="APPROVED")
        del record["ph_ec_range"]
        assert should_show_compatibility_warning(record) is True

    def test_missing_reviewer_name_returns_true(self):
        record = _complete_compatibility_record(status="APPROVED")
        del record["reviewer_name"]
        assert should_show_compatibility_warning(record) is True

    def test_missing_reviewer_credential_returns_true(self):
        record = _complete_compatibility_record(status="APPROVED")
        del record["reviewer_credential"]
        assert should_show_compatibility_warning(record) is True

    def test_all_fields_missing_returns_true(self):
        """Empty record — should always show warning."""
        assert should_show_compatibility_warning({}) is True
