"""
repo.py - storage seam for the knowledge admin module.

KnowledgeRepo is the interface the service and access layers use.
SupabaseKnowledgeRepo is the production implementation (service-role client);
tests supply an in-memory implementation of the same contract
(tests/fake_knowledge_repo.py).

Every write goes through commit_change(), which calls the Postgres function
knowledge_commit_change(jsonb): one transaction, optimistic row_version check.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)

PAGE = 1000
MAX_PAGES = 50

ITEM_COLUMNS = (
    "id, current_version, status, risk_level, topic, subtopic, summary, region, has_conflict, "
    "approved_at, expires_at, retired_reason, row_version, created_by, created_at, updated_at"
)
ADMIN_COLUMNS = "user_id, email, role, display_name, credential, added_by, added_at, active"
INVITE_COLUMNS = "id, email, role, display_name, credential, invited_by, created_at, expires_at"


class RepoError(Exception):
    """Storage layer failure (maps to 503)."""


class ConflictError(Exception):
    """The item changed since it was read, or a unique key is taken (maps to 409)."""


class KnowledgeRepo(Protocol):
    # identities
    def get_admin(self, user_id: str) -> Optional[dict]: ...
    def list_admins(self) -> list[dict]: ...
    def count_active_admins(self) -> int: ...
    def get_auth_user(self, user_id: str) -> Optional[dict]: ...  # {"email", "email_confirmed"}
    def find_auth_user_by_email(self, email: str) -> Optional[dict]: ...  # {"id", "email"}
    def get_invite_for_email(self, email: str, now_iso: str) -> Optional[dict]: ...
    def list_pending_invites(self, now_iso: str) -> list[dict]: ...
    # items
    def get_item(self, item_id: str) -> Optional[dict]: ...
    def all_items(self) -> list[dict]: ...
    def list_items(self, filters: dict, limit: int, offset: int) -> tuple[list[dict], int]: ...
    def list_expired(self, now_iso: str) -> list[dict]: ...
    # history
    def get_version(self, item_id: str, version: int) -> Optional[dict]: ...
    def list_versions(self, item_id: str) -> list[dict]: ...
    def get_current_versions(self, items: list[dict]) -> dict[str, dict]: ...
    def list_approvals(self, item_id: str) -> list[dict]: ...
    def list_comments(self, item_id: str) -> list[dict]: ...
    def list_audit(self, item_id: Optional[str], limit: int, offset: int) -> tuple[list[dict], int]: ...
    # the one write path
    def commit_change(self, payload: dict) -> dict: ...


class SupabaseKnowledgeRepo:
    """Production repository on the shared service-role Supabase client."""

    def __init__(self, db: Any = None) -> None:
        self._db_override = db

    @property
    def db(self) -> Any:
        if self._db_override is not None:
            return self._db_override
        from services.db import get_db
        return get_db()

    @staticmethod
    def _run(query: Any, what: str) -> Any:
        try:
            return query.execute()
        except Exception as exc:  # supabase/postgrest raise various types
            logger.error("DB %s failed: %s", what, exc)
            raise RepoError(what) from exc

    def _all(self, make_query, what: str) -> list[dict]:
        rows: list[dict] = []
        for page in range(MAX_PAGES):
            q = make_query().range(page * PAGE, (page + 1) * PAGE - 1)
            chunk = self._run(q, what).data or []
            rows.extend(chunk)
            if len(chunk) < PAGE:
                break
        return rows

    # -- identities -----------------------------------------------------------
    def get_admin(self, user_id: str) -> Optional[dict]:
        res = self._run(
            self.db.table("admin_users").select(ADMIN_COLUMNS).eq("user_id", user_id).limit(1),
            "select admin_users",
        )
        return (res.data or [None])[0]

    def list_admins(self) -> list[dict]:
        return self._all(
            lambda: self.db.table("admin_users").select(ADMIN_COLUMNS).order("added_at").order("user_id"),
            "list admin_users",
        )

    def count_active_admins(self) -> int:
        res = self._run(
            self.db.table("admin_users").select("user_id", count="exact").eq("role", "admin").eq("active", True).limit(1),
            "count admin_users",
        )
        return int(res.count or 0)

    def get_auth_user(self, user_id: str) -> Optional[dict]:
        try:
            user = self.db.auth.admin.get_user_by_id(user_id).user
        except Exception as exc:
            logger.error("auth lookup failed: %s", exc)
            raise RepoError("auth lookup") from exc
        if user is None:
            return None
        return {"email": user.email, "email_confirmed": bool(getattr(user, "email_confirmed_at", None))}

    def find_auth_user_by_email(self, email: str) -> Optional[dict]:
        target = email.strip().lower()
        try:
            for page in range(1, MAX_PAGES + 1):
                users = self.db.auth.admin.list_users(page=page, per_page=PAGE)
                for u in users or []:
                    if (u.email or "").lower() == target:
                        return {"id": str(u.id), "email": u.email}
                if not users or len(users) < PAGE:
                    break
        except Exception as exc:
            logger.error("auth list failed: %s", exc)
            raise RepoError("auth list") from exc
        return None

    def get_invite_for_email(self, email: str, now_iso: str) -> Optional[dict]:
        res = self._run(
            self.db.table("admin_invites").select(INVITE_COLUMNS)
            .eq("email", email.strip().lower()).is_("consumed_at", "null").gt("expires_at", now_iso)
            .order("created_at", desc=True).limit(1),
            "select admin_invites",
        )
        return (res.data or [None])[0]

    def list_pending_invites(self, now_iso: str) -> list[dict]:
        res = self._run(
            self.db.table("admin_invites").select(INVITE_COLUMNS)
            .is_("consumed_at", "null").gt("expires_at", now_iso).order("created_at", desc=True).limit(200),
            "list admin_invites",
        )
        return res.data or []

    # -- items ----------------------------------------------------------------
    def get_item(self, item_id: str) -> Optional[dict]:
        res = self._run(
            self.db.table("knowledge_items").select(ITEM_COLUMNS).eq("id", item_id).limit(1),
            "select knowledge_items",
        )
        return (res.data or [None])[0]

    def all_items(self) -> list[dict]:
        return self._all(
            lambda: self.db.table("knowledge_items").select(ITEM_COLUMNS).order("id"),
            "list knowledge_items",
        )

    def list_items(self, filters: dict, limit: int, offset: int) -> tuple[list[dict], int]:
        q = self.db.table("knowledge_items").select(ITEM_COLUMNS, count="exact")
        for key in ("status", "topic", "region", "risk_level"):
            if filters.get(key):
                q = q.eq(key, filters[key])
        if filters.get("has_conflict") is not None:
            q = q.eq("has_conflict", bool(filters["has_conflict"]))
        text = re.sub(r"[^0-9A-Za-z _.\-]", " ", filters.get("q") or "").strip()
        if text:
            q = q.or_(f"id.ilike.%{text}%,subtopic.ilike.%{text}%,summary.ilike.%{text}%")
        q = q.order("id").range(offset, offset + limit - 1)
        res = self._run(q, "search knowledge_items")
        return (res.data or []), int(res.count or 0)

    def list_expired(self, now_iso: str) -> list[dict]:
        return self._all(
            lambda: self.db.table("knowledge_items").select(ITEM_COLUMNS)
            .eq("status", "APPROVED").lte("expires_at", now_iso).order("id"),
            "list expired",
        )

    # -- history --------------------------------------------------------------
    def get_version(self, item_id: str, version: int) -> Optional[dict]:
        res = self._run(
            self.db.table("knowledge_item_versions").select("*")
            .eq("item_id", item_id).eq("version", version).limit(1),
            "select versions",
        )
        return (res.data or [None])[0]

    def list_versions(self, item_id: str) -> list[dict]:
        return self._all(
            lambda: self.db.table("knowledge_item_versions").select("*").eq("item_id", item_id).order("version"),
            "list versions",
        )

    def get_current_versions(self, items: list[dict]) -> dict[str, dict]:
        want = {i["id"]: i["current_version"] for i in items}
        ids = list(want)
        out: dict[str, dict] = {}
        step = 100
        for i in range(0, len(ids), step):
            part = ids[i:i + step]
            rows = self._all(
                lambda part=part: self.db.table("knowledge_item_versions").select("*")
                .in_("item_id", part).eq("is_proposal", False).order("item_id").order("version"),
                "list current versions",
            )
            for r in rows:
                if want.get(r["item_id"]) == r["version"]:
                    out[r["item_id"]] = r
        return out

    def list_approvals(self, item_id: str) -> list[dict]:
        return self._all(
            lambda: self.db.table("knowledge_approvals").select("*").eq("item_id", item_id).order("id"),
            "list approvals",
        )

    def list_comments(self, item_id: str) -> list[dict]:
        return self._all(
            lambda: self.db.table("knowledge_comments").select("*").eq("item_id", item_id).order("id"),
            "list comments",
        )

    def list_audit(self, item_id: Optional[str], limit: int, offset: int) -> tuple[list[dict], int]:
        q = self.db.table("knowledge_audit_log").select("*", count="exact")
        if item_id:
            q = q.eq("item_id", item_id)
        q = q.order("id", desc=True).range(offset, offset + limit - 1)
        res = self._run(q, "list audit")
        return (res.data or []), int(res.count or 0)

    # -- the one write path ---------------------------------------------------
    def commit_change(self, payload: dict) -> dict:
        try:
            res = self.db.rpc("knowledge_commit_change", {"p": payload}).execute()
        except Exception as exc:
            text = str(exc)
            if "row_version_conflict" in text or "40001" in text or "23505" in text:
                raise ConflictError("conflict") from exc
            logger.error("DB knowledge_commit_change failed: %s", exc)
            raise RepoError("commit") from exc
        data = res.data
        return data if isinstance(data, dict) else {}


def get_repo() -> KnowledgeRepo:
    """FastAPI dependency. Tests override it with an in-memory repository."""
    return SupabaseKnowledgeRepo()
