# Farmer Login + Crop Care Plan — Setup Guide

This document explains how to deploy the farmer authentication and personalized
crop care plan feature that extends guavaa.netlify.app.

---

## 1. Supabase Setup

### 1.1 Create a Supabase project

Go to [supabase.com](https://supabase.com) and create a new project.

### 1.2 Run the database schema

In the Supabase dashboard → **SQL Editor**, paste and run the contents of
`backend/schema.sql`. This creates the `farmers` table, enables Row Level
Security, and sets up the `updated_at` trigger. The script is safe to re-run.

### 1.3 Enable Google OAuth

1. Go to **Authentication → Providers → Google**.
2. Toggle Google to **Enabled**.
3. Enter your Google Cloud OAuth 2.0 Client ID and Client Secret.
   (Create these at [console.cloud.google.com](https://console.cloud.google.com)
   under APIs & Services → Credentials.)
4. Add `https://guavaa.netlify.app` to **Redirect URLs**.
5. For local dev, also add `http://localhost:3000` (or whichever port you use).

### 1.4 Collect your Supabase keys

From **Project Settings → API** you need:
- **Project URL** — e.g. `https://abcdefgh.supabase.co`
- **anon / public key** — goes into `js/config.js` (safe to commit)
- **service_role key** — goes into `backend/.env` only (never commit)
- **JWT Secret** — from **Project Settings → API → JWT Settings** (never commit)

---

## 2. Backend (Render)

### 2.1 Create a new Web Service on Render

1. Go to [render.com](https://render.com) → **New → Web Service**.
2. Connect your GitHub repository.
3. Set **Root Directory** to `backend`.
4. Set **Runtime** to **Python 3.11**.
5. Set **Build Command**: `pip install -r requirements.txt`
6. Set **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### 2.2 Set environment variables on Render

In the Render dashboard → **Environment**, add these four variables:

| Key | Value |
|-----|-------|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_JWT_SECRET` | Your Supabase JWT Secret |
| `SUPABASE_SERVICE_KEY` | Your Supabase service_role key |
| `GEMINI_API_KEY` | Your Google Gemini API key |

### 2.3 Health check

Once deployed, confirm the service is running:

```
GET https://<your-render-app>.onrender.com/health
→ {"status": "ok"}
```

Render free tier spins down after inactivity. The first request after sleep
may take ~30 seconds (cold start). Subsequent requests are fast.

### 2.4 CORS

The backend already allows `https://guavaa.netlify.app`. If you use a custom
Netlify domain, add it to the `allow_origins` list in `backend/main.py`.

---

## 3. Frontend (Netlify)

### 3.1 Fill in `js/config.js`

Open `js/config.js` and replace the three placeholder values:

```js
export const SUPABASE_URL  = "https://your-project-ref.supabase.co";
export const SUPABASE_ANON_KEY = "your-supabase-anon-key";
export const API_BASE_URL  = "https://your-render-app.onrender.com";
```

`js/config.js` contains only the **public anon key** — it is safe to commit
to the repository. Never put the service key or JWT secret here.

### 3.2 Deploy

Commit and push to your repository. Netlify auto-deploys on push.

The three new pages are served as static files alongside `index.html`:
- `login.html` — sign-in entry point
- `onboarding.html` — first-time farmer form
- `plan.html` — care plan display

---

## 4. Local Development

### 4.1 Run the backend locally

```powershell
cd backend
cp .env.example .env        # then fill in your real keys
pip install -r requirements.txt
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.
Verify: `GET http://localhost:8000/health` → `{"status": "ok"}`

### 4.2 Point the frontend at your local backend

In `js/config.js`, temporarily change:

```js
export const API_BASE_URL = "http://localhost:8000";
```

Open `login.html` directly in your browser (or via a local static server).

### 4.3 Supabase OAuth redirect for local dev

In the Supabase dashboard, add `http://localhost:3000` (or `http://127.0.0.1:5500`
if using VS Code Live Server) to **Authentication → Redirect URLs**.

---

## 5. Key Security Notes

- `js/config.js` — contains **public anon key only**. Safe to commit.
- `backend/.env` — contains service key and JWT secret. **Never commit.**
  It is in `.gitignore` by default (add it if not).
- The backend extracts `user_id` exclusively from the verified JWT.
  It never accepts `user_id` as a client-supplied parameter.
- Row Level Security on the `farmers` table ensures each farmer can only
  read and write their own row, even if the service key is compromised.

---

## 6. File Map

```
Workspace root
├── login.html              ← Sign-in page
├── onboarding.html         ← First-time farmer form
├── plan.html               ← Care plan display
├── js/
│   ├── config.js           ← Public keys + API URL (edit before deploy)
│   ├── auth.js             ← Supabase client + route guard
│   ├── onboarding.js       ← Form logic + validation
│   ├── plan.js             ← Plan fetch + render
│   └── india-locations.js  ← Static LGD state/district data
└── backend/
    ├── main.py             ← FastAPI app + CORS
    ├── schema.sql          ← Run once in Supabase SQL Editor
    ├── .env.example        ← Copy to .env, fill in keys
    ├── requirements.txt    ← Pinned Python dependencies
    ├── routers/
    │   ├── profile.py      ← POST /api/profile
    │   └── plan.py         ← GET  /api/plan
    ├── services/
    │   ├── auth.py         ← JWT verification
    │   ├── stage.py        ← Growth stage lookup
    │   ├── planner.py      ← Gemini prompt + call
    │   └── cache.py        ← Profile hash
    └── data/
        └── crop_knowledge.json  ← Stage data (add new crops here)
```
