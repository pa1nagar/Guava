/**
 * observations.js — Crop health observation form with photo upload and AI label display.
 *
 * Handles:
 *  - GET  /api/farmers/me/observations        → observation list
 *  - POST /api/farmers/me/observations        → create observation
 *  - POST /api/farmers/me/observations/{id}/photos  → upload photo (multipart field "file")
 *
 * AI analysis label is ALWAYS shown as "Preliminary observation — not a diagnosis"
 * (Requirement 7.3).
 *
 * Requirements: 7.1, 7.2, 7.3, 7.4
 */

import { routeGuard, signOut } from "./auth.js";
import { apiFetch, showError } from "./api.js";
import {
  applyI18n, errorMessage, escapeHtml, initPage, renderLoadError, setBusy, t,
} from "./dom.js";
import { formatDate, formatNumber } from "./translator.js";

const MAX_PHOTO_BYTES = 10 * 1024 * 1024; // backend limit (observations.py _MAX_PHOTO_BYTES)
const ALLOWED_PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"];

// ── State ─────────────────────────────────────────────────────────────────────
let _observations = [];

// ── DOM refs ──────────────────────────────────────────────────────────────────
const obsList      = document.getElementById("obs-list");
const obsListEmpty = document.getElementById("obs-list-empty");
const obsLoading   = document.getElementById("obs-loading");

const obsFormWrap  = document.getElementById("obs-form-wrap");
const obsFormBtn   = document.getElementById("btn-show-obs-form");
const obsCancel    = document.getElementById("btn-cancel-obs-form");
const obsForm      = document.getElementById("obs-form");
const obsFormError = document.getElementById("obs-form-error");
const obsSaveBtn   = document.getElementById("btn-save-obs");

// Photo upload
const photoInput    = document.getElementById("obs-photo");
const photoPreview  = document.getElementById("obs-photo-preview");
const photoLabel    = document.getElementById("obs-photo-label");
const photoError    = document.getElementById("obs-photo-error");

// ── Utilities ─────────────────────────────────────────────────────────────────
function setHidden(el, hidden) {
  if (el) el.classList.toggle("hidden", hidden);
}

function showFormError(message) {
  obsFormError.textContent = message;
  obsFormError.classList.remove("hidden");
}

function showPhotoError(message) {
  if (!photoError) return;
  photoError.textContent = message || "";
  photoError.classList.toggle("hidden", !message);
}

function todayIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// ── Severity badge ────────────────────────────────────────────────────────────
function severityBadge(severity) {
  const map = {
    low:     { cls: "bg-green-100 text-green-800", key: "obs.severity.low" },
    medium:  { cls: "bg-amber-100 text-amber-800", key: "obs.severity.medium" },
    high:    { cls: "bg-red-100 text-red-800",     key: "obs.severity.high" },
    unknown: { cls: "bg-gray-100 text-gray-700",   key: "obs.severity.unknown" },
  };
  const m = map[String(severity || "").toLowerCase()] || map.unknown;
  return `<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-sm font-semibold ${m.cls}">${escapeHtml(t(m.key))}</span>`;
}

// ── Render observations ───────────────────────────────────────────────────────
function renderObservations() {
  setHidden(obsLoading, true);
  obsList.innerHTML = "";

  if (!_observations || _observations.length === 0) {
    setHidden(obsListEmpty, false);
    return;
  }
  setHidden(obsListEmpty, true);

  _observations.forEach((obs) => {
    const card = document.createElement("div");
    card.className = "bg-white border border-gray-200 rounded-xl p-4 shadow-sm";
    card.innerHTML = `
      <div class="min-w-0 mb-2">
        <div class="flex flex-wrap items-center gap-2 mb-1">
          <span class="text-sm font-semibold text-gray-600">${escapeHtml(formatDate(obs.observed_date || obs.created_at))}</span>
          ${severityBadge(obs.severity)}
        </div>
        <p class="font-semibold text-emerald-900 text-base break-words">
          ${escapeHtml(obs.symptom_description || t("obs.defaultTitle"))}
        </p>
        <div class="flex flex-wrap gap-x-4 gap-y-0.5 mt-1 text-sm text-gray-600">
          ${obs.plot_name ? `<span>🌿 ${escapeHtml(obs.plot_name)}</span>` : ""}
          ${obs.plant_part ? `<span>🔍 ${escapeHtml(obs.plant_part)}</span>` : ""}
          ${obs.trees_affected != null
            ? `<span>🌳 ${escapeHtml(t("obs.treesAffectedCount", { n: formatNumber(obs.trees_affected) }))}</span>` : ""}
        </div>
      </div>

      ${obs.photos && obs.photos.length > 0 ? `
        <div class="flex gap-2 mt-2 flex-wrap">
          ${obs.photos.slice(0, 3).map((p) => `
            <img src="${escapeHtml(p.signed_url || "")}" alt="${escapeHtml(t("obs.photoAlt"))}" loading="lazy"
              class="w-16 h-16 object-cover rounded-lg border border-gray-200">
          `).join("")}
        </div>
      ` : ""}

      ${obs.ai_analysis_label || obs.ai_analysis ? `
        <div class="mt-3 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2.5">
          <p class="text-sm font-bold text-amber-900 mb-1">⚠️ ${escapeHtml(obs.ai_analysis_label || t("obs.ai.label"))}</p>
          ${obs.ai_analysis ? `<p class="text-sm text-gray-800 leading-relaxed break-words">${escapeHtml(obs.ai_analysis)}</p>` : ""}
          <p class="text-sm text-amber-800 mt-1.5" data-i18n="obs.aiDisclaimerBody"></p>
        </div>
      ` : ""}
    `;
    obsList.appendChild(card);
  });
  applyI18n(obsList);
}

// ── Load observations ─────────────────────────────────────────────────────────
async function loadObservations() {
  setHidden(obsLoading, false);
  setHidden(obsListEmpty, true);
  obsList.innerHTML = "";

  try {
    const res = await apiFetch("/api/farmers/me/observations");
    if (!res.ok) {
      setHidden(obsLoading, true);
      renderLoadError(obsList, loadObservations);
      return;
    }
    _observations = await res.json();
    renderObservations();
  } catch {
    setHidden(obsLoading, true);
    renderLoadError(obsList, loadObservations, "common.error.network");
  }
}

// ── Upload photo after observation is created ─────────────────────────────────
// Returns "" on success or a plain-language message on failure.
async function uploadPhoto(obsId, file) {
  const formData = new FormData();
  formData.append("file", file); // backend parameter name is "file"

  try {
    const res = await apiFetch(`/api/farmers/me/observations/${encodeURIComponent(obsId)}/photos`, {
      method: "POST",
      headers: {}, // let the browser set the multipart boundary
      body: formData,
    });
    if (res.ok) return "";
    let detail = "";
    try { detail = String((await res.clone().json()).detail || ""); } catch { /* not JSON */ }
    if (res.status === 422 && /maximum size/i.test(detail)) return t("obs.photo.tooBig");
    if (res.status === 422 && /JPEG|PNG|WEBP/i.test(detail)) return t("obs.photo.badType");
    if (res.status === 422) return t("obs.photo.unreadable");
    return t("obs.photo.failed");
  } catch {
    return t("obs.photo.failed");
  }
}

// ── Photo input preview ───────────────────────────────────────────────────────
function resetPhoto() {
  if (photoInput) photoInput.value = "";
  if (photoPreview) { photoPreview.removeAttribute("src"); setHidden(photoPreview, true); }
  if (photoLabel) photoLabel.textContent = t("obs.choosePhoto");
  showPhotoError("");
}

function setupPhotoPreview() {
  photoInput?.addEventListener("change", () => {
    showPhotoError("");
    const file = photoInput.files[0];
    if (!file) { resetPhoto(); return; }
    if (file.size > MAX_PHOTO_BYTES) {
      resetPhoto();
      showPhotoError(t("obs.photo.tooBig"));
      return;
    }
    if (!ALLOWED_PHOTO_TYPES.includes(file.type)) {
      resetPhoto();
      showPhotoError(t("obs.photo.badType"));
      return;
    }
    if (photoLabel) photoLabel.textContent = file.name;
    const reader = new FileReader();
    reader.onload = () => {
      photoPreview.src = reader.result;
      setHidden(photoPreview, false);
    };
    reader.readAsDataURL(file);
  });
}

// ── Create observation ────────────────────────────────────────────────────────
async function handleSaveObservation(e) {
  e.preventDefault();
  obsFormError.classList.add("hidden");

  const val = (id) => document.getElementById(id).value.trim();
  const int = (id) => {
    const n = parseInt(document.getElementById(id).value, 10);
    return Number.isNaN(n) ? null : n;
  };
  const body = {
    observed_date:       document.getElementById("obs-date").value || null,
    symptom_description: val("obs-symptom") || "unknown / not sure",
    plant_part:          val("obs-plant-part") || null,
    severity:            document.getElementById("obs-severity").value || null,
    trees_sampled:       int("obs-trees-sampled"),
    trees_affected:      int("obs-trees-affected"),
    spread_pattern:      val("obs-spread") || null,
    weather_notes:       val("obs-weather-notes") || null, // backend field name
    recent_input_notes:  val("obs-input-notes") || null,
    observer_name:       val("obs-observer") || null,
  };

  const plotIdEl = document.getElementById("obs-plot-id");
  if (plotIdEl && plotIdEl.value) body.plot_id = plotIdEl.value;

  if (!body.observed_date) {
    showFormError(t("obs.error.dateRequired"));
    return;
  }
  if (body.trees_sampled != null && body.trees_affected != null && body.trees_affected > body.trees_sampled) {
    showFormError(t("obs.error.affectedMoreThanSampled"));
    return;
  }

  setBusy(obsSaveBtn, true);
  try {
    const res = await apiFetch("/api/farmers/me/observations", { method: "POST", body: JSON.stringify(body) });
    if (!res.ok) {
      showFormError(await errorMessage(res));
      return;
    }
    const saved = await res.json();

    // Upload the photo if one was selected. The observation is already saved, so a
    // photo failure keeps the form open with a clear message instead of losing data.
    const file = photoInput?.files?.[0];
    if (file && saved?.id) {
      const problem = await uploadPhoto(saved.id, file);
      if (problem) showError(`${t("obs.photo.savedWithoutPhoto")} ${problem}`);
    }

    obsForm.reset();
    resetPhoto();
    obsFormWrap.classList.add("hidden");
    await loadObservations();
  } catch {
    showFormError(t("common.error.network"));
  } finally {
    setBusy(obsSaveBtn, false);
  }
}

// ── Initialise ────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  initPage();
  await routeGuard("farm"); // observations page uses 'farm' guard

  document.getElementById("btn-signout")?.addEventListener("click", signOut);

  obsFormBtn?.addEventListener("click", () => {
    obsFormWrap.classList.toggle("hidden");
    obsFormError.classList.add("hidden");
    const dateEl = document.getElementById("obs-date");
    if (dateEl && !dateEl.value) dateEl.value = todayIso();
  });
  obsCancel?.addEventListener("click", () => obsFormWrap.classList.add("hidden"));
  obsForm?.addEventListener("submit", handleSaveObservation);

  setupPhotoPreview();
  await loadObservations();
});
