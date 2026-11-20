"""Read-only production smoke test (GET only, no credentials sent).

python tests/e2e/prod_smoke.py [--out path]

Checks the Render API and the Netlify pages with plain GET requests (stdlib urllib, 30 s timeout,
2 retries because Render's free tier may be asleep for up to ~60 s). Prints counts and the newest
price date only, never row contents.

Netlify still serves the pre-merge code until the owner pushes, so new files (css/tailwind.css, sw.js)
are expected to answer 404 there; they are reported as NOTE, not as failures.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request

API = "https://guava-8wc7.onrender.com"
SITE = "https://guavaa.netlify.app"
PAGES = ["index", "login", "onboarding", "farm", "plan", "tasks", "observations", "inventory", "report", "sell-smart", "privacy"]
NEW_FILES = ["css/tailwind.css", "sw.js", "js/nav.js"]
UA = "SmartFarmerProdSmoke/1.0 (read-only GET)"


def get(url, retries=2, timeout=30):
    """Return (status, body_bytes, seconds). Retries on network errors and 5xx (cold start)."""
    last = (None, b"", 0.0)
    for attempt in range(retries + 1):
        t0 = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"}, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read(), time.time() - t0
        except urllib.error.HTTPError as e:
            last = (e.code, b"", time.time() - t0)
            if e.code < 500:
                return last
        except Exception as e:  # timeout, DNS, TLS
            last = (None, str(type(e).__name__).encode(), time.time() - t0)
        time.sleep(3)
    return last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    args = ap.parse_args()
    lines, failures = [], 0

    def log(s):
        print(s)
        lines.append(s)

    log("Production smoke test (GET only). Netlify still serves the pre-merge code until the owner pushes,")
    log("so new files (css/tailwind.css, sw.js, js/nav.js) are expected to be 404 there.")
    log(f"Run at {time.strftime('%Y-%m-%d %H:%M:%S %z')}")
    log("")

    for path in ("/docs", "/health"):
        s, _, sec = get(API + path)
        ok = s == 200
        failures += 0 if ok else 1
        log(f"{'OK  ' if ok else 'FAIL'} GET {API}{path} -> {s} ({sec:.1f}s)")

    s, body, sec = get(API + "/api/public/market-prices/guava")
    detail = ""
    ok = s == 200
    if ok:
        try:
            data = json.loads(body)
            mandis = data.get("mandis") or []
            rows = [p for m in mandis for p in (m.get("prices") or [])]
            dates = [m.get("trade_date") for m in mandis if m.get("trade_date")]
            has_fields = bool(mandis) and all(m.get("state") and m.get("market") and m.get("trade_date") for m in mandis) \
                and all(p.get("modal_per_kg") is not None and p.get("modal_per_quintal") is not None for p in rows)
            detail = (f"has_data={data.get('has_data')} mandis={len(mandis)} price_rows={len(rows)} "
                      f"newest_date={max(dates) if dates else None} fields_ok={has_fields}")
            ok = bool(data.get("has_data")) and has_fields
        except Exception as e:
            detail = f"not JSON ({type(e).__name__})"
            ok = False
    failures += 0 if ok else 1
    log(f"{'OK  ' if ok else 'FAIL'} GET {API}/api/public/market-prices/guava -> {s} ({sec:.1f}s) {detail}")

    log("")
    for page in PAGES:
        s, _, sec = get(f"{SITE}/{page}.html")
        ok = s == 200
        failures += 0 if ok else 1
        log(f"{'OK  ' if ok else 'FAIL'} GET {SITE}/{page}.html -> {s} ({sec:.1f}s)")
    log("")
    for path in NEW_FILES:
        s, _, _ = get(f"{SITE}/{path}", retries=0)
        note = "present" if s == 200 else "not deployed yet (expected before the push)"
        log(f"NOTE GET {SITE}/{path} -> {s} {note}")
    log("")
    log(f"Failures: {failures}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()