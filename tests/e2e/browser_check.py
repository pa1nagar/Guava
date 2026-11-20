"""Browser check: every page x viewport x language against mocked Supabase + API.

python tests/e2e/browser_check.py [--pages a,b] [--viewport 360x800] [--lang en] [--scenario ok|empty|error]
                                  [--local] [--anon] [--real-cdn] [--report path]
Writes screenshots + results.json + a markdown report under .agents/tasks/guava-polish/ (not committed).
Exit code 1 if any hard check fails.

For the signed-in app pages (farm, plan, tasks, observations, inventory, report) the check also opens every
form, modal and tab panel and measures again, runs the AI chat on plan.html, and checks:
  - no "NaN" / "undefined" / "null" in the visible text
  - the Estimate label on disease alerts, GDD, fertilizer forecast and irrigation advisory (ok scenario)
  - no chemical name or dose in the disease alerts / irrigation advisory text
  - empty scenario: an empty-state message is visible; error scenario: a Retry button (or error panel) is visible
"""
import argparse
import http.server
import json
import mimetypes
import re
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
import mock_api  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
ART = Path("D:/Python World/Experiment/Guava/.agents/tasks/guava-polish")
PAGES = ["index", "login", "onboarding", "farm", "plan", "tasks", "observations",
         "inventory", "report", "sell-smart", "privacy"]
APP_PAGES = {"farm", "plan", "tasks", "observations", "inventory", "report"}
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
    const name = e.getAttribute('aria-label') || e.getAttribute('aria-labelledby') || e.getAttribute('alt') || e.getAttribute('title') ||
      (e.labels && e.labels.length) || e.getAttribute('placeholder') || (e.type === 'submit' && e.value);
    if (!name) out.no_name.push(sel(e));
  });
  out.has_nav = !!document.getElementById('sf-nav');
  out.text = document.body.innerText || '';
  out.empty_state = Array.from(document.querySelectorAll('.empty-state')).some(vis);
  out.error_state = Array.from(document.querySelectorAll('.load-error__retry, #page-error, #report-error .load-error')).some(vis);
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

LIST_KEYS = ("small_tap", "small_font", "body_font", "clipped", "no_name")


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
        f = ROOT / rel
        if f.is_dir() or not f.exists():
            f = ROOT / (rel + ".html") if (ROOT / (rel + ".html")).exists() else None
        if not f:
            return route.fulfill(status=404, body="not found")
        route.fulfill(status=200, body=f.read_bytes(), content_type=mimetypes.guess_type(str(f))[0] or "text/plain")
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
                     estimate_pills={"disease": 0, "irrigation": 0, "gdd": 0, "fert": 0})
    for k in LIST_KEYS:
        for item in m[k]:
            if item not in total[k]:
                total[k].append(item)
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
        total = merge(total, page.evaluate(MEASURE))

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
                    errs, extra = [], []
                    page.on("console", lambda m, errs=errs: errs.append("console." + m.type + ": " + m.text[:200]) if m.type in ("error", "warning") else None)
                    page.on("pageerror", lambda e, errs=errs: errs.append("pageerror: " + str(e)[:200]))
                    page.on("requestfailed", lambda r, errs=errs: errs.append("requestfailed: " + r.url[:150]) if "chrome-extension" not in r.url else None)
                    n0 = len(unmocked)
                    total = None
                    try:
                        page.goto(f"{base}/{pg}.html", wait_until="load", timeout=20000)
                        page.wait_for_timeout(1200)
                        if pg in APP_PAGES:
                            total = explore(page, pg, total, extra)
                        else:
                            total = merge(total, page.evaluate(MEASURE))
                        page.evaluate("window.scrollTo(0, 0)")
                        page.screenshot(path=str(ART / "screens" / f"{pg}_{vp}_{lang}_{args.scenario}.png"), full_page=True)
                    except Exception as e:  # keep going; record as failure
                        total = total or merge(None, {"overflow": 0, "small_tap": [], "small_font": [], "body_font": [], "clipped": [],
                                                      "no_name": [], "has_nav": False, "text": "", "empty_state": False,
                                                      "error_state": False, "risk_text": "",
                                                      "estimate_pills": {"disease": 0, "irrigation": 0, "gdd": 0, "fert": 0}})
                        errs.append("harness: " + str(e)[:80] + " ... " + str(e)[-260:])
                    page.close()
                    # aborted unmocked CDN requests surface as requestfailed; keep them out of console errors
                    errs = [e for e in errs if not any(u in e for u in unmocked[n0:])]
                    if unmocked[n0:]:  # Chromium's generic message for an aborted (unmocked) request has no URL
                        errs = [e for e in errs if "Failed to load resource: net::ERR_FAILED" not in e]
                    errs = [e for e in errs if "Service Worker registration blocked" not in e]
                    if args.scenario != "ok":  # the browser logs every 4xx/5xx response; those are expected here
                        errs = [e for e in errs if "Failed to load resource" not in e]

                    # content checks on the app pages
                    content = []
                    if pg in APP_PAGES:
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
                        if args.scenario == "empty" and not total["empty_state"]:
                            content.append("empty scenario: no empty-state message visible")
                        if args.scenario == "error" and not total["error_state"]:
                            content.append("error scenario: no Retry / error state visible")
                    content += extra
                    total.pop("texts", None)
                    results.append(dict(page=pg, viewport=vp, lang=lang, scenario=args.scenario, errors=errs,
                                        unmocked=unmocked[n0:], content=content, **total))
                ctx.close()
        browser.close()
    if srv:
        srv.shutdown()
    return results


def report(results, out_md):
    hard = 0
    lines = ["| page | viewport | lang | scenario | errors | overflow px | tap<44 | font<14 | p/li/input/label<16 | clipped | no name | content | nav |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    detail = []
    for r in results:
        bad = (bool(r["errors"]) or r["overflow"] > 1 or r["small_tap"] or r["body_font"] or r["clipped"]
               or r["no_name"] or r["small_font"] or r["content"])
        hard += 1 if bad else 0
        lines.append(f"| {r['page']} | {r['viewport']} | {r['lang']} | {r['scenario']} | {len(r['errors'])} | {max(r['overflow'], 0)} | "
                     f"{len(r['small_tap'])} | {len(r['small_font'])} | {len(r['body_font'])} | {len(r['clipped'])} | "
                     f"{len(r['no_name'])} | {len(r['content'])} | {'yes' if r['has_nav'] else 'no'} |")
        for key in ("errors", "small_tap", "small_font", "body_font", "clipped", "no_name", "content"):
            if r[key]:
                detail.append(f"- {r['page']} {r['viewport']} {r['lang']} {r['scenario']} {key} (worst 5 of {len(r[key])}): {r[key][:5]}")
    text = "# Browser check\n\n" + "\n".join(lines) + "\n\n## Offenders\n\n" + "\n".join(detail) + f"\n\nRows with a hard failure: {hard} of {len(results)}\n"
    out_md.write_text(text, encoding="utf-8")
    return hard


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages"); ap.add_argument("--viewport", choices=list(VIEWPORTS)); ap.add_argument("--lang")
    ap.add_argument("--scenario", choices=("ok", "empty", "error"), default="ok")
    ap.add_argument("--local", action="store_true"); ap.add_argument("--anon", action="store_true")
    ap.add_argument("--real-cdn", action="store_true"); ap.add_argument("--report", default=str(ART / "browser_report.md"))
    args = ap.parse_args()
    results = run(args)
    ART.mkdir(parents=True, exist_ok=True)
    (ART / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    hard = report(results, Path(args.report))
    print(f"{len(results)} runs, {hard} with hard failures; report: {args.report}")
    sys.exit(1 if hard else 0)


if __name__ == "__main__":
    main()
