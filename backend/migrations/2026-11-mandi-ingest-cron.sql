-- 2026-11-mandi-ingest-cron.sql
-- Schedules the mandi-ingest Edge Function twice a day with pg_cron + pg_net.
-- NOT applied by any code. The owner runs it once in the Supabase SQL editor,
-- AFTER deploying the function and creating the two Vault secrets below.
-- See docs/MANDI_EDGE_FUNCTION.md. Additive and safe to re-run: extensions use
-- IF NOT EXISTS and cron.schedule() with an existing job name updates that job.
--
-- Step 1 (by hand, once; replace the placeholders, never commit real values):
--   select vault.create_secret('https://<project-ref>.supabase.co', 'project_url');
--   select vault.create_secret('<the MANDI_INGEST_TOKEN value>', 'mandi_ingest_token');
--
-- Step 2: run this file.
--
-- pg_cron uses UTC. 02:00 UTC = 07:30 IST and 14:00 UTC = 19:30 IST, the same
-- times the PC task and the Render cron use. Upserts make repeat runs harmless.

create extension if not exists pg_cron;
create extension if not exists pg_net;

select cron.schedule(
  'mandi-ingest-0730-ist',
  '0 2 * * *',
  $$
  select net.http_post(
    url := (select decrypted_secret from vault.decrypted_secrets where name = 'project_url')
           || '/functions/v1/mandi-ingest?forceFunctionRegion=ap-south-1',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'x-region', 'ap-south-1',
      'x-ingest-token', (select decrypted_secret from vault.decrypted_secrets where name = 'mandi_ingest_token')
    ),
    body := '{}'::jsonb,
    timeout_milliseconds := 120000
  );
  $$
);

select cron.schedule(
  'mandi-ingest-1930-ist',
  '0 14 * * *',
  $$
  select net.http_post(
    url := (select decrypted_secret from vault.decrypted_secrets where name = 'project_url')
           || '/functions/v1/mandi-ingest?forceFunctionRegion=ap-south-1',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'x-region', 'ap-south-1',
      'x-ingest-token', (select decrypted_secret from vault.decrypted_secrets where name = 'mandi_ingest_token')
    ),
    body := '{}'::jsonb,
    timeout_milliseconds := 120000
  );
  $$
);

-- Optional probe (reachability only, writes nothing). Run by hand, then read the
-- answer from net._http_response a few seconds later:
--   select net.http_post(
--     url := (select decrypted_secret from vault.decrypted_secrets where name = 'project_url')
--            || '/functions/v1/mandi-ingest?mode=probe&forceFunctionRegion=ap-south-1',
--     headers := jsonb_build_object(
--       'x-region', 'ap-south-1',
--       'x-ingest-token', (select decrypted_secret from vault.decrypted_secrets where name = 'mandi_ingest_token')
--     ),
--     body := '{}'::jsonb
--   );
--   select status_code, content from net._http_response order by created desc limit 1;
