"""Status machine and approval rules (pure functions)."""
import pytest

from services.knowledge import config as cfg
from services.knowledge import status as st

# The full allowed table, written out independently of status.TRANSITIONS.
ALLOWED = {
    ("submit", "DRAFT"): "IN_REVIEW",
    ("approve", "IN_REVIEW"): "APPROVED",
    ("reject", "IN_REVIEW"): "REJECTED",
    ("request_changes", "IN_REVIEW"): "CHANGES_REQUESTED",
    ("retire", "DRAFT"): "RETIRED",
    ("retire", "IN_REVIEW"): "RETIRED",
    ("retire", "CHANGES_REQUESTED"): "RETIRED",
    ("retire", "APPROVED"): "RETIRED",
    ("retire", "REJECTED"): "RETIRED",
    ("restore", "RETIRED"): "DRAFT",
    ("expire", "APPROVED"): "IN_REVIEW",
    ("edit", "DRAFT"): "DRAFT",
    ("edit", "IN_REVIEW"): "IN_REVIEW",
    ("edit", "CHANGES_REQUESTED"): "IN_REVIEW",
    ("edit", "REJECTED"): "DRAFT",
    ("edit", "APPROVED"): "IN_REVIEW",
    ("accept_proposal", "DRAFT"): "IN_REVIEW",
    ("accept_proposal", "IN_REVIEW"): "IN_REVIEW",
    ("accept_proposal", "CHANGES_REQUESTED"): "IN_REVIEW",
    ("accept_proposal", "APPROVED"): "IN_REVIEW",
    ("accept_proposal", "REJECTED"): "IN_REVIEW",
}
ACTIONS = sorted({a for a, _ in ALLOWED})
CASES = [(a, s) for a in ACTIONS for s in cfg.STATUSES]


def test_six_statuses():
    assert cfg.STATUSES == ("DRAFT", "IN_REVIEW", "CHANGES_REQUESTED", "APPROVED", "REJECTED", "RETIRED")
    assert set(st.TRANSITIONS) == set(ACTIONS)


@pytest.mark.parametrize("action,current", CASES)
def test_every_transition_allowed_or_denied(action, current):
    expected = ALLOWED.get((action, current))
    assert st.next_status(action, current) == expected
    assert st.can_transition(action, current) is (expected is not None)
    if expected is None:
        with pytest.raises(cfg.KnowledgeError) as e:
            st.require_transition(action, current)
        assert e.value.status_code == 409
    else:
        assert st.require_transition(action, current) == expected


def test_retired_can_only_be_restored():
    assert [a for a in ACTIONS if st.can_transition(a, "RETIRED")] == ["restore"]


def test_unknown_action_or_status_is_denied():
    assert st.next_status("delete", "DRAFT") is None
    assert st.next_status("approve", "NOPE") is None


@pytest.mark.parametrize("action", ["reject", "request_changes", "retire", "restore", "decline_proposal"])
def test_reason_required(action):
    for bad in (None, "", "  ", "ab"):
        with pytest.raises(cfg.KnowledgeError) as e:
            st.clean_reason(action, bad)
        assert e.value.status_code == 422
    assert st.clean_reason(action, "  not accurate  ") == "not accurate"


def test_reason_optional_for_approve():
    assert st.clean_reason("approve", None) is None


def _who(role, name="N", cred="C", uid="u1"):
    return {"user_id": uid, "role": role, "display_name": name, "credential": cred}


@pytest.mark.parametrize("risk", ["LOW", "MEDIUM"])
@pytest.mark.parametrize("role", ["admin", "reviewer"])
def test_low_and_medium_any_member_may_approve(risk, role):
    assert st.approval_problem(risk, _who(role, None, None), "other") is None


def test_non_member_role_cannot_approve():
    assert st.approval_problem("LOW", _who("farmer"), None)


def test_high_rules():
    ok = _who("reviewer")
    assert st.approval_problem("HIGH", ok, "someone-else") is None
    assert st.approval_problem("HIGH", _who("admin"), None)
    assert st.approval_problem("HIGH", _who("reviewer", name=""), None)
    assert st.approval_problem("HIGH", _who("reviewer", cred=" "), None)
    assert st.approval_problem("HIGH", _who("reviewer", cred=None), None)
    assert st.approval_problem("HIGH", ok, "u1")  # author


def test_expiry_helpers():
    from datetime import datetime, timedelta, timezone
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert st.expiry_for(t) == t + timedelta(days=365)
    assert st.is_expired(None, t)
    assert st.is_expired("2026-01-01T00:00:00Z", t)
    assert not st.is_expired("2026-01-02T00:00:00+00:00", t)
