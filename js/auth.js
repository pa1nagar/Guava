/**
 * auth.js — Supabase client, session helpers, and route guard.
 *
 * Imported by every page. Handles OAuth callback automatically.
 * Supabase JS v2 detects the URL hash fragment after Google redirect
 * and exchanges it for a session — but this is async and can take
 * a moment. getSession() waits for this to complete.
 */

import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm";
import { SUPABASE_URL, SUPABASE_ANON_KEY, API_BASE_URL } from "./config.js";

// ── Supabase client (singleton) ───────────────────────────────────────────────
export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: {
    // Persist session in localStorage across page loads
    persistSession: true,
    // Automatically refresh the token before it expires
    autoRefreshToken: true,
    // Detect the session from the URL hash on OAuth callback
    detectSessionInUrl: true,
  },
});

// ── Session helpers ───────────────────────────────────────────────────────────

/**
 * Returns the active session, waiting for Supabase to finish processing
 * the OAuth URL hash if we just came back from Google.
 *
 * On OAuth callback pages, getSession() can return null on the first call
 * because Supabase hasn't finished exchanging the code/hash yet.
 * This function waits up to 3 seconds for the session to appear.
 */
export async function getSession() {
  // First try — fast path for already-authenticated users
  const { data: { session } } = await supabase.auth.getSession();
  if (session) return session;

  // If the URL has an access_token hash, Supabase is processing the OAuth
  // callback. Wait for the onAuthStateChange event to fire.
  if (window.location.hash.includes("access_token")) {
    return new Promise((resolve) => {
      const timeout = setTimeout(() => resolve(null), 5000);
      const { data: { subscription } } = supabase.auth.onAuthStateChange(
        (event, session) => {
          if (event === "SIGNED_IN" || event === "TOKEN_REFRESHED") {
            clearTimeout(timeout);
            subscription.unsubscribe();
            resolve(session);
          }
        }
      );
    });
  }

  return null;
}

/** Returns the JWT access token for the active session, or null. */
export async function getJwt() {
  const session = await getSession();
  return session?.access_token ?? null;
}

// ── Auth actions ──────────────────────────────────────────────────────────────

/** Initiates Google OAuth flow. Redirects back to /plan.html after sign-in. */
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
 * Call on DOMContentLoaded on every protected page.
 *
 * currentPage: 'login' | 'onboarding' | 'plan' | 'report'
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
        window.location.href = "plan.html";
      } else if (res.status === 404) {
        window.location.href = "onboarding.html";
      }
    } catch (_) {
      // Network failure — stay on login page
    }
  }
  // 'onboarding', 'plan', 'report' → always allow
}
