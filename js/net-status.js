/**
 * net-status.js - slim in-flow banner shown while the browser is offline.
 * Not fixed-position, so it never covers headers, the error banner or the nav.
 */
function text() {
  const fallback = 'You are offline. Showing saved data.';
  return import('./i18n.js').then(({ TRANSLATIONS: T }) => {
    let l = 'en';
    try { l = localStorage.getItem('sf_lang') === 'hi' ? 'hi' : 'en'; } catch (_) { /* ignore */ }
    return (T[l] && T[l]['net.offline']) || fallback;
  }).catch(() => fallback);
}

let banner = null;
async function show() {
  if (banner) return;
  banner = document.createElement('div');
  banner.id = 'sf-offline-banner';
  banner.className = 'sf-offline-banner';
  banner.setAttribute('role', 'status');
  banner.setAttribute('data-i18n', 'net.offline');
  banner.textContent = await text();
  document.body.prepend(banner);
}
function hide() { if (banner) { banner.remove(); banner = null; } }

function start() {
  window.addEventListener('offline', show);
  window.addEventListener('online', hide);
  if (navigator.onLine === false) show();
}
if (document.body) start(); else document.addEventListener('DOMContentLoaded', start);
