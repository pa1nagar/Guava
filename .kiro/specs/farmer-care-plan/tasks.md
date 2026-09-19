# Tasks — Farmer Login + Personalized Crop Care Plan

## Overview

27 implementation tasks across 6 phases. Tasks within each phase are ordered — later tasks
depend on earlier ones inside the same phase. Phases are sequential. Each task is scoped for
a single focused pass.

**New files produced by this spec:**

Frontend (Netlify):
`login.html`, `onboarding.html`, `plan.html`,
`js/config.js`, `js/auth.js`, `js/onboarding.js`, `js/plan.js`, `js/india-locations.js`

Backend (Render):
`backend/main.py`, `backend/routers/profile.py`, `backend/routers/plan.py`,
`backend/services/auth.py`, `backend/services/stage.py`, `backend/services/planner.py`,
`backend/services/cache.py`, `backend/data/crop_knowledge.json`,
`backend/requirements.txt`, `backend/.env.example`, `backend/schema.sql`

Supporting:
`README-farmer-feature.md`

---

## Phase 1 — Backend Scaffold & Data

### Task 1: Create backend folder structure and stub files
- [ ] 1.1 Create `backend/` directory at workspace root
- [ ] 1.2 Create subdirectories: `backend/routers/`, `backend/services/`, `backend/data/`
- [ ] 1.3 Create empty stub files: `backend/main.py`, `backend/routers/__init__.py`,
      `backend/routers/profile.py`, `backend/routers/plan.py`,
      `backend/services/__init__.py`, `backend/services/auth.py`,
      `backend/services/stage.py`, `backend/services/planner.py`,
      `backend/services/cache.py`
- [ ] 1.4 Create `backend/.env.example` with four placeholder keys:
      `SUPABASE_URL=`, `SUPABASE_JWT_SECRET=`, `SUPABASE_SERVICE_KEY=`, `GEMINI_API_KEY=`
- [ ] 1.5 Confirm all files and directories exist before proceeding

**Files:** all backend stubs, `backend/.env.example`
**Depends on:** nothing

---

### Task 2: Write `backend/requirements.txt`
- [ ] 2.1 Add these pinned dependencies (exact versions, no open ranges):
      `fastapi==0.111.0`, `uvicorn[standard]==0.29.0`, `pyjwt==2.8.0`,
      `python-dotenv==1.0.1`, `httpx==0.27.0`, `supabase==2.4.6`,
      `google-generativeai==0.7.2`, `python-multipart==0.0.9`
- [ ] 2.2 Verify every version pin uses `==` — no `>=`, `~=`, or unpinned entries

**Files:** `backend/requirements.txt`
**Depends on:** Task 1

---

### Task 3: Write `backend/data/crop_knowledge.json`
- [ ] 3.1 Add file-header comment: `"_comment": "Do not add prose advice here — all text
      is passed verbatim to Gemini as reference data."`
- [ ] 3.2 Create top-level `"guava"` key with a `"stages"` array
- [ ] 3.3 Add 9 stage objects covering the full guava lifecycle aligned with the
      `IRRIGATION_STAGES` / `CALENDAR_DATA` already in `js/data.js`.
      Stage boundaries: 0–2 (Establishment), 3–7 (Vegetative Growth), 8–10
      (Post-Monsoon), 11–12 (Pre-Bloom), 13–14 (Bloom & Fruit Set), 15 (Fruit
      Development), 16 (Drought Stress), 17 (Harvest), 18+ (Post-Harvest / Mature)
- [ ] 3.4 Each stage object must contain exactly these fields:
      `stage_id` (snake_case string), `label` (plain English), `month_start` (int),
      `month_end` (int), `description` (one plain sentence), `irrigation` (plain text,
      per-plant daily volume), `fertigation` (plain text, per-plant weekly dose),
      `pest_checks` (plain text, one scouting action), `reference_plant_count` (always 1)
- [ ] 3.5 Verify `month_start` of each stage is exactly one greater than `month_end` of
      the previous stage — no gaps, no overlaps
- [ ] 3.6 Verify all text fields contain no Latin names, no chemical formulas, no absolute
      claims ("guaranteed", "always", "zero")

**Files:** `backend/data/crop_knowledge.json`
**Depends on:** Task 1

---

### Task 4: Write `backend/services/auth.py`
- [ ] 4.1 Import `os`, `jwt` (PyJWT), `fastapi.HTTPException`, `fastapi.Header`
- [ ] 4.2 Read `SUPABASE_JWT_SECRET` from `os.environ` at module load; raise `RuntimeError`
      with a clear message if the variable is absent so the server fails fast on startup
- [ ] 4.3 Implement `get_user_id(authorization: str = Header(...)) -> str`:
      - Strip `"Bearer "` prefix (use `str.removeprefix`)
      - Decode with `jwt.decode(token, secret, algorithms=["HS256"],
        audience="authenticated")`
      - Return `payload["sub"]`
      - Catch any `jwt.PyJWTError` and raise `HTTPException(status_code=401,
        detail="Invalid token")`
- [ ] 4.4 Confirm the function signature is compatible with FastAPI `Depends()` —
      it must accept a single `Header(...)` parameter and return a plain string

**Files:** `backend/services/auth.py`
**Depends on:** Task 1

---

### Task 5: Write `backend/services/stage.py`
- [ ] 5.1 Load `crop_knowledge.json` once at module import time using `pathlib.Path`;
      store in a module-level `_knowledge` dict — do not reload on every request
- [ ] 5.2 Implement `get_stage(crop: str, sowing_date: date) -> tuple[dict, int]`:
      - Import `HTTPException` from fastapi
      - If `sowing_date > date.today()`, raise
        `HTTPException(status_code=422, detail="Planting date cannot be in the future.")`
        — do NOT clamp with `max(..., 0)` (Req 5.6)
      - Compute `months_elapsed` as integer complete months between `sowing_date`
        and `date.today()`, adjusting by -1 when `today.day < sowing_date.day`
      - Walk `_knowledge[crop.lower()]["stages"]`; return the last stage whose
        `month_start <= months_elapsed`, falling back to `stages[0]` if elapsed = 0
      - Return `(matched_stage_dict, months_elapsed)`
- [ ] 5.3 Raise `KeyError` with a descriptive message if `crop` is not in `_knowledge`
      (the router catches this and returns HTTP 422 "Crop not supported")
- [ ] 5.4 Add a docstring stating: "Stage boundaries come exclusively from
      crop_knowledge.json — no stage constants are defined in this module."

**Files:** `backend/services/stage.py`
**Depends on:** Task 3

---

### Task 6: Write `backend/services/cache.py`
- [ ] 6.1 Import `hashlib`
- [ ] 6.2 Implement `compute_profile_hash(crop, plant_count, state, district,
      sowing_date) -> str`:
      - Concatenate as `f"{crop}|{plant_count}|{state}|{district}|{sowing_date}"`
      - Return `hashlib.sha256(raw.encode()).hexdigest()`
- [ ] 6.3 Add a module docstring: "This hash is the sole mechanism for deciding whether
      to regenerate a plan. Same inputs must always produce the same hash."

**Files:** `backend/services/cache.py`
**Depends on:** Task 1

---

### Task 7: Write `backend/services/planner.py`
- [ ] 7.1 Import `google.generativeai as genai`; call `genai.configure(api_key=
      os.environ["GEMINI_API_KEY"])` at module load; raise `RuntimeError` if key absent
- [ ] 7.2 Implement `build_prompt(stage: dict, plant_count: int) -> str`:
      - Compute `scaled_fertigation`: multiply any numeric token in
        `stage["fertigation"]` by `plant_count` (simple regex replace on the per-plant
        quantity string) to produce a total-quantity string
      - Build and return the full prompt string with three clearly labelled sections:
        - SYSTEM: "Use ONLY the reference data below. Invent nothing. Write in plain
          language. Short sentences. No jargon. No Latin names. The farmer has
          {plant_count} plants."
        - REFERENCE DATA: stage label, description, irrigation, scaled fertigation,
          pest_checks — each on its own labelled line
        - TASK: instruct exactly four outputs (current situation, irrigation this week,
          feeding this week, pest-check this week); end with "Output plain text only.
          No bullet symbols, no markdown, no headings."
- [ ] 7.3 Implement `generate_plan(stage: dict, plant_count: int) -> str`:
      - Call `build_prompt(stage, plant_count)`
      - Call `genai.GenerativeModel("gemini-1.5-flash").generate_content(prompt)`
      - Return `response.text.strip()`
      - Catch all exceptions, log them server-side, and raise
        `RuntimeError("Gemini unavailable")` — never forward raw Gemini error text
        to the caller

**Files:** `backend/services/planner.py`
**Depends on:** Tasks 3, 5

---

## Phase 2 — Backend API

### Task 8: Write `backend/main.py`
- [ ] 8.1 Create `FastAPI(title="Guava Care API")` app instance
- [ ] 8.2 Call `load_dotenv()` (python-dotenv) before any imports that read `os.environ`
- [ ] 8.3 Add `CORSMiddleware` with `allow_origins=["https://guavaa.netlify.app",
      "http://localhost:3000", "http://localhost:8080"]`,
      `allow_methods=["GET", "POST"]`, `allow_headers=["*"]`
- [ ] 8.4 Include routers: `app.include_router(profile_router, prefix="/api")` and
      `app.include_router(plan_router, prefix="/api")`
- [ ] 8.5 Add `GET /health` returning `{"status": "ok"}` — used by Render's uptime check

**Files:** `backend/main.py`
**Depends on:** Tasks 4, 5, 6, 7

---

### Task 9: Write `backend/routers/profile.py`
- [ ] 9.1 Define `ProfileIn` Pydantic model: `crop: str`, `plant_count: int = Field(gt=0)`,
      `state: str`, `district: str`, `sowing_date: date`
- [ ] 9.2 Implement `POST /profile` endpoint with `user_id: str = Depends(get_user_id)`:
      - Validate sowing_date directly: `if body.sowing_date > date.today(): raise
        HTTPException(422, "Planting date cannot be in the future.")` — do this before
        the hash computation and DB write; do NOT import stage.py for this check
      - Compute `new_hash = cache.compute_profile_hash(crop, plant_count, state,
        district, sowing_date)`
      - Upsert into `farmers` via Supabase service-role client:
        `INSERT ... ON CONFLICT (user_id) DO UPDATE SET crop=..., ..., updated_at=now()`
      - If `new_hash` differs from the stored `profile_hash`, also set
        `cached_plan = NULL` and `profile_hash = new_hash` in the same upsert
      - Return `{"status": "saved"}`
- [ ] 9.3 Catch `KeyError` (unknown crop) → HTTP 422 "Crop not supported"
- [ ] 9.4 Catch all Supabase/DB errors → HTTP 500; log the real error server-side;
      return only `{"detail": "Database error"}` to the client

**Files:** `backend/routers/profile.py`
**Depends on:** Tasks 4, 6, 8

---

### Task 10: Write `backend/routers/plan.py`
- [ ] 10.1 Define `PlanOut` Pydantic model: `stage_label: str`, `months_elapsed: int`,
       `plan_text: str`, `from_cache: bool`
- [ ] 10.2 Implement `GET /plan` endpoint with `user_id: str = Depends(get_user_id)`:
       - Fetch farmer row from `farmers` (select all columns); return HTTP 404 if absent
         (frontend redirects to onboarding)
       - Compute `current_hash = cache.compute_profile_hash(...)` from the stored fields
       - If `current_hash == stored profile_hash` AND `cached_plan` is not None:
         return `PlanOut(... from_cache=True)`
       - Else: call `stage.get_stage(crop, sowing_date)` to get `(stage, months_elapsed)`;
         call `planner.generate_plan(stage, plant_count)`; update `farmers` row with
         `cached_plan`, `profile_hash = current_hash`, `plan_generated_at = now()`;
         return `PlanOut(... from_cache=False)`
- [ ] 10.3 Catch `RuntimeError("Gemini unavailable")` → HTTP 500 with
       `{"detail": "Plan generation failed. Please try again later."}`
- [ ] 10.4 Confirm response body never contains `user_id`, API keys, or raw DB errors

**Files:** `backend/routers/plan.py`
**Depends on:** Tasks 4, 5, 6, 7, 9

---

## Phase 3 — Frontend Shared Utilities

### Task 11: Write `js/config.js`
- [ ] 11.1 Export `const SUPABASE_URL` and `const SUPABASE_ANON_KEY` (public anon key)
- [ ] 11.2 Export `const API_BASE_URL` pointing to the Render backend URL
- [ ] 11.3 Add comment: "These are public-safe browser keys. Never put the service key
       or JWT secret here."

**Files:** `js/config.js`
**Depends on:** nothing

---

### Task 12: Write `js/auth.js`
- [ ] 12.1 Import `createClient` from Supabase JS CDN ESM URL; import `SUPABASE_URL`,
       `SUPABASE_ANON_KEY` from `./config.js`
- [ ] 12.2 Export `const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)`
- [ ] 12.3 Export `async function getSession()` — returns session or null
- [ ] 12.4 Export `async function getJwt()` — returns `session?.access_token ?? null`
- [ ] 12.5 Export `async function signInWithGoogle()` — calls
       `supabase.auth.signInWithOAuth({ provider: 'google', options: { redirectTo:
       window.location.origin + '/plan.html' } })`
- [ ] 12.6 Export `async function signOut()` — calls `supabase.auth.signOut()` then
       `window.location.href = 'login.html'`
- [ ] 12.7 Export `async function routeGuard(currentPage)`:
       - No session + not on 'login' → redirect to `login.html`
       - Session + on 'login' or 'onboarding' → call `GET {API_BASE_URL}/api/plan` with
         JWT; if HTTP 200 → redirect to `plan.html`; if HTTP 404 → redirect to
         `onboarding.html`; if on 'plan' → do nothing

**Files:** `js/auth.js`
**Depends on:** Task 11

---

### Task 13: Write `js/india-locations.js`
- [ ] 13.1 Add file-header comment: "District data sourced from Ministry of Panchayati Raj
       Local Government Directory (LGD), lgdirectory.nic.in — current as of build date."
- [ ] 13.2 Export `const STATES_DISTRICTS` object with all 28 states and 8 UTs as keys,
       each mapping to a sorted array of district strings; data sourced from LGD (not the
       2011 Census — see Req 9.1)
- [ ] 13.3 The 10 priority states must have complete district coverage: Uttar Pradesh,
       Madhya Pradesh, Bihar, Maharashtra, Karnataka, Andhra Pradesh, Telangana (post-2014
       boundaries), Gujarat, Rajasthan, West Bengal
- [ ] 13.4 Telangana's districts must reflect post-bifurcation boundaries — do not use
       any pre-2014 Andhra Pradesh district list for Telangana
- [ ] 13.5 Export `function getStates()` returning `Object.keys(STATES_DISTRICTS).sort()`
- [ ] 13.6 Export `function getDistricts(state)` returning
       `(STATES_DISTRICTS[state] ?? []).slice().sort()` (sorted, non-mutating)

**Files:** `js/india-locations.js`
**Depends on:** nothing

---

## Phase 4 — Frontend Pages

### Task 14: Write `login.html`
- [ ] 14.1 Standard HTML5 boilerplate: charset UTF-8, mobile viewport meta, title
       "Guava Care — Login"
- [ ] 14.2 Tailwind CDN `<script>` + brand colour config block (copy verbatim from
       `index.html`); no Chart.js, no `app.js`, no `data.js`
- [ ] 14.3 Body: full-viewport-height flex column, vertically and horizontally centred.
       Elements in order:
       - 🌿 icon + "Guava Care" heading (`text-2xl font-bold`, brand-primary colour)
       - Tagline: "Your personal guava crop plan" (`text-sm text-gray-500`)
       - `mt-8` spacer
       - `<button id="btn-google-signin">Sign in with Google</button>`:
         `w-full min-h-[48px] bg-brand-primary text-white rounded-lg text-base font-semibold`
       - Caption: "Free · No password needed" (`text-xs text-gray-400 mt-2`)
       - `<span id="auth-error" class="hidden text-red-600 text-sm mt-3">` for error
         display
- [ ] 14.4 `<script type="module">`: import `routeGuard`, `signInWithGoogle` from
       `./js/auth.js`; on `DOMContentLoaded` call `routeGuard('login')`; on button click
       call `signInWithGoogle()`, catch errors and show `#auth-error`

**Files:** `login.html`
**Depends on:** Tasks 11, 12

---

### Task 15: Write `onboarding.html`
- [ ] 15.1 Standard boilerplate + Tailwind CDN + brand config; no Chart.js, no `app.js`
- [ ] 15.2 Header bar: brand-primary background, white "🌿 Tell us about your farm" text,
       no navigation tabs
- [ ] 15.3 `<form id="onboarding-form" autocomplete="off">` — plain vertical stack,
       no card wrappers:
       - Crop: `<select id="crop"><option value="guava">Guava</option></select>`
       - Plants: `<input type="number" id="plant-count" min="1" placeholder="e.g. 500">`
         + `<span id="plant-count-error" class="hidden text-red-600 text-sm">`
       - State: `<select id="state-select"><option value="">Select state</option></select>`
       - District: `<select id="district-select" disabled>
         <option value="">Select district</option></select>`
       - Date planted: `<input type="date" id="sowing-date">`
         + `<span id="sowing-date-error" class="hidden text-red-600 text-sm">`
       - `<button type="submit" id="btn-submit">Get my plan</button>`:
         `w-full min-h-[48px] bg-brand-primary text-white rounded-lg text-base font-semibold`
       - `<div id="form-error" class="hidden text-red-600 text-sm">`
       - `<div id="form-loading" class="hidden text-gray-500 text-sm">Getting your plan…`
- [ ] 15.4 All fields + button must be visible on 360 × 640 px without scrolling
       (total form height ≤ 540 px: label 18 px + field 44 px + gap 12 px per row)
- [ ] 15.5 `<script type="module" src="js/onboarding.js"></script>` only

**Files:** `onboarding.html`
**Depends on:** Tasks 11, 12

---

### Task 16: Write `js/onboarding.js`
- [ ] 16.1 Import `routeGuard`, `getJwt` from `./auth.js`; import `getStates`,
       `getDistricts` from `./india-locations.js`; import `API_BASE_URL` from `./config.js`
- [ ] 16.2 On `DOMContentLoaded`:
       - Call `routeGuard('onboarding')`
       - Set `#sowing-date` value to `new Date().toISOString().split('T')[0]` (today)
       - Populate `#state-select` with one `<option>` per entry in `getStates()`
- [ ] 16.3 On `#state-select` change: clear and repopulate `#district-select` using
       `getDistricts(selectedValue)`; remove `disabled` attribute; reset to blank default
- [ ] 16.4 On `#onboarding-form` submit (prevent default):
       - Validate `plant_count`: if not a positive integer, show `#plant-count-error`
         "Number of plants must be at least 1." and return
       - Validate `sowing_date`: if `new Date(value) > new Date()` (today at midnight),
         show `#sowing-date-error` "Planting date cannot be in the future." and return
       - Clear all errors; hide `#btn-submit`; show `#form-loading`
       - `POST {API_BASE_URL}/api/profile` with `Authorization: Bearer {jwt}` and JSON body
       - On success (2xx): `window.location.href = 'plan.html'`
       - On HTTP 422: parse `detail` field; show in `#form-error`
       - On any other error / network failure: show "Something went wrong. Please try
         again." in `#form-error`
       - Always: restore `#btn-submit`, hide `#form-loading`

**Files:** `js/onboarding.js`
**Depends on:** Tasks 12, 13, 15

---

### Task 17: Write `plan.html`
- [ ] 17.1 Standard boilerplate + Tailwind CDN + brand config; no Chart.js, no `app.js`
- [ ] 17.2 Header bar: brand-primary background, white "🌿 Your Crop Plan" heading
- [ ] 17.3 `<div id="farmer-context" class="text-sm text-gray-500 px-4 py-2">` — JS
       populates with plant count + crop name
- [ ] 17.4 Main content — all sections hidden initially, shown by JS:
       - `<div id="plan-loading" class="hidden">` — spinner + "Getting your plan…"
       - `<div id="plan-content" class="hidden">`:
         - `<div id="stage-badge">` — growth stage + month number
         - `<div id="plan-text">` — plan paragraphs injected by JS
         - `<hr class="my-4">`
         - `<a href="onboarding.html" class="text-sm text-brand-secondary underline">
           Update my details</a>`
       - `<div id="plan-error" class="hidden text-red-600 text-sm px-4">`
- [ ] 17.5 `<script type="module" src="js/plan.js"></script>` only; no other JS

**Files:** `plan.html`
**Depends on:** Tasks 11, 12

---

### Task 18: Write `js/plan.js`
- [ ] 18.1 Import `routeGuard`, `getJwt`, `supabase` from `./auth.js`;
       import `API_BASE_URL` from `./config.js`
- [ ] 18.2 On `DOMContentLoaded`:
       - Call `routeGuard('plan')`
       - Show `#plan-loading`; hide `#plan-content`, `#plan-error`
       - Fetch session from `supabase.auth.getSession()`; extract `user.user_metadata`
         or use data returned from the API for farmer context
       - `GET {API_BASE_URL}/api/plan` with `Authorization: Bearer {jwt}`
       - On success (200): populate `#stage-badge` with
         `"🌱 {stage_label} — Month {months_elapsed}"` in brand-secondary colour;
         split `plan_text` on `\n`, wrap each non-empty line in `<p class="mb-3">`,
         inject into `#plan-text`; populate `#farmer-context`; hide `#plan-loading`;
         show `#plan-content`
       - On HTTP 404: `window.location.href = 'onboarding.html'`
       - On any other error / timeout: hide `#plan-loading`; show `#plan-error` with
         "Plan not available right now. Please check your connection and try again."

**Files:** `js/plan.js`
**Depends on:** Tasks 12, 17

---

## Phase 5 — Database Setup

### Task 19: Write `backend/schema.sql`
- [ ] 19.1 Add header comment block explaining how to apply: "Run in the Supabase SQL
       Editor. Safe to re-run — uses IF NOT EXISTS / CREATE OR REPLACE."
- [ ] 19.2 `CREATE EXTENSION IF NOT EXISTS "pgcrypto"`
- [ ] 19.3 `CREATE TABLE IF NOT EXISTS farmers` with all 11 columns per Req 7.1:
       `id`, `user_id`, `crop`, `plant_count CHECK (plant_count > 0)`, `state`,
       `district`, `sowing_date`, `cached_plan`, `profile_hash`, `plan_generated_at`,
       `created_at DEFAULT now()`, `updated_at DEFAULT now()`; `user_id` references
       `auth.users(id) ON DELETE CASCADE` and is UNIQUE
- [ ] 19.4 `ALTER TABLE farmers ENABLE ROW LEVEL SECURITY`
- [ ] 19.5 Three RLS policies (SELECT / INSERT / UPDATE) using `auth.uid() = user_id`
- [ ] 19.6 `CREATE OR REPLACE FUNCTION set_updated_at()` trigger function
- [ ] 19.7 `CREATE TRIGGER farmers_updated_at BEFORE UPDATE ON farmers FOR EACH ROW
       EXECUTE FUNCTION set_updated_at()`

**Files:** `backend/schema.sql`
**Depends on:** Task 1

---

## Phase 6 — Verification & Documentation

### Task 20: Verify backend startup — health check and environment guard
- [ ] 20.1 Install dependencies: `pip install -r requirements.txt` from `backend/`
- [ ] 20.2 Copy `.env.example` to `.env`; fill in real or test credentials
- [ ] 20.3 Start the server: `uvicorn main:app --reload` from `backend/`
- [ ] 20.4 Confirm `GET http://localhost:8000/health` returns `{"status": "ok"}`
- [ ] 20.5 Rename `.env` temporarily (or remove a key); confirm the server fails at
       startup with a clear error message, not a runtime crash on first request

**Files:** (verification only)
**Depends on:** Tasks 8, 9, 10

---

### Task 21: Verify JWT enforcement
- [ ] 21.1 `POST /api/profile` with no `Authorization` header → confirm 422 or 401
- [ ] 21.2 `POST /api/profile` with `Authorization: Bearer garbage` → confirm 401
- [ ] 21.3 `GET /api/plan` with `Authorization: Bearer garbage` → confirm 401
- [ ] 21.4 Confirm neither response body contains a stack trace or internal error detail

**Files:** (verification only)
**Depends on:** Task 20

---

### Task 22: Verify future sowing-date rejection at both layers
- [ ] 22.1 In `onboarding.html` (opened in browser): set sowing date to tomorrow;
       confirm the form shows the inline error and does NOT call the API
- [ ] 22.2 Make a direct `POST /api/profile` with a valid JWT and
       `"sowing_date": "<tomorrow's date>"` → confirm HTTP 422 with
       `"Planting date cannot be in the future."` (Req 5.6)
- [ ] 22.3 Confirm `GET /api/plan` also raises 422 if the stored `sowing_date` somehow
       ends up in the future (edge case: call `get_stage` directly in a test script)

**Files:** (verification only)
**Depends on:** Tasks 9, 10, 16

---

### Task 23: Verify growth stage computation
- [ ] 23.1 In a Python script, import `services.stage.get_stage`:
       - `sowing_date = today − 5 months` → confirm `months_elapsed == 5` and
         returned stage has `month_start <= 5`
       - `sowing_date = today − 0 days` (today) → confirm `months_elapsed == 0`,
         stage is "Establishment"
       - `sowing_date = today − 36 months` → confirm the final (mature) stage is
         returned
- [ ] 23.2 Confirm all 9 stage boundaries in `crop_knowledge.json` are contiguous
       (no gap between one stage's `month_end` and the next's `month_start`)

**Files:** (verification only)
**Depends on:** Tasks 3, 5

---

### Task 24: Verify plan caching end-to-end
- [ ] 24.1 `POST /api/profile` for a test user → confirm `{"status": "saved"}`
- [ ] 24.2 `GET /api/plan` → confirm `from_cache: false`, plan text is non-empty,
       and the `farmers` row now has `cached_plan` and `profile_hash` populated
- [ ] 24.3 `GET /api/plan` again immediately → confirm `from_cache: true`
- [ ] 24.4 `POST /api/profile` with a changed `plant_count` → confirm `cached_plan`
       column is now NULL in the database
- [ ] 24.5 `GET /api/plan` → confirm `from_cache: false` (fresh generation triggered)

**Files:** (verification only)
**Depends on:** Tasks 9, 10

---

### Task 25: Verify onboarding form fits 360 × 640 viewport
- [ ] 25.1 Open `onboarding.html` in browser DevTools mobile emulator at 360 × 640 px
- [ ] 25.2 Confirm all four fields and the submit button are fully visible without
       scrolling
- [ ] 25.3 Confirm all interactive elements are ≥ 44 px tall
- [ ] 25.4 Confirm `#district-select` is disabled until a state is selected
- [ ] 25.5 Confirm submitting with `plant_count = 0` shows inline error and makes no
       API call; confirm submitting with a future sowing date shows its inline error

**Files:** (verification only)
**Depends on:** Tasks 15, 16

---

### Task 26: Verify plan page error handling with no network
- [ ] 26.1 Open `plan.html` with DevTools network tab set to "Offline"
- [ ] 26.2 Confirm the loading spinner appears briefly then the friendly error message
       is shown — no stack trace, no raw HTTP status code visible to the user
- [ ] 26.3 Restore network; confirm refreshing the page loads the plan normally

**Files:** (verification only)
**Depends on:** Task 18

---

### Task 27: Write `README-farmer-feature.md`
- [ ] 27.1 Create at workspace root
- [ ] 27.2 Section 1 — Supabase setup: enable Google OAuth provider; add
       `https://guavaa.netlify.app` to redirect URLs; run `backend/schema.sql` in
       Supabase SQL Editor
- [ ] 27.3 Section 2 — Backend (Render): list required env vars; start command
       `uvicorn main:app --host 0.0.0.0 --port $PORT`; health-check URL; CORS origin
       to add
- [ ] 27.4 Section 3 — Frontend (Netlify): fill in `js/config.js` with real
       `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `API_BASE_URL`; commit and push to trigger
       deploy
- [ ] 27.5 Section 4 — Local development: run FastAPI locally; point `API_BASE_URL`
       in `config.js` to `http://localhost:8000`
- [ ] 27.6 Note that `js/config.js` contains only the public anon key and is safe to
       commit; the service key and JWT secret must stay in backend `.env` only

**Files:** `README-farmer-feature.md`
**Depends on:** Tasks 20–26

---

## Dependency Summary

```
Phase 1:  1 → 2, 3, 4, 6, 19
          3 → 5, 7
          5 → 7

Phase 2:  4 + 5 + 6 + 7 → 8
          4 + 6 + 8 → 9
          4 + 5 + 6 + 7 + 9 → 10

Phase 3:  (none) → 11, 13
          11 → 12

Phase 4:  11 + 12 → 14
          11 + 12 → 15
          12 + 13 + 15 → 16
          11 + 12 → 17
          12 + 17 → 18

Phase 6:  8 + 9 + 10 → 20 → 21
          9 + 10 + 16 → 22
          3 + 5 → 23
          9 + 10 → 24
          15 + 16 → 25
          18 → 26
          20–26 → 27
```
