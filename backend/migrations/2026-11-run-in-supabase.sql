-- Smart Farmer: run this whole file ONCE in the Supabase SQL editor (safe to re-run).
-- Part 1: market_prices columns for real mandi prices. Part 2: Sell smart tables.

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
