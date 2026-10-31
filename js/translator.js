/**
 * translator.js — Language toggle engine
 * Imports TRANSLATIONS from data.js and provides setLanguage / getCurrentLang / init
 * No network requests. Works from file:// protocol.
 *
 * ── i18n Convention ──────────────────────────────────────────────────────────
 * All HTML elements that contain user-visible text MUST use a data-i18n attribute
 * whose value is a dot-separated key matching an entry in TRANSLATIONS.en / .hi.
 *
 *   <h2 data-i18n="farm.heading"></h2>
 *   <label data-i18n="farm.plot.name.label"></label>
 *   <button data-i18n="common.save"></button>
 *
 * Never hard-code display text directly in HTML — add a key to TRANSLATIONS
 * instead so both EN and HI variants are always kept in sync.
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * Locale helpers (Requirements 15.2):
 *   formatNumber(value, options?) — formats a number in the Indian locale (en-IN).
 *     e.g. formatNumber(1234567) → "12,34,567"
 *
 *   formatDate(dateInput) — formats a date as DD/MM/YYYY.
 *     e.g. formatDate(new Date()) → "15/07/2025"
 *
 * Both helpers are locale-aware: formatNumber uses 'en-IN' regardless of the
 * active language so that Indian number grouping is always applied.
 */

import { TRANSLATIONS } from './data.js';

/** @type {'en' | 'hi'} */
let currentLang = 'en';
let _initialised = false;

// ─── localStorage key for language preference (Requirement 15.1) ─────────────
const LANG_STORAGE_KEY = 'sf_lang';

/**
 * init() — call once on DOMContentLoaded.
 * Reads the stored language preference from localStorage (key: sf_lang).
 * Falls back to 'en' if no preference is stored.
 * Safe to call multiple times (no-op after first call).
 */
export function init() {
  if (_initialised) return;
  _initialised = true;

  // Read persisted preference; default to 'en'
  const stored = localStorage.getItem(LANG_STORAGE_KEY);
  const lang = stored === 'hi' ? 'hi' : 'en';
  setLanguage(lang);
}

/**
 * setLanguage(lang) — swap all [data-i18n] elements to the given language.
 * Persists the choice to localStorage (key: sf_lang).
 * Toggles .lang-active on #lang-en / #lang-hi buttons.
 * Logs a console.warn for any missing key.
 *
 * @param {'en' | 'hi'} lang
 */
export function setLanguage(lang) {
  currentLang = lang;

  // Persist preference so the next page load restores it
  try {
    localStorage.setItem(LANG_STORAGE_KEY, lang);
  } catch (_) {
    // Storage may be unavailable in private-browsing modes — safe to ignore
  }

  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    const text = TRANSLATIONS[lang]?.[key];
    if (text !== undefined) {
      el.textContent = text;
    } else {
      console.warn(`[Translator] Missing key: "${key}" for lang: "${lang}"`);
    }
  });

  // data-i18n-placeholder — sets the placeholder attribute instead of textContent
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.getAttribute('data-i18n-placeholder');
    const text = TRANSLATIONS[lang]?.[key];
    if (text !== undefined) {
      el.setAttribute('placeholder', text);
    } else {
      console.warn(`[Translator] Missing placeholder key: "${key}" for lang: "${lang}"`);
    }
  });

  // Update active-language button styles
  const btnEn = document.getElementById('lang-en');
  const btnHi = document.getElementById('lang-hi');
  if (btnEn) btnEn.classList.toggle('lang-active', lang === 'en');
  if (btnHi) btnHi.classList.toggle('lang-active', lang === 'hi');
}

/**
 * getCurrentLang() — returns the active language code ('en' | 'hi').
 * @returns {'en' | 'hi'}
 */
export function getCurrentLang() {
  return currentLang;
}

// ─── Locale helpers (Requirement 15.2) ───────────────────────────────────────

/**
 * formatNumber(value, options?) — formats a number using the Indian locale (en-IN).
 * Indian numbering groups digits as: last 3 digits, then pairs (e.g. 12,34,567).
 *
 * @param {number} value       - The number to format.
 * @param {Intl.NumberFormatOptions} [options] - Optional Intl.NumberFormat options.
 * @returns {string}
 *
 * @example
 *   formatNumber(1234567)             // "12,34,567"
 *   formatNumber(1234.5, { minimumFractionDigits: 2 })  // "1,234.50"
 */
export function formatNumber(value, options = {}) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return new Intl.NumberFormat('en-IN', options).format(value);
}

/**
 * formatCurrency(value) — formats a value as Indian Rupees.
 * Always uses INR symbol and 2 decimal places.
 *
 * @param {number} value
 * @returns {string}
 *
 * @example
 *   formatCurrency(12345.6)  // "₹12,345.60"
 */
export function formatCurrency(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(value);
}

/**
 * formatDate(dateInput) — formats a date as DD/MM/YYYY (Requirement 15.2).
 * Accepts a Date object, an ISO 8601 string, or a timestamp number.
 *
 * @param {Date | string | number} dateInput
 * @returns {string}
 *
 * @example
 *   formatDate(new Date('2025-07-15'))  // "15/07/2025"
 *   formatDate('2025-01-01')            // "01/01/2025"
 */
export function formatDate(dateInput) {
  if (!dateInput) return '—';
  const d = dateInput instanceof Date ? dateInput : new Date(dateInput);
  if (Number.isNaN(d.getTime())) return '—';
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const yyyy = d.getFullYear();
  return `${dd}/${mm}/${yyyy}`;
}

/**
 * formatDateTime(dateInput) — formats a date-time as DD/MM/YYYY HH:MM.
 * Uses the local timezone of the browser.
 *
 * @param {Date | string | number} dateInput
 * @returns {string}
 *
 * @example
 *   formatDateTime('2025-07-15T09:30:00')  // "15/07/2025 09:30"
 */
export function formatDateTime(dateInput) {
  if (!dateInput) return '—';
  const d = dateInput instanceof Date ? dateInput : new Date(dateInput);
  if (Number.isNaN(d.getTime())) return '—';
  const datePart = formatDate(d);
  const hh = String(d.getHours()).padStart(2, '0');
  const min = String(d.getMinutes()).padStart(2, '0');
  return `${datePart} ${hh}:${min}`;
}
