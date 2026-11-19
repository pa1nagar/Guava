/**
 * plan.js — Personalized farmer dashboard.
 *
 * Drives the rich multi-panel plan.html page.
 * Every number shown is real data from the farmer's API.
 * No hardcoded values.
 */

import { routeGuard, signOut, supabase } from "./auth.js";
import { apiFetch, showError, loadCached, saveCache } from "./api.js";
import { initAiChat } from "./ai-chat.js";
import { getMandiHistory, loadMandiCard, mandiEsc, mandiLang, mt } from "./mandi.js";

// ── Constants ─────────────────────────────────────────────────────────────────

const ZERO_COST_TYPES = new Set(["Irrigation"]);

const TYPE_COLOURS = {
  Fertilizer: "#4A7C59",
  Pesticide:  "#F59E0B",
  Labour:     "#8B5CF6",
  Other:      "#9CA3AF",
};

const STAGE_IDS = [
  "establishment","vegetative_growth","post_monsoon","pre_bloom",
  "bloom_fruit_set","fruit_development","drought_stress","harvest","post_harvest_mature",
];

const CAT_ICON  = { fertilizer:"🌱", irrigation:"💧", ipm:"🔍", activity:"📋" };
const CAT_LABEL = { fertilizer:"Fertilizer", irrigation:"Irrigation", ipm:"Pest & Disease", activity:"Activity" };

// ── DOM refs ──────────────────────────────────────────────────────────────────
const pageLoading   = document.getElementById("page-loading");
const pageError     = document.getElementById("page-error");
const pageErrorMsg  = document.getElementById("page-error-msg");
const pageContent   = document.getElementById("page-content");

const hdrFarmName   = document.getElementById("hdr-farm-name");
const hdrCropPill   = document.getElementById("hdr-crop-pill");
const hdrLocation   = document.getElementById("hdr-location");
const hdrActiveBadge= document.getElementById("hdr-active-badge");
const hdrStageText  = document.getElementById("hdr-stage-text");
const stageDots     = document.getElementById("stage-dots");
const hdrSowingLabel= document.getElementById("hdr-sowing-label");
const hdrDaysLabel  = document.getElementById("hdr-days-label");

const kpiPlants     = document.getElementById("kpi-plants");
const kpiMonths     = document.getElementById("kpi-months");
const kpiStage      = document.getElementById("kpi-stage");
const kpiSpent      = document.getElementById("kpi-spent");
const kpiBep        = document.getElementById("kpi-bep");
const kpiDistrict   = document.getElementById("kpi-district");

const gapAlertsEl   = document.getElementById("gap-alerts");
const summaryHeading= document.getElementById("summary-stage-heading");
const overviewSum   = document.getElementById("overview-summary");
const spendBig      = document.getElementById("spend-big");
const spendBar      = document.getElementById("spend-bar");
const spendLegend   = document.getElementById("spend-legend");
const stageRoadmap  = document.getElementById("stage-roadmap");

const tasksStageBadge = document.getElementById("tasks-stage-badge");
const taskList      = document.getElementById("task-list");
const taskNotes     = document.getElementById("task-notes");

const typePillsEl   = document.getElementById("type-pills");
const actTypeInput  = document.getElementById("act-type");
const actQtyEl      = document.getElementById("act-qty");
const actUnitEl     = document.getElementById("act-unit");
const actCostEl     = document.getElementById("act-cost");
const costRow       = document.getElementById("cost-row");
const qtyHintEl     = document.getElementById("qty-hint");
const logErrorEl    = document.getElementById("log-error");
const btnLog        = document.getElementById("btn-log");
const recentActEl   = document.getElementById("recent-activities");

const finTotalCost  = document.getElementById("fin-total-cost");
const finRevenue    = document.getElementById("fin-revenue");
const finRevenueNote= document.getElementById("fin-revenue-note");
const finPol        = document.getElementById("fin-pol");
const finBep        = document.getElementById("fin-bep");
const finBepNote    = document.getElementById("fin-bep-note");
const finBreakdown  = document.getElementById("fin-breakdown");
const simPlantCount = document.getElementById("sim-plant-count");
const simPrice      = document.getElementById("sim-price");
const simPriceVal   = document.getElementById("sim-price-val");
const simYield      = document.getElementById("sim-yield");
const simYieldVal   = document.getElementById("sim-yield-val");
const simGross      = document.getElementById("sim-gross");
const simNet        = document.getElementById("sim-net");

const navHarvestBtn = document.getElementById("nav-harvest-btn");
const harvestDoneMsg= document.getElementById("harvest-done-msg");
const harvestFormWrap=document.getElementById("harvest-form-wrap");
const hvQtyEl       = document.getElementById("hv-qty");
const hvPriceEl     = document.getElementById("hv-price");
const hvErrorEl     = document.getElementById("hv-error");
const btnHarvest    = document.getElementById("btn-harvest");

const vendorOptin   = document.getElementById("vendor-optin");
const vendorPanel   = document.getElementById("vendor-panel");
const vendorList    = document.getElementById("vendor-list");
const btnGiveConsent= document.getElementById("btn-give-consent");
const btnDismiss    = document.getElementById("btn-dismiss-optin");
const btnRevoke     = document.getElementById("btn-revoke-consent");
const toastEl       = document.getElementById("toast");
const btnSignout    = document.getElementById("btn-signout");

// ── Module state ──────────────────────────────────────────────────────────────
let _profile    = null;
let _plan       = null;
let _spend      = null;
let _fs         = null;
let _hasBehind  = false;
let _toastTimer = null;
let _simTotalCost = 0;

// ── sessionStorage cache helpers (Req 17.3) ───────────────────────────────────
// Use api.js exports: saveCache(key, data) / loadCached(key)
// Local wrapper that bundles plan+profile under a single timestamp entry.
const CACHE_KEY = "sf_plan_cache";

function _savePlanCache(plan, profile) {
  saveCache(CACHE_KEY, { ts: Date.now(), plan, profile });
}

function _loadPlanCache() {
  return loadCached(CACHE_KEY); // returns { ts, plan, profile } or null
}

// ── Utilities ─────────────────────────────────────────────────────────────────

function fmtINR(n) {
  if (n == null) return "—";
  const abs = Math.abs(Number(n));
  if (abs >= 10000000) return "₹" + (abs/10000000).toFixed(1) + " Cr";
  if (abs >= 100000)   return "₹" + (abs/100000).toFixed(1)   + "L";
  if (abs >= 1000)     return "₹" + (abs/1000).toFixed(1)     + "K";
  return "₹" + abs.toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function fmtINRFull(n) {
  if (n == null) return "—";
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso + "T00:00:00").toLocaleDateString("en-IN",
      { day:"numeric", month:"short", year:"numeric" });
  } catch { return iso; }
}

function showToast(msg, ms = 2500) {
  toastEl.textContent = msg;
  toastEl.style.opacity = "1";
  toastEl.classList.remove("pointer-events-none");
  if (_toastTimer) clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => {
    toastEl.style.opacity = "0";
    toastEl.classList.add("pointer-events-none");
  }, ms);
}

// ── Panel switching ───────────────────────────────────────────────────────────

window.switchPanel = function(id) {
  document.querySelectorAll(".farm-panel").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".farm-nav-btn").forEach(b => b.classList.remove("active"));
  document.getElementById(id)?.classList.add("active");
  document.querySelector(`[data-panel="${id}"]`)?.classList.add("active");
};

// ── Header rendering ──────────────────────────────────────────────────────────

function renderHeader(profile, plan, displayName) {
  const farmLabel = displayName
    ? `${displayName.split(" ")[0]}'s Farm`
    : `${profile.district} Farm`;
  hdrFarmName.textContent = farmLabel;
  hdrCropPill.textContent = `🌿 ${profile.crop.charAt(0).toUpperCase() + profile.crop.slice(1)}`;
  hdrLocation.textContent = `${profile.district}, ${profile.state}`;

  hdrStageText.textContent = `${plan.stage_label} — Month ${plan.months_elapsed}`;
  hdrActiveBadge.classList.remove("hidden");

  hdrSowingLabel.textContent = `Planted ${fmtDate(profile.sowing_date)}`;
  hdrDaysLabel.textContent   = `${plan.days_elapsed} days growing`;

  // Stage progress dots
  stageDots.innerHTML = "";
  const currentIdx = STAGE_IDS.indexOf(plan.stage_id);
  STAGE_IDS.forEach((id, i) => {
    const dot = document.createElement("div");
    dot.className = "stage-dot";
    if (i < currentIdx)  dot.classList.add("done");
    if (i === currentIdx) dot.classList.add("active");
    stageDots.appendChild(dot);

    if (i < STAGE_IDS.length - 1) {
      const line = document.createElement("div");
      line.style.cssText = `flex:1; height:2px; background:${i < currentIdx ? "#4A7C59" : "#D1FAE5"}; border-radius:99px;`;
      stageDots.appendChild(line);
    }
  });
}

// ── KPI strip ─────────────────────────────────────────────────────────────────

function renderKPIs(profile, plan, spend, fs) {
  kpiPlants.textContent   = Number(profile.plant_count).toLocaleString("en-IN");
  kpiMonths.textContent   = plan.months_elapsed;
  kpiStage.textContent    = plan.stage_label.split(" ").slice(0,2).join(" ");
  kpiSpent.textContent    = fmtINR(spend.total_cost);
  kpiDistrict.textContent = profile.district.split(" ")[0];

  if (fs?.break_even_price_per_kg) {
    kpiBep.textContent = `₹${Number(fs.break_even_price_per_kg).toFixed(0)}/kg`;
  } else {
    kpiBep.textContent = "—";
  }
}

// ── Stage roadmap ─────────────────────────────────────────────────────────────

function renderRoadmap(plan) {
  const STAGE_LABELS = {
    establishment:       "Establishment",
    vegetative_growth:   "Vegetative Growth",
    post_monsoon:        "Post-Monsoon",
    pre_bloom:           "Pre-Bloom",
    bloom_fruit_set:     "Bloom & Fruit Set",
    fruit_development:   "Fruit Development",
    drought_stress:      "Drought Stress",
    harvest:             "Harvest",
    post_harvest_mature: "Post-Harvest",
  };

  stageRoadmap.innerHTML = "";
  const currentIdx = STAGE_IDS.indexOf(plan.stage_id);

  STAGE_IDS.forEach((id, i) => {
    const isPast   = i < currentIdx;
    const isCurrent= i === currentIdx;
    const row = document.createElement("div");
    row.className = "flex items-center gap-3";

    const dot = document.createElement("div");
    dot.className = `w-3 h-3 rounded-full flex-shrink-0 ${
      isCurrent ? "bg-brand-accent shadow-md" :
      isPast    ? "bg-brand-secondary" : "bg-gray-200"
    }`;

    const label = document.createElement("div");
    label.className = "flex-1";
    label.innerHTML = `
      <span class="text-sm font-${isCurrent ? "bold" : "medium"} ${
        isCurrent ? "text-brand-dark" : isPast ? "text-gray-500" : "text-gray-300"
      }">
        ${STAGE_LABELS[id] || id}
        ${isCurrent ? `<span class="ml-2 text-xs font-semibold text-brand-accent">← Now</span>` : ""}
      </span>
    `;

    row.appendChild(dot);
    row.appendChild(label);
    stageRoadmap.appendChild(row);
  });
}

// ── Gap alerts ────────────────────────────────────────────────────────────────

function renderGaps(gaps) {
  gapAlertsEl.innerHTML = "";
  _hasBehind = false;

  // Only show Fertilizer gaps on the overview (Irrigation is free, no cost alert)
  const behind = gaps.filter(g => g.status === "behind" && g.activity_type !== "Irrigation");
  if (behind.length === 0) { gapAlertsEl.classList.add("hidden"); return; }

  _hasBehind = true;
  gapAlertsEl.classList.remove("hidden");
  for (const g of behind) {
    const el = document.createElement("div");
    el.className = "flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3";
    el.innerHTML = `
      <span class="text-xl flex-shrink-0">⚠️</span>
      <div>
        <p class="text-sm font-semibold text-amber-900">
          ${g.message || `You may be behind on ${g.activity_type.toLowerCase()} for this stage.`}
        </p>
        <p class="text-xs text-amber-700 mt-0.5">
          Expected <strong>${g.expected} ${g.unit}</strong> so far ·
          Logged <strong>${g.actual} ${g.unit}</strong>
        </p>
        <button onclick="window.switchPanel('panel-log')"
          class="mt-2 text-xs font-semibold text-amber-800 underline">
          Log it now →
        </button>
      </div>
    `;
    gapAlertsEl.appendChild(el);
  }
}

// ── Summary ───────────────────────────────────────────────────────────────────

function renderSummary(plan) {
  summaryHeading.textContent = `Month ${plan.months_elapsed} — ${plan.stage_label}`;
  overviewSum.textContent = plan.summary || "";
}

// ── Spending card ─────────────────────────────────────────────────────────────

function renderSpending(spend) {
  _spend = spend;
  const total = spend.total_cost || 0;
  spendBig.textContent = fmtINRFull(total);
  kpiSpent.textContent = fmtINR(total);

  // Also update financials panel
  finTotalCost.textContent = fmtINRFull(total);
  _simTotalCost = total;
  updateSimulator();

  // Breakdown bar (exclude Irrigation — always ₹0)
  const byType = { ...(spend.by_type || {}) };
  delete byType["Irrigation"];
  spendBar.innerHTML   = "";
  spendLegend.innerHTML = "";

  const entries = Object.entries(byType).filter(([,v]) => v > 0);
  const filteredTotal = entries.reduce((s,[,v]) => s + v, 0);

  if (filteredTotal > 0) {
    for (const [type, amt] of entries) {
      const pct    = (amt / filteredTotal * 100).toFixed(1);
      const colour = TYPE_COLOURS[type] || "#9CA3AF";

      const seg = document.createElement("div");
      seg.className = "spend-seg";
      seg.style.cssText = `width:${pct}%;background:${colour};flex-shrink:0;`;
      spendBar.appendChild(seg);

      const leg = document.createElement("div");
      leg.className = "flex items-center gap-1.5 text-xs text-gray-500";
      leg.innerHTML = `<span class="w-2 h-2 rounded-full" style="background:${colour}"></span>${type} ${fmtINR(amt)}`;
      spendLegend.appendChild(leg);
    }

    // Financials breakdown
    finBreakdown.innerHTML = "";
    const sorted = [...entries].sort(([,a],[,b]) => b - a);
    for (const [type, amt] of sorted) {
      const row = document.createElement("div");
      row.className = "flex items-center justify-between py-2.5";
      row.innerHTML = `<span class="text-sm text-gray-700">${type}</span>
                       <span class="text-sm font-semibold text-brand-dark">${fmtINRFull(amt)}</span>`;
      finBreakdown.appendChild(row);
    }
    const totRow = document.createElement("div");
    totRow.className = "flex items-center justify-between py-2.5 bg-gray-50 -mx-4 px-4 rounded-b-xl mt-1";
    totRow.innerHTML = `<span class="text-sm font-bold text-gray-800">Total</span>
                        <span class="text-sm font-bold text-brand-dark">${fmtINRFull(total)}</span>`;
    finBreakdown.appendChild(totRow);
  } else {
    const p = document.createElement("p");
    p.className = "text-sm text-gray-400 py-2";
    p.textContent = "No costs logged yet.";
    spendLegend.appendChild(p);
    finBreakdown.innerHTML = `<p class="text-sm text-gray-400 py-2">No costs logged yet.</p>`;
  }
}

// ── Tasks ─────────────────────────────────────────────────────────────────────

function renderTasks(plan) {
  tasksStageBadge.textContent = `🌱 ${plan.stage_label} — Month ${plan.months_elapsed}`;
  taskList.innerHTML = "";

  const taskEmptyEl = document.getElementById("task-list-empty");

  const tasks = plan.tasks || [];
  if (tasks.length === 0) {
    // Req 17.1 — show empty state instead of blank panel
    if (taskEmptyEl) taskEmptyEl.classList.remove("hidden");
  } else {
    if (taskEmptyEl) taskEmptyEl.classList.add("hidden");
    for (const task of tasks) {
      const icon  = CAT_ICON[task.category]  || "📋";
      const label = CAT_LABEL[task.category] || task.category;
      const accentClass = `task-card-${task.category}`;

      const card = document.createElement("div");
      card.className = `bg-white rounded-xl border border-gray-200 p-4 shadow-sm ${accentClass}`;
      card.innerHTML = `
        <div class="flex items-center gap-2 mb-2">
          <span class="text-lg">${icon}</span>
          <span class="text-xs font-bold text-gray-400 uppercase tracking-wider">${label}</span>
        </div>
        <p class="text-sm font-semibold text-brand-dark mb-1">${task.title}</p>
        ${task.quantity != null ? `
          <div class="inline-flex items-center gap-1.5 bg-gray-50 rounded-lg px-2.5 py-1 mb-2">
            <span class="text-base font-extrabold text-brand-dark">${task.quantity}</span>
            <span class="text-xs text-brand-muted">${task.unit || ""}</span>
          </div>` : ""}
        <p class="text-sm text-gray-600 leading-relaxed">${task.description}</p>
      `;
      taskList.appendChild(card);
    }
  }

  taskNotes.innerHTML = "";
  for (const note of (plan.notes || [])) {
    const p = document.createElement("p");
    p.className = "text-xs text-gray-400 italic";
    p.textContent = note;
    taskNotes.appendChild(p);
  }
}

// ── Financial summary (post-harvest) ─────────────────────────────────────────

function renderFinancialSummary(fs) {
  _fs = fs;
  if (!fs) return;

  if (fs.revenue != null) {
    finRevenue.textContent = fmtINRFull(fs.revenue);
  } else {
    finRevenue.textContent = "—";
    finRevenueNote.textContent = fs.has_harvest ? "" : "Log harvest to see revenue";
  }

  if (fs.profit_or_loss != null) {
    const isProfit = fs.profit_or_loss >= 0;
    finPol.textContent = (isProfit ? "+" : "−") + fmtINR(Math.abs(fs.profit_or_loss));
    finPol.className   = `text-2xl font-extrabold ${isProfit ? "text-green-600" : "text-red-500"}`;
  }

  if (fs.break_even_price_per_kg != null) {
    finBep.textContent     = `₹${Number(fs.break_even_price_per_kg).toFixed(2)}/kg`;
    kpiBep.textContent     = `₹${Number(fs.break_even_price_per_kg).toFixed(0)}/kg`;
  } else {
    finBep.textContent     = "—";
    finBepNote.textContent = fs.break_even_note || "";
  }
}

// ── Revenue simulator ─────────────────────────────────────────────────────────

function updateSimulator() {
  if (!_profile) return;
  const price     = parseInt(simPrice.value, 10);
  const yieldKg   = parseInt(simYield.value, 10);
  const plants    = _profile.plant_count;
  const gross     = price * yieldKg * plants;
  const net       = gross - (_simTotalCost || 0);

  simPriceVal.textContent = `₹${price}`;
  simYieldVal.textContent = `${yieldKg} kg`;
  simGross.textContent    = fmtINR(gross);
  simNet.textContent      = fmtINR(net);
  simNet.className        = `text-lg font-bold ${net >= 0 ? "text-emerald-800" : "text-red-600"}`;
}

simPrice?.addEventListener("input", updateSimulator);
simYield?.addEventListener("input", updateSimulator);

// ── Activity type pills ───────────────────────────────────────────────────────

function buildTypePills(types) {
  typePillsEl.innerHTML = "";
  for (const t of types) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.dataset.type = t;
    btn.textContent = t;
    btn.className = `type-pill ${t === "Fertilizer" ? "selected" : ""}`;
    btn.addEventListener("click", () => selectType(t));
    typePillsEl.appendChild(btn);
  }
}

function selectType(type) {
  actTypeInput.value = type;
  typePillsEl.querySelectorAll(".type-pill").forEach(b => {
    b.classList.toggle("selected", b.dataset.type === type);
  });
  if (type === "Fertilizer") { actUnitEl.value = "kg"; }
  else if (type === "Irrigation") { actUnitEl.value = "litres"; }
  else if (type === "Labour") { actUnitEl.value = "hours"; }

  // Hide cost field for free inputs
  if (ZERO_COST_TYPES.has(type)) {
    costRow.classList.add("hidden");
    actCostEl.value = "0";
  } else {
    costRow.classList.remove("hidden");
    if (actCostEl.value === "0") actCostEl.value = "";
  }
}

function preFillFromPlan(plan) {
  const fertTask = (plan.tasks || []).find(t => t.category === "fertilizer");
  if (fertTask?.quantity != null) {
    actQtyEl.value  = fertTask.quantity;
    actUnitEl.value = fertTask.unit?.includes("kg") ? "kg" : "kg";
    qtyHintEl.textContent = `ref: ${fertTask.quantity} ${fertTask.unit || ""}`;
  }
  selectType("Fertilizer");
}

// ── Recent activities ─────────────────────────────────────────────────────────

async function loadRecentActivities() {
  const recentLoadingEl = document.getElementById("recent-activities-loading");
  const recentEmptyEl   = document.getElementById("recent-activities-empty");

  // Show spinner (Req 17.5)
  if (recentLoadingEl) recentLoadingEl.classList.remove("hidden");
  if (recentEmptyEl)   recentEmptyEl.classList.add("hidden");
  recentActEl.innerHTML = "";

  try {
    const res = await apiFetch("/api/farmers/me/activities");
    if (recentLoadingEl) recentLoadingEl.classList.add("hidden");
    if (!res.ok) return;
    const activities = await res.json();
    const recent = [...activities].reverse().slice(0, 5);
    if (recent.length === 0) {
      // Req 17.1 — show friendly empty state
      if (recentEmptyEl) recentEmptyEl.classList.remove("hidden");
      return;
    }
    for (const a of recent) {
      const el = document.createElement("div");
      el.className = "flex items-center justify-between bg-white border border-gray-100 rounded-xl px-4 py-2.5";
      el.innerHTML = `
        <div>
          <p class="text-sm font-semibold text-brand-dark">${a.activity_type}</p>
          <p class="text-xs text-gray-400">${fmtDate(a.logged_date)} · ${a.quantity} ${a.unit || ""}</p>
        </div>
        <p class="text-sm font-semibold text-brand-dark">${fmtINRFull(a.cost)}</p>
      `;
      recentActEl.appendChild(el);
    }
  } catch {
    if (recentLoadingEl) recentLoadingEl.classList.add("hidden");
    /* non-critical — empty state already visible */
  }
}

// ── Log form submit ───────────────────────────────────────────────────────────

btnLog?.addEventListener("click", async () => {
  logErrorEl.classList.add("hidden");
  const type = actTypeInput.value;
  const qty  = parseFloat(actQtyEl.value);
  const cost = ZERO_COST_TYPES.has(type) ? 0 : parseFloat(actCostEl.value);

  if (isNaN(qty) || qty < 0) {
    logErrorEl.textContent = "Quantity must be 0 or more.";
    logErrorEl.classList.remove("hidden");
    return;
  }
  if (!ZERO_COST_TYPES.has(type) && (isNaN(cost) || cost < 0)) {
    logErrorEl.textContent = "Cost must be 0 or more.";
    logErrorEl.classList.remove("hidden");
    return;
  }

  btnLog.textContent = "Saving…";
  btnLog.disabled = true;

  try {
    const res = await apiFetch("/api/farmers/me/activities", {
      method: "POST",
      body: JSON.stringify({ activity_type: type, quantity: qty, unit: actUnitEl.value, cost }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    actQtyEl.value = "";
    if (!ZERO_COST_TYPES.has(type)) actCostEl.value = "";
    showToast("✓ Saved");
    await refreshSpendingAndGaps();
    await loadRecentActivities();
  } catch (err) {
    logErrorEl.textContent = err.message || "Could not save.";
    logErrorEl.classList.remove("hidden");
  } finally {
    btnLog.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save entry';
    btnLog.disabled = false;
  }
});

// ── Harvest form ──────────────────────────────────────────────────────────────

btnHarvest?.addEventListener("click", async () => {
  hvErrorEl.classList.add("hidden");
  const qty   = parseFloat(hvQtyEl.value);
  const price = parseFloat(hvPriceEl.value);
  if (isNaN(qty) || qty <= 0) {
    hvErrorEl.textContent = "Quantity must be > 0."; hvErrorEl.classList.remove("hidden"); return;
  }
  if (isNaN(price) || price < 0) {
    hvErrorEl.textContent = "Price must be ≥ 0."; hvErrorEl.classList.remove("hidden"); return;
  }
  btnHarvest.disabled = true; btnHarvest.textContent = "Saving…";
  try {
    const res = await apiFetch("/api/farmers/me/harvest", {
      method: "POST",
      body: JSON.stringify({ sale_quantity_kg: qty, sale_price_per_kg: price }),
    });
    if (res.status === 409) {
      harvestFormWrap.classList.add("hidden");
      harvestDoneMsg.textContent = "Harvest already recorded. See your financial report.";
      harvestDoneMsg.classList.remove("hidden");
      return;
    }
    if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || `HTTP ${res.status}`); }
    const data = await res.json();
    harvestFormWrap.classList.add("hidden");
    harvestDoneMsg.textContent =
      `Harvest recorded — ${data.sale_quantity_kg.toLocaleString("en-IN")} kg at ₹${data.sale_price_per_kg}/kg. Revenue: ₹${data.revenue.toLocaleString("en-IN")}.`;
    harvestDoneMsg.classList.remove("hidden");
    showToast("✓ Harvest recorded");
    const fsRes = await apiFetch("/api/farmers/me/financial-summary");
    if (fsRes.ok) renderFinancialSummary(await fsRes.json());
  } catch (err) {
    hvErrorEl.textContent = err.message || "Could not save.";
    hvErrorEl.classList.remove("hidden");
  } finally {
    btnHarvest.disabled = false; btnHarvest.textContent = "Record harvest & sale";
  }
});

// ── Vendor consent ────────────────────────────────────────────────────────────

btnGiveConsent?.addEventListener("click", async () => {
  try {
    await apiFetch("/api/farmers/me/vendor-consent", { method: "PUT", body: JSON.stringify({ consent: true }) });
    vendorOptin.classList.add("hidden");
    await refreshVendors();
  } catch { showToast("Could not update preference."); }
});
btnDismiss?.addEventListener("click", () => vendorOptin.classList.add("hidden"));
btnRevoke?.addEventListener("click", async () => {
  try {
    await apiFetch("/api/farmers/me/vendor-consent", { method: "PUT", body: JSON.stringify({ consent: false }) });
    vendorPanel.classList.add("hidden");
    showToast("Vendor suggestions turned off.");
  } catch { showToast("Could not update preference."); }
});
btnSignout?.addEventListener("click", () => signOut());

// ── Vendor rendering ──────────────────────────────────────────────────────────

function renderVendors(cards) {
  vendorList.innerHTML = "";
  if (!cards || cards.length === 0) { vendorPanel.classList.add("hidden"); return; }
  vendorPanel.classList.remove("hidden");
  for (const c of cards) {
    const hasWA   = c.contact_method === "whatsapp" || c.contact_method === "both";
    const hasCall = c.contact_method === "call" || c.contact_method === "both";
    const card = document.createElement("div");
    card.className = "flex flex-col gap-2";
    card.innerHTML = `
      <p class="text-sm font-bold text-brand-dark">${c.vendor_name} — ${c.district}</p>
      <p class="text-xs text-gray-500">For: <strong>${c.input_needed}</strong> (need ${c.quantity_needed} ${c.unit})</p>
      <div class="flex gap-2">
        ${hasCall ? `<a href="tel:${c.phone}" class="flex-1 h-10 flex items-center justify-center bg-brand-primary text-white text-sm font-bold rounded-xl">📞 Call</a>` : ""}
        ${hasWA   ? `<a href="https://wa.me/${c.phone.replace(/\D/g,"")}" target="_blank" rel="noopener" class="flex-1 h-10 flex items-center justify-center bg-green-600 text-white text-sm font-bold rounded-xl">💬 WhatsApp</a>` : ""}
      </div>
    `;
    vendorList.appendChild(card);
  }
}

// ── Refresh helpers ───────────────────────────────────────────────────────────

async function refreshSpendingAndGaps() {
  const [spendRes, gapsRes, fsRes] = await Promise.all([
    apiFetch("/api/farmers/me/spending"),
    apiFetch("/api/farmers/me/gaps"),
    apiFetch("/api/farmers/me/financial-summary"),
  ]);
  if (spendRes.ok) renderSpending(await spendRes.json());
  if (gapsRes.ok)  renderGaps(await gapsRes.json());
  if (fsRes.ok)    renderFinancialSummary(await fsRes.json());
  await refreshVendors();
}

async function refreshVendors() {
  try {
    const res = await apiFetch("/api/farmers/me/vendor-recommendations");
    if (!res.ok) return;
    const cards = await res.json();
    renderVendors(cards);
    if (_hasBehind && cards.length === 0) {
      const profRes = await apiFetch("/api/farmers/me");
      if (profRes.ok) {
        const prof = await profRes.json();
        if (!prof.vendor_recommendation_consent) vendorOptin.classList.remove("hidden");
      }
    }
  } catch { /* non-critical */ }
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────

// Exposed so the stale-banner Retry button can call it (Req 17.3)
window._retryLoad = function() {
  try { sessionStorage.removeItem(CACHE_KEY); } catch { /* ignore */ }
  location.reload();
};

document.addEventListener("DOMContentLoaded", async () => {
  await routeGuard("plan");

  // Show "server waking up" hint after 5 seconds of loading
  const coldStartTimer = setTimeout(() => {
    const msg = document.getElementById("cold-start-msg");
    if (msg) msg.classList.remove("hidden");
  }, 5000);

  let displayName = "";
  try {
    const { data: { session } } = await supabase.auth.getSession();
    displayName = session?.user?.user_metadata?.full_name || "";
  } catch { /* non-critical */ }

  // Refs for new empty/no-farm elements
  const pageNoFarm  = document.getElementById("page-no-farm");
  const staleBanner = document.getElementById("stale-banner");

  try {
    // ── Step 1: Load critical data first (plan + profile) ──────────────────
    // Show the page as soon as these two respond — don't wait for spending/gaps
    const loadingMsg = document.querySelector("#page-loading p.text-sm");

    if (loadingMsg) loadingMsg.textContent = "Connecting to server…";

    const [planRes, profileRes] = await Promise.all([
      apiFetch("/api/plan"),
      apiFetch("/api/farmers/me"),
    ]);

    if (planRes.status === 404 || profileRes.status === 404) {
      // Req 17.1 — no farm yet: show friendly empty state, not a redirect
      clearTimeout(coldStartTimer);
      pageLoading.classList.add("hidden");
      if (pageNoFarm) {
        pageNoFarm.classList.remove("hidden");
      } else {
        window.location.href = "onboarding.html";
      }
      return;
    }
    if (!planRes.ok || !profileRes.ok) throw new Error("Load failed");

    _plan    = await planRes.json();
    _profile = await profileRes.json();

    // Cache successful load for offline fallback (Req 17.3)
    _savePlanCache(_plan, _profile);

    if (loadingMsg) loadingMsg.textContent = "Building your dashboard…";

    // Build activity type pills (use fallback — don't wait for API)
    buildTypePills(["Fertilizer","Irrigation","Pesticide","Labour","Other"]);
    preFillFromPlan(_plan);

    // Render core dashboard immediately
    renderHeader(_profile, _plan, displayName);
    renderKPIs(_profile, _plan, { total_cost: 0, by_type: {} }, null);
    renderSummary(_plan);
    renderTasks(_plan);
    renderRoadmap(_plan);

    // Show the page now — farmer sees their dashboard
    clearTimeout(coldStartTimer);
    pageLoading.classList.add("hidden");
    pageContent.classList.remove("hidden");

    // ── Step 2: Load secondary data in background (no spinner) ─────────────
    // These fire after the page is visible — failures are silent
    const [spendRes, gapsRes, fsRes, typesRes] = await Promise.all([
      apiFetch("/api/farmers/me/spending"),
      apiFetch("/api/farmers/me/gaps"),
      apiFetch("/api/farmers/me/financial-summary"),
      apiFetch("/api/constants/activity-types"),
    ]);

    _spend = spendRes.ok ? await spendRes.json() : { total_cost: 0, by_type: {} };
    _fs    = fsRes.ok    ? await fsRes.json()    : null;

    // Update KPIs and spending now that we have real data
    renderKPIs(_profile, _plan, _spend, _fs);
    renderSpending(_spend);
    if (fsRes.ok) renderFinancialSummary(_fs);

    // Update activity type pills with server values
    if (typesRes.ok) {
      const td = await typesRes.json();
      buildTypePills(td.activity_types || ["Fertilizer","Irrigation","Pesticide","Labour","Other"]);
      preFillFromPlan(_plan);
    }

    simPlantCount.textContent = Number(_profile.plant_count).toLocaleString("en-IN");
    updateSimulator();

    if (gapsRes.ok) renderGaps(await gapsRes.json());

    // Harvest tab
    if (_plan.is_final_stage) {
      navHarvestBtn.classList.remove("hidden");
      if (_fs?.has_harvest) {
        harvestFormWrap.classList.add("hidden");
        harvestDoneMsg.textContent = "Harvest already recorded. See your financial report.";
        harvestDoneMsg.classList.remove("hidden");
      }
    }

    await loadRecentActivities();
    await refreshVendors();

  } catch (err) {
    clearTimeout(coldStartTimer);

    // Req 17.3 — if page hasn't loaded yet try to show cached data
    const cached = _loadPlanCache();
    if (cached && !pageContent.classList.contains("hidden") === false) {
      // We haven't rendered anything yet — use cache
      _plan    = cached.plan;
      _profile = cached.profile;

      buildTypePills(["Fertilizer","Irrigation","Pesticide","Labour","Other"]);
      preFillFromPlan(_plan);
      renderHeader(_profile, _plan, displayName);
      renderKPIs(_profile, _plan, { total_cost: 0, by_type: {} }, null);
      renderSummary(_plan);
      renderTasks(_plan);
      renderRoadmap(_plan);

      pageLoading.classList.add("hidden");
      pageContent.classList.remove("hidden");

      // Show stale-data banner with Retry button (Req 17.3)
      if (staleBanner) staleBanner.classList.remove("hidden");
      return;
    }

    // Only show error if page hasn't loaded yet
    if (!pageContent.classList.contains("hidden")) return; // already showing — silent fail
    pageLoading.classList.add("hidden");
    const isTimeout = err.name === "AbortError";
    pageErrorMsg.textContent = isTimeout
      ? "The server took too long to respond. Please refresh — it may still be waking up (can take 30s on first load)."
      : "Could not load your farm. Please check your connection and try again.";
    pageError.classList.remove("hidden");
    console.error(err);
  }
});


// ═══════════════════════════════════════════════════════════════════════════
// INSIGHTS PANEL — Weather, Pest Risk, Market, Future Stages
// ═══════════════════════════════════════════════════════════════════════════

// WMO weather code → emoji
function wmoEmoji(code) {
  if (code === 0 || code === 1) return "☀️";
  if (code === 2 || code === 3) return "⛅";
  if (code >= 45 && code <= 48) return "🌫️";
  if (code >= 51 && code <= 67) return "🌧️";
  if (code >= 71 && code <= 77) return "❄️";
  if (code >= 80 && code <= 82) return "🌦️";
  if (code >= 95) return "⛈️";
  return "🌤️";
}

function formatDateShort(iso) {
  try {
    const d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric" });
  } catch { return iso; }
}

function renderWeather(weather, locationStr) {
  const locEl = document.getElementById("weather-location");
  const curEl = document.getElementById("weather-current");
  const irrEl = document.getElementById("irrigation-advisory");
  const gridEl = document.getElementById("weather-grid");

  if (locEl) locEl.textContent = `📍 ${locationStr}  ·  Source: Open-Meteo.com`;

  if (!weather.fetched) {
    if (curEl) curEl.innerHTML = `<p class="text-sm opacity-75">Weather data unavailable. ${weather.error || ""}</p>`;
    return;
  }

  const cur = weather.current || {};
  if (curEl) {
    curEl.innerHTML = `
      <span class="text-5xl">${wmoEmoji(cur.weathercode || 0)}</span>
      <div>
        <p class="text-3xl font-extrabold">${cur.temperature ?? "—"}°C</p>
        <p class="text-sm opacity-75">${cur.weather_desc || ""}</p>
        <p class="text-xs opacity-60 mt-0.5">Wind ${cur.windspeed ?? "—"} km/h</p>
      </div>
    `;
  }

  // Irrigation advisory
  const irr = weather.irrigation || {};
  if (irrEl) {
    const colours = {
      high_demand:    "bg-red-50 border-red-300 text-red-800",
      normal:         "bg-green-50 border-green-300 text-green-800",
      low_demand:     "bg-blue-50 border-blue-300 text-blue-800",
      drought_period: "bg-amber-50 border-amber-300 text-amber-800",
      unknown:        "bg-gray-50 border-gray-200 text-gray-600",
    };
    irrEl.className = `mb-3 rounded-xl border px-4 py-3 text-sm font-medium ${colours[irr.status] || colours.unknown}`;
    irrEl.innerHTML = `
      <span class="font-bold">💧 Irrigation today: </span>${irr.message || "—"}
      ${irr.et0 ? `<span class="ml-2 text-xs opacity-70">(ET0 ${irr.et0} mm/day)</span>` : ""}
    `;
  }

  // 7-day forecast grid
  if (gridEl) {
    gridEl.innerHTML = "";
    for (const day of (weather.forecast || [])) {
      const card = document.createElement("div");
      card.className = "bg-white border border-gray-200 rounded-xl p-2 text-center flex flex-col gap-0.5";
      card.innerHTML = `
        <p class="text-xs text-gray-400 font-medium">${formatDateShort(day.date)}</p>
        <p class="text-2xl">${wmoEmoji(day.weathercode || 0)}</p>
        <p class="text-xs font-bold text-brand-dark">${day.tmax ?? "—"}°</p>
        <p class="text-xs text-gray-400">${day.tmin ?? "—"}°</p>
        ${day.rain_mm > 0
          ? `<p class="text-xs text-blue-600 font-semibold">🌧 ${day.rain_mm}mm</p>`
          : `<p class="text-xs text-gray-300">—</p>`
        }
        ${day.rain_prob > 0
          ? `<p class="text-xs text-gray-400">${day.rain_prob}%</p>`
          : ""
        }
      `;
      gridEl.appendChild(card);
    }
  }
}

function renderDiseaseRisks(risks) {
  const listEl = document.getElementById("disease-risk-list");
  if (!listEl) return;

  if (!risks || risks.length === 0) {
    listEl.innerHTML = `
      <div class="flex items-center gap-3 bg-green-50 border border-green-200 rounded-xl px-4 py-3">
        <span class="text-2xl">✅</span>
        <p class="text-sm font-medium text-green-800">
          No high-risk weather conditions detected for the next 3 days. Continue routine monitoring.
        </p>
      </div>`;
    return;
  }

  listEl.innerHTML = "";
  const colourMap = {
    red:   "bg-red-50 border-red-300 text-red-900",
    amber: "bg-amber-50 border-amber-200 text-amber-900",
  };

  for (const r of risks) {
    const el = document.createElement("div");
    el.className = `flex items-start gap-3 border rounded-2xl px-4 py-3 ${colourMap[r.colour] || colourMap.amber}`;
    el.innerHTML = `
      <span class="text-2xl flex-shrink-0">${r.colour === "red" ? "🚨" : "⚠️"}</span>
      <div>
        <p class="text-sm font-bold">${r.disease}
          <span class="ml-2 text-xs font-semibold px-2 py-0.5 rounded-full
            ${r.risk === "High" ? "bg-red-200 text-red-800" : "bg-amber-200 text-amber-800"}">
            ${r.risk} Risk
          </span>
        </p>
        <p class="text-sm mt-1 leading-relaxed">${r.action}</p>
      </div>
    `;
    listEl.appendChild(el);
  }
}

// ── Harvest timing + mandi card ──────────────────────────────────────────────
// The mandi price card itself lives in js/mandi.js (shared with index.html).
// Prices come from GET /api/market-prices/guava (saved daily by the backend).
// Nothing here is estimated.

let _harvestTiming = null;
let _priceHistorySummary = null;

function renderHarvestTiming() {
  const el = document.getElementById("harvest-timing-card");
  if (!el) return;
  const ht = _harvestTiming || {};
  const days = _priceHistorySummary?.distinct_days ?? 0;
  const minDays = getMandiHistory()?.min_days_for_trend;  // from the backend
  const lang = mandiLang() === "hi" ? "hi-IN" : "en-IN";
  let month = ht.harvest_month_name || "—";
  if (ht.estimated_harvest_date) {
    const d = new Date(ht.estimated_harvest_date + "T00:00:00");
    if (!Number.isNaN(d.getTime())) month = d.toLocaleDateString(lang, { month: "long", year: "numeric" });
  }

  let note;
  if ((ht.harvest_month_saved_days || 0) > 0 && ht.harvest_month_avg_per_kg != null) {
    note = mt("mandi.harvest.savedMonth", {
      month, days: ht.harvest_month_saved_days, avg: ht.harvest_month_avg_per_kg,
    });
  } else if (minDays != null && days < minDays) {
    note = mt("mandi.history.notEnough", { min: minDays, have: days });
  } else {
    note = mt("mandi.harvest.noMonth", { month, days });
  }

  el.innerHTML = `
    <p class="text-sm font-bold text-amber-900 mb-1">
      <i class="fa-solid fa-calendar-star mr-1"></i> ${mandiEsc(mt("mandi.harvest.title"))}
    </p>
    <p class="text-2xl font-extrabold text-amber-900">${mandiEsc(month)}</p>
    <p class="text-sm text-amber-800 mt-1">${mandiEsc(note)}</p>
    <p class="text-xs text-amber-700 mt-3 border-t border-amber-200 pt-2">${mandiEsc(mt("mandi.harvest.disclaimer"))}</p>`;
}

function renderMarket(market) {
  _harvestTiming = market.harvest_timing || {};
  _priceHistorySummary = market.price_history || {};
  renderHarvestTiming();
  loadMandiCard({ apiFetch, onRender: renderHarvestTiming });
}

function renderFutureStages(stages) {
  const el = document.getElementById("future-stages");
  if (!el) return;

  if (!stages || stages.length === 0) {
    el.innerHTML = `<p class="text-sm text-gray-400">No upcoming stages — you are in the final stage.</p>`;
    return;
  }

  el.innerHTML = "";
  const icons = ["🌿", "🌸", "🍈"];
  stages.forEach((s, i) => {
    const card = document.createElement("div");
    card.className = "bg-white border border-gray-200 rounded-2xl p-4 shadow-sm";
    card.innerHTML = `
      <div class="flex items-center gap-2 mb-2">
        <span class="text-xl">${icons[i] || "🌱"}</span>
        <p class="text-base font-bold text-brand-dark">${s.label}</p>
        <span class="ml-auto text-xs text-gray-400">Starts Month ${s.month_start}</span>
      </div>
      <p class="text-sm text-gray-600 mb-3 leading-relaxed">${s.description}</p>
      <div class="grid grid-cols-2 gap-2 text-xs">
        ${s.fertilizer_name ? `
          <div class="bg-green-50 rounded-lg px-3 py-2">
            <p class="text-gray-500 font-semibold">Fertilizer</p>
            <p class="font-bold text-green-800">${s.fertilizer_name}</p>
            ${s.fertilizer_kg_per_month > 0
              ? `<p class="text-green-600">${s.fertilizer_kg_per_month} kg/month</p>` : ""}
          </div>` : ""}
        ${s.irrigation_litres_per_day > 0 ? `
          <div class="bg-blue-50 rounded-lg px-3 py-2">
            <p class="text-gray-500 font-semibold">Irrigation</p>
            <p class="font-bold text-blue-800">${s.irrigation_litres_per_day.toLocaleString("en-IN")} L/day</p>
            <p class="text-blue-600">total for all plants</p>
          </div>` : ""}
        ${s.ipm_checks?.length ? `
          <div class="bg-amber-50 rounded-lg px-3 py-2 col-span-2">
            <p class="text-gray-500 font-semibold mb-1">Watch for</p>
            <p class="font-medium text-amber-800">${s.ipm_checks.join(" · ")}</p>
          </div>` : ""}
      </div>
    `;
    el.appendChild(card);
  });
}

// Load insights when panel is first activated
let _insightsLoaded = false;
let _aiChatReady    = false;

const _origSwitchPanel = window.switchPanel;
window.switchPanel = function(id) {
  _origSwitchPanel(id);
  if (id === "panel-insights" && !_insightsLoaded) {
    _insightsLoaded = true;
    loadInsights();
  }
  if (id === "panel-ai" && !_aiChatReady) {
    _aiChatReady = true;
    const container = document.getElementById("ai-chat-container");
    if (container) initAiChat(container);
  }
};


// ─────────────────────────────────────────────────────────────────────────────
// Advanced insights rendering — GDD, climate, compliance, fertilizer budget
// ─────────────────────────────────────────────────────────────────────────────

function renderGDDAndClimate(climate, currentStageId) {
  const el = document.getElementById("gdd-section");
  if (!el) return;

  if (!climate?.fetched) {
    el.innerHTML = `<p class="text-sm text-gray-400">NASA POWER climate data unavailable. ${climate?.error || ""}</p>`;
    return;
  }

  const gdd = climate.gdd_cumulative || 0;
  const thresholds = climate.gdd_thresholds || {};
  const STAGE_LABELS = {
    establishment:"Establishment", vegetative_growth:"Vegetative Growth",
    post_monsoon:"Post-Monsoon", pre_bloom:"Pre-Bloom",
    bloom_fruit_set:"Bloom & Fruit Set", fruit_development:"Fruit Development",
    drought_stress:"Drought Stress", harvest:"Harvest", post_harvest_mature:"Post-Harvest",
  };

  // Next stage threshold
  const stageOrder = Object.keys(thresholds);
  const curIdx = stageOrder.indexOf(currentStageId);
  const nextStageId = stageOrder[curIdx + 1];
  const nextThreshold = nextStageId ? thresholds[nextStageId] : null;
  const currentThreshold = thresholds[currentStageId] || 0;
  const progressPct = nextThreshold
    ? Math.min(((gdd - currentThreshold) / (nextThreshold - currentThreshold)) * 100, 100)
    : 100;

  // GDD vs calendar comparison
  const gddVsCal = climate.gdd_vs_calendar || "on_track";
  const gddColour = gddVsCal === "ahead" ? "text-green-600" : gddVsCal === "behind" ? "text-amber-600" : "text-gray-600";
  const gddIcon   = gddVsCal === "ahead" ? "🚀" : gddVsCal === "behind" ? "🐢" : "✅";

  el.innerHTML = `
    <!-- GDD gauge -->
    <div class="bg-white border border-gray-200 rounded-2xl p-4 shadow-sm">
      <div class="flex items-start justify-between mb-3">
        <div>
          <p class="text-xs text-gray-400 font-semibold uppercase tracking-wider">Growing Degree Days accumulated</p>
          <p class="text-3xl font-extrabold text-brand-dark mt-0.5">${gdd.toLocaleString("en-IN")} GDD</p>
          <p class="text-sm text-gray-500 mt-1">Base temperature 10°C · since planting</p>
        </div>
        <span class="text-3xl">${gddIcon}</span>
      </div>
      ${nextStageId ? `
        <div class="mb-1 flex justify-between text-xs text-gray-500">
          <span>Current: ${STAGE_LABELS[currentStageId] || currentStageId}</span>
          <span>Next: ${STAGE_LABELS[nextStageId] || nextStageId} at ${nextThreshold} GDD</span>
        </div>
        <div class="h-3 bg-gray-100 rounded-full overflow-hidden">
          <div class="h-3 bg-brand-secondary rounded-full transition-all"
               style="width:${progressPct.toFixed(1)}%"></div>
        </div>
        <p class="text-xs text-gray-400 mt-1">${progressPct.toFixed(0)}% of the way to next stage</p>
      ` : `<p class="text-sm text-gray-500">Final stage reached.</p>`}
      <p class="text-sm mt-3 font-medium ${gddColour}">${climate.gdd_note || ""}</p>
    </div>

    <!-- Climate anomaly -->
    <div class="bg-white border border-gray-200 rounded-2xl p-4 shadow-sm">
      <p class="text-xs text-gray-400 font-semibold uppercase tracking-wider mb-2">This Month vs 30-Year Normal (NASA POWER)</p>
      <div class="grid grid-cols-2 gap-3 mb-3">
        <div class="bg-gray-50 rounded-xl p-3 text-center">
          <p class="text-xs text-gray-400 mb-1">Temperature anomaly</p>
          ${climate.anomaly_temperature != null ? `
            <p class="text-xl font-extrabold ${Math.abs(climate.anomaly_temperature) > 1.5 ? "text-red-600" : "text-gray-700"}">
              ${climate.anomaly_temperature > 0 ? "+" : ""}${climate.anomaly_temperature}°C
            </p>
          ` : `<p class="text-sm text-gray-400">Insufficient data</p>`}
        </div>
        <div class="bg-gray-50 rounded-xl p-3 text-center">
          <p class="text-xs text-gray-400 mb-1">Rainfall anomaly</p>
          ${climate.anomaly_rainfall_mm != null ? `
            <p class="text-xl font-extrabold ${Math.abs(climate.anomaly_rainfall_mm) > 20 ? "text-blue-600" : "text-gray-700"}">
              ${climate.anomaly_rainfall_mm > 0 ? "+" : ""}${climate.anomaly_rainfall_mm}mm
            </p>
          ` : `<p class="text-sm text-gray-400">Insufficient data</p>`}
        </div>
      </div>
      <p class="text-sm text-gray-700 leading-relaxed">${climate.anomaly_summary || ""}</p>
    </div>
  `;
}

function renderMonsoonRisk(climate) {
  const el = document.getElementById("monsoon-card");
  if (!el || !climate?.fetched) return;

  const risk = climate.waterlogging_risk || "low";
  const colours = {
    high:     "bg-red-50 border-red-300",
    moderate: "bg-amber-50 border-amber-300",
    drought:  "bg-orange-50 border-orange-300",
    low:      "bg-green-50 border-green-200",
  };
  const icons = { high: "🌊", moderate: "⚠️", drought: "🌵", low: "✅" };

  el.className = `rounded-2xl border px-5 py-4 ${colours[risk] || colours.low}`;
  el.innerHTML = `
    <div class="flex items-start gap-3 mb-3">
      <span class="text-3xl">${icons[risk] || "✅"}</span>
      <div>
        <p class="text-sm font-bold text-gray-800 capitalize">${risk === "drought" ? "Drought Risk" : risk + " waterlogging risk"}</p>
        <p class="text-sm text-gray-700 mt-1 leading-relaxed">${climate.waterlogging_message || ""}</p>
      </div>
    </div>
    <div class="grid grid-cols-2 gap-3 text-center mt-2">
      <div class="bg-white/60 rounded-xl p-2">
        <p class="text-xs text-gray-500">Monsoon rainfall so far</p>
        <p class="text-lg font-extrabold text-brand-dark">${(climate.monsoon_cumulative_mm || 0).toLocaleString("en-IN")} mm</p>
      </div>
      <div class="bg-white/60 rounded-xl p-2">
        <p class="text-xs text-gray-500">vs 30-yr normal</p>
        <p class="text-lg font-extrabold ${(climate.monsoon_deficit_pct || 0) > 0 ? "text-blue-700" : "text-red-600"}">
          ${(climate.monsoon_deficit_pct || 0) > 0 ? "+" : ""}${(climate.monsoon_deficit_pct || 0).toFixed(0)}%
        </p>
      </div>
    </div>
  `;
}

function renderCompliance(compliance) {
  const el = document.getElementById("compliance-card");
  if (!el || !compliance) return;

  const score = compliance.score || 0;
  const colour = score >= 85 ? "#4A7C59" : score >= 60 ? "#F59E0B" : "#EF4444";
  const bgColour = score >= 85 ? "bg-green-50" : score >= 60 ? "bg-amber-50" : "bg-red-50";

  // Simple circular score display using CSS
  el.innerHTML = `
    <div class="flex items-center gap-5 mb-4">
      <div class="relative w-20 h-20 flex-shrink-0">
        <svg viewBox="0 0 36 36" class="w-20 h-20 -rotate-90">
          <circle cx="18" cy="18" r="15.9" fill="none" stroke="#E5E7EB" stroke-width="3"/>
          <circle cx="18" cy="18" r="15.9" fill="none" stroke="${colour}" stroke-width="3"
            stroke-dasharray="${score} ${100 - score}" stroke-dashoffset="0"
            stroke-linecap="round"/>
        </svg>
        <span class="absolute inset-0 flex items-center justify-center text-lg font-extrabold text-brand-dark">
          ${score.toFixed(0)}
        </span>
      </div>
      <div>
        <p class="text-xs text-gray-400 font-semibold uppercase tracking-wider">Input Compliance Score</p>
        <p class="text-base font-bold ${score >= 85 ? "text-green-700" : score >= 60 ? "text-amber-700" : "text-red-700"} mt-0.5">
          ${score >= 85 ? "Good" : score >= 60 ? "Moderate" : "Needs attention"}
        </p>
      </div>
    </div>
    <p class="text-sm text-gray-700 leading-relaxed mb-3">${compliance.interpretation || ""}</p>
    <div class="grid grid-cols-2 gap-3">
      <div class="${bgColour} rounded-xl p-3 text-center">
        <p class="text-xs text-gray-500">Logged fertilizer</p>
        <p class="text-lg font-bold text-brand-dark">${(compliance.logged_fert_kg || 0).toLocaleString("en-IN")} kg</p>
      </div>
      <div class="bg-gray-50 rounded-xl p-3 text-center">
        <p class="text-xs text-gray-500">Expected so far</p>
        <p class="text-lg font-bold text-brand-dark">${(compliance.expected_fert_kg || 0).toLocaleString("en-IN")} kg</p>
      </div>
    </div>
  `;
}

function renderFertForecast(items) {
  const el = document.getElementById("fert-forecast");
  if (!el) return;

  if (!items || items.length === 0) {
    el.innerHTML = `<p class="text-sm text-gray-400">No upcoming fertilizer stages.</p>`;
    return;
  }

  let totalCost = 0;
  el.innerHTML = "";

  for (const item of items) {
    totalCost += item.cost_estimate || 0;
    const card = document.createElement("div");
    card.className = "bg-white border border-gray-200 rounded-2xl p-4 shadow-sm";
    card.innerHTML = `
      <div class="flex items-start justify-between gap-3">
        <div class="flex-1 min-w-0">
          <p class="text-sm font-bold text-brand-dark">${item.stage_label}</p>
          <p class="text-xs text-gray-500 mt-0.5">${item.fertilizer}</p>
          <p class="text-xs text-gray-400 mt-1">${item.total_kg} kg · ₹${item.rate_per_kg}/kg · ${item.months} month${item.months > 1 ? "s" : ""}</p>
        </div>
        <div class="text-right flex-shrink-0">
          <p class="text-xs text-gray-400">Estimated cost</p>
          <p class="text-lg font-extrabold text-brand-dark">₹${(item.cost_estimate || 0).toLocaleString("en-IN")}</p>
        </div>
      </div>
    `;
    el.appendChild(card);
  }

  // Total row
  const total = document.createElement("div");
  total.className = "bg-emerald-50 border border-emerald-200 rounded-2xl p-4 flex justify-between items-center";
  total.innerHTML = `
    <p class="text-sm font-bold text-emerald-900">Total fertilizer cost (remaining stages)</p>
    <p class="text-xl font-extrabold text-emerald-900">₹${totalCost.toLocaleString("en-IN")}</p>
  `;
  el.appendChild(total);
}

// Override loadInsights to use new data
async function loadInsights() {
  const loadingEl = document.getElementById("insights-loading");
  const contentEl = document.getElementById("insights-content");
  if (!loadingEl || !contentEl) return;

  try {
    const res = await apiFetch("/api/farmers/me/insights");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const locStr = `${data.location?.district}, ${data.location?.state}`;
    const stageId = data.current_stage?.stage_id || "";

    renderWeather(data.weather || {}, locStr);
    renderDiseaseRisks(data.weather?.disease_risks || []);
    renderMarket(data.market || {});
    renderFutureStages(data.future_stages || []);
    renderGDDAndClimate(data.climate || {}, stageId);
    renderMonsoonRisk(data.climate || {});
    renderCompliance(data.compliance || null);
    renderFertForecast(data.fertilizer_forecast || []);

    loadingEl.classList.add("hidden");
    contentEl.classList.remove("hidden");

  } catch (err) {
    loadingEl.innerHTML = `
      <p class="text-sm text-red-600">
        Could not load insights. Please check your connection and try again.
      </p>`;
    console.error("Insights load failed:", err);
  }
}
