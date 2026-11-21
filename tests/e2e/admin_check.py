"""Browser check for admin.html (Knowledge admin) against a mocked Supabase session and mocked
/api/admin/knowledge routes. No real network, no real data: every item below is made-up TEST DATA.

python tests/e2e/admin_check.py [--roles admin,reviewer,nonadmin,anon] [--viewports 360x800,1366x768] [--langs en,hi]

Matrix: roles x viewports x languages. Per case it checks
  - 0 console errors / page errors (a 403 "Failed to load resource" line is expected for the non-admin role only)
  - no horizontal overflow, every visible tap target >= 43.5 px, no raw translation keys on screen
  - admin: all tabs, edit/retire present, "Propose edit" absent; reviewer: no add/reviewers tabs, no edit/retire,
    "Propose edit" present; HIGH approval shows the name-and-credential note; admin approve is disabled with the reason
  - non-admin: access-denied card, and the only /api/admin/knowledge request is GET /me (asserted)
  - anonymous: redirected to login.html and no /api/admin/knowledge request at all
  - admin.html source holds no item data and no other page links to it
Extra flows (admin, 1366x768, en): add form validation blocks an empty submit, a valid item is POSTed with a source,
CSV download uses a bearer request; (reviewer, 360x800, en): approve sends expected_row_version.
Writes report.md, results.json and screenshots under .agents/tasks/guava-knowledge-admin/admin-browser/.
Exit code 1 if any check fails.
"""
import argparse
import json
import mimetypes
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
import mock_api  # noqa: E402

mimetypes.add_type("image/webp", ".webp")
ROOT = Path(__file__).resolve().parents[2]
ART = Path("D:/Python World/Experiment/Guava/.agents/tasks/guava-knowledge-admin/admin-browser")
ORIGIN = "https://guavaa.netlify.app"
API = "https://guava-8wc7.onrender.com"
PREFIX = "/api/admin/knowledge"
ANDROID_UA = ("Mozilla/5.0 (Linux; Android 12; Pixel 5) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36")
VIEWPORTS = {"360x800": dict(width=360, height=800, mobile=True), "1366x768": dict(width=1366, height=768, mobile=False)}
CORS = {"access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*"}


# ---------------------------------------------------------------- strings from js/admin-i18n.js

def load_strings():
    text = (ROOT / "js" / "admin-i18n.js").read_text(encoding="utf-8")
    out = {"en": {}, "hi": {}}
    cur = None
    for line in text.splitlines():
        if line.startswith("export const ADMIN_EN"):
            cur = "en"
        elif line.startswith("export const ADMIN_HI"):
            cur = "hi"
        m = re.match(r'\s*"(adm_[a-z0-9_]+)":\s*"(.*)",?\s*$', line)
        if m and cur:
            out[cur][m.group(1)] = json.loads('"' + m.group(2) + '"')
    return out


STR = load_strings()


# ---------------------------------------------------------------- mocked admin API (TEST DATA)

def item_row(i, **kw):
    row = {"id": f"GUA-TST-{i:04d}", "current_version": 2, "status": "IN_REVIEW", "risk_level": "HIGH", "topic": "pests",
           "subtopic": "test_subtopic", "summary": f"Test item {i}: a made-up statement used only by the browser check.",
           "region": "MP", "has_conflict": i == 1, "approved_at": None, "expires_at": None, "retired_reason": None,
           "row_version": 3, "created_by": "seed-import", "created_at": "2026-11-20T10:00:00Z", "updated_at": "2026-11-21T10:00:00Z"}
    row.update(kw)
    return row


def payload(item_id="GUA-TST-0001"):
    return {"id": item_id, "topic": "pests", "subtopic": "test_subtopic", "region": "MP",
            "applicability": {"tree_age_months_min": 12, "months": [6, 7], "bahar": "mrig", "varieties": ["Test variety"]},
            "statement_en": "This is a made-up test statement about a pest, with a_very_long_unbroken_token_" + "x" * 90 + " to check wrapping.",
            "statement_hi": "यह एक काल्पनिक परीक्षण कथन है।", "hi_machine_translated": True, "hi_reviewed": False,
            "values": [{"name": "dose", "min": 1.0, "max": 2.5, "unit": "g", "per": "litre"}],
            "risk_level": "HIGH", "involves_chemical": True, "cibrc_check_required": True,
            "sources": [{"title": "Test bulletin " + "y" * 70, "publisher": "Test Institute", "year": 2020,
                         "url": "https://example.com/test.pdf", "page": "4", "section_or_table": "Table 2",
                         "quote": "made-up quote of a few words", "access": "opened_read"}],
            "source_confidence": "official_guideline",
            "conflicts": [{"source_title": "Other test bulletin", "url": "https://example.com/other", "quote": "another quote", "note": "differs"}],
            "retrieved_on": "2026-11-21"}


def detail(role):
    admin = role == "admin"
    p = payload()
    proposal = dict(payload(), statement_en="A proposed new made-up statement for the test item.")
    return {
        "item": item_row(1),
        "current": {"item_id": "GUA-TST-0001", "version": 2, "is_proposal": False, "payload": p, "content_hash": "h2",
                    "created_by": "u9", "created_at": "2026-11-21T10:00:00Z", "change_reason": "test"},
        "versions": [{"version": 2, "is_proposal": False, "content_hash": "h2", "created_by": "u9", "created_at": "2026-11-21T10:00:00Z", "change_reason": "test edit"},
                     {"version": 1, "is_proposal": False, "content_hash": "h1", "created_by": "seed-import", "created_at": "2026-11-20T10:00:00Z", "change_reason": "seed"}],
        "pending_proposals": [{"item_id": "GUA-TST-0001", "version": 3, "is_proposal": True, "payload": proposal, "created_by": "u7",
                               "created_at": "2026-11-22T10:00:00Z", "change_reason": "clearer"}] if admin else [],
        "approvals": [{"id": 1, "item_id": "GUA-TST-0001", "version": 1, "decision": "request_changes", "approver_id": "u8",
                       "approver_role": "reviewer", "approver_name": "Test Expert", "approver_credential": "Test scientist, Test Institute",
                       "reason": "needs a table reference", "expires_at": None, "created_at": "2026-11-21T09:00:00Z"}],
        "comments": [{"id": 1, "item_id": "GUA-TST-0001", "version": None, "author_id": "u8", "author_role": "reviewer",
                      "author_name": "Test Expert", "body": "A made-up comment.", "created_at": "2026-11-21T09:30:00Z"}],
        "audit": [{"id": 5, "actor_id": "u9", "actor_role": "admin", "actor_name": "Owner Test", "action": "edit", "item_id": "GUA-TST-0001",
                   "from_status": "DRAFT", "to_status": "IN_REVIEW", "before": {}, "after": {}, "diff": {"statement_en": {"before": "old", "after": "new"}},
                   "reason": "test edit", "created_at": "2026-11-21T10:00:00Z"}],
        "audit_total": 1,
        "allowed_actions": ["edit", "approve", "reject", "request_changes", "retire"] if admin else ["approve", "reject", "request_changes"],
        "approve_blocked_reason": "an admin cannot approve a high-risk item alone" if admin else None,
    }


def dashboard():
    return {"total": 2, "by_status": {"DRAFT": 0, "IN_REVIEW": 2, "CHANGES_REQUESTED": 0, "APPROVED": 0, "REJECTED": 0, "RETIRED": 0},
            "by_risk": {"LOW": 0, "MEDIUM": 0, "HIGH": 2}, "by_topic": {"pests": 2}, "by_region": {"MP": 2},
            "high_risk_in_review": 2, "with_conflict": 1, "expiring_soon": [{"id": "GUA-TST-0002", "expires_at": "2027-01-01T00:00:00Z"}],
            "expired_just_now": []}


def admin_respond(path, method, body, role, log):
    """(status, json or text, content_type) for /api/admin/knowledge/*."""
    sub = path.split(PREFIX, 1)[1].split("?")[0]
    if sub == "/me":
        if role == "nonadmin":
            return 403, {"detail": "Forbidden"}, "application/json"
        return 200, {"user_id": "u1", "role": role, "email": "t@example.com",
                     "display_name": "Owner Test" if role == "admin" else "Test Expert",
                     "credential": None if role == "admin" else "Test scientist"}, "application/json"
    if sub == "/dashboard":
        return 200, dashboard(), "application/json"
    if sub == "/items" and method == "GET":
        return 200, {"items": [item_row(1), item_row(2, has_conflict=False)], "total": 2, "page": 1, "page_size": 25}, "application/json"
    if sub == "/items" and method == "POST":
        log.append(("create", json.loads(body or "{}")))
        return 201, {"item": item_row(1)}, "application/json"
    if re.fullmatch(r"/items/GUA-[A-Z]+-\d+", sub) and method == "GET":
        return 200, detail(role), "application/json"
    m = re.fullmatch(r"/items/GUA-[A-Z]+-\d+/versions/(\d+)", sub)
    if m:
        old = payload()
        old["statement_en"] = "The older made-up statement."
        return 200, {"item_id": "GUA-TST-0001", "version": int(m.group(1)), "is_proposal": False, "payload": old,
                     "content_hash": "h1", "created_by": "seed-import", "created_at": "2026-11-20T10:00:00Z", "change_reason": "seed"}, "application/json"
    if re.search(r"/items/GUA-[A-Z]+-\d+/(approve|reject|request-changes|submit|retire|restore)$", sub) and method == "POST":
        log.append((sub.rsplit("/", 1)[1], json.loads(body or "{}")))
        return 200, {"item": item_row(1, status="APPROVED")}, "application/json"
    if sub == "/export.csv":
        log.append(("export_csv", None))
        return 200, "id,topic\nGUA-TST-0001,pests\n", "text/csv"
    if sub == "/reviewers" and method == "GET":
        return 200, {"members": [
            {"user_id": "u1", "email": "t@example.com", "role": "admin", "display_name": "Owner Test", "credential": None, "added_by": None, "added_at": "2026-11-20T10:00:00Z", "active": True},
            {"user_id": "u8", "email": "expert@example.com", "role": "reviewer", "display_name": "Test Expert", "credential": None, "added_by": "u1", "added_at": "2026-11-21T10:00:00Z", "active": True}],
            "invites": [{"id": 1, "email": "later@example.com", "role": "reviewer", "display_name": "Later Expert", "credential": None,
                         "invited_by": "u1", "created_at": "2026-11-21T10:00:00Z", "expires_at": "2026-12-05T10:00:00Z"}]}, "application/json"
    return 404, {"detail": "Not found"}, "application/json"


# ---------------------------------------------------------------- page measurements

MEASURE = """() => {
  const vis = (e) => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const sel = (e) => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + ((e.textContent || '').trim().slice(0, 24) ? ' "' + (e.textContent || '').trim().slice(0, 24) + '"' : '');
  const out = { overflow: document.documentElement.scrollWidth - innerWidth, small_tap: [], raw_keys: [] };
  document.querySelectorAll('a,button,input,select,textarea').forEach((e) => {
    if (!vis(e) || e.type === 'hidden' || e.classList.contains('sr-only')) return;
    let r = e.getBoundingClientRect();
    if ((e.type === 'checkbox' || e.type === 'radio') && e.closest('label')) r = e.closest('label').getBoundingClientRect();
    if (r.width < 43.5 || r.height < 43.5) out.small_tap.push(sel(e) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
  });
  const t = document.body.innerText || '';
  (t.match(/\\badm_[a-z0-9_]+/g) || []).forEach((k) => out.raw_keys.push(k));
  out.text = t;
  return out;
}"""


class Case:
    def __init__(self, name):
        self.name = name
        self.fails = []
        self.notes = []

    def check(self, ok, msg):
        if not ok:
            self.fails.append(msg)

    def measure(self, page, state):
        m = page.evaluate(MEASURE)
        self.check(m["overflow"] <= 0, f"[{state}] horizontal overflow {m['overflow']}px")
        self.check(not m["small_tap"], f"[{state}] tap targets under 44px: {m['small_tap'][:6]}")
        self.check(not m["raw_keys"], f"[{state}] raw translation keys on screen: {sorted(set(m['raw_keys']))[:5]}")
        self.check(not re.search(r"\b(NaN|undefined|null)\b|\[object Object\]", m["text"]), f"[{state}] NaN/undefined/null text on screen")
        return m


def install_routes(ctx, role, anon, admin_log, reqs, lang):
    def site(route):
        url = route.request.url.split("?")[0].split("#")[0]
        rel = url[len(ORIGIN):].lstrip("/") or "index.html"
        f = ROOT / rel
        if f.is_dir() or not f.exists():
            f = ROOT / (rel + ".html") if (ROOT / (rel + ".html")).exists() else None
        if not f:
            return route.fulfill(status=404, body="not found")
        route.fulfill(status=200, body=f.read_bytes(), content_type=mimetypes.guess_type(str(f))[0] or "text/plain")

    def other(route):
        u = route.request.url
        if u.startswith(ORIGIN) or u.startswith(API) or u.startswith("data:"):
            return route.fallback()
        route.abort()
    ctx.route("**/*", other)
    ctx.route(ORIGIN + "/**", site)
    ctx.route("**/@supabase/supabase-js@2/+esm", lambda r: r.fulfill(
        status=200, content_type="application/javascript", body=mock_api.supabase_stub(anon)))

    def api(route):
        p = route.request.url[len(API):]
        method = route.request.method
        if method == "OPTIONS":
            return route.fulfill(status=204, headers=CORS)
        if PREFIX in p:
            reqs.append((method, p.split("?")[0].split(PREFIX, 1)[1] or "/", route.request.headers.get("authorization", "")))
            status, data, ctype = admin_respond(p, method, route.request.post_data or "", role, admin_log)
            body = data if isinstance(data, str) else json.dumps(data)
            return route.fulfill(status=status, content_type=ctype, body=body, headers=CORS)
        route.fulfill(status=200, content_type="application/json", body="{}", headers=CORS)
    ctx.route(API + "/**", api)
    ctx.route("**/npm/chart.js", lambda r: r.fulfill(status=200, content_type="application/javascript", body=mock_api.CHART_STUB))


def btn(page, key, lang, **kw):
    return page.get_by_role("button", name=STR[lang][key], exact=True, **kw)


def snap(page, case, vp, lang, role, state):
    ART.joinpath("screens").mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(ART / "screens" / f"{role}_{vp}_{lang}_{state}.png"), full_page=True)
    return case.measure(page, state)


def run_case(browser, role, vp, lang, extra):
    case = Case(f"{role} {vp} {lang}")
    cfg = VIEWPORTS[vp]
    kw = dict(viewport={"width": cfg["width"], "height": cfg["height"]}, service_workers="block", accept_downloads=True)
    if cfg["mobile"]:
        kw.update(is_mobile=True, has_touch=True, device_scale_factor=2, user_agent=ANDROID_UA)
    ctx = browser.new_context(**kw)
    ctx.add_init_script(f"try{{localStorage.setItem('sf_lang','{lang}')}}catch(e){{}}")
    anon = role == "anon"
    if anon:
        ctx.add_init_script("localStorage.setItem('sf_test_anon','1')")
    admin_log, reqs, errs = [], [], []
    install_routes(ctx, role, anon, admin_log, reqs, lang)
    page = ctx.new_page()
    page.on("console", lambda m: errs.append(f"console.{m.type}: {m.text[:200]}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: errs.append("pageerror: " + str(e)[:200]))
    S = STR[lang]
    try:
        page.goto(f"{ORIGIN}/admin.html", wait_until="load")
        if anon:
            page.wait_for_url("**/login.html", timeout=8000)
            case.check(not reqs, f"anonymous visitor made admin requests: {reqs}")
        elif role == "nonadmin":
            page.get_by_text(S["adm_denied_title"], exact=True).wait_for(timeout=8000)
            page.wait_for_timeout(800)
            snap(page, case, vp, lang, role, "denied")
            paths = [(m, p) for m, p, _ in reqs]
            case.check(paths == [("GET", "/me")], f"non-admin made requests other than GET /me: {paths}")
            case.check(page.locator(".banner").count() == 0 and page.locator("nav").count() == 0, "non-admin sees admin chrome")
            case.check(not re.search(r"GUA-", page.inner_text("body")), "non-admin page shows item data")
            errs = [e for e in errs if "status of 403" not in e]  # the expected 403 on /me
        else:
            run_member(page, case, role, vp, lang, S, extra, reqs, admin_log)
            case.check(all(a.startswith("Bearer ") for _, _, a in reqs), "a request had no bearer token")
    except Exception as e:  # noqa: BLE001
        case.fails.append(f"exception: {type(e).__name__}: {str(e)[:300]}")
        try:
            page.screenshot(path=str(ART / "screens" / f"{role}_{vp}_{lang}_FAILED.png"))
        except Exception:  # noqa: BLE001
            pass
    errs = [e for e in errs if "Service Worker registration blocked" not in e]  # harness blocks workers (login.html registers one)
    case.check(not errs, f"console errors: {errs[:5]}")
    ctx.close()
    return case


def run_member(page, case, role, vp, lang, S, extra, reqs, admin_log):
    admin = role == "admin"
    page.locator(".banner").wait_for(timeout=8000)
    page.get_by_text(S["adm_dash_total"], exact=True).wait_for(timeout=8000)
    case.check(page.get_by_text(S["adm_banner"], exact=True).is_visible(), "banner 'Nothing here reaches farmers until approved' missing")
    snap(page, case, vp, lang, role, "dashboard")
    tabs = {k: btn(page, k, lang).count() for k in ("adm_tab_dashboard", "adm_tab_items", "adm_tab_add", "adm_tab_reviewers")}
    case.check(tabs["adm_tab_dashboard"] == 1 and tabs["adm_tab_items"] == 1, "dashboard/items tabs missing")
    case.check((tabs["adm_tab_add"] == 1 and tabs["adm_tab_reviewers"] == 1) == admin and (tabs["adm_tab_add"] == tabs["adm_tab_reviewers"] == 0) == (not admin),
               f"role tabs wrong for {role}: {tabs}")
    case.check((btn(page, "adm_import_seed", lang).count() == 1) == admin, "import button visibility wrong for role")

    # list
    btn(page, "adm_tab_items", lang).click()
    page.locator("ul li button").first.wait_for(timeout=8000)
    snap(page, case, vp, lang, role, "list")
    # detail
    page.locator("ul li button").first.click()
    page.get_by_role("heading", name="GUA-TST-0001", exact=True).wait_for(timeout=8000)
    snap(page, case, vp, lang, role, "detail")
    has = lambda k: btn(page, k, lang).count() == 1  # noqa: E731
    case.check(has("adm_act_edit") == admin, f"Edit button wrong for {role}")
    case.check(has("adm_act_retire") == admin, f"Retire button wrong for {role}")
    case.check(has("adm_act_propose") == (not admin), f"Propose edit button wrong for {role}")
    case.check(has("adm_act_approve") and has("adm_act_reject") and has("adm_act_request_changes"), "approve/reject/request changes missing")
    approve = btn(page, "adm_act_approve", lang)
    case.check(approve.is_disabled() == admin, "admin must have a disabled Approve on a HIGH item (reviewer must have an enabled one)")
    if admin:
        case.check(page.get_by_text(S["adm_approve_blocked"].replace("{reason}", "an admin cannot approve a high-risk item alone"), exact=True).count() == 1, "blocked-approval reason not shown")
        case.check(btn(page, "adm_proposal_accept", lang).count() == 1, "pending proposal accept missing for admin")
    else:
        case.check(btn(page, "adm_proposal_accept", lang).count() == 0, "reviewer sees accept proposal")
    # the link to the source opens safely
    link = page.locator("a.src-link").first
    case.check(link.get_attribute("rel") == "noopener noreferrer" and link.get_attribute("target") == "_blank", "source link lacks rel=noopener noreferrer")
    # Hindi item text carries the machine-translated tag
    case.check(page.get_by_text(S["adm_hi_tag"], exact=True).count() >= 1, "machine translated tag missing")
    # version compare
    btn(page, "adm_version_compare", lang).first.click()
    page.get_by_text(S["adm_diff_before"], exact=False).first.wait_for(timeout=5000)
    snap(page, case, vp, lang, role, "detail_compare")

    # action panel: reject needs a reason, nothing is sent without one
    before = len(admin_log)
    btn(page, "adm_act_reject", lang).click()
    btn(page, "adm_act_confirm", lang).click()
    page.get_by_text(S["adm_act_reason_required"], exact=True).wait_for(timeout=3000)
    case.check(len(admin_log) == before, "reject without a reason was sent")
    btn(page, "adm_act_cancel", lang).click()

    if extra and role == "reviewer" and vp == "360x800" and lang == "en":
        btn(page, "adm_act_approve", lang).click()
        case.check(page.get_by_text(S["adm_high_note"], exact=True).count() == 1, "HIGH approval note (name and credential) missing")
        snap(page, case, vp, lang, role, "approve_panel")
        btn(page, "adm_act_confirm", lang).click()
        page.wait_for_timeout(600)
        sent = [b for k, b in admin_log if k == "approve"]
        case.check(len(sent) == 1 and sent[0].get("expected_row_version") == 3, f"approve body wrong: {sent}")

    # form
    if admin:
        btn(page, "adm_act_edit", lang).click()
    else:
        btn(page, "adm_act_propose", lang).click()
    page.get_by_label(S["adm_f_statement_en"], exact=True).wait_for(timeout=5000)
    case.check(page.get_by_label(S["adm_f_id"], exact=True).get_attribute("readonly") is not None, "id must be read-only when editing")
    snap(page, case, vp, lang, role, "form_edit")

    if admin:
        btn(page, "adm_tab_reviewers", lang).click()
        page.get_by_text(S["adm_rev_intro"], exact=True).wait_for(timeout=5000)
        snap(page, case, vp, lang, role, "reviewers")
        case.check(btn(page, "adm_rev_deactivate", lang).count() == 1, "exactly one deactivate button expected (not for yourself)")
        if extra and vp == "1366x768" and lang == "en":
            admin_extra(page, case, vp, lang, role, S, admin_log)


def admin_extra(page, case, vp, lang, role, S, admin_log):
    btn(page, "adm_tab_add", lang).click()
    page.get_by_label(S["adm_f_id"], exact=True).wait_for(timeout=5000)
    snap(page, case, vp, lang, role, "form_add")
    before = len(admin_log)
    btn(page, "adm_f_save_create", lang).click()
    page.get_by_text(S["adm_error_validation"], exact=True).wait_for(timeout=3000)
    case.check(len(admin_log) == before, "an empty add form was sent")
    snap(page, case, vp, lang, role, "form_add_errors")
    page.get_by_label(S["adm_f_id"], exact=True).fill("GUA-TST-0001")
    page.get_by_label(S["adm_f_subtopic"], exact=True).fill("test_subtopic")
    page.get_by_label(S["adm_f_statement_en"], exact=True).fill("A made-up English statement for the browser check.")
    page.get_by_label(S["adm_f_statement_hi"], exact=True).fill("परीक्षण के लिए एक काल्पनिक कथन।")
    page.get_by_label(S["adm_f_src_title"], exact=True).fill("Test bulletin")
    page.get_by_label(S["adm_f_src_publisher"], exact=True).fill("Test Institute")
    page.get_by_label(S["adm_f_src_url"], exact=True).fill("https://example.com/test.pdf")
    page.get_by_label(S["adm_f_src_section"], exact=True).fill("Table 2")
    page.get_by_label(S["adm_f_src_quote"], exact=True).fill("a short made-up quote")
    page.get_by_label(S["adm_f_chemical"], exact=True).check()
    case.check(page.get_by_label(S["adm_f_risk"], exact=True).input_value() == "HIGH", "chemical must force HIGH risk in the form")
    btn(page, "adm_f_save_create", lang).click()
    page.get_by_role("heading", name="GUA-TST-0001", exact=True).wait_for(timeout=8000)
    sent = [b for k, b in admin_log if k == "create"]
    case.check(len(sent) == 1 and len(sent[0]["item"]["sources"]) == 1 and sent[0]["item"]["sources"][0]["url"].startswith("https://")
               and sent[0]["item"]["risk_level"] == "HIGH", f"create body wrong: {sent}")
    # CSV export fetches with a bearer token and starts a download
    btn(page, "adm_tab_dashboard", lang).click()
    page.get_by_text(S["adm_dash_total"], exact=True).wait_for(timeout=5000)
    with page.expect_download(timeout=8000) as dl:
        btn(page, "adm_export_csv", lang).click()
    case.check(dl.value.suggested_filename == "guava-knowledge.csv", "CSV download file name wrong")
    case.check(any(k == "export_csv" for k, _ in admin_log), "CSV export request not seen")


# ---------------------------------------------------------------- static checks

def static_checks():
    fails = []
    src = (ROOT / "admin.html").read_text(encoding="utf-8")
    if "GUA-" in src:
        fails.append("admin.html source contains item data")
    if 'name="robots" content="noindex' not in src:
        fails.append("admin.html lacks the noindex meta tag")
    body = src.split("<body", 1)[1]
    if body.count("<p ") != 1 or "Checking access" not in body:
        fails.append("admin.html body must hold only the 'Checking access...' status")
    for f in list(ROOT.glob("*.html")) + list((ROOT / "js").glob("*.js")) + [ROOT / "sw.js", ROOT / "netlify.toml"]:
        if f.name in ("admin.html", "admin.js", "admin-i18n.js") or not f.exists():
            continue
        if "admin.html" in f.read_text(encoding="utf-8", errors="ignore"):
            fails.append(f"{f.name} links to admin.html")
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roles", default="admin,reviewer,nonadmin,anon")
    ap.add_argument("--viewports", default="360x800,1366x768")
    ap.add_argument("--langs", default="en,hi")
    args = ap.parse_args()
    ART.mkdir(parents=True, exist_ok=True)
    results = []
    static = static_checks()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for role in args.roles.split(","):
            for vp in args.viewports.split(","):
                for lang in args.langs.split(","):
                    case = run_case(browser, role, vp, lang, extra=True)
                    results.append(case)
                    print(("FAIL " if case.fails else "ok   ") + case.name, *case.fails[:3], sep="\n     " if case.fails else "")
        browser.close()
    lines = ["# Knowledge admin browser check", "", f"Cases: {len(results)}; failed: {sum(1 for c in results if c.fails)}", "",
             "| Case | Result |", "|---|---|"]
    for c in results:
        lines.append(f"| {c.name} | {'FAIL: ' + '; '.join(c.fails) if c.fails else 'ok'} |")
    lines += ["", "## Static checks", "", *(f"- FAIL {s}" for s in static)] if static else ["", "## Static checks", "", "- ok (noindex, shell only, not linked from any page)"]
    (ART / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (ART / "results.json").write_text(json.dumps([{"case": c.name, "fails": c.fails} for c in results] + [{"case": "static", "fails": static}], indent=1), encoding="utf-8")
    bad = [c for c in results if c.fails]
    for s in static:
        print("FAIL static:", s)
    print(f"{len(results) - len(bad)}/{len(results)} cases ok; static {'FAIL' if static else 'ok'}; report: {ART / 'report.md'}")
    return 1 if (bad or static) else 0


if __name__ == "__main__":
    sys.exit(main())
