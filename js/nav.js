/**
 * nav.js - shared bottom navigation for every signed-in app page.
 * Usage: import { mountNav } from './js/nav.js'; mountNav('tasks');
 * Labels carry data-i18n keys (nav.item.*) so translator.setLanguage updates them;
 * they are also filled once here because the translator may have run already.
 */
const I = (d) => `<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${d}</svg>`;
const ITEMS = [
  ['plan', 'plan.html', 'Plan', I('<path d="M3 11l9-8 9 8v10H3z"/>')],
  ['farm', 'farm.html', 'Farm', I('<path d="M5 21c0-9 5-15 15-16 0 10-6 15-15 16zM5 21l8-8"/>')],
  ['tasks', 'tasks.html', 'Tasks', I('<path d="M4 6l2 2 3-3M4 14l2 2 3-3M12 7h8M12 15h8"/>')],
  ['sell', 'sell-smart.html', 'Sell', I('<path d="M12 2v20M17 6H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/>')],
];
const MORE = [['observations', 'observations.html', 'Observations'], ['inventory', 'inventory.html', 'Inventory'],
  ['report', 'report.html', 'Crop report'], ['privacy', 'privacy.html', 'Privacy']];

export function mountNav(active) {
  if (document.getElementById('sf-nav')) return;
  const on = (k) => (k === active ? ' aria-current="page"' : '');
  const item = ([k, href, en, icon]) =>
    `<a href="${href}" class="sf-nav-item"${on(k)}>${icon}<span data-i18n="nav.item.${k}">${en}</span></a>`;
  const nav = document.createElement('nav');
  nav.id = 'sf-nav';
  nav.className = 'sf-nav';
  nav.setAttribute('aria-label', 'Main menu');
  nav.innerHTML = ITEMS.map(item).join('') +
    `<button type="button" class="sf-nav-item" id="sf-more-btn" aria-expanded="false" aria-controls="sf-more"${MORE.some((m) => m[0] === active) ? ' aria-current="page"' : ''}>${I('<path d="M5 12h.01M12 12h.01M19 12h.01" stroke-width="4"/>')}<span data-i18n="nav.item.more">More</span></button>` +
    `<div id="sf-more" class="sf-more" hidden>` +
    MORE.map(([k, href, en]) => `<a href="${href}"${on(k)} data-i18n="nav.item.${k}">${en}</a>`).join('') +
    `<div class="sf-more-row"><span data-i18n="nav.item.language">Language</span><button type="button" data-lang="en">English</button><button type="button" data-lang="hi" lang="hi">हिंदी</button></div>` +
    `<button type="button" id="sf-signout" data-i18n="nav.item.signOut">Sign out</button></div>`;
  document.body.appendChild(nav);
  document.body.classList.add('has-bottom-nav');
  const btn = nav.querySelector('#sf-more-btn');
  const sheet = nav.querySelector('#sf-more');
  const toggle = (open) => { sheet.hidden = !open; btn.setAttribute('aria-expanded', String(open)); };
  btn.addEventListener('click', () => toggle(sheet.hidden));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !sheet.hidden) { toggle(false); btn.focus(); } });
  document.addEventListener('click', (e) => { if (!nav.contains(e.target)) toggle(false); });
  sheet.querySelectorAll('[data-lang]').forEach((b) => b.addEventListener('click', () => {
    try { localStorage.setItem('sf_lang', b.dataset.lang); } catch (_) { /* private mode */ }
    location.reload();
  }));
  nav.querySelector('#sf-signout').addEventListener('click', () => import('./auth.js').then((m) => m.signOut()));
  import('./i18n.js').then(({ TRANSLATIONS: T }) => {
    let l = 'en';
    try { l = localStorage.getItem('sf_lang') === 'hi' ? 'hi' : 'en'; } catch (_) { /* ignore */ }
    nav.querySelectorAll('[data-i18n]').forEach((el) => { const v = T[l] && T[l][el.dataset.i18n]; if (v) el.textContent = v; });
    if (T[l]['nav.item.main']) nav.setAttribute('aria-label', T[l]['nav.item.main']);
  }).catch(() => {});
}
