# Sell smart: owner checklist

Do these once before telling farmers about "Where and when to sell".

1. **Run the migrations.** `backend/migrations/2026-11-run-in-supabase.sql` is the combined file (mandi price columns plus the Sell smart tables) and you have already run it. Next, in the Supabase SQL editor, run `backend/migrations/2026-11-sell-smart-harden.sql` (removes the client write policies on `price_alerts` and `sell_settings`, adds length checks) and `backend/migrations/2026-11-mandi-ingest-cron.sql`. All three are safe to run twice. The Sell smart tables all have row-level security.
2. **Render environment variables.** Render's own 07:30 and 19:30 IST price ingestion is now OFF by default (`MANDI_INGEST_ON_RENDER`), because data.gov.in refuses Render's servers. Prices come from the Supabase Edge Function or the PC script, and Sell smart reads what they save. Do **not** set `SELL_SMART_ALLOW_DEMO` on Render (it is for local demo only, and the demo server also refuses to start when `RENDER` is set).
3. **Check the Render logs** after the next 07:45 or 19:45 IST. The `sell_smart_post_ingestion` job still runs on Render at those times, even though Render no longer fetches prices. It should log a summary (quality rows written, alerts checked, notifications created). It works on the prices the Edge Function or PC script saved earlier.
4. **Set your own farm location and costs in the app.** Without a farm location the distance starts from your district centre. Without costs the list is sorted by mandi price and asks you to set your own cost. Nothing is filled in for you.
5. **Review `privacy.html`.** The wording should say that the farm location is used to measure distance to mandis and is not shown to other farmers or sent to the browser as coordinates.
6. **Demo data warning.** Anything seen with `?demo=1` is synthetic. After the frontend change in this release, `?demo=1` only works on localhost. Never show it to farmers as real prices.

## What needs more saved history

The feed keeps no history, so these views fill in only as the app saves prices (one price per mandi per trade date).

| Output | Needs | Until then the app says |
|---|---|---|
| Any trend text | 7 distinct saved days (`MIN_TREND_DAYS`) | how many more days are needed |
| 7-day change | at least 3 saved days in each of two 7-day windows, about 10 days of history | about N more saved days |
| 14-day change | at least 3 saved days in each of two 14-day windows, about 17 days | about N more saved days |
| 30-day change | at least 3 saved days in each of two 30-day windows, about 33 days | about N more saved days |
| How much prices swing | 7 saved days within the last 30 days | about N more saved days |
| Month-by-month view | a saved span of 730 days (2 years), and for each month shown at least 3 saved days in each of 2 different years | days saved so far and the date it can be shown (first saved date + 730 days) |
| "Based on N mandis" confidence High | fresh prices, at least 3 mandis, at least 14 saved days (2 x 7) and no flagged share | Medium or Low with the reason |
| Fairness check | prices from at least 3 mandis within your radius, within 7 days of your sale date | "too few mandis had a price near your sale date" |

Day counts are defined, each with its basis, in `backend/services/sell_smart/config.py`.
