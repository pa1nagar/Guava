"""Browser check: every page x viewport x language against mocked Supabase + API.

python tests/e2e/browser_check.py [--pages a,b] [--viewport 360x800] [--lang en] [--scenario all|ok|empty|error]
                                  [--local] [--anon] [--real-cdn] [--report path]
Writes screenshots + results.json + a markdown report under .agents/tasks/visual-redesign/ (not committed).
Default --scenario all runs ok, empty and error.
Exit code 1 if any hard check fails.

For the signed-in app pages (farm, plan, tasks, observations, inventory, report) the check also opens every
form, modal and tab panel and measures again, runs the AI chat on plan.html, and checks:
  - no "NaN" / "undefined" / "null" in the visible text
  - the Estimate label on disease alerts, GDD, fertilizer forecast and irrigation advisory (ok scenario)
  - no chemical name or dose in the disease alerts / irrigation advisory text
  - empty scenario: an empty-state message is visible; error scenario: a Retry button (or error panel) is visible
Quality gates on every page and state: every <img> loads (scrolled into view first), has width and height attributes
and a same-origin src; first-load image bytes on index at 360x800 stay under 150 KB; every .sf-chart canvas is drawn or its
.sf-chart-summary is visible with text; in Hindi, runs of 3+ plain English words in <main> are listed as a soft warning.
"""
import argparse
import http.server
import json
import mimetypes
import re
import shutil
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
import mock_api  # noqa: E402

mimetypes.add_type("image/webp", ".webp")  # missing from Windows' registry-based type table
ROOT = Path(__file__).resolve().parents[2]
ART = Path("D:/Python World/Experiment/Guava/.agents/tasks/visual-redesign")
PAGES = ["index", "login", "onboarding", "farm", "plan", "tasks", "observations",
         "inventory", "report", "sell-smart", "privacy"]
APP_PAGES = {"farm", "plan", "tasks", "observations", "inventory", "report"}
PUBLIC_PAGES = {"index", "login", "onboarding", "sell-smart", "privacy"}
VIEWPORTS = {"360x800": dict(width=360, height=800, mobile=True), "1366x768": dict(width=1366, height=768, mobile=False)}
ORIGIN = "https://guavaa.netlify.app"
API = "https://guava-8wc7.onrender.com"
ANDROID_UA = ("Mozilla/5.0 (Linux; Android 12; Pixel 5) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36")

# Pesticide / fungicide product names. Generic words (pesticide, fungicide) are not in this list because
# "Pesticide" is a legitimate activity type in the log form.
CHEMICAL_WORDS = (
    "copper", "oxychloride", "sulphur", "sulfur", "mancozeb", "chlorpyrifos", "imidacloprid", "carbendazim",
    "thiophanate", "hexaconazole", "propiconazole", "azoxystrobin", "streptocycline", "malathion",
    "cypermethrin", "dimethoate", "methyl eugenol", "bordeaux",
)
DOSE_RE = re.compile(r"\d+\s*(g|mg|ml|kg|l|litre|liter|litres|liters|%)(?![a-z])", re.IGNORECASE)
BAD_TEXT_RE = re.compile(r"\b(NaN|undefined|null)\b|\[object Object\]")

# Runs in the page: returns measurements.
MEASURE = """() => {
  const vis = (e) => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && !e.closest('[hidden]'); };
  const sel = (e) => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') +
    (e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\\s+/).slice(0, 2).join('.') : '');
  const out = { overflow: document.documentElement.scrollWidth - innerWidth, small_tap: [], small_font: [], body_font: [], clipped: [], no_name: [] };
  const inPara = (e) => e.tagName === 'A' && e.closest('p, li, span.text, td') && getComputedStyle(e).display === 'inline';
  document.querySelectorAll('a,button,input,select,textarea,[role=button]').forEach((e) => {
    if (!vis(e) || e.type === 'hidden' || inPara(e) || e.classList.contains('sr-only')) return;
    let r = e.getBoundingClientRect();
    if ((e.type === 'checkbox' || e.type === 'radio') && e.closest('label')) r = e.closest('label').getBoundingClientRect();
    if (r.width < 43.5 || r.height < 43.5) out.small_tap.push([sel(e), Math.round(r.width) + 'x' + Math.round(r.height)]);
  });
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (w.nextNode()) {
    const t = w.currentNode; const e = t.parentElement;
    if (!e || !t.nodeValue.trim() || seen.has(e) || ['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(e.tagName) || !vis(e)) continue;
    seen.add(e);
    const fs = parseFloat(getComputedStyle(e).fontSize);
    if (fs < 14) out.small_font.push([sel(e), fs]);
    if (['P', 'LI', 'INPUT', 'LABEL'].includes(e.tagName) && fs < 16) out.body_font.push([sel(e), fs]);
    const s = getComputedStyle(e);
    if (!e.classList.contains('sr-only') && s.overflow !== 'visible' && e.scrollHeight > e.clientHeight + 2 && e.clientHeight > 0) out.clipped.push([sel(e), e.scrollHeight + '>' + e.clientHeight]);
  }
  document.querySelectorAll('img,input,select,textarea').forEach((e) => {
    if (!vis(e) || e.type === 'hidden') return;
    const name = e.getAttribute('aria-label') || e.getAttribute('aria-labelledby') || (e.tagName === 'IMG' && e.getAttribute('alt') !== null) || e.getAttribute('title') ||
      (e.labels && e.labels.length) || e.getAttribute('placeholder') || (e.type === 'submit' && e.value);
    if (!name) out.no_name.push(sel(e));
  });
  out.imgs = 0; out.bad_img = []; out.bad_chart = []; out.charts = 0; out.ascii_runs = [];
  document.querySelectorAll('img').forEach((im) => {
    out.imgs++;
    const src = im.currentSrc || im.getAttribute('src') || '';
    const name = sel(im) + ' ' + src.slice(0, 80);
    let origin = '';
    try { origin = new URL(src, location.href).origin; } catch (e) { origin = 'invalid'; }
    if (!im.getAttribute('width') || !im.getAttribute('height')) out.bad_img.push('no width/height attribute: ' + name);
    if (origin !== location.origin) out.bad_img.push('not same-origin: ' + name);
    const r = im.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && !(im.complete && im.naturalWidth > 0)) out.bad_img.push('broken or not loaded: ' + name);
  });
  document.querySelectorAll('.sf-chart canvas').forEach((c) => {
    const block = c.closest('.sf-chart-block');
    if (!block || !vis(block)) return;
    out.charts++;
    let drawn = false;
    try { const blank = document.createElement('canvas'); blank.width = c.width; blank.height = c.height; drawn = c.width > 0 && c.height > 0 && c.toDataURL() !== blank.toDataURL(); } catch (e) {}
    const sm = block.querySelector('.sf-chart-summary');
    const summaryOk = !!sm && vis(sm) && sm.innerText.trim().length > 0;
    if (!(drawn && vis(c)) && !summaryOk) out.bad_chart.push(sel(c) + ': canvas blank and no visible text summary');
  });
  ((document.querySelector('main') || document.body).innerText || '').split('\\n').forEach((line) => {
    (line.match(/\\b[A-Za-z][A-Za-z'’-]*(?:\\s+[A-Za-z][A-Za-z'’-]*){2,}/g) || []).forEach((m) => out.ascii_runs.push(m));
  });
  out.has_nav = !!document.getElementById('sf-nav');
  out.text = document.body.innerText || '';
  out.empty_state = Array.from(document.querySelectorAll('.empty-state, #mandi-hero[data-state=empty]')).some(vis) ||\n    (!!document.getElementById('ranking-status') && vis(document.getElementById('ranking-status')) && document.getElementById('ranking-status').innerText.trim().length > 0 && !document.getElementById('ranking-retry').offsetParent && document.getElementById('ranking-body').classList.contains('hidden'));
  out.error_state = Array.from(document.querySelectorAll('.load-error__retry, #page-error, #report-error .load-error, [data-mandi-retry], #ranking-retry, #settings-retry')).some(vis);
  const grab = (id) => { const e = document.querySelector(id); return e && vis(e) ? e.innerText : ''; };
  out.risk_text = grab('#disease-risk-list') + ' ' + grab('#irrigation-advisory');
  out.estimate_pills = {
    disease: document.querySelectorAll('#disease-risk-list .estimate-pill').length,
    irrigation: document.querySelectorAll('#irrigation-advisory .estimate-pill').length,
    gdd: document.querySelectorAll('#gdd-section .estimate-pill').length,
    fert: document.querySelectorAll('#fert-forecast .estimate-pill').length,
  };
  return out;
}"""

IMG_BYTES = {}  # url -> bytes of every image the page loaded through the site route (reset per page)
IMG_BUDGET = 150 * 1024
FIXTURES = Path(__file__).parent / "fixtures"
# Words that may stay English in Hindi pages: brand, unit and test-data names.
ASCII_OK = set("smart farmer agmarknet guava google netlify supabase ai gps kvk icar govt india test mandi one two fake district variety farm block apmc rs kg quintal per sf rani nature photography".split())

LIST_KEYS = ("small_tap", "small_font", "body_font", "clipped", "no_name")


LOAD_IMAGES = """async () => {
  const imgs = Array.from(document.querySelectorAll('img'));
  for (const im of imgs) {
    const r = im.getBoundingClientRect();
    if (!r.width && !r.height) continue;
    im.scrollIntoView({ block: 'center' });
    if (!(im.complete && im.naturalWidth > 0)) {
      await Promise.race([new Promise((res) => { im.addEventListener('load', res, { once: true }); im.addEventListener('error', res, { once: true }); }),
                          new Promise((res) => setTimeout(res, 2500))]);
    }
  }
  window.scrollTo(0, 0);
}"""


def measure(page):
    """Scroll every image into view so lazy ones load, then take the measurements."""
    page.evaluate(LOAD_IMAGES)
    return page.evaluate(MEASURE)


def serve_local(port_holder):
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(ROOT), **k)
        def log_message(self, *a):
            pass
    srv = socketserver.TCPServer(("127.0.0.1", 0), H)
    port_holder.append(srv.server_address[1])
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def install_routes(ctx, args, base, unmocked):
    def site(route):
        url = route.request.url.split("?")[0].split("#")[0]
        rel = url[len(ORIGIN):].lstrip("/") or "index.html"
        if rel.startswith("__fixtures__/"):
            f = FIXTURES / rel[len("__fixtures__/"):]
            return route.fulfill(status=200, body=f.read_bytes(), content_type=mimetypes.guess_type(str(f))[0] or "text/plain") if f.is_file() else route.fulfill(status=404, body="not found")
        f = ROOT / rel
        if f.is_dir() or not f.exists():
            f = ROOT / (rel + ".html") if (ROOT / (rel + ".html")).exists() else None
        if not f:
            return route.fulfill(status=404, body="not found")
        body = f.read_bytes()
        ctype = mimetypes.guess_type(str(f))[0] or "text/plain"
        if ctype.startswith("image/"):
            IMG_BYTES[url] = len(body)
        route.fulfill(status=200, body=body, content_type=ctype)
    # Playwright runs the LAST registered matching route first, so the catch-all goes first.
    def other(route):
        u = route.request.url
        if u.startswith(ORIGIN) or u.startswith("http://127.0.0.1") or u.startswith(API) or u.startswith("data:"):
            return route.fallback()
        if args.real_cdn and ("jsdelivr" in u or "cdnjs" in u):
            return route.continue_()
        unmocked.append(u)
        route.abort()
    ctx.route("**/*", other)
    if not args.local:
        ctx.route(ORIGIN + "/**", site)
    ctx.route("**/@supabase/supabase-js@2/+esm", lambda r: r.fulfill(
        status=200, content_type="application/javascript", body=mock_api.supabase_stub(args.anon)))
    cors = {"access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*"}
    def api(route):
        p = route.request.url[len(API):].split("?")[0]
        if route.request.method == "OPTIONS":
            return route.fulfill(status=204, headers=cors)
        status, data = mock_api.respond(p, route.request.method, route.request.post_data or "", args.scenario)
        route.fulfill(status=status, content_type="application/json", body=json.dumps(data), headers=cors)
    ctx.route(API + "/**", api)
    if not args.real_cdn:
        ctx.route("**/npm/chart.js", lambda r: r.fulfill(status=200, content_type="application/javascript", body=mock_api.CHART_STUB))
        ctx.route("https://cdnjs.cloudflare.com/**", lambda r: r.fulfill(status=200, content_type="text/css", body="/* font-awesome stub */"))


def merge(total, m):
    """Fold one measurement into the running total for a page."""
    if total is None:
        total = {k: [] for k in LIST_KEYS}
        total.update(overflow=0, has_nav=False, texts=[], empty_state=False, error_state=False, risk_text="",
                     imgs=0, bad_img=[], charts=0, bad_chart=[], ascii_runs=[], img_kb=None,
                     estimate_pills={"disease": 0, "irrigation": 0, "gdd": 0, "fert": 0})
    for k in LIST_KEYS:
        for item in m[k]:
            if item not in total[k]:
                total[k].append(item)
    for k in ("bad_img", "bad_chart", "ascii_runs"):
        for item in m.get(k, []):
            if item not in total[k]:
                total[k].append(item)
    total["imgs"] = max(total["imgs"], m.get("imgs", 0))
    total["charts"] = max(total["charts"], m.get("charts", 0))
    total["overflow"] = max(total["overflow"], m["overflow"])
    total["has_nav"] = total["has_nav"] or m["has_nav"]
    total["texts"].append(m["text"])
    total["empty_state"] = total["empty_state"] or m["empty_state"]
    total["error_state"] = total["error_state"] or m["error_state"]
    total["risk_text"] += " " + m["risk_text"]
    for k, v in m["estimate_pills"].items():
        total["estimate_pills"][k] = max(total["estimate_pills"][k], v)
    return total


def explore(page, pg, total, extra):
    """Open forms, modals and tab panels on the app pages and measure each state."""
    def snap():
        nonlocal total
        total = merge(total, measure(page))

    snap()
    if pg == "plan":
        page.wait_for_selector("#page-content:not(.hidden), #page-error:not(.hidden), #page-no-farm:not(.hidden)", timeout=8000)
        page.wait_for_timeout(500)
        for panel in page.eval_on_selector_all("[data-panel]", "els => els.map(e => e.dataset.panel)"):
            btn = page.query_selector(f'[data-panel="{panel}"]')
            if not btn or not btn.is_visible():
                continue
            btn.click()
            if panel == "panel-insights":
                page.wait_for_selector("#insights-content:not(.hidden), #insights-loading .load-error", timeout=8000)
                page.wait_for_timeout(600)
            page.wait_for_timeout(250)
            snap()
            if panel == "panel-ai" and page.query_selector("#ai-chat-input"):
                chat_flow(page, extra)
                snap()
    else:
        page.wait_for_timeout(300)
        for btn_id in page.eval_on_selector_all('[id^="btn-show-"]', "els => els.map(e => e.id)"):
            btn = page.query_selector("#" + btn_id)
            if btn and btn.is_visible():
                btn.click()
                page.wait_for_timeout(250)
                snap()
        for modal_btn in (".btn-consume:not([disabled])", ".btn-plant-history"):
            b = page.query_selector(modal_btn)
            if b and b.is_visible():
                b.click()
                page.wait_for_timeout(300)
                snap()
                page.keyboard.press("Escape")
                page.wait_for_timeout(150)
    # Error scenario: the Retry button must work (re-run the loader) without a page error.
    retry = page.query_selector(".load-error__retry")
    if retry and retry.is_visible():
        retry.click()
        page.wait_for_timeout(500)
        snap()
    return total


def chat_flow(page, extra):
    box = page.query_selector("#ai-chat-input")
    send = page.query_selector("#ai-chat-container button")
    for question, expect in (("How often should I water my trees?", "steady moisture"),
                             ("What dose of pesticide should I spray?", "cannot verify the safety")):
        before = page.eval_on_selector("#ai-chat-messages", "e => e.children.length")
        box.fill(question)
        send.click()
        try:
            page.wait_for_function("n => document.querySelector('#ai-chat-messages').children.length >= n + 2", arg=before, timeout=6000)
        except Exception:
            extra.append(f"AI chat gave no reply to: {question}")
            return
        last = page.eval_on_selector("#ai-chat-messages", "e => e.lastElementChild.innerText")
        if expect not in last:
            extra.append(f"AI reply did not show the server text for: {question} -> {last[:80]!r}")


def _largest_font(page):
    return page.evaluate("""() => { let best = 0, txt = '';
      const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      while (w.nextNode()) { const e = w.currentNode.parentElement; if (!e || !w.currentNode.nodeValue.trim()) continue;
        if (['SCRIPT','STYLE','NOSCRIPT'].includes(e.tagName)) continue; const r = e.getBoundingClientRect(); if (!r.width) continue;
        const fs = parseFloat(getComputedStyle(e).fontSize); if (fs > best) { best = fs; txt = e.innerText.slice(0, 40); } }
      const hero = document.querySelector('.price-hero__value');
      return { best, txt, hero: hero ? parseFloat(getComputedStyle(hero).fontSize) : 0 }; }""")


def explore_public(page, pg, total, extra, scenario):
    """Interactions on index, login, onboarding, sell-smart and privacy; measures after each state."""
    def snap():
        nonlocal total
        total = merge(total, measure(page))

    page.on("dialog", lambda d: d.accept())
    snap()
    if pg == "index":
        f = _largest_font(page)
        if scenario == "ok":
            if not f["hero"] or f["hero"] < 36 or f["hero"] < f["best"]:
                extra.append(f"index: the mandi price is not the largest number/text (hero {f['hero']}px, largest {f['best']}px: {f['txt']!r})")
            hero = page.inner_text("#mandi-hero")
            for need in ("42", "4,200", "Madhya Pradesh", "20/11/2026", "Agmarknet"):
                if need not in hero:
                    extra.append(f"index hero missing {need!r}")
        # language toggle persists (then restore the language this run started with)
        start_lang = page.evaluate("localStorage.getItem('sf_lang')") or "en"
        other = "en" if start_lang == "hi" else "hi"
        page.click("#lang-" + other)
        page.wait_for_timeout(200)
        if page.evaluate("localStorage.getItem('sf_lang')") != other:
            extra.append("index: language toggle did not persist")
        page.click("#lang-" + start_lang)
        # contact form: validation, then success
        page.click("#contact-submit")
        page.wait_for_timeout(150)
        if not page.is_visible("#contact-validation"):
            extra.append("index: empty contact form shows no validation text")
        snap()
        page.fill("#contact-name", "Test Farmer")
        page.fill("#contact-phone", "9999999999")
        page.click("#contact-submit")
        page.wait_for_timeout(150)
        if "tick" not in page.inner_text("#contact-validation-text").lower() and "निशान" not in page.inner_text("#contact-validation-text"):
            extra.append("index: missing-consent message not shown")
        page.click("label[for=contact-consent]")
        page.click("#contact-submit")
        page.wait_for_timeout(500)
        if scenario == "ok" and not page.is_visible("#contact-success"):
            extra.append("index: contact form did not show success")
        snap()
    elif pg == "login":
        if not page.is_visible("#btn-google-signin"):
            extra.append("login: sign-in button not visible")
        h = page.evaluate("document.getElementById('btn-google-signin').getBoundingClientRect().height")
        w = page.evaluate("document.getElementById('btn-google-signin').getBoundingClientRect().width / document.getElementById('btn-google-signin').parentElement.getBoundingClientRect().width")
        if h < 47.5 or w < 0.99:
            extra.append(f"login: button should be full width and >= 48px (got height {h}, width ratio {w:.2f})")
        page.click("#btn-google-signin")
        page.wait_for_timeout(300)
        snap()
    elif pg == "onboarding":
        opts = page.eval_on_selector_all("#state-select option", "o => o.map(x => x.value).filter(Boolean)")
        if opts != ["Madhya Pradesh", "Maharashtra"]:
            extra.append(f"onboarding: state options are {opts}")
        for sel, mode in (("#plant-count", "numeric"), ("#expected-yield", "decimal")):
            if page.get_attribute(sel, "inputmode") != mode:
                extra.append(f"onboarding: {sel} inputmode is not {mode}")
        page.select_option("#state-select", "Maharashtra")
        n = page.eval_on_selector_all("#district-select option", "o => o.length")
        if n < 5:
            extra.append("onboarding: district list did not fill")
        page.click("#btn-submit")
        page.wait_for_timeout(150)
        if not page.is_visible("#plant-count-error"):
            extra.append("onboarding: empty plant count shows no inline error")
        snap()
        page.fill("#plant-count", "7777")
        page.select_option("#district-select", index=1)
        if scenario == "ok":
            page.click("#btn-submit")
            page.wait_for_selector("#form-error:not(.hidden)", timeout=5000)
            if "too high" not in page.inner_text("#form-error") and "looks" not in page.inner_text("#form-error"):
                extra.append("onboarding: backend 422 text not shown")
            if page.is_disabled("#btn-submit"):
                extra.append("onboarding: submit stays disabled after an error")
            snap()
    elif pg == "sell-smart":
        page.wait_for_timeout(600)
        if scenario == "ok":
            cards = page.eval_on_selector_all("#ranking-body ol > li", "l => l.length")
            if cards < 3:
                extra.append(f"sell-smart: expected ranked cards, found {cards}")
            if not page.is_visible("#trend-chart-summary") or not page.inner_text("#trend-chart-summary").strip():
                extra.append("sell-smart: chart has no text summary")
            if not page.get_attribute("#trend-chart", "aria-label"):
                extra.append("sell-smart: chart has no aria-label")
            need = page.inner_text("#trend-windows")
            if "12" not in need:
                extra.append("sell-smart: 'N more days needed' text missing")
            # edit, pause, delete, 409, mark as read
            page.click("#alerts-list li >> text=/Change price|भाव बदलें/")
            page.wait_for_timeout(150)
            snap()
            page.fill("#alerts-list input", "55")
            page.click("#alerts-list .btn-primary")
            page.wait_for_timeout(400)
            if page.is_visible("#alerts-list input"):
                extra.append("sell-smart: alert edit did not close after save")
            page.select_option("#alert-where", index=1)
            page.fill("#alert-target", "999")
            page.click("#alert-add")
            page.wait_for_timeout(400)
            msg = page.inner_text("#alert-form-status")
            if "20" not in msg:
                extra.append(f"sell-smart: 409 limit message not shown in plain words: {msg!r}")
            snap()
            page.click("#alerts-list li >> nth=0 >> text=/Delete|हटाएं/")
            page.wait_for_timeout(400)
            if page.is_visible("#alert-form-status.is-error") and "20" not in page.inner_text("#alert-form-status"):
                extra.append("sell-smart: delete failed")
            b = page.query_selector("#notif-list .btn")
            if b:
                b.click()
                page.wait_for_timeout(300)
            else:
                extra.append("sell-smart: no mark-as-read button in notifications")
            snap()
            # every card shows a source and a date
            for li in page.query_selector_all("#ranking-body ol > li"):
                if "/" not in li.inner_text():
                    extra.append("sell-smart: ranked card without a date")
                    break
            if "Agmarknet" not in page.inner_text("#ranking-body"):
                extra.append("sell-smart: ranking shows no source")
        start_lang = page.evaluate("localStorage.getItem('sf_lang')") or "en"
        other = "en" if start_lang == "hi" else "hi"
        page.click("#lang-" + other)
        page.wait_for_timeout(300)
        m = measure(page)
        m["ascii_runs"] = []  # the page is in the other language here
        total = merge(total, m)
        page.click("#lang-" + start_lang)
    else:  # privacy
        heads = page.eval_on_selector_all("h1, h2", "e => e.map(x => x.tagName)")
        if heads[:1] != ["H1"] or len(heads) < 6:
            extra.append(f"privacy: heading hierarchy looks wrong {heads}")
        txt = page.inner_text("main").lower()
        if not ("mandi" in txt or "मंडिय" in txt) or not ("saved cop" in txt or "सहेजी" in txt):
            extra.append("privacy: farm-location / saved-copy statements missing")
    return total


def special_runs(browser, args):
    """Extra scenarios: ?demo=1 on a production origin vs localhost, Supabase unreachable, Chart.js offline."""
    import copy
    out = []
    (ART / "screens").mkdir(parents=True, exist_ok=True)

    def new_ctx(local_base=None, anon=True):
        a = copy.copy(args)
        a.anon = anon
        a.scenario = "ok"
        a.local = bool(local_base)
        ctx = browser.new_context(viewport={"width": 360, "height": 800}, is_mobile=True, has_touch=True,
                                  device_scale_factor=2, user_agent=ANDROID_UA, service_workers="block")
        ctx.add_init_script("try{localStorage.setItem('sf_lang','en')}catch(e){}")
        un = []
        install_routes(ctx, a, local_base or ORIGIN, un)
        return ctx, un

    def row(name, errs, content, measure):
        total = merge(None, measure)
        total.pop("texts", None)
        out.append(dict(page=name, viewport="360x800", lang="en", scenario="special", errors=errs, unmocked=[],
                        content=content, **total))

    def watch(page, errs, reqs):
        page.on("console", lambda m: errs.append("console." + m.type + ": " + m.text[:200]) if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: errs.append("pageerror: " + str(e)[:200]))
        page.on("request", lambda r: reqs.append(r.url))

    # 1. ?demo=1 on the production origin: sign-in gate, no banner, no request to 127.0.0.1:8001
    ctx, un = new_ctx(anon=True)
    page = ctx.new_page()
    page.add_init_script("localStorage.setItem('sf_test_anon','1')")
    errs, reqs, content = [], [], []
    watch(page, errs, reqs)
    page.goto(f"{ORIGIN}/sell-smart.html?demo=1", wait_until="load")
    try:
        page.wait_for_url("**/login.html", timeout=8000)
    except Exception:
        content.append("demo flag on the production origin did not send an anonymous visitor to the sign-in page")
    page.wait_for_timeout(500)
    if any("127.0.0.1:8001" in r for r in reqs):
        content.append("request sent to 127.0.0.1:8001 from the production origin")
    if page.query_selector("#demo-banner") and page.is_visible("#demo-banner"):
        content.append("DEMO banner visible on the production origin")
    errs = [e for e in errs if "Service Worker" not in e]
    page.screenshot(path=str(ART / "screens" / "special_demo_prod_origin.png"))
    row("sell-smart?demo=1 [production origin]", errs, content, measure(page))
    ctx.close()

    # 2. ?demo=1 on 127.0.0.1: the demo works and shows the banner
    holder = []
    srv = serve_local(holder)
    base = f"http://127.0.0.1:{holder[0]}"
    ctx, un = new_ctx(local_base=base, anon=True)
    cors = {"access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*"}

    def demo_api(route):
        if route.request.method == "OPTIONS":
            return route.fulfill(status=204, headers=cors)
        p = route.request.url[len("http://127.0.0.1:8001"):].split("?")[0]
        status, data = mock_api.respond(p, route.request.method, route.request.post_data or "", "ok")
        route.fulfill(status=status, content_type="application/json", body=json.dumps(data), headers=cors)
    ctx.route("http://127.0.0.1:8001/**", demo_api)
    page = ctx.new_page()
    errs, reqs, content = [], [], []
    watch(page, errs, reqs)
    page.goto(f"{base}/sell-smart.html?demo=1", wait_until="load")
    page.wait_for_timeout(1500)
    if not page.is_visible("#demo-banner"):
        content.append("DEMO banner not shown on 127.0.0.1")
    if not any("127.0.0.1:8001" in r for r in reqs):
        content.append("demo mode on 127.0.0.1 made no request to the demo server")
    errs = [e for e in errs if "Service Worker" not in e]
    page.screenshot(path=str(ART / "screens" / "special_demo_local.png"), full_page=True)
    row("sell-smart?demo=1 [127.0.0.1]", errs, content, measure(page))
    ctx.close()
    srv.shutdown()

    # 3. Supabase library unreachable: login shows a message, not a blank page
    ctx, un = new_ctx(anon=True)
    ctx.route("**/@supabase/supabase-js@2/+esm", lambda r: r.abort())
    page = ctx.new_page()
    errs, reqs, content = [], [], []
    watch(page, errs, reqs)
    page.goto(f"{ORIGIN}/login.html", wait_until="load")
    page.wait_for_timeout(1200)
    if not page.is_visible("#auth-error-box"):
        content.append("login: no message when the sign-in library cannot load")
    errs = [e for e in errs if "Failed to load resource" not in e and "Service Worker" not in e and "ERR_FAILED" not in e
            and "dynamically imported" not in e]
    page.screenshot(path=str(ART / "screens" / "special_login_no_supabase.png"))
    row("login [sign-in library unreachable]", errs, content, measure(page))
    ctx.close()

    # 4. Chart.js unreachable (offline): the text summary stays, no console error
    ctx, un = new_ctx(anon=False)
    ctx.route("**/npm/chart.js", lambda r: r.abort())
    page = ctx.new_page()
    errs, reqs, content = [], [], []
    watch(page, errs, reqs)
    page.goto(f"{ORIGIN}/sell-smart.html", wait_until="load")
    page.wait_for_timeout(1500)
    summ = page.inner_text("#trend-chart-summary")
    if not summ.strip():
        content.append("sell-smart: no text summary when Chart.js fails to load")
    if page.is_visible("#trend-chart"):
        content.append("sell-smart: empty chart canvas still visible when Chart.js fails")
    errs = [e for e in errs if "Failed to load resource" not in e and "Service Worker" not in e and "ERR_FAILED" not in e]
    page.screenshot(path=str(ART / "screens" / "special_sell_chart_offline.png"), full_page=True)
    row("sell-smart [Chart.js unreachable]", errs, content, measure(page))
    ctx.close()
    # 5. Chart.js unreachable on index and report: each chart keeps its text summary and shows a plain list
    def chart_text(page, canvas_id):
        return page.evaluate("""(id) => { const c = document.getElementById(id); if (!c) return null;
            const b = c.closest('.sf-chart-block'); return { summary: b.querySelector('.sf-chart-summary').textContent.trim(),
            listItems: b.querySelectorAll('.sf-chart-list li').length, canvasVisible: !!(c.offsetWidth || c.offsetHeight),
            aria: c.getAttribute('aria-label') || '' }; }""", canvas_id)
    for pg_name, anon_flag, cid in (("index", True, "mandi-bar-chart"), ("report", False, "spend-donut")):
        ctx, un = new_ctx(anon=anon_flag)
        ctx.route("**/npm/chart.js", lambda r: r.abort())
        page = ctx.new_page()
        if anon_flag:
            page.add_init_script("localStorage.setItem('sf_test_anon','1')")
        errs, reqs, content = [], [], []
        watch(page, errs, reqs)
        page.goto(f"{ORIGIN}/{pg_name}.html", wait_until="load")
        page.wait_for_timeout(1800)
        info = chart_text(page, cid)
        if not info:
            content.append(f"{pg_name}: chart #{cid} not rendered")
        else:
            if not info["summary"]:
                content.append(f"{pg_name}: no text summary when Chart.js fails to load")
            if not info["listItems"]:
                content.append(f"{pg_name}: no plain list when Chart.js fails to load")
            if info["canvasVisible"]:
                content.append(f"{pg_name}: empty chart canvas still visible when Chart.js fails")
            if not info["aria"]:
                content.append(f"{pg_name}: chart canvas has no aria-label")
        errs = [e for e in errs if "Failed to load resource" not in e and "Service Worker" not in e and "ERR_FAILED" not in e]
        page.screenshot(path=str(ART / "screens" / f"special_{pg_name}_chart_offline.png"), full_page=True)
        row(f"{pg_name} [Chart.js unreachable]", errs, content, measure(page))
        ctx.close()
    # 6. Price history: day counter below 7 saved days, line chart from 7 (the backend decides via has_trend)
    ctx, un = new_ctx(anon=False)
    page = ctx.new_page()
    errs, reqs, content = [], [], []
    watch(page, errs, reqs)
    page.goto(f"{ORIGIN}/plan.html", wait_until="load")
    page.wait_for_selector("#page-content:not(.hidden)", timeout=8000)
    page.evaluate("switchPanel('panel-insights')")
    page.wait_for_timeout(1500)
    few = page.inner_text("#mandi-history")
    if "3 of 7" not in few or page.query_selector("#mandi-history-chart"):
        content.append("plan: fewer than 7 saved days (3 in the default fixture) must show the day counter and no chart")
    ctx.close()
    days = [f"2026-11-{d:02d}" for d in range(13, 21)]
    hist = {"has_trend": True, "min_days_for_trend": 7, "distinct_days": 8, "market": "Test Mandi (fake)",
            "first_date": days[0], "last_date": days[-1],
            "series": [{"trade_date": d, "modal_per_kg": 40 + i, "min_per_kg": 30, "max_per_kg": 50, "rows": 1} for i, d in enumerate(days)]}
    ctx, un = new_ctx(anon=False)
    hist_cors = {"access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*"}
    ctx.route("**/api/market-prices/guava/history*", lambda r: r.fulfill(
        status=204 if r.request.method == "OPTIONS" else 200, content_type="application/json",
        body="" if r.request.method == "OPTIONS" else json.dumps(hist), headers=hist_cors))
    page = ctx.new_page()
    watch(page, errs, reqs)
    page.goto(f"{ORIGIN}/plan.html", wait_until="load")
    page.wait_for_selector("#page-content:not(.hidden)", timeout=8000)
    page.evaluate("switchPanel('panel-insights')")
    page.wait_for_timeout(1500)
    info = chart_text(page, "mandi-history-chart")
    if not info or not info["summary"]:
        content.append("plan: 8 saved days must draw the history chart with a text summary")
    errs = [e for e in errs if "Failed to load resource" not in e and "Service Worker" not in e]
    page.screenshot(path=str(ART / "screens" / "special_plan_history.png"), full_page=True)
    row("plan [price history 1 day vs 8 days]", errs, content, measure(page))
    ctx.close()
    return out


def run(args):
    pages = args.pages.split(",") if args.pages else PAGES
    vps = [args.viewport] if args.viewport else list(VIEWPORTS)
    langs = args.lang.split(",") if args.lang else ["en", "hi"]
    (ART / "screens").mkdir(parents=True, exist_ok=True)
    holder = []
    srv = serve_local(holder) if args.local else None
    base = f"http://127.0.0.1:{holder[0]}" if args.local else ORIGIN
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for vp in vps:
            cfg = VIEWPORTS[vp]
            for lang in langs:
                kw = dict(viewport={"width": cfg["width"], "height": cfg["height"]}, service_workers="block")
                if cfg["mobile"]:
                    kw.update(is_mobile=True, has_touch=True, device_scale_factor=2, user_agent=ANDROID_UA)
                ctx = browser.new_context(**kw)
                ctx.add_init_script(f"try{{localStorage.setItem('sf_lang','{lang}')}}catch(e){{}}")
                unmocked = []
                install_routes(ctx, args, base, unmocked)
                for pg in pages:
                    page = ctx.new_page()
                    # localStorage is shared by every page of the origin, so set or clear the flag on each page
                    anon_js = "setItem('sf_test_anon','1')" if (pg == 'login' or args.anon) else "removeItem('sf_test_anon')"
                    page.add_init_script("try{localStorage." + anon_js + "}catch(e){}")
                    errs, extra = [], []
                    page.on("console", lambda m, errs=errs: errs.append("console." + m.type + ": " + m.text[:200]) if m.type in ("error", "warning") else None)
                    page.on("pageerror", lambda e, errs=errs: errs.append("pageerror: " + str(e)[:200]))
                    page.on("requestfailed", lambda r, errs=errs: errs.append("requestfailed: " + r.url[:150]) if "chrome-extension" not in r.url else None)
                    n0 = len(unmocked)
                    total = None
                    IMG_BYTES.clear()
                    first_load_bytes = None
                    try:
                        page.goto(f"{base}/{pg}.html", wait_until="load", timeout=20000)
                        page.wait_for_timeout(1200)
                        first_load_bytes = sum(IMG_BYTES.values())
                        if pg in APP_PAGES:
                            total = explore(page, pg, total, extra)
                        elif pg in PUBLIC_PAGES:
                            total = explore_public(page, pg, total, extra, args.scenario)
                        else:
                            total = merge(total, measure(page))
                        page.evaluate("window.scrollTo(0, 0)")
                        shot = ART / "screens" / f"{pg}_{vp}_{lang}_{args.scenario}.png"
                        page.screenshot(path=str(shot), full_page=True)
                        if (vp, lang, args.scenario) == ("360x800", "en", "ok"):
                            (ART / "screens" / "after").mkdir(parents=True, exist_ok=True)
                            shutil.copyfile(shot, ART / "screens" / "after" / f"{pg}.png")
                    except Exception as e:  # keep going; record as failure
                        total = total or merge(None, {"overflow": 0, "small_tap": [], "small_font": [], "body_font": [], "clipped": [],
                                                      "no_name": [], "has_nav": False, "text": "", "empty_state": False,
                                                      "error_state": False, "risk_text": "",
                                                      "imgs": 0, "bad_img": [], "charts": 0, "bad_chart": [], "ascii_runs": [],
                                                      "estimate_pills": {"disease": 0, "irrigation": 0, "gdd": 0, "fert": 0}})
                        errs.append("harness: " + str(e)[:80] + " ... " + str(e)[-260:])
                    page.close()
                    # aborted unmocked CDN requests surface as requestfailed; keep them out of console errors
                    errs = [e for e in errs if not any(u in e for u in unmocked[n0:])]
                    if unmocked[n0:]:  # Chromium's generic message for an aborted (unmocked) request has no URL
                        errs = [e for e in errs if "Failed to load resource: net::ERR_FAILED" not in e]
                    errs = [e for e in errs if "Service Worker registration blocked" not in e]
                    if pg in ("onboarding", "sell-smart"):  # the check provokes a 422 / 409 on purpose
                        errs = [e for e in errs if not re.search(r"Failed to load resource: the server responded with a status of (409|422)", e)]
                    if args.scenario != "ok":  # the browser logs every 4xx/5xx response; those are expected here
                        errs = [e for e in errs if "Failed to load resource" not in e and "Mandi prices load failed" not in e]

                    # content checks on the app pages
                    content = []
                    if pg in APP_PAGES or pg in PUBLIC_PAGES:
                        text = " ".join(total["texts"])
                        bad = sorted(set(BAD_TEXT_RE.findall(text)))
                        if bad:
                            content.append(f"bad text in page: {bad}")
                        risk = total["risk_text"].lower()
                        found = [w for w in CHEMICAL_WORDS if w in risk]
                        if found:
                            content.append(f"chemical words in alerts: {found}")
                        if DOSE_RE.search(total["risk_text"]):
                            content.append("dose-like text in alerts")
                        if args.scenario == "ok" and pg == "plan":
                            pills = total["estimate_pills"]
                            for key, n in pills.items():
                                if n < 1:
                                    content.append(f"missing Estimate label: {key}")
                        if args.scenario == "empty" and pg in (APP_PAGES | {"index", "sell-smart"}) and not total["empty_state"]:
                            content.append("empty scenario: no empty-state message visible")
                        if args.scenario == "error" and pg in (APP_PAGES | {"index", "sell-smart"}) and not total["error_state"]:
                            content.append("error scenario: no Retry / error state visible")
                    content += [f"image: {x}" for x in total["bad_img"]]
                    content += [f"chart: {x}" for x in total["bad_chart"]]
                    if pg == "index" and vp == "360x800" and not args.local and first_load_bytes is not None:
                        total["img_kb"] = round(first_load_bytes / 1024)
                        if first_load_bytes > IMG_BUDGET:
                            content.append(f"image: index first load fetched {total['img_kb']} KB of images (limit 150 KB)")
                    total["soft"] = []
                    if lang == "hi":
                        for run_text in total["ascii_runs"]:
                            if not all(w.lower() in ASCII_OK for w in re.findall(r"[A-Za-z]+", run_text)):
                                total["soft"].append(run_text)
                    content += extra
                    total.pop("texts", None)
                    results.append(dict(page=pg, viewport=vp, lang=lang, scenario=args.scenario, errors=errs,
                                        unmocked=unmocked[n0:], content=content, **total))
                ctx.close()
        if args.scenario == 'ok' and not args.pages and not args.viewport and not args.lang:
            results += special_runs(browser, args)
        browser.close()
    if srv:
        srv.shutdown()
    return results


def report(results, out_md):
    hard = 0
    lines = ["| page | viewport | lang | scenario | errors | overflow px | tap<44 | font<14 | p/li/input/label<16 | clipped | no name | content | imgs | broken img | img KB (index) | charts | bad charts | untranslated (soft) | nav |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    detail = []
    soft = []
    for r in results:
        bad = (bool(r["errors"]) or r["overflow"] > 1 or r["small_tap"] or r["body_font"] or r["clipped"]
               or r["no_name"] or r["small_font"] or r["content"])
        hard += 1 if bad else 0
        lines.append(f"| {r['page']} | {r['viewport']} | {r['lang']} | {r['scenario']} | {len(r['errors'])} | {max(r['overflow'], 0)} | "
                     f"{len(r['small_tap'])} | {len(r['small_font'])} | {len(r['body_font'])} | {len(r['clipped'])} | "
                     f"{len(r['no_name'])} | {len(r['content'])} | {r.get('imgs', 0)} | {len(r.get('bad_img', []))} | "
                     f"{r.get('img_kb') if r.get('img_kb') is not None else '-'} | {r.get('charts', 0)} | {len(r.get('bad_chart', []))} | "
                     f"{len(r.get('soft', []))} | {'yes' if r['has_nav'] else 'no'} |")
        if r.get("soft"):
            soft.append(f"- {r['page']} {r['viewport']} {r['lang']} {r['scenario']} (first 5 of {len(r['soft'])}): {r['soft'][:5]}")
        for key in ("errors", "small_tap", "small_font", "body_font", "clipped", "no_name", "content"):
            if r[key]:
                detail.append(f"- {r['page']} {r['viewport']} {r['lang']} {r['scenario']} {key} (worst 5 of {len(r[key])}): {r[key][:5]}")
    text = "# Browser check\n\n" + "\n".join(lines) + "\n\n## Offenders\n\n" + "\n".join(detail) + "\n\n## Soft warnings: English text on Hindi pages (not a failure)\n\n" + "\n".join(soft) + f"\n\nRows with a hard failure: {hard} of {len(results)}\n"
    out_md.write_text(text, encoding="utf-8")
    return hard


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages"); ap.add_argument("--viewport", choices=list(VIEWPORTS)); ap.add_argument("--lang")
    ap.add_argument("--scenario", choices=("all", "ok", "empty", "error"), default="all")
    ap.add_argument("--local", action="store_true"); ap.add_argument("--anon", action="store_true")
    ap.add_argument("--real-cdn", action="store_true"); ap.add_argument("--report", default=str(ART / "browser_report.md"))
    args = ap.parse_args()
    import copy
    results = []
    for sc in (("ok", "empty", "error") if args.scenario == "all" else (args.scenario,)):
        a = copy.copy(args)
        a.scenario = sc
        results += run(a)
    ART.mkdir(parents=True, exist_ok=True)
    (ART / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    hard = report(results, Path(args.report))
    print(f"{len(results)} runs, {hard} with hard failures; report: {args.report}")
    sys.exit(1 if hard else 0)


if __name__ == "__main__":
    main()
