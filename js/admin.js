/**
 * admin.js - Knowledge admin page (admin.html).
 *
 * Talks to /api/admin/knowledge/* (backend/routers/knowledge_admin.py). The page shows
 * nothing until GET /me answers 200:
 *   no session -> login.html;  401 -> login.html;  403 -> access-denied card, no more API calls;
 *   200 -> screens by role (admin: everything, reviewer: read, comment, approve, propose).
 * The server decides what is allowed; buttons only mirror detail.allowed_actions.
 *
 * All server text (item statements, sources, names, reasons) is inserted with textContent
 * through h(); no innerHTML is ever built from data. Hindi item text is shown as stored,
 * with a "machine translated, needs native review" tag.
 */
import { TRANSLATIONS } from "./i18n.js";
import { installAdminTranslations } from "./admin-i18n.js";
import { init as initTranslator, setLanguage, getCurrentLang } from "./translator.js";

const BASE = "/api/admin/knowledge";
const TOPICS = ["varieties", "climate_soil", "planting_system", "propagation", "bahar_crop_regulation",
  "canopy_pruning", "nutrient_management", "irrigation", "flowering_fruit_set", "pests", "diseases",
  "harvest_maturity", "post_harvest", "yield", "economics"];
const REGIONS = ["MP", "MH", "ALL"];
const STATUSES = ["DRAFT", "IN_REVIEW", "CHANGES_REQUESTED", "APPROVED", "REJECTED", "RETIRED"];
const RISKS = ["LOW", "MEDIUM", "HIGH"];
const CONFIDENCE = ["official_guideline", "peer_reviewed", "secondary"];
const ACCESS = ["opened_read", "opened_partial", "found_not_opened", "pdf_unreadable"];
const BAHAR = ["", "ambe", "mrig", "hasta", "any"];
const ID_RE = /^GUA-[A-Z]{3,6}-\d{4}$/;
const MAX_QUOTE_WORDS = 29;
const ACTION_DEF = {
  submit: { path: "submit", needReason: false },
  approve: { path: "approve", needReason: false },
  reject: { path: "reject", needReason: true },
  request_changes: { path: "request-changes", needReason: true },
  retire: { path: "retire", needReason: true },
  restore: { path: "restore", needReason: true },
};

let apiMod = null;
const state = {
  me: null,
  denied: false,
  view: "dashboard",
  dashboard: null,
  list: null,
  filters: { q: "", topic: "", region: "", status: "", risk_level: "", has_conflict: "", needs_review: "", page: 1 },
  detailId: null,
  detail: null,
  compare: {},        // version number -> { payload } | { error }
  pendingAction: null,
  reviewers: null,
  form: null,         // { mode, itemId, rowVersion, draft }
  notice: null,       // { kind: "ok" | "err", text, list? }
};
let uid = 0;

// ---------------------------------------------------------------- helpers

function tr(key, vars = {}) {
  const lang = getCurrentLang();
  const text = TRANSLATIONS[lang]?.[key] ?? TRANSLATIONS.en?.[key];
  if (text === undefined) return key;
  return text.replace(/\{(\w+)\}/g, (m, name) => (name in vars ? String(vars[name]) : m));
}

/** Label for an enum value (status, risk, topic ...) with the raw value as fallback. */
function label(prefix, value) {
  const key = `${prefix}${value}`;
  const lang = getCurrentLang();
  return TRANSLATIONS[lang]?.[key] ?? TRANSLATIONS.en?.[key] ?? String(value);
}

/** Tiny DOM builder. Strings become text nodes (never HTML). */
function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "text") el.textContent = v;
    else if (k === "value") el.value = v;
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
const isAdmin = () => state.me?.role === "admin";

function fmtDateTime(iso) {
  if (!iso) return "-";
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/.exec(String(iso));
  if (!m) return String(iso);
  return `${m[3]}/${m[2]}/${m[1]}` + (m[4] ? ` ${m[4]}:${m[5]}` : "");
}

function humanize(s) { return String(s ?? "").replace(/_/g, " "); }

function short(v, n = 160) {
  let s;
  try { s = typeof v === "string" ? v : JSON.stringify(v); } catch (_) { s = String(v); }
  if (s === undefined) s = "";
  return s.length > n ? s.slice(0, n) + "..." : s;
}

function wordCount(s) { return String(s).trim().split(/\s+/).filter(Boolean).length; }
function isHttpUrl(s) { return /^https?:\/\/[^\s/]+\S*$/i.test(String(s).trim()); }

async function request(path, method = "GET", body) {
  const opts = { method };
  if (body !== undefined) opts.body = JSON.stringify(body);
  let res;
  try {
    res = await apiMod.apiFetch(BASE + path, opts);
  } catch (_) {
    return { ok: false, status: 0, data: null };
  }
  if (res.status === 401) {
    window.location.href = "login.html";
    return new Promise(() => {}); // the page is leaving; never continue
  }
  let data = null;
  try { data = await res.json(); } catch (_) { /* empty or non-JSON body */ }
  return { ok: res.ok, status: res.status, data };
}

/** Turn a failed response into { text, list } for the notice box. */
function explain(res) {
  const detail = res.data?.detail;
  if (res.status === 422 && Array.isArray(detail)) {
    return { text: tr("adm_error_validation"),
      list: detail.slice(0, 12).map((d) => `${(d.loc || []).filter((x) => x !== "body").join(".")}: ${d.msg}`) };
  }
  if (res.status === 409) {
    return { text: tr("adm_error_conflict") + (typeof detail === "string" ? ` (${detail})` : "") };
  }
  if (res.status === 403) return { text: tr("adm_error_forbidden") };
  if (res.status === 429) return { text: tr("adm_error_ratelimit") };
  if (res.status === 503 || res.status === 0) return { text: tr("adm_error_unavailable") };
  return { text: tr("adm_error_generic") };
}

function setNotice(kind, text, list) { state.notice = { kind, text, list }; }

function noticeNode() {
  const n = state.notice;
  if (!n) return null;
  return h("div", { class: `notice ${n.kind === "ok" ? "notice-ok" : "notice-err"}`, role: n.kind === "ok" ? "status" : "alert" },
    h("p", { text: n.text }),
    n.list ? h("ul", { class: "list-disc pl-5 mt-1" }, n.list.map((t) => h("li", { text: t }))) : null);
}

// ---------------------------------------------------------------- shell

function root() { return $("app"); }

function header() {
  const lang = getCurrentLang();
  const langBtn = (code, key) => h("button", {
    type: "button", id: `lang-${code}`, class: `lang-btn${lang === code ? " lang-active" : ""}`, lang: code,
    "aria-pressed": lang === code ? "true" : "false", text: tr(key),
    onclick: () => switchLanguage(code),
  });
  return h("header", { class: "bg-brand-primary text-white shadow-lg rounded-xl" },
    h("div", { class: "px-4 py-3 flex flex-wrap items-center justify-between gap-3" },
      h("div", { class: "min-w-0" },
        h("h1", { class: "text-lg font-bold", text: tr("adm_heading") }),
        state.me ? h("p", { class: "text-sm text-green-100", text: `${tr(`adm_role_${state.me.role}`)}${state.me.display_name ? " - " + state.me.display_name : ""}` }) : null),
      h("div", { class: "flex gap-2", role: "group", "aria-label": tr("adm_language") },
        langBtn("en", "adm_lang_en"), langBtn("hi", "adm_lang_hi"))));
}

function tabs() {
  const items = [["dashboard", "adm_tab_dashboard"], ["items", "adm_tab_items"]];
  if (isAdmin()) items.push(["add", "adm_tab_add"], ["reviewers", "adm_tab_reviewers"]);
  const current = state.view === "detail" ? "items" : (state.view === "form" && state.form?.mode !== "create" ? "items" : (state.view === "form" ? "add" : state.view));
  return h("nav", { class: "flex flex-wrap gap-2", "aria-label": tr("adm_heading") },
    items.map(([view, key]) => h("button", {
      type: "button", class: "btn tab", "aria-current": current === view ? "page" : null, text: tr(key),
      onclick: () => go(view),
    })));
}

function render(body) {
  const app = root();
  app.replaceChildren(header());
  if (state.me) app.append(tabs());
  app.append(h("div", { class: "banner", role: "note", text: tr("adm_banner") }));
  const n = noticeNode();
  if (n) app.append(n);
  if (body) app.append(body);
}

function switchLanguage(lang) {
  setLanguage(lang);
  document.title = tr("adm_page_title");
  rerender();
}

function rerender() {
  if (!state.me) return state.denied ? renderDenied() : renderBootError();
  if (state.view === "dashboard") return paintDashboard();
  if (state.view === "items") return paintList();
  if (state.view === "detail") return paintDetail();
  if (state.view === "form") return paintForm();
  if (state.view === "reviewers") return paintReviewers();
}

async function go(view) {
  state.notice = null;
  state.pendingAction = null;
  if (view === "dashboard") return loadDashboard();
  if (view === "items") return loadList();
  if (view === "add") return openForm("create");
  if (view === "reviewers" && isAdmin()) return loadReviewers();
}

function loadingBody() {
  return h("p", { class: "status-line", role: "status", text: tr("adm_loading") });
}

function retryBody(fn) {
  return h("div", { class: "section-card flex flex-col gap-2" },
    h("p", { class: "status-line", role: "alert", text: tr("adm_error_generic") }),
    h("button", { type: "button", class: "btn btn-secondary", text: tr("adm_retry"), onclick: fn }));
}

function chip(text, cls = "") { return h("span", { class: `chip ${cls}`.trim(), text }); }

function itemChips(it) {
  return h("div", { class: "flex flex-wrap gap-2" },
    chip(label("adm_status_", it.status), `chip-${it.status}`),
    chip(label("adm_risk_", it.risk_level), `chip-${it.risk_level}`),
    chip(label("adm_region_", it.region)),
    chip(label("adm_topic_", it.topic)),
    it.has_conflict ? chip(tr("adm_conflict_tag"), "chip-warn") : null);
}

// ---------------------------------------------------------------- dashboard

async function loadDashboard() {
  state.view = "dashboard";
  render(loadingBody());
  const res = await request("/dashboard");
  if (!res.ok) { render(retryBody(loadDashboard)); return; }
  state.dashboard = res.data;
  paintDashboard();
}

async function downloadExport(kind) {
  const ext = kind === "csv" ? "csv" : "json";
  const res = await apiMod.apiFetch(`${BASE}/export.${ext}`, { method: "GET" }).catch(() => null);
  if (!res || !res.ok) {
    setNotice("err", res ? explain({ status: res.status }).text : tr("adm_error_unavailable"));
    return rerender();
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = h("a", { href: url, download: `guava-knowledge.${ext}` });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
  setNotice("ok", tr("adm_export_done"));
  rerender();
}

async function runImport(dry) {
  const res = await request("/import-seed", "POST", { dry_run: dry });
  if (!res.ok) { const e = explain(res); setNotice("err", e.text, e.list); return rerender(); }
  setNotice("ok", tr(dry ? "adm_import_dry_result" : "adm_import_result", res.data));
  if (!dry) return loadDashboardKeepNotice();
  rerender();
}

async function loadDashboardKeepNotice() {
  const keep = state.notice;
  await loadDashboard();
  if (keep) { state.notice = keep; paintDashboard(); }
}

async function runSweep() {
  const res = await request("/sweep-expired", "POST");
  if (!res.ok) { const e = explain(res); setNotice("err", e.text, e.list); return rerender(); }
  const n = (res.data?.expired || []).length;
  const keepText = tr("adm_sweep_result", { n });
  await loadDashboard();
  setNotice("ok", keepText);
  paintDashboard();
}

function statCard(titleText, value, onclick) {
  return h("div", { class: "section-card flex flex-col gap-1" },
    h("p", { class: "text-sm font-semibold text-gray-700", text: titleText }),
    h("p", { class: "text-2xl font-bold text-emerald-900", text: String(value) }),
    onclick ? h("button", { type: "button", class: "btn btn-secondary", text: tr("adm_dash_view_status"), onclick }) : null);
}

function countList(title, counts, prefix, onPick) {
  const entries = Object.entries(counts || {}).filter(([, n]) => n > 0);
  return h("section", { class: "section-card flex flex-col gap-2" },
    h("h2", { class: "font-bold text-emerald-900 text-lg", text: title }),
    entries.length ? h("ul", { class: "flex flex-col gap-1" }, entries.map(([k, n]) =>
      h("li", { class: "flex items-center justify-between gap-2 min-h-[44px]" },
        h("span", { text: label(prefix, k) }),
        onPick ? h("button", { type: "button", class: "btn btn-secondary", "aria-label": `${label(prefix, k)}: ${n}`, text: String(n), onclick: () => onPick(k) })
               : h("strong", { text: String(n) })))) : h("p", { class: "status-line", text: "-" }));
}

function paintDashboard() {
  const d = state.dashboard;
  if (!d) return;
  const jump = (key) => (value) => { state.filters = { ...blankFilters(), [key]: value }; loadList(); };
  const body = h("div", { class: "flex flex-col gap-4" },
    d.expired_just_now?.length ? h("div", { class: "notice notice-err", role: "status", text: tr("adm_dash_expired_now", { n: d.expired_just_now.length }) }) : null,
    h("div", { class: "grid grid-cols-1 sm:grid-cols-3 gap-3" },
      statCard(tr("adm_dash_total"), d.total),
      statCard(tr("adm_dash_high_review"), d.high_risk_in_review, () => { state.filters = { ...blankFilters(), status: "IN_REVIEW", risk_level: "HIGH" }; loadList(); }),
      statCard(tr("adm_dash_conflicts"), d.with_conflict, () => { state.filters = { ...blankFilters(), has_conflict: "true" }; loadList(); })),
    countList(tr("adm_dash_by_status"), d.by_status, "adm_status_", jump("status")),
    countList(tr("adm_dash_by_risk"), d.by_risk, "adm_risk_", jump("risk_level")),
    countList(tr("adm_dash_by_topic"), d.by_topic, "adm_topic_", jump("topic")),
    h("section", { class: "section-card flex flex-col gap-2" },
      h("h2", { class: "font-bold text-emerald-900 text-lg", text: tr("adm_dash_expiring") }),
      d.expiring_soon?.length ? h("ul", { class: "flex flex-col gap-1" }, d.expiring_soon.map((e) =>
        h("li", { class: "flex items-center justify-between gap-2 min-h-[44px]" },
          h("span", { text: `${e.id} - ${fmtDateTime(e.expires_at)}` }),
          h("button", { type: "button", class: "btn btn-secondary", text: tr("adm_dash_open"), onclick: () => openDetail(e.id) }))))
        : h("p", { class: "status-line", text: tr("adm_dash_expiring_none") })),
    isAdmin() ? h("section", { class: "section-card flex flex-col gap-2" },
      h("h2", { class: "font-bold text-emerald-900 text-lg", text: tr("adm_admin_tools") }),
      h("div", { class: "flex flex-wrap gap-2" },
        h("button", { type: "button", class: "btn btn-secondary", text: tr("adm_import_dry"), onclick: () => runImport(true) }),
        h("button", { type: "button", class: "btn btn-primary", text: tr("adm_import_seed"), onclick: () => runImport(false) }),
        h("button", { type: "button", class: "btn btn-secondary", text: tr("adm_sweep"), onclick: runSweep }),
        h("button", { type: "button", class: "btn btn-secondary", text: tr("adm_export_csv"), onclick: () => downloadExport("csv") }),
        h("button", { type: "button", class: "btn btn-secondary", text: tr("adm_export_json"), onclick: () => downloadExport("json") }))) : null);
  render(body);
}

// ---------------------------------------------------------------- list

function blankFilters() {
  return { q: "", topic: "", region: "", status: "", risk_level: "", has_conflict: "", needs_review: "", page: 1 };
}

function listQuery() {
  const f = state.filters;
  const p = new URLSearchParams();
  if (f.q.trim()) p.set("q", f.q.trim());
  if (f.topic) p.set("topic", f.topic);
  if (f.region) p.set("region", f.region);
  const status = f.needs_review === "true" ? "IN_REVIEW" : f.status;
  if (status) p.set("status", status);
  if (f.risk_level) p.set("risk_level", f.risk_level);
  if (f.has_conflict === "true") p.set("has_conflict", "true");
  p.set("page", String(f.page));
  p.set("page_size", "25");
  return p.toString();
}

async function loadList() {
  state.view = "items";
  render(loadingBody());
  const res = await request(`/items?${listQuery()}`);
  if (!res.ok) { render(retryBody(loadList)); return; }
  state.list = res.data;
  paintList();
}

function selectField(id, labelText, options, value, onchange) {
  return h("div", {},
    h("label", { for: id, class: "form-label", text: labelText }),
    h("select", { id, class: "form-input", onchange: (e) => onchange(e.target.value) },
      options.map(([v, t]) => h("option", { value: v, selected: v === value ? true : null, text: t }))));
}

function paintList() {
  const f = state.filters;
  const all = [["", tr("adm_filter_all")]];
  const form = h("form", { class: "section-card flex flex-col gap-3", novalidate: true,
    onsubmit: (e) => { e.preventDefault(); state.filters.page = 1; loadList(); } },
    h("div", {},
      h("label", { for: "f-q", class: "form-label", text: tr("adm_search") }),
      h("input", { id: "f-q", type: "search", class: "form-input", maxlength: "100", placeholder: tr("adm_search_ph"), value: f.q,
        oninput: (e) => { state.filters.q = e.target.value; } })),
    h("div", { class: "grid grid-cols-1 sm:grid-cols-2 gap-3" },
      selectField("f-topic", tr("adm_filter_topic"), all.concat(TOPICS.map((t) => [t, label("adm_topic_", t)])), f.topic, (v) => { state.filters.topic = v; }),
      selectField("f-region", tr("adm_filter_region"), all.concat(REGIONS.map((t) => [t, label("adm_region_", t)])), f.region, (v) => { state.filters.region = v; }),
      selectField("f-status", tr("adm_filter_status"), all.concat(STATUSES.map((t) => [t, label("adm_status_", t)])), f.status, (v) => { state.filters.status = v; }),
      selectField("f-risk", tr("adm_filter_risk"), all.concat(RISKS.map((t) => [t, label("adm_risk_", t)])), f.risk_level, (v) => { state.filters.risk_level = v; }),
      selectField("f-conflict", tr("adm_filter_conflict"), [["", tr("adm_filter_all")], ["true", tr("adm_filter_yes")]], f.has_conflict, (v) => { state.filters.has_conflict = v; }),
      selectField("f-review", tr("adm_filter_review"), [["", tr("adm_filter_all")], ["true", tr("adm_filter_review_yes")]], f.needs_review, (v) => { state.filters.needs_review = v; })),
    h("div", { class: "flex flex-wrap gap-2" },
      h("button", { type: "submit", class: "btn btn-primary", text: tr("adm_filter_apply") }),
      h("button", { type: "button", class: "btn btn-secondary", text: tr("adm_filter_clear"),
        onclick: () => { state.filters = blankFilters(); loadList(); } }),
      isAdmin() ? h("button", { type: "button", class: "btn btn-secondary", text: tr("adm_export_csv"), onclick: () => downloadExport("csv") }) : null,
      isAdmin() ? h("button", { type: "button", class: "btn btn-secondary", text: tr("adm_export_json"), onclick: () => downloadExport("json") }) : null));

  const L = state.list;
  const pages = Math.max(1, Math.ceil((L.total || 0) / (L.page_size || 25)));
  const cards = L.items.length
    ? h("ul", { class: "flex flex-col gap-3" }, L.items.map((it) =>
        h("li", { class: "section-card flex flex-col gap-2" },
          h("p", { class: "font-bold", text: it.id }),
          h("p", { text: it.summary || "" }),
          itemChips(it),
          h("button", { type: "button", class: "btn btn-secondary self-start", text: tr("adm_dash_open"), "aria-label": `${tr("adm_dash_open")} ${it.id}`, onclick: () => openDetail(it.id) }))))
    : h("p", { class: "status-line section-card", text: tr("adm_list_empty") });
  const pager = h("div", { class: "flex flex-wrap items-center gap-2" },
    h("button", { type: "button", class: "btn btn-secondary", text: tr("adm_page_prev"), disabled: L.page <= 1 ? true : null,
      onclick: () => { state.filters.page = Math.max(1, L.page - 1); loadList(); } }),
    h("span", { class: "status-line", text: tr("adm_page_of", { page: L.page, pages }) }),
    h("button", { type: "button", class: "btn btn-secondary", text: tr("adm_page_next"), disabled: L.page >= pages ? true : null,
      onclick: () => { state.filters.page = L.page + 1; loadList(); } }));
  render(h("div", { class: "flex flex-col gap-4" },
    h("h2", { class: "font-bold text-emerald-900 text-lg", text: `${tr("adm_list_title")} - ${tr("adm_list_count", { n: L.total })}` }),
    form, cards, pager));
}

// ---------------------------------------------------------------- detail

async function openDetail(id) {
  state.view = "detail";
  state.detailId = id;
  state.compare = {};
  state.pendingAction = null;
  state.notice = null;
  await reloadDetail();
}

async function reloadDetail(keepNotice = false) {
  const keep = keepNotice ? state.notice : null;
  render(loadingBody());
  const res = await request(`/items/${encodeURIComponent(state.detailId)}`);
  if (!res.ok) { render(retryBody(reloadDetail)); return; }
  state.detail = res.data;
  state.notice = keep;
  paintDetail();
}

function kv(name, value) {
  return h("div", { class: "flex flex-col" },
    h("span", { class: "text-sm font-semibold text-gray-700", text: name }),
    h("span", { text: value === null || value === undefined || value === "" ? "-" : String(value) }));
}

function card(title, ...kids) {
  return h("section", { class: "section-card flex flex-col gap-2" },
    h("h2", { class: "font-bold text-emerald-900 text-lg", text: title }), ...kids);
}

function valueText(v) {
  const bits = [];
  if (v.value !== null && v.value !== undefined) bits.push(String(v.value));
  if (v.min !== null && v.min !== undefined) bits.push(`min ${v.min}`);
  if (v.max !== null && v.max !== undefined) bits.push(`max ${v.max}`);
  const unit = v.unit ? ` ${v.unit}` : "";
  const per = v.per ? ` / ${v.per}` : "";
  return `${v.name}: ${bits.join(", ")}${unit}${per}`;
}

function applicabilityLines(a) {
  const out = [];
  if (!a) return out;
  if (a.tree_age_months_min != null || a.tree_age_months_max != null)
    out.push(`${tr("adm_f_age_min")}: ${a.tree_age_months_min ?? "-"}; ${tr("adm_f_age_max")}: ${a.tree_age_months_max ?? "-"}`);
  if (a.months?.length) out.push(`${tr("adm_f_months")}: ${a.months.join(", ")}`);
  if (a.bahar) out.push(`${tr("adm_f_bahar")}: ${a.bahar}`);
  if (a.irrigation_type) out.push(`${tr("adm_f_irrigation")}: ${a.irrigation_type}`);
  if (a.planting_system) out.push(`${tr("adm_f_planting")}: ${a.planting_system}`);
  if (a.varieties?.length) out.push(`${tr("adm_f_varieties")}: ${a.varieties.join(", ")}`);
  return out;
}

function diffLines(diff) {
  const entries = Object.entries(diff || {});
  if (!entries.length) return null;
  return h("ul", { class: "flex flex-col gap-1" }, entries.slice(0, 30).map(([path, d]) =>
    h("li", { class: "diff-line", text: `${path}: ${short(d?.before, 120)} -> ${short(d?.after, 120)}` })));
}

function payloadDiff(oldP, newP) {
  const keys = new Set([...Object.keys(oldP || {}), ...Object.keys(newP || {}), ]);
  const out = {};
  for (const k of keys) {
    if (JSON.stringify(oldP?.[k]) !== JSON.stringify(newP?.[k])) out[k] = { before: oldP?.[k], after: newP?.[k] };
  }
  return out;
}

function paintDetail() {
  const D = state.detail;
  const it = D.item;
  const p = D.current?.payload || {};
  const high = it.risk_level === "HIGH";
  const sections = [];

  sections.push(h("button", { type: "button", class: "btn btn-secondary self-start", text: tr("adm_back_list"), onclick: () => (state.list ? paintListOrLoad() : loadList()) }));
  sections.push(h("section", { class: "section-card flex flex-col gap-2" },
    h("h2", { class: "font-bold text-lg", text: it.id }),
    itemChips(it),
    kv(tr("adm_f_subtopic"), it.subtopic),
    it.approved_at ? kv(tr("adm_approved_on"), fmtDateTime(it.approved_at)) : null,
    it.expires_at ? kv(tr("adm_expires"), fmtDateTime(it.expires_at)) : null,
    it.retired_reason ? kv(tr("adm_act_reason"), it.retired_reason) : null));

  sections.push(card(tr("adm_statement_en"), h("p", { text: p.statement_en || "" })));
  sections.push(card(tr("adm_statement_hi"),
    h("p", { lang: "hi", text: p.statement_hi || "" }),
    p.hi_reviewed ? chip(tr("adm_hi_reviewed_tag"), "chip-APPROVED") : chip(tr("adm_hi_tag"), "chip-warn")));

  const vals = p.values || [];
  sections.push(card(tr("adm_values"), vals.length ? h("ul", { class: "list-disc pl-5" }, vals.map((v) => h("li", { text: valueText(v) }))) : h("p", { text: tr("adm_values_none") })));
  const al = applicabilityLines(p.applicability);
  sections.push(card(tr("adm_applicability"), al.length ? h("ul", { class: "list-disc pl-5" }, al.map((t) => h("li", { text: t }))) : h("p", { text: tr("adm_applicability_none") })));
  sections.push(card(tr("adm_f_confidence"), h("p", { text: label("adm_conf_", p.source_confidence) }),
    p.retrieved_on ? kv(tr("adm_f_retrieved"), p.retrieved_on) : null,
    p.involves_chemical ? chip(tr("adm_f_chemical"), "chip-HIGH") : null,
    p.cibrc_check_required ? chip(tr("adm_f_cibrc"), "chip-warn") : null));

  sections.push(card(tr("adm_sources"), (p.sources || []).map((s) => sourceBlock(s))));
  sections.push(card(tr("adm_conflicts"), (p.conflicts || []).length
    ? (p.conflicts || []).map((c) => h("div", { class: "flex flex-col gap-1 border-t pt-2" },
        h("p", { class: "font-semibold", text: c.source_title }),
        h("p", { class: "quote", text: c.quote }),
        h("p", { text: c.note }),
        safeLink(c.url, tr("adm_source_open"))))
    : h("p", { text: tr("adm_conflicts_none") })));

  sections.push(actionsCard(D, it, high));
  sections.push(proposalsCard(D));
  sections.push(versionsCard(D));
  sections.push(approvalsCard(D));
  sections.push(commentsCard(D));
  sections.push(auditCard(D));
  render(h("div", { class: "flex flex-col gap-4" }, sections.filter(Boolean)));
}

function paintListOrLoad() {
  if (!state.list) return loadList();
  state.view = "items";
  state.notice = null;
  return paintList();
}

function safeLink(url, text) {
  if (!isHttpUrl(url)) return h("span", { class: "status-line", text: String(url || "") });
  return h("a", { class: "src-link", href: url, target: "_blank", rel: "noopener noreferrer", text });
}

function sourceBlock(s) {
  return h("div", { class: "flex flex-col gap-1 border-t pt-2" },
    h("p", { class: "font-semibold", text: s.title }),
    h("p", { text: `${s.publisher}${s.year ? ", " + s.year : ""}${s.page ? ", p. " + s.page : ""}` }),
    kv(tr("adm_source_section"), s.section_or_table),
    h("p", { class: "quote", text: s.quote }),
    kv(tr("adm_source_access"), label("adm_access_", s.access)),
    safeLink(s.url, tr("adm_source_open")));
}

function actionsCard(D, it, high) {
  const allowed = D.allowed_actions || [];
  const buttons = [];
  if (allowed.includes("edit") && isAdmin()) buttons.push(h("button", { type: "button", class: "btn btn-primary", text: tr("adm_act_edit"), onclick: () => openForm("edit") }));
  if (!isAdmin() && it.status !== "RETIRED") buttons.push(h("button", { type: "button", class: "btn btn-secondary", text: tr("adm_act_propose"), onclick: () => openForm("propose") }));
  for (const name of Object.keys(ACTION_DEF)) {
    if (!allowed.includes(name)) continue;
    const blocked = name === "approve" && D.approve_blocked_reason;
    buttons.push(h("button", { type: "button", class: `btn ${name === "reject" || name === "retire" ? "btn-danger" : "btn-secondary"}`,
      text: tr(`adm_act_${name}`), disabled: blocked ? true : null, onclick: () => { state.pendingAction = name; paintDetail(); } }));
  }
  const kids = [];
  if (!buttons.length) kids.push(h("p", { text: tr("adm_actions_none") }));
  else kids.push(h("div", { class: "flex flex-wrap gap-2" }, buttons));
  if (D.approve_blocked_reason && allowed.includes("approve")) {
    kids.push(h("p", { class: "notice notice-err", text: tr("adm_approve_blocked", { reason: D.approve_blocked_reason }) }));
  }
  if (state.pendingAction) kids.push(actionPanel(it, high));
  return card(tr("adm_actions"), ...kids);
}

function actionPanel(it, high) {
  const name = state.pendingAction;
  const def = ACTION_DEF[name];
  const id = `act-reason-${++uid}`;
  const err = h("p", { class: "notice notice-err hidden", role: "alert", text: tr("adm_act_reason_required") });
  const ta = h("textarea", { id, class: "form-input", maxlength: "1000" });
  return h("form", { class: "flex flex-col gap-2 border-t pt-2", novalidate: true,
    onsubmit: async (e) => {
      e.preventDefault();
      const reason = ta.value.trim();
      if (def.needReason && reason.length < 3) { err.classList.remove("hidden"); ta.focus(); return; }
      const body = { expected_row_version: it.row_version };
      if (reason) body.reason = reason;
      const res = await request(`/items/${encodeURIComponent(it.id)}/${def.path}`, "POST", body);
      state.pendingAction = null;
      if (res.ok) { setNotice("ok", tr("adm_act_done")); return reloadDetail(true); }
      const ex = explain(res);
      setNotice("err", ex.text, ex.list);
      return reloadDetail(true);
    } },
    h("p", { class: "font-semibold", text: tr(`adm_act_${name}`) }),
    name === "approve" && high ? h("p", { class: "notice notice-err", text: tr("adm_high_note") }) : null,
    h("label", { for: id, class: "form-label", text: tr("adm_act_reason") }), ta, err,
    h("div", { class: "flex flex-wrap gap-2" },
      h("button", { type: "submit", class: "btn btn-primary", text: tr("adm_act_confirm") }),
      h("button", { type: "button", class: "btn btn-secondary", text: tr("adm_act_cancel"), onclick: () => { state.pendingAction = null; paintDetail(); } })));
}

function proposalsCard(D) {
  const props = D.pending_proposals || [];
  if (!props.length) return null;
  const it = D.item;
  return card(tr("adm_proposals"), props.map((pv) => h("div", { class: "flex flex-col gap-2 border-t pt-2" },
    h("p", { class: "font-semibold", text: `v${pv.version} - ${tr("adm_proposal_by", { who: pv.created_by })} - ${fmtDateTime(pv.created_at)}` }),
    pv.change_reason ? h("p", { text: pv.change_reason }) : null,
    diffLines(payloadDiff(D.current?.payload, pv.payload)),
    isAdmin() ? h("div", { class: "flex flex-wrap gap-2" },
      h("button", { type: "button", class: "btn btn-primary", text: tr("adm_proposal_accept"), onclick: () => proposalAction(it, pv.version, "accept") }),
      h("button", { type: "button", class: "btn btn-danger", text: tr("adm_proposal_decline"), onclick: () => proposalAction(it, pv.version, "decline") })) : null)));
}

async function proposalAction(it, n, what) {
  let reason;
  if (what === "decline") {
    reason = window.prompt(tr("adm_act_reason"), "") || "";
    if (reason.trim().length < 3) { setNotice("err", tr("adm_act_reason_required")); return paintDetail(); }
  }
  const body = { expected_row_version: it.row_version };
  if (reason) body.reason = reason.trim();
  const res = await request(`/items/${encodeURIComponent(it.id)}/proposals/${n}/${what}`, "POST", body);
  if (res.ok) setNotice("ok", tr("adm_act_done"));
  else { const ex = explain(res); setNotice("err", ex.text, ex.list); }
  return reloadDetail(true);
}

function versionsCard(D) {
  return card(tr("adm_versions"), h("ul", { class: "flex flex-col gap-3" }, (D.versions || []).map((v) => {
    const cmp = state.compare[v.version];
    return h("li", { class: "flex flex-col gap-1 border-t pt-2" },
      h("p", { class: "font-semibold", text: `v${v.version}${v.version === D.item.current_version && !v.is_proposal ? " (" + tr("adm_version_current") + ")" : ""}${v.is_proposal ? " (" + tr("adm_version_proposal") + ")" : ""}` }),
      h("p", { text: `${fmtDateTime(v.created_at)} - ${v.created_by}` }),
      v.change_reason ? h("p", { text: v.change_reason }) : null,
      v.version !== D.item.current_version ? h("button", { type: "button", class: "btn btn-secondary self-start", text: tr("adm_version_compare"), onclick: () => compareVersion(v.version) }) : null,
      cmp?.diff ? (Object.keys(cmp.diff).length
        ? h("div", {}, h("p", { class: "text-sm", text: `${tr("adm_diff_before")}: v${v.version} -> ${tr("adm_diff_after")}: ${tr("adm_version_current")}` }), diffLines(cmp.diff))
        : h("p", { text: tr("adm_version_diff_none") })) : null,
      cmp?.error ? h("p", { class: "notice notice-err", text: cmp.error }) : null);
  })));
}

async function compareVersion(n) {
  const res = await request(`/items/${encodeURIComponent(state.detailId)}/versions/${n}`);
  state.compare[n] = res.ok ? { diff: payloadDiff(res.data.payload, state.detail.current?.payload) } : { error: explain(res).text };
  paintDetail();
}

function approvalsCard(D) {
  const list = D.approvals || [];
  return card(tr("adm_approvals"), list.length ? h("ul", { class: "flex flex-col gap-2" }, list.map((a) =>
    h("li", { class: "flex flex-col gap-1 border-t pt-2" },
      h("p", { class: "font-semibold", text: tr("adm_approved_by", { decision: humanize(a.decision), name: a.approver_name || a.approver_role }) }),
      h("p", { text: `v${a.version} - ${fmtDateTime(a.created_at)}` }),
      a.approver_credential ? kv(tr("adm_credential"), a.approver_credential) : null,
      a.expires_at ? kv(tr("adm_expires"), fmtDateTime(a.expires_at)) : null,
      a.reason ? h("p", { text: a.reason }) : null)))
    : h("p", { text: tr("adm_approvals_none") }));
}

function commentsCard(D) {
  const id = `cmt-${++uid}`;
  const ta = h("textarea", { id, class: "form-input", maxlength: "4000" });
  const list = D.comments || [];
  return card(tr("adm_comments"),
    list.length ? h("ul", { class: "flex flex-col gap-2" }, list.map((c) =>
      h("li", { class: "flex flex-col gap-1 border-t pt-2" },
        h("p", { class: "text-sm font-semibold", text: `${c.author_name || c.author_role || ""} - ${fmtDateTime(c.created_at)}` }),
        h("p", { text: c.body })))) : h("p", { text: tr("adm_comments_none") }),
    h("form", { class: "flex flex-col gap-2", novalidate: true,
      onsubmit: async (e) => {
        e.preventDefault();
        const body = ta.value.trim();
        if (!body) { ta.focus(); return; }
        const res = await request(`/items/${encodeURIComponent(D.item.id)}/comments`, "POST", { body });
        if (res.ok) setNotice("ok", tr("adm_act_done")); else { const ex = explain(res); setNotice("err", ex.text, ex.list); }
        return reloadDetail(true);
      } },
      h("label", { for: id, class: "form-label", text: tr("adm_comment_add") }), ta,
      h("button", { type: "submit", class: "btn btn-secondary self-start", text: tr("adm_comment_post") })));
}

function auditCard(D) {
  const list = D.audit || [];
  return card(tr("adm_audit"),
    list.length ? h("ul", { class: "flex flex-col gap-2" }, list.map((a) =>
      h("li", { class: "flex flex-col gap-1 border-t pt-2" },
        h("p", { class: "font-semibold", text: `${humanize(a.action)} - ${a.actor_name || a.actor_role || ""}` }),
        h("p", { class: "text-sm", text: `${fmtDateTime(a.created_at)}${a.from_status || a.to_status ? ` - ${a.from_status || "-"} -> ${a.to_status || "-"}` : ""}` }),
        a.reason ? h("p", { text: a.reason }) : null,
        diffLines(a.diff)))) : h("p", { text: tr("adm_audit_none") }),
    D.audit_total > list.length ? h("p", { class: "text-sm", text: tr("adm_audit_more", { shown: list.length, total: D.audit_total }) }) : null);
}

// ---------------------------------------------------------------- add / edit / propose form

function emptyDraft() {
  return { id: "", topic: TOPICS[0], subtopic: "", region: "ALL", statement_en: "", statement_hi: "",
    hi_machine_translated: true, hi_reviewed: false, risk_level: "LOW", involves_chemical: false,
    cibrc_check_required: false, source_confidence: "official_guideline", retrieved_on: "", reason: "",
    app: { age_min: "", age_max: "", months: "", bahar: "", irrigation: "", planting: "", varieties: "" },
    values: [], sources: [emptySource()], conflicts: [] };
}
function emptySource() { return { title: "", publisher: "", year: "", url: "", page: "", section: "", quote: "", access: "opened_read" }; }
function emptyValue() { return { name: "", value: "", min: "", max: "", unit: "", per: "" }; }
function emptyConflict() { return { title: "", url: "", quote: "", note: "" }; }

function draftFromPayload(p) {
  const a = p.applicability || {};
  const s = (v) => (v === null || v === undefined ? "" : String(v));
  return { id: p.id, topic: p.topic, subtopic: p.subtopic, region: p.region, statement_en: p.statement_en, statement_hi: p.statement_hi,
    hi_machine_translated: !!p.hi_machine_translated, hi_reviewed: !!p.hi_reviewed, risk_level: p.risk_level,
    involves_chemical: !!p.involves_chemical, cibrc_check_required: !!p.cibrc_check_required,
    source_confidence: p.source_confidence, retrieved_on: s(p.retrieved_on), reason: "",
    app: { age_min: s(a.tree_age_months_min), age_max: s(a.tree_age_months_max), months: (a.months || []).join(", "),
      bahar: s(a.bahar), irrigation: s(a.irrigation_type), planting: s(a.planting_system), varieties: (a.varieties || []).join(", ") },
    values: (p.values || []).map((v) => ({ name: s(v.name), value: s(v.value), min: s(v.min), max: s(v.max), unit: s(v.unit), per: s(v.per) })),
    sources: (p.sources || []).map((x) => ({ title: x.title, publisher: x.publisher, year: s(x.year), url: x.url, page: s(x.page),
      section: x.section_or_table, quote: x.quote, access: x.access })),
    conflicts: (p.conflicts || []).map((c) => ({ title: c.source_title, url: c.url, quote: c.quote, note: c.note })) };
}

function openForm(mode) {
  state.notice = null;
  state.pendingAction = null;
  state.view = "form";
  if (mode === "create") state.form = { mode, itemId: null, rowVersion: null, draft: emptyDraft() };
  else {
    const D = state.detail;
    state.form = { mode, itemId: D.item.id, rowVersion: D.item.row_version, draft: draftFromPayload(D.current.payload) };
  }
  paintForm();
}

function numOrNull(raw, fieldName, errors, integer = false) {
  const t = String(raw).trim();
  if (t === "") return null;
  const n = Number(t);
  if (!Number.isFinite(n) || (integer && !Number.isInteger(n))) { errors.push(tr("adm_v_number", { field: fieldName })); return null; }
  return n;
}

/** Build the API payload from the draft and list every problem (mirrors the server rules). */
function buildPayload(d, mode) {
  const errors = [];
  if (!ID_RE.test(d.id.trim())) errors.push(tr("adm_v_id"));
  if (!d.subtopic.trim()) errors.push(tr("adm_v_required", { field: tr("adm_f_subtopic") }));
  const en = d.statement_en.trim(), hi = d.statement_hi.trim();
  if (en.length < 10 || en.length > 600) errors.push(tr("adm_v_statement_en"));
  if (hi.length < 5 || hi.length > 900) errors.push(tr("adm_v_statement_hi"));
  if (d.involves_chemical && d.risk_level !== "HIGH") errors.push(tr("adm_v_chemical_high"));

  const app = {};
  const amin = numOrNull(d.app.age_min, tr("adm_f_age_min"), errors, true);
  const amax = numOrNull(d.app.age_max, tr("adm_f_age_max"), errors, true);
  if (amin !== null) app.tree_age_months_min = amin;
  if (amax !== null) app.tree_age_months_max = amax;
  if (d.app.months.trim()) {
    const months = d.app.months.split(",").map((x) => Number(x.trim()));
    if (months.some((m) => !Number.isInteger(m) || m < 1 || m > 12) || new Set(months).size !== months.length) errors.push(tr("adm_v_months"));
    else app.months = months;
  }
  if (d.app.bahar) app.bahar = d.app.bahar;
  if (d.app.irrigation.trim()) app.irrigation_type = d.app.irrigation.trim();
  if (d.app.planting.trim()) app.planting_system = d.app.planting.trim();
  const vars = d.app.varieties.split(",").map((x) => x.trim()).filter(Boolean);
  if (vars.length) app.varieties = vars;

  const values = [];
  d.values.forEach((v, i) => {
    const name = v.name.trim();
    const val = String(v.value).trim();
    const min = numOrNull(v.min, tr("adm_f_value_min"), errors);
    const max = numOrNull(v.max, tr("adm_f_value_max"), errors);
    if (!name || (val === "" && min === null && max === null)) { errors.push(tr("adm_v_value_one", { n: i + 1 })); return; }
    const o = { name };
    if (val !== "") o.value = Number.isFinite(Number(val)) ? Number(val) : val;
    if (min !== null) o.min = min;
    if (max !== null) o.max = max;
    if (v.unit.trim()) o.unit = v.unit.trim();
    if (v.per.trim()) o.per = v.per.trim();
    values.push(o);
  });

  const sources = [];
  if (!d.sources.length) errors.push(tr("adm_v_source_needed"));
  d.sources.forEach((s, i) => {
    const n = i + 1;
    if (!s.title.trim() || !s.publisher.trim() || !s.section.trim() || !s.url.trim() || !s.quote.trim()) { errors.push(tr("adm_v_source_fields", { n })); return; }
    if (!isHttpUrl(s.url)) errors.push(tr("adm_v_source_url", { n }));
    if (wordCount(s.quote) > MAX_QUOTE_WORDS || s.quote.trim().length > 200) errors.push(tr("adm_v_quote_words", { where: `${tr("adm_sources")} ${n}` }));
    const year = numOrNull(s.year, tr("adm_f_src_year"), errors, true);
    const o = { title: s.title.trim(), publisher: s.publisher.trim(), url: s.url.trim(), section_or_table: s.section.trim(), quote: s.quote.trim(), access: s.access };
    if (year !== null) o.year = year;
    if (s.page.trim()) o.page = s.page.trim();
    sources.push(o);
  });

  const conflicts = [];
  d.conflicts.forEach((c, i) => {
    if (!c.title.trim() || !c.quote.trim() || !c.note.trim() || !isHttpUrl(c.url)) { errors.push(tr("adm_v_conflict_fields", { n: i + 1 })); return; }
    if (wordCount(c.quote) > MAX_QUOTE_WORDS || c.quote.trim().length > 200) errors.push(tr("adm_v_quote_words", { where: `${tr("adm_conflicts")} ${i + 1}` }));
    conflicts.push({ source_title: c.title.trim(), url: c.url.trim(), quote: c.quote.trim(), note: c.note.trim() });
  });

  const item = { id: d.id.trim(), topic: d.topic, subtopic: d.subtopic.trim(), region: d.region, applicability: app,
    statement_en: en, statement_hi: hi, hi_machine_translated: d.hi_machine_translated, hi_reviewed: d.hi_reviewed,
    values, risk_level: d.risk_level, involves_chemical: d.involves_chemical, cibrc_check_required: d.cibrc_check_required,
    sources, source_confidence: d.source_confidence, conflicts };
  if (d.retrieved_on) item.retrieved_on = d.retrieved_on;
  return { errors, item };
}

function textField(labelText, obj, prop, opts = {}) {
  const id = `fld-${++uid}`;
  const common = { id, class: "form-input", value: obj[prop], oninput: (e) => { obj[prop] = e.target.value; } };
  if (opts.maxlength) common.maxlength = String(opts.maxlength);
  if (opts.readonly) common.readonly = true;
  const input = opts.area ? h("textarea", common) : h("input", { ...common, type: opts.type || "text", inputmode: opts.inputmode || null });
  return h("div", {}, h("label", { for: id, class: "form-label", text: labelText }), input);
}

function selectProp(labelText, obj, prop, options, extra) {
  const id = `fld-${++uid}`;
  const sel = h("select", { id, class: "form-input", onchange: (e) => { obj[prop] = e.target.value; extra?.(e.target.value); } },
    options.map(([v, t]) => h("option", { value: v, selected: v === obj[prop] ? true : null, text: t })));
  return h("div", {}, h("label", { for: id, class: "form-label", text: labelText }), sel);
}

function checkProp(labelText, obj, prop, onchange) {
  const id = `fld-${++uid}`;
  return h("label", { for: id, class: "check-row" },
    h("input", { id, type: "checkbox", checked: obj[prop] ? true : null, onchange: (e) => { obj[prop] = e.target.checked; onchange?.(e.target.checked); } }),
    h("span", { text: labelText }));
}

function listBlock(title, arr, makeRow, addLabel, addFn) {
  return h("fieldset", { class: "section-card flex flex-col gap-3" },
    h("legend", { class: "font-bold text-emerald-900 text-lg px-1", text: title }),
    arr.map((row, i) => h("div", { class: "flex flex-col gap-2 border-b pb-3" }, makeRow(row, i),
      h("button", { type: "button", class: "btn btn-danger self-start", text: tr("adm_f_remove"),
        onclick: () => { arr.splice(i, 1); paintForm(); } }))),
    h("button", { type: "button", class: "btn btn-secondary self-start", text: addLabel, onclick: () => { addFn(); paintForm(); } }));
}

function paintForm() {
  const F = state.form;
  const d = F.draft;
  const mode = F.mode;
  const titleKey = mode === "create" ? "adm_form_add_title" : mode === "edit" ? "adm_form_edit_title" : "adm_form_propose_title";
  const saveKey = mode === "create" ? "adm_f_save_create" : mode === "edit" ? "adm_f_save_edit" : "adm_f_save_propose";
  let riskSelect;
  const risk = selectProp(tr("adm_f_risk"), d, "risk_level", RISKS.map((r) => [r, label("adm_risk_", r)]));
  riskSelect = risk.querySelector("select");
  const chem = checkProp(tr("adm_f_chemical"), d, "involves_chemical", (on) => {
    if (on) { d.risk_level = "HIGH"; riskSelect.value = "HIGH"; }
  });
  const form = h("form", { class: "flex flex-col gap-4", novalidate: true,
    onsubmit: (e) => { e.preventDefault(); submitForm(); } },
    h("p", { class: "status-line", text: tr("adm_form_note") }),
    h("div", { class: "section-card flex flex-col gap-3" },
      textField(tr("adm_f_id"), d, "id", { readonly: mode !== "create", maxlength: 20 }),
      selectProp(tr("adm_f_topic"), d, "topic", TOPICS.map((t) => [t, label("adm_topic_", t)])),
      textField(tr("adm_f_subtopic"), d, "subtopic", { maxlength: 80 }),
      selectProp(tr("adm_f_region"), d, "region", REGIONS.map((t) => [t, label("adm_region_", t)])),
      textField(tr("adm_f_statement_en"), d, "statement_en", { area: true, maxlength: 600 }),
      textField(tr("adm_f_statement_hi"), d, "statement_hi", { area: true, maxlength: 900 }),
      checkProp(tr("adm_f_hi_machine"), d, "hi_machine_translated"),
      checkProp(tr("adm_f_hi_reviewed"), d, "hi_reviewed"),
      risk, chem,
      checkProp(tr("adm_f_cibrc"), d, "cibrc_check_required"),
      selectProp(tr("adm_f_confidence"), d, "source_confidence", CONFIDENCE.map((t) => [t, label("adm_conf_", t)])),
      textField(tr("adm_f_retrieved"), d, "retrieved_on", { type: "date" })),
    h("fieldset", { class: "section-card flex flex-col gap-3" },
      h("legend", { class: "font-bold text-emerald-900 text-lg px-1", text: tr("adm_f_app_title") }),
      textField(tr("adm_f_age_min"), d.app, "age_min", { inputmode: "numeric" }),
      textField(tr("adm_f_age_max"), d.app, "age_max", { inputmode: "numeric" }),
      textField(tr("adm_f_months"), d.app, "months"),
      selectProp(tr("adm_f_bahar"), d.app, "bahar", BAHAR.map((b) => [b, b || "-"])),
      textField(tr("adm_f_irrigation"), d.app, "irrigation", { maxlength: 60 }),
      textField(tr("adm_f_planting"), d.app, "planting", { maxlength: 60 }),
      textField(tr("adm_f_varieties"), d.app, "varieties")),
    listBlock(tr("adm_f_values_title"), d.values, (v) => h("div", { class: "flex flex-col gap-2" },
      textField(tr("adm_f_value_name"), v, "name", { maxlength: 80 }),
      textField(tr("adm_f_value_value"), v, "value", { maxlength: 80 }),
      textField(tr("adm_f_value_min"), v, "min", { inputmode: "decimal" }),
      textField(tr("adm_f_value_max"), v, "max", { inputmode: "decimal" }),
      textField(tr("adm_f_value_unit"), v, "unit", { maxlength: 40 }),
      textField(tr("adm_f_value_per"), v, "per", { maxlength: 80 })), tr("adm_f_add_value"), () => d.values.push(emptyValue())),
    listBlock(tr("adm_f_sources_title"), d.sources, (s) => h("div", { class: "flex flex-col gap-2" },
      textField(tr("adm_f_src_title"), s, "title", { maxlength: 300 }),
      textField(tr("adm_f_src_publisher"), s, "publisher", { maxlength: 200 }),
      textField(tr("adm_f_src_year"), s, "year", { inputmode: "numeric" }),
      textField(tr("adm_f_src_url"), s, "url", { maxlength: 600, type: "url" }),
      textField(tr("adm_f_src_page"), s, "page", { maxlength: 40 }),
      textField(tr("adm_f_src_section"), s, "section", { maxlength: 200 }),
      textField(tr("adm_f_src_quote"), s, "quote", { area: true, maxlength: 200 }),
      selectProp(tr("adm_f_src_access"), s, "access", ACCESS.map((a) => [a, label("adm_access_", a)]))), tr("adm_f_add_source"), () => d.sources.push(emptySource())),
    listBlock(tr("adm_f_conf_title"), d.conflicts, (c) => h("div", { class: "flex flex-col gap-2" },
      textField(tr("adm_f_conf_title_field"), c, "title", { maxlength: 300 }),
      textField(tr("adm_f_conf_url"), c, "url", { maxlength: 600, type: "url" }),
      textField(tr("adm_f_conf_quote"), c, "quote", { area: true, maxlength: 200 }),
      textField(tr("adm_f_conf_note"), c, "note", { maxlength: 400 })), tr("adm_f_add_conflict"), () => d.conflicts.push(emptyConflict())),
    mode !== "create" ? h("div", { class: "section-card" }, textField(tr("adm_f_reason"), d, "reason", { area: true, maxlength: 1000 })) : null,
    h("div", { id: "form-errors" }),
    h("div", { class: "flex flex-wrap gap-2" },
      h("button", { type: "submit", class: "btn btn-primary", text: tr(saveKey) }),
      h("button", { type: "button", class: "btn btn-secondary", text: tr("adm_act_cancel"),
        onclick: () => (mode === "create" ? go("items") : (state.view = "detail", paintDetail())) })));
  render(h("div", { class: "flex flex-col gap-4" }, h("h2", { class: "font-bold text-emerald-900 text-lg", text: tr(titleKey) }), form));
}

async function submitForm() {
  const F = state.form;
  const { errors, item } = buildPayload(F.draft, F.mode);
  const box = $("form-errors");
  if (errors.length) {
    box.replaceChildren(h("div", { class: "notice notice-err", role: "alert" },
      h("p", { text: tr("adm_error_validation") }), h("ul", { class: "list-disc pl-5" }, errors.map((t) => h("li", { text: t })))));
    box.scrollIntoView({ block: "center" });
    return;
  }
  const reason = F.draft.reason.trim();
  let res;
  if (F.mode === "create") res = await request("/items", "POST", { item });
  else if (F.mode === "edit") res = await request(`/items/${encodeURIComponent(F.itemId)}`, "PUT", { item, expected_row_version: F.rowVersion, ...(reason ? { reason } : {}) });
  else res = await request(`/items/${encodeURIComponent(F.itemId)}/proposals`, "POST", { item, ...(reason ? { reason } : {}) });
  if (!res.ok) {
    const ex = explain(res);
    box.replaceChildren(h("div", { class: "notice notice-err", role: "alert" },
      h("p", { text: ex.text }), ex.list ? h("ul", { class: "list-disc pl-5" }, ex.list.map((t) => h("li", { text: t }))) : null));
    if (res.status === 409 && F.mode === "edit") { /* keep the draft; the admin can reload the item from the list */ }
    return;
  }
  setNotice("ok", tr("adm_f_saved"));
  await openDetailKeepNotice(F.mode === "create" ? item.id : F.itemId);
}

async function openDetailKeepNotice(id) {
  const keep = state.notice;
  state.view = "detail";
  state.detailId = id;
  state.compare = {};
  state.notice = keep;
  await reloadDetail(true);
}

// ---------------------------------------------------------------- reviewers

async function loadReviewers() {
  state.view = "reviewers";
  render(loadingBody());
  const res = await request("/reviewers");
  if (!res.ok) { render(retryBody(loadReviewers)); return; }
  state.reviewers = res.data;
  paintReviewers();
}

async function toggleMember(m) {
  const res = await request(`/reviewers/${encodeURIComponent(m.user_id)}/${m.active ? "deactivate" : "reactivate"}`, "POST");
  if (res.ok) setNotice("ok", tr("adm_act_done")); else { const ex = explain(res); setNotice("err", ex.text, ex.list); }
  const keep = state.notice;
  await loadReviewers();
  state.notice = keep;
  paintReviewers();
}

function paintReviewers() {
  const R = state.reviewers;
  const draft = { email: "", display_name: "", credential: "" };
  const members = R.members || [];
  const invites = R.invites || [];
  const form = h("form", { class: "section-card flex flex-col gap-3", novalidate: true,
    onsubmit: async (e) => {
      e.preventDefault();
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(draft.email.trim()) || !draft.display_name.trim()) {
        setNotice("err", tr("adm_error_validation"), [tr("adm_v_required", { field: `${tr("adm_rev_email")}, ${tr("adm_rev_name")}` })]);
        return paintReviewers();
      }
      const body = { email: draft.email.trim(), display_name: draft.display_name.trim() };
      if (draft.credential.trim()) body.credential = draft.credential.trim();
      const res = await request("/reviewers", "POST", body);
      if (res.ok) setNotice("ok", tr(res.data?.result === "invited" ? "adm_rev_invited" : res.data?.result === "updated" ? "adm_rev_updated" : "adm_rev_added"));
      else { const ex = explain(res); setNotice("err", ex.text, ex.list); return paintReviewers(); }
      const keep = state.notice;
      await loadReviewers();
      state.notice = keep;
      paintReviewers();
    } },
    h("h2", { class: "font-bold text-emerald-900 text-lg", text: tr("adm_rev_add") }),
    textField(tr("adm_rev_email"), draft, "email", { type: "email", maxlength: 254 }),
    textField(tr("adm_rev_name"), draft, "display_name", { maxlength: 120 }),
    textField(tr("adm_rev_credential"), draft, "credential", { maxlength: 300 }),
    h("button", { type: "submit", class: "btn btn-primary self-start", text: tr("adm_rev_save") }));
  render(h("div", { class: "flex flex-col gap-4" },
    h("h2", { class: "font-bold text-emerald-900 text-lg", text: tr("adm_rev_title") }),
    h("p", { class: "status-line", text: tr("adm_rev_intro") }),
    h("section", { class: "section-card flex flex-col gap-3" },
      h("h3", { class: "font-bold", text: tr("adm_rev_members") }),
      members.length ? h("ul", { class: "flex flex-col gap-3" }, members.map((m) =>
        h("li", { class: "flex flex-col gap-1 border-t pt-2" },
          h("p", { class: "font-semibold", text: `${m.display_name || m.email}${m.user_id === state.me.user_id ? " " + tr("adm_rev_you") : ""}` }),
          h("p", { text: m.email }),
          h("div", { class: "flex flex-wrap gap-2" }, chip(tr(`adm_role_${m.role}`)), chip(tr(m.active ? "adm_rev_active" : "adm_rev_inactive"), m.active ? "chip-APPROVED" : "chip-RETIRED")),
          m.credential ? kv(tr("adm_credential"), m.credential) : (m.role === "reviewer" ? h("p", { class: "text-sm", text: tr("adm_rev_no_credential") }) : null),
          m.user_id !== state.me.user_id ? h("button", { type: "button", class: `btn ${m.active ? "btn-danger" : "btn-secondary"} self-start`,
            text: tr(m.active ? "adm_rev_deactivate" : "adm_rev_reactivate"), onclick: () => toggleMember(m) }) : null)))
        : h("p", { text: tr("adm_rev_none") })),
    h("section", { class: "section-card flex flex-col gap-3" },
      h("h3", { class: "font-bold", text: tr("adm_rev_invites") }),
      invites.length ? h("ul", { class: "flex flex-col gap-2" }, invites.map((i) =>
        h("li", { class: "flex flex-col gap-1 border-t pt-2" },
          h("p", { class: "font-semibold", text: i.display_name || i.email }), h("p", { text: i.email }),
          kv(tr("adm_rev_expires"), fmtDateTime(i.expires_at))))) : h("p", { text: tr("adm_rev_invites_none") })),
    form));
}

// ---------------------------------------------------------------- boot

function renderDenied() {
  state.me = null;
  const app = root();
  app.replaceChildren(header(), h("section", { class: "section-card flex flex-col gap-3", role: "alert" },
    h("h2", { class: "font-bold text-lg", text: tr("adm_denied_title") }),
    h("p", { text: tr("adm_denied_body") }),
    h("a", { class: "btn btn-secondary self-start", href: "index.html", text: tr("adm_home") })));
  state.denied = true;
}

function renderBootError() {
  const app = root();
  app.replaceChildren(header(), retryBody(boot));
}

async function boot() {
  const res = await request("/me");
  if (res.status === 403) { renderDenied(); return; }
  if (!res.ok) { renderBootError(); return; }
  state.me = res.data;
  await loadDashboard();
}

async function start() {
  installAdminTranslations();
  initTranslator();
  document.title = tr("adm_page_title");
  const [auth, api] = await Promise.all([import("./auth.js"), import("./api.js")]);
  apiMod = api;
  const session = await auth.getSession();
  if (!session) { window.location.href = "login.html"; return; }
  await boot();
}

start();
