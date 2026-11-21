/**
 * home.js: landing page (index.html) controller. Self-contained and small on purpose:
 * language toggle, today's guava price card, mandi bars (HTML/CSS, no chart library).
 * Data: GET /api/public/market-prices/guava (Agmarknet / data.gov.in). Nothing here is estimated.
 */
import { HOME } from "./i18n-home.js";
import { API_BASE_URL } from "./config.js";

const PATH = "/api/public/market-prices/guava";
let lang = "en";
let state = "loading";   // loading | ready | error
let board = null;
let savedAt = null;

try { lang = localStorage.getItem("sf_lang") === "hi" ? "hi" : "en"; } catch { /* ignore */ }

function mt(key, vars = {}) {
  let s = HOME[lang]?.[key] ?? HOME.en[key] ?? key;
  for (const [k, v] of Object.entries(vars)) s = s.split(`{{${k}}}`).join(String(v ?? ""));
  return s;
}
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const rupee = (v) => (v == null ? "—" : `₹${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`);
function dmy(iso) {
  const [y, m, d] = String(iso || "").slice(0, 10).split("-");
  return y && m && d ? `${d}/${m}/${y}` : "—";
}

function applyStatic() {
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = mt(el.getAttribute("data-i18n")); });
  document.querySelectorAll("[data-i18n-alt]").forEach((el) => el.setAttribute("alt", mt(el.getAttribute("data-i18n-alt"))));
  document.querySelectorAll("[data-i18n-aria-label]").forEach((el) => el.setAttribute("aria-label", mt(el.getAttribute("data-i18n-aria-label"))));
  document.getElementById("lang-en")?.classList.toggle("lang-active", lang === "en");
  document.getElementById("lang-hi")?.classList.toggle("lang-active", lang === "hi");
  document.getElementById("lang-en")?.setAttribute("aria-pressed", String(lang === "en"));
  document.getElementById("lang-hi")?.setAttribute("aria-pressed", String(lang === "hi"));
}

/** One modal price per mandi (first priced row), highest first, top 5. */
function rows() {
  const out = (board?.mandis || []).map((m) => {
    const p = (m.prices || []).find((x) => x.modal_per_kg != null);
    return p ? { name: m.market, value: Number(p.modal_per_kg) } : null;
  }).filter(Boolean).sort((a, b) => b.value - a.value).slice(0, 5);
  if (out.length) out[0].best = true;
  return out;
}

function renderHero() {
  const el = document.getElementById("mandi-hero");
  if (!el) return;
  el.dataset.state = state === "ready" ? "ok" : state;
  if (state === "loading") {
    el.innerHTML = `<span class="sf-skeleton" style="height:150px" role="status" aria-label="${esc(mt("mandi.loading"))}"></span>`;
    return;
  }
  if (state === "error") {
    el.innerHTML = `<div class="load-error" role="alert"><p class="load-error__text">${esc(mt("mandi.loadError"))}</p><button type="button" class="load-error__retry" data-mandi-retry>${esc(mt("mandi.retry"))}</button></div>`;
    el.querySelector("[data-mandi-retry]").addEventListener("click", load);
    return;
  }
  const priced = (board.mandis || []).filter((m) => (m.prices || []).some((p) => p.modal_per_kg != null))
    .sort((a, b) => String(b.trade_date).localeCompare(String(a.trade_date)));
  const top = board.has_data ? priced[0] : null;
  if (!top) {
    el.dataset.state = "empty";
    el.innerHTML = `<h2 class="price-hero__unit">${esc(mt("mandi.hero.title"))}</h2><p class="price-hero__value">—</p>
      <p class="price-hero__unit">${esc(mt("mandi.hero.empty"))}</p><p class="price-hero__meta">${esc(mt("mandi.hero.emptyBody"))}</p>
      <p class="price-hero__meta">${esc(mt("mandi.source"))}</p>`;
    return;
  }
  const p = top.prices.find((x) => x.modal_per_kg != null);
  const quintal = p.modal_per_quintal != null
    ? `<p class="price-hero__quintal">${esc(mt("mandi.hero.perQuintal", { value: Number(p.modal_per_quintal).toLocaleString("en-IN", { maximumFractionDigits: 0 }) }))}</p>` : "";
  el.innerHTML = `<h2 class="price-hero__unit">${esc(mt("mandi.hero.title"))}</h2>
    <p class="price-hero__value">${rupee(p.modal_per_kg)}</p>
    <p class="price-hero__unit">${esc(mt("mandi.perKg"))} · ${esc(mt("mandi.modal"))}</p>${quintal}
    <p class="price-hero__meta"><strong>${esc(mt("mandi.hero.at", { market: top.market, state: top.state }))}</strong></p>
    <p class="price-hero__meta">${esc(mt("mandi.asOf", { date: dmy(top.trade_date) }))}${top.is_stale ? ` · ${esc(mt("mandi.hero.stale"))}` : ""}</p>
    <p class="price-hero__meta">${esc(mt("mandi.source"))}</p>
    ${savedAt ? `<p class="price-hero__meta" role="status"><strong>${esc(mt("mandi.offlineCopy", { date: dmy(savedAt) }))}</strong></p>` : ""}`;
}

function renderChart() {
  const el = document.getElementById("mandi-chart");
  if (!el) return;
  const r = state === "ready" ? rows() : [];
  if (state === "loading") { el.classList.remove("hidden"); el.innerHTML = `<span class="sf-skeleton" style="height:190px"></span>`; return; }
  if (r.length < 2) { el.classList.add("hidden"); el.innerHTML = ""; return; }
  el.classList.remove("hidden");
  const max = r[0].value || 1;
  el.innerHTML = `<div class="h-chart__head"><h3>${esc(mt("chart.mandi.title"))}</h3><span class="h-chip">${esc(mt("chart.mandi.best"))} · ${esc(r[0].name)}</span></div>
    <ul class="sf-rank">${r.map((x) => `<li${x.best ? ' class="is-best"' : ""}><div class="sf-rank__name"><span>${esc(x.name)}</span><span>${rupee(x.value)}</span></div>
      <div class="sf-rank__bar" aria-hidden="true"><span style="width:${Math.max(4, Math.round((x.value / max) * 100))}%"></span></div></li>`).join("")}</ul>
    <p class="h-note">${esc(mt("chart.mandi.unit"))} · ${esc(mt("mandi.asOf", { date: dmy(board.as_of) }))} · ${esc(mt("mandi.source"))}</p>`;
}

function renderAll() {
  const el = document.getElementById("mandi-all");
  if (!el) return;
  if (state !== "ready" || !board?.has_data) { el.classList.add("hidden"); return; }
  el.classList.remove("hidden");
  const list = (board.mandis || []).map((m) => {
    const p = (m.prices || []).find((x) => x.modal_per_kg != null);
    if (!p) return "";
    return `<div class="h-mandi"><p class="h-mandi__name">${esc(m.market)} <span style="font-weight:400">· ${esc([m.district, m.state].filter(Boolean).join(", "))}</span></p>
      <p>${esc(mt("mandi.modal"))}: <strong>${rupee(p.modal_per_kg)}</strong> · ${esc(mt("mandi.min"))} ${rupee(p.min_per_kg)} · ${esc(mt("mandi.max"))} ${rupee(p.max_per_kg)}</p>
      <p>${esc(mt("mandi.asOf", { date: dmy(m.trade_date) }))}</p></div>`;
  }).join("");
  el.querySelector("[data-list]").innerHTML = list;
}

function render() {
  applyStatic();
  renderHero();
  renderChart();
  renderAll();
}

async function load() {
  state = "loading"; savedAt = null;
  render();
  try {
    const res = await fetch(`${API_BASE_URL}${PATH}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    board = await res.json();
    savedAt = res.headers.get("x-sf-from-cache");   // set by sw.js when the network failed
    state = "ready";
  } catch (err) {
    console.error("Mandi prices load failed:", err);
    state = "error";
  }
  render();
}

function setLang(next) {
  lang = next === "hi" ? "hi" : "en";
  try { localStorage.setItem("sf_lang", lang); } catch { /* ignore */ }
  render();
}

document.getElementById("lang-en")?.addEventListener("click", () => setLang("en"));
document.getElementById("lang-hi")?.addEventListener("click", () => setLang("hi"));
load();
// Render's free tier sleeps; waking it early makes sign-in faster.
fetch(`${API_BASE_URL}/health`).catch(() => {});
