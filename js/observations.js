/**
 * observations.js — Crop health observation form with photo upload and AI label display.
 *
 * Handles:
 *  - GET  /api/farmers/me/observations        → observation list
 *  - POST /api/farmers/me/observations        → create observation
 *  - POST /api/farmers/me/observations/{id}/photos  → upload photo
 *
 * AI analysis label is ALWAYS shown as "Preliminary observation — not a diagnosis"
 * (Requirement 7.3).
 *
 * Requirements: 7.1, 7.2, 7.3, 7.4
 */

import { routeGuard, signOut } from "./auth.js";
import { apiFetch, showError } from "./api.js";

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

// ── Utilities ─────────────────────────────────────────────────────────────────
function setHidden(el, hidden) {
  if (el) el.classList.toggle("hidden", hidden);
}

function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatDate(isoStr) {
  if (!isoStr) return "—";
  const d = new Date(isoStr);
  return `${String(d.getDate()).padStart(2,"0")}/${String(d.getMonth()+1).padStart(2,"0")}/${d.getFullYear()}`;
}

// ── Severity badge ────────────────────────────────────────────────────────────
function severityBadge(severity) {
  const map = {
    low:      { bg: "bg-green-100",  text: "text-green-700",  label: "Low" },
    medium:   { bg: "bg-amber-100",  text: "text-amber-700",  label: "Medium" },
    high:     { bg: "bg-red-100",    text: "text-red-700",    label: "High" },
    unknown:  { bg: "bg-gray-100",   text: "text-gray-600",   label: "Unknown" },
  };
  const m = map[severity?.toLowerCase()] || map.unknown;
  return `<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${m.bg} ${m.text}">
    ${escapeHtml(m.label)}
  </span>`;
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

  _observations.forEach(obs => {
    const card = document.createElement("div");
    card.className = "bg-white border border-gray-200 rounded-xl p-4 shadow-sm";
    card.innerHTML = `
      <div class="flex items-start justify-between gap-3 mb-2">
        <div class="flex-1 min-w-0">
          <div class="flex flex-wrap items-center gap-2 mb-1">
            <span class="text-xs font-semibold text-gray-500">${formatDate(obs.observed_date || obs.created_at)}</span>
            ${severityBadge(obs.severity)}
          </div>
          <p class="font-semibold text-emerald-900 text-sm">
            ${escapeHtml(obs.symptom_description || "Observation")}
          </p>
          <div class="flex flex-wrap gap-x-4 gap-y-0.5 mt-1 text-xs text-gray-400">
            ${obs.plot_name ? `<span>🌿 ${escapeHtml(obs.plot_name)}</span>` : ""}
            ${obs.plant_part ? `<span>🔍 ${escapeHtml(obs.plant_part)}</span>` : ""}
            ${obs.trees_affected != null ? `<span>🌳 ${Number(obs.trees_affected).toLocaleString("en-IN")} trees affected</span>` : ""}
          </div>
        </div>
      </div>

      ${obs.photos && obs.photos.length > 0 ? `
        <div class="flex gap-2 mt-2 flex-wrap">
          ${obs.photos.slice(0, 3).map(p => `
            <img src="${escapeHtml(p.signed_url || '')}"
              alt="Observation photo"
              class="w-16 h-16 object-cover rounded-lg border border-gray-200">
          `).join("")}
        </div>
      ` : ""}

      ${obs.ai_analysis_label || obs.ai_analysis ? `
        <div class="mt-3 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2.5">
          <p class="text-xs font-bold text-amber-800 mb-1">
            ⚠️ Preliminary observation — not a diagnosis
          </p>
          ${obs.ai_analysis ? `<p class="text-xs text-gray-700 leading-relaxed">${escapeHtml(obs.ai_analysis)}</p>` : ""}
          <p class="text-xs text-amber-600 mt-1.5">
            If symptoms are severe or spreading rapidly, consult your local KVK, agronomist, or official lab.
          </p>
        </div>
      ` : ""}
    `;
    obsList.appendChild(card);
  });
}

// ── Load observations ─────────────────────────────────────────────────────────
async function loadObservations() {
  setHidden(obsLoading, false);
  setHidden(obsListEmpty, true);
  obsList.innerHTML = "";

  try {
    const res = await apiFetch("/api/farmers/me/observations");
    if (!res.ok) {
      showError("Failed to load observations.");
      setHidden(obsLoading, true);
      return;
    }
    _observations = await res.json();
    renderObservations();
  } catch {
    showError("Could not connect to server.");
    setHidden(obsLoading, true);
  }
}

// ── Upload photo after observation is created ─────────────────────────────────
async function uploadPhoto(obsId, file) {
  const formData = new FormData();
  formData.append("photo", file);

  try {
    const res = await apiFetch(`/api/farmers/me/observations/${obsId}/photos`, {
      method: "POST",
      headers: {}, // Let the browser set Content-Type with boundary for multipart
      body: formData,
    });
    if (!res.ok) {
      showError("Observation saved but photo upload failed. You can upload later.");
    }
  } catch {
    showError("Observation saved but photo could not be uploaded.");
  }
}

// ── Photo input preview ───────────────────────────────────────────────────────
function setupPhotoPreview() {
  photoInput?.addEventListener("change", () => {
    const file = photoInput.files[0];
    if (!file) {
      photoPreview.src = "";
      setHidden(photoPreview, true);
      if (photoLabel) photoLabel.textContent = "Choose photo";
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      showError("Photo must be 10 MB or smaller.");
      photoInput.value = "";
      return;
    }
    const allowed = ["image/jpeg", "image/png", "image/webp"];
    if (!allowed.includes(file.type)) {
      showError("Only JPEG, PNG, or WebP photos are accepted.");
      photoInput.value = "";
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
  obsSaveBtn.disabled = true;
  obsSaveBtn.textContent = "Saving…";

  const body = {
    observed_date:       document.getElementById("obs-date").value || null,
    symptom_description: document.getElementById("obs-symptom").value.trim() || "unknown / not sure",
    plant_part:          document.getElementById("obs-plant-part").value.trim() || null,
    severity:            document.getElementById("obs-severity").value || null,
    trees_sampled:       parseInt(document.getElementById("obs-trees-sampled").value) || null,
    trees_affected:      parseInt(document.getElementById("obs-trees-affected").value) || null,
    spread_pattern:      document.getElementById("obs-spread").value.trim() || null,
    recent_weather_notes: document.getElementById("obs-weather-notes").value.trim() || null,
    recent_input_notes:  document.getElementById("obs-input-notes").value.trim() || null,
    observer_name:       document.getElementById("obs-observer").value.trim() || null,
  };

  // plot_id if selected (optional)
  const plotIdEl = document.getElementById("obs-plot-id");
  if (plotIdEl && plotIdEl.value) body.plot_id = plotIdEl.value;

  if (!body.observed_date) {
    obsFormError.textContent = "Observation date is required.";
    obsFormError.classList.remove("hidden");
    obsSaveBtn.disabled = false;
    obsSaveBtn.textContent = "Save Observation";
    return;
  }

  try {
    const res = await apiFetch("/api/farmers/me/observations", {
      method: "POST",
      body: JSON.stringify(body),
    });

    if (res.status === 422) {
      const data = await res.json();
      const detail = data.detail;
      obsFormError.textContent = typeof detail === "string"
        ? detail : Array.isArray(detail)
        ? detail.map(d => d.msg).join(". ")
        : "Validation error. Check the form.";
      obsFormError.classList.remove("hidden");
      return;
    }
    if (!res.ok) {
      obsFormError.textContent = "Failed to save observation. Please try again.";
      obsFormError.classList.remove("hidden");
      return;
    }

    const saved = await res.json();

    // Upload photo if one was selected
    const file = photoInput?.files?.[0];
    if (file && saved?.id) {
      await uploadPhoto(saved.id, file);
    }

    obsForm.reset();
    photoPreview.src = "";
    setHidden(photoPreview, true);
    if (photoLabel) photoLabel.textContent = "Choose photo";
    obsFormWrap.classList.add("hidden");
    await loadObservations();
  } catch {
    obsFormError.textContent = "Network error. Please try again.";
    obsFormError.classList.remove("hidden");
  } finally {
    obsSaveBtn.disabled = false;
    obsSaveBtn.textContent = "Save Observation";
  }
}

// ── Initialise ────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  await routeGuard("farm"); // observations page uses 'farm' guard

  document.getElementById("btn-signout")?.addEventListener("click", signOut);

  obsFormBtn?.addEventListener("click", () => {
    obsFormWrap.classList.toggle("hidden");
    obsFormError.classList.add("hidden");
    obsForm.reset();
  });
  obsCancel?.addEventListener("click", () => obsFormWrap.classList.add("hidden"));
  obsForm?.addEventListener("submit", handleSaveObservation);

  setupPhotoPreview();
  await loadObservations();
});
