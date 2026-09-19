# Requirements — Farmer Login + Personalized Crop Care Plan

## Introduction

This feature extends the existing static Guava dashboard at guavaa.netlify.app with farmer
authentication and a personalized, AI-generated weekly care plan. A farmer signs in once with
Google, fills in a single onboarding form, and receives a plain-language care plan matched to
their actual growth stage. Returning farmers skip the form and land directly on their saved plan.

The primary users are Indian smallholder farmers using basic Android phones on patchy mobile data.
Every screen must minimize taps and text, use no jargon, and fit on one phone screen without
scrolling.

---

## Glossary

- **Farmer**: The authenticated end-user of this feature.
- **Onboarding_Form**: The single-page form a first-time farmer completes after signing in.
- **Care_Plan**: The AI-generated plain-language output showing growth stage and this week's tasks.
- **Growth_Stage**: A named phase of guava cultivation derived from the number of months elapsed
  since sowing_date.
- **Crop_Knowledge**: Stage-based structured JSON data used as the grounding reference for plan
  generation. Never hardcoded prose — always loaded from a data file so new crops can be added
  without code changes.
- **Supabase**: The hosted Postgres + Auth platform used for user data and Google OAuth.
- **FastAPI_Backend**: The Python API hosted on Render free tier that computes growth stage, calls
  Gemini, caches the plan, and returns it to the frontend.
- **Gemini**: Google Gemini Flash, the LLM used for plan generation. It receives only structured
  reference data — it must not invent information not present in Crop_Knowledge.
- **Plan_Cache**: A column on the `farmers` table that stores the last generated plan so it is not
  regenerated on every page load.

---

## Requirements

### Requirement 1: Google Sign-In Entry Point

**User Story:** As a farmer opening the site, I want a single "Sign in with Google" button so I
can log in without creating a separate account or remembering a password.

#### Acceptance Criteria

1. THE site SHALL display a single "Sign in with Google" button as the first thing a
   visitor sees, above any dashboard content.
2. THE button SHALL use Supabase Auth with the Google OAuth provider. No email/password
   field and no OTP flow SHALL be present.
3. WHEN the farmer taps "Sign in with Google", THE browser SHALL redirect through Google's
   OAuth consent screen and back to the site.
4. AFTER a successful OAuth callback, THE site SHALL detect whether the authenticated user
   already has a record in the `farmers` table.
5. IF a record exists, THE site SHALL route the farmer directly to their saved Care_Plan
   (Requirement 4) — the Onboarding_Form SHALL NOT be shown.
6. IF no record exists, THE site SHALL route the farmer to the Onboarding_Form
   (Requirement 2).
7. THE Google sign-in button SHALL be visually prominent, tappable on a small phone screen
   (minimum 48 × 48 px touch target), and require no other action to proceed.

---

### Requirement 2: Onboarding Form

**User Story:** As a first-time farmer, I want to fill in a single form — crop, number of plants,
location, and planting date — so the app can build a plan specific to my farm.

#### Acceptance Criteria

1. THE Onboarding_Form SHALL be a single page (no multi-step wizard, no pagination).
2. THE Onboarding_Form SHALL contain exactly these four fields in order:
   - Crop — a `<select>` dropdown; the only selectable option for this release is "Guava".
   - Number of plants — a `<input type="number">` accepting positive integers only.
   - State — a `<select>` dropdown listing all Indian states and union territories.
   - District — a `<select>` dropdown filtered to show only districts belonging to the
     selected State. The District dropdown SHALL be disabled until a State is chosen.
   - Date trees were planted — a `<input type="date">` defaulting to today's date.
3. THE Onboarding_Form SHALL have a single submit button labelled "Get my plan".
4. THE form SHALL validate that number of plants is a positive integer greater than zero
   before submission; if not, it SHALL show a brief inline error message in plain language.
5. THE form SHALL validate that the date trees were planted is not in the future. IF the
   selected sowing_date is after today's date, THE form SHALL reject submission and show an
   inline error: "Planting date cannot be in the future." The submit button SHALL NOT call
   the API until this is resolved.
6. THE entire form — all four fields and the submit button — SHALL be visible on a 360 × 640
   pixel viewport without vertical scrolling.
7. WHEN the farmer taps "Get my plan", THE frontend SHALL POST the form data to the FastAPI
   backend.
8. AFTER a successful submission, THE frontend SHALL display the Care_Plan returned by the
   backend (Requirement 3).
9. WHILE the plan is being generated, THE frontend SHALL show a simple loading indicator so
   the farmer knows the app is working.

---

### Requirement 3: Care Plan Display

**User Story:** As a farmer who just submitted the form, I want to see a plain-language care plan
for this week so I know exactly what to do without needing to read technical jargon.

#### Acceptance Criteria

1. THE Care_Plan SHALL display at minimum:
   - The current growth stage name (e.g. "Vegetative Growth — Month 3").
   - A brief one-line description of what is happening to the crop right now.
   - What to do this week: irrigation guidance, fertigation guidance, and pest-check
     guidance — each as a short, jargon-free sentence.
2. THE Care_Plan SHALL be generated by Gemini Flash using only the data retrieved from
   Crop_Knowledge for the matched growth stage. Gemini SHALL NOT invent advice not present
   in Crop_Knowledge.
3. THE FastAPI_Backend SHALL include an explicit system instruction in the Gemini prompt
   instructing it to use only the provided reference data and to invent nothing.
4. THE Care_Plan output SHALL be in plain language suitable for a farmer with low formal
   literacy — short sentences, no Latin names, no chemical formulas in the displayed text.
5. THE Care_Plan SHALL display the farmer's plant count and the matched growth stage name
   so the farmer can confirm the plan is for their farm.
6. WHEN fertigation quantities are shown, THE backend SHALL scale them by the farmer's
   plant_count before passing them to Gemini.
7. THE Care_Plan page SHALL include a small "Update my details" link that allows a farmer
   to re-submit the Onboarding_Form if their details change.

---

### Requirement 4: Returning Farmer Plan Access

**User Story:** As a farmer who has already set up my account, I want to see my plan immediately
when I sign in — without filling in the form again.

#### Acceptance Criteria

1. WHEN an authenticated farmer who has an existing record in the `farmers` table opens the
   site, THE Care_Plan SHALL be displayed without showing the Onboarding_Form.
2. THE displayed plan SHALL be the cached plan stored in the `farmers` table unless the
   farmer's profile has changed since the plan was last generated.
3. IF the farmer's profile has NOT changed since the last plan generation, THE backend SHALL
   return the cached plan without calling Gemini.
4. IF the farmer updates their details via the "Update my details" link, THE backend SHALL
   regenerate the plan and update the cache.
5. THE returning farmer experience SHALL require at most one tap (the Google Sign-In button)
   to reach their plan.

---

### Requirement 5: Backend — Growth Stage Computation

**User Story:** As the system, I need to correctly derive the farmer's current growth stage from
their sowing date so the plan reflects where their trees actually are today, not where they were
at planting.

#### Acceptance Criteria

1. THE FastAPI_Backend SHALL compute months_elapsed as the integer number of complete months
   between sowing_date and today's date (UTC).
2. THE backend SHALL map months_elapsed to a Growth_Stage using the stage boundaries defined
   in Crop_Knowledge — not hardcoded in application logic.
3. IF months_elapsed exceeds the highest defined stage, THE backend SHALL use the final
   (mature) stage.
4. THE computed Growth_Stage SHALL be included in the response returned to the frontend.
5. WHEN a farmer with sowing_date 5 months before today's date requests a plan, THE backend
   SHALL return a plan for the growth stage matching month 5, not month 0 or month 1.
6. IF sowing_date received by the backend is after today's date (UTC), THE backend SHALL
   reject the request with HTTP 422 and the message "Planting date cannot be in the
   future." This check applies regardless of whether the request arrives via the form or
   a direct API call.

---

### Requirement 6: Backend — Plan Caching

**User Story:** As the system, I need to avoid calling Gemini on every page load to control costs
and keep response times low for farmers on slow connections.

#### Acceptance Criteria

1. THE FastAPI_Backend SHALL store the generated plan text in a `cached_plan` column on the
   `farmers` table after each successful generation.
2. THE backend SHALL also store a `plan_generated_at` timestamp and a `profile_hash` (a
   deterministic hash of crop + plant_count + state + district + sowing_date) in the
   `farmers` table.
3. ON each plan request, THE backend SHALL recompute the profile_hash and compare it to the
   stored value. IF they match, the cached plan SHALL be returned without calling Gemini.
4. IF the profile_hash differs (because the farmer updated their details), THE backend SHALL
   regenerate the plan, update `cached_plan`, `plan_generated_at`, and `profile_hash`.
5. THE backend SHALL never store raw API keys in the `farmers` table or any user-visible
   response.

---

### Requirement 7: Database Schema

**User Story:** As a developer, I need a clear Postgres schema so the backend and Supabase are
set up consistently.

#### Acceptance Criteria

1. THE Supabase Postgres database SHALL contain a `farmers` table with these columns:
   - `id` — UUID primary key, default `gen_random_uuid()`.
   - `user_id` — UUID, NOT NULL, references `auth.users(id)`, UNIQUE.
   - `crop` — TEXT NOT NULL.
   - `plant_count` — INTEGER NOT NULL, CHECK > 0.
   - `state` — TEXT NOT NULL.
   - `district` — TEXT NOT NULL.
   - `sowing_date` — DATE NOT NULL.
   - `cached_plan` — TEXT, nullable (null until first generation).
   - `profile_hash` — TEXT, nullable.
   - `plan_generated_at` — TIMESTAMPTZ, nullable.
   - `created_at` — TIMESTAMPTZ NOT NULL DEFAULT now().
   - `updated_at` — TIMESTAMPTZ NOT NULL DEFAULT now().
2. ROW LEVEL SECURITY SHALL be enabled on the `farmers` table. A farmer SHALL only be able
   to read or write their own row (WHERE user_id = auth.uid()).
3. THE `updated_at` column SHALL be automatically updated via a Postgres trigger on every
   UPDATE to the `farmers` table.

---

### Requirement 8: Crop Knowledge Data Structure

**User Story:** As a developer, I want crop data stored as structured JSON (not prose) so new
crops can be added later without touching application code.

#### Acceptance Criteria

1. CROP_KNOWLEDGE SHALL be stored as a JSON file (or dict) in the backend codebase keyed
   first by crop name (e.g. `"guava"`) then by stage index or stage id.
2. EACH stage entry SHALL contain at minimum: `stage_id`, `label`, `month_start`,
   `month_end`, `description`, `irrigation` (text guidance), `fertigation` (text guidance
   with per-plant quantities), `pest_checks` (text guidance).
3. THE stage boundaries (month_start, month_end) SHALL be the sole source of truth for
   growth stage mapping — they SHALL NOT be duplicated in application logic.
4. ONLY Guava data SHALL exist in this release. The structure SHALL support adding a second
   crop (e.g. Mango) by inserting a new top-level key with identically shaped stage objects,
   without modifying any Python functions.
5. THE Crop_Knowledge file SHALL carry a comment stating "Do not add prose advice here — all
   text is passed verbatim to Gemini as reference data."

---

### Requirement 9: State and District Reference Data

**User Story:** As a developer, I need a complete, sourced list of Indian states and districts
so the onboarding form's location dropdowns are accurate and don't need a network call.

#### Acceptance Criteria

1. THE frontend SHALL ship a static `js/india-locations.js` module containing all 28 states
   and 8 union territories (36 total) and their current districts, sourced from the Ministry
   of Panchayati Raj's Local Government Directory (LGD) — the continuously-updated
   government registry of administrative boundaries. The 2011 Census SHALL NOT be used as
   the data source because it pre-dates Telangana's creation (2014), the J&K/Ladakh split
   (2019), and ~150 districts created through administrative reorganisation since 2011.
2. THE data SHALL be embedded directly in the JS module as a plain object — no external API
   call, no CDN dependency, no runtime fetch. The LGD is the source for building the static
   dataset; the app never calls the LGD API at runtime.
3. THE district list for each state SHALL be complete and sorted alphabetically. The 10 major
   guava-producing states (Uttar Pradesh, Madhya Pradesh, Bihar, Maharashtra, Karnataka,
   Andhra Pradesh, Telangana, Gujarat, Rajasthan, West Bengal) SHALL have full district
   coverage. Telangana's districts SHALL reflect the post-2014 state boundaries, not any
   pre-bifurcation Andhra Pradesh list.
4. THE module SHALL export exactly two functions: `getStates()` returning a sorted array of
   state/UT names, and `getDistricts(state)` returning a sorted array of district names for
   that state (empty array if state not found).
5. THE source of the data SHALL be noted in a comment at the top of the file:
   "District data sourced from Ministry of Panchayati Raj Local Government Directory (LGD),
   lgdirectory.nic.in — current as of build date."

---

### Requirement 10: Security & Privacy

**User Story:** As a farmer, I want my data kept private and the system to be secure so my farm
information cannot be read by other users.

#### Acceptance Criteria

1. ALL API endpoints on the FastAPI_Backend SHALL require a valid Supabase JWT in the
   `Authorization: Bearer <token>` header. Requests without a valid token SHALL receive
   HTTP 401.
2. THE backend SHALL verify the JWT using the Supabase JWT secret before processing any
   request.
3. THE backend SHALL only read or write `farmers` rows for the `user_id` extracted from the
   verified JWT — it SHALL NOT accept user_id as a client-supplied parameter.
4. THE Gemini API key, Supabase service-role key, and Supabase JWT secret SHALL be stored as
   environment variables and SHALL never be committed to the repository.
5. THE `cached_plan` text stored in the database SHALL NOT include any PII beyond what the
   farmer themselves provided (crop, plant count, state, district, sowing date).

---

### Requirement 11: Performance & Offline Constraints

**User Story:** As a farmer on a 2G/3G connection, I want the app to load quickly and behave
gracefully when the network is slow.

#### Acceptance Criteria

1. THE frontend HTML, CSS, and JS for the login and onboarding screens SHALL be served as
   static files from Netlify — no server-side rendering.
2. IF the backend returns an error or times out, THE frontend SHALL display a brief, friendly
   error message in plain language (not a stack trace or HTTP status code).
3. THE login and onboarding pages SHALL NOT load Chart.js, the existing dashboard JS, or any
   other asset not required for those screens — each screen loads only its own minimal
   dependencies.
4. THE FastAPI_Backend on Render free tier SHALL respond to plan requests within 10 seconds
   on a cached plan and within 30 seconds on a fresh Gemini generation.
