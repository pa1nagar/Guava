# Owner steps

Do these in order. Each step says where to run it. Nothing here is done for you by the code.

1. **Push `main` and wait for both deploys.** (The workflow orchestrator pushes; you only wait.)
   - Netlify: Deploys page for `smart-farmer.in` must show "Published" for the new commit. The three most recent Netlify deploys failed at "Install dependencies"; if that happens again, copy the deploy log to the developer.
   - Render: the service `guava-8wc7` must show "Live". The first request after a sleep can take about a minute.

2. **Harden the sell-smart tables.** Supabase dashboard, SQL editor, paste and run the whole file `backend/migrations/2026-11-sell-smart-harden.sql`. It removes browser write access to `price_alerts` and `sell_settings` and adds length checks. It is safe to run twice.

3. **Deploy the Edge Function and set its secrets.** Details and exact commands: `docs/MANDI_EDGE_FUNCTION.md`.
   ```powershell
   npx supabase login
   npx supabase link --project-ref ifgppywdggnxdudlkvtr
   npx supabase secrets set DATA_GOV_IN_API_KEY=<your key> MANDI_INGEST_TOKEN=<a new random string> --project-ref ifgppywdggnxdudlkvtr
   npx supabase functions deploy mandi-ingest --no-verify-jwt --project-ref ifgppywdggnxdudlkvtr
   ```
   Then call the probe from Mumbai:
   ```powershell
   curl -X POST "https://ifgppywdggnxdudlkvtr.supabase.co/functions/v1/mandi-ingest?mode=probe&forceFunctionRegion=ap-south-1" -H "x-region: ap-south-1" -H "x-ingest-token: <token>"
   ```
   Check that the answer says `"reachable": true` and `"region": "ap-south-1"`. If it says `false`, data.gov.in also blocks Mumbai: skip steps 4 and keep the PC task as the price source.

4. **Schedule it (only if step 3 said reachable).** In the SQL editor create the Vault secrets `project_url` (`https://ifgppywdggnxdudlkvtr.supabase.co`) and `mandi_ingest_token` (same token as step 3); the commands are in the comments at the top of `backend/migrations/2026-11-mandi-ingest-cron.sql`. Then run that whole file once. It schedules 07:30 and 19:30 IST.

5. **Leave `MANDI_INGEST_ON_RENDER` unset on Render.** Set it to `1` only if data.gov.in ever stops refusing Render's servers. Do not set `SELL_SMART_ALLOW_DEMO` on Render.

6. **Keep the Windows task `SmartFarmer-MandiPrices`** until the Edge Function has saved rows on two days in a row. Check in the SQL editor: `select max(arrival_date) from market_prices where commodity = 'guava';` on two consecutive days (the date must move forward without the PC running). After that you may disable the task.

7. **Check on a real Android phone.** Open `https://guavaa.netlify.app`, then check one page per feature: Home (today's price, Hindi toggle, contact form), Sign in, Plan, Farm, Tasks, Sell smart (ranked cards, add a price alert), Observations (take a photo), Inventory, Report, Privacy. Turn on airplane mode and reload Home: it should show the last price with "Offline - showing saved copy".

More detail for the sell-smart items: `SELL_SMART_OWNER_CHECKLIST.md`.