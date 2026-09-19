# Guavaa — Farmer Crop Management Platform

A practical farm-management and agricultural advisory application for guava farmers.
Farmers can sign in with Google, create a farm profile, receive a personalized crop-care
plan, log activities, track spending, and see a financial report at harvest.

**Live site:** https://guavaa.netlify.app

---

## Architecture

```
Frontend (Netlify — static HTML/JS)
        |
        | HTTPS + JWT Bearer token
        v
FastAPI Backend (Render)
        |
        +─────────────────────────┐
        |                         |
        v                         v
Supabase (Postgres + Auth)      Gemini 1.5 Flash
  farmers                        Explanation text only.
  farm_activities                All quantities come from
  harvests                       the backend.
  vendors
```

### Key design principles

- **Gemini explains; the backend calculates.** Fertilizer quantities, irrigation volumes,
  expected-vs-actual gaps, costs, revenue, profit, and break-even are all computed in Python.
  Gemini receives only deterministic facts and is asked to phrase them in plain farmer language.
- **Graceful degradation.** If Gemini is unavailable, the farmer still sees the correct
  reference data. The application never blocks on a successful LLM call.
- **Structured crop knowledge.** All agricultural data lives in
  `backend/data/crop_knowledge.json`. Adding a new crop requires only adding a new JSON key —
  no Python changes.
- **Row Level Security.** Every farmer-owned table enforces ownership at the database level.
  The backend derives `user_id` from the verified JWT — never from the request body.

---

## Pages

| Page | File | Purpose |
|---|---|---|
| Landing dashboard | `index.html` | Static market & agronomic reference for Taiwan Pink Guava |
| Login | `login.html` | Google OAuth sign-in |
| Onboarding | `onboarding.html` | First-time farm profile creation |
| Care plan | `plan.html` | Personalized stage plan, activity logging, spending, gaps |
| Crop report | `report.html` | Full financial summary and activity history |
| Privacy | `privacy.html` | Privacy policy |

---

## API Endpoints

All farmer endpoints require `Authorization: Bearer <supabase_jwt>` header.

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Uptime check |
| GET | `/api/farmers/me` | Get farmer profile |
| POST | `/api/profile` | Create/update farmer profile |
| PUT | `/api/profile` | Alias for POST |
| GET | `/api/plan` | Get personalized care plan (cached) |
| POST | `/api/farmers/me/plan/generate` | Force-regenerate plan |
| GET | `/api/farmers/me/activities` | List logged activities |
| POST | `/api/farmers/me/activities` | Log a new activity |
| GET | `/api/farmers/me/spending` | Total cost + breakdown |
| GET | `/api/farmers/me/gaps` | Expected-vs-actual input gaps |
| GET | `/api/farmers/me/financial-summary` | Full financial summary |
| POST | `/api/farmers/me/harvest` | Log harvest/sale (write-once) |
| GET | `/api/farmers/me/report` | Full crop-cycle report |
| GET | `/api/farmers/me/vendor-recommendations` | Matched vendor cards (consent-gated) |
| PUT | `/api/farmers/me/vendor-consent` | Update vendor recommendation consent |
| GET | `/api/constants/activity-types` | Allowed activity type values |

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|---|---|---|
| `SUPABASE_URL` | Yes | Your Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Yes | Service-role key (never expose to frontend) |
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `SUPABASE_JWT_SECRET` | No | Only for legacy HS256 JWT projects |

Copy `backend/.env.example` to `backend/.env` and fill in values.

### Frontend (`js/config.js`)

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Same as backend |
| `SUPABASE_ANON_KEY` | Public anon key — safe to commit |
| `API_BASE_URL` | Backend URL (Render or localhost) |

---

## Database Setup

Run `backend/schema.sql` in the Supabase SQL Editor. The script is idempotent —
safe to re-run on an existing database. It creates:

- `farmers` — farmer profile with `expected_yield_kg` and vendor consent fields
- `farm_activities` — activity ledger with RLS
- `harvests` — harvest/sale record (write-once per cycle) with RLS
- `vendors` — manually curated vendor directory with RLS (read-only for farmers)

After running the SQL:

1. Enable Google OAuth in **Supabase → Authentication → Providers → Google**.
2. Add `https://guavaa.netlify.app` and `http://localhost:5500` to
   **Supabase → Authentication → URL Configuration → Redirect URLs**.

---

## Local Development

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
# Create .env from .env.example and fill in values
uvicorn main:app --reload --port 8000
```

The API is available at `http://localhost:8000`.

Update `js/config.js`:
```js
export const API_BASE_URL = "http://localhost:8000";
```

### Frontend

Open `index.html`, `plan.html`, etc. directly in a browser, or use Live Server
(VS Code extension) at `http://localhost:5500`.

### Tests

```powershell
cd backend
python -m pytest tests/ -v
```

All 92 tests cover deterministic logic only. Gemini is mocked — no API key needed
for tests.

---

## Deployment

### Frontend → Netlify

1. Push to GitHub.
2. Connect repository in Netlify. No build command needed — it's static HTML.
3. Set the production URL in `js/config.js`:
   ```js
   export const API_BASE_URL = "https://guava-8wc7.onrender.com";
   ```
4. Add `https://guavaa.netlify.app` to Supabase redirect URLs.

### Backend → Render

1. Create a **Web Service** in Render pointing to the repository.
2. Set **Root Directory** to `backend`.
3. Set **Build Command**: `pip install -r requirements.txt`
4. Set **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Set **Runtime**: Python 3.11
6. Add all environment variables from the table above.

The `/health` endpoint is used by Render for uptime checks.

---

## Adding a New Crop

The application is designed so a new crop requires **only a data change**, not code changes.

### Step 1 — Add crop knowledge

In `backend/data/crop_knowledge.json`, add a new top-level key:

```json
{
  "guava": { ... },
  "mango": {
    "is_final_stage_id": "harvest",
    "stages": [
      {
        "stage_id": "establishment",
        "label": "Establishment",
        "month_start": 0,
        "month_end": 3,
        "description": "...",
        "irrigation": "...",
        "fertigation": "...",
        "pest_checks": "...",
        "reference_plant_count": 1,
        "quantities": {
          "irrigation_litres_per_plant_per_day": 5,
          "fertilizer_grams_per_plant_per_week": 10,
          "fertilizer_name": "NPK 10-26-26",
          "fertilizer_type": "Fertilizer",
          "duration_months": 4
        },
        "ipm": [
          {
            "pest": "Hoppers",
            "check": "Inspect young leaves for hoppers",
            "action": "Apply neem-based spray if present"
          }
        ],
        "activities": ["irrigation", "fertigation", "pest_scouting"]
      }
    ]
  }
}
```

Rules for crop knowledge values:
- All quantities are **per plant per reference period** (per day for irrigation, per week for fertilizer).
- `reference_plant_count` must always be `1`.
- Do not invent quantities — use published extension service data.
- `is_final_stage_id` must match the `stage_id` of the harvest stage.

### Step 2 — Add crop to onboarding

In `onboarding.html`, add an option to the crop `<select>`:

```html
<option value="mango">Mango</option>
```

### Step 3 — Verify

Run `pytest tests/` — all existing tests must still pass.
Load the onboarding form, select Mango, complete the form, and verify the plan page
shows the correct stage for the planting date entered.

No Python files need editing.

---

## Crop Knowledge Schema Reference

Each stage object in `crop_knowledge.json` supports these fields:

| Field | Type | Required | Description |
|---|---|---|---|
| `stage_id` | string | Yes | Unique identifier, snake_case |
| `label` | string | Yes | Display name shown to farmer |
| `month_start` | int | Yes | First complete month of this stage (0-indexed) |
| `month_end` | int | Yes | Last month (use 9999 for open-ended final stage) |
| `description` | string | Yes | Plain-language description (passed to Gemini) |
| `irrigation` | string | Yes | Plain-language irrigation guidance |
| `fertigation` | string | Yes | Plain-language fertilizer guidance |
| `pest_checks` | string | Yes | Plain-language pest check action |
| `reference_plant_count` | int | Yes | Always 1 |
| `quantities.irrigation_litres_per_plant_per_day` | float | Yes | Per-plant daily water volume |
| `quantities.fertilizer_grams_per_plant_per_week` | float | Yes | Per-plant weekly fertilizer dose |
| `quantities.fertilizer_name` | string | Yes | Product name / blend description |
| `quantities.fertilizer_type` | string | Yes | Must be an ACTIVITY_TYPES value |
| `quantities.duration_months` | int/null | No | Months in this stage (null = open-ended) |
| `ipm` | array | No | List of IPM check objects |
| `ipm[].pest` | string | Yes | Pest or disease name |
| `ipm[].check` | string | Yes | What to inspect |
| `ipm[].action` | string | Yes | What to do if found |
| `activities` | array | No | Activity type identifiers for this stage |

---

## Security Notes

- `SUPABASE_SERVICE_KEY` and `GEMINI_API_KEY` are backend-only. They never appear in
  frontend JavaScript.
- `SUPABASE_ANON_KEY` in `js/config.js` is intentionally public — it is the read-only
  anonymous key and is safe to commit.
- All farmer data endpoints validate ownership from the JWT `sub` claim.
  A farmer's `id` from the browser is never trusted for authorization.
- Row Level Security policies enforce ownership at the database level even if the
  application layer is bypassed.
- All numeric inputs (plant_count, quantity, cost, sale_quantity, sale_price) are
  validated to be >= 0 at the API level.
- Harvest submission is write-once — a second POST returns HTTP 409.

---

## Out of Scope (V1)

The following are explicitly not built and should not be added without a new spec:

- Marketplace / checkout / payment
- Vendor self-registration dashboard
- Multi-farm management
- Multiple simultaneous crop cycles
- Photo-based disease diagnosis
- Sensor / drone integrations
- Credit or loan recommendations
- Real-time GPS tracking
