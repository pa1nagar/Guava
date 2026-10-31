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
 * Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.7, 4.8
 */

import { routeGuard, signOut } from "./auth.js";
import { apiFetch, showError, loadCached, saveCache } from "./api.js";

// ── State ─────────────────────────────────────────────────────────────────────
let _farms = [];
let _activeFarmId = null;
let _plots = [];

// ── i18n helper ───────────────────────────────────────────────────────────────
function t(key) {
  const el = document.querySelector(`[data-i18n="${key}"]`);
  return el ? el.textContent : key;
}

// ── DOM refs ──────────────────────────────────────────────────────────────────
const farmList        = document.getElementById("farm-list");
const farmListEmpty   = document.getElementById("farm-list-empty");
const farmListLoading = document.getElementById("farm-list-loading");
const plotsSection    = document.getElementById("plots-section");
const plotList        = document.getElementById("plot-list");
const plotListEmpty   = document.getElementById("plot-list-empty");
const plotListLoading = document.getElementById("plot-list-loading");
const activeFarmName  = document.getElementById("active-farm-name");

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

function formatDate(isoStr) {
  if (!isoStr) return "—";
  const d = new Date(isoStr);
  return `${String(d.getDate()).padStart(2,"0")}/${String(d.getMonth()+1).padStart(2,"0")}/${d.getFullYear()}`;
}

function cropAgeMonths(plantingDate) {
  if (!plantingDate) return null;
  const now = new Date();
  const plant = new Date(plantingDate);
  return (now.getFullYear() - plant.getFullYear()) * 12
       + (now.getMonth() - plant.getMonth());
}

// ── Load farms ────────────────────────────────────────────────────────────────
async function loadFarms() {
  setLoading(farmListLoading, true);
  setLoading(farmList, false);
  setLoading(farmListEmpty, false);

  try {
    const res = await apiFetch("/api/farmers/me/farms");
    if (!res.ok) {
      showError("Failed to load farms. Please try again.");
      setLoading(farmListLoading, false);
      return;
    }
    _farms = await res.json();
    renderFarms();
  } catch (err) {
    showError("Could not connect to server. Please check your connection.");
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

  _farms.forEach(farm => {
    const card = document.createElement("div");
    card.className = "bg-white border border-gray-200 rounded-xl p-4 shadow-sm cursor-pointer hover:border-brand-secondary transition";
    card.setAttribute("data-farm-id", farm.id);
    card.innerHTML = `
      <div class="flex items-start justify-between gap-3">
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 flex-wrap">
            <h3 class="font-bold text-emerald-900 text-base truncate">${escapeHtml(farm.name)}</h3>
            ${farm.is_active === false
              ? '<span class="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">Archived</span>'
              : '<span class="text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full">Active</span>'}
          </div>
          <p class="text-sm text-gray-500 mt-0.5 truncate">
            ${[farm.village, farm.district, farm.state].filter(Boolean).join(", ") || "—"}
          </p>
          ${farm.area ? `<p class="text-xs text-gray-400 mt-1">${escapeHtml(String(farm.area))} ${escapeHtml(farm.area_unit || "")}</p>` : ""}
        </div>
        <div class="flex gap-2 flex-shrink-0">
          <button class="btn-select-farm text-xs font-semibold text-brand-secondary border border-brand-secondary px-3 py-1.5 rounded-lg hover:bg-brand-secondary hover:text-white transition"
            data-farm-id="${farm.id}" data-i18n-btn="farm.viewPlots">
            View Plots
          </button>
          ${farm.is_active !== false ? `
          <button class="btn-archive-farm text-xs font-semibold text-gray-400 border border-gray-300 px-3 py-1.5 rounded-lg hover:bg-gray-100 transition"
            data-farm-id="${farm.id}" data-farm-name="${escapeHtml(farm.name)}" data-i18n-btn="farm.archive">
            Archive
          </button>` : ""}
        </div>
      </div>
    `;
    farmList.appendChild(card);
  });

  // Bind events
  farmList.querySelectorAll(".btn-select-farm").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const id = btn.getAttribute("data-farm-id");
      selectFarm(id);
    });
  });
  farmList.querySelectorAll(".btn-archive-farm").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      archiveFarm(btn.getAttribute("data-farm-id"), btn.getAttribute("data-farm-name"));
    });
  });
}

// ── Select farm → load plots ──────────────────────────────────────────────────
async function selectFarm(farmId) {
  _activeFarmId = farmId;
  const farm = _farms.find(f => f.id === farmId);
  if (activeFarmName) {
    activeFarmName.textContent = farm ? farm.name : "";
  }

  plotsSection.classList.remove("hidden");
  plotsSection.scrollIntoView({ behavior: "smooth", block: "start" });

  setLoading(plotListLoading, true);
  setLoading(plotListEmpty, false);
  plotList.innerHTML = "";

  try {
    const res = await apiFetch(`/api/farmers/me/farms/${farmId}/plots`);
    if (!res.ok) {
      showError("Failed to load plots.");
      return;
    }
    _plots = await res.json();
    renderPlots();
  } catch {
    showError("Could not load plots. Please try again.");
  } finally {
    setLoading(plotListLoading, false);
  }
}

function renderPlots() {
  plotList.innerHTML = "";
  if (!_plots || _plots.length === 0) {
    setLoading(plotListEmpty, true);
    return;
  }
  setLoading(plotListEmpty, false);

  _plots.forEach(plot => {
    const ageMonths = cropAgeMonths(plot.planting_date);
    const card = document.createElement("div");
    card.className = "bg-white border border-gray-200 rounded-xl p-4 shadow-sm";
    card.innerHTML = `
      <div class="flex items-start justify-between gap-3">
        <div class="flex-1 min-w-0">
          <h4 class="font-bold text-emerald-900">${escapeHtml(plot.name)}</h4>
          <p class="text-sm text-gray-500 mt-0.5">
            ${escapeHtml(plot.crop || "—")}
            ${plot.variety ? " · " + escapeHtml(plot.variety) : ""}
          </p>
          <div class="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-gray-500">
            ${plot.planting_date
              ? `<span>🌱 Planted: ${formatDate(plot.planting_date)}</span>`
              : ""}
            ${ageMonths !== null && ageMonths >= 0
              ? `<span>🗓️ Age: ${ageMonths} months</span>`
              : ""}
            ${plot.plant_count
              ? `<span>🌿 Plants: ${Number(plot.plant_count).toLocaleString("en-IN")}</span>`
              : ""}
            ${plot.area
              ? `<span>📐 Area: ${plot.area} ${plot.area_unit || ""}</span>`
              : ""}
          </div>
        </div>
        <button class="btn-plant-history text-xs text-brand-secondary underline flex-shrink-0"
          data-plot-id="${plot.id}" data-i18n-btn="plot.plantHistory">
          Count history
        </button>
      </div>
    `;
    plotList.appendChild(card);
  });

  plotList.querySelectorAll(".btn-plant-history").forEach(btn => {
    btn.addEventListener("click", () => loadPlantCountHistory(btn.getAttribute("data-plot-id")));
  });
}

// ── Archive farm ──────────────────────────────────────────────────────────────
async function archiveFarm(farmId, farmName) {
  if (!confirm(`Archive "${farmName}"? It will be hidden but all records are preserved.`)) return;

  try {
    const res = await apiFetch(`/api/farmers/me/farms/${farmId}/archive`, { method: "DELETE" });
    if (!res.ok) {
      showError("Failed to archive farm.");
      return;
    }
    await loadFarms();
    if (_activeFarmId === farmId) {
      _activeFarmId = null;
      plotsSection.classList.add("hidden");
    }
  } catch {
    showError("Could not archive farm. Please try again.");
  }
}

// ── Plant count history ───────────────────────────────────────────────────────
async function loadPlantCountHistory(plotId) {
  historyList.innerHTML = `<div class="loading-overlay"><span class="loading-spinner loading-spinner--sm"></span> Loading…</div>`;
  historyModal.classList.remove("hidden");

  try {
    const res = await apiFetch(`/api/farmers/me/farms/${_activeFarmId}/plots/${plotId}/plant-count-history`);
    if (!res.ok) {
      historyList.innerHTML = `<p class="text-sm text-red-600 p-4">Failed to load history.</p>`;
      return;
    }
    const rows = await res.json();
    if (!rows || rows.length === 0) {
      historyList.innerHTML = `<p class="text-sm text-gray-500 p-4" data-i18n="plot.noHistory">No count changes recorded yet.</p>`;
      return;
    }
    historyList.innerHTML = rows.map(row => `
      <div class="flex items-center justify-between py-2 border-b border-gray-100 last:border-0 text-sm">
        <span class="text-gray-500">${formatDate(row.changed_at)}</span>
        <span class="text-gray-700">${Number(row.prior_count).toLocaleString("en-IN")} → <strong class="text-emerald-800">${Number(row.new_count).toLocaleString("en-IN")}</strong></span>
        ${row.note ? `<span class="text-gray-400 text-xs ml-2">${escapeHtml(row.note)}</span>` : ""}
      </div>
    `).join("");
  } catch {
    historyList.innerHTML = `<p class="text-sm text-red-600 p-4">Could not load history.</p>`;
  }
}

// ── Create farm ───────────────────────────────────────────────────────────────
async function handleSaveFarm(e) {
  e.preventDefault();
  farmFormError.classList.add("hidden");
  farmFormBtn.disabled = true;
  farmFormBtn.textContent = "Saving…";

  const body = {
    name:            document.getElementById("farm-name").value.trim(),
    village:         document.getElementById("farm-village").value.trim() || null,
    district:        document.getElementById("farm-district").value.trim() || null,
    state:           document.getElementById("farm-state").value.trim() || null,
    country:         document.getElementById("farm-country").value.trim() || "India",
    area:            parseFloat(document.getElementById("farm-area").value) || null,
    area_unit:       document.getElementById("farm-area-unit").value || null,
    irrigation_method: document.getElementById("farm-irrigation").value.trim() || null,
    notes:           document.getElementById("farm-notes").value.trim() || null,
  };

  if (!body.name) {
    farmFormError.textContent = "Farm name is required.";
    farmFormError.classList.remove("hidden");
    farmFormBtn.disabled = false;
    farmFormBtn.textContent = "Save Farm";
    return;
  }

  try {
    const res = await apiFetch("/api/farmers/me/farms", {
      method: "POST",
      body: JSON.stringify(body),
    });

    if (res.status === 422) {
      const data = await res.json();
      farmFormError.textContent = data.detail || "Validation error. Check the form fields.";
      farmFormError.classList.remove("hidden");
      return;
    }
    if (!res.ok) {
      farmFormError.textContent = "Failed to create farm. Please try again.";
      farmFormError.classList.remove("hidden");
      return;
    }

    farmForm.reset();
    farmFormWrap.classList.add("hidden");
    await loadFarms();
  } catch {
    farmFormError.textContent = "Network error. Please try again.";
    farmFormError.classList.remove("hidden");
  } finally {
    farmFormBtn.disabled = false;
    farmFormBtn.textContent = "Save Farm";
  }
}

// ── Create plot ───────────────────────────────────────────────────────────────
async function handleSavePlot(e) {
  e.preventDefault();
  plotFormError.classList.add("hidden");
  plotFormBtn.disabled = true;
  plotFormBtn.textContent = "Saving…";

  const plantingDateVal = document.getElementById("plot-planting-date").value;

  // Client-side future-date guard (requirement 4.5)
  if (plantingDateVal) {
    const plantingDate = new Date(plantingDateVal);
    if (plantingDate > new Date()) {
      plotFormError.textContent = "Planting date cannot be in the future.";
      plotFormError.classList.remove("hidden");
      plotFormBtn.disabled = false;
      plotFormBtn.textContent = "Save Plot";
      return;
    }
  }

  const body = {
    name:           document.getElementById("plot-name").value.trim(),
    crop:           document.getElementById("plot-crop").value.trim() || null,
    variety:        document.getElementById("plot-variety").value.trim() || null,
    planting_date:  plantingDateVal || null,
    area:           parseFloat(document.getElementById("plot-area").value) || null,
    area_unit:      document.getElementById("plot-area-unit").value || null,
    plant_count:    parseInt(document.getElementById("plot-plant-count").value) || null,
    row_spacing_m:  parseFloat(document.getElementById("plot-row-spacing").value) || null,
    within_row_spacing_m: parseFloat(document.getElementById("plot-within-row-spacing").value) || null,
    notes:          document.getElementById("plot-notes").value.trim() || null,
  };

  if (!body.name) {
    plotFormError.textContent = "Plot name is required.";
    plotFormError.classList.remove("hidden");
    plotFormBtn.disabled = false;
    plotFormBtn.textContent = "Save Plot";
    return;
  }

  if (!_activeFarmId) {
    plotFormError.textContent = "No farm selected. Please select a farm first.";
    plotFormError.classList.remove("hidden");
    plotFormBtn.disabled = false;
    plotFormBtn.textContent = "Save Plot";
    return;
  }

  try {
    const res = await apiFetch(`/api/farmers/me/farms/${_activeFarmId}/plots`, {
      method: "POST",
      body: JSON.stringify(body),
    });

    if (res.status === 422) {
      const data = await res.json();
      // Server validates future date too (requirement 4.5)
      const detail = data.detail;
      if (typeof detail === "string") {
        plotFormError.textContent = detail;
      } else if (Array.isArray(detail)) {
        plotFormError.textContent = detail.map(d => d.msg).join(". ");
      } else {
        plotFormError.textContent = "Validation error. Check the form fields.";
      }
      plotFormError.classList.remove("hidden");
      return;
    }
    if (!res.ok) {
      plotFormError.textContent = "Failed to create plot. Please try again.";
      plotFormError.classList.remove("hidden");
      return;
    }

    plotForm.reset();
    plotFormWrap.classList.add("hidden");
    await selectFarm(_activeFarmId);
  } catch {
    plotFormError.textContent = "Network error. Please try again.";
    plotFormError.classList.remove("hidden");
  } finally {
    plotFormBtn.disabled = false;
    plotFormBtn.textContent = "Save Plot";
  }
}

// ── XSS guard ─────────────────────────────────────────────────────────────────
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// ── Initialise ────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  await routeGuard("farm");

  // Sign out button
  document.getElementById("btn-signout")?.addEventListener("click", signOut);

  // Farm form toggle
  farmFormToggle?.addEventListener("click", () => {
    farmFormWrap.classList.toggle("hidden");
    farmFormError.classList.add("hidden");
    farmForm.reset();
  });
  farmFormCancel?.addEventListener("click", () => farmFormWrap.classList.add("hidden"));
  farmForm?.addEventListener("submit", handleSaveFarm);

  // Plot form toggle
  plotFormToggle?.addEventListener("click", () => {
    if (!_activeFarmId) {
      showError("Select a farm first before adding a plot.");
      return;
    }
    plotFormWrap.classList.toggle("hidden");
    plotFormError.classList.add("hidden");
    plotForm.reset();
  });
  plotFormCancel?.addEventListener("click", () => plotFormWrap.classList.add("hidden"));
  plotForm?.addEventListener("submit", handleSavePlot);

  // Plant count history modal close
  historyClose?.addEventListener("click", () => historyModal.classList.add("hidden"));
  historyModal?.addEventListener("click", (e) => {
    if (e.target === historyModal) historyModal.classList.add("hidden");
  });

  await loadFarms();
});
