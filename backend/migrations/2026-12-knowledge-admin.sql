-- =============================================================================
-- Knowledge admin: admin identities, the versioned knowledge base, approvals,
-- comments and an append-only audit log.
--
-- NOT APPLIED BY CODE. The project owner runs this file once in the Supabase
-- SQL editor (Dashboard > SQL Editor > New query > paste > Run). It is additive
-- and idempotent: running it twice changes nothing the second time.
--
-- Owner steps
--   1. Run this whole file in the SQL editor.
--   2. Make the first admin. Either
--        a) set ADMIN_BOOTSTRAP_EMAILS (comma list of your own Google account
--           emails) on the backend host. The first confirmed sign-in from one of
--           those emails becomes admin, but only while no active admin exists; or
--        b) run this one line (replace the placeholders; never commit real values):
--           insert into admin_users (user_id, email, role, display_name, added_by) values ('<AUTH_USER_UUID>', '<ADMIN_EMAIL>', 'admin', '<DISPLAY_NAME>', '<AUTH_USER_UUID>');
--   3. Sign in on admin.html and add reviewers from the Reviewers tab.
--
-- Security model
--   * Row level security is ON for every table and there are NO policies, so the
--     anon and authenticated roles can read and write nothing. Only the backend
--     (service role, which bypasses RLS) touches these tables.
--   * History tables (versions, approvals, comments, audit log) cannot be
--     updated, deleted or truncated by anyone: triggers raise, and UPDATE,
--     DELETE and TRUNCATE are revoked from every role including service_role.
--   * Every write goes through knowledge_commit_change(jsonb), one transaction
--     with an optimistic row_version check. Only service_role may execute it.
-- =============================================================================

-- -- Tables -------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS admin_users (
    user_id      uuid PRIMARY KEY REFERENCES auth.users (id),
    email        text NOT NULL,
    role         text NOT NULL CHECK (role IN ('admin', 'reviewer')),
    display_name text,
    credential   text,
    added_by     uuid,
    added_at     timestamptz NOT NULL DEFAULT now(),
    active       boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS admin_invites (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email        text NOT NULL,
    role         text NOT NULL CHECK (role IN ('admin', 'reviewer')),
    display_name text,
    credential   text,
    invited_by   uuid,
    created_at   timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL,
    consumed_at  timestamptz,
    consumed_by  uuid
);

CREATE TABLE IF NOT EXISTS knowledge_items (
    id              text PRIMARY KEY,
    current_version integer NOT NULL DEFAULT 1,
    status          text NOT NULL DEFAULT 'DRAFT'
                    CHECK (status IN ('DRAFT', 'IN_REVIEW', 'CHANGES_REQUESTED', 'APPROVED', 'REJECTED', 'RETIRED')),
    risk_level      text NOT NULL CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH')),
    topic           text NOT NULL,
    subtopic        text,
    summary         text,
    region          text NOT NULL CHECK (region IN ('MP', 'MH', 'ALL')),
    has_conflict    boolean NOT NULL DEFAULT false,
    approved_at     timestamptz,
    expires_at      timestamptz,
    retired_reason  text,
    row_version     integer NOT NULL DEFAULT 1,
    created_by      text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS knowledge_item_versions (
    item_id      text NOT NULL REFERENCES knowledge_items (id),
    version      integer NOT NULL,
    is_proposal  boolean NOT NULL DEFAULT false,
    payload      jsonb NOT NULL,
    content_hash text NOT NULL,
    created_by   text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    change_reason text,
    PRIMARY KEY (item_id, version)
);

CREATE TABLE IF NOT EXISTS knowledge_approvals (
    id                  bigserial PRIMARY KEY,
    item_id             text NOT NULL REFERENCES knowledge_items (id),
    version             integer NOT NULL,
    decision            text NOT NULL
                        CHECK (decision IN ('approve', 'reject', 'request_changes', 'proposal_accept', 'proposal_decline')),
    approver_id         uuid NOT NULL,
    approver_role       text NOT NULL CHECK (approver_role IN ('admin', 'reviewer')),
    approver_name       text,
    approver_credential text,
    reason              text,
    expires_at          timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS knowledge_comments (
    id          bigserial PRIMARY KEY,
    item_id     text NOT NULL REFERENCES knowledge_items (id),
    version     integer,
    author_id   uuid NOT NULL,
    author_role text NOT NULL CHECK (author_role IN ('admin', 'reviewer')),
    author_name text,
    body        text NOT NULL CHECK (char_length(body) BETWEEN 1 AND 4000),
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS knowledge_audit_log (
    id          bigserial PRIMARY KEY,
    actor_id    uuid,
    actor_role  text,
    actor_name  text,
    action      text NOT NULL,
    item_id     text,
    from_status text,
    to_status   text,
    before      jsonb,
    after       jsonb,
    diff        jsonb,
    reason      text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- -- Indexes ------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_admin_invites_email ON admin_invites (lower(email));
CREATE INDEX IF NOT EXISTS idx_knowledge_items_status ON knowledge_items (status);
CREATE INDEX IF NOT EXISTS idx_knowledge_items_topic ON knowledge_items (topic, region);
CREATE INDEX IF NOT EXISTS idx_knowledge_items_expires ON knowledge_items (expires_at) WHERE status = 'APPROVED';
CREATE INDEX IF NOT EXISTS idx_knowledge_approvals_item ON knowledge_approvals (item_id, id);
CREATE INDEX IF NOT EXISTS idx_knowledge_comments_item ON knowledge_comments (item_id, id);
CREATE INDEX IF NOT EXISTS idx_knowledge_audit_item ON knowledge_audit_log (item_id, id);
CREATE INDEX IF NOT EXISTS idx_knowledge_audit_created ON knowledge_audit_log (created_at);

-- -- Row level security: enabled everywhere, no policies (default deny) ------------

ALTER TABLE admin_users              ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_invites            ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_items          ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_item_versions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_approvals      ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_comments       ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_audit_log      ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE admin_users, admin_invites, knowledge_items, knowledge_item_versions,
    knowledge_approvals, knowledge_comments, knowledge_audit_log FROM anon, authenticated;
REVOKE ALL ON SEQUENCE knowledge_approvals_id_seq, knowledge_comments_id_seq,
    knowledge_audit_log_id_seq FROM anon, authenticated;

-- -- Trigger functions ----------------------------------------------------------

CREATE OR REPLACE FUNCTION knowledge_set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION knowledge_block_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% on % is not allowed: this table is append-only', TG_OP, TG_TABLE_NAME
        USING ERRCODE = '42501';
END;
$$;

CREATE OR REPLACE FUNCTION knowledge_block_truncate() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'TRUNCATE on % is not allowed', TG_TABLE_NAME USING ERRCODE = '42501';
END;
$$;

-- -- Triggers -------------------------------------------------------------------

DROP TRIGGER IF EXISTS trg_knowledge_items_updated_at ON knowledge_items;
CREATE TRIGGER trg_knowledge_items_updated_at
    BEFORE UPDATE ON knowledge_items
    FOR EACH ROW EXECUTE FUNCTION knowledge_set_updated_at();

-- Items are never deleted (retire them instead).
DROP TRIGGER IF EXISTS trg_knowledge_items_no_delete ON knowledge_items;
CREATE TRIGGER trg_knowledge_items_no_delete
    BEFORE DELETE ON knowledge_items
    FOR EACH ROW EXECUTE FUNCTION knowledge_block_mutation();

-- History tables: no UPDATE, no DELETE.
DROP TRIGGER IF EXISTS trg_knowledge_versions_immutable ON knowledge_item_versions;
CREATE TRIGGER trg_knowledge_versions_immutable
    BEFORE UPDATE OR DELETE ON knowledge_item_versions
    FOR EACH ROW EXECUTE FUNCTION knowledge_block_mutation();

DROP TRIGGER IF EXISTS trg_knowledge_approvals_immutable ON knowledge_approvals;
CREATE TRIGGER trg_knowledge_approvals_immutable
    BEFORE UPDATE OR DELETE ON knowledge_approvals
    FOR EACH ROW EXECUTE FUNCTION knowledge_block_mutation();

DROP TRIGGER IF EXISTS trg_knowledge_comments_immutable ON knowledge_comments;
CREATE TRIGGER trg_knowledge_comments_immutable
    BEFORE UPDATE OR DELETE ON knowledge_comments
    FOR EACH ROW EXECUTE FUNCTION knowledge_block_mutation();

DROP TRIGGER IF EXISTS trg_knowledge_audit_immutable ON knowledge_audit_log;
CREATE TRIGGER trg_knowledge_audit_immutable
    BEFORE UPDATE OR DELETE ON knowledge_audit_log
    FOR EACH ROW EXECUTE FUNCTION knowledge_block_mutation();

-- TRUNCATE is blocked on every table.
DROP TRIGGER IF EXISTS trg_admin_users_no_truncate ON admin_users;
CREATE TRIGGER trg_admin_users_no_truncate
    BEFORE TRUNCATE ON admin_users
    FOR EACH STATEMENT EXECUTE FUNCTION knowledge_block_truncate();

DROP TRIGGER IF EXISTS trg_admin_invites_no_truncate ON admin_invites;
CREATE TRIGGER trg_admin_invites_no_truncate
    BEFORE TRUNCATE ON admin_invites
    FOR EACH STATEMENT EXECUTE FUNCTION knowledge_block_truncate();

DROP TRIGGER IF EXISTS trg_knowledge_items_no_truncate ON knowledge_items;
CREATE TRIGGER trg_knowledge_items_no_truncate
    BEFORE TRUNCATE ON knowledge_items
    FOR EACH STATEMENT EXECUTE FUNCTION knowledge_block_truncate();

DROP TRIGGER IF EXISTS trg_knowledge_versions_no_truncate ON knowledge_item_versions;
CREATE TRIGGER trg_knowledge_versions_no_truncate
    BEFORE TRUNCATE ON knowledge_item_versions
    FOR EACH STATEMENT EXECUTE FUNCTION knowledge_block_truncate();

DROP TRIGGER IF EXISTS trg_knowledge_approvals_no_truncate ON knowledge_approvals;
CREATE TRIGGER trg_knowledge_approvals_no_truncate
    BEFORE TRUNCATE ON knowledge_approvals
    FOR EACH STATEMENT EXECUTE FUNCTION knowledge_block_truncate();

DROP TRIGGER IF EXISTS trg_knowledge_comments_no_truncate ON knowledge_comments;
CREATE TRIGGER trg_knowledge_comments_no_truncate
    BEFORE TRUNCATE ON knowledge_comments
    FOR EACH STATEMENT EXECUTE FUNCTION knowledge_block_truncate();

DROP TRIGGER IF EXISTS trg_knowledge_audit_no_truncate ON knowledge_audit_log;
CREATE TRIGGER trg_knowledge_audit_no_truncate
    BEFORE TRUNCATE ON knowledge_audit_log
    FOR EACH STATEMENT EXECUTE FUNCTION knowledge_block_truncate();

-- -- Privileges -----------------------------------------------------------------

-- History tables: nobody can change or remove rows.
REVOKE UPDATE, DELETE, TRUNCATE ON knowledge_item_versions FROM PUBLIC, anon, authenticated, service_role;
REVOKE UPDATE, DELETE, TRUNCATE ON knowledge_approvals     FROM PUBLIC, anon, authenticated, service_role;
REVOKE UPDATE, DELETE, TRUNCATE ON knowledge_comments      FROM PUBLIC, anon, authenticated, service_role;
REVOKE UPDATE, DELETE, TRUNCATE ON knowledge_audit_log     FROM PUBLIC, anon, authenticated, service_role;
-- Items are updated (never deleted); admin tables are updated by the function.
REVOKE DELETE, TRUNCATE ON knowledge_items FROM PUBLIC, anon, authenticated, service_role;
REVOKE TRUNCATE ON admin_users, admin_invites FROM PUBLIC, anon, authenticated, service_role;

GRANT SELECT, INSERT ON knowledge_item_versions, knowledge_approvals, knowledge_comments,
    knowledge_audit_log TO service_role;
GRANT SELECT, INSERT, UPDATE ON knowledge_items, admin_users, admin_invites TO service_role;
GRANT USAGE, SELECT ON SEQUENCE knowledge_approvals_id_seq, knowledge_comments_id_seq,
    knowledge_audit_log_id_seq TO service_role;

-- -- Atomic write function --------------------------------------------------------
-- p = {
--   item: {...}|null, expected_row_version: int|null (null = create),
--   version: {...}|null, approval: {...}|null, comment: {...}|null,
--   admin_user: {op: insert|upsert|set_active, row: {...}}|null,
--   invite: {op: insert|consume, ...}|null,
--   audit: {...}                       (required)
-- }
-- Raises 'row_version_conflict' (SQLSTATE 40001) when the item changed since the
-- caller read it, when a version number or key is already taken, or when the
-- last active admin would be deactivated.
CREATE OR REPLACE FUNCTION knowledge_commit_change(p jsonb) RETURNS jsonb
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    it       jsonb := p->'item';
    ver      jsonb := p->'version';
    apr      jsonb := p->'approval';
    cmt      jsonb := p->'comment';
    adm      jsonb := p->'admin_user';
    inv      jsonb := p->'invite';
    aud      jsonb := p->'audit';
    r        jsonb;
    expected integer := nullif(p->>'expected_row_version', '')::integer;
    rec      knowledge_items;
    result   jsonb := '{}'::jsonb;
BEGIN
    IF jsonb_typeof(aud) IS DISTINCT FROM 'object' THEN
        RAISE EXCEPTION 'audit_required';
    END IF;

    BEGIN
        IF jsonb_typeof(it) = 'object' THEN
            IF expected IS NULL THEN
                INSERT INTO knowledge_items (
                    id, current_version, status, risk_level, topic, subtopic, summary, region,
                    has_conflict, approved_at, expires_at, retired_reason, row_version, created_by
                ) VALUES (
                    it->>'id', (it->>'current_version')::integer, it->>'status', it->>'risk_level',
                    it->>'topic', it->>'subtopic', it->>'summary', it->>'region',
                    coalesce((it->>'has_conflict')::boolean, false),
                    (it->>'approved_at')::timestamptz, (it->>'expires_at')::timestamptz,
                    it->>'retired_reason', 1, it->>'created_by'
                ) RETURNING * INTO rec;
            ELSE
                UPDATE knowledge_items SET
                    current_version = (it->>'current_version')::integer,
                    status          = it->>'status',
                    risk_level      = it->>'risk_level',
                    topic           = it->>'topic',
                    subtopic        = it->>'subtopic',
                    summary         = it->>'summary',
                    region          = it->>'region',
                    has_conflict    = coalesce((it->>'has_conflict')::boolean, false),
                    approved_at     = (it->>'approved_at')::timestamptz,
                    expires_at      = (it->>'expires_at')::timestamptz,
                    retired_reason  = it->>'retired_reason',
                    row_version     = row_version + 1
                WHERE id = it->>'id' AND row_version = expected
                RETURNING * INTO rec;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'row_version_conflict' USING ERRCODE = '40001';
                END IF;
            END IF;
            result := to_jsonb(rec);
        END IF;

        IF jsonb_typeof(ver) = 'object' THEN
            INSERT INTO knowledge_item_versions (
                item_id, version, is_proposal, payload, content_hash, created_by, created_at, change_reason
            ) VALUES (
                ver->>'item_id', (ver->>'version')::integer,
                coalesce((ver->>'is_proposal')::boolean, false), ver->'payload',
                ver->>'content_hash', ver->>'created_by',
                coalesce((ver->>'created_at')::timestamptz, now()), ver->>'change_reason'
            );
        END IF;

        IF jsonb_typeof(apr) = 'object' THEN
            INSERT INTO knowledge_approvals (
                item_id, version, decision, approver_id, approver_role, approver_name,
                approver_credential, reason, expires_at, created_at
            ) VALUES (
                apr->>'item_id', (apr->>'version')::integer, apr->>'decision',
                (apr->>'approver_id')::uuid, apr->>'approver_role', apr->>'approver_name',
                apr->>'approver_credential', apr->>'reason', (apr->>'expires_at')::timestamptz,
                coalesce((apr->>'created_at')::timestamptz, now())
            );
        END IF;

        IF jsonb_typeof(cmt) = 'object' THEN
            INSERT INTO knowledge_comments (
                item_id, version, author_id, author_role, author_name, body, created_at
            ) VALUES (
                cmt->>'item_id', (cmt->>'version')::integer, (cmt->>'author_id')::uuid,
                cmt->>'author_role', cmt->>'author_name', cmt->>'body',
                coalesce((cmt->>'created_at')::timestamptz, now())
            );
        END IF;

        IF jsonb_typeof(adm) = 'object' THEN
            r := adm->'row';
            IF adm->>'op' = 'insert' THEN
                INSERT INTO admin_users (user_id, email, role, display_name, credential, added_by, active)
                VALUES ((r->>'user_id')::uuid, lower(r->>'email'), r->>'role', r->>'display_name',
                        r->>'credential', (r->>'added_by')::uuid, true);
            ELSIF adm->>'op' = 'upsert' THEN
                INSERT INTO admin_users (user_id, email, role, display_name, credential, added_by, active)
                VALUES ((r->>'user_id')::uuid, lower(r->>'email'), r->>'role', r->>'display_name',
                        r->>'credential', (r->>'added_by')::uuid, true)
                ON CONFLICT (user_id) DO UPDATE
                    SET display_name = EXCLUDED.display_name, credential = EXCLUDED.credential
                    WHERE admin_users.role = 'reviewer';
            ELSIF adm->>'op' = 'set_active' THEN
                UPDATE admin_users SET active = (r->>'active')::boolean
                WHERE user_id = (r->>'user_id')::uuid;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'admin_user_not_found' USING ERRCODE = '40001';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM admin_users WHERE role = 'admin' AND active) THEN
                    RAISE EXCEPTION 'row_version_conflict' USING ERRCODE = '40001';
                END IF;
            ELSE
                RAISE EXCEPTION 'bad_admin_op';
            END IF;
        END IF;

        IF jsonb_typeof(inv) = 'object' THEN
            IF inv->>'op' = 'insert' THEN
                INSERT INTO admin_invites (email, role, display_name, credential, invited_by, expires_at)
                VALUES (lower(inv->>'email'), inv->>'role', inv->>'display_name', inv->>'credential',
                        (inv->>'invited_by')::uuid, (inv->>'expires_at')::timestamptz);
            ELSIF inv->>'op' = 'consume' THEN
                UPDATE admin_invites SET consumed_at = now(), consumed_by = (inv->>'user_id')::uuid
                WHERE id = (inv->>'id')::uuid AND consumed_at IS NULL;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'row_version_conflict' USING ERRCODE = '40001';
                END IF;
            ELSE
                RAISE EXCEPTION 'bad_invite_op';
            END IF;
        END IF;

        INSERT INTO knowledge_audit_log (
            actor_id, actor_role, actor_name, action, item_id, from_status, to_status,
            before, after, diff, reason, created_at
        ) VALUES (
            (aud->>'actor_id')::uuid, aud->>'actor_role', aud->>'actor_name', aud->>'action',
            aud->>'item_id', aud->>'from_status', aud->>'to_status',
            aud->'before', aud->'after', aud->'diff', aud->>'reason',
            coalesce((aud->>'created_at')::timestamptz, now())
        );
    EXCEPTION WHEN unique_violation THEN
        RAISE EXCEPTION 'row_version_conflict' USING ERRCODE = '40001';
    END;

    RETURN result;
END;
$$;

REVOKE ALL ON FUNCTION knowledge_commit_change(jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION knowledge_commit_change(jsonb) FROM anon, authenticated;
GRANT EXECUTE ON FUNCTION knowledge_commit_change(jsonb) TO service_role;
