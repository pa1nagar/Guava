-- schema.sql — Supabase Postgres schema for the Guava Care feature.
--
-- HOW TO APPLY:
--   Run this in the Supabase SQL Editor for your project.
--   Safe to re-run — uses IF NOT EXISTS / CREATE OR REPLACE throughout.
--
-- AFTER RUNNING:
--   Enable Google OAuth in the Supabase Auth dashboard and add
--   https://guavaa.netlify.app to the allowed redirect URLs.

-- ── Extensions ────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── farmers table ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS farmers (
  id                 UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id            UUID        NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
  crop               TEXT        NOT NULL,
  plant_count        INTEGER     NOT NULL CHECK (plant_count > 0),
  state              TEXT        NOT NULL,
  district           TEXT        NOT NULL,
  sowing_date        DATE        NOT NULL,
  cached_plan        TEXT,
  profile_hash       TEXT,
  plan_generated_at  TIMESTAMPTZ,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Row Level Security ────────────────────────────────────────────────────────
ALTER TABLE farmers ENABLE ROW LEVEL SECURITY;

-- A farmer can only read their own row.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'farmers' AND policyname = 'Farmers can read own row'
  ) THEN
    CREATE POLICY "Farmers can read own row"
      ON farmers FOR SELECT
      USING (auth.uid() = user_id);
  END IF;
END $$;

-- A farmer can only insert their own row.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'farmers' AND policyname = 'Farmers can insert own row'
  ) THEN
    CREATE POLICY "Farmers can insert own row"
      ON farmers FOR INSERT
      WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

-- A farmer can only update their own row.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'farmers' AND policyname = 'Farmers can update own row'
  ) THEN
    CREATE POLICY "Farmers can update own row"
      ON farmers FOR UPDATE
      USING (auth.uid() = user_id);
  END IF;
END $$;

-- ── auto-update updated_at ────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop and recreate trigger so this script is idempotent.
DROP TRIGGER IF EXISTS farmers_updated_at ON farmers;

CREATE TRIGGER farmers_updated_at
  BEFORE UPDATE ON farmers
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
