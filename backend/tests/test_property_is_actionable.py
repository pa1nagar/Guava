# Feature: smart-farmer-app, Property 1: Non-APPROVED content records are never actionable
"""
test_property_is_actionable.py — Property-based tests for is_actionable()

Validates Property 1: For any ContentRecord whose status is NOT 'APPROVED',
is_actionable(record) must return False.

Uses Hypothesis with @given and @settings(max_examples=200).

Validates: Requirements 1.2
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from services.content_governance import (
    PERMANENTLY_BLOCKED_CONTENT_IDENTIFIERS,
    is_actionable,
)
from services.constants import CONTENT_STATUSES

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# The four statuses that are explicitly NOT APPROVED.
NON_APPROVED_STATUSES = [s for s in CONTENT_STATUSES if s != "APPROVED"]

non_approved_known_st = st.sampled_from(NON_APPROVED_STATUSES)

# Arbitrary text statuses (unknown/garbage values) that are also not 'APPROVED'.
non_approved_arbitrary_st = st.text(min_size=0, max_size=100).filter(
    lambda s: s != "APPROVED"
)

# A record_uid that is not in the permanently-blocked list, so the uid itself
# does not interfere with the actionability check.
safe_uid_st = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_"),
    min_size=1,
    max_size=80,
).filter(lambda uid: uid not in PERMANENTLY_BLOCKED_CONTENT_IDENTIFIERS)


# ---------------------------------------------------------------------------
# Property 1a: Non-APPROVED known statuses (DRAFT, NEEDS_REVIEW, EXPIRED, WITHDRAWN)
# ---------------------------------------------------------------------------

# Feature: smart-farmer-app, Property 1: Non-APPROVED content records are never actionable
@given(uid=safe_uid_st, status=non_approved_known_st)
@settings(max_examples=200)
def test_known_non_approved_status_is_never_actionable(uid: str, status: str):
    """For any record with a known non-APPROVED status, is_actionable must be False.

    Covers DRAFT, NEEDS_REVIEW, EXPIRED, WITHDRAWN explicitly.

    Validates: Requirements 1.2
    """
    record = {"record_uid": uid, "status": status}
    assert is_actionable(record) is False, (
        f"is_actionable returned True for status={status!r} — expected False. "
        f"record_uid={uid!r}"
    )


# ---------------------------------------------------------------------------
# Property 1b: Arbitrary non-APPROVED string statuses (unknown/garbage values)
# ---------------------------------------------------------------------------

# Feature: smart-farmer-app, Property 1: Non-APPROVED content records are never actionable
@given(uid=safe_uid_st, status=non_approved_arbitrary_st)
@settings(max_examples=200)
def test_arbitrary_non_approved_status_is_never_actionable(uid: str, status: str):
    """For any arbitrary string status that is not 'APPROVED', is_actionable must be False.

    This ensures unknown or future statuses are treated conservatively as
    non-actionable rather than accidentally permitted.

    Validates: Requirements 1.2
    """
    record = {"record_uid": uid, "status": status}
    assert is_actionable(record) is False, (
        f"is_actionable returned True for arbitrary status={status!r} — expected False. "
        f"record_uid={uid!r}"
    )


# ---------------------------------------------------------------------------
# Property 1c: APPROVED status returns True (positive case)
# ---------------------------------------------------------------------------

# Feature: smart-farmer-app, Property 1: Non-APPROVED content records are never actionable
@given(uid=safe_uid_st)
@settings(max_examples=200)
def test_approved_status_is_actionable(uid: str):
    """A record with status 'APPROVED' and a non-blocked uid must be actionable.

    Validates: Requirements 1.2 (positive/inverse case — ensures no over-blocking)
    """
    record = {"record_uid": uid, "status": "APPROVED"}
    assert is_actionable(record) is True, (
        f"is_actionable returned False for APPROVED record — expected True. "
        f"record_uid={uid!r}"
    )
