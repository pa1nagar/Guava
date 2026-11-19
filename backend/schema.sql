-- schema.sql — Supabase Postgres schema for the Smart Farmer platform.
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


-- ═══════════════════════════════════════════════════════════════════════════
-- Smart Farmer — additive schema migration (Task 2)
-- Safe to re-run; all DDL uses IF NOT EXISTS / DO $$ guards.
-- Requirements: 1.3, 1.4
-- ═══════════════════════════════════════════════════════════════════════════

-- ── content_records table ────────────────────────────────────────────────────
-- Central content governance store. Admin-only writes; farmers read APPROVED rows.
-- Requirement 1.3
CREATE TABLE IF NOT EXISTS content_records (
  id                     UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  record_uid             TEXT        NOT NULL UNIQUE,
  title                  TEXT        NOT NULL,
  body                   TEXT        NOT NULL,
  crop                   TEXT,
  risk_level             TEXT        NOT NULL
                         CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH')),
  status                 TEXT        NOT NULL DEFAULT 'DRAFT'
                         CHECK (status IN ('DRAFT','NEEDS_REVIEW','APPROVED','EXPIRED','WITHDRAWN')),
  source_org             TEXT        NOT NULL,
  source_title           TEXT        NOT NULL,
  source_url             TEXT        NOT NULL,
  source_section         TEXT        NOT NULL,
  source_pub_date        DATE        NOT NULL,
  review_expiry          DATE        NOT NULL,
  reviewer_name          TEXT,
  reviewer_credential    TEXT,
  language               TEXT        NOT NULL DEFAULT 'en',
  applicability_metadata JSONB,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS content_records_status_idx
  ON content_records (status);

CREATE INDEX IF NOT EXISTS content_records_review_expiry_idx
  ON content_records (review_expiry) WHERE status = 'APPROVED';

ALTER TABLE content_records ENABLE ROW LEVEL SECURITY;

-- Farmers (and anonymous visitors) may read only APPROVED records.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'content_records' AND policyname = 'Content records public read approved'
  ) THEN
    CREATE POLICY "Content records public read approved"
      ON content_records FOR SELECT
      USING (status = 'APPROVED');
  END IF;
END $$;

-- Auto-update updated_at on every row change.
DROP TRIGGER IF EXISTS content_records_updated_at ON content_records;
CREATE TRIGGER content_records_updated_at
  BEFORE UPDATE ON content_records
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ── content_audit_log table ──────────────────────────────────────────────────
-- Immutable record of every status transition for a ContentRecord.
-- Requirement 1.4 (scheduler writes here after expiring records)
CREATE TABLE IF NOT EXISTS content_audit_log (
  id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  content_record_id UUID        NOT NULL REFERENCES content_records(id) ON DELETE CASCADE,
  old_status        TEXT,
  new_status        TEXT,
  changed_by        TEXT        NOT NULL,   -- admin user_id or 'scheduler'
  changed_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  reason            TEXT
);

CREATE INDEX IF NOT EXISTS content_audit_log_record_idx
  ON content_audit_log (content_record_id);

-- No RLS INSERT from client — rows written by service-role only (scheduler / admin router).
ALTER TABLE content_audit_log ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'content_audit_log' AND policyname = 'Content audit log no client access'
  ) THEN
    -- Block direct client reads/writes; all access goes through the service-role backend.
    CREATE POLICY "Content audit log no client access"
      ON content_audit_log FOR SELECT
      USING (FALSE);
  END IF;
END $$;


-- ── export_audit_log table ───────────────────────────────────────────────────
-- Records every CSV/PDF export for audit purposes.
-- Requirement 16.3
CREATE TABLE IF NOT EXISTS export_audit_log (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  export_type     TEXT        NOT NULL,
  farm_id         UUID,
  date_range_from DATE,
  date_range_to   DATE,
  record_count    INTEGER,
  exported_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS export_audit_log_user_idx
  ON export_audit_log (user_id);

ALTER TABLE export_audit_log ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'export_audit_log' AND policyname = 'Export audit log select own'
  ) THEN
    CREATE POLICY "Export audit log select own"
      ON export_audit_log FOR SELECT
      USING (auth.uid() = user_id);
  END IF;
END $$;


-- ── market_prices table ──────────────────────────────────────────────────────
-- Stores verified market price data points with source provenance.
-- Requirement 9.5, 9.6
CREATE TABLE IF NOT EXISTS market_prices (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  source_name   TEXT        NOT NULL,
  market_name   TEXT        NOT NULL,
  commodity     TEXT        NOT NULL,
  grade         TEXT,
  unit          TEXT        NOT NULL,
  price         NUMERIC     NOT NULL CHECK (price >= 0),
  observed_at   TIMESTAMPTZ NOT NULL,
  ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS market_prices_commodity_idx
  ON market_prices (commodity, observed_at DESC);

-- Market prices are public read — no farmer-specific data.
ALTER TABLE market_prices ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'market_prices' AND policyname = 'Market prices public read'
  ) THEN
    CREATE POLICY "Market prices public read"
      ON market_prices FOR SELECT
      USING (TRUE);
  END IF;
END $$;


-- ═══════════════════════════════════════════════════════════════════════════
-- Smart Farmer — additive schema migration (Task 10)
-- Multi-tenant farm model: farms, plots, crop_cycles, tasks, observations,
-- inventory, expenses, and audit trails.
-- Safe to re-run; all DDL uses IF NOT EXISTS / DO $$ guards.
-- Requirements: 4.1, 4.2, 4.3, 5.4
-- ═══════════════════════════════════════════════════════════════════════════

-- ── farms table ──────────────────────────────────────────────────────────────
-- A named agricultural holding owned by a Farmer (User).
-- Requirement 4.1
CREATE TABLE IF NOT EXISTS farms (
  id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name              TEXT        NOT NULL,
  locality          TEXT,
  district          TEXT        NOT NULL,
  state             TEXT        NOT NULL,
  country           TEXT        NOT NULL DEFAULT 'India',
  timezone          TEXT        NOT NULL DEFAULT 'Asia/Kolkata',
  approx_lat        NUMERIC,
  approx_lon        NUMERIC,
  area_value        NUMERIC,
  area_unit         TEXT        CHECK (area_unit IN ('acres','hectares','sqm')),
  soil_description  TEXT,
  irrigation_method TEXT,
  water_source      TEXT,
  notes             TEXT,
  is_active         BOOLEAN     NOT NULL DEFAULT TRUE,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS farms_user_id_idx
  ON farms (user_id);

ALTER TABLE farms ENABLE ROW LEVEL SECURITY;

-- A farmer can read their own farms.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'farms' AND policyname = 'Farms select own'
  ) THEN
    CREATE POLICY "Farms select own"
      ON farms FOR SELECT
      USING (auth.uid() = user_id);
  END IF;
END $$;

-- A farmer can insert their own farms.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'farms' AND policyname = 'Farms insert own'
  ) THEN
    CREATE POLICY "Farms insert own"
      ON farms FOR INSERT
      WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

-- A farmer can update their own farms.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'farms' AND policyname = 'Farms update own'
  ) THEN
    CREATE POLICY "Farms update own"
      ON farms FOR UPDATE
      USING (auth.uid() = user_id);
  END IF;
END $$;

-- A farmer can delete (archive) their own farms.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'farms' AND policyname = 'Farms delete own'
  ) THEN
    CREATE POLICY "Farms delete own"
      ON farms FOR DELETE
      USING (auth.uid() = user_id);
  END IF;
END $$;

-- Auto-update updated_at on farms.
DROP TRIGGER IF EXISTS farms_updated_at ON farms;
CREATE TRIGGER farms_updated_at
  BEFORE UPDATE ON farms
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ── plots table ─────────────────────────────────────────────────────────────
-- A named sub-unit of a Farm with a crop, variety, and planting details.
-- Requirement 4.2
CREATE TABLE IF NOT EXISTS plots (
  id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  farm_id               UUID        NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
  user_id               UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name                  TEXT        NOT NULL,
  area_value            NUMERIC,
  area_unit             TEXT,
  crop                  TEXT        NOT NULL,
  variety               TEXT,
  planting_date         DATE        NOT NULL,
  planting_method       TEXT,
  row_spacing_m         NUMERIC,
  within_row_spacing_m  NUMERIC,
  plant_count           INTEGER     NOT NULL CHECK (plant_count > 0),
  survival_count        INTEGER,
  notes                 TEXT,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS plots_farm_id_idx
  ON plots (farm_id);

CREATE INDEX IF NOT EXISTS plots_user_id_idx
  ON plots (user_id);

ALTER TABLE plots ENABLE ROW LEVEL SECURITY;

-- A farmer can read their own plots.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'plots' AND policyname = 'Plots select own'
  ) THEN
    CREATE POLICY "Plots select own"
      ON plots FOR SELECT
      USING (auth.uid() = user_id);
  END IF;
END $$;

-- A farmer can insert their own plots.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'plots' AND policyname = 'Plots insert own'
  ) THEN
    CREATE POLICY "Plots insert own"
      ON plots FOR INSERT
      WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

-- A farmer can update their own plots.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'plots' AND policyname = 'Plots update own'
  ) THEN
    CREATE POLICY "Plots update own"
      ON plots FOR UPDATE
      USING (auth.uid() = user_id);
  END IF;
END $$;

-- A farmer can delete their own plots.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'plots' AND policyname = 'Plots delete own'
  ) THEN
    CREATE POLICY "Plots delete own"
      ON plots FOR DELETE
      USING (auth.uid() = user_id);
  END IF;
END $$;

-- Auto-update updated_at on plots.
DROP TRIGGER IF EXISTS plots_updated_at ON plots;
CREATE TRIGGER plots_updated_at
  BEFORE UPDATE ON plots
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ── crop_cycles table ───────────────────────────────────────────────────────
-- Links a crop/variety, Plot, planting date, and sequence of Stage observations.
-- Requirement 4.1
CREATE TABLE IF NOT EXISTS crop_cycles (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  plot_id       UUID        NOT NULL REFERENCES plots(id) ON DELETE CASCADE,
  user_id       UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  crop          TEXT        NOT NULL,
  variety       TEXT,
  planting_date DATE        NOT NULL,
  is_active     BOOLEAN     NOT NULL DEFAULT TRUE,
  notes         TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS crop_cycles_plot_id_idx
  ON crop_cycles (plot_id);

CREATE INDEX IF NOT EXISTS crop_cycles_user_id_idx
  ON crop_cycles (user_id);

ALTER TABLE crop_cycles ENABLE ROW LEVEL SECURITY;

-- A farmer can read their own crop cycles.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'crop_cycles' AND policyname = 'Crop cycles select own'
  ) THEN
    CREATE POLICY "Crop cycles select own"
      ON crop_cycles FOR SELECT
      USING (auth.uid() = user_id);
  END IF;
END $$;

-- A farmer can insert their own crop cycles.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'crop_cycles' AND policyname = 'Crop cycles insert own'
  ) THEN
    CREATE POLICY "Crop cycles insert own"
      ON crop_cycles FOR INSERT
      WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

-- A farmer can update their own crop cycles.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'crop_cycles' AND policyname = 'Crop cycles update own'
  ) THEN
    CREATE POLICY "Crop cycles update own"
      ON crop_cycles FOR UPDATE
      USING (auth.uid() = user_id);
  END IF;
END $$;

-- A farmer can delete their own crop cycles.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'crop_cycles' AND policyname = 'Crop cycles delete own'
  ) THEN
    CREATE POLICY "Crop cycles delete own"
      ON crop_cycles FOR DELETE
      USING (auth.uid() = user_id);
  END IF;
END $$;


-- ── plot_plant_count_audit table ────────────────────────────────────────────
-- Immutable audit trail for plant count changes on a Plot.
-- Requirement 4.3
CREATE TABLE IF NOT EXISTS plot_plant_count_audit (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  plot_id     UUID        NOT NULL REFERENCES plots(id) ON DELETE CASCADE,
  user_id     UUID        NOT NULL REFERENCES auth.users(id),
  prior_count INTEGER     NOT NULL,
  new_count   INTEGER     NOT NULL,
  changed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS plot_plant_count_audit_plot_id_idx
  ON plot_plant_count_audit (plot_id);

-- RLS: farmer can read their own audit rows. No client INSERT (trigger/service-only).
ALTER TABLE plot_plant_count_audit ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'plot_plant_count_audit' AND policyname = 'Plant count audit select own'
  ) THEN
    CREATE POLICY "Plant count audit select own"
      ON plot_plant_count_audit FOR SELECT
      USING (auth.uid() = user_id);
  END IF;
END $$;


-- ── farm_tasks table ────────────────────────────────────────────────────────
-- Scheduled or suggested farm actions with due date, status, source, and reviewer.
-- Table name is farm_tasks (not "tasks") to avoid SQL keyword conflict.
-- Requirement 6.1, 6.2
CREATE TABLE IF NOT EXISTS farm_tasks (
  id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  farm_id             UUID        REFERENCES farms(id) ON DELETE SET NULL,
  plot_id             UUID        REFERENCES plots(id) ON DELETE SET NULL,
  title               TEXT        NOT NULL,
  due_date            TIMESTAMPTZ,
  description         TEXT,
  source              TEXT        CHECK (source IN ('manual','ai')),
  priority            TEXT        CHECK (priority IN ('low','medium','high')),
  status              TEXT        NOT NULL DEFAULT 'planned'
                      CHECK (status IN ('suggested','planned','due','completed','skipped','cancelled','needs-review')),
  content_record_id   UUID        REFERENCES content_records(id),
  is_ai_generated     BOOLEAN     NOT NULL DEFAULT FALSE,
  risk_level          TEXT        CHECK (risk_level IN ('LOW','MEDIUM','HIGH')),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS farm_tasks_user_id_idx
  ON farm_tasks (user_id);

CREATE INDEX IF NOT EXISTS farm_tasks_status_idx
  ON farm_tasks (user_id, status);

CREATE INDEX IF NOT EXISTS farm_tasks_due_date_idx
  ON farm_tasks (user_id, due_date);

ALTER TABLE farm_tasks ENABLE ROW LEVEL SECURITY;

-- A farmer can read their own tasks.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'farm_tasks' AND policyname = 'Farm tasks select own'
  ) THEN
    CREATE POLICY "Farm tasks select own"
      ON farm_tasks FOR SELECT
      USING (auth.uid() = user_id);
  END IF;
END $$;

-- A farmer can insert their own tasks.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'farm_tasks' AND policyname = 'Farm tasks insert own'
  ) THEN
    CREATE POLICY "Farm tasks insert own"
      ON farm_tasks FOR INSERT
      WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

-- A farmer can update their own tasks.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'farm_tasks' AND policyname = 'Farm tasks update own'
  ) THEN
    CREATE POLICY "Farm tasks update own"
      ON farm_tasks FOR UPDATE
      USING (auth.uid() = user_id);
  END IF;
END $$;

-- A farmer can delete their own tasks.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'farm_tasks' AND policyname = 'Farm tasks delete own'
  ) THEN
    CREATE POLICY "Farm tasks delete own"
      ON farm_tasks FOR DELETE
      USING (auth.uid() = user_id);
  END IF;
END $$;

-- Auto-update updated_at on farm_tasks.
DROP TRIGGER IF EXISTS farm_tasks_updated_at ON farm_tasks;
CREATE TRIGGER farm_tasks_updated_at
  BEFORE UPDATE ON farm_tasks
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ── observations table ───────────────────────────────────────────────────────
-- Structured crop-health records with symptoms, photos, and AI analysis.
-- Requirement 7.1
CREATE TABLE IF NOT EXISTS observations (
  id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  plot_id             UUID        REFERENCES plots(id) ON DELETE SET NULL,
  observed_date       DATE        NOT NULL,
  plant_part          TEXT,
  symptom_description TEXT,
  onset_date          DATE,
  spread_pattern      TEXT,
  severity            TEXT,
  trees_sampled       INTEGER,
  trees_affected      INTEGER,
  weather_notes       TEXT,
  recent_input_notes  TEXT,
  observer_name       TEXT,
  ai_analysis         TEXT,
  ai_analysis_label   TEXT        DEFAULT 'Preliminary observation — not a diagnosis',
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS observations_user_id_idx
  ON observations (user_id);

CREATE INDEX IF NOT EXISTS observations_plot_id_idx
  ON observations (plot_id);

ALTER TABLE observations ENABLE ROW LEVEL SECURITY;

-- A farmer can read their own observations.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'observations' AND policyname = 'Observations select own'
  ) THEN
    CREATE POLICY "Observations select own"
      ON observations FOR SELECT
      USING (auth.uid() = user_id);
  END IF;
END $$;

-- A farmer can insert their own observations.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'observations' AND policyname = 'Observations insert own'
  ) THEN
    CREATE POLICY "Observations insert own"
      ON observations FOR INSERT
      WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

-- A farmer can update their own observations.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'observations' AND policyname = 'Observations update own'
  ) THEN
    CREATE POLICY "Observations update own"
      ON observations FOR UPDATE
      USING (auth.uid() = user_id);
  END IF;
END $$;

-- A farmer can delete their own observations.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'observations' AND policyname = 'Observations delete own'
  ) THEN
    CREATE POLICY "Observations delete own"
      ON observations FOR DELETE
      USING (auth.uid() = user_id);
  END IF;
END $$;


-- ── observation_photos table ────────────────────────────────────────────────
-- Stores photo references for observations. Original and AI versions are
-- stored as separate rows (is_ai_version flag).
-- Requirement 7.4
CREATE TABLE IF NOT EXISTS observation_photos (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  observation_id  UUID        NOT NULL REFERENCES observations(id) ON DELETE CASCADE,
  user_id         UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  storage_key     TEXT        NOT NULL,
  is_ai_version   BOOLEAN     NOT NULL DEFAULT FALSE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS observation_photos_observation_id_idx
  ON observation_photos (observation_id);

CREATE INDEX IF NOT EXISTS observation_photos_user_id_idx
  ON observation_photos (user_id);

ALTER TABLE observation_photos ENABLE ROW LEVEL SECURITY;

-- A farmer can read their own observation photos.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'observation_photos' AND policyname = 'Observation photos select own'
  ) THEN
    CREATE POLICY "Observation photos select own"
      ON observation_photos FOR SELECT
      USING (auth.uid() = user_id);
  END IF;
END $$;

-- A farmer can insert their own observation photos.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'observation_photos' AND policyname = 'Observation photos insert own'
  ) THEN
    CREATE POLICY "Observation photos insert own"
      ON observation_photos FOR INSERT
      WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

-- A farmer can delete their own observation photos.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'observation_photos' AND policyname = 'Observation photos delete own'
  ) THEN
    CREATE POLICY "Observation photos delete own"
      ON observation_photos FOR DELETE
      USING (auth.uid() = user_id);
  END IF;
END $$;


-- ── inventory_items table ───────────────────────────────────────────────────
-- Farmer-entered catalogue of agricultural inputs on hand.
-- Requirement 8.1
CREATE TABLE IF NOT EXISTS inventory_items (
  id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  farm_id           UUID        REFERENCES farms(id) ON DELETE SET NULL,
  product_name      TEXT        NOT NULL,
  active_ingredient TEXT,
  formulation       TEXT,
  manufacturer      TEXT,
  batch_number      TEXT,
  expiry_date       DATE,
  quantity_on_hand  NUMERIC     NOT NULL DEFAULT 0,
  unit              TEXT        NOT NULL,
  purchase_price    NUMERIC,
  label_photo_key   TEXT,
  safety_doc_ref    TEXT,
  supplier_name     TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS inventory_items_user_id_idx
  ON inventory_items (user_id);

ALTER TABLE inventory_items ENABLE ROW LEVEL SECURITY;

-- A farmer can read their own inventory items.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'inventory_items' AND policyname = 'Inventory items select own'
  ) THEN
    CREATE POLICY "Inventory items select own"
      ON inventory_items FOR SELECT
      USING (auth.uid() = user_id);
  END IF;
END $$;

-- A farmer can insert their own inventory items.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'inventory_items' AND policyname = 'Inventory items insert own'
  ) THEN
    CREATE POLICY "Inventory items insert own"
      ON inventory_items FOR INSERT
      WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

-- A farmer can update their own inventory items.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'inventory_items' AND policyname = 'Inventory items update own'
  ) THEN
    CREATE POLICY "Inventory items update own"
      ON inventory_items FOR UPDATE
      USING (auth.uid() = user_id);
  END IF;
END $$;

-- A farmer can delete their own inventory items.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'inventory_items' AND policyname = 'Inventory items delete own'
  ) THEN
    CREATE POLICY "Inventory items delete own"
      ON inventory_items FOR DELETE
      USING (auth.uid() = user_id);
  END IF;
END $$;

-- Auto-update updated_at on inventory_items.
DROP TRIGGER IF EXISTS inventory_items_updated_at ON inventory_items;
CREATE TRIGGER inventory_items_updated_at
  BEFORE UPDATE ON inventory_items
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ── expenses table ──────────────────────────────────────────────────────────
-- Farmer-entered expense records by category.
-- Requirement 10.1
CREATE TABLE IF NOT EXISTS expenses (
  id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  farm_id             UUID        REFERENCES farms(id) ON DELETE SET NULL,
  plot_id             UUID        REFERENCES plots(id) ON DELETE SET NULL,
  category            TEXT        NOT NULL
                      CHECK (category IN ('input','labour','irrigation_electricity','machinery',
                                          'packaging','transport','rent_lease','services','other')),
  amount              NUMERIC     NOT NULL CHECK (amount >= 0),
  expense_date        DATE        NOT NULL,
  description         TEXT,
  receipt_key         TEXT,
  linked_activity_id  UUID        REFERENCES farm_activities(id),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS expenses_user_id_idx
  ON expenses (user_id);

CREATE INDEX IF NOT EXISTS expenses_category_idx
  ON expenses (user_id, category);

CREATE INDEX IF NOT EXISTS expenses_linked_activity_idx
  ON expenses (linked_activity_id);

ALTER TABLE expenses ENABLE ROW LEVEL SECURITY;

-- A farmer can read their own expenses.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'expenses' AND policyname = 'Expenses select own'
  ) THEN
    CREATE POLICY "Expenses select own"
      ON expenses FOR SELECT
      USING (auth.uid() = user_id);
  END IF;
END $$;

-- A farmer can insert their own expenses.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'expenses' AND policyname = 'Expenses insert own'
  ) THEN
    CREATE POLICY "Expenses insert own"
      ON expenses FOR INSERT
      WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

-- A farmer can update their own expenses.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'expenses' AND policyname = 'Expenses update own'
  ) THEN
    CREATE POLICY "Expenses update own"
      ON expenses FOR UPDATE
      USING (auth.uid() = user_id);
  END IF;
END $$;

-- A farmer can delete their own expenses.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'expenses' AND policyname = 'Expenses delete own'
  ) THEN
    CREATE POLICY "Expenses delete own"
      ON expenses FOR DELETE
      USING (auth.uid() = user_id);
  END IF;
END $$;


-- ── activity_audit_log table ─────────────────────────────────────────────────
-- Immutable record of all activity edits. Written before any field update.
-- Requirement 5.4
CREATE TABLE IF NOT EXISTS activity_audit_log (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  activity_id   UUID        NOT NULL REFERENCES farm_activities(id) ON DELETE CASCADE,
  user_id       UUID        NOT NULL REFERENCES auth.users(id),
  field_name    TEXT        NOT NULL,
  old_value     TEXT,
  new_value     TEXT,
  changed_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS activity_audit_log_activity_id_idx
  ON activity_audit_log (activity_id);

CREATE INDEX IF NOT EXISTS activity_audit_log_user_id_idx
  ON activity_audit_log (user_id);

-- RLS: farmer can read their own audit rows. No client INSERT (service/trigger-only).
ALTER TABLE activity_audit_log ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'activity_audit_log' AND policyname = 'Activity audit log select own'
  ) THEN
    CREATE POLICY "Activity audit log select own"
      ON activity_audit_log FOR SELECT
      USING (auth.uid() = user_id);
  END IF;
END $$;


-- ── Extend farm_activities with new columns (additive) ───────────────────────
-- All new columns are optional to preserve backward compatibility with legacy rows.
-- Requirement 5.1, 5.4, 5.6, 5.7
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='farm_activities' AND column_name='plot_id'
  ) THEN
    ALTER TABLE farm_activities ADD COLUMN plot_id UUID REFERENCES plots(id) ON DELETE SET NULL;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='farm_activities' AND column_name='crop_cycle_id'
  ) THEN
    ALTER TABLE farm_activities ADD COLUMN crop_cycle_id UUID REFERENCES crop_cycles(id) ON DELETE SET NULL;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='farm_activities' AND column_name='logged_date_tz'
  ) THEN
    ALTER TABLE farm_activities ADD COLUMN logged_date_tz TIMESTAMPTZ;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='farm_activities' AND column_name='method'
  ) THEN
    ALTER TABLE farm_activities ADD COLUMN method TEXT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='farm_activities' AND column_name='actor'
  ) THEN
    ALTER TABLE farm_activities ADD COLUMN actor TEXT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='farm_activities' AND column_name='photo_storage_key'
  ) THEN
    ALTER TABLE farm_activities ADD COLUMN photo_storage_key TEXT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='farm_activities' AND column_name='status'
  ) THEN
    ALTER TABLE farm_activities ADD COLUMN status TEXT NOT NULL DEFAULT 'recorded'
      CHECK (status IN ('planned','recorded'));
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='farm_activities' AND column_name='original_cost'
  ) THEN
    ALTER TABLE farm_activities ADD COLUMN original_cost NUMERIC;
  END IF;
END $$;

-- Index for filtering activities by plot.
CREATE INDEX IF NOT EXISTS farm_activities_plot_id_idx
  ON farm_activities (plot_id);


-- ── Extend harvests with new columns (additive) ─────────────────────────────
-- All new columns are optional to preserve backward compatibility with legacy rows.
-- Requirement 9.1, 9.2
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='harvests' AND column_name='plot_id'
  ) THEN
    ALTER TABLE harvests ADD COLUMN plot_id UUID REFERENCES plots(id) ON DELETE SET NULL;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='harvests' AND column_name='total_weight_kg'
  ) THEN
    ALTER TABLE harvests ADD COLUMN total_weight_kg NUMERIC;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='harvests' AND column_name='weight_unit'
  ) THEN
    ALTER TABLE harvests ADD COLUMN weight_unit TEXT DEFAULT 'kg';
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='harvests' AND column_name='grade'
  ) THEN
    ALTER TABLE harvests ADD COLUMN grade TEXT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='harvests' AND column_name='damaged_qty'
  ) THEN
    ALTER TABLE harvests ADD COLUMN damaged_qty NUMERIC DEFAULT 0;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='harvests' AND column_name='packaging'
  ) THEN
    ALTER TABLE harvests ADD COLUMN packaging TEXT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='harvests' AND column_name='buyer_name'
  ) THEN
    ALTER TABLE harvests ADD COLUMN buyer_name TEXT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='harvests' AND column_name='market_type'
  ) THEN
    ALTER TABLE harvests ADD COLUMN market_type TEXT
      CHECK (market_type IN ('farm_gate','mandi','retail'));
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='harvests' AND column_name='deductions'
  ) THEN
    ALTER TABLE harvests ADD COLUMN deductions NUMERIC DEFAULT 0;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='harvests' AND column_name='transport_cost'
  ) THEN
    ALTER TABLE harvests ADD COLUMN transport_cost NUMERIC DEFAULT 0;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='harvests' AND column_name='payment_status'
  ) THEN
    ALTER TABLE harvests ADD COLUMN payment_status TEXT DEFAULT 'unpaid'
      CHECK (payment_status IN ('unpaid','partial','paid'));
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='harvests' AND column_name='is_scenario'
  ) THEN
    ALTER TABLE harvests ADD COLUMN is_scenario BOOLEAN NOT NULL DEFAULT FALSE;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='harvests' AND column_name='gross_sales'
  ) THEN
    ALTER TABLE harvests ADD COLUMN gross_sales NUMERIC;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='harvests' AND column_name='net_realisation'
  ) THEN
    ALTER TABLE harvests ADD COLUMN net_realisation NUMERIC;
  END IF;
END $$;

-- Index for filtering harvests by plot.
CREATE INDEX IF NOT EXISTS harvests_plot_id_idx
  ON harvests (plot_id);

-- ═══════════════════════════════════════════════════════════════════════════
-- Smart Farmer — contact_submissions table (Task 9)
-- Public contact / join-pilot form submissions with explicit consent flag.
-- Safe to re-run; all DDL uses IF NOT EXISTS / DO $$ guards.
-- Requirements: 2.3
-- ═══════════════════════════════════════════════════════════════════════════

-- ── contact_submissions table ───────────────────────────────────────────────
-- Stores visitor contact / join-pilot form submissions.
-- Inserts are performed by the backend service-role client (bypasses RLS);
-- RLS still denies public reads to protect submitted personal data.
-- Requirement 2.3
CREATE TABLE IF NOT EXISTS contact_submissions (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  name          TEXT        NOT NULL,
  contact_value TEXT        NOT NULL,
  contact_type  TEXT        NOT NULL CHECK (contact_type IN ('email', 'phone')),
  consent       BOOLEAN     NOT NULL DEFAULT TRUE,
  submitted_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS contact_submissions_submitted_at_idx
  ON contact_submissions (submitted_at DESC);

ALTER TABLE contact_submissions ENABLE ROW LEVEL SECURITY;

-- Public can insert submissions (the contact form is anonymous / pre-auth).
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'contact_submissions' AND policyname = 'Contact submissions public insert'
  ) THEN
    CREATE POLICY "Contact submissions public insert"
      ON contact_submissions FOR INSERT
      WITH CHECK (TRUE);
  END IF;
END $$;

-- No public read: explicitly deny SELECT to all roles. Only the service-role
-- backend (which bypasses RLS) can read submissions.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'contact_submissions' AND policyname = 'Contact submissions no public read'
  ) THEN
    CREATE POLICY "Contact submissions no public read"
      ON contact_submissions FOR SELECT
      USING (FALSE);
  END IF;
END $$;


-- ══════════════════════════════════════════════════════════════════════════
-- market_prices: real mandi price ingestion (Agmarknet / data.gov.in)
-- Adds the columns the daily ingestion fills and a unique key so re-runs
-- upsert instead of duplicating. Safe to re-run (IF NOT EXISTS everywhere).
-- Prices are stored as reported: Rs per quintal. `price` keeps the modal price
-- for the older reader in routers/financial.py.
-- ══════════════════════════════════════════════════════════════════════════
ALTER TABLE market_prices ADD COLUMN IF NOT EXISTS state        TEXT;
ALTER TABLE market_prices ADD COLUMN IF NOT EXISTS district     TEXT;
ALTER TABLE market_prices ADD COLUMN IF NOT EXISTS variety      TEXT;
ALTER TABLE market_prices ADD COLUMN IF NOT EXISTS min_price    NUMERIC CHECK (min_price >= 0);
ALTER TABLE market_prices ADD COLUMN IF NOT EXISTS max_price    NUMERIC CHECK (max_price >= 0);
ALTER TABLE market_prices ADD COLUMN IF NOT EXISTS modal_price  NUMERIC CHECK (modal_price >= 0);
ALTER TABLE market_prices ADD COLUMN IF NOT EXISTS arrival_date DATE;
ALTER TABLE market_prices ADD COLUMN IF NOT EXISTS fetched_at   TIMESTAMPTZ;

-- One row per mandi, variety, grade and trade date. The ingestion writes empty
-- strings (not NULL) for a missing district, variety or grade so this key works.
CREATE UNIQUE INDEX IF NOT EXISTS market_prices_daily_key
  ON market_prices (source_name, state, district, market_name, commodity,
                    variety, grade, arrival_date);

CREATE INDEX IF NOT EXISTS market_prices_state_date_idx
  ON market_prices (commodity, state, arrival_date DESC);

-- ============================================================================
-- Sell smart ("Where and when to sell") - additive, idempotent migration.
-- Run once in the Supabase SQL editor; safe to run again. NOT applied by code.
-- Tables: sell_settings, price_alerts, notifications, market_price_quality.
-- Every table has RLS enabled. Policies use pg_policies guards.
-- ============================================================================

-- -- sell_settings: one row per farmer, own-row access ------------------------
CREATE TABLE IF NOT EXISTS sell_settings (
  user_id                         UUID        PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  transport_mode                  TEXT        NULL
    CHECK (transport_mode IN ('per_quintal_per_km', 'flat_per_quintal')),
  transport_rs_per_quintal_per_km NUMERIC     NULL CHECK (transport_rs_per_quintal_per_km >= 0),
  transport_rs_per_quintal_flat   NUMERIC     NULL CHECK (transport_rs_per_quintal_flat >= 0),
  handling_rs_per_quintal         NUMERIC     NULL CHECK (handling_rs_per_quintal >= 0),
  commission_pct                  NUMERIC     NULL CHECK (commission_pct >= 0 AND commission_pct <= 100),
  radius_km                       NUMERIC     NULL CHECK (radius_km > 0 AND radius_km <= 1500),
  road_km_overrides               JSONB       NOT NULL DEFAULT '{}'::jsonb,
  updated_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE sell_settings ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'sell_settings' AND policyname = 'Sell settings select own'
  ) THEN
    CREATE POLICY "Sell settings select own"
      ON sell_settings FOR SELECT
      USING (auth.uid() = user_id);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'sell_settings' AND policyname = 'Sell settings insert own'
  ) THEN
    CREATE POLICY "Sell settings insert own"
      ON sell_settings FOR INSERT
      WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'sell_settings' AND policyname = 'Sell settings update own'
  ) THEN
    CREATE POLICY "Sell settings update own"
      ON sell_settings FOR UPDATE
      USING (auth.uid() = user_id)
      WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

-- -- price_alerts: own-row access, soft removal through deleted_at ------------
CREATE TABLE IF NOT EXISTS price_alerts (
  id                 UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id            UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  state              TEXT        NOT NULL,
  district           TEXT        NULL,
  market_name        TEXT        NULL,
  target_rs_per_kg   NUMERIC     NOT NULL CHECK (target_rs_per_kg > 0),
  direction          TEXT        NOT NULL DEFAULT 'at_or_above'
    CHECK (direction IN ('at_or_above', 'at_or_below')),
  is_active          BOOLEAN     NOT NULL DEFAULT TRUE,
  deleted_at         TIMESTAMPTZ NULL,
  last_state         TEXT        NULL,
  last_trigger_date  DATE        NULL,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS price_alerts_user_idx
  ON price_alerts (user_id);

ALTER TABLE price_alerts ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'price_alerts' AND policyname = 'Price alerts select own'
  ) THEN
    CREATE POLICY "Price alerts select own"
      ON price_alerts FOR SELECT
      USING (auth.uid() = user_id);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'price_alerts' AND policyname = 'Price alerts insert own'
  ) THEN
    CREATE POLICY "Price alerts insert own"
      ON price_alerts FOR INSERT
      WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'price_alerts' AND policyname = 'Price alerts update own'
  ) THEN
    CREATE POLICY "Price alerts update own"
      ON price_alerts FOR UPDATE
      USING (auth.uid() = user_id)
      WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

-- -- notifications: owner reads and marks read; rows are inserted by the ------
-- -- backend (service role bypasses RLS), so there is no INSERT policy. -------
CREATE TABLE IF NOT EXISTS notifications (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  kind        TEXT        NOT NULL,
  alert_id    UUID        NULL REFERENCES price_alerts(id) ON DELETE SET NULL,
  payload     JSONB       NOT NULL DEFAULT '{}'::jsonb,
  read_at     TIMESTAMPTZ NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS notifications_user_idx
  ON notifications (user_id);
CREATE INDEX IF NOT EXISTS notifications_user_read_idx
  ON notifications (user_id, read_at);

ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'notifications' AND policyname = 'Notifications select own'
  ) THEN
    CREATE POLICY "Notifications select own"
      ON notifications FOR SELECT
      USING (auth.uid() = user_id);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'notifications' AND policyname = 'Notifications update own'
  ) THEN
    CREATE POLICY "Notifications update own"
      ON notifications FOR UPDATE
      USING (auth.uid() = user_id)
      WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

-- RLS cannot limit columns, so limit them with a column privilege: a signed-in
-- client may change read_at only. Repeating these statements is harmless.
REVOKE UPDATE ON notifications FROM authenticated;
GRANT UPDATE (read_at) ON notifications TO authenticated;

-- -- market_price_quality: side table keyed by market_prices.id ----------------
-- Public data quality flags, no user data. last_modal detects late corrections.
CREATE TABLE IF NOT EXISTS market_price_quality (
  price_id        UUID        PRIMARY KEY REFERENCES market_prices(id) ON DELETE CASCADE,
  flags           TEXT[]      NOT NULL DEFAULT '{}',
  severity        TEXT        NOT NULL DEFAULT 'ok'
    CHECK (severity IN ('ok', 'warn', 'reject')),
  last_modal      NUMERIC     NULL,
  revision_count  INTEGER     NOT NULL DEFAULT 0,
  checked_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE market_price_quality ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'market_price_quality' AND policyname = 'Market price quality public read'
  ) THEN
    CREATE POLICY "Market price quality public read"
      ON market_price_quality FOR SELECT
      USING (TRUE);
  END IF;
END $$;
