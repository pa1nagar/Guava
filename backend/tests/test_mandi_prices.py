"""
test_mandi_prices.py — Ingestion parser, fetch and upsert for guava mandi prices.

No live calls: HTTP is mocked with httpx.MockTransport and the database is a
recording fake. The sample file follows the documented data.gov.in response
shape (resource 9ef84268-d588-465a-a308-a864a43d0070).
"""

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from services import mandi_prices as mp

SAMPLE = json.loads(
    (Path(__file__).parent / "fixtures" / "mandi_guava_sample.json").read_text(encoding="utf-8")
)


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _page(request: httpx.Request) -> dict:
    # Whole sample on the first page, nothing after (like a real paged feed).
    return SAMPLE if request.url.params.get("offset") == "0" else {"records": []}


def _ok_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=_page(request))


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch):
    """Retries must not slow the suite down."""
    monkeypatch.setattr(mp.time, "sleep", lambda s: None)


class FakeDb:
    """Records upserts; keeps rows keyed by the conflict columns like Postgres."""

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.store: dict[tuple, dict] = {}
        self.calls = 0

    def table(self, name):
        assert name == "market_prices"
        return self

    def upsert(self, rows, on_conflict=None):
        assert on_conflict == mp.CONFLICT_COLUMNS
        if self.fail:
            raise RuntimeError("db down")
        self.calls += 1
        cols = on_conflict.split(",")
        for r in rows:
            self.store[tuple(r[c] for c in cols)] = r
        return self

    def execute(self):
        return MagicMock()


# ── parse_record ──────────────────────────────────────────────────────────────

class TestParseRecord:
    def test_maps_fields(self):
        row = mp.parse_record(SAMPLE["records"][0])
        assert row["state"] == "Madhya Pradesh"
        assert row["district"] == "Indore"
        assert row["market_name"] == "Indore"
        assert row["commodity"] == "guava"
        assert row["variety"] == "Other"
        assert row["grade"] == "FAQ"
        assert (row["min_price"], row["max_price"], row["modal_price"]) == (3000.0, 4500.0, 3800.0)
        assert row["price"] == 3800.0
        assert row["unit"] == "Rs/Quintal"
        assert row["arrival_date"] == "2026-11-10"
        assert row["observed_at"].startswith("2026-11-10")
        assert row["source_name"] == "Agmarknet / data.gov.in"
        assert row["fetched_at"]

    def test_missing_variety_and_grade_become_empty_strings(self):
        row = mp.parse_record(SAMPLE["records"][2])
        assert row["variety"] == "" and row["grade"] == ""

    def test_non_guava_is_ignored(self):
        assert mp.parse_record(SAMPLE["records"][5]) is None

    def test_unreadable_modal_price_is_skipped(self):
        assert mp.parse_record(SAMPLE["records"][4]) is None

    def test_unreadable_date_is_skipped(self):
        assert mp.parse_record(SAMPLE["records"][6]) is None

    def test_field_name_case_changes_are_tolerated(self):
        raw = {k.title().replace("_", "_"): v for k, v in SAMPLE["records"][0].items()}
        assert "Modal_Price" in raw
        assert mp.parse_record(raw)["modal_price"] == 3800.0

    def test_renamed_required_field_is_skipped_not_crashed(self):
        raw = dict(SAMPLE["records"][0])
        raw["mandi"] = raw.pop("market")
        assert mp.parse_record(raw) is None

    def test_negative_price_rejected(self):
        raw = dict(SAMPLE["records"][0], modal_price="-5")
        assert mp.parse_record(raw) is None

    def test_non_dict_input(self):
        assert mp.parse_record("oops") is None


class TestParseRecords:
    def test_duplicates_collapse_last_wins_and_bad_rows_counted(self):
        rows, skipped = mp.parse_records(SAMPLE["records"])
        # 7 records: 1 duplicate pair (Pune), 1 non-guava, 1 bad modal, 1 bad date.
        assert len(rows) == 3
        assert skipped == 3
        pune = next(r for r in rows if r["market_name"] == "Pune")
        assert pune["modal_price"] == 5100.0


# ── fetch_guava_records ───────────────────────────────────────────────────────

class TestFetch:
    def test_sends_documented_query(self):
        seen = {}

        def handler(request):
            seen.update(dict(request.url.params))
            seen["path"] = request.url.path
            return httpx.Response(200, json={"records": []})

        mp.fetch_guava_records("KEY", _client(handler))
        assert seen["path"].endswith("/9ef84268-d588-465a-a308-a864a43d0070")
        assert seen["api-key"] == "KEY"
        assert seen["format"] == "json"
        assert seen["filters[commodity]"] == "Guava"

    def test_paginates_until_short_page(self, monkeypatch):
        monkeypatch.setattr(mp, "PAGE_LIMIT", 2)
        pages = []

        def handler(request):
            offset = int(request.url.params["offset"])
            pages.append(offset)
            data = SAMPLE["records"][offset : offset + 2]
            return httpx.Response(200, json={"records": data})

        out = mp.fetch_guava_records("KEY", _client(handler))
        assert pages == [0, 2, 4, 6, 7]
        assert len(out) == len(SAMPLE["records"])

    def test_retries_timeout_and_502_then_succeeds(self):
        attempts = []

        def handler(request):
            attempts.append(1)
            if len(attempts) == 1:
                raise httpx.ReadTimeout("slow")
            if len(attempts) == 2:
                return httpx.Response(502)
            return httpx.Response(200, json=_page(request))

        out = mp.fetch_guava_records("K", _client(handler))
        assert len(out) == len(SAMPLE["records"])
        assert len(attempts) >= 3

    def test_gives_up_after_fetch_attempts(self):
        attempts = []

        def handler(request):
            attempts.append(1)
            return httpx.Response(502)

        with pytest.raises(mp.MandiFetchError, match="502"):
            mp.fetch_guava_records("K", _client(handler))
        assert len(attempts) == mp.FETCH_ATTEMPTS

    def test_403_and_500_are_not_retried(self):
        for code in (403, 500):
            attempts = []

            def handler(request, code=code):
                attempts.append(1)
                return httpx.Response(code)

            with pytest.raises(mp.MandiFetchError):
                mp.fetch_guava_records("K", _client(handler))
            assert len(attempts) == 1

    def test_default_client_sends_custom_user_agent(self, monkeypatch):
        # data.gov.in stalls the default python-httpx User-Agent (verified live).
        captured = {}
        real_client = httpx.Client

        def fake_client(*args, **kwargs):
            captured["headers"] = kwargs.get("headers")
            return real_client(transport=httpx.MockTransport(_ok_handler))

        monkeypatch.setattr(mp.httpx, "Client", fake_client)
        mp.fetch_guava_records("K")
        assert captured["headers"]["User-Agent"] == mp.USER_AGENT
        assert "httpx" not in mp.USER_AGENT.lower()

    def test_http_error_raises(self):
        with pytest.raises(mp.MandiFetchError):
            mp.fetch_guava_records("K", _client(lambda r: httpx.Response(403)))

    @pytest.mark.parametrize("code,word", [(400, "400"), (403, "403")])
    def test_explicit_400_and_403_messages(self, code, word):
        with pytest.raises(mp.MandiFetchError, match=word):
            mp.fetch_guava_records("K", _client(lambda r: httpx.Response(code)))

    def test_server_page_cap_below_limit_still_paginates(self):
        calls = []

        def handler(request):
            offset = int(request.url.params["offset"])
            calls.append(offset)
            return httpx.Response(200, json={"records": SAMPLE["records"][offset : offset + 3]})

        out = mp.fetch_guava_records("K", _client(handler))
        assert len(out) == len(SAMPLE["records"]) and calls == [0, 3, 6, 7]

    def test_network_error_raises(self):
        def handler(request):
            raise httpx.ConnectError("boom")

        with pytest.raises(mp.MandiFetchError):
            mp.fetch_guava_records("K", _client(handler))

    def test_invalid_json_raises(self):
        with pytest.raises(mp.MandiFetchError):
            mp.fetch_guava_records("K", _client(lambda r: httpx.Response(200, text="<html>")))

    def test_payload_without_records_raises(self):
        with pytest.raises(mp.MandiFetchError):
            mp.fetch_guava_records("K", _client(lambda r: httpx.Response(200, json={"error": "x"})))


# ── run_ingestion ─────────────────────────────────────────────────────────────

class TestRunIngestion:
    def test_populates_market_prices_from_sample(self):
        db = FakeDb()
        summary = mp.run_ingestion(db=db, client=_client(_ok_handler), api_key="KEY")
        assert summary["status"] == "ok"
        assert summary["fetched"] == 7
        assert summary["parsed"] == 3
        assert summary["skipped"] == 3
        assert summary["upserted"] == 3
        assert {r["market_name"] for r in db.store.values()} == {"Indore", "Ujjain", "Pune"}

    def test_rerun_does_not_duplicate(self):
        db = FakeDb()
        mp.run_ingestion(db=db, client=_client(_ok_handler), api_key="KEY")
        mp.run_ingestion(db=db, client=_client(_ok_handler), api_key="KEY")
        assert len(db.store) == 3
        assert db.calls == 2

    def test_no_api_key_skips_without_calling_out(self, monkeypatch):
        monkeypatch.delenv("DATA_GOV_IN_API_KEY", raising=False)

        def handler(request):
            raise AssertionError("must not call the network")

        summary = mp.run_ingestion(db=FakeDb(), client=_client(handler))
        assert summary["status"] == "no_api_key"

    def test_api_key_read_from_env(self, monkeypatch):
        monkeypatch.setenv("DATA_GOV_IN_API_KEY", "FROM_ENV")
        keys = []

        def handler(request):
            keys.append(request.url.params["api-key"])
            return httpx.Response(200, json=_page(request))

        mp.run_ingestion(db=FakeDb(), client=_client(handler))
        assert set(keys) == {"FROM_ENV"}

    def test_fetch_failure_is_reported_not_raised(self):
        summary = mp.run_ingestion(
            db=FakeDb(), client=_client(lambda r: httpx.Response(500)), api_key="K"
        )
        assert summary["status"] == "fetch_failed"

    def test_empty_feed(self):
        db = FakeDb()
        summary = mp.run_ingestion(
            db=db, client=_client(lambda r: httpx.Response(200, json={"records": []})), api_key="K"
        )
        assert summary["status"] == "empty"
        assert db.store == {}

    def test_changed_fields_report_unusable(self):
        changed = {"records": [{"mandi": "X", "price": "10", "commodity": "Guava"}]}
        db = FakeDb()
        summary = mp.run_ingestion(
            db=db, client=_client(lambda r: httpx.Response(200, json=changed)), api_key="K"
        )
        assert summary["status"] == "unusable"
        assert db.store == {}

    def test_store_failure_is_reported_not_raised(self):
        summary = mp.run_ingestion(
            db=FakeDb(fail=True), client=_client(_ok_handler), api_key="K"
        )
        assert summary["status"] == "store_failed"


# ── helpers ───────────────────────────────────────────────────────────────────

class TestHelpers:
    def test_per_kg(self):
        assert mp.per_kg(3800) == 38.0
        assert mp.per_kg(None) is None

    def test_is_stale_boundary(self):
        today = date(2026, 11, 20)
        assert mp.is_stale(date(2026, 11, 13), today) is False   # exactly 7 days
        assert mp.is_stale(date(2026, 11, 12), today) is True

    def test_summarise_saved_prices(self):
        rows = [
            {"arrival_date": "2026-11-10", "modal_price": 3800},
            {"arrival_date": "2026-11-10", "modal_price": 3400},
            {"arrival_date": "2026-12-01", "modal_price": 2000},
            {"arrival_date": "bad", "modal_price": 1},
        ]
        s = mp.summarise_saved_prices(rows, 11)
        assert s["distinct_days"] == 2
        assert s["first_date"] == "2026-11-10" and s["last_date"] == "2026-12-01"
        assert s["harvest_month_days"] == 1
        assert s["harvest_month_avg_quintal"] == 3600.0

    def test_summarise_empty(self):
        s = mp.summarise_saved_prices([], 7)
        assert s["distinct_days"] == 0 and s["harvest_month_avg_quintal"] is None
