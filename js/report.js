/**
 * report.js — Crop-cycle financial report page.
 *
 * Fetches GET /api/farmers/me/report and renders:
 *  - Financial summary (total cost, revenue, profit/loss, break-even)
 *  - Cost breakdown by activity type  (Req 17.1: empty state when none)
 *  - Activity history (chronological) (Req 17.1: empty state when none)
 *  - Incomplete-stage warning when stages have no logged activities
 *  - No-harvest empty state           (Req 17.1)
 *  - Section-level loading indicator  (Req 17.5)
 */

import { routeGuard } from "./auth.js";
import { apiFetch } from "./api.js";
import { applyI18n, escapeHtml, initPage, renderLoadError, t } from "./dom.js";
import { formatDate, formatNumber } from "./translator.js";

// ── DOM refs ──────────────────────────────────────────────────────────────────
const loadingEl            = document.getElementById("report-loading");
const errorEl              = document.getElementById("report-error");
const contentEl            = document.getElementById("report-content");
const cropEl               = document.getElementById("report-crop");
const metaEl               = document.getElementById("report-meta");
const incompleteWarnEl     = document.getElementById("incomplete-warning");
const incompleteListEl     = document.getElementById("incomplete-list");
const headlineNetEl        = document.getElementById("headline-net");
const fsTotalCostEl        = document.getElementById("fs-total-cost");
const fsRevenueEl          = document.getElementById("fs-revenue");
const fsRevenueNoteEl      = document.getElementById("fs-revenue-note");
const fsPolEl              = document.getElementById("fs-pol");
const fsBepEl              = document.getElementById("fs-bep");
const fsBepNoteEl          = document.getElementById("fs-bep-note");
const costBreakdownEl      = document.getElementById("cost-breakdown");
const costBreakdownLoading = document.getElementById("cost-breakdown-loading");
const costBreakdownEmpty   = document.getElementById("cost-breakdown-empty");
const actHistoryEl         = document.getElementById("activity-history");
const noActivitiesEl       = document.getElementById("no-activities");
const noHarvestEmptyEl     = document.getElementById("no-harvest-empty");

// ── Utilities ─────────────────────────────────────────────────────────────────

function fmt(n) {
  if (n == null) return "—";
  return "₹" + formatNumber(Number(n), { maximumFractionDigits: 2 });
}

// ── Renderers ─────────────────────────────────────────────────────────────────

function renderReport(r) {
  // Crop header
  cropEl.textContent = t("report.title", { crop: r.crop });
  metaEl.textContent = t("report.meta", { plants: formatNumber(r.plant_count), date: formatDate(r.sowing_date) });

  // Incomplete stage warning
  incompleteListEl.innerHTML = "";
  if (r.stages_with_no_activity && r.stages_with_no_activity.length > 0) {
    incompleteWarnEl.classList.remove("hidden");
    for (const label of r.stages_with_no_activity) {
      const li = document.createElement("li");
      li.textContent = t("report.incomplete.item", { stage: label });
      incompleteListEl.appendChild(li);
    }
  } else {
    incompleteWarnEl.classList.add("hidden");
  }

  // Financial summary
  fsTotalCostEl.textContent = fmt(r.total_cost);

  if (r.revenue != null) {
    fsRevenueEl.textContent = fmt(r.revenue);
    fsRevenueNoteEl.textContent = "";
  } else {
    fsRevenueEl.textContent = "—";
    fsRevenueNoteEl.textContent = r.has_harvest ? "" : t("report.logHarvestHint");
  }

  if (r.profit_or_loss != null) {
    const isProfit = r.profit_or_loss >= 0;
    const text = (isProfit ? "+" : "−") + fmt(Math.abs(r.profit_or_loss));
    fsPolEl.className = `text-xl font-bold ${isProfit ? "text-green-700" : "text-red-700"}`;
    fsPolEl.textContent = text;
    headlineNetEl.textContent = text;
    headlineNetEl.style.color = isProfit ? "#15803D" : "#B91C1C";
  } else {
    fsPolEl.textContent = "—";
    fsPolEl.className = "text-xl font-bold text-gray-600";
    headlineNetEl.textContent = "—";
    headlineNetEl.style.color = "";
  }

  if (r.break_even_price_per_kg != null) {
    fsBepEl.textContent = fmt(r.break_even_price_per_kg) + "/kg";
    fsBepNoteEl.textContent = "";
  } else {
    fsBepEl.textContent = "—";
    // break_even_note is written for farmers by the backend
    fsBepNoteEl.textContent = r.break_even_note || "";
  }

  // ── Cost breakdown ──────────────────────────────────────────────────────
  if (costBreakdownLoading) costBreakdownLoading.classList.add("hidden");

  costBreakdownEl.innerHTML = "";
  const byType = r.cost_by_type || {};
  const types = Object.keys(byType);

  if (types.length === 0) {
    costBreakdownEl.classList.add("hidden");
    if (costBreakdownEmpty) costBreakdownEmpty.classList.remove("hidden");
  } else {
    costBreakdownEl.classList.remove("hidden");
    if (costBreakdownEmpty) costBreakdownEmpty.classList.add("hidden");

    for (const type of types.sort((a, b) => byType[b] - byType[a])) {
      const row = document.createElement("div");
      row.className = "flex items-center justify-between gap-3 px-4 py-3";
      row.innerHTML = `
        <span class="text-base text-gray-800 break-words">${escapeHtml(type)}</span>
        <span class="text-base font-semibold text-brand-dark">${escapeHtml(fmt(byType[type]))}</span>
      `;
      costBreakdownEl.appendChild(row);
    }
    const totalRow = document.createElement("div");
    totalRow.className = "flex items-center justify-between gap-3 px-4 py-3 bg-gray-50 rounded-b-xl";
    totalRow.innerHTML = `
      <span class="text-base font-semibold text-gray-800">${escapeHtml(t("report.total"))}</span>
      <span class="text-base font-bold text-brand-dark">${escapeHtml(fmt(r.total_cost))}</span>
    `;
    costBreakdownEl.appendChild(totalRow);
  }

  // ── Activity history ────────────────────────────────────────────────────
  actHistoryEl.innerHTML = "";
  const history = r.activity_history || [];
  if (history.length === 0) {
    noActivitiesEl.classList.remove("hidden");
  } else {
    noActivitiesEl.classList.add("hidden");
    for (const a of history) {
      const card = document.createElement("div");
      card.className = "bg-white rounded-xl border border-gray-200 px-4 py-3 flex items-start justify-between gap-3";
      card.innerHTML = `
        <div class="flex flex-col gap-0.5 flex-1 min-w-0">
          <p class="text-base font-medium text-brand-dark break-words">${escapeHtml(a.activity_type)}</p>
          <p class="text-sm text-gray-600">${escapeHtml(formatDate(a.date))}</p>
          ${a.quantity ? `<p class="text-sm text-gray-600">${escapeHtml(formatNumber(a.quantity))} ${escapeHtml(a.unit || "")}</p>` : ""}
          ${a.notes ? `<p class="text-sm text-gray-600 italic break-words">${escapeHtml(a.notes)}</p>` : ""}
        </div>
        <div class="text-right flex-shrink-0">
          <p class="text-base font-semibold text-brand-dark">${escapeHtml(fmt(a.cost))}</p>
        </div>
      `;
      actHistoryEl.appendChild(card);
    }
  }

  // ── No-harvest empty state (Req 17.1) ───────────────────────────────────
  if (noHarvestEmptyEl) {
    noHarvestEmptyEl.classList.toggle("hidden", !(history.length === 0 && !r.has_harvest));
  }
  applyI18n(contentEl);
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function loadReport() {
  loadingEl.classList.remove("hidden");
  errorEl.classList.add("hidden");
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
  } catch {
    loadingEl.classList.add("hidden");
    // Req 17.2: friendly message with Retry, no stack traces or internal detail
    renderLoadError(errorEl, loadReport);
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  initPage();
  await routeGuard("report"); // authenticated users only; no profile-check redirect
  await loadReport();
});
