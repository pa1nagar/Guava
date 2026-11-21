"""The audit log and the other history stores are append-only (fake repo and migration SQL)."""
import re
from pathlib import Path

import pytest

from services.knowledge import service as svc
from tests.fake_knowledge_repo import ImmutableError
from tests.knowledge_helpers import ADMIN, REVIEWER, T0, make_item, members_repo

SQL = (Path(__file__).resolve().parents[1] / "migrations" / "2026-12-knowledge-admin.sql").read_text(encoding="utf-8")
HISTORY = ("knowledge_item_versions", "knowledge_approvals", "knowledge_comments", "knowledge_audit_log")


def _busy_repo():
    repo = members_repo()
    row = svc.create_item(repo, ADMIN, make_item(), now=T0)
    svc.add_comment(repo, REVIEWER, "GUA-VAR-0001", "check the page number", None, now=T0)
    row = svc.transition(repo, ADMIN, "GUA-VAR-0001", "submit", row["row_version"], None, now=T0)
    svc.transition(repo, REVIEWER, "GUA-VAR-0001", "approve", row["row_version"], "ok", now=T0)
    return repo


def test_every_action_writes_an_audit_row():
    repo = _busy_repo()
    assert [a["action"] for a in repo.audit_log] == ["create", "comment", "submit", "approve"]
    approve = repo.audit_log[-1]
    assert (approve["from_status"], approve["to_status"]) == ("IN_REVIEW", "APPROVED")
    assert approve["actor_id"] == REVIEWER.user_id and approve["reason"] == "ok"


@pytest.mark.parametrize("store", ["audit_log", "versions", "approvals", "comments"])
def test_fake_history_stores_refuse_mutation(store):
    repo = _busy_repo()
    rows = getattr(repo, store)
    assert len(rows) > 0
    with pytest.raises(ImmutableError):
        rows[0] = {}
    with pytest.raises(ImmutableError):
        del rows[0]
    with pytest.raises(ImmutableError):
        rows.pop()
    with pytest.raises(ImmutableError):
        rows.clear()
    with pytest.raises(ImmutableError):
        rows.append({})
    with pytest.raises(ImmutableError):
        rows.remove(rows[0])
    assert len(getattr(repo, store)) > 0


def test_fake_refuses_delete_and_truncate():
    repo = _busy_repo()
    with pytest.raises(ImmutableError):
        repo.delete_item("GUA-VAR-0001")
    with pytest.raises(ImmutableError):
        repo.truncate("knowledge_audit_log")
    assert repo.get_item("GUA-VAR-0001")


def test_rows_returned_by_the_repo_are_copies():
    repo = _busy_repo()
    entries, _ = repo.list_audit("GUA-VAR-0001", 10, 0)
    entries[0]["action"] = "tampered"
    assert repo.audit_log[0]["action"] != "tampered"
    repo.get_version("GUA-VAR-0001", 1)["payload"]["statement_en"] = "tampered"
    assert repo.get_version("GUA-VAR-0001", 1)["payload"]["statement_en"] != "tampered"


def test_failed_commit_leaves_no_partial_write():
    repo = members_repo()
    svc.create_item(repo, ADMIN, make_item(), now=T0)
    before = (len(repo.versions), len(repo.audit_log), repo.get_item("GUA-VAR-0001")["row_version"])
    with pytest.raises(Exception):
        repo.commit_change({
            "item": {"id": "GUA-VAR-0001", "current_version": 2, "status": "DRAFT", "risk_level": "LOW",
                     "topic": "varieties", "region": "MP"},
            "expected_row_version": 99,  # stale -> conflict
            "version": {"item_id": "GUA-VAR-0001", "version": 2, "payload": {}, "content_hash": "x"},
            "audit": {"action": "edit", "item_id": "GUA-VAR-0001"},
        })
    assert (len(repo.versions), len(repo.audit_log), repo.get_item("GUA-VAR-0001")["row_version"]) == before


def test_audit_is_required_for_every_commit():
    repo = members_repo()
    from services.knowledge.repo import RepoError
    with pytest.raises(RepoError):
        repo.commit_change({"expected_row_version": None})


@pytest.mark.parametrize("table", HISTORY)
def test_migration_blocks_update_delete_truncate_on_history(table):
    code = "\n".join(l.split("--", 1)[0] for l in SQL.splitlines())
    assert re.search(
        rf"CREATE TRIGGER \w+\s+BEFORE UPDATE OR DELETE ON {table}\s+FOR EACH ROW EXECUTE FUNCTION knowledge_block_mutation",
        code), table
    assert re.search(
        rf"CREATE TRIGGER \w+\s+BEFORE TRUNCATE ON {table}\s+FOR EACH STATEMENT EXECUTE FUNCTION knowledge_block_truncate",
        code), table
    revoke = re.search(rf"REVOKE UPDATE, DELETE, TRUNCATE ON {table}\s+FROM ([^;]+);", code)
    assert revoke, table
    for role in ("PUBLIC", "anon", "authenticated", "service_role"):
        assert role in revoke.group(1)


def test_migration_trigger_functions_raise():
    assert re.search(r"knowledge_block_mutation\(\).*?RAISE EXCEPTION", SQL, flags=re.S)
    assert re.search(r"knowledge_block_truncate\(\).*?RAISE EXCEPTION", SQL, flags=re.S)
