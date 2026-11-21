"""
test_knowledge_migration.py - static checks on 2026-12-knowledge-admin.sql.
The file is parsed as text; nothing is run against a database.
"""
import re
from pathlib import Path

import pytest

SQL_PATH = Path(__file__).resolve().parents[1] / "migrations" / "2026-12-knowledge-admin.sql"
TABLES = ("admin_users", "admin_invites", "knowledge_items", "knowledge_item_versions",
          "knowledge_approvals", "knowledge_comments", "knowledge_audit_log")
APPEND_ONLY = ("knowledge_item_versions", "knowledge_approvals", "knowledge_comments", "knowledge_audit_log")


def _sql() -> str:
    return SQL_PATH.read_text(encoding="utf-8")


def _code() -> str:
    """SQL without -- comments."""
    return "\n".join(line.split("--", 1)[0] for line in _sql().splitlines())


def test_header_says_not_applied_by_code_and_has_owner_steps():
    head = _sql().split("CREATE TABLE", 1)[0]
    assert "NOT APPLIED BY CODE" in head and "Owner steps" in head
    assert "ADMIN_BOOTSTRAP_EMAILS" in head


def test_every_table_is_created_if_not_exists():
    creates = re.findall(r"\bCREATE\s+TABLE\b[^(]*", _code(), flags=re.I)
    assert len(creates) == len(TABLES)
    for c in creates:
        assert re.search(r"IF\s+NOT\s+EXISTS", c, flags=re.I), c
    for t in TABLES:
        assert re.search(rf"CREATE TABLE IF NOT EXISTS {t}\b", _code()), t


def test_every_index_is_if_not_exists():
    idx = re.findall(r"\bCREATE\s+(?:UNIQUE\s+)?INDEX\b[^;]*", _code(), flags=re.I)
    assert idx
    for c in idx:
        assert re.search(r"INDEX\s+IF\s+NOT\s+EXISTS", c, flags=re.I), c


def test_every_function_is_create_or_replace_and_every_trigger_is_recreated():
    code = _code()
    for fn in re.findall(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\b", code, flags=re.I):
        assert re.search(r"OR\s+REPLACE", fn, flags=re.I)
    triggers = re.findall(r"CREATE TRIGGER (\w+)\s+\w+ [^;]*? ON (\w+)", code, flags=re.S)
    assert len(triggers) >= 13
    for name, table in triggers:
        assert re.search(rf"DROP TRIGGER IF EXISTS {name} ON {table};", code), name


def test_rls_is_enabled_on_every_table():
    code = _code()
    for t in TABLES:
        assert re.search(rf"ALTER\s+TABLE\s+{t}\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY", code, flags=re.I), t


def test_no_policies_at_all_on_admin_and_knowledge_tables():
    code = _code()
    assert not re.search(r"\bCREATE\s+POLICY\b", code, flags=re.I)
    assert not re.search(r"\bALTER\s+POLICY\b", code, flags=re.I)
    assert not re.search(r"USING\s*\(\s*true\s*\)", code, flags=re.I)


def test_anon_and_authenticated_get_no_table_access():
    code = _code()
    revoke = re.search(r"REVOKE ALL ON TABLE ([^;]+?) FROM anon, authenticated;", code, flags=re.S)
    assert revoke
    for t in TABLES:
        assert t in revoke.group(1), t
    assert not re.search(r"GRANT\b[^;]*\bTO\b[^;]*\b(anon|authenticated|PUBLIC)\b", code, flags=re.I)


@pytest.mark.parametrize("table", APPEND_ONLY)
def test_history_tables_block_update_delete_truncate(table):
    code = _code()
    assert re.search(rf"BEFORE UPDATE OR DELETE ON {table}\s+FOR EACH ROW EXECUTE FUNCTION knowledge_block_mutation", code)
    assert re.search(rf"BEFORE TRUNCATE ON {table}\s+FOR EACH STATEMENT EXECUTE FUNCTION knowledge_block_truncate", code)
    assert re.search(rf"REVOKE UPDATE, DELETE, TRUNCATE ON {table}\s+FROM PUBLIC, anon, authenticated, service_role", code)


def test_every_table_blocks_truncate_and_items_block_delete():
    code = _code()
    for t in TABLES:
        assert re.search(rf"BEFORE TRUNCATE ON {t}\s+FOR EACH STATEMENT", code), t
    assert re.search(r"BEFORE DELETE ON knowledge_items\s+FOR EACH ROW EXECUTE FUNCTION knowledge_block_mutation", code)
    assert re.search(r"REVOKE DELETE, TRUNCATE ON knowledge_items FROM PUBLIC, anon, authenticated, service_role", code)


def test_commit_function_exists_and_is_service_role_only():
    code = _code()
    assert re.search(r"CREATE OR REPLACE FUNCTION knowledge_commit_change\(p jsonb\) RETURNS jsonb", code)
    assert re.search(r"REVOKE ALL ON FUNCTION knowledge_commit_change\(jsonb\) FROM PUBLIC;", code)
    assert re.search(r"REVOKE ALL ON FUNCTION knowledge_commit_change\(jsonb\) FROM anon, authenticated;", code)
    assert re.search(r"GRANT EXECUTE ON FUNCTION knowledge_commit_change\(jsonb\) TO service_role;", code)
    body = code.split("knowledge_commit_change(p jsonb)", 1)[1]
    assert "row_version = expected" in body and "row_version_conflict" in body
    assert "knowledge_audit_log" in body and "audit_required" in body
    assert not re.search(r"SECURITY\s+DEFINER", code, flags=re.I)


def test_self_contained_updated_at_trigger():
    code = _code()
    assert "FUNCTION knowledge_set_updated_at()" in code
    assert not re.search(r"\bset_updated_at\s*\(", code.replace("knowledge_set_updated_at", ""))


def test_required_columns_and_checks():
    code = _code()
    for status in ("DRAFT", "IN_REVIEW", "CHANGES_REQUESTED", "APPROVED", "REJECTED", "RETIRED"):
        assert f"'{status}'" in code
    assert "CHECK (role IN ('admin', 'reviewer'))" in code
    for col in ("current_version", "row_version", "has_conflict", "approved_at", "expires_at", "retired_reason",
                "is_proposal", "content_hash", "change_reason", "actor_role", "actor_name", "from_status",
                "to_status", "before", "after", "diff", "reason"):
        assert re.search(rf"\b{col}\b", code), col
    assert re.search(r"id\s+bigserial PRIMARY KEY", code)
    assert re.search(r"PRIMARY KEY \(item_id, version\)", code)
    assert re.search(r"user_id\s+uuid PRIMARY KEY REFERENCES auth\.users \(id\)", code)


def test_nothing_destructive_and_no_hard_coded_email_or_secret():
    code = _code()
    assert not re.search(r"\bDROP\s+(TABLE|FUNCTION|SCHEMA|COLUMN|POLICY)\b", code, flags=re.I)
    assert not re.search(r"\bDELETE\s+FROM\b", code, flags=re.I)
    assert not re.search(r"^\s*TRUNCATE\b", code, flags=re.I | re.M)
    assert not re.search(r"\bALTER\s+TABLE\s+\w+\s+DROP\b", code, flags=re.I)
    # the owner's one-line bootstrap insert in the header uses placeholders only
    raw = _sql()
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", raw), "no email addresses in the migration"
    assert "<ADMIN_EMAIL>" in raw and "<AUTH_USER_UUID>" in raw
    assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", raw, flags=re.I)
    assert not re.search(r"eyJ[A-Za-z0-9_-]{10,}|service_role_key|sk_live|sb_secret", raw)
