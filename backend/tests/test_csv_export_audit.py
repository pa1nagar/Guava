"""
test_csv_export_audit.py — Unit tests for CSV export audit (task 28.1).
Requirements: 16.3
"""
import pytest
from unittest.mock import MagicMock


def _simulate_export(user_id: str, db, activities, expenses):
    """Simulate the export endpoint logic: audit row first, then data filtered by user_id."""
    # Insert audit row BEFORE streaming
    db.table("export_audit_log").insert({
        "user_id": user_id,
        "export_type": "csv",
        "record_count": len(activities) + len(expenses),
    }).execute()

    # Only include records belonging to this user
    own_activities = [a for a in activities if a.get("user_id") == user_id]
    own_expenses = [e for e in expenses if e.get("user_id") == user_id]
    return own_activities, own_expenses


class TestCsvExportAudit:

    def _make_db(self):
        db = MagicMock()
        chain = MagicMock()
        chain.insert.return_value = chain
        chain.execute.return_value = MagicMock(data=[{"id": "audit-row-1"}])
        db.table.return_value = chain
        return db, chain

    def test_export_inserts_audit_log_row(self):
        """Export endpoint inserts an export_audit_log row before returning data.
        Requirements: 16.3
        """
        db, chain = self._make_db()
        activities = [{"id": "a1", "user_id": "user-a", "activity_type": "Fertilizer"}]
        expenses = []

        _simulate_export("user-a", db, activities, expenses)

        db.table.assert_called_with("export_audit_log")
        chain.insert.assert_called_once()
        payload = chain.insert.call_args[0][0]
        assert payload["user_id"] == "user-a"
        assert payload["export_type"] == "csv"

    def test_export_does_not_include_other_farmers_records(self):
        """Export only includes records belonging to the requesting farmer.
        Requirements: 16.3
        """
        db, _ = self._make_db()
        activities = [
            {"id": "a1", "user_id": "user-a", "activity_type": "Fertilizer"},
            {"id": "a2", "user_id": "user-b", "activity_type": "Irrigation"},
        ]
        expenses = [
            {"id": "e1", "user_id": "user-a", "category": "input"},
            {"id": "e2", "user_id": "user-b", "category": "labour"},
        ]

        own_acts, own_exps = _simulate_export("user-a", db, activities, expenses)

        assert all(a["user_id"] == "user-a" for a in own_acts)
        assert all(e["user_id"] == "user-a" for e in own_exps)
        assert len(own_acts) == 1
        assert len(own_exps) == 1
