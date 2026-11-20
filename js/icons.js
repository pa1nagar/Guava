/**
 * icons.js: inline SVG icons (24x24, 2px stroke), no network request.
 * icon(name, cls) returns markup for JS-built HTML.
 * Static HTML uses <span class="sf-icon" data-icon="name"></span>; this module fills those in.
 */
const P = {
  home: 'M3 11l9-8 9 8M5 10v10h5v-6h4v6h5V10',
  plus: 'M12 5v14M5 12h14',
  plusCircle: 'M12 3a9 9 0 100 18 9 9 0 000-18zM12 8v8M8 12h8',
  layers: 'M12 3l9 5-9 5-9-5 9-5zM3 13l9 5 9-5M3 17.5l9 5 9-5',
  login: 'M15 4h4a1 1 0 011 1v14a1 1 0 01-1 1h-4M10 8l4 4-4 4M14 12H3',
  tractor: 'M3 5h9v7H3zM12 8h4l3 4v4M3 12v4M7 20a3 3 0 100-6 3 3 0 000 6zM18 19a2 2 0 100-4 2 2 0 000 4zM10 17h6',
  info: 'M12 3a9 9 0 100 18 9 9 0 000-18zM12 11v5M12 8v.01',
  chart: 'M3 3v18h18M7 15l4-4 3 3 5-6',
  arrow: 'M5 12h14M13 6l6 6-6 6',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  x: 'M6 6l12 12M18 6L6 18',
  send: 'M21 3L3 10.5l7 3 3 7L21 3zM10 13.5L21 3',
  checkCircle: 'M12 3a9 9 0 100 18 9 9 0 000-18zM8 12.5l3 3 5-6',
  alert: 'M12 3a9 9 0 100 18 9 9 0 000-18zM12 7.5v5M12 16v.01',
  box: 'M3 8l9-5 9 5v8l-9 5-9-5V8zM3 8l9 5 9-5M12 13v8',
  eye: 'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM12 9a3 3 0 100 6 3 3 0 000-6z',
  camera: 'M4 7h3l2-3h6l2 3h3a1 1 0 011 1v11a1 1 0 01-1 1H4a1 1 0 01-1-1V8a1 1 0 011-1zM12 10a3.5 3.5 0 100 7 3.5 3.5 0 000-7z',
  pie: 'M12 3v9h9a9 9 0 11-9-9zM15 3.5A9 9 0 0120.5 9H15V3.5z',
  list: 'M9 6h11M9 12h11M9 18h11M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2',
  rupee: 'M7 5h10M7 9h10M7 5c5 0 8 1 8 4s-3 4-8 4l8 7',
  basket: 'M3 10h18l-2 10H5L3 10zM8 10l3-6M16 10l-3-6',
  brain: 'M9 4a3 3 0 00-3 3 3 3 0 00-2 5 3 3 0 002 5 3 3 0 006 1V5a2 2 0 00-3-1zM15 4a3 3 0 013 3 3 3 0 012 5 3 3 0 01-2 5 3 3 0 01-6 1',
  robot: 'M5 8h14v11H5zM12 4v4M9 13v1M15 13v1M9 17h6M2 12v3M22 12v3',
  calendar: 'M4 6h16v14H4zM4 10h16M8 3v4M16 3v4M9 15l2 2 4-4',
  bolt: 'M13 3L5 14h6l-1 7 8-11h-6l1-7z',
  receipt: 'M6 3h12v18l-3-2-3 2-3-2-3 2V3zM9 8h6M9 12h6',
  seedling: 'M12 21v-9M12 12C12 8 9 6 4 6c0 4 3 6 8 6zM12 14c0-3 2-5 7-5 0 3-2 5-7 5z',
  save: 'M5 3h12l4 4v13a1 1 0 01-1 1H5a1 1 0 01-1-1V4a1 1 0 011-1zM8 3v5h7V3M8 21v-7h8v7',
  cloudSun: 'M7 19a4 4 0 010-8 5 5 0 019.5-1A4.5 4.5 0 0117 19H7zM8 7L6.5 5.5M12 5V3M4 11H2',
  shield: 'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3zM9 12l2 2 4-4',
  thermo: 'M10 14.5V5a2 2 0 014 0v9.5a4 4 0 11-4 0zM12 9v7',
  rain: 'M7 15a4 4 0 010-8 5 5 0 019.5-1A4.5 4.5 0 0117 15H7zM8 18l-1 3M12 18l-1 3M16 18l-1 3',
  clipboard: 'M9 4h6v3H9zM7 5H5v16h14V5h-2M9 14l2 2 4-4',
  coins: 'M12 3a4 4 0 00-4 4h8a4 4 0 00-4-4zM8 7C5 11 4 14 4 16a4 4 0 004 4h8a4 4 0 004-4c0-2-1-5-4-9M12 11v6M10 13h4',
  sun: 'M12 8a4 4 0 100 8 4 4 0 000-8zM12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5',
  star: 'M12 3l2.7 5.6 6.3.9-4.6 4.4 1.1 6.1L12 17l-5.5 3 1.1-6.1L3 9.5l6.3-.9L12 3z',
  leaf: 'M5 19c0-9 5-14 15-14 0 10-5 15-14 15M5 19l8-8',
  market: 'M4 9l1-5h14l1 5M4 9a2.5 2.5 0 005 0 2.5 2.5 0 006 0 2.5 2.5 0 005 0M5 11v9h14v-9',
  trend: 'M3 17l6-6 4 4 8-8M15 7h6v6',
};

export function icon(name, cls = '') {
  const d = P[name];
  if (!d) return '';
  return `<svg class="sf-svg ${cls}" viewBox="0 0 24 24" width="1.25em" height="1.25em" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="${d}"/></svg>`;
}

export function hydrateIcons(root = document) {
  root.querySelectorAll('[data-icon]:not([data-icon-done])').forEach((el) => {
    el.innerHTML = icon(el.getAttribute('data-icon'));
    el.setAttribute('data-icon-done', '1');
  });
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => hydrateIcons());
  else hydrateIcons();
}
