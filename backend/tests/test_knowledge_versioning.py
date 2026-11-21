"""Every edit adds a version; nothing is overwritten or deleted."""
import pytest

from services.knowledge import config as cfg
from services.knowledge import diff as diff_mod
from services.knowledge import service as svc
from tests.knowledge_helpers import ADMIN, REVIEWER, T0, item_dict, make_item, members_repo


def _edited(text="Guava varieties grown in Madhya Pradesh include L-49, Allahabad Safeda and Lalit."):
    return make_item(statement_en=text)


def test_create_stores_version_1_as_draft():
    repo = members_repo()
    row = svc.create_item(repo, ADMIN, make_item(), now=T0)
    assert row["status"] == "DRAFT" and row["current_version"] == 1 and row["row_version"] == 1
    v = repo.get_version("GUA-VAR-0001", 1)
    assert v["payload"]["id"] == "GUA-VAR-0001" and v["created_by"] == ADMIN.user_id
    assert v["content_hash"] == diff_mod.content_hash(v["payload"])


def test_create_twice_is_409():
    repo = members_repo()
    svc.create_item(repo, ADMIN, make_item(), now=T0)
    with pytest.raises(cfg.KnowledgeError) as e:
        svc.create_item(repo, ADMIN, make_item(), now=T0)
    assert e.value.status_code == 409


def test_edit_creates_new_version_and_keeps_the_old_one():
    repo = members_repo()
    first = svc.create_item(repo, ADMIN, make_item(), now=T0)
    old_payload = repo.get_version("GUA-VAR-0001", 1)["payload"]
    row = svc.edit_item(repo, ADMIN, "GUA-VAR-0001", _edited(), first["row_version"], "added Lalit", now=T0)
    assert row["current_version"] == 2 and row["row_version"] == 2
    versions = repo.list_versions("GUA-VAR-0001")
    assert [v["version"] for v in versions] == [1, 2]
    assert versions[0]["payload"] == old_payload  # untouched
    assert "Lalit" in versions[1]["payload"]["statement_en"]
    assert versions[1]["change_reason"] == "added Lalit"
    assert row["summary"].startswith("Guava varieties")


def test_nothing_is_deleted_across_many_edits():
    repo = members_repo()
    row = svc.create_item(repo, ADMIN, make_item(), now=T0)
    for i in range(4):
        row = svc.edit_item(repo, ADMIN, "GUA-VAR-0001", _edited(f"Edit number {i} of this guava varieties statement."),
                            row["row_version"], None, now=T0)
    assert [v["version"] for v in repo.list_versions("GUA-VAR-0001")] == [1, 2, 3, 4, 5]
    assert len(repo.audit_log) == 5


def test_edit_audit_row_has_before_after_and_diff():
    repo = members_repo()
    row = svc.create_item(repo, ADMIN, make_item(), now=T0)
    svc.edit_item(repo, ADMIN, "GUA-VAR-0001", _edited(), row["row_version"], "typo", now=T0)
    entry = repo.audit_log[-1]
    assert entry["action"] == "edit" and entry["reason"] == "typo"
    assert entry["before"]["statement_en"] != entry["after"]["statement_en"]
    assert set(entry["diff"]) == {"statement_en"}
    assert entry["actor_id"] == ADMIN.user_id and entry["actor_role"] == "admin"


def test_edit_without_change_is_422():
    repo = members_repo()
    row = svc.create_item(repo, ADMIN, make_item(), now=T0)
    with pytest.raises(cfg.KnowledgeError) as e:
        svc.edit_item(repo, ADMIN, "GUA-VAR-0001", make_item(), row["row_version"], None, now=T0)
    assert e.value.status_code == 422


def test_stale_row_version_is_409_and_writes_nothing():
    repo = members_repo()
    row = svc.create_item(repo, ADMIN, make_item(), now=T0)
    svc.edit_item(repo, ADMIN, "GUA-VAR-0001", _edited(), row["row_version"], None, now=T0)
    n_versions, n_audit = len(repo.versions), len(repo.audit_log)
    with pytest.raises(cfg.KnowledgeError) as e:
        svc.edit_item(repo, ADMIN, "GUA-VAR-0001", _edited("A different statement about guava varieties."),
                      row["row_version"], None, now=T0)
    assert e.value.status_code == 409
    assert (len(repo.versions), len(repo.audit_log)) == (n_versions, n_audit)


def test_id_cannot_change_on_edit():
    repo = members_repo()
    row = svc.create_item(repo, ADMIN, make_item(), now=T0)
    with pytest.raises(cfg.KnowledgeError) as e:
        svc.edit_item(repo, ADMIN, "GUA-VAR-0001", make_item("GUA-VAR-0002"), row["row_version"], None, now=T0)
    assert e.value.status_code == 422


def test_retired_item_cannot_be_edited():
    repo = members_repo()
    row = svc.create_item(repo, ADMIN, make_item(), now=T0)
    row = svc.transition(repo, ADMIN, "GUA-VAR-0001", "retire", row["row_version"], "wrong crop", now=T0)
    with pytest.raises(cfg.KnowledgeError) as e:
        svc.edit_item(repo, ADMIN, "GUA-VAR-0001", _edited(), row["row_version"], None, now=T0)
    assert e.value.status_code == 409


def test_missing_item_is_404():
    repo = members_repo()
    with pytest.raises(cfg.KnowledgeError) as e:
        svc.edit_item(repo, ADMIN, "GUA-VAR-0009", make_item("GUA-VAR-0009"), 1, None, now=T0)
    assert e.value.status_code == 404


def test_editing_an_approved_item_voids_the_approval():
    repo = members_repo()
    row = svc.create_item(repo, ADMIN, make_item(), now=T0)
    row = svc.transition(repo, ADMIN, "GUA-VAR-0001", "submit", row["row_version"], None, now=T0)
    row = svc.transition(repo, ADMIN, "GUA-VAR-0001", "approve", row["row_version"], None, now=T0)
    assert row["status"] == "APPROVED" and row["expires_at"]
    row = svc.edit_item(repo, ADMIN, "GUA-VAR-0001", _edited(), row["row_version"], None, now=T0)
    assert row["status"] == "IN_REVIEW" and row["approved_at"] is None and row["expires_at"] is None
    assert svc.get_published_items(repo, now=T0) == []


def test_changes_requested_then_edit_goes_back_to_review_and_rejected_to_draft():
    repo = members_repo()
    row = svc.create_item(repo, ADMIN, make_item(), now=T0)
    row = svc.transition(repo, ADMIN, "GUA-VAR-0001", "submit", row["row_version"], None, now=T0)
    row = svc.transition(repo, REVIEWER, "GUA-VAR-0001", "request_changes", row["row_version"], "cite page", now=T0)
    assert row["status"] == "CHANGES_REQUESTED"
    row = svc.edit_item(repo, ADMIN, "GUA-VAR-0001", _edited(), row["row_version"], None, now=T0)
    assert row["status"] == "IN_REVIEW"
    row = svc.transition(repo, REVIEWER, "GUA-VAR-0001", "reject", row["row_version"], "not supported", now=T0)
    assert row["status"] == "REJECTED"
    row = svc.edit_item(repo, ADMIN, "GUA-VAR-0001", _edited("Another, better supported statement text."),
                        row["row_version"], None, now=T0)
    assert row["status"] == "DRAFT"


def test_reviewer_proposal_does_not_change_current_version_until_accepted():
    repo = members_repo()
    row = svc.create_item(repo, ADMIN, make_item(), now=T0)
    out = svc.propose_edit(repo, REVIEWER, "GUA-VAR-0001", _edited(), "add Lalit", now=T0)
    assert out["proposal_version"] == 2
    item = repo.get_item("GUA-VAR-0001")
    assert item["current_version"] == 1 and item["row_version"] == row["row_version"]
    assert repo.get_version("GUA-VAR-0001", 2)["is_proposal"] is True
    detail = svc.get_detail(repo, ADMIN, "GUA-VAR-0001")
    assert [p["version"] for p in detail["pending_proposals"]] == [2]

    row = svc.accept_proposal(repo, ADMIN, "GUA-VAR-0001", 2, item["row_version"], None, now=T0)
    assert row["current_version"] == 3 and row["status"] == "IN_REVIEW"
    assert repo.get_version("GUA-VAR-0001", 3)["created_by"] == REVIEWER.user_id  # proposer stays the author
    assert svc.get_detail(repo, ADMIN, "GUA-VAR-0001")["pending_proposals"] == []
    with pytest.raises(cfg.KnowledgeError) as e:  # cannot be accepted twice
        svc.accept_proposal(repo, ADMIN, "GUA-VAR-0001", 2, row["row_version"], None, now=T0)
    assert e.value.status_code == 409


def test_declined_proposal_stays_in_history_and_needs_a_reason():
    repo = members_repo()
    row = svc.create_item(repo, ADMIN, make_item(), now=T0)
    svc.propose_edit(repo, REVIEWER, "GUA-VAR-0001", _edited(), None, now=T0)
    with pytest.raises(cfg.KnowledgeError) as e:
        svc.decline_proposal(repo, ADMIN, "GUA-VAR-0001", 2, row["row_version"], None, now=T0)
    assert e.value.status_code == 422
    svc.decline_proposal(repo, ADMIN, "GUA-VAR-0001", 2, row["row_version"], "not in the source", now=T0)
    assert repo.get_version("GUA-VAR-0001", 2) is not None
    assert repo.get_item("GUA-VAR-0001")["current_version"] == 1
    assert svc.get_detail(repo, ADMIN, "GUA-VAR-0001")["pending_proposals"] == []


def test_diff_is_field_level_and_hash_ignores_key_order():
    a = {"x": 1, "n": {"p": 1, "q": 2}, "l": [1, 2]}
    b = {"x": 1, "n": {"p": 1, "q": 3}, "l": [1, 2, 3], "new": "y"}
    d = diff_mod.diff(a, b)
    assert d == {"n.q": {"before": 2, "after": 3}, "l": {"before": [1, 2], "after": [1, 2, 3]},
                 "new": {"before": None, "after": "y"}}
    assert diff_mod.diff(a, a) == {}
    assert diff_mod.content_hash({"a": 1, "b": 2}) == diff_mod.content_hash({"b": 2, "a": 1})
    assert diff_mod.content_hash({"a": 1}) != diff_mod.content_hash({"a": 2})


def test_model_rules():
    from pydantic import ValidationError
    from services.knowledge.models import ItemIn
    ok = item_dict()
    ItemIn.model_validate(ok)
    bad_cases = [
        {**ok, "unknown": 1},
        {**ok, "sources": []},
        {**ok, "sources": [{**ok["sources"][0], "url": "javascript:alert(1)"}]},
        {**ok, "sources": [{**ok["sources"][0], "url": "ftp://x.org/a"}]},
        {**ok, "sources": [{**ok["sources"][0], "quote": " ".join(["word"] * 30)}]},
        {**ok, "sources": [{**ok["sources"][0], "quote": ""}]},
        {**ok, "involves_chemical": True, "risk_level": "MEDIUM"},
        {**ok, "id": "bad id"},
        {**ok, "statement_en": "x" * 601},
        {**ok, "region": "KA"},
        {**ok, "topic": "tractors"},
    ]
    for bad in bad_cases:
        with pytest.raises(ValidationError):
            ItemIn.model_validate(bad)
    ItemIn.model_validate({**ok, "sources": [{**ok["sources"][0], "quote": " ".join(["word"] * 29)}]})
