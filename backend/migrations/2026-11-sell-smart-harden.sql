-- ============================================================================
-- Sell smart hardening - idempotent, NOT applied by code. Run once in the
-- Supabase SQL editor; safe to run again.
-- For databases that already ran an older 2026-11-sell-smart.sql or
-- 2026-11-run-in-supabase.sql, which created client INSERT/UPDATE policies on
-- price_alerts and sell_settings. The backend writes both tables with the
-- service role (bypasses RLS), so signed-in clients only need SELECT.
-- ============================================================================
-- -- remove the four client write policies -------------------------------------
DROP POLICY IF EXISTS "Price alerts insert own" ON price_alerts;
DROP POLICY IF EXISTS "Price alerts update own" ON price_alerts;
DROP POLICY IF EXISTS "Sell settings insert own" ON sell_settings;
DROP POLICY IF EXISTS "Sell settings update own" ON sell_settings;
-- The SELECT policies stay. Clients can read their own rows, nothing else.
REVOKE INSERT, UPDATE, DELETE ON price_alerts, sell_settings FROM anon, authenticated;
-- The cap of 20 active alerts per farmer (MAX_ALERTS_PER_FARMER) cannot be a
-- CHECK constraint. With client writes revoked, the API is the only write path
-- and it enforces that cap.
-- -- length and shape constraints ----------------------------------------------
-- 120 = cfg.MAX_NAME_LENGTH in backend/services/sell_smart/config.py.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'price_alerts_state_len') THEN
    ALTER TABLE price_alerts
      ADD CONSTRAINT price_alerts_state_len CHECK (char_length(state) <= 120);
  END IF;
END $$;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'price_alerts_district_len') THEN
    ALTER TABLE price_alerts
      ADD CONSTRAINT price_alerts_district_len CHECK (char_length(district) <= 120);
  END IF;
END $$;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'price_alerts_market_name_len') THEN
    ALTER TABLE price_alerts
      ADD CONSTRAINT price_alerts_market_name_len CHECK (char_length(market_name) <= 120);
  END IF;
END $$;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'sell_settings_road_km_is_object') THEN
    ALTER TABLE sell_settings
      ADD CONSTRAINT sell_settings_road_km_is_object CHECK (jsonb_typeof(road_km_overrides) = 'object');
  END IF;
END $$;