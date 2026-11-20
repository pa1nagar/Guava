"""
test_sell_smart_harden_migration.py - static checks on the hardening migration.
The file is parsed as text; nothing is run against a database.
"""
import re
from pathlib import Path

from services.sell_smart import config as cfg

SQL_PATH = Path(__file__).resolve().parents[1] / "migrations" / "2026-11-sell-smart-harden.sql"


def _code() -> str:
    text = SQL_PATH.read_text(encoding="utf-8")
    return "\n".join(line.split("--", 1)[0] for line in text.splitlines())


def test_only_drop_policy_if_exists():
    code = _code()
    drops = re.findall(r"\bDROP\b[^;]*;", code, flags=re.I)
    assert len(drops) == 4
    for d in drops:
        assert re.match(r"DROP\s+POLICY\s+IF\s+EXISTS\b", d, flags=re.I), d


def test_drops_exactly_the_four_client_write_policies():
    code = _code()
    names = set(re.findall(r'DROP\s+POLICY\s+IF\s+EXISTS\s+"([^"]+)"', code, flags=re.I))
    assert names == {
        "Price alerts insert own", "Price alerts update own",
        "Sell settings insert own", "Sell settings update own",
    }


def test_no_other_destructive_statements():
    code = _code()
    assert not re.search(r"\bDROP\s+(TABLE|COLUMN|CONSTRAINT|INDEX)\b", code, flags=re.I)
    assert not re.search(r"\bTRUNCATE\b", code, flags=re.I)
    assert not re.search(r"\bDELETE\s+FROM\b", code, flags=re.I)


def test_revokes_client_writes():
    assert re.search(
        r"REVOKE\s+INSERT,\s*UPDATE,\s*DELETE\s+ON\s+price_alerts,\s*sell_settings\s+FROM\s+anon,\s*authenticated",
        _code(), flags=re.I)


def test_select_policies_not_touched():
    assert not re.search(r"select own", _code(), flags=re.I)


def test_every_check_is_guarded():
    code = _code()
    adds = re.findall(r"ADD\s+CONSTRAINT\s+(\w+)", code, flags=re.I)
    guards = re.findall(r"SELECT\s+1\s+FROM\s+pg_constraint\s+WHERE\s+conname\s*=\s*'(\w+)'", code, flags=re.I)
    assert len(adds) == 4
    assert sorted(adds) == sorted(guards)


def test_length_constraints_match_config():
    code = _code()
    for col in ("state", "district", "market_name"):
        m = re.search(rf"char_length\({col}\)\s*<=\s*(\d+)", code)
        assert m and int(m.group(1)) == cfg.MAX_NAME_LENGTH, col
    assert "jsonb_typeof(road_km_overrides) = 'object'" in code