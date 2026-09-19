/**
 * report.js — Crop-cycle financial report page.
 *
 * Fetches GET /api/farmers/me/report and renders:
 *  - Financial summary (total cost, revenue, profit/loss, break-even)
 *  - Cost breakdown by activity type
 *  - Activity history (chronological)
 *  - Incomplete-stage warning when stages have no logged activities
 */

import { routeGuard, getJwt, signOut } from "./auth.js";
import { API_BASE_URL } from "./config.js";

// ── DOM refs ──────────────────────────────────────────────────────────────────
const loadingEl       = document.getElementById("report-loading");
const errorEl         = document.getElementById("report-error");
const contentEl       = document.getElementById("report-content");
const cropEl          = document.getElementById("report-crop");
const metaEl          = document.getElementById("report-meta");
const incompleteWarnEl= document.getElementById("incomplete-warning");
const incompleteListEl= document.getElementById("incomplete-list");
const fsTotalCostEl   = document.getElementById("fs-total-cost");
const fsRevenueEl     = document.getElementById("fs-revenue");
const fsRevenueNoteEl = document.getElementById("fs-revenue-note");
const fsPolEl         = document.getElementById("fs-pol");
const fsBepEl         = document.getElementById("fs-bep");
const fsBepNoteEl     = document.getElementById("fs-bep-note");
const costBreakdownEl = document.getElementById("cost-breakdown");
const actHistoryEl    = document.getElementById("activity-history");
const noActivitiesEl  = document.getElementById("no-activities");

// ── Utilities ─────────────────────────────────────────────────────────────────

function fmt(n) {
  if (n == null) return "—";
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-IN", {
      day: "numeric", month: "short", year: "numeric",
    });
  } catch {
    return iso;
  }
}

async function apiFetch(path) {
  const jwt = await getJwt();
  return fetch(`${API_BASE_URL}${path}`, {
    headers: { Authorization: `Bearer ${jwt}` },
  });
}

// ── Renderers ─────────────────────────────────────────────────────────────────

function renderReport(r) {
  // Crop header
  cropEl.textContent = `${r.crop} Farm Report`;
  metaEl.textContent =
    `${r.plant_count.toLocaleString("en-IN")} plants · Planted ${fmtDate(r.sowing_date)}`;

  // Incomplete stage warning
  if (r.stages_with_no_activity && r.stages_with_no_activity.length > 0) {
    incompleteWarnEl.classList.remove("hidden");
    incompleteListEl.innerHTML = "";
    for (const label of r.stages_with_no_activity) {
      const li = document.createElement("li");
      li.textContent = `${label} — Not logged. Totals may be incomplete for this stage.`;
      incompleteListEl.appendChild(li);
    }
  }

  // Financial summary
  fsTotalCostEl.textContent = fmt(r.total_cost);

  if (r.revenue != null) {
    fsRevenueEl.textContent = fmt(r.revenue);
  } else {
    fsRevenueEl.textContent = "—";
    fsRevenueNoteEl.textContent = r.has_harvest ? "" : "Log harvest to see revenue";
  }

  if (r.profit_or_loss != null) {
    const isProfit = r.profit_or_loss >= 0;
    fsPolEl.textContent = fmt(Math.abs(r.profit_or_loss));
    fsPolEl.className = `text-xl font-bold ${isProfit ? "text-green-600" : "text-red-600"}`;
    fsPolEl.textContent = (isProfit ? "+" : "−") + fmt(Math.abs(r.profit_or_loss));
  } else {
    fsPolEl.textContent = "—";
    fsPolEl.className = "text-xl font-bold text-gray-400";
  }

  if (r.break_even_price_per_kg != null) {
    fsBepEl.textContent = fmt(r.break_even_price_per_kg) + "/kg";
  } else {
    fsBepEl.textContent = "—";
    if (r.break_even_note) {
      fsBepNoteEl.textContent = r.break_even_note;
    }
  }

  // Cost breakdown
  costBreakdownEl.innerHTML = "";
  const byType = r.cost_by_type || {};
  const types = Object.keys(byType);

  if (types.length === 0) {
    const row = document.createElement("div");
    row.className = "px-4 py-3 text-sm text-gray-400";
    row.textContent = "No costs logged yet.";
    costBreakdownEl.appendChild(row);
  } else {
    // Sort by cost descending.
    const sorted = types.sort((a, b) => byType[b] - byType[a]);
    for (const type of sorted) {
      const row = document.createElement("div");
      row.className = "flex items-center justify-between px-4 py-3";
      row.innerHTML = `
        <span class="text-sm text-gray-700">${type}</span>
        <span class="text-sm font-semibold text-brand-dark">${fmt(byType[type])}</span>
      `;
      costBreakdownEl.appendChild(row);
    }
    // Total row
    const totalRow = document.createElement("div");
    totalRow.className =
      "flex items-center justify-between px-4 py-3 bg-gray-50 rounded-b-xl";
    totalRow.innerHTML = `
      <span class="text-sm font-semibold text-gray-700">Total</span>
      <span class="text-sm font-bold text-brand-dark">${fmt(r.total_cost)}</span>
    `;
    costBreakdownEl.appendChild(totalRow);
  }

  // Activity history
  actHistoryEl.innerHTML = "";
  const history = r.activity_history || [];
  if (history.length === 0) {
    noActivitiesEl.classList.remove("hidden");
  } else {
    noActivitiesEl.classList.add("hidden");
    for (const a of history) {
      const card = document.createElement("div");
      card.className =
        "bg-white rounded-xl border border-gray-200 px-4 py-3 flex items-start justify-between gap-3";
      card.innerHTML = `
        <div class="flex flex-col gap-0.5 flex-1 min-w-0">
          <p class="text-sm font-medium text-brand-dark">${a.activity_type}</p>
          <p class="text-xs text-gray-500">${fmtDate(a.date)}</p>
          ${a.quantity ? `<p class="text-xs text-gray-500">${a.quantity} ${a.unit || ""}</p>` : ""}
          ${a.notes ? `<p class="text-xs text-gray-400 italic truncate">${a.notes}</p>` : ""}
        </div>
        <div class="text-right flex-shrink-0">
          <p class="text-sm font-semibold text-brand-dark">${fmt(a.cost)}</p>
        </div>
      `;
      actHistoryEl.appendChild(card);
    }
  }
}

// ── Main ──────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
  await routeGuard("plan");   // reuse "plan" guard — any authenticated user

  try {
    const res = await apiFetch("/api/farmers/me/report");

    if (res.status === 404) {
      window.location.href = "onboarding.html";
      return;
    }
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }

    const report = await res.json();

    loadingEl.classList.add("hidden");
    renderReport(report);
    contentEl.classList.remove("hidden");

  } catch (err) {
    loadingEl.classList.add("hidden");
    errorEl.textContent = "Could not load report. Please check your connection and try again.";
    errorEl.classList.remove("hidden");
  }
});
