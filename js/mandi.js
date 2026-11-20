/**
 * mandi.js — Guava mandi price card (real data: Agmarknet / data.gov.in).
 *
 * One component used by plan.html (logged-in farmer, prices near the farm plus
 * saved history) and index.html (public view: latest prices in Madhya Pradesh
 * and Maharashtra, with a sign-in prompt).
 *
 * The page provides the container elements (#mandi-title, #mandi-subtitle,
 * #mandi-board, #mandi-history, #mandi-lang-en, #mandi-lang-hi). Nothing here
 * is estimated. Text is bilingual (EN / HI) via TRANSLATIONS, using the same
 * sf_lang preference as the rest of the site.
 *
 * Staleness: the backend decides (is_stale per mandi) and sends
 * stale_after_days; the UI only displays that number.
 */
import { TRANSLATIONS } from "./i18n.js";

const PUBLIC_PATH  = "/api/public/market-prices/guava";
const PRIVATE_PATH = "/api/market-prices/guava?limit=5";

let _board   = null;       // last board payload
let _history = null;       // last history payload
let _state   = "loading";  // "loading" | "ready" | "error"
let _public  = false;
let _savedAt = null;      // set when the service worker served a saved copy (offline)
let _onRender = null;
let _lastOpts = null;      // arguments of the last loadMandiCard() call, so Retry can re-run it

export function mandiLang() {
  try { return localStorage.getItem("sf_lang") === "hi" ? "hi" : "en"; }
  catch { return "en"; }
}

export function mt(key, vars = {}) {
  const lang = mandiLang();
  let text = TRANSLATIONS[lang]?.[key] ?? TRANSLATIONS.en?.[key] ?? key;
  for (const [k, v] of Object.entries(vars)) text = text.split(`{{${k}}}`).join(String(v));
  return text;
}

export function mandiEsc(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

export function mandiDate(iso) {
  if (!iso) return "—";
  const [y, m, d] = String(iso).slice(0, 10).split("-");
  return y && m && d ? `${d}/${m}/${y}` : "—";
}

export function rupee(value) {
  return value == null ? "—" : `₹${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

/** Last history payload (plan page uses it for the harvest card). */
export function getMandiHistory() { return _history; }

function renderHeader() {
  const title = document.getElementById("mandi-title");
  const sub   = document.getElementById("mandi-subtitle");
  if (title) title.textContent = mt("mandi.title");
  if (sub)   sub.textContent   = mt(_public ? "mandi.subtitle.public" : "mandi.subtitle");
  document.getElementById("mandi-lang-en")?.classList.toggle("font-bold", mandiLang() === "en");
  document.getElementById("mandi-lang-hi")?.classList.toggle("font-bold", mandiLang() === "hi");
}

function renderBoard() {
  const el = document.getElementById("mandi-board");
  if (!el) return;

  if (_state === "loading") {
    el.innerHTML = `<p class="text-sm text-gray-600">${mandiEsc(mt("mandi.loading"))}</p>`;
    return;
  }
  if (_state === "error") {
    el.innerHTML = `<div class="load-error" role="alert"><p class="load-error__text">${mandiEsc(mt("mandi.loadError"))}</p><button type="button" class="load-error__retry">${mandiEsc(mt("mandi.retry"))}</button></div>`;
    el.querySelector(".load-error__retry")?.addEventListener("click", () => loadMandiCard(_lastOpts || {}));
    return;
  }

  const board = _board || {};
  if (!board.has_data) {
    el.innerHTML = `
      <div class="bg-white border border-gray-200 rounded-2xl p-5 text-center">
        <p class="text-base font-bold text-gray-700">${mandiEsc(mt("mandi.empty.title"))}</p>
        <p class="text-sm text-gray-600 mt-1">${mandiEsc(mt("mandi.empty.body"))}</p>
        <p class="text-sm text-gray-600 mt-3">${mandiEsc(mt("mandi.source"))}</p>
      </div>`;
    return;
  }

  const scopeKey = `mandi.scope.${board.scope}`;
  const staleDays = board.stale_after_days;
  const cards = board.mandis.map(m => {
    const stale = m.is_stale;
    const badge = stale
      ? `<span class="text-sm font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800">${mandiEsc(mt("mandi.stale", { days: staleDays ?? "" }))}</span>`
      : `<span class="text-sm font-semibold px-2 py-0.5 rounded-full bg-green-100 text-green-800">${mandiEsc(mt("mandi.fresh"))}</span>`;
    const where = [m.district, m.state].filter(Boolean).map(mandiEsc).join(", ");
    const dist = m.distance_km != null && m.match !== "same_district"
      ? ` · ${mandiEsc(mt("mandi.distance", { km: m.distance_km }))}` : "";
    const rows = m.prices.map(p => {
      const label = [p.variety, p.grade].filter(Boolean).map(mandiEsc).join(" · ");
      return `
        <div class="grid grid-cols-3 gap-2 text-center ${label ? "mt-2" : ""}">
          ${label ? `<p class="col-span-3 text-sm text-gray-600 text-left">${label}</p>` : ""}
          <div class="bg-green-50 rounded-xl py-2">
            <p class="text-sm text-gray-600">${mandiEsc(mt("mandi.modal"))}</p>
            <p class="text-lg font-extrabold text-brand-dark">${rupee(p.modal_per_kg)}</p>
          </div>
          <div class="bg-gray-50 rounded-xl py-2">
            <p class="text-sm text-gray-600">${mandiEsc(mt("mandi.min"))}</p>
            <p class="text-base font-bold text-gray-700">${rupee(p.min_per_kg)}</p>
          </div>
          <div class="bg-gray-50 rounded-xl py-2">
            <p class="text-sm text-gray-600">${mandiEsc(mt("mandi.max"))}</p>
            <p class="text-base font-bold text-gray-700">${rupee(p.max_per_kg)}</p>
          </div>
        </div>`;
    }).join("");
    return `
      <div class="bg-white border ${stale ? "border-amber-300" : "border-gray-200"} rounded-2xl p-4 shadow-sm">
        <div class="flex items-start justify-between gap-2 flex-wrap">
          <div>
            <p class="text-base font-bold text-brand-dark">${mandiEsc(m.market)}</p>
            <p class="text-sm text-gray-600">${where}${dist}</p>
          </div>
          ${badge}
        </div>
        <p class="text-sm text-gray-600 mt-1">${mandiEsc(mt("mandi.asOf", { date: mandiDate(m.trade_date) }))} · ${mandiEsc(mt("mandi.perKg"))}</p>
        ${rows}
      </div>`;
  }).join("");

  const signIn = _public
    ? `<p class="text-sm mt-3"><a href="login.html" class="font-semibold text-brand-primary underline">${mandiEsc(mt("mandi.public.signin"))}</a></p>`
    : "";

  el.innerHTML = `
    ${_savedAt ? `<p class="text-sm font-semibold text-amber-800 mb-2" role="status">${mandiEsc(mt("mandi.offlineCopy", { date: mandiDate(_savedAt) }))}</p>` : ""}
    <p class="text-sm text-gray-600 mb-2">${mandiEsc(mt(scopeKey))}</p>
    <div class="grid gap-3 sm:grid-cols-2">${cards}</div>
    <p class="text-sm text-gray-600 mt-3">${mandiEsc(mt("mandi.source"))} · ${mandiEsc(mt("mandi.asOf", { date: mandiDate(board.as_of) }))}</p>
    ${signIn}`;
}

function renderHistory() {
  const el = document.getElementById("mandi-history");
  if (!el) return;
  if (_state !== "ready" || !_history || !_board?.has_data) {
    el.innerHTML = "";
    return;
  }
  const h = _history;
  const title = `<p class="text-sm font-bold text-emerald-900 mb-1">${mandiEsc(mt("mandi.history.title"))}${h.market ? ` · ${mandiEsc(h.market)}` : ""}</p>`;

  if (!h.has_trend) {
    el.innerHTML = `
      <div class="bg-white border border-gray-200 rounded-2xl p-4">
        ${title}
        <p class="text-sm text-gray-600">${mandiEsc(mt("mandi.history.notEnough", { min: h.min_days_for_trend, have: h.distinct_days }))}</p>
      </div>`;
    return;
  }

  const pts = h.series.filter(s => s.modal_per_kg != null);
  const max = Math.max(...pts.map(s => s.modal_per_kg), 1);
  const bars = pts.map(s => `
    <div title="${mandiEsc(mandiDate(s.trade_date))}: ${rupee(s.modal_per_kg)}"
         style="flex:1; min-width:3px; height:${Math.max(4, Math.round((s.modal_per_kg / max) * 100))}%; background:#4A7C59; border-radius:3px 3px 0 0;"></div>`).join("");
  el.innerHTML = `
    <div class="bg-white border border-gray-200 rounded-2xl p-4">
      ${title}
      <div class="flex items-end gap-px h-24 mb-2">${bars}</div>
      <p class="text-sm text-gray-600">${mandiEsc(mt("mandi.history.range", { n: h.distinct_days, from: mandiDate(h.first_date), to: mandiDate(h.last_date) }))} · ${mandiEsc(mt("mandi.modal"))} ${mandiEsc(mt("mandi.perKg"))}</p>
      <p class="text-sm text-gray-600 mt-1">${mandiEsc(mt("mandi.source"))}</p>
    </div>`;
}

/** Largest-number headline on the public page: the newest saved price (js/mandi.js feeds #mandi-hero). */
function renderHero() {
  const el = document.getElementById("mandi-hero");
  if (!el) return;
  el.dataset.state = _state === "ready" ? "ok" : _state;
  const retryBtn = `<button type="button" class="load-error__retry" data-mandi-retry>${mandiEsc(mt("mandi.retry"))}</button>`;
  if (_state === "loading") {
    el.innerHTML = `<p class="price-hero__meta" role="status">${mandiEsc(mt("mandi.loading"))}</p>`;
    return;
  }
  if (_state === "error") {
    el.innerHTML = `<p class="price-hero__meta text-red-700">${mandiEsc(mt("mandi.loadError"))}</p>${retryBtn}`;
    el.querySelector("[data-mandi-retry]")?.addEventListener("click", () => loadMandiCard(_lastOpts || {}));
    return;
  }
  const board = _board || {};
  // Newest trade date first; the board already lists freshest mandis first per state.
  const mandis = (board.mandis || []).filter(m => (m.prices || []).some(p => p.modal_per_kg != null));
  mandis.sort((a, b) => String(b.trade_date).localeCompare(String(a.trade_date)));
  const top = board.has_data ? mandis[0] : null;
  if (!top) {
    el.dataset.state = "empty";
    el.innerHTML = `
      <h2 class="price-hero__unit">${mandiEsc(mt("mandi.hero.title"))}</h2>
      <p class="price-hero__value">—</p>
      <p class="price-hero__unit">${mandiEsc(mt("mandi.hero.empty"))}</p>
      <p class="price-hero__meta">${mandiEsc(mt("mandi.hero.emptyBody"))}</p>
      <p class="price-hero__meta">${mandiEsc(mt("mandi.source"))}</p>`;
    return;
  }
  const p = top.prices.find(x => x.modal_per_kg != null);
  const quintal = p.modal_per_quintal != null
    ? `<p class="price-hero__quintal">${mandiEsc(mt("mandi.hero.perQuintal", { value: Number(p.modal_per_quintal).toLocaleString("en-IN", { maximumFractionDigits: 0 }) }))}</p>` : "";
  el.innerHTML = `
    <h2 class="price-hero__unit">${mandiEsc(mt("mandi.hero.title"))}</h2>
    <p class="price-hero__value">${rupee(p.modal_per_kg)}</p>
    <p class="price-hero__unit">${mandiEsc(mt("mandi.perKg"))} · ${mandiEsc(mt("mandi.modal"))}</p>
    ${quintal}
    <p class="price-hero__meta font-semibold">${mandiEsc(mt("mandi.hero.at", { market: top.market, state: top.state }))}</p>
    <p class="price-hero__meta">${mandiEsc(mt("mandi.asOf", { date: mandiDate(top.trade_date) }))}${top.is_stale ? ` · ${mandiEsc(mt("mandi.hero.stale"))}` : ""}</p>
    <p class="price-hero__meta">${mandiEsc(mt("mandi.source"))}</p>
    ${_savedAt ? `<p class="price-hero__meta font-semibold text-amber-800" role="status">${mandiEsc(mt("mandi.offlineCopy", { date: mandiDate(_savedAt) }))}</p>` : ""}`;
}

export function renderMandiAll() {
  renderHeader();
  renderHero();
  renderBoard();
  renderHistory();
  if (_onRender) _onRender();
}

/**
 * Load and render the card.
 *
 * @param {object}   opts
 * @param {Function} [opts.apiFetch]  authenticated fetch (plan page). Omit for
 *                                    the public view, which needs no login.
 * @param {string}   [opts.apiBase]   API origin (public view only).
 * @param {Function} [opts.onRender]  called after every render.
 */
export async function loadMandiCard({ apiFetch, apiBase = "", onRender } = {}) {
  _lastOpts = { apiFetch, apiBase, onRender };
  _public = !apiFetch;
  _onRender = onRender || null;
  _state = "loading";
  _savedAt = null;
  renderMandiAll();
  try {
    if (_public) {
      const res = await fetch(`${apiBase}${PUBLIC_PATH}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      _board = await res.json();
      // sw.js adds X-SF-From-Cache when the network failed and a saved copy was served
      _savedAt = res.headers.get("x-sf-from-cache");
      _history = null;
    } else {
      const res = await apiFetch(PRIVATE_PATH);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      _board = await res.json();
      _history = null;
      if (_board.has_data) {
        const top = _board.mandis[0];
        const hr = await apiFetch(
          `/api/market-prices/guava/history?market=${encodeURIComponent(top.market)}&state=${encodeURIComponent(top.state)}`
        );
        if (hr.ok) _history = await hr.json();
      }
    }
    _state = "ready";
  } catch (err) {
    console.error("Mandi prices load failed:", err);
    _state = "error";
  }
  renderMandiAll();
}

window.setMandiLang = function (lang) {
  try { localStorage.setItem("sf_lang", lang === "hi" ? "hi" : "en"); } catch { /* ignore */ }
  renderMandiAll();
};

// index.html's header toggle (setLang) must re-render the card too.
const _origSetLang = window.setLang;
if (typeof _origSetLang === "function") {
  window.setLang = function (lang) {
    _origSetLang(lang);
    renderMandiAll();
  };
}
