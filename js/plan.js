/**
 * plan.js — Care plan page logic.
 *
 * Responsibilities:
 *  - Route guard
 *  - Load plan, spending, gaps, vendor recommendations in parallel
 *  - Render structured plan tasks
 *  - Activity logging form with pre-fill from current plan
 *  - Spending summary
 *  - Expected-vs-actual gap alerts
 *  - Harvest/sale form (shown only at final stage)
 *  - Vendor recommendations (consent-gated)
 *  - Toast notifications
 */

import { routeGuard, getJwt, signOut, supabase } from "./auth.js";
import { API_BASE_URL } from "./config.js";

// ── DOM refs ──────────────────────────────────────────────────────────────────
const loadingEl       = document.getElementById("plan-loading");
const contentEl       = document.getElementById("plan-content");
const errorEl         = document.getElementById("plan-error");
const stageBadgeEl    = document.getElementById("stage-badge");
const daysSinceEl     = document.getElementById("days-since");
const planSummaryEl   = document.getElementById("plan-summary");
const taskListEl      = document.getElementById("task-list");
const gapAlertsEl     = document.getElementById("gap-alerts");
const spentAmountEl   = document.getElementById("spent-amount");
const logForm         = document.getElementById("log-form");
const actTypeEl       = document.getElementById("act-type");
const actQtyEl        = document.getElementById("act-qty");
const actUnitEl       = document.getElementById("act-unit");
const actCostEl       = document.getElementById("act-cost");
const qtyHintEl       = document.getElementById("qty-hint");
const logErrorEl      = document.getElementById("log-error");
const btnLog          = document.getElementById("btn-log");
const harvestSection  = document.getElementById("harvest-section");
const harvestDoneMsg  = document.getElementById("harvest-done-msg");
const harvestForm     = document.getElementById("harvest-form");
const hvQtyEl         = document.getElementById("hv-qty");
const hvPriceEl       = document.getElementById("hv-price");
const hvErrorEl       = document.getElementById("hv-error");
const btnHarvest      = document.getElementById("btn-harvest");
const vendorSection   = document.getElementById("vendor-section");
const vendorListEl    = document.getElementById("vendor-list");
const vendorOptinEl   = document.getElementById("vendor-optin");
const btnGiveConsent  = document.getElementById("btn-give-consent");
const btnRevokeConsent= document.getElementById("btn-revoke-consent");
const toastEl         = document.getElementById("toast");
const btnSignout      = document.getElementById("btn-signout");

// ── Module state ──────────────────────────────────────────────────────────────
let _currentPlan = null;   // last PlanOut response
let _hasBehindGap = false; // whether any gap is "behind"

// ── Utilities ─────────────────────────────────────────────────────────────────

function fmt(n) {
  if (n == null) return "—";
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

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

function showError(msg) {
  loadingEl.classList.add("hidden");
  contentEl.classList.add("hidden");
  errorEl.textContent = msg;
  errorEl.classList.remove("hidden");
}

let _toastTimer = null;
function showToast(msg, durationMs = 2500) {
  toastEl.textContent = msg;
  toastEl.style.opacity = "1";
  toastEl.classList.remove("pointer-events-none");
  if (_toastTimer) clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => {
    toastEl.style.opacity = "0";
    toastEl.classList.add("pointer-events-none");
  }, durationMs);
}

async function apiFetch(path, opts = {}) {
  const jwt = await getJwt();
  return fetch(`${API_BASE_URL}${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${jwt}`,
      ...(opts.headers || {}),
    },
  });
}

// ── Renderers ─────────────────────────────────────────────────────────────────

const CATEGORY_DOT = {
  fertilizer: "dot-fertilizer",
  irrigation:  "dot-irrigation",
  ipm:         "dot-ipm",
  activity:    "dot-activity",
};

const CATEGORY_LABEL = {
  fertilizer: "Fertilizer",
  irrigation:  "Irrigation",
  ipm:         "Pest & Disease",
  activity:    "Activity",
};

function renderPlan(plan) {
  _currentPlan = plan;

  // Stage badge
  stageBadgeEl.textContent = `🌱 ${plan.stage_label} — Month ${plan.months_elapsed}`;
  daysSinceEl.textContent = `${plan.days_elapsed} days since planting`;

  // Summary
  planSummaryEl.textContent = plan.summary || "";

  // Tasks
  taskListEl.innerHTML = "";
  for (const task of (plan.tasks || [])) {
    const dotClass = CATEGORY_DOT[task.category] || "dot-activity";
    const catLabel = CATEGORY_LABEL[task.category] || task.category;

    let qtyLine = "";
    if (task.quantity != null) {
      qtyLine = `<span class="font-semibold text-brand-dark">${task.quantity} ${task.unit || ""}</span>`;
    }

    const card = document.createElement("div");
    card.className = "bg-white rounded-xl border border-gray-200 px-4 py-3 flex flex-col gap-1";
    card.innerHTML = `
      <div class="flex items-center gap-2">
        <span class="w-2 h-2 rounded-full flex-shrink-0 ${dotClass}"></span>
        <span class="text-xs font-semibold text-gray-400 uppercase tracking-wide">${catLabel}</span>
      </div>
      <p class="text-sm font-medium text-brand-dark">${task.title}</p>
      ${qtyLine ? `<p class="text-sm text-gray-500">${qtyLine}</p>` : ""}
      <p class="text-sm text-gray-600 leading-relaxed">${task.description}</p>
    `;
    taskListEl.appendChild(card);
  }

  // Notes
  for (const note of (plan.notes || [])) {
    const el = document.createElement("p");
    el.className = "text-xs text-gray-400 italic";
    el.textContent = note;
    taskListEl.appendChild(el);
  }

  // Pre-fill activity type based on first fertilizer task
  const fertTask = plan.tasks?.find(t => t.category === "fertilizer");
  if (fertTask) {
    setActType("Fertilizer");
    if (fertTask.quantity != null) {
      actQtyEl.value = fertTask.quantity;
      actUnitEl.value = fertTask.unit?.includes("kg") ? "kg" : "kg";
      qtyHintEl.textContent = `— reference: ${fertTask.quantity} ${fertTask.unit || ""}`;
    }
  }

  // Show harvest section if at final stage
  if (plan.is_final_stage) {
    harvestSection.classList.remove("hidden");
  }
}

function renderGaps(gaps) {
  gapAlertsEl.innerHTML = "";
  _hasBehindGap = false;

  const behind = gaps.filter(g => g.status === "behind");
  if (behind.length === 0) {
    gapAlertsEl.classList.add("hidden");
    return;
  }

  _hasBehindGap = true;
  gapAlertsEl.classList.remove("hidden");

  for (const g of behind) {
    const el = document.createElement("div");
    el.className =
      "flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3";
    el.innerHTML = `
      <span class="text-amber-500 text-lg flex-shrink-0">⚠</span>
      <div>
        <p class="text-sm text-amber-800">${g.message || `You may be behind on ${g.activity_type.toLowerCase()} for this stage.`}</p>
        <p class="text-xs text-amber-600 mt-0.5">Expected ${g.expected} ${g.unit} · Logged ${g.actual} ${g.unit}</p>
      </div>
    `;
    gapAlertsEl.appendChild(el);
  }
}

function renderSpending(data) {
  spentAmountEl.textContent = fmt(data.total_cost);
}

function renderVendors(cards) {
  vendorListEl.innerHTML = "";
  if (!cards || cards.length === 0) {
    vendorSection.classList.add("hidden");
    return;
  }
  vendorSection.classList.remove("hidden");
  for (const c of cards) {
    const hasWA = c.contact_method === "whatsapp" || c.contact_method === "both";
    const hasCall = c.contact_method === "call" || c.contact_method === "both";

    const card = document.createElement("div");
    card.className = "bg-white rounded-xl border border-gray-200 px-4 py-3 flex flex-col gap-2";
    card.innerHTML = `
      <p class="text-sm font-semibold text-brand-dark">${c.vendor_name}</p>
      <p class="text-xs text-gray-500">${c.district}</p>
      <p class="text-xs text-gray-500">For: <span class="font-medium">${c.input_needed}</span> — ${c.quantity_needed} ${c.unit} needed</p>
      <div class="flex gap-2 mt-1">
        ${hasCall ? `<a href="tel:${c.phone}" class="flex-1 min-h-[40px] flex items-center justify-center bg-brand-primary text-white text-sm font-medium rounded-lg">📞 Call</a>` : ""}
        ${hasWA ? `<a href="https://wa.me/${c.phone.replace(/\D/g,'')}" target="_blank" rel="noopener" class="flex-1 min-h-[40px] flex items-center justify-center bg-green-600 text-white text-sm font-medium rounded-lg">💬 WhatsApp</a>` : ""}
      </div>
    `;
    vendorListEl.appendChild(card);
  }
}

// ── Form helpers ──────────────────────────────────────────────────────────────

function setActType(value) {
  for (const opt of actTypeEl.options) {
    if (opt.value === value) { opt.selected = true; break; }
  }
  updateUnitForType(value);
}

function updateUnitForType(type) {
  if (type === "Fertilizer") {
    actUnitEl.value = "kg";
  } else if (type === "Irrigation") {
    actUnitEl.value = "litres";
  } else if (type === "Labour") {
    actUnitEl.value = "hours";
  }
}

// ── Activity types bootstrap ──────────────────────────────────────────────────

async function loadActivityTypes() {
  try {
    const res = await apiFetch("/api/constants/activity-types");
    if (!res.ok) throw new Error();
    const data = await res.json();
    actTypeEl.innerHTML = "";
    for (const t of data.activity_types) {
      const opt = document.createElement("option");
      opt.value = t;
      opt.textContent = t;
      actTypeEl.appendChild(opt);
    }
  } catch {
    // Fallback if endpoint fails.
    const fallback = ["Fertilizer", "Irrigation", "Pesticide", "Labour", "Other"];
    actTypeEl.innerHTML = fallback.map(t => `<option>${t}</option>`).join("");
  }
  actTypeEl.addEventListener("change", () => updateUnitForType(actTypeEl.value));
}

// ── Activity log form ─────────────────────────────────────────────────────────

logForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  logErrorEl.classList.add("hidden");

  const qty = parseFloat(actQtyEl.value);
  const cost = parseFloat(actCostEl.value);

  if (isNaN(qty) || qty < 0) {
    logErrorEl.textContent = "Quantity must be 0 or more.";
    logErrorEl.classList.remove("hidden");
    return;
  }
  if (isNaN(cost) || cost < 0) {
    logErrorEl.textContent = "Cost must be 0 or more.";
    logErrorEl.classList.remove("hidden");
    return;
  }

  btnLog.disabled = true;
  btnLog.textContent = "Saving…";

  try {
    const res = await apiFetch("/api/farmers/me/activities", {
      method: "POST",
      body: JSON.stringify({
        activity_type: actTypeEl.value,
        quantity: qty,
        unit: actUnitEl.value,
        cost: cost,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    // Reset form.
    actQtyEl.value = "";
    actCostEl.value = "";

    showToast("✓ Saved");

    // Refresh spending and gaps without a full page reload.
    await Promise.all([refreshSpending(), refreshGaps(), refreshVendors()]);

  } catch (err) {
    logErrorEl.textContent = err.message || "Could not save. Please try again.";
    logErrorEl.classList.remove("hidden");
  } finally {
    btnLog.disabled = false;
    btnLog.textContent = "Save";
  }
});

// ── Harvest form ──────────────────────────────────────────────────────────────

harvestForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  hvErrorEl.classList.add("hidden");

  const qty = parseFloat(hvQtyEl.value);
  const price = parseFloat(hvPriceEl.value);

  if (isNaN(qty) || qty <= 0) {
    hvErrorEl.textContent = "Quantity sold must be greater than 0.";
    hvErrorEl.classList.remove("hidden");
    return;
  }
  if (isNaN(price) || price < 0) {
    hvErrorEl.textContent = "Price must be 0 or more.";
    hvErrorEl.classList.remove("hidden");
    return;
  }

  btnHarvest.disabled = true;
  btnHarvest.textContent = "Saving…";

  try {
    const res = await apiFetch("/api/farmers/me/harvest", {
      method: "POST",
      body: JSON.stringify({
        sale_quantity_kg: qty,
        sale_price_per_kg: price,
      }),
    });

    if (res.status === 409) {
      // Already submitted.
      harvestForm.classList.add("hidden");
      harvestDoneMsg.textContent = "Harvest already recorded. View your report for the full financial summary.";
      harvestDoneMsg.classList.remove("hidden");
      return;
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    harvestForm.classList.add("hidden");
    harvestDoneMsg.textContent =
      `Harvest recorded — ${data.sale_quantity_kg} kg at ₹${data.sale_price_per_kg}/kg. Revenue: ₹${data.revenue.toLocaleString("en-IN")}. See your full report.`;
    harvestDoneMsg.classList.remove("hidden");
    showToast("✓ Harvest recorded");

  } catch (err) {
    hvErrorEl.textContent = err.message || "Could not save. Please try again.";
    hvErrorEl.classList.remove("hidden");
  } finally {
    btnHarvest.disabled = false;
    btnHarvest.textContent = "Record harvest & sale";
  }
});

// ── Vendor consent ────────────────────────────────────────────────────────────

btnGiveConsent?.addEventListener("click", async () => {
  try {
    const res = await apiFetch("/api/farmers/me/vendor-consent", {
      method: "PUT",
      body: JSON.stringify({ consent: true }),
    });
    if (!res.ok) throw new Error();
    vendorOptinEl.classList.add("hidden");
    await refreshVendors();
  } catch {
    showToast("Could not update preference. Try again.");
  }
});

btnRevokeConsent?.addEventListener("click", async () => {
  try {
    const res = await apiFetch("/api/farmers/me/vendor-consent", {
      method: "PUT",
      body: JSON.stringify({ consent: false }),
    });
    if (!res.ok) throw new Error();
    vendorSection.classList.add("hidden");
    showToast("Vendor suggestions turned off.");
  } catch {
    showToast("Could not update preference. Try again.");
  }
});

btnSignout?.addEventListener("click", () => signOut());

// ── Refresh helpers ───────────────────────────────────────────────────────────

async function refreshSpending() {
  try {
    const res = await apiFetch("/api/farmers/me/spending");
    if (!res.ok) return;
    const data = await res.json();
    renderSpending(data);
  } catch { /* non-critical */ }
}

async function refreshGaps() {
  try {
    const res = await apiFetch("/api/farmers/me/gaps");
    if (!res.ok) return;
    const gaps = await res.json();
    renderGaps(gaps);
  } catch { /* non-critical */ }
}

async function refreshVendors() {
  try {
    const res = await apiFetch("/api/farmers/me/vendor-recommendations");
    if (!res.ok) return;
    const cards = await res.json();
    renderVendors(cards);

    // Show opt-in prompt if there are behind gaps but no consent yet.
    if (_hasBehindGap && cards.length === 0) {
      // Check profile for consent status.
      const profRes = await apiFetch("/api/farmers/me");
      if (profRes.ok) {
        const prof = await profRes.json();
        if (!prof.vendor_recommendation_consent) {
          vendorOptinEl.classList.remove("hidden");
        }
      }
    }
  } catch { /* non-critical */ }
}

// ── Main ──────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
  await routeGuard("plan");
  showLoading();

  const jwt = await getJwt();
  if (!jwt) { window.location.href = "login.html"; return; }

  // Load activity types into the dropdown.
  await loadActivityTypes();

  // Fetch plan, spending, and gaps in parallel.
  try {
    const [planRes, spendRes, gapsRes] = await Promise.all([
      apiFetch("/api/plan"),
      apiFetch("/api/farmers/me/spending"),
      apiFetch("/api/farmers/me/gaps"),
    ]);

    // ── Plan ──────────────────────────────────────────────────────────────────
    if (planRes.status === 404) {
      window.location.href = "onboarding.html";
      return;
    }
    if (!planRes.ok) {
      throw new Error(`Plan fetch failed: HTTP ${planRes.status}`);
    }
    const plan = await planRes.json();
    renderPlan(plan);

    // ── Spending ──────────────────────────────────────────────────────────────
    if (spendRes.ok) {
      const spend = await spendRes.json();
      renderSpending(spend);
    }

    // ── Gaps ──────────────────────────────────────────────────────────────────
    if (gapsRes.ok) {
      const gaps = await gapsRes.json();
      renderGaps(gaps);
    }

    // ── Harvest status (check if already recorded) ────────────────────────────
    if (plan.is_final_stage) {
      try {
        const fsRes = await apiFetch("/api/farmers/me/financial-summary");
        if (fsRes.ok) {
          const fs = await fsRes.json();
          if (fs.has_harvest) {
            harvestForm.classList.add("hidden");
            harvestDoneMsg.textContent =
              "Harvest already recorded. View your full financial report.";
            harvestDoneMsg.classList.remove("hidden");
          }
        }
      } catch { /* non-critical */ }
    }

    // ── Vendor recommendations ────────────────────────────────────────────────
    await refreshVendors();

    showContent();

  } catch (err) {
    showError("Could not load your plan. Please check your connection and try again.");
  }
});
