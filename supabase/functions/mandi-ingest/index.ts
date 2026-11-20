// mandi-ingest: saves today's guava mandi prices (Agmarknet / data.gov.in) into
// market_prices. Runs in an India region (x-region: ap-south-1) because
// data.gov.in does not answer Render's IPs. Called by pg_cron or by hand.
//
// Secrets: DATA_GOV_IN_API_KEY, MANDI_INGEST_TOKEN (set with `supabase secrets set`).
// Auth: header x-ingest-token must equal MANDI_INGEST_TOKEN (verify_jwt is off).
// Modes: ?mode=probe or body {"mode":"probe"} only tests reachability.

import {
  pickServiceKey,
  probe,
  realDeps,
  runIngestion,
  safeEqual,
} from "./ingest.ts";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export async function handler(req: Request): Promise<Response> {
  const expected = Deno.env.get("MANDI_INGEST_TOKEN") ?? "";
  if (!expected) {
    console.error("mandi-ingest: MANDI_INGEST_TOKEN not set");
    return json({ error: "server not configured" }, 500);
  }
  if (!safeEqual(req.headers.get("x-ingest-token") ?? "", expected)) {
    return json({ error: "unauthorized" }, 401);
  }

  let mode = new URL(req.url).searchParams.get("mode") ?? "";
  if (!mode && req.method === "POST") {
    try {
      const body = await req.json();
      if (body && typeof body.mode === "string") mode = body.mode;
    } catch { /* empty or non-JSON body means ingest mode */ }
  }

  const apiKey = (Deno.env.get("DATA_GOV_IN_API_KEY") ?? "").trim();
  if (mode === "probe") {
    return json(await probe(apiKey, Deno.env.get("SB_REGION") ?? null, realDeps));
  }

  const summary = await runIngestion({
    apiKey,
    supabaseUrl: Deno.env.get("SUPABASE_URL") ?? "",
    serviceKey: pickServiceKey(Deno.env),
  });
  return json(summary);
}

if (import.meta.main) Deno.serve(handler);
