/**
 * farm.js — Farm and Plot CRUD UI for Smart Farmer.
 *
 * Handles:
 *  - Loading the farmer's farm list via GET /api/farmers/me/farms
 *  - Creating a new farm via POST /api/farmers/me/farms
 *  - Archiving a farm via DELETE /api/farmers/me/farms/{id}/archive
 *  - Loading plots for a farm via GET /api/farmers/me/farms/{farm_id}/plots
 *  - Creating a new plot via POST /api/farmers/me/farms/{farm_id}/plots
 *  - Viewing plant count history via GET /api/farmers/me/farms/{farm_id}/plots/{plot_id}/plant-count-history
 *
 * Field names follow backend/routers/farms.py (FarmIn/FarmOut, PlotIn/PlotOut):
 * locality, area_value, area_unit; plots need crop, planting_date and plant_count.
 *
 * Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.7, 4.8
 */

import { routeGuard, signOut } from "./auth.js";
import { apiFetch, showError } from "./api.js";
import {
  applyI18n, errorMessage, escapeHtml, getLang, initPage, renderLoadError, setBusy, t,
} from "./dom.js";
import { formatDate as fmtDate, formatNumber } from "./translator.js";

// ── State ─────────────────────────────────────────────────────────────────────
let _farms = [];
let _activeFarmId = null;
let _plots = [];

// ── DOM refs ──────────────────────────────────────────────────────────────────
const farmList        = document.getElementById("farm-list");
const farmListEmpty   = document.getElementById("farm-list-empty");
const farmListLoading = document.getElementById("farm-list-loading");
const plotsSection    = document.getElementById("plots-section");
const plotList        = document.getElementById("plot-list");
const plotListEmpty   = document.getElementById("plot-list-empty");
const plotListLoading = document.getElementById("plot-list-loading");
const activeFarmName  = document.getElementById("active-farm-name");
const headlineTrees   = document.getElementById("headline-trees");
const headlineArea    = document.getElementById("headline-area");

// ── Farm form ─────────────────────────────────────────────────────────────────
const farmFormWrap   = document.getElementById("farm-form-wrap");
const farmFormToggle = document.getElementById("btn-show-farm-form");
const farmFormCancel = document.getElementById("btn-cancel-farm-form");
const farmForm       = document.getElementById("farm-form");
const farmFormError  = document.getElementById("farm-form-error");
const farmFormBtn    = document.getElementById("btn-save-farm");

// ── Plot form ─────────────────────────────────────────────────────────────────
const plotFormWrap   = document.getElementById("plot-form-wrap");
const plotFormToggle = document.getElementById("btn-show-plot-form");
const plotFormCancel = document.getElementById("btn-cancel-plot-form");
const plotForm       = document.getElementById("plot-form");
const plotFormError  = document.getElementById("plot-form-error");
const plotFormBtn    = document.getElementById("btn-save-plot");

// ── Plant count history modal ─────────────────────────────────────────────────
const historyModal   = document.getElementById("plant-count-history-modal");
const historyList    = document.getElementById("plant-count-history-list");
const historyClose   = document.getElementById("btn-close-history");

// ── Utilities ─────────────────────────────────────────────────────────────────
function setLoading(el, show) {
  if (el) el.classList.toggle("hidden", !show);
}

function showFormError(el, message) {
  el.textContent = message;
  el.classList.remove("hidden");
}

function cropAgeMonths(plantingDate) {
  if (!plantingDate) return null;
  const now = new Date();
  const plant = new Date(plantingDate);
  if (Number.isNaN(plant.getTime())) return null;
  return (now.getFullYear() - plant.getFullYear()) * 12 + (now.getMonth() - plant.getMonth());
}

function areaText(value, unit) {
  if (value == null || value === "") return "";
  return `${formatNumber(value)} ${unit || ""}`.trim();
}

// ── Load farms ────────────────────────────────────────────────────────────────
async function loadFarms() {
  setLoading(farmListLoading, true);
  setLoading(farmList, false);
  setLoading(farmListEmpty, false);

  try {
    const res = await apiFetch("/api/farmers/me/farms");
    if (!res.ok) {
      renderLoadError(farmList, loadFarms);
      return;
    }
    _farms = await res.json();
    renderFarms();
    // Show the plots of the first active farm without an extra tap.
    if (!_activeFarmId) {
      const first = _farms.find((f) => f.is_active !== false);
      if (first) await selectFarm(first.id, { scroll: false });
    }
  } catch {
    renderLoadError(farmList, loadFarms, "common.error.network");
  } finally {
    setLoading(farmListLoading, false);
  }
}

function renderFarms() {
  farmList.innerHTML = "";

  if (!_farms || _farms.length === 0) {
    setLoading(farmListEmpty, true);
    setLoading(farmList, false);
    return;
  }

  setLoading(farmListEmpty, false);
  farmList.classList.remove("hidden");

  _farms.forEach((farm) => {
    const card = document.createElement("div");
    card.className = "bg-white border border-gray-200 rounded-xl p-4 shadow-sm";
    card.setAttribute("data-farm-id", farm.id);
    const place = [farm.locality, farm.district, farm.state].filter(Boolean).map(escapeHtml).join(", ") || "—";
    const area = areaText(farm.area_value, farm.area_unit);
    card.innerHTML = `
      <div class="flex flex-col gap-3">
        <div class="min-w-0">
          <div class="flex items-center gap-2 flex-wrap">
            <h3 class="font-bold text-emerald-900 text-base break-words">${escapeHtml(farm.name)}</h3>
            ${farm.is_active === false
              ? `<span class="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full" data-i18n="farm.archived.badge"></span>`
              : `<span class="text-xs bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full" data-i18n="farm.active.badge"></span>`}
          </div>
          <p class="text-sm text-gray-600 mt-0.5 break-words">${place}</p>
          ${area ? `<p class="text-sm text-gray-600 mt-1">${escapeHtml(area)}</p>` : ""}
        </div>
        <div class="flex gap-2 flex-wrap">
          <button type="button" class="btn-select-farm flex-1 text-sm font-semibold text-brand-secondary border border-brand-secondary px-3 py-1.5 rounded-lg"
            data-farm-id="${escapeHtml(farm.id)}" data-i18n="farm.viewPlots"></button>
          ${farm.is_active !== false ? `
          <button type="button" class="btn-archive-farm flex-1 text-sm font-semibold text-gray-600 border border-gray-300 px-3 py-1.5 rounded-lg"
            data-farm-id="${escapeHtml(farm.id)}" data-farm-name="${escapeHtml(farm.name)}" data-i18n="common.archive"></button>` : ""}
        </div>
      </div>
    `;
    farmList.appendChild(card);
  });
  applyI18n(farmList);

  farmList.querySelectorAll(".btn-select-farm").forEach((btn) => {
    btn.addEventListener("click", () => selectFarm(btn.getAttribute("data-farm-id")));
  });
  farmList.querySelectorAll(".btn-archive-farm").forEach((btn) => {
    btn.addEventListener("click", () =>
      archiveFarm(btn.getAttribute("data-farm-id"), btn.getAttribute("data-farm-name")));
  });
}

// ── Select farm → load plots ──────────────────────────────────────────────────
async function selectFarm(farmId, { scroll = true } = {}) {
  _activeFarmId = farmId;
  const farm = _farms.find((f) => f.id === farmId);
  if (activeFarmName) activeFarmName.textContent = farm ? farm.name : "";

  plotsSection.classList.remove("hidden");
  if (scroll) plotsSection.scrollIntoView({ behavior: "smooth", block: "start" });

  setLoading(plotListLoading, true);
  setLoading(plotListEmpty, false);
  plotList.innerHTML = "";

  try {
    const res = await apiFetch(`/api/farmers/me/farms/${encodeURIComponent(farmId)}/plots`);
    if (!res.ok) {
      renderLoadError(plotList, () => selectFarm(farmId, { scroll: false }));
      return;
    }
    _plots = await res.json();
    renderPlots();
  } catch {
    renderLoadError(plotList, () => selectFarm(farmId, { scroll: false }), "common.error.network");
  } finally {
    setLoading(plotListLoading, false);
  }
}

function renderHeadline() {
  const trees = (_plots || []).reduce((s, p) => s + (Number(p.plant_count) || 0), 0);
  if (headlineTrees) headlineTrees.textContent = _plots.length ? formatNumber(trees) : "—";
  if (headlineArea) {
    const units = new Set(_plots.filter((p) => p.area_value != null).map((p) => p.area_unit || ""));
    if (units.size === 1) {
      const total = _plots.reduce((s, p) => s + (Number(p.area_value) || 0), 0);
      headlineArea.textContent = areaText(total, [...units][0]);
    } else {
      headlineArea.textContent = "—";
    }
  }
}

function renderPlots() {
  plotList.innerHTML = "";
  renderHeadline();
  if (!_plots || _plots.length === 0) {
    setLoading(plotListEmpty, true);
    return;
  }
  setLoading(plotListEmpty, false);

  _plots.forEach((plot) => {
    const ageMonths = cropAgeMonths(plot.planting_date);
    const card = document.createElement("div");
    card.className = "bg-white border border-gray-200 rounded-xl p-4 shadow-sm";
    card.innerHTML = `
      <div class="flex flex-col gap-3">
        <div class="min-w-0">
          <h4 class="font-bold text-emerald-900 break-words">${escapeHtml(plot.name)}</h4>
          <p class="text-sm text-gray-600 mt-0.5 break-words">
            ${escapeHtml(plot.crop || "—")}${plot.variety ? " · " + escapeHtml(plot.variety) : ""}
          </p>
          <div class="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-sm text-gray-600">
            ${plot.planting_date
              ? `<span>🌱 ${escapeHtml(t("plot.planted"))}: ${escapeHtml(fmtDate(plot.planting_date))}</span>` : ""}
            ${ageMonths !== null && ageMonths >= 0
              ? `<span>🗓️ ${escapeHtml(t("plot.cropAge.months", { months: ageMonths }))}</span>` : ""}
            ${plot.plant_count
              ? `<span>🌿 ${escapeHtml(t("plot.trees"))}: ${escapeHtml(formatNumber(plot.plant_count))}</span>` : ""}
            ${plot.area_value != null
              ? `<span>📐 ${escapeHtml(areaText(plot.area_value, plot.area_unit))}</span>` : ""}
          </div>
        </div>
        <button type="button" class="btn-plant-history text-sm font-semibold text-brand-secondary underline self-start"
          data-plot-id="${escapeHtml(plot.id)}" data-i18n="plot.plantCountHistory"></button>
      </div>
    `;
    plotList.appendChild(card);
  });
  applyI18n(plotList);

  plotList.querySelectorAll(".btn-plant-history").forEach((btn) => {
    btn.addEventListener("click", () => loadPlantCountHistory(btn.getAttribute("data-plot-id")));
  });
}

// ── Archive farm ──────────────────────────────────────────────────────────────
async function archiveFarm(farmId, farmName) {
  if (!confirm(t("farm.archive.confirmNamed", { name: farmName }))) return;

  try {
    const res = await apiFetch(`/api/farmers/me/farms/${encodeURIComponent(farmId)}/archive`, { method: "DELETE" });
    if (!res.ok) {
      showError(await errorMessage(res));
      return;
    }
    if (_activeFarmId === farmId) {
      _activeFarmId = null;
      _plots = [];
      plotsSection.classList.add("hidden");
    }
    await loadFarms();
  } catch {
    showError(t("common.error.network"));
  }
}

// ── Plant count history ───────────────────────────────────────────────────────
async function loadPlantCountHistory(plotId) {
  historyList.innerHTML =
    `<div class="loading-overlay"><span class="loading-spinner loading-spinner--sm"></span> <span>${escapeHtml(t("common.loading"))}</span></div>`;
  historyModal.classList.remove("hidden");

  try {
    const res = await apiFetch(
      `/api/farmers/me/farms/${encodeURIComponent(_activeFarmId)}/plots/${encodeURIComponent(plotId)}/plant-count-history`);
    if (!res.ok) {
      renderLoadError(historyList, () => loadPlantCountHistory(plotId));
      return;
    }
    const rows = await res.json();
    if (!rows || rows.length === 0) {
      historyList.innerHTML = `<p class="text-sm text-gray-600 p-4">${escapeHtml(t("plot.plantCountHistory.empty"))}</p>`;
      return;
    }
    historyList.innerHTML = rows.map((row) => `
      <div class="flex items-center justify-between gap-2 py-2 border-b border-gray-100 last:border-0 text-sm">
        <span class="text-gray-600">${escapeHtml(fmtDate(row.changed_at))}</span>
        <span class="text-gray-800">${escapeHtml(formatNumber(row.prior_count))} → <strong class="text-emerald-800">${escapeHtml(formatNumber(row.new_count))}</strong></span>
      </div>
    `).join("");
  } catch {
    renderLoadError(historyList, () => loadPlantCountHistory(plotId), "common.error.network");
  }
}

// ── Create farm ───────────────────────────────────────────────────────────────
async function handleSaveFarm(e) {
  e.preventDefault();
  farmFormError.classList.add("hidden");

  const val = (id) => document.getElementById(id).value.trim();
  const body = {
    name:     val("farm-name"),
    locality: val("farm-village") || null,
    district: val("farm-district"),
    state:    val("farm-state"),
    country:  val("farm-country") || "India",
    area_value: parseFloat(document.getElementById("farm-area").value),
    area_unit:  document.getElementById("farm-area-unit").value || null,
    irrigation_method: val("farm-irrigation") || null,
    notes:    val("farm-notes") || null,
  };
  if (Number.isNaN(body.area_value)) { body.area_value = null; body.area_unit = null; }

  // The backend requires name, district and state.
  if (!body.name || !body.district || !body.state) {
    showFormError(farmFormError, t("farm.error.required"));
    return;
  }

  setBusy(farmFormBtn, true);
  try {
    const res = await apiFetch("/api/farmers/me/farms", { method: "POST", body: JSON.stringify(body) });
    if (!res.ok) {
      showFormError(farmFormError, await errorMessage(res));
      return;
    }
    farmForm.reset();
    farmFormWrap.classList.add("hidden");
    await loadFarms();
  } catch {
    showFormError(farmFormError, t("common.error.network"));
  } finally {
    setBusy(farmFormBtn, false);
  }
}

// ── Create plot ───────────────────────────────────────────────────────────────
async function handleSavePlot(e) {
  e.preventDefault();
  plotFormError.classList.add("hidden");

  const val = (id) => document.getElementById(id).value.trim();
  const plantingDateVal = document.getElementById("plot-planting-date").value;
  const num = (id) => {
    const n = parseFloat(document.getElementById(id).value);
    return Number.isNaN(n) ? null : n;
  };
  const body = {
    name:          val("plot-name"),
    crop:          val("plot-crop"),
    variety:       val("plot-variety") || null,
    planting_date: plantingDateVal || null,
    area_value:    num("plot-area"),
    area_unit:     num("plot-area") != null ? document.getElementById("plot-area-unit").value : null,
    plant_count:   parseInt(document.getElementById("plot-plant-count").value, 10) || null,
    row_spacing_m: num("plot-row-spacing"),
    within_row_spacing_m: num("plot-within-row-spacing"),
    notes:         val("plot-notes") || null,
  };

  // The backend requires name, crop, planting date and a plant count of at least 1.
  if (!body.name || !body.crop || !body.planting_date || !body.plant_count) {
    showFormError(plotFormError, t("plot.error.required"));
    return;
  }
  if (new Date(body.planting_date) > new Date()) {
    showFormError(plotFormError, t("plot.plantingDate.error.future"));
    return;
  }
  if (!_activeFarmId) {
    showFormError(plotFormError, t("plot.error.noFarm"));
    return;
  }

  setBusy(plotFormBtn, true);
  try {
    const res = await apiFetch(`/api/farmers/me/farms/${encodeURIComponent(_activeFarmId)}/plots`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      showFormError(plotFormError, await errorMessage(res));
      return;
    }
    plotForm.reset();
    plotFormWrap.classList.add("hidden");
    await selectFarm(_activeFarmId, { scroll: false });
  } catch {
    showFormError(plotFormError, t("common.error.network"));
  } finally {
    setBusy(plotFormBtn, false);
  }
}

// ── Initialise ────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  initPage();
  await routeGuard("farm");

  document.getElementById("btn-signout")?.addEventListener("click", signOut);

  farmFormToggle?.addEventListener("click", () => {
    farmFormWrap.classList.toggle("hidden");
    farmFormError.classList.add("hidden");
  });
  farmFormCancel?.addEventListener("click", () => farmFormWrap.classList.add("hidden"));
  farmForm?.addEventListener("submit", handleSaveFarm);

  plotFormToggle?.addEventListener("click", () => {
    if (!_activeFarmId) {
      showError(t("plot.error.noFarm"));
      return;
    }
    plotFormWrap.classList.toggle("hidden");
    plotFormError.classList.add("hidden");
  });
  plotFormCancel?.addEventListener("click", () => plotFormWrap.classList.add("hidden"));
  plotForm?.addEventListener("submit", handleSavePlot);

  historyClose?.addEventListener("click", () => historyModal.classList.add("hidden"));
  historyModal?.addEventListener("click", (e) => {
    if (e.target === historyModal) historyModal.classList.add("hidden");
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") historyModal?.classList.add("hidden");
  });

  document.documentElement.lang = getLang();
  await loadFarms();
});
