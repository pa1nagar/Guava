import { assertEquals } from "jsr:@std/assert@1";
import { parseDate, parsePrice, parseRecords } from "./parse.ts";
import {
  type Deps,
  fetchGuavaRecords,
  probe,
  runIngestion,
  safeEqual,
  upsertRows,
} from "./ingest.ts";

const fixture = JSON.parse(
  Deno.readTextFileSync(
    new URL("../../../backend/tests/fixtures/mandi_edge_parity.json", import.meta.url),
  ),
);

Deno.test("parseRecords matches the Python-generated expected rows", () => {
  const { rows, skipped } = parseRecords(fixture.records, fixture.fetched_at);
  assertEquals(rows, fixture.expected_rows);
  assertEquals(skipped, fixture.expected_skipped);
});

Deno.test("parsePrice", () => {
  assertEquals(parsePrice("1,500"), 1500);
  assertEquals(parsePrice(" 2600.5 "), 2600.5);
  assertEquals(parsePrice("0"), 0);
  for (const v of ["NA", "n/a", "NULL", "-", "", "  ", "-5", "abc", "NaN", null, undefined]) {
    assertEquals(parsePrice(v), null, String(v));
  }
});

Deno.test("parseDate", () => {
  assertEquals(parseDate("09/11/2026"), "2026-11-09");
  assertEquals(parseDate("9/1/2026"), "2026-01-09");
  assertEquals(parseDate("2026-11-09"), "2026-11-09");
  assertEquals(parseDate("09-11-2026"), "2026-11-09");
  assertEquals(parseDate("29/02/2024"), "2024-02-29");
  assertEquals(parseDate("29/02/2026"), null);
  assertEquals(parseDate("31/04/2026"), null);
  assertEquals(parseDate("not a date"), null);
  assertEquals(parseDate(null), null);
});

function fakeDeps(responses: (Response | Error)[]): Deps & { calls: string[]; sleeps: number[] } {
  const calls: string[] = [];
  const sleeps: number[] = [];
  return {
    calls,
    sleeps,
    fetchFn: (url) => {
      calls.push(url);
      const next = responses.shift();
      if (!next) throw new Error("unexpected extra fetch");
      return next instanceof Error ? Promise.reject(next) : Promise.resolve(next);
    },
    sleep: (ms) => {
      sleeps.push(ms);
      return Promise.resolve();
    },
    now: () => 0,
  };
}

const page = (records: unknown[], status = 200) =>
  new Response(JSON.stringify({ records }), { status });

Deno.test("retries a 503 then succeeds and stops on an empty page", async () => {
  const deps = fakeDeps([
    new Response("", { status: 503 }),
    page([{ commodity: "Guava" }]),
    page([]),
  ]);
  const recs = await fetchGuavaRecords("KEY", deps);
  assertEquals(recs.length, 1);
  assertEquals(deps.sleeps, [3000]);
  assertEquals(deps.calls.length, 3);
  assertEquals(deps.calls[2].includes("offset=1"), true);
});

Deno.test("403 fails at once with the Python wording and no retry", async () => {
  const deps = fakeDeps([new Response("", { status: 403 })]);
  const summary = await runIngestion(
    { apiKey: "SECRETKEY", supabaseUrl: "https://x.supabase.co", serviceKey: "k" },
    deps,
    () => {},
  );
  assertEquals(summary.status, "fetch_failed");
  assertEquals(
    summary.error,
    "HTTP 403 from data.gov.in (API key missing, invalid or not allowed)",
  );
  assertEquals(deps.calls.length, 1);
});

Deno.test("network errors are retried 3 times and the key is stripped", async () => {
  const deps = fakeDeps([
    new Error("connect SECRETKEY failed"),
    new Error("boom"),
    new Error("boom"),
  ]);
  const summary = await runIngestion(
    { apiKey: "SECRETKEY", supabaseUrl: "https://x.supabase.co", serviceKey: "k" },
    deps,
    () => {},
  );
  assertEquals(summary.status, "fetch_failed");
  assertEquals(summary.error?.includes("SECRETKEY"), false);
  assertEquals(summary.error?.endsWith("(after 3 attempts)"), true);
  assertEquals(deps.sleeps, [3000, 6000]);
});

Deno.test("no api key", async () => {
  const lines: string[] = [];
  const summary = await runIngestion(
    { apiKey: "", supabaseUrl: "", serviceKey: "" },
    fakeDeps([]),
    (l) => lines.push(l),
  );
  assertEquals(summary.status, "no_api_key");
  assertEquals(lines, ["mandi-ingest status=no_api_key"]);
});

Deno.test("full run upserts parsed rows with the conflict key", async () => {
  const deps = fakeDeps([
    page([
      { state: "A", market: "M", commodity: "Guava", arrival_date: "01/11/2026", modal_price: "10" },
      { commodity: "Banana" },
    ]),
    page([]),
    new Response(null, { status: 201 }),
  ]);
  const summary = await runIngestion(
    {
      apiKey: "KEY",
      supabaseUrl: "https://x.supabase.co/",
      serviceKey: "sb_secret_abc",
      nowIso: "2026-11-20T00:00:00+00:00",
    },
    deps,
    () => {},
  );
  assertEquals(summary, { status: "ok", fetched: 2, parsed: 1, skipped: 1, upserted: 1 });
  assertEquals(
    deps.calls[2],
    "https://x.supabase.co/rest/v1/market_prices?on_conflict=source_name%2Cstate%2Cdistrict%2Cmarket_name%2Ccommodity%2Cvariety%2Cgrade%2Carrival_date",
  );
});

Deno.test("upsert sends Authorization only for non sb_secret_ keys", async () => {
  const seen: Record<string, string>[] = [];
  const f = (_u: string, init?: RequestInit) => {
    seen.push(init?.headers as Record<string, string>);
    return Promise.resolve(new Response(null, { status: 201 }));
  };
  const row = parseRecords(fixture.records, fixture.fetched_at).rows.slice(0, 1);
  await upsertRows(row, "https://x.supabase.co", "sb_secret_abc", f);
  await upsertRows(row, "https://x.supabase.co", "eyLegacy", f);
  assertEquals("Authorization" in seen[0], false);
  assertEquals(seen[0].apikey, "sb_secret_abc");
  assertEquals(seen[1].Authorization, "Bearer eyLegacy");
  assertEquals(seen[1].Prefer, "resolution=merge-duplicates,return=minimal");
});

Deno.test("store failure reports only the HTTP status", async () => {
  const deps = fakeDeps([
    page([{ state: "A", market: "M", commodity: "Guava", arrival_date: "01/11/2026", modal_price: "10" }]),
    page([]),
    new Response("secret body", { status: 401 }),
  ]);
  const summary = await runIngestion(
    { apiKey: "KEY", supabaseUrl: "https://x.supabase.co", serviceKey: "k" },
    deps,
    () => {},
  );
  assertEquals(summary.status, "store_failed");
  assertEquals(summary.error, "HTTP 401");
});

Deno.test("probe reports unreachable on a network error", async () => {
  const deps = fakeDeps([new Error("timed out")]);
  const r = await probe("KEY", "ap-south-1", deps);
  assertEquals(r.reachable, false);
  assertEquals(r.http_status, null);
  assertEquals(r.region, "ap-south-1");
  assertEquals(r.api_key_present, true);
  assertEquals(typeof r.error, "string");
});

Deno.test("probe reports reachable with the status and never the key", async () => {
  const deps = fakeDeps([new Response("{}", { status: 403 })]);
  const r = await probe("KEY", null, deps);
  assertEquals(r.reachable, true);
  assertEquals(r.http_status, 403);
  assertEquals(JSON.stringify(r).includes("KEY\""), false);
});

Deno.test("safeEqual", () => {
  assertEquals(safeEqual("abc", "abc"), true);
  assertEquals(safeEqual("abc", "abd"), false);
  assertEquals(safeEqual("abc", "abcd"), false);
  assertEquals(safeEqual("", "x"), false);
});
