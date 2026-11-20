/* Smart Farmer service worker.
 * - same-origin static GET: stale-while-revalidate
 * - navigations: network-first, cached copy when offline
 * - public mandi prices (only): network-first, last good copy kept in sf-meta
 *   with an X-SF-From-Cache header so the page can say "saved copy from <date>"
 * - NEVER caches a request with an Authorization header or any other /api/ path.
 */
const STATIC = 'sf-static-v1';
const META = 'sf-meta';
const PUBLIC_PRICES = 'https://guava-8wc7.onrender.com/api/public/market-prices/guava';
const SHELL = ['css/tailwind.css', 'css/style.css', 'js/nav.js', 'js/translator.js', 'js/i18n.js',
  'js/config.js', 'js/api.js', 'js/auth.js'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(STATIC).then((c) =>
    Promise.all(SHELL.map((p) => c.add(new URL(p, self.registration.scope)).catch(() => {})))
  ).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k !== STATIC && k !== META).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

async function publicPrices(request) {
  const meta = await caches.open(META);
  try {
    const res = await fetch(request);
    if (res.ok) {
      const headers = new Headers(res.headers);
      headers.set('X-SF-Cached-At', new Date().toISOString());
      await meta.put(PUBLIC_PRICES, new Response(await res.clone().blob(), { status: 200, headers }));
    }
    return res;
  } catch (err) {
    const saved = await meta.match(PUBLIC_PRICES);
    if (!saved) throw err;
    const headers = new Headers(saved.headers);
    headers.set('X-SF-From-Cache', headers.get('X-SF-Cached-At') || '1');
    return new Response(await saved.blob(), { status: 200, headers });
  }
}

async function networkFirst(request) {
  const cache = await caches.open(STATIC);
  try {
    const res = await fetch(request);
    if (res.ok) cache.put(request, res.clone());
    return res;
  } catch (err) {
    const hit = await cache.match(request);
    if (hit) return hit;
    throw err;
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(STATIC);
  const hit = await cache.match(request);
  const refresh = fetch(request).then((res) => { if (res.ok) cache.put(request, res.clone()); return res; });
  if (hit) { refresh.catch(() => {}); return hit; }
  return refresh;
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET' || req.headers.has('Authorization')) return;
  const url = new URL(req.url);
  if (url.origin + url.pathname === PUBLIC_PRICES) {
    event.respondWith(publicPrices(req));
    return;
  }
  if (url.origin !== self.location.origin || url.pathname.startsWith('/api/') || url.pathname === '/sw.js') return;
  event.respondWith(req.mode === 'navigate' ? networkFirst(req) : staleWhileRevalidate(req));
});
