/**
 * translator.js — Language toggle engine
 * Imports TRANSLATIONS from data.js and provides setLanguage / getCurrentLang / init
 * No network requests. Works from file:// protocol.
 */

import { TRANSLATIONS } from './data.js';

let currentLang = 'en';
let _initialised = false;

/**
 * init() — call once on DOMContentLoaded to seed English text.
 * Safe to call multiple times (no-op after first call).
 */
export function init() {
  if (_initialised) return;
  _initialised = true;
  setLanguage('en');
}

/**
 * setLanguage(lang) — swap all [data-i18n] elements to the given language.
 * Toggles .lang-active on #lang-en / #lang-hi buttons.
 * Logs a console.warn for any missing key.
 */
export function setLanguage(lang) {
  currentLang = lang;

  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    const text = TRANSLATIONS[lang]?.[key];
    if (text !== undefined) {
      el.textContent = text;
    } else {
      console.warn(`[Translator] Missing key: "${key}" for lang: "${lang}"`);
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
 */
export function getCurrentLang() {
  return currentLang;
}
