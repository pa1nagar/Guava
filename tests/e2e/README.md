Browser check for all pages (360x800 + 1366x768, English + Hindi) with mocked Supabase and API.
Setup once: pip install playwright && playwright install chromium
Run: python tests/e2e/browser_check.py [--pages a,b] [--viewport 360x800] [--local] [--anon] [--real-cdn]; report goes to .agents/tasks/guava-polish/browser_report.md, exit 1 on a hard failure.
Scenarios: --scenario empty|error (empty and error states). The full run (no filters) also checks ?demo=1 on a production origin vs 127.0.0.1, sign-in library unreachable, Chart.js unreachable. Read-only live smoke: python tests/e2e/prod_smoke.py.
