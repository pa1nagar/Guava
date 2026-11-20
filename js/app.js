/**
 * app.js — Smart Farmer public homepage controller
 *
 * Handles language toggle initialisation and contact form submission.
 * The contact form posts to the backend /api/contact endpoint.
 */

import { setLanguage, init } from './translator.js';
import { API_BASE_URL } from './config.js';
import { t, errorMessage } from './dom.js';

// ─── Language ────────────────────────────────────────────────────────────────

/**
 * setLang(lang) — wrapper exposed on window for inline onclick handlers.
 * Delegates to translator.js setLanguage().
 */
export function setLang(lang) {
  setLanguage(lang);
}

window.setLang = setLang;

// ─── Contact Form ─────────────────────────────────────────────────────────────

/**
 * Handles the contact/join-pilot form submission.
 *
 * Validates client-side:
 *   - name is required (max 100 chars, enforced by HTML maxlength)
 *   - at least one of email or phone is required
 *   - consent checkbox must be checked
 *
 * Sends a POST to ${API_BASE_URL}/api/contact with JSON body:
 *   { name, email, phone, message, consent: true }
 *
 * Shows success or error message based on response. Preserves form
 * field values on failure (inputs are not cleared).
 */
async function handleContactSubmit(event) {
  event.preventDefault();

  const form = document.getElementById('contact-form');
  if (!form) return;

  // Gather form values
  const name    = (document.getElementById('contact-name')?.value    || '').trim();
  const email   = (document.getElementById('contact-email')?.value   || '').trim();
  const phone   = (document.getElementById('contact-phone')?.value   || '').trim();
  const message = (document.getElementById('contact-message')?.value || '').trim();
  const consent = document.getElementById('contact-consent')?.checked || false;

  // UI message elements
  const successEl  = document.getElementById('contact-success');
  const errorEl    = document.getElementById('contact-error');
  const errorMsgEl = document.getElementById('contact-error-msg');
  const validationEl = document.getElementById('contact-validation');

  // Hide all messages before re-validating
  successEl?.classList.add('hidden');
  errorEl?.classList.add('hidden');
  validationEl?.classList.add('hidden');

  // ── Client-side validation ──────────────────────────────────────────────

  const fail = (key, field) => {
    const txt = document.getElementById('contact-validation-text');
    if (txt) { txt.removeAttribute('data-i18n'); txt.textContent = t(key); }
    validationEl?.classList.remove('hidden');
    document.getElementById(field)?.focus();
  };
  if (!name) return fail('home.contact.v.name', 'contact-name');
  if (!email && !phone) return fail('home.contact.v.contact', 'contact-email');
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return fail('home.contact.v.email', 'contact-email');
  if (!consent) return fail('home.contact.v.consent', 'contact-consent');
  // ── Submit to backend ────────────────────────────────────────────────────

  const submitBtn = document.getElementById('contact-submit');
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.classList.add('opacity-60', 'cursor-not-allowed');
    submitBtn.setAttribute('aria-busy', 'true');
    submitBtn.dataset.label = submitBtn.innerHTML;
    submitBtn.textContent = t('home.contact.sending');
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/contact`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        email: email || null,
        phone: phone || null,
        message: message || null,
        consent: true,
      }),
    });

    if (response.ok || response.status === 200) {
      // Success — show success message and clear the form
      successEl?.classList.remove('hidden');
      form.reset();
    } else if (response.status === 422) {
      // Validation failure from server: show a plain message, keep form values
      if (errorMsgEl) errorMsgEl.textContent = t('home.contact.serverInvalid');
      errorEl?.classList.remove('hidden');
    } else if (response.status === 429) {
      const retryAfter = response.headers.get('Retry-After');
      if (errorMsgEl) errorMsgEl.textContent = retryAfter
        ? t('home.contact.rateLimited', { seconds: retryAfter })
        : t('home.contact.rateLimitedLater');
      errorEl?.classList.remove('hidden');
    } else {
      // Other server errors: generic message, keep form values
      if (errorMsgEl) errorMsgEl.textContent = await errorMessage(response);
      errorEl?.classList.remove('hidden');
    }  } catch (err) {
    // Network failure — show error, keep form values for retry
    if (errorMsgEl) errorMsgEl.textContent = t('common.error.network');
    errorEl?.classList.remove('hidden');
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.classList.remove('opacity-60', 'cursor-not-allowed');
    }
  }
}

// ─── Bootstrap ────────────────────────────────────────────────────────────────

window.addEventListener('DOMContentLoaded', () => {
  // Initialise language (seeds English text from TRANSLATIONS)
  init();

  // Wire contact form
  const form = document.getElementById('contact-form');
  if (form) {
    form.addEventListener('submit', handleContactSubmit);
  }
});
