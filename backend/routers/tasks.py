"""
tasks.py — Task calendar endpoints for the Smart Farmer platform.

Endpoints:
  GET  /api/farmers/me/tasks              List tasks (filter: status, plot_id, date range)
  POST /api/farmers/me/tasks              Create a new task
  PUT  /api/farmers/me/tasks/{id}/status  Update task status
  GET  /api/farmers/me/tasks/today        Today's due tasks (Asia/Kolkata)

Business rules:
  - HIGH-risk AI tasks are forced to status='needs-review' regardless of the
    client-supplied status (Requirement 6.3).
  - Status transitions follow the lifecycle:
        suggested → planned → due → completed/skipped/cancelled/needs-review
    Terminal states (completed, skipped, cancelled) allow no further
    transitions.
  - When a task's due date is reached in the Asia/Kolkata timezone, its
    status is promoted from 'planned' to 'due' (Requirement 6.4).
  - Tasks without an explicit due_date are never surfaced in the Today view
    (Requirement 6.5).

Multi-tenant isolation:
  user_id is always derived from JWT via Depends(get_user_id). It is NEVER
  read from the request body. All DB queries filter by user_id. IDOR
  attempts return 404 (not 403) to avoid confirming resource existence.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
"""

# ── Multi-tenant isolation ──────────────────────────────────────────────────
# Security: user_id is always derived from JWT via Depends(get_user_id).
# It is NEVER read from the request body. All DB queries filter by user_id.
# IDOR attempts return 404 (not 403) to avoid confirming resource existence.
# Requirements: 3.2, 3.3, 3.4

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from services.auth import get_user_id
from services.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Timezone ──────────────────────────────────────────────────────────────────
KOLKATA_TZ = ZoneInfo("Asia/Kolkata")


# ── Constants (must match schema.sql CHECK constraints) ──────────────────────

# Valid task statuses. Must match the CHECK constraint on farm_tasks.status.
TASK_STATUSES: list[str] = [
    "suggested", "planned", "due", "completed", "skipped", "cancelled", "needs-review",
]

# Valid task sources. Must match the CHECK constraint on farm_tasks.source.
TASK_SOURCES: list[str] = ["manual", "ai"]

# Valid task priorities. Must match the CHECK constraint on farm_tasks.priority.
TASK_PRIORITIES: list[str] = ["low", "medium", "high"]

# Valid task risk levels. Must match the CHECK constraint on farm_tasks.risk_level.
TASK_RISK_LEVELS: list[str] = ["LOW", "MEDIUM", "HIGH"]

# Valid status transitions.
# Lifecycle: suggested → planned → due → completed/skipped/cancelled/needs-review
# Terminal states (completed, skipped, cancelled) allow no further transitions.
# Practical terminal transitions are allowed from earlier states (e.g. you can
# cancel a suggested task without first promoting it to planned).
TASK_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "suggested":    {"planned", "skipped", "cancelled"},
    "planned":      {"due", "completed", "skipped", "cancelled", "needs-review"},
    "due":          {"completed", "skipped", "cancelled", "needs-review"},
    "needs-review": {"planned", "completed", "skipped", "cancelled"},
    "completed":    set(),   # terminal
    "skipped":      set(),    # terminal
    "cancelled":    set(),    # terminal
}


# ── Pure helper functions (unit-testable without DB) ─────────────────────────

def is_valid_transition(old_status: str, new_status: str) -> bool:
    """Check whether transitioning from old_status to new_status is allowed.

    A no-op transition (same status) is always allowed.
    Terminal states (completed, skipped, cancelled) allow no further
    transitions.
    """
    if old_status == new_status:
        return True
    allowed = TASK_STATUS_TRANSITIONS.get(old_status, set())
    return new_status in allowed


def resolve_task_status(
    source: Optional[str],
    risk_level: Optional[str],
    requested_status: Optional[str],
) -> str:
    """Determine the effective status for a new task.

    HIGH-risk AI tasks are forced to 'needs-review' regardless of the
    client-supplied status (Requirement 6.3).  All other tasks use the
    requested status, defaulting to 'planned' when none is supplied.
    """
    if source == "ai" and risk_level == "HIGH":
        return "needs-review"
    return requested_status or "planned"


def _today_in_kolkata() -> date:
    """Return today's date in the Asia/Kolkata timezone."""
    return datetime.now(KOLKATA_TZ).date()


# ── Models ─────────────────────────────────────────────────────────────────────

class TaskIn(BaseModel):
    """Request payload for creating a new task.

    Only ``title`` is required. All other fields are optional. The server
    derives ``user_id`` from the JWT and overrides the status for HIGH-risk
    AI tasks.
    """

    title: str = Field(min_length=1, max_length=500)
    due_date: Optional[datetime] = None
    plot_id: Optional[str] = None
    farm_id: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    risk_level: Optional[str] = None
    content_record_id: Optional[str] = None
    is_ai_generated: bool = False

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("title is required and must not be blank.")
        return v.strip()

    @field_validator("source")
    @classmethod
    def _validate_source(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in TASK_SOURCES:
            raise ValueError(f"source must be one of: {', '.join(TASK_SOURCES)}")
        return v

    @field_validator("priority")
    @classmethod
    def _validate_priority(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in TASK_PRIORITIES:
            raise ValueError(f"priority must be one of: {', '.join(TASK_PRIORITIES)}")
        return v

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in TASK_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(TASK_STATUSES)}")
        return v

    @field_validator("risk_level")
    @classmethod
    def _validate_risk_level(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in TASK_RISK_LEVELS:
            raise ValueError(f"risk_level must be one of: {', '.join(TASK_RISK_LEVELS)}")
        return v


class TaskOut(BaseModel):
    id: str
    title: str
    due_date: Optional[str] = None
    plot_id: Optional[str] = None
    farm_id: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None
    priority: Optional[str] = None
    status: str
    risk_level: Optional[str] = None
    content_record_id: Optional[str] = None
    is_ai_generated: bool = False
    created_at: str
    updated_at: str


class TaskStatusUpdate(BaseModel):
    """Request payload for updating a task's status."""

    status: str = Field(min_length=1)

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: str) -> str:
        if v not in TASK_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(TASK_STATUSES)}")
        return v


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_task_out(row: dict) -> TaskOut:
    """Convert a raw DB row dict to a TaskOut model."""
    return TaskOut(
        id=str(row["id"]),
        title=row["title"],
        due_date=str(row["due_date"]) if row.get("due_date") is not None else None,
        plot_id=str(row["plot_id"]) if row.get("plot_id") is not None else None,
        farm_id=str(row["farm_id"]) if row.get("farm_id") is not None else None,
        description=row.get("description"),
        source=row.get("source"),
        priority=row.get("priority"),
        status=row["status"],
        risk_level=row.get("risk_level"),
        content_record_id=(
            str(row["content_record_id"])
            if row.get("content_record_id") is not None
            else None
        ),
        is_ai_generated=row.get("is_ai_generated", False),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


# ── GET /api/farmers/me/tasks/today ──────────────────────────────────────────
# NOTE: defined before the parameterised route to avoid any ambiguity.

@router.get("/farmers/me/tasks/today", response_model=List[TaskOut])
def get_tasks_today(user_id: str = Depends(get_user_id)) -> List[TaskOut]:
    """Return tasks due today in the Asia/Kolkata timezone.

    Tasks whose ``due_date`` falls on today's date (Kolkata) are returned.
    Any task still in the ``planned`` status is promoted to ``due``
    (Requirement 6.4).  Tasks without an explicit ``due_date`` are never
    included (Requirement 6.5).
    """
    today = _today_in_kolkata()
    today_start = datetime.combine(today, time.min, tzinfo=KOLKATA_TZ)
    today_end = datetime.combine(today, time.max, tzinfo=KOLKATA_TZ)

    db = get_db()
    try:
        result = (
            db.table("farm_tasks")
            .select("*")
            .eq("user_id", user_id)
            .gte("due_date", today_start.isoformat())
            .lte("due_date", today_end.isoformat())
            .order("due_date", desc=False)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("DB select today tasks failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    tasks = result.data or []

    # Promote planned → due (Requirement 6.4).
    for task in tasks:
        if task.get("status") == "planned":
            try:
                (
                    db.table("farm_tasks")
                    .update({"status": "due"})
                    .eq("id", task["id"])
                    .eq("user_id", user_id)
                    .execute()
                )
                task["status"] = "due"
            except Exception as exc:  # noqa: BLE001
                # Log but do not fail the request — the task is still returned.
                logger.error("DB promote task %s to due failed: %s", task.get("id"), exc)

    return [_to_task_out(t) for t in tasks]


# ── GET /api/farmers/me/tasks ─────────────────────────────────────────────────

@router.get("/farmers/me/tasks", response_model=List[TaskOut])
def list_tasks(
    status: Optional[str] = None,
    plot_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    user_id: str = Depends(get_user_id),
) -> List[TaskOut]:
    """List the authenticated farmer's tasks with optional filters.

    Query params:
      status     — filter by exact status value
      plot_id    — filter by exact plot_id
      date_from  — include tasks with due_date >= this date (inclusive, Asia/Kolkata)
      date_to    — include tasks with due_date <= this date (inclusive, Asia/Kolkata)
    """
    db = get_db()
    try:
        query = db.table("farm_tasks").select("*").eq("user_id", user_id)

        if status:
            query = query.eq("status", status)
        if plot_id:
            query = query.eq("plot_id", plot_id)
        if date_from:
            start = datetime.combine(date_from, time.min, tzinfo=KOLKATA_TZ)
            query = query.gte("due_date", start.isoformat())
        if date_to:
            end = datetime.combine(date_to, time.max, tzinfo=KOLKATA_TZ)
            query = query.lte("due_date", end.isoformat())

        result = query.order("due_date", desc=False).execute()
    except Exception as exc:  # noqa: BLE001
        logger.error("DB select tasks failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    tasks = result.data or []
    return [_to_task_out(t) for t in tasks]


# ── POST /api/farmers/me/tasks ────────────────────────────────────────────────

@router.post("/farmers/me/tasks", response_model=TaskOut)
def create_task(body: TaskIn, user_id: str = Depends(get_user_id)) -> TaskOut:
    """Create a new task for the authenticated farmer.

    HIGH-risk AI tasks are forced to ``status='needs-review'`` regardless of
    the client-supplied status (Requirement 6.3).
    """
    # Resolve effective status — HIGH-risk AI tasks always need review.
    effective_status = resolve_task_status(body.source, body.risk_level, body.status)

    # is_ai_generated is True if explicitly set OR if source is 'ai'.
    is_ai_generated = body.is_ai_generated or (body.source == "ai")

    payload: dict = {
        "user_id": user_id,
        "title": body.title,
        "due_date": body.due_date.isoformat() if body.due_date else None,
        "plot_id": body.plot_id,
        "farm_id": body.farm_id,
        "description": body.description,
        "source": body.source,
        "priority": body.priority,
        "status": effective_status,
        "risk_level": body.risk_level,
        "content_record_id": body.content_record_id,
        "is_ai_generated": is_ai_generated,
    }

    db = get_db()
    try:
        result = db.table("farm_tasks").insert(payload).execute()
    except Exception as exc:  # noqa: BLE001
        logger.error("DB insert task failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    if not result.data:
        raise HTTPException(status_code=500, detail="Database error.")
    return _to_task_out(result.data[0])


# ── PUT /api/farmers/me/tasks/{task_id}/status ────────────────────────────────

@router.put("/farmers/me/tasks/{task_id}/status", response_model=TaskOut)
def update_task_status(
    task_id: str,
    body: TaskStatusUpdate,
    user_id: str = Depends(get_user_id),
) -> TaskOut:
    """Update a task's status.

    Validates that the transition is allowed per the lifecycle rules.
    Returns 404 when the task does not belong to the requesting farmer
    (IDOR prevention).
    """
    db = get_db()

    # Fetch the task — filter by both id AND user_id (IDOR prevention → 404).
    try:
        result = (
            db.table("farm_tasks")
            .select("*")
            .eq("id", task_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("DB select task failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Task not found.")

    task = result.data

    # Validate the transition is allowed.
    if not is_valid_transition(task["status"], body.status):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid status transition: '{task['status']}' → '{body.status}'. "
                f"Allowed transitions from '{task['status']}': "
                f"{', '.join(sorted(TASK_STATUS_TRANSITIONS.get(task['status'], set()))) or 'none (terminal state)'}."
            ),
        )

    # Apply the update — filter by both id AND user_id (belt-and-suspenders).
    try:
        update_result = (
            db.table("farm_tasks")
            .update({"status": body.status})
            .eq("id", task_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("DB update task status failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error.")

    if not update_result.data:
        raise HTTPException(status_code=404, detail="Task not found.")
    return _to_task_out(update_result.data[0])
