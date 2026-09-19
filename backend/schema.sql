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
  expected_yield_kg  NUMERIC     CHECK (expected_yield_kg IS NULL OR expected_yield_kg > 0),
  vendor_recommendation_consent     BOOLEAN     NOT NULL DEFAULT FALSE,
  vendor_recommendation_consent_at  TIMESTAMPTZ,
  cached_plan        TEXT,
  profile_hash       TEXT,
  plan_generated_at  TIMESTAMPTZ,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Add new columns idempotently for existing databases.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='farmers' AND column_name='expected_yield_kg'
  ) THEN
    ALTER TABLE farmers ADD COLUMN expected_yield_kg NUMERIC
      CHECK (expected_yield_kg IS NULL OR expected_yield_kg > 0);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='farmers' AND column_name='vendor_recommendation_consent'
  ) THEN
    ALTER TABLE farmers ADD COLUMN vendor_recommendation_consent BOOLEAN NOT NULL DEFAULT FALSE;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='farmers' AND column_name='vendor_recommendation_consent_at'
  ) THEN
    ALTER TABLE farmers ADD COLUMN vendor_recommendation_consent_at TIMESTAMPTZ;
  END IF;
END $$;

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

-- ── farm_activities table ─────────────────────────────────────────────────────
-- Ledger of everything a farmer has applied/done on their farm.
CREATE TABLE IF NOT EXISTS farm_activities (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  farmer_id     UUID        NOT NULL REFERENCES farmers(id) ON DELETE CASCADE,
  activity_type TEXT        NOT NULL
                CHECK (activity_type IN ('Fertilizer','Irrigation','Pesticide','Labour','Other')),
  quantity      NUMERIC     NOT NULL CHECK (quantity >= 0),
  unit          TEXT,
  -- cost must be 0 for Irrigation (water is free — enforced at both app and DB level).
  cost          NUMERIC     NOT NULL CHECK (cost >= 0)
                CHECK (activity_type <> 'Irrigation' OR cost = 0),
  notes         TEXT,
  logged_date   DATE        NOT NULL DEFAULT CURRENT_DATE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS farm_activities_farmer_id_idx
  ON farm_activities (farmer_id);

CREATE INDEX IF NOT EXISTS farm_activities_logged_date_idx
  ON farm_activities (farmer_id, logged_date);

-- RLS
ALTER TABLE farm_activities ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'farm_activities' AND policyname = 'Activities select own'
  ) THEN
    CREATE POLICY "Activities select own"
      ON farm_activities FOR SELECT
      USING (
        farmer_id IN (
          SELECT id FROM farmers WHERE user_id = auth.uid()
        )
      );
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'farm_activities' AND policyname = 'Activities insert own'
  ) THEN
    CREATE POLICY "Activities insert own"
      ON farm_activities FOR INSERT
      WITH CHECK (
        farmer_id IN (
          SELECT id FROM farmers WHERE user_id = auth.uid()
        )
      );
  END IF;
END $$;

-- ── harvests table ────────────────────────────────────────────────────────────
-- One record per crop cycle. Write-once; second insert is rejected at app level.
CREATE TABLE IF NOT EXISTS harvests (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  farmer_id       UUID        NOT NULL UNIQUE REFERENCES farmers(id) ON DELETE CASCADE,
  sale_quantity_kg NUMERIC    NOT NULL CHECK (sale_quantity_kg > 0),
  sale_price_per_kg NUMERIC   NOT NULL CHECK (sale_price_per_kg >= 0),
  sale_date       DATE        NOT NULL DEFAULT CURRENT_DATE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE harvests ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'harvests' AND policyname = 'Harvests select own'
  ) THEN
    CREATE POLICY "Harvests select own"
      ON harvests FOR SELECT
      USING (
        farmer_id IN (
          SELECT id FROM farmers WHERE user_id = auth.uid()
        )
      );
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'harvests' AND policyname = 'Harvests insert own'
  ) THEN
    CREATE POLICY "Harvests insert own"
      ON harvests FOR INSERT
      WITH CHECK (
        farmer_id IN (
          SELECT id FROM farmers WHERE user_id = auth.uid()
        )
      );
  END IF;
END $$;

-- ── vendors table ─────────────────────────────────────────────────────────────
-- Manually curated by product owner. No self-registration.
CREATE TABLE IF NOT EXISTS vendors (
  id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  vendor_name    TEXT        NOT NULL,
  product_types  TEXT[]      NOT NULL,   -- e.g. ARRAY['Fertilizer','Pesticide']
  district       TEXT        NOT NULL,
  state          TEXT        NOT NULL,
  phone          TEXT        NOT NULL,
  contact_method TEXT        NOT NULL DEFAULT 'call'
                 CHECK (contact_method IN ('call','whatsapp','both')),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS vendors_district_idx ON vendors (district);

-- Vendors are read-only from the farmer perspective (no RLS insert/update needed).
ALTER TABLE vendors ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'vendors' AND policyname = 'Vendors public read'
  ) THEN
    CREATE POLICY "Vendors public read"
      ON vendors FOR SELECT
      USING (TRUE);
  END IF;
END $$;
