/**
 * plan.js — Care plan page logic.
 *
 * Responsibilities:
 *  - Route guard (redirect to login if no session)
 *  - Show loading indicator
 *  - GET /api/plan with JWT
 *  - Render stage badge, plan text, and farmer context
 *  - Handle 404 (redirect to onboarding) and errors (show friendly message)
 */

import { routeGuard, getJwt, supabase } from "./auth.js";
import { API_BASE_URL } from "./config.js";

// ── DOM refs ──────────────────────────────────────────────────────────────────
const loadingEl       = document.getElementById("plan-loading");
const contentEl       = document.getElementById("plan-content");
const stageBadgeEl    = document.getElementById("stage-badge");
const planTextEl      = document.getElementById("plan-text");
const errorEl         = document.getElementById("plan-error");
const farmerContextEl = document.getElementById("farmer-context");

// ── Helpers ───────────────────────────────────────────────────────────────────

function showLoading() {
  loadingEl.classList.remove("hidden");
  contentEl.classList.add("hidden");
  errorEl.classList.add("hidden");
}

function showContent() {
  loadingEl.classList.add("hidden");
  contentEl.classList.remove("hidden");
  errorEl.classList.add("hidden");
}

function showError(message) {
  loadingEl.classList.add("hidden");
  contentEl.classList.add("hidden");
  errorEl.textContent = message;
  errorEl.classList.remove("hidden");
}

function renderPlan(data) {
  // Stage badge: "🌱 Vegetative Growth — Month 5"
  stageBadgeEl.textContent = `🌱 ${data.stage_label} — Month ${data.months_elapsed}`;

  // Plan text: split on newlines, wrap each non-empty line in a <p>
  planTextEl.innerHTML = "";
  const lines = data.plan_text.split("\n").filter(l => l.trim().length > 0);
  for (const line of lines) {
    const p = document.createElement("p");
    p.textContent = line.trim();
    planTextEl.appendChild(p);
  }
}

// ── Main ──────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
  // Guard: redirect to login if no session.
  await routeGuard("plan");

  showLoading();

  // Get JWT for API call.
  const jwt = await getJwt();
  if (!jwt) {
    // routeGuard should have redirected, but handle defensively.
    window.location.href = "login.html";
    return;
  }

  // Populate farmer context from session metadata while plan loads.
  try {
    const { data: { session } } = await supabase.auth.getSession();
    if (session?.user?.user_metadata?.full_name) {
      farmerContextEl.textContent = session.user.user_metadata.full_name;
    }
  } catch (_) { /* non-critical */ }

  // Fetch plan from backend.
  try {
    const res = await fetch(`${API_BASE_URL}/api/plan`, {
      headers: { Authorization: `Bearer ${jwt}` },
    });

    if (res.status === 404) {
      // No profile yet — send to onboarding.
      window.location.href = "onboarding.html";
      return;
    }

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }

    const data = await res.json();

    // Render plan.
    renderPlan(data);

    // Update farmer context with plant count from response.
    // (The API response includes stage_label and months_elapsed;
    //  we use what we have — plant count comes from the profile,
    //  not the plan response. Show stage info in the context bar.)
    farmerContextEl.textContent =
      farmerContextEl.textContent
        ? farmerContextEl.textContent
        : `Month ${data.months_elapsed} · ${data.stage_label}`;

    showContent();

  } catch (err) {
    // Network failure or unexpected error.
    showError(
      "Plan not available right now. Please check your connection and try again."
    );
  }
});
