// Fetch + store helpers for the mandi-ingest Edge Function.
// Mirrors fetch_guava_records / run_ingestion in backend/services/mandi_prices.py.
// Every network call goes through an injected `fetchFn` so tests need no network.

import { CONFLICT_COLUMNS, parseRecords, type PriceRow } from "./parse.ts";

export const RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070";
export const API_URL = `https://api.data.gov.in/resource/${RESOURCE_ID}`;
export const USER_AGENT = "SmartFarmerGuava/1.0 (mandi price sync)";
export const PAGE_LIMIT = 100;
export const MAX_PAGES = 100;
export const PAGE_TIMEOUT_MS = 20_000;
export const PROBE_TIMEOUT_MS = 15_000;
export const FETCH_ATTEMPTS = 3;
export const RETRY_BACKOFF_MS = 3_000;
export const RETRY_STATUSES = [502, 503, 504];
export const WALL_BUDGET_MS = 110_000;
export const UPSERT_CHUNK = 200;

export type FetchFn = (
  input: string,
  init?: RequestInit,
) => Promise<Response>;

export interface Deps {
  fetchFn: FetchFn;
  sleep: (ms: number) => Promise<void>;
  now: () => number;
}

export const realDeps: Deps = {
  fetchFn: (input, init) => fetch(input, init),
  sleep: (ms) => new Promise((r) => setTimeout(r, ms)),
  now: () => Date.now(),
};

export class MandiFetchError extends Error {}

function scrub(message: string, apiKey: string): string {
  let out = message;
  if (apiKey) out = out.split(apiKey).join("***");
  return out.slice(0, 200);
}

function pageUrl(apiKey: string, limit: number, offset: number): string {
  const p = new URLSearchParams({
    "api-key": apiKey,
    format: "json",
    limit: String(limit),
    offset: String(offset),
    "filters[commodity]": "Guava",
  });
  return `${API_URL}?${p.toString()}`;
}

async function getPage(
  deps: Deps,
  apiKey: string,
  offset: number,
  startedAt: number,
): Promise<Response> {
  let lastError = "no attempt made";
  for (let attempt = 1; attempt <= FETCH_ATTEMPTS; attempt++) {
    if (deps.now() - startedAt > WALL_BUDGET_MS) {
      throw new MandiFetchError("time budget exceeded");
    }
    try {
      const resp = await deps.fetchFn(pageUrl(apiKey, PAGE_LIMIT, offset), {
        headers: { "User-Agent": USER_AGENT, Accept: "application/json" },
        signal: AbortSignal.timeout(PAGE_TIMEOUT_MS),
      });
      if (!RETRY_STATUSES.includes(resp.status)) return resp;
      await resp.body?.cancel();
      lastError = `HTTP ${resp.status} from data.gov.in`;
    } catch (exc) {
      const e = exc as Error;
      lastError = `request failed: ${e?.name ?? "Error"}: ${
        scrub(String(e?.message ?? e), apiKey)
      }`;
    }
    if (attempt < FETCH_ATTEMPTS) {
      await deps.sleep(RETRY_BACKOFF_MS * attempt);
    }
  }
  throw new MandiFetchError(`${lastError} (after ${FETCH_ATTEMPTS} attempts)`);
}

/** All guava records currently in the feed. Throws MandiFetchError. */
export async function fetchGuavaRecords(
  apiKey: string,
  deps: Deps = realDeps,
): Promise<Record<string, unknown>[]> {
  const startedAt = deps.now();
  const records: Record<string, unknown>[] = [];
  let offset = 0;
  for (let page = 0; page < MAX_PAGES; page++) {
    const resp = await getPage(deps, apiKey, offset, startedAt);
    if (resp.status === 400) {
      throw new MandiFetchError("HTTP 400 from data.gov.in (bad request parameters)");
    }
    if (resp.status === 403) {
      throw new MandiFetchError(
        "HTTP 403 from data.gov.in (API key missing, invalid or not allowed)",
      );
    }
    if (resp.status !== 200) {
      throw new MandiFetchError(`HTTP ${resp.status} from data.gov.in`);
    }
    let payload: unknown;
    try {
      payload = await resp.json();
    } catch {
      throw new MandiFetchError("response was not valid JSON");
    }
    const batch = payload && typeof payload === "object"
      ? (payload as { records?: unknown }).records
      : undefined;
    if (!Array.isArray(batch)) {
      throw new MandiFetchError("response has no 'records' list (format changed?)");
    }
    for (const r of batch) {
      if (r && typeof r === "object" && !Array.isArray(r)) {
        records.push(r as Record<string, unknown>);
      }
    }
    // The server may return fewer rows than asked; page until an empty batch.
    if (batch.length === 0) break;
    offset += batch.length;
  }
  return records;
}

export interface Summary {
  status: string;
  fetched: number;
  parsed: number;
  skipped: number;
  upserted: number;
  error?: string;
}

/** Pick a server-side key from the env Supabase injects into functions. */
export function pickServiceKey(
  env: { get(name: string): string | undefined },
): string {
  const legacy = (env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "").trim();
  if (legacy) return legacy;
  try {
    const keys = JSON.parse(env.get("SUPABASE_SECRET_KEYS") ?? "{}");
    const first = Object.values(keys)[0];
    return typeof first === "string" ? first.trim() : "";
  } catch {
    return "";
  }
}

export async function upsertRows(
  rows: PriceRow[],
  supabaseUrl: string,
  serviceKey: string,
  fetchFn: FetchFn,
): Promise<number> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    apikey: serviceKey,
    Prefer: "resolution=merge-duplicates,return=minimal",
  };
  if (!serviceKey.startsWith("sb_secret_")) {
    headers["Authorization"] = `Bearer ${serviceKey}`;
  }
  const url = `${supabaseUrl.replace(/\/+$/, "")}/rest/v1/market_prices?on_conflict=${
    encodeURIComponent(CONFLICT_COLUMNS)
  }`;
  let stored = 0;
  for (let i = 0; i < rows.length; i += UPSERT_CHUNK) {
    const chunk = rows.slice(i, i + UPSERT_CHUNK);
    const resp = await fetchFn(url, {
      method: "POST",
      headers,
      body: JSON.stringify(chunk),
    });
    if (!resp.ok) {
      await resp.body?.cancel();
      throw new Error(`HTTP ${resp.status}`);
    }
    await resp.body?.cancel();
    stored += chunk.length;
  }
  return stored;
}

export interface IngestConfig {
  apiKey: string;
  supabaseUrl: string;
  serviceKey: string;
  nowIso?: string;
}

/** Fetch, parse and store. Never throws; returns a summary like run_ingestion. */
export async function runIngestion(
  cfg: IngestConfig,
  deps: Deps = realDeps,
  log: (line: string) => void = console.log,
): Promise<Summary> {
  const summary: Summary = {
    status: "ok",
    fetched: 0,
    parsed: 0,
    skipped: 0,
    upserted: 0,
  };
  if (!cfg.apiKey) {
    log("mandi-ingest status=no_api_key");
    summary.status = "no_api_key";
    return summary;
  }

  let records: Record<string, unknown>[];
  try {
    records = await fetchGuavaRecords(cfg.apiKey, deps);
  } catch (exc) {
    const reason = scrub(String((exc as Error).message), cfg.apiKey);
    log(`mandi-ingest status=fetch_failed error=${reason}`);
    summary.status = "fetch_failed";
    summary.error = reason;
    return summary;
  }
  summary.fetched = records.length;
  if (records.length === 0) {
    log("mandi-ingest status=empty (no guava records in the feed)");
    summary.status = "empty";
    return summary;
  }

  const { rows, skipped } = parseRecords(
    records,
    cfg.nowIso ?? new Date().toISOString(),
  );
  summary.parsed = rows.length;
  summary.skipped = skipped;
  if (rows.length === 0) {
    log(
      `mandi-ingest status=unusable fetched=${records.length} first_record_keys=${
        JSON.stringify(Object.keys(records[0]).sort())
      }`,
    );
    summary.status = "unusable";
    return summary;
  }

  try {
    summary.upserted = await upsertRows(
      rows,
      cfg.supabaseUrl,
      cfg.serviceKey,
      deps.fetchFn,
    );
  } catch (exc) {
    const reason = (exc as Error).message;
    log(`mandi-ingest status=store_failed error=${reason}`);
    summary.status = "store_failed";
    summary.error = reason;
    return summary;
  }
  log(`mandi-ingest status=ok ${JSON.stringify(summary)}`);
  return summary;
}

export interface ProbeResult {
  mode: "probe";
  reachable: boolean;
  http_status: number | null;
  elapsed_ms: number;
  region: string | null;
  api_key_present: boolean;
  error: string | null;
}

/** One limit=1 request to see whether data.gov.in answers from this region. */
export async function probe(
  apiKey: string,
  region: string | null,
  deps: Deps = realDeps,
): Promise<ProbeResult> {
  const started = deps.now();
  const result: ProbeResult = {
    mode: "probe",
    reachable: false,
    http_status: null,
    elapsed_ms: 0,
    region,
    api_key_present: apiKey.length > 0,
    error: null,
  };
  try {
    const resp = await deps.fetchFn(pageUrl(apiKey, 1, 0), {
      headers: { "User-Agent": USER_AGENT, Accept: "application/json" },
      signal: AbortSignal.timeout(PROBE_TIMEOUT_MS),
    });
    await resp.body?.cancel();
    result.http_status = resp.status;
    result.reachable = true; // the server answered; status tells key problems
  } catch (exc) {
    const e = exc as Error;
    result.error = `${e?.name ?? "Error"}: ${scrub(String(e?.message ?? e), apiKey)}`;
  }
  result.elapsed_ms = deps.now() - started;
  return result;
}

/** Constant-time string comparison. */
export function safeEqual(a: string, b: string): boolean {
  const enc = new TextEncoder();
  const x = enc.encode(a), y = enc.encode(b);
  let diff = x.length ^ y.length;
  const n = Math.max(x.length, y.length);
  for (let i = 0; i < n; i++) diff |= (x[i] ?? 0) ^ (y[i] ?? 0);
  return diff === 0;
}
