/**
 * api.js — Centralised HTTP client for Smart Farmer.
 *
 * Provides:
 *  - apiFetch(path, options)  — authenticated fetch with 401/429 handling
 *  - showError(message)       — dismissible error banner (no stack traces)
 *  - loadCached(key)          — read sessionStorage cache
 *  - saveCache(key, data)     — write sessionStorage cache
 *
 * All API calls should use apiFetch instead of raw fetch so that
 * auth errors and rate-limit responses are handled consistently.
 */

import { getJwt, signOut } from "./auth.js";
import { API_BASE_URL } from "./config.js";
import { TRANSLATIONS } from "./i18n.js";

// -- Slow-server notice --
// Render's free tier sleeps; when a request has not answered after 6 s, show a
// non-blocking status line (in page flow, so it never covers the nav or headers).
const SLOW_AFTER_MS = 6000;
let _slowCount = 0;
function _showSlowNotice() {
  _slowCount += 1;
  if (document.getElementById("sf-waking")) return;
  let lang = "en";
  try { lang = localStorage.getItem("sf_lang") === "hi" ? "hi" : "en"; } catch { /* ignore */ }
  const el = document.createElement("div");
  el.id = "sf-waking";
  el.className = "sf-status-line";
  el.setAttribute("role", "status");
  el.setAttribute("data-i18n", "net.waking");
  el.textContent = TRANSLATIONS[lang]?.["net.waking"] || TRANSLATIONS.en["net.waking"];
  document.body.prepend(el);
}
function _hideSlowNotice() {
  _slowCount = Math.max(0, _slowCount - 1);
  if (_slowCount === 0) document.getElementById("sf-waking")?.remove();
}

// ── Rate-limit banner ─────────────────────────────────────────────────────────

let _rateLimitBannerId = "sf-rate-limit-banner";

function _getOrCreateRateLimitBanner() {
  let banner = document.getElementById(_rateLimitBannerId);
  if (banner) return banner;

  banner = document.createElement("div");
  banner.id = _rateLimitBannerId;
  banner.setAttribute("role", "alert");
  banner.setAttribute("aria-live", "assertive");
  banner.style.cssText = [
    "position:fixed",
    "top:0",
    "left:0",
    "right:0",
    "z-index:9999",
    "background:#7C3AED",
    "color:#fff",
    "font-size:0.875rem",
    "font-weight:600",
    "padding:0.75rem 1rem",
    "display:flex",
    "align-items:center",
    "justify-content:space-between",
    "gap:1rem",
    "box-shadow:0 2px 8px rgba(0,0,0,0.25)",
  ].join(";");

  const msg = document.createElement("span");
  msg.id = _rateLimitBannerId + "-msg";
  banner.appendChild(msg);

  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.textContent = "✕";
  closeBtn.setAttribute("aria-label", "Dismiss");
  closeBtn.style.cssText =
    "background:none;border:none;color:#fff;cursor:pointer;font-size:1rem;line-height:1;flex-shrink:0;min-width:44px;min-height:44px;";
  closeBtn.addEventListener("click", () => banner.remove());
  banner.appendChild(closeBtn);

  document.body.prepend(banner);
  return banner;
}

function _showRateLimitBanner(retryAfterSeconds) {
  const banner = _getOrCreateRateLimitBanner();
  const msgEl = document.getElementById(_rateLimitBannerId + "-msg");
  const secs = Number(retryAfterSeconds);
  const display = !isNaN(secs) && secs > 0
    ? `Too many requests. Please wait ${secs} second${secs === 1 ? "" : "s"} before trying again.`
    : "Too many requests. Please wait a moment before trying again.";
  if (msgEl) msgEl.textContent = display;
  banner.style.display = "flex";

  // Auto-dismiss after the retry window (plus a small buffer)
  if (!isNaN(secs) && secs > 0) {
    setTimeout(() => banner.remove(), (secs + 1) * 1000);
  }
}

// ── Error banner ──────────────────────────────────────────────────────────────

let _errorBannerId = "sf-error-banner";

/**
 * Renders a dismissible error banner at the top of the page.
 * Does NOT expose stack traces, internal service names, or raw exception text.
 *
 * @param {string} message - Human-readable message safe to show to the user.
 */
export function showError(message) {
  // Sanitise — strip anything that looks like a stack trace or HTML injection.
  const safe = String(message || "Something went wrong. Please try again.")
    .replace(/<[^>]*>/g, "")   // strip HTML tags
    .replace(/\s+at\s+\S+/g, "") // strip JS stack-trace lines ("  at functionName")
    .slice(0, 300);

  let banner = document.getElementById(_errorBannerId);

  if (!banner) {
    banner = document.createElement("div");
    banner.id = _errorBannerId;
    banner.setAttribute("role", "alert");
    banner.setAttribute("aria-live", "polite");
    banner.style.cssText = [
      "position:fixed",
      "top:0",
      "left:0",
      "right:0",
      "z-index:9998",
      "background:#DC2626",
      "color:#fff",
      "font-size:0.875rem",
      "font-weight:500",
      "padding:0.75rem 1rem",
      "display:flex",
      "align-items:center",
      "justify-content:space-between",
      "gap:1rem",
      "box-shadow:0 2px 8px rgba(0,0,0,0.25)",
    ].join(";");

    const msgEl = document.createElement("span");
    msgEl.id = _errorBannerId + "-msg";
    banner.appendChild(msgEl);

    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.textContent = "✕";
    closeBtn.setAttribute("aria-label", "Dismiss error");
    closeBtn.style.cssText =
      "background:none;border:none;color:#fff;cursor:pointer;font-size:1rem;line-height:1;flex-shrink:0;min-width:44px;min-height:44px;";
    closeBtn.addEventListener("click", () => banner.remove());
    banner.appendChild(closeBtn);

    document.body.prepend(banner);
  }

  const msgEl = document.getElementById(_errorBannerId + "-msg");
  if (msgEl) msgEl.textContent = safe;
  banner.style.display = "flex";
}

// ── sessionStorage cache helpers ──────────────────────────────────────────────

/**
 * Loads a JSON-parsed value from sessionStorage.
 * Returns null if the key does not exist or the stored value cannot be parsed.
 *
 * @param {string} key
 * @returns {*} The cached value, or null.
 */
export function loadCached(key) {
  try {
    const raw = sessionStorage.getItem(key);
    if (raw == null) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

/**
 * Serialises data to JSON and writes it to sessionStorage.
 * Silently ignores errors (e.g. storage quota exceeded in private mode).
 *
 * @param {string} key
 * @param {*} data
 */
export function saveCache(key, data) {
  try {
    sessionStorage.setItem(key, JSON.stringify(data));
  } catch {
    // Non-fatal — private browsing or quota exceeded
  }
}

// ── Core fetch wrapper ────────────────────────────────────────────────────────

/**
 * Authenticated fetch wrapper.
 *
 * Behaviour:
 *  - Attaches `Authorization: Bearer <JWT>` to every request.
 *  - 401 response → calls signOut() and redirects to login.html.
 *  - 429 response → shows a rate-limit banner with the Retry-After value.
 *  - 45-second timeout to handle cold-start latency on Render free tier.
 *  - Content-Type defaults to application/json (override via options.headers).
 *
 * @param {string} path    - Path relative to API_BASE_URL, e.g. "/api/farmers/me"
 * @param {RequestInit} [options={}] - Standard fetch options (method, body, headers, …)
 * @returns {Promise<Response>}
 */
export async function apiFetch(path, options = {}) {
  const jwt = await getJwt();

  // 45-second timeout — handles Render free-tier cold starts
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 45000);
  let slowShown = false;
  const slowTimer = setTimeout(() => { slowShown = true; _showSlowNotice(); }, SLOW_AFTER_MS);

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(jwt ? { "Authorization": `Bearer ${jwt}` } : {}),
        ...(options.headers || {}),
      },
    });
  } finally {
    clearTimeout(timer);
    clearTimeout(slowTimer);
    if (slowShown) _hideSlowNotice();
  }

  // ── 401 Unauthorized — session expired or revoked ─────────────────────────
  if (response.status === 401) {
    await signOut();
    // signOut() redirects; return a synthetic Response so any awaiting
    // caller doesn't throw before the redirect fires.
    return new Response(null, { status: 401 });
  }

  // ── 429 Too Many Requests — rate limit hit ────────────────────────────────
  if (response.status === 429) {
    const retryAfter = response.headers.get("Retry-After");
    _showRateLimitBanner(retryAfter);
    // Return the response so callers can still inspect it or surface their
    // own message if needed.
    return response;
  }

  return response;
}
