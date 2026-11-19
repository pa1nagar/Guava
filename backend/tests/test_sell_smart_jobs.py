"""
test_sell_smart_jobs.py - post-ingestion job on an in-memory repository.
"""
import json
from datetime import date

from services.sell_smart import jobs
from tests.fake_sell_repo import FakeRepo, price_row

TODAY = date(2026, 11, 12)
USER = "11111111-1111-1111-1111-111111111111"
MH = "Maharashtra"


def _repo(pune_modal=5000, day="2026-11-12"):
    repo = FakeRepo()
    repo.prices = [
        price_row(MH, "Pune", "Pune", day, pune_modal, row_id="p1"),
        price_row(MH, "Nashik", "Nashik", day, 4200, row_id="p2"),
        price_row(MH, "Solapur", "Solapur", day, 3900, row_id="p3"),
        price_row(MH, "Mumbai", "Mumbai", day, 4600, row_id="p4"),
    ]
    return repo


def _alert(repo, target=45.0, direction="at_or_above", market="Pune"):
    return repo.create_alert(USER, {
        "state": MH, "district": None, "market_name": market,
        "target_rs_per_kg": target, "direction": direction,
        "is_active": True, "last_state": None,
    })


class TestQuality:
    def test_writes_quality_for_every_row_once(self):
        repo = _repo()
        s = jobs.run_post_ingestion(repo, TODAY)
        assert s["status"] == "ok"
        assert s["quality"]["assessed"] == 4
        assert set(repo.quality) == {"p1", "p2", "p3", "p4"}
        assert repo.quality["p1"]["last_modal"] == 5000
        again = jobs.run_post_ingestion(repo, TODAY)
        assert again["quality"]["assessed"] == 0  # nothing new, nothing changed

    def test_zero_price_is_stored_as_reject(self):
        repo = _repo()
        repo.prices.append(price_row(MH, "Nagpur", "Nagpur", "2026-11-12", 0, mn=0, mx=0, row_id="z1"))
        jobs.run_post_ingestion(repo, TODAY)
        assert repo.quality["z1"]["severity"] == "reject"
        assert "ZERO_PRICE" in repo.quality["z1"]["flags"]

    def test_late_correction_is_flagged_revised_and_stays_flagged(self):
        repo = _repo()
        jobs.run_post_ingestion(repo, TODAY)
        for r in repo.prices:
            if r["id"] == "p2":
                r["modal_price"] = 4300
        s = jobs.run_post_ingestion(repo, TODAY)
        assert s["quality"]["revised"] == 1
        rec = repo.quality["p2"]
        assert "REVISED" in rec["flags"] and rec["severity"] == "warn"
        assert rec["revision_count"] == 1 and rec["last_modal"] == 4300
        jobs.run_post_ingestion(repo, TODAY)
        assert "REVISED" in repo.quality["p2"]["flags"]
        assert repo.quality["p2"]["revision_count"] == 1


class TestAlerts:
    def test_fires_once_and_rerun_creates_no_duplicate(self):
        repo = _repo()
        a = _alert(repo)
        first = jobs.run_post_ingestion(repo, TODAY)
        assert first["alerts"]["fired"] == 1
        assert len(repo.notifications) == 1
        n = repo.notifications[0]
        assert n["user_id"] == USER and n["alert_id"] == a["id"] and n["kind"] == "price_alert"
        assert n["payload"]["price_per_kg"] == 50.0
        assert n["payload"]["trade_date"] == "2026-11-12"
        assert repo.alerts[a["id"]]["last_trigger_date"] == "2026-11-12"
        again = jobs.run_post_ingestion(repo, TODAY)
        assert again["alerts"]["fired"] == 0
        assert len(repo.notifications) == 1

    def test_state_lost_after_insert_does_not_duplicate_notification(self):
        repo = _repo()
        a = _alert(repo)
        jobs.run_post_ingestion(repo, TODAY)
        repo.alerts[a["id"]]["last_state"] = None  # simulate a failed state write
        repo.alerts[a["id"]]["last_trigger_date"] = None
        jobs.run_post_ingestion(repo, TODAY)
        assert len(repo.notifications) == 1

    def test_not_met_does_not_fire(self):
        repo = _repo()
        _alert(repo, target=60.0)
        s = jobs.run_post_ingestion(repo, TODAY)
        assert s["alerts"]["fired"] == 0 and repo.notifications == []

    def test_fires_again_only_after_price_leaves_and_recrosses(self):
        repo = _repo()
        a = _alert(repo)
        jobs.run_post_ingestion(repo, TODAY)
        repo.prices.append(price_row(MH, "Pune", "Pune", "2026-11-13", 4000, row_id="p5"))
        jobs.run_post_ingestion(repo, date(2026, 11, 13))
        assert len(repo.notifications) == 1
        assert json.loads(repo.alerts[a["id"]]["last_state"])["last_met"] is False
        repo.prices.append(price_row(MH, "Pune", "Pune", "2026-11-14", 5100, row_id="p6"))
        jobs.run_post_ingestion(repo, date(2026, 11, 14))
        assert len(repo.notifications) == 2

    def test_rejected_price_never_fires(self):
        repo = FakeRepo()
        repo.prices = [price_row(MH, "Pune", "Pune", "2026-11-12", 9000, mn=9500, mx=9600, row_id="bad")]
        _alert(repo)
        s = jobs.run_post_ingestion(repo, TODAY)
        assert s["alerts"]["fired"] == 0 and repo.notifications == []

    def test_stale_price_never_fires(self):
        repo = _repo(day="2026-11-01")
        _alert(repo)
        jobs.run_post_ingestion(repo, TODAY)
        assert repo.notifications == []

    def test_district_scope_uses_median_of_mandis(self):
        repo = _repo()
        repo.prices.append(price_row(MH, "Pune", "Pune Market 2", "2026-11-12", 4000, row_id="p7"))
        found = jobs.alert_price(
            jobs.annotate_with_stored(repo.prices, {}),
            {"state": MH, "district": "Pune", "market_name": None},
        )
        assert found == (45.0, date(2026, 11, 12))

    def test_deleted_alert_is_ignored(self):
        repo = _repo()
        a = _alert(repo)
        repo.soft_delete_alert(USER, a["id"])
        s = jobs.run_post_ingestion(repo, TODAY)
        assert s["alerts"]["checked"] == 0


class TestNeverRaises:
    def test_read_failure_returns_summary(self):
        repo = _repo()
        repo.fail = True
        s = jobs.run_post_ingestion(repo, TODAY)
        assert s["status"] == "read_failed"

    def test_empty_table_returns_summary(self):
        s = jobs.run_post_ingestion(FakeRepo(), TODAY)
        assert s["status"] == "empty"

    def test_failure_in_quality_write_is_reported(self):
        repo = _repo()
        _alert(repo)

        def boom(records):
            raise RuntimeError("write failed")

        repo.upsert_quality = boom
        s = jobs.run_post_ingestion(repo, TODAY)
        assert s["status"] == "quality_failed"
        assert s["alerts"] is not None

    def test_one_bad_alert_does_not_stop_the_others(self):
        repo = _repo()
        bad = _alert(repo)
        good = _alert(repo, market="Nashik", target=40.0)
        original = repo.set_alert_state

        def flaky(alert_id, last_state, last_trigger_date):
            if alert_id == bad["id"]:
                raise RuntimeError("boom")
            original(alert_id, last_state, last_trigger_date)

        repo.set_alert_state = flaky
        s = jobs.run_post_ingestion(repo, TODAY)
        assert s["alerts"]["errors"] == 1
        assert repo.alerts[good["id"]]["last_trigger_date"] == "2026-11-12"
