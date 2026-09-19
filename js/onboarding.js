/**
 * onboarding.js — First-time farmer form logic.
 *
 * Responsibilities:
 *  - Route guard (redirect away if already has a profile)
 *  - Populate State dropdown from india-locations.js
 *  - Cascade District dropdown on State change
 *  - Client-side validation (plant count, future sowing date)
 *  - POST to /api/profile with JWT
 *  - Redirect to plan.html on success
 */

import { routeGuard, getJwt } from "./auth.js";
import { getStates, getDistricts } from "./india-locations.js";
import { API_BASE_URL } from "./config.js";

// ── DOM refs ──────────────────────────────────────────────────────────────────
const form          = document.getElementById("onboarding-form");
const cropEl        = document.getElementById("crop");
const plantCountEl  = document.getElementById("plant-count");
const stateEl       = document.getElementById("state-select");
const districtEl    = document.getElementById("district-select");
const sowingEl      = document.getElementById("sowing-date");
const yieldEl       = document.getElementById("expected-yield");
const btnSubmit     = document.getElementById("btn-submit");
const formError     = document.getElementById("form-error");
const formLoading   = document.getElementById("form-loading");
const plantCountErr = document.getElementById("plant-count-error");
const sowingErr     = document.getElementById("sowing-date-error");
const yieldErr      = document.getElementById("yield-error");

// ── Initialise ────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  await routeGuard("onboarding");

  // Default sowing date to today.
  sowingEl.value = new Date().toISOString().split("T")[0];

  // Populate State dropdown.
  for (const state of getStates()) {
    const opt = document.createElement("option");
    opt.value = state;
    opt.textContent = state;
    stateEl.appendChild(opt);
  }
});

// ── State → District cascade ──────────────────────────────────────────────────
stateEl.addEventListener("change", () => {
  const selected = stateEl.value;

  // Clear current options.
  districtEl.innerHTML = '<option value="">Select district</option>';

  if (!selected) {
    districtEl.disabled = true;
    return;
  }

  for (const district of getDistricts(selected)) {
    const opt = document.createElement("option");
    opt.value = district;
    opt.textContent = district;
    districtEl.appendChild(opt);
  }

  districtEl.disabled = false;
  districtEl.value = ""; // reset to blank default
});

// ── Form submission ───────────────────────────────────────────────────────────
form.addEventListener("submit", async (e) => {
  e.preventDefault();

  // Clear previous errors.
  plantCountErr.textContent = "";
  plantCountErr.classList.add("hidden");
  sowingErr.textContent = "";
  sowingErr.classList.add("hidden");
  if (yieldErr) { yieldErr.textContent = ""; yieldErr.classList.add("hidden"); }
  formError.textContent = "";
  formError.classList.add("hidden");

  // ── Validate plant count ──────────────────────────────────────────────────
  const plantCount = parseInt(plantCountEl.value, 10);
  if (!plantCountEl.value || isNaN(plantCount) || plantCount < 1) {
    plantCountErr.textContent = "Number of plants must be at least 1.";
    plantCountErr.classList.remove("hidden");
    plantCountEl.focus();
    return;
  }

  // ── Validate sowing date (Req 2.5) ────────────────────────────────────────
  const sowingValue = sowingEl.value;
  if (!sowingValue) {
    sowingErr.textContent = "Please enter the planting date.";
    sowingErr.classList.remove("hidden");
    sowingEl.focus();
    return;
  }
  // Compare dates at midnight local time to avoid timezone-offset false positives.
  const sowingDate = new Date(sowingValue + "T00:00:00");
  const today      = new Date(new Date().toISOString().split("T")[0] + "T00:00:00");
  if (sowingDate > today) {
    sowingErr.textContent = "Planting date cannot be in the future.";
    sowingErr.classList.remove("hidden");
    sowingEl.focus();
    return;
  }

  // ── Show loading state ────────────────────────────────────────────────────
  btnSubmit.disabled = true;
  formLoading.classList.remove("hidden");

  // ── POST to backend ───────────────────────────────────────────────────────
  try {
    const jwt = await getJwt();

    // Parse optional expected yield.
    let expectedYieldKg = null;
    if (yieldEl && yieldEl.value.trim() !== "") {
      const parsed = parseFloat(yieldEl.value);
      if (isNaN(parsed) || parsed <= 0) {
        if (yieldErr) {
          yieldErr.textContent = "Expected harvest must be a positive number.";
          yieldErr.classList.remove("hidden");
        }
        btnSubmit.disabled = false;
        formLoading.classList.add("hidden");
        return;
      }
      expectedYieldKg = parsed;
    }

    const payload = {
      crop:             cropEl.value,
      plant_count:      plantCount,
      state:            stateEl.value,
      district:         districtEl.value,
      sowing_date:      sowingValue,
      expected_yield_kg: expectedYieldKg,
    };

    const res = await fetch(`${API_BASE_URL}/api/profile`, {
      method:  "POST",
      headers: {
        "Content-Type":  "application/json",
        "Authorization": `Bearer ${jwt}`,
      },
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      window.location.href = "plan.html";
      return;
    }

    // Handle error responses.
    let detail = "Something went wrong. Please try again.";
    try {
      const data = await res.json();
      if (res.status === 422 && data.detail) {
        detail = data.detail;
      }
    } catch (_) { /* ignore parse errors */ }

    formError.textContent = detail;
    formError.classList.remove("hidden");

  } catch (_) {
    formError.textContent = "Something went wrong. Please check your connection and try again.";
    formError.classList.remove("hidden");
  } finally {
    btnSubmit.disabled = false;
    formLoading.classList.add("hidden");
  }
});
