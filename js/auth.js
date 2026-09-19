/**
 * auth.js — Supabase client, session helpers, and route guard.
 *
 * Imported by every page. Handles OAuth callback automatically
 * (Supabase JS detects the URL hash after Google redirect).
 */

import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm";
import { SUPABASE_URL, SUPABASE_ANON_KEY, API_BASE_URL } from "./config.js";

// ── Supabase client (singleton) ───────────────────────────────────────────────
export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// ── Session helpers ───────────────────────────────────────────────────────────

/** Returns the active Supabase session, or null if not signed in. */
export async function getSession() {
  const { data: { session } } = await supabase.auth.getSession();
  return session;
}

/** Returns the JWT access token for the active session, or null. */
export async function getJwt() {
  const session = await getSession();
  return session?.access_token ?? null;
}

// ── Auth actions ──────────────────────────────────────────────────────────────

/**
 * Initiates Google OAuth flow.
 * After sign-in Google redirects back to /plan.html — Supabase JS handles
 * the URL hash and establishes the session automatically.
 */
export async function signInWithGoogle() {
  const { error } = await supabase.auth.signInWithOAuth({
    provider: "google",
    options: {
      redirectTo: window.location.origin + "/plan.html",
    },
  });
  if (error) throw error;
}

/** Signs out and redirects to login.html. */
export async function signOut() {
  await supabase.auth.signOut();
  window.location.href = "login.html";
}

// ── Route guard ───────────────────────────────────────────────────────────────

/**
 * Call on DOMContentLoaded on every page.
 *
 * currentPage: 'login' | 'onboarding' | 'plan'
 *
 * Logic:
 *   No session  + not on login  → redirect to login.html
 *   Session     + on login      → check profile; redirect accordingly
 *   Session     + on onboarding → check profile; redirect to plan if exists
 *   Session     + on plan       → do nothing (stay)
 */
export async function routeGuard(currentPage) {
  const session = await getSession();

  if (!session) {
    if (currentPage !== "login") {
      window.location.href = "login.html";
    }
    return;
  }

  // Signed in — check whether a profile row exists.
  if (currentPage === "login") {
    // Only auto-redirect from login, not from onboarding
    // (farmer may have clicked "Update my details" deliberately).
    const jwt = session.access_token;
    try {
      const res = await fetch(`${API_BASE_URL}/api/plan`, {
        headers: { Authorization: `Bearer ${jwt}` },
      });
      if (res.ok) {
        window.location.href = "plan.html";
      } else if (res.status === 404) {
        window.location.href = "onboarding.html";
      }
    } catch (_) {
      // Network failure during guard check — do nothing.
    }
  }
  // currentPage === 'onboarding' — always allow (farmer may be updating details)
  // currentPage === 'plan' with a valid session — do nothing
}
