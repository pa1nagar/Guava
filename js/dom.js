/**
 * dom.js - small shared helpers for the signed-in app pages (no network, no auth).
 *
 *  - escapeHtml(v)        escape a value before putting it in an innerHTML template
 *  - t(key, vars)         translate a key for the current language ({{name}} placeholders)
 *  - applyI18n(root)      translate [data-i18n] elements inside root (used after dynamic renders)
 *  - initPage()           start the language engine (data-i18n on static HTML)
 *  - setBusy(btn, busy)   disable a submit button and show "Saving..." while a request runs
 *  - renderLoadError(el, retry)  friendly error state with a Retry button
 *  - errorMessage(res)    plain-language message for a failed API response (never raw exception text)
 */

import { TRANSLATIONS } from "./i18n.js";
import { init as initTranslator } from "./translator.js";

export function getLang() {
  try {
    return localStorage.getItem("sf_lang") === "hi" ? "hi" : "en";
  } catch {
    return "en";
  }
}

export function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function t(key, vars) {
  const table = TRANSLATIONS[getLang()] || {};
  if (table[key] === undefined) console.warn(`[i18n] Missing key: "${key}" for lang: "${getLang()}"`);
  let text = table[key] ?? TRANSLATIONS.en[key] ?? key;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      text = text.split(`{{${k}}}`).join(String(v ?? ""));
    }
  }
  return text;
}

export function applyI18n(root = document) {
  root.querySelectorAll("[data-i18n]").forEach((el) => {
    const v = TRANSLATIONS[getLang()]?.[el.getAttribute("data-i18n")];
    if (v !== undefined) el.textContent = v;
  });
  root.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    const v = TRANSLATIONS[getLang()]?.[el.getAttribute("data-i18n-placeholder")];
    if (v !== undefined) el.setAttribute("placeholder", v);
  });
  applyAria(root);
}

function applyAria(root) {
  root.querySelectorAll("[data-i18n-aria-label]").forEach((el) => {
    const v = TRANSLATIONS[getLang()]?.[el.getAttribute("data-i18n-aria-label")];
    if (v !== undefined) el.setAttribute("aria-label", v);
  });
}

export function initPage() {
  try {
    initTranslator();
  } catch {
    /* language engine is optional; pages still render in English */
  }
  applyAria(document);
}

export function setBusy(btn, busy) {
  if (!btn) return;
  if (busy) {
    if (btn.dataset.label === undefined) btn.dataset.label = btn.innerHTML;
    btn.disabled = true;
    btn.setAttribute("aria-busy", "true");
    btn.textContent = t("common.saving");
  } else {
    if (btn.dataset.label !== undefined) {
      btn.innerHTML = btn.dataset.label;
      delete btn.dataset.label;
    }
    btn.disabled = false;
    btn.removeAttribute("aria-busy");
  }
}

/** Replace container content with an error message and a Retry button that calls retry(). */
export function renderLoadError(container, retry, messageKey = "common.error.load") {
  if (!container) return;
  container.classList.remove("hidden");
  container.innerHTML =
    `<div class="load-error" role="alert">` +
    `<p class="load-error__text" data-i18n="${escapeHtml(messageKey)}">${escapeHtml(t(messageKey))}</p>` +
    `<button type="button" class="load-error__retry" data-i18n="common.retry">${escapeHtml(t("common.retry"))}</button>` +
    `</div>`;
  container.querySelector(".load-error__retry")?.addEventListener("click", () => retry());
}

function _fieldName(loc) {
  const last = Array.isArray(loc) ? loc[loc.length - 1] : "";
  return String(last || "").replace(/_/g, " ");
}

/**
 * Plain-language message for a failed response. Backend validation text written for
 * users (a string `detail`) is shown; anything else becomes a generic message.
 * @param {Response|null} res
 * @param {any} body  parsed JSON body if the caller already has it
 */
export async function errorMessage(res, body) {
  if (!res) return t("common.error.network");
  if (res.status === 429) return t("common.error.rateLimitShort");
  if (res.status >= 500) return t("common.error.unexpected");
  let data = body;
  if (data === undefined) {
    try {
      data = await res.clone().json();
    } catch {
      data = null;
    }
  }
  const detail = data && data.detail;
  if (res.status === 422 || res.status === 400) {
    if (typeof detail === "string" && detail.length <= 200) return detail;
    if (Array.isArray(detail) && detail.length) {
      const fields = [...new Set(detail.map((d) => _fieldName(d.loc)).filter(Boolean))];
      if (fields.length) return t("form.error.checkFields", { fields: fields.join(", ") });
    }
    return t("form.error.invalid");
  }
  return t("common.error.unexpected");
}
