# Mandi prices from a Supabase Edge Function (India region)

data.gov.in refuses Render's IP addresses, so Render cannot fetch mandi prices. The Edge Function `mandi-ingest` does the same job from Supabase's Mumbai region (`ap-south-1`) and writes straight to `market_prices`. It uses the same row shape and upsert key as `backend/services/mandi_prices.py`, so running it twice, or alongside the PC script, never creates duplicates.

**Not verified:** whether data.gov.in answers from Supabase's Mumbai region. It was not tested from the developer PC. Step 5 below checks it. If the probe says `reachable: false`, data.gov.in blocks that region too and the PC scheduled task stays the price source.

## Steps

1. **Install nothing.** Use the Supabase CLI through `npx`.
2. **Log in and link** (the project ref is the part of `SUPABASE_URL` in `js/config.js` before `.supabase.co`):

   ```
   npx supabase login
   npx supabase link --project-ref ifgppywdggnxdudlkvtr
   ```

3. **Set the two secrets.** Make `MANDI_INGEST_TOKEN` a new long random string and keep it; the cron job and your curl commands need it. (You can also set both on the dashboard: Edge Functions > Secrets.)

   ```
   npx supabase secrets set DATA_GOV_IN_API_KEY=<your data.gov.in key> MANDI_INGEST_TOKEN=<new random string> --project-ref ifgppywdggnxdudlkvtr
   ```

   The function reads `SUPABASE_URL` and the service key from the environment Supabase injects. You do not set them.

4. **Deploy.** Use the CLI; pasting into the dashboard editor does not handle the multiple files.

   ```
   npx supabase functions deploy mandi-ingest --no-verify-jwt --project-ref ifgppywdggnxdudlkvtr
   ```

   `--no-verify-jwt` is needed because the cron call authenticates with `x-ingest-token`, not a user JWT (`supabase/config.toml` also sets this). If the CLI asks for a `project_id` in `config.toml`, `link` normally fills it in; otherwise add `project_id = "ifgppywdggnxdudlkvtr"` at the top.

5. **Probe from Mumbai.** This sends one request to data.gov.in and writes nothing:

   ```
   curl -X POST "https://ifgppywdggnxdudlkvtr.supabase.co/functions/v1/mandi-ingest?mode=probe&forceFunctionRegion=ap-south-1" -H "x-region: ap-south-1" -H "x-ingest-token: <token>"
   ```

   Read the JSON: `region` must be `ap-south-1`; `reachable: true` with `http_status: 200` means data.gov.in answered. `reachable: false` (with `error`) means it did not answer from that region. `http_status: 403` means it answered but the key is wrong or not allowed. The key is never shown.

6. **Run one real ingest by hand:**

   ```
   curl -X POST "https://ifgppywdggnxdudlkvtr.supabase.co/functions/v1/mandi-ingest?forceFunctionRegion=ap-south-1" -H "x-region: ap-south-1" -H "x-ingest-token: <token>"
   ```

   The answer has the same shape as the PC script: `status`, `fetched`, `parsed`, `skipped`, `upserted`. `status: ok` with `upserted` above 0 is success.

7. **Schedule it (only if the probe was reachable).** In the SQL editor, create two Vault secrets by hand (commands are in the comments at the top of `backend/migrations/2026-11-mandi-ingest-cron.sql`): `project_url` (`https://ifgppywdggnxdudlkvtr.supabase.co`) and `mandi_ingest_token` (the same token as above). Then run the whole migration file once. It schedules 07:30 and 19:30 IST (02:00 and 14:00 UTC, because pg_cron uses UTC). Running it again only updates the same two jobs. Nothing in the repository runs this file for you.

## Reading the logs

Dashboard > Edge Functions > mandi-ingest > Logs. Look for lines starting `mandi-ingest`:

| Line | Meaning |
|---|---|
| `status=ok ...` | Prices fetched and saved |
| `status=no_api_key` | `DATA_GOV_IN_API_KEY` secret missing |
| `status=fetch_failed error=...` | data.gov.in failed or refused; the reason follows |
| `status=empty` | The feed had no guava rows |
| `status=unusable` | Rows arrived but the field names changed |
| `status=store_failed error=HTTP <code>` | Saving to `market_prices` failed |
| `MANDI_INGEST_TOKEN not set` | The token secret is missing (the function answers 500) |

To see cron history: `select * from cron.job_run_details order by start_time desc limit 10;` and `select status_code, content from net._http_response order by created desc limit 5;`.

## Other pieces

- Leave `MANDI_INGEST_ON_RENDER` unset on Render. It only exists to switch the old in-process cron back on.
- The PC script `backend/scripts/ingest_from_pc.py` and its Windows scheduled task stay as the fallback. Both paths write the same rows with the same upsert key, so running both is harmless.
- Tests: `npx -y deno test --allow-read supabase/functions/mandi-ingest/` and, from `backend/`, `python -m pytest tests/test_mandi_edge_parity.py`. The parity test keeps the TypeScript and Python parsers identical.
