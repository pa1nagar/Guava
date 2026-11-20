/**
 * sell-smart.js - "Where and when to sell" page.
 *
 * Talks to /api/sell-smart/* (see backend/routers/sell_smart.py). Every number
 * shown comes from the API (saved Agmarknet rows or values the farmer typed);
 * nothing is computed here except display formatting and the min/max of the
 * saved series for the chart summary.
 *
 * Demo mode: only when the URL has ?demo=1 AND the page is opened from this
 * computer (host 127.0.0.1, localhost, or a file:// path). The page then calls
 * http://127.0.0.1:8001 (scripts/run_sell_smart_demo.py), skips sign-in and
 * shows a DEMO DATA banner. On any other host (for example the live site) the
 * flag is ignored: the normal sign-in gate runs and no request goes to port 8001.
 *
 * All display text goes through tr() / data-i18n (js/sell-smart-i18n.js).
 * Server-provided text (market names) is inserted with textContent only.
 */
import { TRANSLATIONS } from "./i18n.js";
import { loadChartJs } from "./lazy.js";
import { installSellTranslations } from "./sell-smart-i18n.js";
import { init as initTranslator, setLanguage, getCurrentLang, formatNumber } from "./translator.js";

const params = new URLSearchParams(window.location.search);
const LOCAL_HOSTS = ["127.0.0.1", "localhost", ""]; // "" is file://
const DEMO = params.get("demo") === "1" && LOCAL_HOSTS.includes(window.location.hostname);
const DEMO_BASE = "http://127.0.0.1:8001";
const BASE = "/api/sell-smart";

let apiMod = null; // { apiFetch, showError } - loaded only outside demo mode

// ---------------------------------------------------------------- helpers

function tr(key, vars = {}) {
  const lang = getCurrentLang();
  let text = TRANSLATIONS[lang]?.[key] ?? TRANSLATIONS.en?.[key];
  if (text === undefined) {
    console.warn(`[sell-smart] missing key: ${key}`);
    return key;
  }
  return text.replace(/\{(\w+)\}/g, (m, name) => (name in vars ? String(vars[name]) : m));
}

function fmt(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return tr("sell_none");
  return formatNumber(Number(value), { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function fmtDate(iso) {
  if (!iso) return tr("sell_none");
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso));
  if (!m) return String(iso);
  return `${m[3]}/${m[2]}/${m[1]}`;
}

/** Tiny DOM builder. Strings become text nodes (never HTML). */
function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "text") el.textContent = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

const $ = (id) => document.getElementById(id);

async function request(path, method = "GET", body) {
  const opts = { method };
  if (body !== undefined) opts.body = JSON.stringify(body);
  let res;
  if (DEMO) {
    res = await fetch(DEMO_BASE + path, { ...opts, headers: { "Content-Type": "application/json" } });
  } else {
    res = await apiMod.apiFetch(path, opts);
  }
  let data = null;
  try { data = await res.json(); } catch (_) { /* empty or non-JSON body */ }
  return { ok: res.ok, status: res.status, data };
}

// ---------------------------------------------------------------- section state

const SECTIONS = ["settings", "ranking", "trends", "alerts", "notif", "fair"];
const bodyId = { settings: "settings-body", ranking: "ranking-body", trends: "trends-body",
                 alerts: "alerts-body", notif: "notif-list", fair: "fair-body" };
const view = {};   // section -> { mode, key, data }
const data = { settings: null, ranking: null, trends: null, alerts: null, notif: null, fair: null };

function setStatus(section, mode, key) {
  view[section] = { ...(view[section] || {}), mode, key };
  paintStatus(section);
}

function paintStatus(section) {
  const { mode, key } = view[section] || {};
  const status = $(`${section}-status`);
  const retry = $(`${section}-retry`);
  const body = $(bodyId[section]);
  if (!status) return;
  const message = key ? tr(key) : (mode === "loading" ? tr("sell_loading") : "");
  status.textContent = message;
  status.classList.toggle("is-error", mode === "error");
  retry?.classList.toggle("hidden", mode !== "error");
  body?.classList.toggle("hidden", mode !== "ready");
}

function loading(section) { setStatus(section, "loading", "sell_loading"); }
function ready(section) { setStatus(section, "ready", null); }
function empty(section, key) { setStatus(section, "empty", key); }
function failed(section, key = "sell_error_generic") {
  setStatus(section, "error", DEMO ? "sell_error_demo_offline" : key);
}

// ---------------------------------------------------------------- settings

const el = {
  mode: () => $("set-mode"), perKm: () => $("set-per-km"), flat: () => $("set-flat"),
  handling: () => $("set-handling"), commission: () => $("set-commission"), radius: () => $("set-radius"),
};

function numOrNull(input) {
  const v = input.value.trim();
  if (v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : NaN;
}

function toggleModeFields() {
  const mode = el.mode().value;
  $("wrap-per-km").classList.toggle("hidden", mode !== "per_quintal_per_km");
  $("wrap-flat").classList.toggle("hidden", mode !== "flat_per_quintal");
}

function renderSettings() {
  const d = data.settings;
  if (!d) return;
  const s = d.settings || {};
  $("costs-prompt").classList.toggle("hidden", !!d.costs_set);
  $("location-basis").textContent = d.location_basis ? tr(`sell_location_${d.location_basis}`) : tr("sell_location_none");
  $("set-radius-hint").textContent = tr("sell_set_radius_hint", { km: d.default_radius_km });
  const sugg = d.transport_suggestion;
  const box = $("sugg-box");
  if (sugg) {
    $("sugg-text").textContent = tr("sell_sugg_text", {
      value: fmt(sugg.rs_per_quintal), label: tr("sell_sugg_label", { n: sugg.n_sales }),
    });
    box.classList.remove("hidden");
  } else {
    box.classList.add("hidden");
  }
}

function fillSettingsForm() {
  const s = data.settings?.settings || {};
  const set = (input, v) => { input.value = v === null || v === undefined ? "" : String(v); };
  el.mode().value = s.transport_mode || "";
  set(el.perKm(), s.transport_rs_per_quintal_per_km);
  set(el.flat(), s.transport_rs_per_quintal_flat);
  set(el.handling(), s.handling_rs_per_quintal);
  set(el.commission(), s.commission_pct);
  set(el.radius(), s.radius_km);
  toggleModeFields();
}

async function loadSettings() {
  loading("settings");
  try {
    const r = await request(`${BASE}/settings`);
    if (!r.ok) { failed("settings"); return; }
    data.settings = r.data;
    fillSettingsForm();
    renderSettings();
    ready("settings");
  } catch (_) { failed("settings"); }
}

async function saveSettings(ev) {
  ev.preventDefault();
  const status = $("settings-form-status");
  status.classList.remove("is-error");
  const mode = el.mode().value || null;
  const body = {
    transport_mode: mode,
    transport_rs_per_quintal_per_km: mode === "per_quintal_per_km" ? numOrNull(el.perKm()) : null,
    transport_rs_per_quintal_flat: mode === "flat_per_quintal" ? numOrNull(el.flat()) : null,
    handling_rs_per_quintal: numOrNull(el.handling()),
    commission_pct: numOrNull(el.commission()),
    radius_km: numOrNull(el.radius()),
    road_km_overrides: data.settings?.settings?.road_km_overrides || {},
  };
  const nums = [body.transport_rs_per_quintal_per_km, body.transport_rs_per_quintal_flat,
                body.handling_rs_per_quintal, body.commission_pct, body.radius_km];
  const modeMissing = (mode === "per_quintal_per_km" && body.transport_rs_per_quintal_per_km === null)
    || (mode === "flat_per_quintal" && body.transport_rs_per_quintal_flat === null);
  const maxRadius = data.settings?.max_radius_km ?? 1500;
  if (modeMissing || nums.some((n) => Number.isNaN(n) || (n !== null && n < 0))
      || (body.commission_pct !== null && body.commission_pct > 100)
      || (body.radius_km !== null && (body.radius_km <= 0 || body.radius_km > maxRadius))) {
    status.textContent = tr("sell_error_validation");
    status.classList.add("is-error");
    return;
  }
  $("settings-save").disabled = true;
  try {
    const r = await request(`${BASE}/settings`, "PUT", body);
    if (!r.ok) {
      status.textContent = tr(r.status === 422 ? "sell_error_validation" : "sell_error_save");
      status.classList.add("is-error");
      return;
    }
    status.textContent = tr("sell_saved");
    await Promise.all([loadSettings(), loadRanking()]);
  } catch (_) {
    status.textContent = tr(DEMO ? "sell_error_demo_offline" : "sell_error_save");
    status.classList.add("is-error");
  } finally {
    $("settings-save").disabled = false;
  }
}

function applySuggestion() {
  const sugg = data.settings?.transport_suggestion;
  if (!sugg) return;
  el.mode().value = "flat_per_quintal";
  el.flat().value = String(Math.round(sugg.rs_per_quintal * 100) / 100);
  toggleModeFields();
  el.flat().focus();
}

// ---------------------------------------------------------------- ranking

function sourceLine(d, date) {
  return h("p", { class: "status-line" },
    d.demo ? tr("sell_source_demo", { date: fmtDate(date) }) : tr("sell_source", { source: d.source, date: fmtDate(date) }));
}

function formulaBox(d) {
  const mode = data.settings?.settings?.transport_mode;
  const lines = [tr("sell_formula_net")];
  if (mode === "per_quintal_per_km") lines.push(tr("sell_formula_transport_per_km"));
  if (mode === "flat_per_quintal") lines.push(tr("sell_formula_transport_flat"));
  lines.push(tr("sell_formula_handling"));
  return h("div", { class: "bg-gray-50 border border-gray-200 rounded-xl p-3 text-sm" },
    h("p", { class: "font-semibold" }, tr("sell_formula_title")),
    lines.map((t) => h("p", { class: "mt-1" }, t)));
}

function flagList(flags) {
  if (!flags || !flags.length) return null;
  return h("ul", { class: "mt-2 flex flex-col gap-1" },
    flags.map((f) => h("li", { class: "text-sm text-amber-900" }, tr(`sell_flag_${f}`))));
}

function mandiCard(e, costsSet, ranked) {
  const hasNet = e.net_per_kg !== null && e.net_per_kg !== undefined;
  const headline = costsSet && hasNet ? e.net_per_kg : e.gross_per_kg;
  const badges = [];
  if (e.is_stale) badges.push(h("span", { class: "badge badge-old" }, tr("sell_badge_stale")));
  if (!e.location_known) badges.push(h("span", { class: "badge badge-old" }, tr("sell_badge_no_location")));
  badges.push(e.quality_flags && e.quality_flags.length
    ? h("span", { class: "badge badge-warn" }, tr("sell_badge_warn"))
    : h("span", { class: "badge badge-ok" }, tr("sell_badge_ok")));

  let formulaLine;
  if (!costsSet) formulaLine = tr("sell_formula_no_costs");
  else if (hasNet) {
    formulaLine = tr("sell_formula_yours", {
      modal: fmt(e.gross_per_kg), transport: fmt(e.transport_per_kg), handling: fmt(e.handling_per_kg),
      commission: fmt(e.commission_per_kg), net: fmt(e.net_per_kg),
    });
  } else formulaLine = tr("sell_formula_no_net");

  const distance = e.distance_km === null || e.distance_km === undefined
    ? tr("sell_distance_unknown")
    : tr("sell_km", { km: fmt(e.distance_km, 0) });

  return h("li", { class: "border border-gray-200 rounded-xl p-3" },
    h("div", { class: "flex items-start justify-between gap-3" },
      h("div", {},
        h("p", { class: "font-bold text-emerald-900" }, ranked && e.rank ? `${e.rank}. ` : "", e.market_name, ` (${e.district})`),
        h("div", { class: "mt-1 flex flex-wrap gap-1" }, badges)),
      h("div", { class: "text-right" },
        h("p", { class: "text-sm text-brand-muted" }, costsSet && hasNet ? tr("sell_net") : tr("sell_gross")),
        h("p", { class: "text-3xl font-bold text-emerald-900" }, fmt(headline)),
        h("p", { class: "text-sm text-brand-muted" }, tr("sell_unit_rs_kg")))),
    h("dl", { class: "mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-sm" },
      h("dt", { class: "text-brand-muted" }, tr("sell_gross")), h("dd", {}, `${fmt(e.gross_per_kg)} ${tr("sell_unit_rs_kg")}`),
      h("dt", { class: "text-brand-muted" }, tr("sell_distance")), h("dd", {}, distance),
      h("dt", { class: "text-brand-muted" }, tr("sell_price_date")), h("dd", {}, fmtDate(e.trade_date))),
    e.distance_label_key ? h("p", { class: "status-line mt-1" }, tr(e.distance_label_key)) : null,
    e.is_stale ? h("p", { class: "status-line mt-1" }, tr("sell_badge_stale_hint")) : null,
    h("p", { class: "mt-2 text-sm font-medium break-words" }, formulaLine),
    flagList(e.quality_flags));
}

function renderRanking() {
  const d = data.ranking;
  const body = $("ranking-body");
  body.replaceChildren();
  if (!d) return;
  const costsSet = !!d.costs_set;
  body.append(h("p", { class: "text-sm" }, tr(costsSet ? "sell_rank_sorted_net" : "sell_rank_sorted_gross")));
  if (!costsSet) body.append(h("p", { class: "text-sm text-amber-900" }, tr("sell_set_prompt")));
  if (d.status === "no_origin") body.append(h("p", { class: "text-sm font-semibold" }, tr("sell_location_none")));
  body.append(formulaBox(d));

  if (d.ranked.length) {
    body.append(h("ol", { class: "flex flex-col gap-3" }, d.ranked.map((e) => mandiCard(e, costsSet, true))));
  } else if (d.status !== "no_origin") {
    body.append(h("p", { class: "text-sm" }, tr("sell_rank_none_in_radius", { km: fmt(d.radius_km, 0) })));
  }
  if (d.unranked.length) {
    body.append(h("h3", { class: "font-semibold text-emerald-900" }, tr("sell_rank_unranked_title")));
    body.append(h("ul", { class: "flex flex-col gap-3" }, d.unranked.map((e) => mandiCard(e, costsSet, false))));
  }
  if (d.outside_radius) {
    body.append(h("p", { class: "status-line" }, tr("sell_rank_outside", { n: d.outside_radius, km: fmt(d.radius_km, 0) })));
  }
  body.append(h("p", { class: "status-line" }, tr("sell_mix_note")));
  body.append(sourceLine(d, d.as_of));
}

async function loadRanking() {
  loading("ranking");
  try {
    const r = await request(`${BASE}/ranking`);
    if (r.status === 404) { empty("ranking", "sell_location_none"); data.ranking = null; refreshMandiChoices(); return; }
    if (!r.ok) { failed("ranking"); return; }
    data.ranking = r.data;
    refreshMandiChoices();
    if (!r.data.has_data) { empty("ranking", "sell_rank_empty"); return; }
    renderRanking();
    ready("ranking");
  } catch (_) { failed("ranking"); }
}

// ---------------------------------------------------------------- mandi choices (trend scope and alert target)

function knownMandis() {
  const d = data.ranking;
  if (!d) return [];
  const seen = new Map();
  for (const e of [...d.ranked, ...d.unranked]) seen.set(e.id, e);
  return [...seen.values()].sort((a, b) => String(a.market_name).localeCompare(String(b.market_name)));
}

function refreshMandiChoices() {
  const mandis = knownMandis();

  const scope = $("trend-scope");
  const keepScope = scope.value;
  scope.replaceChildren(h("option", { value: "" }, tr("sell_trend_scope_district", { district: data.trends?.scope?.district || "" })));
  for (const m of mandis) {
    scope.append(h("option", { value: JSON.stringify({ m: m.market_name, s: m.state, d: m.district }) },
      tr("sell_trend_scope_mandi", { market: m.market_name, district: m.district })));
  }
  if ([...scope.options].some((o) => o.value === keepScope)) scope.value = keepScope;

  const where = $("alert-where");
  const keepWhere = where.value;
  where.replaceChildren();
  if (!mandis.length) {
    where.append(h("option", { value: "" }, tr("sell_alert_pick")));
    if (["empty", "ready"].includes(view.ranking?.mode)) $("alert-form-status").textContent = tr("sell_alert_no_mandis");
  } else {
    where.append(h("option", { value: "" }, tr("sell_alert_pick")));
    const districts = new Map();
    for (const m of mandis) {
      where.append(h("option", { value: JSON.stringify({ s: m.state, d: m.district, m: m.market_name }) },
        tr("sell_trend_scope_mandi", { market: m.market_name, district: m.district })));
      districts.set(`${m.state}|${m.district}`, m);
    }
    for (const m of districts.values()) {
      where.append(h("option", { value: JSON.stringify({ s: m.state, d: m.district, m: null }) },
        tr("sell_alert_whole_district", { district: m.district })));
    }
    if ($("alert-form-status").textContent === tr("sell_alert_no_mandis")) $("alert-form-status").textContent = "";
  }
  if ([...where.options].some((o) => o.value === keepWhere)) where.value = keepWhere;
}

// ---------------------------------------------------------------- trends

let chart = null;

/** Own Chart.js helper (js/charts.js is not used or edited by this feature). */
function drawTrendChart(canvas, series) {
  if (chart) { chart.destroy(); chart = null; }
  if (typeof window.Chart === "undefined") return false;
  chart = new window.Chart(canvas, {
    type: "line",
    data: {
      labels: series.map((p) => p.trade_date),
      datasets: [{
        label: tr("sell_chart_series"),
        data: series.map((p) => p.value_per_kg),
        borderColor: "#1E3A2B", backgroundColor: "rgba(74,124,89,0.15)",
        borderWidth: 2, pointRadius: 0, pointHoverRadius: 4, tension: 0.15, fill: true,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { maxTicksLimit: 6, callback(v) { return fmtDate(this.getLabelForValue(v)); } } },
        y: { title: { display: true, text: tr("sell_unit_rs_kg") } },
      },
    },
  });
  return true;
}

function needsText(block) {
  const p = { ...(block.needs_params || {}) };
  for (const k of ["first_date", "earliest"]) if (p[k]) p[k] = fmtDate(p[k]);
  return block.needs_key ? tr(block.needs_key, p) : tr("needs_no_data");
}

function windowCard(w) {
  const card = h("div", { class: "border border-gray-200 rounded-xl p-3" },
    h("h3", { class: "font-semibold text-emerald-900" }, tr("sell_win_title", { days: w.window_days })));
  if (w.status === "ok") {
    const amount = fmt(Math.abs(w.change_rs_per_kg));
    const pct = w.change_pct === null ? tr("sell_none") : fmt(Math.abs(w.change_pct), 1);
    let key = "sell_win_flat";
    if (w.change_rs_per_kg > 0) key = "sell_win_up";
    else if (w.change_rs_per_kg < 0) key = "sell_win_down";
    card.append(h("p", { class: "text-lg font-bold" }, tr(key, { amount, pct })));
    card.append(h("p", { class: "status-line mt-1" }, tr("sell_win_compare", { days: w.window_days })));
  } else {
    card.append(h("p", { class: "text-sm" }, needsText(w)));
  }
  return card;
}

function renderTrends() {
  const d = data.trends;
  if (!d) return;
  const canvas = $("trend-chart");
  canvas.setAttribute("aria-label", tr("sell_chart_label"));
  const series = d.series;
  const values = series.map((p) => p.value_per_kg);
  const done = (drawn) => {
    // The text summary is always shown (it is the text alternative for the chart).
    // When Chart.js cannot load (offline), the empty canvas is hidden and a note is added.
    const summary = series.length
      ? tr("sell_chart_summary", { from: fmtDate(series[0].trade_date), to: fmtDate(series[series.length - 1].trade_date),
                                   min: fmt(Math.min(...values)), max: fmt(Math.max(...values)) })
      : "";
    $("trend-chart-summary").textContent = drawn ? summary : `${tr("sell_chart_unavailable")} ${summary}`.trim();
    canvas.parentElement.classList.toggle("hidden", !drawn);
  };
  // Chart.js is fetched on first use so it never blocks first paint.
  loadChartJs().then(() => done(drawTrendChart(canvas, series)), () => done(false));
  $("trend-windows").replaceChildren(...d.windows.map(windowCard));

  const vol = d.volatility;
  $("trend-volatility").replaceChildren(h("div", { class: "border border-gray-200 rounded-xl p-3" },
    h("h3", { class: "font-semibold text-emerald-900" }, tr("sell_vol_title")),
    h("p", { class: "text-sm mt-1" }, vol.status === "ok"
      ? tr("sell_vol_text", { days: vol.window_days, pct: fmt(vol.relative_mad_pct, 1) })
      : needsText(vol))));

  const q = d.quality || {};
  $("trend-confidence").replaceChildren(h("div", { class: "border border-gray-200 rounded-xl p-3" },
    h("h3", { class: "font-semibold text-emerald-900" }, tr("sell_conf_title")),
    h("p", { class: "mt-1" }, h("span", { class: `badge ${q.confidence === "High" ? "badge-ok" : "badge-warn"}` }, tr(`sell_conf_${q.confidence}`))),
    h("p", { class: "text-sm mt-1" }, tr(`sell_conf_expl_${q.confidence}`)),
    h("p", { class: "text-sm mt-1 font-medium" }, tr("sell_conf_text", { n: q.n_mandis ?? 0, date: fmtDate(q.last_updated) })),
    sourceLine(d, q.last_updated)));

  const s = d.seasonal;
  const seasonal = h("div", { class: "border border-gray-200 rounded-xl p-3" },
    h("h3", { class: "font-semibold text-emerald-900" }, tr("sell_season_title")));
  if (s.status === "ok") {
    const rows = s.months.map((m) => h("tr", {},
      h("th", { scope: "row", class: "text-left font-medium py-1 pr-3" }, tr(`sell_month_${m.month}`)),
      h("td", { class: "py-1 pr-3" }, fmt(m.median)),
      h("td", { class: "py-1" }, m.years.join(", "))));
    seasonal.append(h("div", { class: "overflow-x-auto mt-2" }, h("table", { class: "text-sm w-full" },
      h("thead", {}, h("tr", {},
        h("th", { scope: "col", class: "text-left py-1 pr-3" }, tr("sell_col_month")),
        h("th", { scope: "col", class: "text-left py-1 pr-3" }, tr("sell_col_median")),
        h("th", { scope: "col", class: "text-left py-1" }, tr("sell_col_years")))),
      h("tbody", {}, rows))));
  } else {
    seasonal.append(h("p", { class: "text-sm mt-1" }, needsText(s)));
    seasonal.append(h("p", { class: "text-sm mt-1" }, tr("sell_season_days", { days: s.days_saved })));
    if (s.earliest_meaningful_date) seasonal.append(h("p", { class: "text-sm mt-1" }, tr("sell_season_from", { date: fmtDate(s.earliest_meaningful_date) })));
  }
  $("trend-seasonal").replaceChildren(seasonal);
}

async function loadTrends() {
  loading("trends");
  let query = "";
  const raw = $("trend-scope").value;
  if (raw) {
    const s = JSON.parse(raw);
    query = `?market=${encodeURIComponent(s.m)}&state=${encodeURIComponent(s.s)}&district=${encodeURIComponent(s.d)}`;
  }
  try {
    const r = await request(`${BASE}/trends${query}`);
    if (r.status === 404) { empty("trends", "sell_location_none"); return; }
    if (!r.ok) { failed("trends"); return; }
    data.trends = r.data;
    if (!raw) refreshMandiChoices();
    if (!r.data.has_data) { empty("trends", "sell_trend_empty"); return; }
    ready("trends");
    renderTrends();
  } catch (_) { failed("trends"); }
}

// ---------------------------------------------------------------- alerts

function alertPlace(a) {
  return a.market_name
    ? tr("sell_trend_scope_mandi", { market: a.market_name, district: a.district || "" })
    : tr("sell_alert_whole_district", { district: a.district || a.state });
}

function alertRow(a) {
  const place = alertPlace(a);
  const line = tr(a.direction === "at_or_below" ? "sell_alert_line_below" : "sell_alert_line_above",
    { place, target: fmt(a.target_rs_per_kg) });
  const li = h("li", { class: "border border-gray-200 rounded-xl p-3" },
    h("p", { class: "font-medium break-words" }, line),
    h("p", { class: "mt-1" }, h("span", { class: `badge ${a.is_active ? "badge-ok" : "badge-old"}` },
      tr(a.is_active ? "sell_alert_active" : "sell_alert_paused"))),
    h("div", { class: "mt-2 flex flex-wrap gap-2" },
      h("button", { type: "button", class: "btn btn-secondary", "aria-label": `${tr("sell_alert_edit")}: ${line}`,
        onclick: () => startEditAlert(a, li) }, tr("sell_alert_edit")),
      h("button", { type: "button", class: "btn btn-secondary", "aria-label": `${tr(a.is_active ? "sell_alert_pause" : "sell_alert_resume")}: ${line}`,
        onclick: () => toggleAlert(a) }, tr(a.is_active ? "sell_alert_pause" : "sell_alert_resume")),
      h("button", { type: "button", class: "btn btn-danger", "aria-label": `${tr("sell_alert_delete")}: ${line}`,
        onclick: () => deleteAlert(a) }, tr("sell_alert_delete"))));
  return li;
}

/** Change the target price of one alert in place (PUT /alerts/{id}). */
function startEditAlert(a, li) {
  const inputId = `edit-target-${a.id}`;
  const input = h("input", { id: inputId, type: "number", inputmode: "decimal", min: "0.01", step: "any",
    class: "form-input", value: String(a.target_rs_per_kg) });
  const msg = h("p", { class: "status-line mt-1", role: "status", "aria-live": "polite" });
  const save = h("button", { type: "button", class: "btn btn-primary", onclick: async () => {
    const target = numOrNull(input);
    if (target === null || Number.isNaN(target) || target <= 0) {
      msg.textContent = tr("sell_error_validation");
      msg.classList.add("is-error");
      return;
    }
    save.disabled = true;
    try {
      const r = await request(`${BASE}/alerts/${encodeURIComponent(a.id)}`, "PUT", { target_rs_per_kg: target });
      if (!r.ok) {
        msg.textContent = tr(r.status === 422 ? "sell_error_validation" : "sell_error_save");
        msg.classList.add("is-error");
        save.disabled = false;
        return;
      }
      await loadAlerts();
    } catch (_) {
      msg.textContent = tr("sell_error_save");
      msg.classList.add("is-error");
      save.disabled = false;
    }
  } }, tr("sell_alert_save_price"));
  const cancel = h("button", { type: "button", class: "btn btn-secondary", onclick: () => renderAlerts() }, tr("sell_alert_cancel"));
  li.replaceChildren(
    h("label", { class: "form-label", for: inputId }, tr("sell_alert_target")),
    input, msg,
    h("div", { class: "mt-2 flex flex-wrap gap-2" }, save, cancel));
  input.focus();
}

function renderAlerts() {
  const d = data.alerts;
  if (!d) return;
  $("alerts-limit").textContent = tr("sell_alert_limit", { max: d.max_alerts });
  const list = $("alerts-list");
  list.replaceChildren(...(d.alerts.length ? d.alerts.map(alertRow) : [h("li", { class: "status-line" }, tr("sell_alert_empty"))]));
}

async function loadAlerts() {
  loading("alerts");
  try {
    const r = await request(`${BASE}/alerts`);
    if (!r.ok) { failed("alerts"); return; }
    data.alerts = r.data;
    renderAlerts();
    ready("alerts");
  } catch (_) { failed("alerts"); }
}

async function addAlert(ev) {
  ev.preventDefault();
  const status = $("alert-form-status");
  status.classList.remove("is-error");
  const where = $("alert-where").value;
  const target = numOrNull($("alert-target"));
  if (!where || target === null || Number.isNaN(target) || target <= 0) {
    status.textContent = tr("sell_error_validation");
    status.classList.add("is-error");
    return;
  }
  const w = JSON.parse(where);
  $("alert-add").disabled = true;
  try {
    const r = await request(`${BASE}/alerts`, "POST", {
      state: w.s, district: w.d, market_name: w.m, target_rs_per_kg: target, direction: $("alert-direction").value,
    });
    if (r.status === 409) { status.textContent = tr("sell_error_limit", { max: data.alerts?.max_alerts ?? 20 }); status.classList.add("is-error"); return; }
    if (!r.ok) {
      status.textContent = tr(r.status === 422 ? "sell_error_validation" : "sell_error_save");
      status.classList.add("is-error");
      return;
    }
    $("alert-target").value = "";
    status.textContent = tr("sell_alert_added");
    await loadAlerts();
  } catch (_) {
    status.textContent = tr(DEMO ? "sell_error_demo_offline" : "sell_error_save");
    status.classList.add("is-error");
  } finally {
    $("alert-add").disabled = false;
  }
}

async function toggleAlert(a) {
  const status = $("alert-form-status");
  status.classList.remove("is-error");
  try {
    const r = await request(`${BASE}/alerts/${encodeURIComponent(a.id)}`, "PUT", { is_active: !a.is_active });
    if (!r.ok) {
      status.textContent = tr(r.status === 409 ? "sell_error_limit" : "sell_error_save", { max: data.alerts?.max_alerts ?? 20 });
      status.classList.add("is-error");
      return;
    }
    await loadAlerts();
  } catch (_) {
    status.textContent = tr("sell_error_save");
    status.classList.add("is-error");
  }
}

async function deleteAlert(a) {
  if (!window.confirm(tr("sell_alert_confirm_delete"))) return;
  const status = $("alert-form-status");
  status.classList.remove("is-error");
  try {
    const r = await request(`${BASE}/alerts/${encodeURIComponent(a.id)}/delete`, "POST");
    if (!r.ok) { status.textContent = tr("sell_error_save"); status.classList.add("is-error"); return; }
    await loadAlerts();
  } catch (_) {
    status.textContent = tr("sell_error_save");
    status.classList.add("is-error");
  }
}

// ---------------------------------------------------------------- notifications

function notificationRow(n) {
  const p = n.payload || {};
  const place = p.market_name ? tr("sell_trend_scope_mandi", { market: p.market_name, district: p.district || "" })
                              : tr("sell_alert_whole_district", { district: p.district || p.state || "" });
  const text = p.message_key
    ? tr(p.message_key, { place, price: fmt(p.price_per_kg), date: fmtDate(p.trade_date), target: fmt(p.target_per_kg),
                          direction: tr(`sell_dir_${p.direction || "at_or_above"}`) })
    : "";
  return h("li", { class: "border border-gray-200 rounded-xl p-3" },
    n.read_at ? null : h("span", { class: "badge badge-warn mr-2" }, tr("sell_notif_new")),
    h("span", { class: "break-words" }, text),
    h("p", { class: "status-line mt-1" }, p.demo ? tr("sell_source_demo", { date: fmtDate(p.trade_date) })
                                                : tr("sell_source", { source: p.source || "", date: fmtDate(p.trade_date) })),
    n.read_at ? null : h("button", { type: "button", class: "btn btn-secondary mt-2", onclick: () => markRead(n) },
      tr("sell_notif_mark_read")));
}

function renderNotifications() {
  const d = data.notif;
  if (!d) return;
  $("notif-list").replaceChildren(...d.notifications.map(notificationRow));
}

async function loadNotifications() {
  loading("notif");
  try {
    const r = await request(`${BASE}/notifications`);
    if (!r.ok) { failed("notif"); return; }
    data.notif = r.data;
    if (!r.data.notifications.length) { empty("notif", "sell_notif_empty"); return; }
    renderNotifications();
    ready("notif");
  } catch (_) { failed("notif"); }
}

async function markRead(n) {
  try {
    const r = await request(`${BASE}/notifications/${encodeURIComponent(n.id)}/read`, "POST");
    if (!r.ok) { failed("notif", "sell_error_save"); return; }
    await loadNotifications();
  } catch (_) { failed("notif", "sell_error_save"); }
}

// ---------------------------------------------------------------- fairness

function renderFairness() {
  const d = data.fair;
  const body = $("fair-body");
  body.replaceChildren();
  if (!d || d.status !== "ok") return;
  const gap = d.gap_per_kg;
  const key = gap < 0 ? "sell_fair_below" : gap > 0 ? "sell_fair_above" : "sell_fair_equal";
  body.append(h("p", { class: "text-lg font-bold text-emerald-900" }, tr(key, {
    gap: fmt(Math.abs(gap)), total: fmt(Math.abs(d.gap_total_rs)), qty: fmt(d.sale_quantity_kg, 0),
  })));
  body.append(h("p", { class: "text-sm" }, tr("sell_fair_detail", {
    sale: fmt(d.sale_price_per_kg), sale_date: fmtDate(d.sale_date), market: fmt(d.market_median_per_kg),
    price_date: fmtDate(d.price_date), n: d.n_mandis, radius: fmt(d.radius_km, 0),
  })));
  body.append(h("div", { class: "bg-amber-50 border border-amber-300 rounded-xl p-3 text-sm text-amber-900" },
    h("p", { class: "font-semibold" }, tr("sell_fair_caveat_title")),
    h("p", { class: "mt-1" }, tr("sell_fair_caveat")),
    d.notes && d.notes.length ? h("ul", { class: "mt-2 flex flex-col gap-1" }, d.notes.map((n) => h("li", {}, tr(n.key)))) : null));
  body.append(sourceLine(d, d.price_date));
}

async function loadFairness() {
  loading("fair");
  try {
    const r = await request(`${BASE}/fairness`);
    if (r.status === 404) { empty("fair", "sell_location_none"); return; }
    if (!r.ok) { failed("fair"); return; }
    data.fair = r.data;
    if (r.data.status !== "ok") {
      // The API sends `reason` (for example "no_origin"); the text key is sell_fairness_<reason>.
      const reasonKey = `sell_fairness_${r.data.reason}`;
      empty("fair", TRANSLATIONS.en[reasonKey] ? reasonKey : "sell_fairness_no_sale");
      return;
    }
    renderFairness();
    ready("fair");
  } catch (_) { failed("fair"); }
}

// ---------------------------------------------------------------- language and start-up

function renderAll() {
  document.documentElement.lang = getCurrentLang();
  document.querySelectorAll("[data-aria-i18n]").forEach((node) => {
    node.setAttribute("aria-label", tr(node.getAttribute("data-aria-i18n")));
  });
  refreshMandiChoices();
  renderSettings();
  if (view.ranking?.mode === "ready") renderRanking();
  if (view.trends?.mode === "ready") renderTrends();
  if (view.alerts?.mode === "ready") renderAlerts();
  if (view.notif?.mode === "ready") renderNotifications();
  if (view.fair?.mode === "ready") renderFairness();
  for (const s of SECTIONS) paintStatus(s);
}

function switchLanguage(lang) {
  setLanguage(lang);
  renderAll();
}

async function start() {
  installSellTranslations();
  initTranslator();

  if (DEMO) {
    $("demo-banner").classList.remove("hidden");
  } else {
    // Normal mode: load auth and the API client only now, and require a session.
    // (routeGuard in js/auth.js only protects pages on its own list, so the
    // session is checked directly here.)
    const [auth, api] = await Promise.all([import("./auth.js"), import("./api.js")]);
    apiMod = api;
    const session = await auth.getSession();
    if (!session) { window.location.href = "login.html"; return; }
  }

  $("lang-en").addEventListener("click", () => switchLanguage("en"));
  $("lang-hi").addEventListener("click", () => switchLanguage("hi"));
  el.mode().addEventListener("change", toggleModeFields);
  $("settings-form").addEventListener("submit", saveSettings);
  $("sugg-apply").addEventListener("click", applySuggestion);
  $("alert-form").addEventListener("submit", addAlert);
  $("trend-scope").addEventListener("change", loadTrends);
  $("settings-retry").addEventListener("click", loadSettings);
  $("ranking-retry").addEventListener("click", loadRanking);
  $("trends-retry").addEventListener("click", loadTrends);
  $("alerts-retry").addEventListener("click", loadAlerts);
  $("notif-retry").addEventListener("click", loadNotifications);
  $("fair-retry").addEventListener("click", loadFairness);

  renderAll();
  await loadSettings();
  await Promise.all([loadRanking(), loadTrends(), loadAlerts(), loadNotifications(), loadFairness()]);
  renderAll();
}

start();
