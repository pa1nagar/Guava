/**
 * plan.js — Personalized farmer dashboard.
 *
 * Drives the rich multi-panel plan.html page.
 * Every number shown is real data from the farmer's API.
 * No hardcoded values.
 */

import { routeGuard, getJwt, signOut, supabase } from "./auth.js";
import { API_BASE_URL } from "./config.js";

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

  for (const task of (plan.tasks || [])) {
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
  try {
    const res = await apiFetch("/api/farmers/me/activities");
    if (!res.ok) return;
    const activities = await res.json();
    recentActEl.innerHTML = "";
    const recent = [...activities].reverse().slice(0, 5);
    if (recent.length === 0) {
      recentActEl.innerHTML = `<p class="text-sm text-gray-400">No entries yet.</p>`;
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
  } catch { /* non-critical */ }
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

document.addEventListener("DOMContentLoaded", async () => {
  await routeGuard("plan");

  let displayName = "";
  try {
    const { data: { session } } = await supabase.auth.getSession();
    displayName = session?.user?.user_metadata?.full_name || "";
  } catch { /* non-critical */ }

  try {
    const [planRes, profileRes, spendRes, gapsRes, typesRes, fsRes] = await Promise.all([
      apiFetch("/api/plan"),
      apiFetch("/api/farmers/me"),
      apiFetch("/api/farmers/me/spending"),
      apiFetch("/api/farmers/me/gaps"),
      apiFetch("/api/constants/activity-types"),
      apiFetch("/api/farmers/me/financial-summary"),
    ]);

    if (planRes.status === 404 || profileRes.status === 404) {
      window.location.href = "onboarding.html"; return;
    }
    if (!planRes.ok || !profileRes.ok) throw new Error("Load failed");

    _plan    = await planRes.json();
    _profile = await profileRes.json();
    _spend   = spendRes.ok  ? await spendRes.json()  : { total_cost:0, by_type:{} };
    _fs      = fsRes.ok     ? await fsRes.json()      : null;

    // Build activity type pills
    let actTypes = ["Fertilizer","Irrigation","Pesticide","Labour","Other"];
    if (typesRes.ok) { const d = await typesRes.json(); actTypes = d.activity_types || actTypes; }
    buildTypePills(actTypes);

    // Render everything
    renderHeader(_profile, _plan, displayName);
    renderKPIs(_profile, _plan, _spend, _fs);
    renderSummary(_plan);
    renderTasks(_plan);
    renderRoadmap(_plan);
    renderSpending(_spend);
    preFillFromPlan(_plan);
    if (fsRes.ok) renderFinancialSummary(_fs);

    // Simulator setup
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

    pageLoading.classList.add("hidden");
    pageContent.classList.remove("hidden");

  } catch (err) {
    pageLoading.classList.add("hidden");
    pageErrorMsg.textContent = "Could not load your farm. Please check your connection and try again.";
    pageError.classList.remove("hidden");
    console.error(err);
  }
});
