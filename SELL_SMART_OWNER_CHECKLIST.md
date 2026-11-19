# Sell smart: owner checklist

Do these once before telling farmers about "Where and when to sell".

1. **Run the migration.** In the Supabase SQL editor, run `backend/migrations/2026-11-sell-smart.sql`. It is safe to run twice (`IF NOT EXISTS`, policy guards). It creates `sell_settings`, `price_alerts`, `notifications` and `market_price_quality`, all with row-level security. (The same SQL is also appended to `backend/schema.sql`.)
2. **Render environment variables.** Nothing new is required. `DATA_GOV_IN_API_KEY` must already be set, because Sell smart reads the prices that the ingestion job saves. Do **not** set `SELL_SMART_ALLOW_DEMO` on Render (it is for local demo only, and the demo server also refuses to start when `RENDER` is set).
3. **Check the Render logs** after the next 07:45 or 19:45 IST. The `sell_smart_post_ingestion` job should log a summary (quality rows written, alerts checked, notifications created). It runs 15 minutes after the 07:30 and 19:30 price ingestion.
4. **Set your own farm location and costs in the app.** Without a farm location the distance starts from your district centre. Without costs the list is sorted by mandi price and asks you to set your own cost. Nothing is filled in for you.
5. **Review `privacy.html`.** The wording should say that the farm location is used to measure distance to mandis and is not shown to other farmers or sent to the browser as coordinates.
6. **Demo data warning.** Anything seen with `?demo=1` is synthetic. Never show it to farmers as real prices.

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

Day counts come from the threshold table in `.agents/tasks/sell-smart/plan.md` and are defined, each with its basis, in `backend/services/sell_smart/config.py`.
