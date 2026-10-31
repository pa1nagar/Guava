"""
test_property_expiry_scheduler.py — Property 3: expiry scheduler.

Property 3: check_and_expire_records marks all APPROVED records whose
review_expiry is strictly before today as EXPIRED.

Uses Hypothesis with @given and @settings(max_examples=200).
Mocks the Supabase DB client — no live database required.

Feature: smart-farmer-app, Property 3: Expiry scheduler marks past-expiry records EXPIRED
Validates: Requirements 1.4
"""

from datetime import date, timedelta
from unittest.mock import MagicMock, call
from typing import List

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from services.content_governance import check_and_expire_records


# ---------------------------------------------------------------------------
# Mock DB builder
# ---------------------------------------------------------------------------

def _make_db_mock(approved_record_ids: List[str]):
    """Create a mock Supabase client that returns the given record ids as APPROVED rows."""
    db = MagicMock()
    content_records_chain = MagicMock()
    audit_chain = MagicMock()

    # Build the fluent query chain for content_records (SELECT).
    select_result = MagicMock()
    select_result.data = [{"id": rid} for rid in approved_record_ids]

    content_records_chain.select.return_value = content_records_chain
    content_records_chain.eq.return_value = content_records_chain
    content_records_chain.lt.return_value = content_records_chain
    content_records_chain.update.return_value = content_records_chain
    content_records_chain.in_.return_value = content_records_chain
    content_records_chain.execute.return_value = select_result

    # Audit log chain
    audit_chain.insert.return_value = audit_chain
    audit_chain.execute.return_value = MagicMock()

    def table_factory(name):
        if name == "content_records":
            return content_records_chain
        if name == "content_audit_log":
            return audit_chain
        mock = MagicMock()
        mock.select.return_value = mock
        mock.eq.return_value = mock
        mock.lt.return_value = mock
        mock.update.return_value = mock
        mock.in_.return_value = mock
        mock.insert.return_value = mock
        mock.execute.return_value = MagicMock(data=[])
        return mock

    db.table.side_effect = table_factory
    return db, content_records_chain, audit_chain


# ---------------------------------------------------------------------------
# Strategy: generate lists of unique record IDs
# ---------------------------------------------------------------------------

_record_id_st = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
    min_size=1,
    max_size=36,
)

_unique_ids_st = st.lists(
    _record_id_st,
    min_size=0,
    max_size=20,
    unique=True,
)


# ---------------------------------------------------------------------------
# Property 3a: all returned APPROVED records are expired
# ---------------------------------------------------------------------------

# Feature: smart-farmer-app, Property 3: Expiry scheduler marks past-expiry records EXPIRED
@given(record_ids=_unique_ids_st)
@settings(max_examples=200)
def test_expired_count_matches_approved_records_returned(record_ids: List[str]):
    """check_and_expire_records returns the count of records it expired.

    The count must equal the number of APPROVED past-expiry records the DB query
    returns — every record found must be expired.

    Validates: Requirements 1.4
    """
    db, content_chain, _ = _make_db_mock(record_ids)
    count = check_and_expire_records(db)
    assert count == len(record_ids), (
        f"Expected to expire {len(record_ids)} record(s), got {count}."
    )


# Feature: smart-farmer-app, Property 3: Expiry scheduler marks past-expiry records EXPIRED
@given(record_ids=_unique_ids_st.filter(lambda ids: len(ids) > 0))
@settings(max_examples=200)
def test_update_called_with_expired_status_when_records_exist(record_ids: List[str]):
    """When there are APPROVED past-expiry records, an update to EXPIRED must be issued.

    Validates: Requirements 1.4
    """
    db, content_chain, _ = _make_db_mock(record_ids)
    check_and_expire_records(db)

    # The update() call must set status to EXPIRED.
    content_chain.update.assert_called_once_with({"status": "EXPIRED"})
    # The in_() call must include all the record ids.
    in_call_args = content_chain.in_.call_args
    assert in_call_args is not None, "in_() was not called on content_records chain"
    called_field, called_ids = in_call_args[0]
    assert called_field == "id"
    assert set(called_ids) == set(record_ids)


# Feature: smart-farmer-app, Property 3: Expiry scheduler marks past-expiry records EXPIRED
@given(record_ids=_unique_ids_st.filter(lambda ids: len(ids) > 0))
@settings(max_examples=200)
def test_audit_log_rows_inserted_for_each_expired_record(record_ids: List[str]):
    """For each expired record, an audit log row must be inserted.

    Validates: Requirements 1.4
    """
    db, _, audit_chain = _make_db_mock(record_ids)
    check_and_expire_records(db)

    # Audit insert must have been called.
    audit_chain.insert.assert_called_once()
    rows_arg = audit_chain.insert.call_args[0][0]  # first positional arg
    assert isinstance(rows_arg, list)
    assert len(rows_arg) == len(record_ids)

    inserted_ids = {r["content_record_id"] for r in rows_arg}
    assert inserted_ids == set(record_ids)

    # Every audit row must mark the transition from APPROVED to EXPIRED.
    for row in rows_arg:
        assert row["old_status"] == "APPROVED"
        assert row["new_status"] == "EXPIRED"
        assert row["changed_by"] == "scheduler"


# ---------------------------------------------------------------------------
# Property 3b: no side effects when there are no past-expiry records
# ---------------------------------------------------------------------------

# Feature: smart-farmer-app, Property 3: Expiry scheduler marks past-expiry records EXPIRED
def test_no_update_when_no_records_to_expire():
    """When no APPROVED past-expiry records exist, no update or audit insert is made.

    Validates: Requirements 1.4
    """
    db, content_chain, audit_chain = _make_db_mock([])
    count = check_and_expire_records(db)

    assert count == 0
    # update() must NOT have been called on content_records.
    content_chain.update.assert_not_called()
    # audit insert must NOT have been called.
    audit_chain.insert.assert_not_called()


# ---------------------------------------------------------------------------
# Unit tests: deterministic cases
# ---------------------------------------------------------------------------

class TestCheckAndExpireRecordsDeterministic:
    """Deterministic unit tests with well-known inputs."""

    def test_two_records_both_expired(self):
        db, _, audit_chain = _make_db_mock(["rec-001", "rec-002"])
        count = check_and_expire_records(db)
        assert count == 2

        rows = audit_chain.insert.call_args[0][0]
        assert len(rows) == 2
        ids = {r["content_record_id"] for r in rows}
        assert ids == {"rec-001", "rec-002"}

    def test_single_record_expired(self):
        db, content_chain, _ = _make_db_mock(["single-rec"])
        count = check_and_expire_records(db)
        assert count == 1
        content_chain.update.assert_called_once_with({"status": "EXPIRED"})
