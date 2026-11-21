"""HIGH risk items (pesticide, dose) need a credentialed reviewer who is not the author."""
from datetime import timedelta

import pytest
from pydantic import ValidationError

from services.knowledge import config as cfg
from services.knowledge import service as svc
from tests.knowledge_helpers import (
    ADMIN, NOCRED, REVIEWER, REVIEWER2, T0, high_item, make_item, members_repo,
)

ID = "GUA-PEST-0001"


def _in_review(repo, item=None):
    row = svc.create_item(repo, ADMIN, item or high_item(), now=T0)
    return svc.transition(repo, ADMIN, ID, "submit", row["row_version"], None, now=T0)


def _approve(repo, who, row):
    return svc.transition(repo, who, ID, "approve", row["row_version"], None, now=T0)


def test_admin_cannot_approve_high():
    repo = members_repo()
    row = _in_review(repo)
    with pytest.raises(cfg.KnowledgeError) as e:
        _approve(repo, ADMIN, row)
    assert e.value.status_code == 403
    assert repo.get_item(ID)["status"] == "IN_REVIEW"
    assert repo.approvals == []


def test_reviewer_without_credential_cannot_approve_high():
    repo = members_repo()
    row = _in_review(repo)
    with pytest.raises(cfg.KnowledgeError) as e:
        _approve(repo, NOCRED, row)
    assert e.value.status_code == 403 and "credential" in e.value.detail


def test_reviewer_without_name_cannot_approve_high():
    repo = members_repo()
    row = _in_review(repo)
    nameless = REVIEWER.__class__(user_id=REVIEWER.user_id, role="reviewer", email="x@example.test",
                                  display_name=None, credential="PhD")
    with pytest.raises(cfg.KnowledgeError) as e:
        _approve(repo, nameless, row)
    assert e.value.status_code == 403


def test_author_cannot_approve_own_high_item():
    repo = members_repo()
    row = svc.create_item(repo, ADMIN, high_item(), now=T0)
    # REVIEWER proposes the change, the admin accepts it: REVIEWER is the author of version 2.
    svc.propose_edit(repo, REVIEWER, ID, high_item(statement_en="A reviewed statement about the spray schedule."),
                     "better wording", now=T0)
    row = svc.accept_proposal(repo, ADMIN, ID, 2, row["row_version"], None, now=T0)
    assert row["status"] == "IN_REVIEW"
    with pytest.raises(cfg.KnowledgeError) as e:
        _approve(repo, REVIEWER, row)
    assert e.value.status_code == 403 and "author" in e.value.detail
    done = _approve(repo, REVIEWER2, row)
    assert done["status"] == "APPROVED"


def test_credentialed_reviewer_approves_and_name_and_credential_are_recorded():
    repo = members_repo()
    row = _in_review(repo)
    done = _approve(repo, REVIEWER, row)
    assert done["status"] == "APPROVED"
    (approval,) = repo.approvals
    assert approval["decision"] == "approve"
    assert approval["approver_id"] == REVIEWER.user_id
    assert approval["approver_name"] == "Dr Ravi Rao"
    assert approval["approver_credential"] == "PhD Horticulture, ICAR-CISH"
    assert approval["version"] == 1
    exp = svc.st.parse_ts(approval["expires_at"])
    assert exp == T0 + timedelta(days=cfg.APPROVAL_VALIDITY_DAYS)


def test_recorded_credential_does_not_change_when_the_profile_changes_later():
    repo = members_repo()
    row = _in_review(repo)
    _approve(repo, REVIEWER, row)
    repo.admins[REVIEWER.user_id]["credential"] = "something else"
    assert repo.approvals[0]["approver_credential"] == "PhD Horticulture, ICAR-CISH"


def test_get_detail_tells_the_ui_why_approve_is_blocked():
    repo = members_repo()
    _in_review(repo)
    blocked = svc.get_detail(repo, ADMIN, ID)
    assert "approve" in blocked["allowed_actions"] and blocked["approve_blocked_reason"]
    assert svc.get_detail(repo, REVIEWER2, ID)["approve_blocked_reason"] is None


def test_admin_can_still_approve_low_and_medium():
    repo = members_repo()
    for i, risk in enumerate(("LOW", "MEDIUM"), start=1):
        item_id = f"GUA-VAR-000{i}"
        row = svc.create_item(repo, ADMIN, make_item(item_id, risk_level=risk), now=T0)
        row = svc.transition(repo, ADMIN, item_id, "submit", row["row_version"], None, now=T0)
        assert svc.transition(repo, ADMIN, item_id, "approve", row["row_version"], None, now=T0)["status"] == "APPROVED"


def test_item_with_chemical_must_be_high():
    with pytest.raises(ValidationError):
        make_item(involves_chemical=True, risk_level="MEDIUM")
    with pytest.raises(ValidationError):
        make_item(involves_chemical=True, risk_level="LOW")
    assert make_item(involves_chemical=True, risk_level="HIGH").risk_level == "HIGH"


def test_approve_requires_in_review():
    repo = members_repo()
    row = svc.create_item(repo, ADMIN, make_item(), now=T0)
    with pytest.raises(cfg.KnowledgeError) as e:
        svc.transition(repo, ADMIN, "GUA-VAR-0001", "approve", row["row_version"], None, now=T0)
    assert e.value.status_code == 409


def test_reviewer_cannot_use_admin_only_transitions_in_the_service():
    repo = members_repo()
    row = svc.create_item(repo, ADMIN, make_item(), now=T0)
    for action in ("retire", "restore"):
        with pytest.raises(cfg.KnowledgeError) as e:
            svc.transition(repo, REVIEWER, "GUA-VAR-0001", action, row["row_version"], "because", now=T0)
        assert e.value.status_code == 403
