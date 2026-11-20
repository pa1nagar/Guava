Browser check for all pages (360x800 + 1366x768, English + Hindi) with mocked Supabase and API.
Setup once: pip install playwright && playwright install chromium
Run: python tests/e2e/browser_check.py [--pages a,b] [--viewport 360x800] [--local] [--anon] [--real-cdn]; report goes to .agents/tasks/guava-polish/browser_report.md, exit 1 on a hard failure.
