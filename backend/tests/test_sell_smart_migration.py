"""
test_sell_smart_migration.py - static checks on the Sell smart migration file.
The file is parsed as text; nothing is run against a database.
"""
import re
from pathlib import Path

SQL_PATH = Path(__file__).resolve().parents[1] / "migrations" / "2026-11-sell-smart.sql"
TABLES = ("sell_settings", "price_alerts", "notifications", "market_price_quality")


def _sql() -> str:
    return SQL_PATH.read_text(encoding="utf-8")


def _code() -> str:
    """SQL without -- comments."""
    return "\n".join(line.split("--", 1)[0] for line in _sql().splitlines())


def test_every_create_table_is_if_not_exists():
    creates = re.findall(r"\bCREATE\s+TABLE\b[^(]*", _code(), flags=re.I)
    assert len(creates) == len(TABLES)
    for c in creates:
        assert re.search(r"IF\s+NOT\s+EXISTS", c, flags=re.I), c


def test_every_create_index_is_if_not_exists():
    for c in re.findall(r"\bCREATE\s+(?:UNIQUE\s+)?INDEX\b[^;]*", _code(), flags=re.I):
        assert re.search(r"^\s*INDEX\s+IF\s+NOT\s+EXISTS|INDEX\s+IF\s+NOT\s+EXISTS", c, flags=re.I), c


def test_rls_enabled_on_every_table():
    code = _code()
    for t in TABLES:
        assert re.search(rf"ALTER\s+TABLE\s+{t}\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY", code, flags=re.I), t


def test_every_policy_is_guarded_by_pg_policies():
    code = _code()
    n_policies = len(re.findall(r"\bCREATE\s+POLICY\b", code, flags=re.I))
    n_guards = len(re.findall(r"SELECT\s+1\s+FROM\s+pg_policies", code, flags=re.I))
    assert n_policies > 0
    assert n_policies == n_guards


def test_no_destructive_statements():
    code = _code()
    assert not re.search(r"\bDROP\b", code, flags=re.I)
    assert not re.search(r"\bTRUNCATE\b", code, flags=re.I)
    assert not re.search(r"\bDELETE\s+FROM\b", code, flags=re.I)


def test_notifications_has_no_client_insert_policy_and_update_is_column_limited():
    code = _code()
    assert not re.search(r"ON\s+notifications\s+FOR\s+INSERT", code, flags=re.I)
    assert re.search(r"GRANT\s+UPDATE\s*\(read_at\)\s+ON\s+notifications", code, flags=re.I)


def test_required_columns_and_checks_present():
    code = _code()
    for fragment in (
        "per_quintal_per_km", "flat_per_quintal", "commission_pct >= 0 AND commission_pct <= 100",
        "radius_km > 0 AND radius_km <= 1500", "road_km_overrides", "at_or_above", "at_or_below",
        "target_rs_per_kg > 0", "deleted_at", "last_trigger_date", "revision_count",
        "'ok', 'warn', 'reject'", "REFERENCES market_prices(id) ON DELETE CASCADE",
    ):
        assert fragment in code, fragment
