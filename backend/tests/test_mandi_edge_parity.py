"""
test_mandi_edge_parity.py - keeps the Python parser and the Edge Function parser
(supabase/functions/mandi-ingest/parse.ts) in step. Both are checked against
fixtures/mandi_edge_parity.json; parse_test.ts runs the TypeScript side.
"""
import json
import re
from datetime import datetime
from pathlib import Path

from services.mandi_prices import CONFLICT_COLUMNS, parse_records

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "mandi_edge_parity.json"
PARSE_TS = ROOT / "supabase" / "functions" / "mandi-ingest" / "parse.ts"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_python_parser_matches_expected_rows():
    fx = _fixture()
    rows, skipped = parse_records(fx["records"], datetime.fromisoformat(fx["fetched_at"]))
    assert rows == fx["expected_rows"]
    assert skipped == fx["expected_skipped"]


def test_fixture_covers_edge_cases():
    fx = _fixture()
    assert fx["expected_skipped"] >= 5
    assert len(fx["expected_rows"]) >= 10
    assert any(r["min_price"] is None for r in fx["expected_rows"])


def test_conflict_columns_match_typescript():
    ts = PARSE_TS.read_text(encoding="utf-8")
    match = re.search(r'CONFLICT_COLUMNS\s*=\s*"([^"]+)"', ts)
    assert match, "CONFLICT_COLUMNS not found in parse.ts"
    assert match.group(1) == CONFLICT_COLUMNS
