/**
 * sw-register.js - registers the service worker (https only) and starts the
 * offline banner. Included on every page.
 */
import './net-status.js';

// Lets CSS :lang(hi) loosen line height on pages that do not run the translator.
try { document.documentElement.lang = localStorage.getItem('sf_lang') === 'hi' ? 'hi' : 'en'; } catch (_) { /* ignore */ }

if ('serviceWorker' in navigator && location.protocol === 'https:') {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => { /* optional enhancement */ });
  });
}
