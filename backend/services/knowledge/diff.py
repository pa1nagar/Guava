"""
diff.py - pure field-level diff and content hash. No I/O.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Optional


def _flatten(value: Any, prefix: str, out: dict[str, Any]) -> None:
    if isinstance(value, dict) and value:
        for k in value:
            _flatten(value[k], f"{prefix}.{k}" if prefix else str(k), out)
    else:
        out[prefix] = value


def diff(before: Optional[dict], after: Optional[dict]) -> dict[str, dict[str, Any]]:
    """Return {path: {"before": x, "after": y}} for every field that differs.

    Nested objects are compared field by field (dotted paths); lists are compared
    as a whole. A missing field shows as None.
    """
    a: dict[str, Any] = {}
    b: dict[str, Any] = {}
    _flatten(before or {}, "", a)
    _flatten(after or {}, "", b)
    a.pop("", None)
    b.pop("", None)
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(set(a) | set(b)):
        if a.get(path) != b.get(path):
            out[path] = {"before": a.get(path), "after": b.get(path)}
    return out


def content_hash(payload: dict) -> str:
    """SHA-256 of the canonical JSON form of ``payload`` (key order does not matter)."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
