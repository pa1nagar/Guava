/**
 * onboarding.js — First-time farmer form logic.
 *
 * Responsibilities:
 *  - Route guard (redirect to login when signed out)
 *  - Populate State dropdown (launch states only) from india-locations.js
 *  - Cascade District dropdown on State change
 *  - Client-side validation (plant count, future sowing date, optional yield)
 *  - POST to /api/profile with JWT, show backend 4xx messages in plain words
 *  - Redirect to plan.html on success
 *
 * All text goes through t() / data-i18n (EN and HI, js/i18n-public.js).
 * The sign-in library comes from a CDN, so auth.js and api.js are imported
 * inside try/catch: if they cannot load, the page shows a message, not a blank screen.
 */

import { getStates, getDistricts } from "./india-locations.js";
import { initPage, t, errorMessage, setBusy } from "./dom.js";
import { setLanguage } from "./translator.js";

// States offered at launch (the repo data has all states; the backend and mandi data target these two).
const LAUNCH_STATES = ["Madhya Pradesh", "Maharashtra"];

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

let apiFetch = null;

function showFormError(text) {
  formError.textContent = text;
  formError.classList.remove("hidden");
}

function fieldError(el, key) {
  el.textContent = t(key);
  el.classList.remove("hidden");
}

function resetDistricts() {
  const selected = stateEl.value;
  districtEl.replaceChildren();
  const first = document.createElement("option");
  first.value = "";
  first.setAttribute("data-i18n", "onb.district.placeholder");
  first.textContent = t("onb.district.placeholder");
  districtEl.appendChild(first);
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
  districtEl.value = "";
}

function fillStates() {
  const known = new Set(getStates());
  for (const state of LAUNCH_STATES.filter((s) => known.has(s))) {
    const opt = document.createElement("option");
    opt.value = state;
    opt.textContent = state;
    stateEl.appendChild(opt);
  }
}

// ── Initialise ────────────────────────────────────────────────────────────────
async function start() {
  initPage();
  document.getElementById("lang-en").addEventListener("click", () => setLanguage("en"));
  document.getElementById("lang-hi").addEventListener("click", () => setLanguage("hi"));

  // Default sowing date to today (local date, not UTC).
  const now = new Date();
  sowingEl.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  sowingEl.max = sowingEl.value;
  fillStates();

  try {
    const [auth, api] = await Promise.all([import("./auth.js"), import("./api.js")]);
    apiFetch = api.apiFetch;
    await auth.routeGuard("onboarding");
  } catch (_) {
    btnSubmit.disabled = true;
    showFormError(t("onb.err.unreachable"));
  }
}

// ── State → District cascade ──────────────────────────────────────────────────
stateEl.addEventListener("change", resetDistricts);

// ── Form submission ───────────────────────────────────────────────────────────
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!apiFetch) {
    showFormError(t("onb.err.unreachable"));
    return;
  }

  for (const el of [plantCountErr, sowingErr, yieldErr, formError]) {
    el.textContent = "";
    el.classList.add("hidden");
  }

  const plantCount = Number(plantCountEl.value);
  if (!plantCountEl.value || !Number.isInteger(plantCount) || plantCount < 1) {
    fieldError(plantCountErr, "onb.err.plantCount");
    plantCountEl.focus();
    return;
  }
  if (!stateEl.value) {
    showFormError(t("onb.err.state"));
    stateEl.focus();
    return;
  }
  if (!districtEl.value) {
    showFormError(t("onb.err.district"));
    districtEl.focus();
    return;
  }

  const sowingValue = sowingEl.value;
  if (!sowingValue) {
    fieldError(sowingErr, "onb.err.date");
    sowingEl.focus();
    return;
  }
  // Compare calendar dates (YYYY-MM-DD strings sort correctly) to avoid timezone false positives.
  if (sowingValue > sowingEl.max) {
    fieldError(sowingErr, "onb.err.dateFuture");
    sowingEl.focus();
    return;
  }

  let expectedYieldKg = null;
  if (yieldEl.value.trim() !== "") {
    const parsed = Number(yieldEl.value);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      fieldError(yieldErr, "onb.err.yield");
      yieldEl.focus();
      return;
    }
    expectedYieldKg = parsed;
  }

  // Submit disabled while saving.
  setBusy(btnSubmit, true);
  formLoading.classList.remove("hidden");

  try {
    const res = await apiFetch("/api/profile", {
      method: "POST",
      body: JSON.stringify({
        crop: cropEl.value,
        plant_count: plantCount,
        state: stateEl.value,
        district: districtEl.value,
        sowing_date: sowingValue,
        expected_yield_kg: expectedYieldKg,
      }),
    });
    if (res.ok) {
      sessionStorage.removeItem("sf_onboarding_draft");
      window.location.href = "plan.html";
      return;
    }
    // Field values are kept on failure so the farmer can correct and retry.
    showFormError(await errorMessage(res));
  } catch (_) {
    showFormError(t("onb.err.network"));
  } finally {
    setBusy(btnSubmit, false);
    formLoading.classList.add("hidden");
  }
});

start();
