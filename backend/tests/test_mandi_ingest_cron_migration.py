"""
test_mandi_ingest_cron_migration.py - static checks on the pg_cron migration.
The file is parsed as text; nothing is run against a database.
"""
import re
from pathlib import Path

SQL_PATH = Path(__file__).resolve().parents[1] / "migrations" / "2026-11-mandi-ingest-cron.sql"


def _sql() -> str:
    return SQL_PATH.read_text(encoding="utf-8")


def _code() -> str:
    """SQL without -- comments."""
    return "\n".join(line.split("--", 1)[0] for line in _sql().splitlines())


def test_no_destructive_statements():
    assert not re.search(r"\b(DROP|TRUNCATE|DELETE|ALTER)\b", _code(), flags=re.I)


def test_extensions_are_if_not_exists():
    creates = re.findall(r"\bcreate\s+extension\b[^;]*", _code(), flags=re.I)
    assert len(creates) == 2
    for c in creates:
        assert re.search(r"if\s+not\s+exists", c, flags=re.I), c
    assert "pg_cron" in _code() and "pg_net" in _code()


def test_both_schedules_use_utc_equivalents_of_ist_times():
    code = _code()
    assert re.search(r"'mandi-ingest-0730-ist'\s*,\s*'0 2 \* \* \*'", code)
    assert re.search(r"'mandi-ingest-1930-ist'\s*,\s*'0 14 \* \* \*'", code)
    assert len(re.findall(r"cron\.schedule\(", code)) == 2


def test_calls_pin_the_mumbai_region():
    code = _code()
    assert code.count("'x-region', 'ap-south-1'") == 2
    assert code.count("forceFunctionRegion=ap-south-1") == 2


def test_secrets_come_from_vault_not_the_file():
    assert "vault.decrypted_secrets" in _code()
    assert not re.search(r"eyJ[A-Za-z0-9_-]{10,}", _sql())
    assert "sb_secret_" not in _sql()
    assert "sb_publishable_" not in _sql()
