"""Approval validity (365 days), expired items not published, sweep returns them to review."""
from datetime import timedelta

from services.knowledge import config as cfg
from services.knowledge import service as svc
from tests.knowledge_helpers import ADMIN, REVIEWER, T0, make_item, members_repo


def _approved(repo, item_id="GUA-VAR-0001"):
    row = svc.create_item(repo, ADMIN, make_item(item_id), now=T0)
    row = svc.transition(repo, ADMIN, item_id, "submit", row["row_version"], None, now=T0)
    return svc.transition(repo, REVIEWER, item_id, "approve", row["row_version"], None, now=T0)


def test_approval_is_valid_for_365_days():
    repo = members_repo()
    row = _approved(repo)
    assert svc.st.parse_ts(row["expires_at"]) == T0 + timedelta(days=365)
    assert [i["id"] for i in svc.get_published_items(repo, now=T0 + timedelta(days=364))] == ["GUA-VAR-0001"]
    assert svc.get_published_items(repo, now=T0 + timedelta(days=365)) == []
    assert svc.get_published_items(repo, now=T0 + timedelta(days=400)) == []


def test_published_items_carry_their_payload_and_only_approved_ones():
    repo = members_repo()
    _approved(repo, "GUA-VAR-0001")
    svc.create_item(repo, ADMIN, make_item("GUA-VAR-0002"), now=T0)  # DRAFT
    out = svc.get_published_items(repo, now=T0)
    assert [i["id"] for i in out] == ["GUA-VAR-0001"]
    assert out[0]["payload"]["statement_en"].startswith("Guava varieties")


def test_blocked_identifiers_are_never_published(monkeypatch):
    repo = members_repo()
    _approved(repo)
    monkeypatch.setattr(cfg, "PERMANENTLY_BLOCKED_CONTENT_IDENTIFIERS", frozenset({"GUA-VAR-0001"}))
    assert svc.get_published_items(repo, now=T0) == []


def test_blocked_list_is_the_governance_list():
    from services.content_governance import PERMANENTLY_BLOCKED_CONTENT_IDENTIFIERS as gov
    assert cfg.PERMANENTLY_BLOCKED_CONTENT_IDENTIFIERS is gov


def test_sweep_moves_lapsed_items_back_to_review_and_audits_it():
    repo = members_repo()
    _approved(repo)
    later = T0 + timedelta(days=366)
    assert svc.sweep_expired(repo, now=later) == ["GUA-VAR-0001"]
    item = repo.get_item("GUA-VAR-0001")
    assert item["status"] == "IN_REVIEW" and item["expires_at"] is None and item["approved_at"] is None
    entry = repo.audit_log[-1]
    assert entry["action"] == "approval_expired" and entry["actor_role"] == "system"
    assert entry["actor_id"] is None
    assert (entry["from_status"], entry["to_status"]) == ("APPROVED", "IN_REVIEW")


def test_sweep_is_idempotent_and_leaves_valid_items_alone():
    repo = members_repo()
    _approved(repo, "GUA-VAR-0001")
    later = T0 + timedelta(days=366)
    assert svc.sweep_expired(repo, now=T0 + timedelta(days=10)) == []
    assert svc.sweep_expired(repo, now=later) == ["GUA-VAR-0001"]
    n = len(repo.audit_log)
    assert svc.sweep_expired(repo, now=later) == []
    assert len(repo.audit_log) == n


def test_sweep_skips_an_item_changed_in_the_meantime(monkeypatch):
    repo = members_repo()
    _approved(repo)
    stale = repo.list_expired(str((T0 + timedelta(days=400)).isoformat()))
    # someone retires it between the read and the write
    row = repo.get_item("GUA-VAR-0001")
    svc.transition(repo, ADMIN, "GUA-VAR-0001", "retire", row["row_version"], "withdrawn", now=T0)
    monkeypatch.setattr(repo, "list_expired", lambda now_iso: stale)
    assert svc.sweep_expired(repo, now=T0 + timedelta(days=400)) == []
    assert repo.get_item("GUA-VAR-0001")["status"] == "RETIRED"


def test_expired_item_needs_a_new_approval_to_be_published_again():
    repo = members_repo()
    _approved(repo)
    later = T0 + timedelta(days=366)
    svc.sweep_expired(repo, now=later)
    row = repo.get_item("GUA-VAR-0001")
    assert svc.get_published_items(repo, now=later) == []
    row = svc.transition(repo, REVIEWER, "GUA-VAR-0001", "approve", row["row_version"], None, now=later)
    assert svc.st.parse_ts(row["expires_at"]) == later + timedelta(days=365)
    assert len(svc.get_published_items(repo, now=later)) == 1


def test_dashboard_and_list_sweep_lazily():
    repo = members_repo()
    _approved(repo)
    later = T0 + timedelta(days=366)
    dash = svc.dashboard(repo, now=later)
    assert dash["by_status"]["IN_REVIEW"] == 1 and dash["by_status"]["APPROVED"] == 0
    assert dash["expired_just_now"] == ["GUA-VAR-0001"]


def test_dashboard_lists_items_expiring_soon():
    repo = members_repo()
    _approved(repo)
    soon = svc.dashboard(repo, now=T0 + timedelta(days=350))
    assert [x["id"] for x in soon["expiring_soon"]] == ["GUA-VAR-0001"]
    assert svc.dashboard(repo, now=T0 + timedelta(days=100))["expiring_soon"] == []


def test_item_is_published_until_the_exact_expiry_instant():
    repo = members_repo()
    row = _approved(repo)
    exp = svc.st.parse_ts(row["expires_at"])
    assert len(svc.get_published_items(repo, now=exp - timedelta(seconds=1))) == 1
    assert svc.get_published_items(repo, now=exp) == []
