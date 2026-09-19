# Design — Farmer Login + Personalized Crop Care Plan

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                  Netlify (static hosting)                    │
│                                                             │
│  login.html          onboarding.html         plan.html      │
│  js/auth.js          js/onboarding.js        js/plan.js     │
│       │                    │                      │         │
│       └──────── Supabase JS SDK (CDN) ────────────┘         │
└─────────────────────────┬───────────────────────────────────┘
                          │  JWT in Authorization header
                          ▼
┌─────────────────────────────────────────────────────────────┐
│               FastAPI on Render (free tier)                  │
│                                                             │
│  POST /api/profile      ← save / update farmer profile      │
│  GET  /api/plan         ← get care plan (cached or fresh)   │
│                                                             │
│  services/                                                  │
│    stage.py            ← growth-stage computation           │
│    planner.py          ← Gemini prompt build + call         │
│    cache.py            ← profile-hash + cache logic         │
│                                                             │
│  data/                                                      │
│    crop_knowledge.json ← structured stage data (guava now)  │
└──────────┬──────────────────────────┬───────────────────────┘
           │                          │
           ▼                          ▼
  ┌────────────────┐         ┌─────────────────────┐
  │    Supabase    │         │   Google Gemini API  │
  │  Postgres DB   │         │   (Flash tier)       │
  │  + Auth        │         └─────────────────────┘
  └────────────────┘
```

The frontend is three lightweight HTML pages served from Netlify. There is no build step —
plain ES modules and the Supabase JS CDN are sufficient. The existing `index.html` dashboard
is left untouched; the new pages sit alongside it.

---

## 2. Frontend Pages & Files

### 2.1 New Files

| File | Purpose |
|------|---------|
| `login.html` | Landing page — Google Sign-In button only |
| `onboarding.html` | First-time farmer form |
| `plan.html` | Care plan display for authenticated farmers |
| `js/auth.js` | Supabase client init, OAuth callback handling, route guard |
| `js/onboarding.js` | Form logic, state/district cascade, POST to backend |
| `js/plan.js` | Fetch plan from backend, render care plan |
| `js/india-locations.js` | Static state → district lookup data (no network call) |

### 2.2 Existing Files (unchanged)

`index.html`, `css/style.css`, `js/app.js`, `js/data.js`, `js/charts.js`, `js/translator.js`
are not modified. The new pages share the same Tailwind CDN and brand colour config.

### 2.3 Routing Logic (client-side, no SPA framework)

```
User opens any page
       │
       ▼
auth.js: check Supabase session
       │
   ┌───┴──────────────────┐
   │ No session           │ Session exists
   ▼                      ▼
login.html         Has farmers row?
                   ┌──────┴──────┐
                   │ No          │ Yes
                   ▼             ▼
             onboarding.html  plan.html
```

`auth.js` is imported by every page. It reads the current Supabase session and redirects if
the user is on the wrong page for their state. The OAuth callback is handled by Supabase JS
automatically when `login.html` loads after the Google redirect.

---

## 3. Page Designs

### 3.1 login.html

Minimal. No navigation, no dashboard tabs.

```
┌──────────────────────────────────┐  360px wide
│  🌿  Guava Care                  │
│                                  │
│  Your personal guava crop plan   │
│                                  │
│  ┌──────────────────────────┐    │
│  │  G  Sign in with Google  │    │  48px tall, full width
│  └──────────────────────────┘    │
│                                  │
│  Free • No password needed       │
└──────────────────────────────────┘
```

- Supabase `signInWithOAuth({ provider: 'google' })` on button tap.
- No other interactive elements.
- Page loads < 20 KB (Supabase JS CDN + ~2 KB inline styles).

### 3.2 onboarding.html

Single screen, all fields visible without scrolling on 360 × 640.

```
┌──────────────────────────────────┐
│  🌿  Tell us about your farm     │
│                                  │
│  Crop                            │
│  ┌──────────────────────────┐    │  <select> — only "Guava"
│  │ Guava               ▼   │    │
│  └──────────────────────────┘    │
│                                  │
│  Number of plants                │
│  ┌──────────────────────────┐    │  <input type="number">
│  │ e.g. 500                 │    │
│  └──────────────────────────┘    │
│                                  │
│  State                           │
│  ┌──────────────────────────┐    │  <select>
│  │ Select state         ▼  │    │
│  └──────────────────────────┘    │
│                                  │
│  District                        │
│  ┌──────────────────────────┐    │  <select> disabled until state chosen
│  │ Select district      ▼  │    │
│  └──────────────────────────┘    │
│                                  │
│  When did you plant the trees?   │
│  ┌──────────────────────────┐    │  <input type="date"> default=today
│  │ 2026-09-18               │    │
│  └──────────────────────────┘    │
│                                  │
│  ┌──────────────────────────┐    │
│  │      Get my plan         │    │  primary button, 48px tall
│  └──────────────────────────┘    │
└──────────────────────────────────┘
```

Layout constraints:
- Total form height including button: ≤ 540 px (fits 640 px viewport with header).
- Labels: 14 px, field height: 44 px, gap between fields: 12 px.
- No card wrappers, no accordion — just a plain vertical stack.

### 3.3 plan.html

```
┌──────────────────────────────────┐
│  🌿  Your Crop Plan              │
│  500 plants · Guava              │  farmer's own data confirmed
│                                  │
│  ┌──────────────────────────┐    │
│  │  🌱 Month 5              │    │  growth stage badge
│  │  Vegetative Growth       │    │
│  └──────────────────────────┘    │
│                                  │
│  What's happening                │
│  Your trees are growing their    │
│  main branches right now.        │
│                                  │
│  This week                       │
│  💧 Water  Give 4 L per plant    │
│            every day.            │
│                                  │
│  🧪 Feed   Apply 7 g of 19-19-19 │
│            per plant this week.  │
│                                  │
│  🔍 Check  Look for white sticky │
│            insects on stems.     │
│                                  │
│  ─────────────────────────────   │
│  Update my details               │  small text link
└──────────────────────────────────┘
```

- No tabs, no charts, no navigation bar from the existing dashboard.
- Text rendered from the Gemini response — no markdown, plain sentences only.

---

## 4. Backend Design

### 4.1 Project Layout

```
backend/
├── main.py                  ← FastAPI app, CORS, route registration
├── routers/
│   ├── profile.py           ← POST /api/profile
│   └── plan.py              ← GET  /api/plan
├── services/
│   ├── auth.py              ← JWT verification (Supabase secret)
│   ├── stage.py             ← growth stage lookup
│   ├── planner.py           ← Gemini prompt + call
│   └── cache.py             ← profile hash + cache check
├── data/
│   └── crop_knowledge.json  ← guava stage data
├── requirements.txt
└── .env.example             ← SUPABASE_URL, SUPABASE_JWT_SECRET,
                                GEMINI_API_KEY, SUPABASE_SERVICE_KEY
```

### 4.2 API Endpoints

#### `POST /api/profile`

Saves or updates the farmer's profile. Called by `onboarding.js` on form submit.

**Request headers:** `Authorization: Bearer <supabase_jwt>`

**Request body:**
```json
{
  "crop": "guava",
  "plant_count": 500,
  "state": "Madhya Pradesh",
  "district": "Dhar",
  "sowing_date": "2026-04-18"
}
```

**Logic:**
1. Verify JWT → extract `user_id`.
2. Upsert `farmers` row (INSERT … ON CONFLICT (user_id) DO UPDATE).
3. Compute `profile_hash` from the five profile fields (SHA-256, hex digest).
4. If hash differs from stored value, clear `cached_plan` and `profile_hash` so next
   `GET /api/plan` triggers a fresh generation.
5. Return `{ "status": "saved" }`.

**Error responses:** 401 (bad token), 422 (validation error), 500 (DB error).

#### `GET /api/plan`

Returns the care plan — from cache if profile is unchanged, from Gemini if not.

**Request headers:** `Authorization: Bearer <supabase_jwt>`

**Response:**
```json
{
  "stage_label": "Vegetative Growth",
  "months_elapsed": 5,
  "plan_text": "...",
  "from_cache": true
}
```

**Logic (see §4.4 for detail):**
1. Verify JWT → `user_id`.
2. Fetch `farmers` row for `user_id`.
3. Compute current `profile_hash`; compare to stored.
4. If match AND `cached_plan` is not null → return cached plan.
5. Else → run generation pipeline → store → return fresh plan.

**Error responses:** 401, 404 (no profile yet — frontend redirects to onboarding), 500.

### 4.3 JWT Verification (`services/auth.py`)

```python
import jwt  # PyJWT
from fastapi import HTTPException, Header

SUPABASE_JWT_SECRET = os.environ["SUPABASE_JWT_SECRET"]

def get_user_id(authorization: str = Header(...)) -> str:
    """Verify Supabase JWT and return user_id (sub claim)."""
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload["sub"]
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail="Invalid token")
```

Used as a FastAPI dependency on every protected route.

### 4.4 Growth Stage Computation (`services/stage.py`)

```python
from datetime import date
from fastapi import HTTPException
import json, pathlib

_knowledge = json.loads(
    (pathlib.Path(__file__).parent.parent / "data" / "crop_knowledge.json").read_text()
)

def get_stage(crop: str, sowing_date: date) -> tuple[dict, int]:
    """Return the matching stage dict and months_elapsed for the given crop and sowing date.

    Raises HTTPException 422 if sowing_date is in the future.
    Stage boundaries come exclusively from crop_knowledge.json — no constants in this file.
    """
    today = date.today()

    # Reject future sowing dates (Req 5.6) — do not clamp, reject explicitly
    if sowing_date > today:
        raise HTTPException(
            status_code=422,
            detail="Planting date cannot be in the future."
        )

    # Integer complete months elapsed
    months = (today.year - sowing_date.year) * 12 + (today.month - sowing_date.month)
    if today.day < sowing_date.day:
        months -= 1

    stages = _knowledge[crop.lower()]["stages"]
    # Walk stages in order; return the last one whose month_start <= months_elapsed
    matched = stages[0]
    for stage in stages:
        if stage["month_start"] <= months:
            matched = stage
        else:
            break
    return matched, months
```

### 4.5 Gemini Prompt Construction (`services/planner.py`)

The prompt is structured in three parts:

```
SYSTEM:
You are an agricultural assistant. You must use ONLY the reference data provided below.
Do not add any advice, product names, or quantities not present in the reference data.
Write in simple, plain language — short sentences, no jargon, no Latin names.
The farmer has {plant_count} plants.

REFERENCE DATA (use only this):
Stage: {stage["label"]}
Description: {stage["description"]}
Irrigation: {stage["irrigation"]}
Fertigation (per plant): {stage["fertigation"]}  ← scaled by plant_count before passing
Pest checks: {stage["pest_checks"]}

TASK:
Write a care plan for this farmer for the current week.
Include:
1. One sentence about what is happening to the crop right now.
2. Irrigation guidance for this week.
3. Fertigation guidance for this week (use the quantities provided above).
4. One pest-check action for this week.

Output plain text only. No bullet symbols, no markdown, no headings.
```

The backend scales fertigation quantities by `plant_count / reference_plant_count` (where
`reference_plant_count` is a field in the stage data, e.g. 1) before inserting into the
prompt, so Gemini receives already-scaled numbers and cannot hallucinate doses.

### 4.6 Plan Caching (`services/cache.py`)

```python
import hashlib

def compute_profile_hash(crop, plant_count, state, district, sowing_date) -> str:
    raw = f"{crop}|{plant_count}|{state}|{district}|{sowing_date}"
    return hashlib.sha256(raw.encode()).hexdigest()
```

The hash is stored in the `farmers` table alongside the cached plan. On each `GET /api/plan`
request:

```
recompute hash
     │
hash == stored?  AND  cached_plan not null?
     │                          │
    YES                        NO
     │                          │
return cached_plan         call Gemini
                                │
                         update cached_plan,
                         profile_hash,
                         plan_generated_at
                                │
                         return fresh plan
```

---

## 5. Database Schema (Supabase SQL)

```sql
-- Enable UUID extension (already on by default in Supabase)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE farmers (
  id                 UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id            UUID        NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
  crop               TEXT        NOT NULL,
  plant_count        INTEGER     NOT NULL CHECK (plant_count > 0),
  state              TEXT        NOT NULL,
  district           TEXT        NOT NULL,
  sowing_date        DATE        NOT NULL,
  cached_plan        TEXT,
  profile_hash       TEXT,
  plan_generated_at  TIMESTAMPTZ,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Row-level security
ALTER TABLE farmers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Farmers can read own row"
  ON farmers FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Farmers can insert own row"
  ON farmers FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Farmers can update own row"
  ON farmers FOR UPDATE
  USING (auth.uid() = user_id);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER farmers_updated_at
  BEFORE UPDATE ON farmers
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

---

## 6. Crop Knowledge JSON Structure

```json
{
  "guava": {
    "stages": [
      {
        "stage_id": "establishment",
        "label": "Establishment",
        "month_start": 0,
        "month_end": 2,
        "description": "Trees are settling in. Roots are growing.",
        "irrigation": "Water every day. Give 3 litres per plant.",
        "fertigation": "Give 5 g of 19-19-19 fertiliser per plant each week.",
        "pest_checks": "Check the base of each stem for white sticky insects.",
        "reference_plant_count": 1
      },
      {
        "stage_id": "vegetative_growth",
        "label": "Vegetative Growth",
        "month_start": 3,
        "month_end": 7,
        "description": "Branches are growing. The tree is building its shape.",
        "irrigation": "Water every day. Give 4 litres per plant.",
        "fertigation": "Give 7 g of 19-19-19 fertiliser per plant each week.",
        "pest_checks": "Look for wilted shoot tips — this means a borer is inside.",
        "reference_plant_count": 1
      }
      // ... remaining stages following same shape
    ]
  }
  // New crops added here without touching Python code
}
```

Rules for this file (enforced by code review, noted in file header):
- All quantities are per single plant.
- No Latin names, no chemical formulas — plain language only.
- `month_start` of each stage must be exactly one more than `month_end` of the previous.
- `reference_plant_count` is always 1 (quantities are already per-plant).

---

## 7. Frontend JavaScript Design

### 7.1 `js/auth.js` (shared by all three pages)

```js
import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js/+esm'

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

/**
 * Returns the active session, or null.
 * Handles the OAuth callback automatically (Supabase JS detects the URL hash).
 */
export async function getSession() {
  const { data: { session } } = await supabase.auth.getSession()
  return session
}

/**
 * Call on every protected page. Redirects to login.html if not signed in.
 * Redirects to onboarding.html if signed in but no farmers row exists.
 * Redirects to plan.html if signed in and profile exists.
 */
export async function routeGuard(currentPage) { ... }
```

`SUPABASE_URL` and `SUPABASE_ANON_KEY` are inlined as JS constants in a small
`js/config.js` file — these are public-safe anon keys, not service keys.

### 7.2 `js/onboarding.js`

```
DOMContentLoaded
  → routeGuard('onboarding')          // redirects away if already has profile
  → populate State <select>           // from india-locations.js
  → on State change → populate District <select>
  → on form submit:
      validate plant_count > 0
      POST /api/profile with JWT
      on success → redirect to plan.html
      on error   → show inline error message
```

### 7.3 `js/plan.js`

```
DOMContentLoaded
  → routeGuard('plan')                // redirects to login if no session
  → show loading indicator
  → GET /api/plan with JWT
      on success:
        render plan (stage badge + plan text)
        hide loading indicator
      on HTTP 404:
        redirect to onboarding.html
      on error / timeout:
        hide loading indicator
        show friendly error message
```

### 7.4 `js/india-locations.js`

A static JS module exporting a `STATES_DISTRICTS` object keyed by state name, each value
being an array of district strings. Data is embedded at build time (no API call) — sourced
from the Ministry of Panchayati Raj Local Government Directory (LGD, lgdirectory.nic.in),
the continuously-updated government registry of administrative boundaries. Approximately 800
districts across all 28 states and 8 UTs. File size is roughly 30 KB uncompressed, acceptable
for the target connection. A comment at the top of the file records the source and build date
per Req 9.5.

---

## 8. Styling Conventions

All new pages follow the existing brand palette:

| Token | Value | Usage |
|-------|-------|-------|
| `brand-primary` | `#1E3A2B` | Header background, primary button |
| `brand-secondary` | `#4A7C59` | Active states, stage badge |
| `brand-accent` | `#E07A5F` | CTA hover, error states |
| `brand-bg` | `#FDFBF7` | Page background |

The Tailwind config `<script>` block from `index.html` is duplicated verbatim in each new
page's `<head>` so the colour tokens are available without a build step.

Primary button style (consistent with existing dashboard's active nav button):
```
background: #1E3A2B; color: white; border-radius: 8px;
padding: 12px 16px; font-size: 16px; width: 100%;
min-height: 48px;  /* WCAG 2.5.5 touch target */
```

---

## 9. Error States & Edge Cases

| Scenario | Frontend behaviour | Backend behaviour |
|----------|--------------------|-------------------|
| User denies Google OAuth | Stay on login.html, show "Sign-in cancelled" message | — |
| Form submitted with plants = 0 | Inline error, no API call | 422 returned anyway as safety net |
| Backend timeout (Render cold start) | Show spinner up to 35 s, then show friendly error | — |
| Gemini API failure | Return 500; frontend shows "Plan not available right now. Try again later." | Log error, do not expose Gemini error text to client |
| No profile row on GET /api/plan | Return 404 | Frontend redirects to onboarding.html |
| Sowing date in the future | Inline error on form, no API call | `get_stage()` raises HTTP 422 "Planting date cannot be in the future." (Req 5.6) |
| All Supabase RLS blocks a query | 403 from Supabase; backend raises 401 to client | Logged server-side |

---

## 10. Deployment Checklist (not a task — reference only)

**Supabase:**
- Enable Google OAuth provider in Supabase Auth dashboard.
- Add `https://guavaa.netlify.app` to allowed redirect URLs.
- Run the schema SQL from §5.

**Render:**
- New Web Service, Python 3.11, free tier.
- Set env vars: `SUPABASE_URL`, `SUPABASE_JWT_SECRET`, `SUPABASE_SERVICE_KEY`,
  `GEMINI_API_KEY`.
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`.
- Add `https://guavaa.netlify.app` to CORS allowed origins.

**Netlify:**
- New files (`login.html`, `onboarding.html`, `plan.html`, `js/auth.js`,
  `js/onboarding.js`, `js/plan.js`, `js/india-locations.js`, `js/config.js`)
  are committed to the repo and auto-deployed on push.
- `js/config.js` contains only public anon key — safe to commit.
