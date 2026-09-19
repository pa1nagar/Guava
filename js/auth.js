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
 *
 * Redirects back to the site root after sign-in. Supabase JS handles the URL
 * hash fragment and establishes the session automatically. The root redirect
 * is safer than hard-coding /plan.html because it works even if the URL
 * structure changes, and Supabase only needs one redirect URL configured.
 *
 * After the session is established, routeGuard() on the landing page decides
 * where to send the user based on whether they have a profile.
 */
export async function signInWithGoogle() {
  const { error } = await supabase.auth.signInWithOAuth({
    provider: "google",
    options: {
      // Redirect to root; the page's routeGuard will handle onward routing.
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
 * Call on DOMContentLoaded on every protected page.
 *
 * currentPage: 'login' | 'onboarding' | 'plan' | 'report'
 *
 * Logic:
 *   No session  + not on login  → redirect to login.html
 *   Session     + on login      → check profile; redirect accordingly
 *   Session     + on onboarding → allow (farmer may be updating details)
 *   Session     + on plan/report → do nothing (stay; page fetches own data)
 *
 * Profile check uses GET /api/farmers/me (lightweight — no Gemini call).
 */
export async function routeGuard(currentPage) {
  const session = await getSession();

  if (!session) {
    if (currentPage !== "login") {
      window.location.href = "login.html";
    }
    return;
  }

  // Signed in on the login page → decide where to send the farmer.
  if (currentPage === "login") {
    const jwt = session.access_token;
    try {
      const res = await fetch(`${API_BASE_URL}/api/farmers/me`, {
        headers: { Authorization: `Bearer ${jwt}` },
      });
      if (res.ok) {
        // Profile exists — go straight to the dashboard.
        window.location.href = "plan.html";
      } else if (res.status === 404) {
        // New farmer — needs to complete onboarding first.
        window.location.href = "onboarding.html";
      }
      // Any other error (5xx, network) — stay on login page silently.
    } catch (_) {
      // Network failure during guard check — do nothing (leave farmer on login).
    }
  }
  // 'onboarding' → always allow (farmer may be updating details deliberately)
  // 'plan', 'report' → always allow; the page's own data fetch handles 404
}
