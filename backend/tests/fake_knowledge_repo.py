"""
fake_knowledge_repo.py - in-memory KnowledgeRepo for tests. No DB, no network.

Same contract as SupabaseKnowledgeRepo and the knowledge_commit_change SQL
function: optimistic row_version checks, all-or-nothing commits, append-only
history stores that raise when mutated, and a `fail` flag that simulates a
storage outage (RepoError).
"""
import copy
import itertools
import uuid
from datetime import datetime, timezone
from typing import Optional

from services.knowledge.repo import ConflictError, RepoError
from services.knowledge.status import parse_ts


class ImmutableError(Exception):
    """Raised when something tries to change or remove a history row."""


class AppendOnlyList(list):
    """A list rows can only be added to (append through ``add``)."""

    def add(self, row: dict) -> None:
        list.append(self, copy.deepcopy(row))

    def _no(self, *a, **k):
        raise ImmutableError("append-only store")

    append = extend = insert = remove = pop = clear = sort = reverse = _no
    __setitem__ = __delitem__ = __iadd__ = __imul__ = _no


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FakeKnowledgeRepo:
    def __init__(self):
        self.fail = False
        self.admins: dict[str, dict] = {}
        self.invites: list[dict] = []
        self.auth_users: dict[str, dict] = {}  # user_id -> {"email", "email_confirmed"}
        self.items: dict[str, dict] = {}
        self.versions = AppendOnlyList()
        self.approvals = AppendOnlyList()
        self.comments = AppendOnlyList()
        self.audit_log = AppendOnlyList()
        self._ids = itertools.count(1)
        self.commits = 0

    # -- test helpers ---------------------------------------------------------
    def add_admin(self, user_id, role="admin", email=None, display_name=None, credential=None, active=True):
        self.admins[user_id] = {
            "user_id": user_id, "email": email or f"{user_id[:8]}@example.test", "role": role,
            "display_name": display_name, "credential": credential, "added_by": None,
            "added_at": now_iso(), "active": active,
        }
        return self.admins[user_id]

    def add_auth_user(self, user_id, email, confirmed=True):
        self.auth_users[user_id] = {"email": email, "email_confirmed": confirmed}

    def add_invite(self, email, role="reviewer", expires_at=None, display_name=None, credential=None):
        row = {"id": str(uuid.uuid4()), "email": email.lower(), "role": role, "display_name": display_name,
               "credential": credential, "invited_by": None, "created_at": now_iso(),
               "expires_at": expires_at or "2099-01-01T00:00:00+00:00", "consumed_at": None}
        self.invites.append(row)
        return row

    def delete_item(self, item_id):
        raise ImmutableError("items are never deleted")

    def truncate(self, table):
        raise ImmutableError("TRUNCATE is not allowed")

    def _check(self):
        if self.fail:
            raise RepoError("simulated outage")

    # -- identities ------------------------------------------------------------
    def get_admin(self, user_id):
        self._check()
        return copy.deepcopy(self.admins.get(str(user_id)))

    def list_admins(self):
        self._check()
        return copy.deepcopy(sorted(self.admins.values(), key=lambda r: r["user_id"]))

    def count_active_admins(self):
        self._check()
        return sum(1 for a in self.admins.values() if a["role"] == "admin" and a["active"])

    def get_auth_user(self, user_id):
        self._check()
        return copy.deepcopy(self.auth_users.get(str(user_id)))

    def find_auth_user_by_email(self, email):
        self._check()
        for uid, u in self.auth_users.items():
            if (u["email"] or "").lower() == email.strip().lower():
                return {"id": uid, "email": u["email"]}
        return None

    def get_invite_for_email(self, email, now_iso_):
        self._check()
        now = parse_ts(now_iso_)
        rows = [i for i in self.invites if i["email"] == email.strip().lower()
                and i["consumed_at"] is None and parse_ts(i["expires_at"]) > now]
        return copy.deepcopy(rows[-1]) if rows else None

    def list_pending_invites(self, now_iso_):
        self._check()
        now = parse_ts(now_iso_)
        return copy.deepcopy([i for i in self.invites if i["consumed_at"] is None and parse_ts(i["expires_at"]) > now])

    # -- items --------------------------------------------------------------------
    def get_item(self, item_id):
        self._check()
        return copy.deepcopy(self.items.get(item_id))

    def all_items(self):
        self._check()
        return copy.deepcopy([self.items[k] for k in sorted(self.items)])

    def list_items(self, filters, limit, offset):
        self._check()
        rows = [self.items[k] for k in sorted(self.items)]
        for key in ("status", "topic", "region", "risk_level"):
            if filters.get(key):
                rows = [r for r in rows if r[key] == filters[key]]
        if filters.get("has_conflict") is not None:
            rows = [r for r in rows if bool(r["has_conflict"]) == bool(filters["has_conflict"])]
        q = (filters.get("q") or "").strip().lower()
        if q:
            rows = [r for r in rows if q in (r["id"] or "").lower() or q in (r.get("subtopic") or "").lower()
                    or q in (r.get("summary") or "").lower()]
        return copy.deepcopy(rows[offset:offset + limit]), len(rows)

    def list_expired(self, now_iso_):
        self._check()
        now = parse_ts(now_iso_)
        return copy.deepcopy([r for _, r in sorted(self.items.items())
                              if r["status"] == "APPROVED" and r["expires_at"] and parse_ts(r["expires_at"]) <= now])

    # -- history --------------------------------------------------------------------
    def get_version(self, item_id, version):
        self._check()
        for v in self.versions:
            if v["item_id"] == item_id and v["version"] == version:
                return copy.deepcopy(v)
        return None

    def list_versions(self, item_id):
        self._check()
        return copy.deepcopy(sorted((v for v in self.versions if v["item_id"] == item_id), key=lambda v: v["version"]))

    def get_current_versions(self, items):
        self._check()
        want = {i["id"]: i["current_version"] for i in items}
        return {v["item_id"]: copy.deepcopy(v) for v in self.versions
                if want.get(v["item_id"]) == v["version"] and not v["is_proposal"]}

    def list_approvals(self, item_id):
        self._check()
        return copy.deepcopy([a for a in self.approvals if a["item_id"] == item_id])

    def list_comments(self, item_id):
        self._check()
        return copy.deepcopy([c for c in self.comments if c["item_id"] == item_id])

    def list_audit(self, item_id, limit, offset):
        self._check()
        rows = [a for a in self.audit_log if item_id is None or a["item_id"] == item_id]
        rows = sorted(rows, key=lambda a: a["id"], reverse=True)
        return copy.deepcopy(rows[offset:offset + limit]), len(rows)

    # -- the one write path ---------------------------------------------------------------
    def commit_change(self, payload):
        self._check()
        p = copy.deepcopy(payload)
        aud = p.get("audit")
        if not isinstance(aud, dict):
            raise RepoError("audit_required")
        it, ver, apr, cmt = p.get("item"), p.get("version"), p.get("approval"), p.get("comment")
        adm, inv = p.get("admin_user"), p.get("invite")
        expected = p.get("expected_row_version")

        # validate everything first so a failure leaves no partial write
        new_item_id = None
        if it:
            if expected is None:
                if it["id"] in self.items:
                    raise ConflictError("exists")
                new_item_id = it["id"]
            else:
                cur = self.items.get(it["id"])
                if cur is None or cur["row_version"] != expected:
                    raise ConflictError("row_version_conflict")
        known = lambda item_id: item_id in self.items or item_id == new_item_id  # noqa: E731
        if ver:
            if not known(ver["item_id"]) or any(
                    v["item_id"] == ver["item_id"] and v["version"] == ver["version"] for v in self.versions):
                raise ConflictError("version taken")
        for row in (apr, cmt):
            if row and not known(row["item_id"]):
                raise RepoError("unknown item")
        if adm:
            r = adm["row"]
            if adm["op"] == "insert" and r["user_id"] in self.admins:
                raise ConflictError("exists")
            if adm["op"] == "set_active":
                if r["user_id"] not in self.admins:
                    raise ConflictError("not found")
                others = [a for uid, a in self.admins.items()
                          if uid != r["user_id"] and a["role"] == "admin" and a["active"]]
                target = self.admins[r["user_id"]]
                still = bool(others) or (target["role"] == "admin" and r["active"])
                if not still:
                    raise ConflictError("last admin")
        if inv and inv["op"] == "consume":
            row = next((i for i in self.invites if i["id"] == inv["id"] and i["consumed_at"] is None), None)
            if row is None:
                raise ConflictError("invite used")

        # apply
        self.commits += 1
        result = {}
        stamp = now_iso()
        if it:
            if expected is None:
                row = {**{k: it.get(k) for k in (
                    "id", "current_version", "status", "risk_level", "topic", "subtopic", "summary", "region",
                    "has_conflict", "approved_at", "expires_at", "retired_reason", "created_by")},
                    "row_version": 1, "created_at": stamp, "updated_at": stamp}
            else:
                row = {**self.items[it["id"]], **{k: it.get(k) for k in (
                    "current_version", "status", "risk_level", "topic", "subtopic", "summary", "region",
                    "has_conflict", "approved_at", "expires_at", "retired_reason")}}
                row["row_version"] = self.items[it["id"]]["row_version"] + 1
                row["updated_at"] = stamp
            self.items[it["id"]] = row
            result = copy.deepcopy(row)
        if ver:
            self.versions.add({**ver, "created_at": ver.get("created_at") or stamp})
        if apr:
            self.approvals.add({**apr, "id": next(self._ids), "created_at": apr.get("created_at") or stamp})
        if cmt:
            self.comments.add({**cmt, "id": next(self._ids), "created_at": cmt.get("created_at") or stamp})
        if adm:
            r = adm["row"]
            if adm["op"] == "insert":
                self.admins[r["user_id"]] = {
                    "user_id": r["user_id"], "email": r["email"].lower(), "role": r["role"],
                    "display_name": r.get("display_name"), "credential": r.get("credential"),
                    "added_by": r.get("added_by"), "added_at": stamp, "active": True}
            elif adm["op"] == "upsert":
                cur = self.admins.get(r["user_id"])
                if cur is None:
                    self.admins[r["user_id"]] = {
                        "user_id": r["user_id"], "email": r["email"].lower(), "role": r["role"],
                        "display_name": r.get("display_name"), "credential": r.get("credential"),
                        "added_by": r.get("added_by"), "added_at": stamp, "active": True}
                elif cur["role"] == "reviewer":
                    cur["display_name"], cur["credential"] = r.get("display_name"), r.get("credential")
            elif adm["op"] == "set_active":
                self.admins[r["user_id"]]["active"] = bool(r["active"])
        if inv:
            if inv["op"] == "insert":
                self.invites.append({
                    "id": str(uuid.uuid4()), "email": inv["email"].lower(), "role": inv["role"],
                    "display_name": inv.get("display_name"), "credential": inv.get("credential"),
                    "invited_by": inv.get("invited_by"), "created_at": stamp,
                    "expires_at": inv["expires_at"], "consumed_at": None})
            else:
                next(i for i in self.invites if i["id"] == inv["id"])["consumed_at"] = stamp
        self.audit_log.add({**aud, "id": next(self._ids), "created_at": aud.get("created_at") or stamp})
        return result
