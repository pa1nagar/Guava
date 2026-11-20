// Pure parsing of data.gov.in guava records. No I/O.
// Mirrors backend/services/mandi_prices.py (parse_record / parse_records).
// backend/tests/test_mandi_edge_parity.py and parse_test.ts compare both
// implementations against backend/tests/fixtures/mandi_edge_parity.json.

export const SOURCE_NAME = "Agmarknet / data.gov.in";
export const COMMODITY = "guava";
export const UNIT = "Rs/Quintal";
export const CONFLICT_COLUMNS =
  "source_name,state,district,market_name,commodity,variety,grade,arrival_date";

const REQUIRED_FIELDS = ["state", "market", "arrival_date", "modal_price"];

export interface PriceRow {
  source_name: string;
  state: string;
  district: string;
  market_name: string;
  commodity: string;
  variety: string;
  grade: string;
  unit: string;
  min_price: number | null;
  max_price: number | null;
  modal_price: number;
  price: number;
  arrival_date: string;
  observed_at: string;
  fetched_at: string;
}

export function normKey(key: unknown): string {
  return String(key).trim().toLowerCase().replace(/ /g, "_");
}

const NUMBER_RE = /^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/;

/** Non-negative number, or null for blank / non-numeric / negative. */
export function parsePrice(value: unknown): number | null {
  if (value === null || value === undefined) return null;
  const text = String(value).trim().replace(/,/g, "");
  if (!text || ["NA", "N/A", "NULL", "-"].includes(text.toUpperCase())) {
    return null;
  }
  if (!NUMBER_RE.test(text)) return null;
  const n = Number(text);
  if (!Number.isFinite(n) || n < 0) return null;
  return n;
}

/** DD/MM/YYYY, YYYY-MM-DD or DD-MM-YYYY -> YYYY-MM-DD, or null. */
export function parseDate(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  const text = String(value).trim();
  let d: string, m: string, y: string;
  let match = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(text);
  if (match) {
    [, d, m, y] = match;
  } else if ((match = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(text))) {
    [, y, m, d] = match;
  } else if ((match = /^(\d{1,2})-(\d{1,2})-(\d{4})$/.exec(text))) {
    [, d, m, y] = match;
  } else {
    return null;
  }
  const year = Number(y), month = Number(m), day = Number(d);
  if (year < 1 || month < 1 || month > 12 || day < 1) return null;
  const daysInMonth = new Date(Date.UTC(2000 + (year % 400), month, 0))
    .getUTCDate(); // year % 400 keeps the leap-year rule, avoids 0-99 quirks
  if (day > daysInMonth) return null;
  return `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}-${
    String(day).padStart(2, "0")
  }`;
}

function optText(v: unknown): string {
  // Python: str(value or "").strip()
  return !v ? "" : String(v).trim();
}

/** One feed record -> market_prices row, or null if unusable. */
export function parseRecord(
  raw: unknown,
  fetchedAtIso: string,
): PriceRow | null {
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
    return null;
  }
  const rec: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
    rec[normKey(k)] = v;
  }

  if (String(rec["commodity"] ?? "").trim().toLowerCase() !== COMMODITY) {
    return null;
  }
  for (const field of REQUIRED_FIELDS) {
    const v = rec[field];
    if (v === null || v === undefined || v === "") return null;
  }

  const date = parseDate(rec["arrival_date"]);
  const modal = parsePrice(rec["modal_price"]);
  if (date === null || modal === null) return null;

  return {
    source_name: SOURCE_NAME,
    state: String(rec["state"]).trim(),
    district: optText(rec["district"]),
    market_name: String(rec["market"]).trim(),
    commodity: COMMODITY,
    variety: optText(rec["variety"]),
    grade: optText(rec["grade"]),
    unit: UNIT,
    min_price: parsePrice(rec["min_price"]),
    max_price: parsePrice(rec["max_price"]),
    modal_price: modal,
    price: modal,
    arrival_date: date,
    observed_at: `${date}T00:00:00+05:30`,
    fetched_at: fetchedAtIso,
  };
}

/** Parse and de-duplicate by CONFLICT_COLUMNS (last wins). */
export function parseRecords(
  records: unknown[],
  fetchedAtIso: string,
): { rows: PriceRow[]; skipped: number } {
  const keyed = new Map<string, PriceRow>();
  let skipped = 0;
  const cols = CONFLICT_COLUMNS.split(",") as (keyof PriceRow)[];
  for (const raw of records) {
    const row = parseRecord(raw, fetchedAtIso);
    if (row === null) {
      skipped++;
      continue;
    }
    keyed.set(JSON.stringify(cols.map((c) => row[c])), row);
  }
  return { rows: [...keyed.values()], skipped };
}
