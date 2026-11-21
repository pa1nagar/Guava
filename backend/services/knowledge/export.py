"""
export.py - CSV and JSON export of the knowledge items. CSV cells that a
spreadsheet could run as a formula are neutralised.
"""
from __future__ import annotations

import csv
import io
from typing import Any

COLUMNS = (
    "id", "status", "risk_level", "topic", "subtopic", "region", "has_conflict", "current_version",
    "approved_at", "expires_at", "involves_chemical", "cibrc_check_required", "source_confidence",
    "statement_en", "statement_hi", "source_urls",
)
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r", "\n")


def safe_cell(value: Any) -> Any:
    """Prefix text that starts with = + - @ (or a control character) with an apostrophe."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return value
    text = str(value)
    return "'" + text if text.startswith(_FORMULA_START) else text


def _row(item: dict) -> list[Any]:
    payload = item.get("payload") or {}
    flat = {**{k: item.get(k) for k in COLUMNS}, **{k: payload.get(k) for k in (
        "involves_chemical", "cibrc_check_required", "source_confidence", "statement_en", "statement_hi")}}
    flat["source_urls"] = " | ".join(s.get("url", "") for s in payload.get("sources", []))
    return [safe_cell(flat.get(c)) for c in COLUMNS]


def items_to_csv(items: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(COLUMNS)
    for item in items:
        writer.writerow(_row(item))
    return buf.getvalue()
