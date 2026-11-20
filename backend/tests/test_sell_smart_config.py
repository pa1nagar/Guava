"""Sell smart config: every threshold has a basis and matches the plan."""

from services.sell_smart import config as c


def test_every_threshold_has_basis():
    assert c.THRESHOLDS
    for name, t in c.THRESHOLDS.items():
        assert isinstance(t.get("basis"), str) and len(t["basis"].strip()) > 10, name
        assert "value" in t, name


def test_values_match_plan():
    assert c.OUTLIER_MODIFIED_Z == 3.5
    assert c.MIN_ROBUST_N == 3
    assert c.TREND_WINDOWS == (7, 14, 30)
    assert c.SEASONAL_MIN_SPAN_DAYS == 730
    assert c.SEASONAL_MIN_YEARS == 2
    assert c.MIN_TREND_DAYS == 7
    assert c.STALE_DAYS == 7
    assert c.QUINTAL_KG == 100


def test_threshold_dict_matches_constants():
    assert c.threshold_value("OUTLIER_MODIFIED_Z") == c.OUTLIER_MODIFIED_Z
    assert c.threshold_value("MIN_ROBUST_N") == c.MIN_ROBUST_N
    assert c.threshold_value("STALE_DAYS") == c.STALE_DAYS


def test_default_radius_equals_prices_router():
    from routers.prices import NEARBY_MAX_KM
    assert c.DEFAULT_RADIUS_KM == NEARBY_MAX_KM


CAP_NAMES = ("LOOKBACK_DAYS", "MAX_ROAD_KM_OVERRIDES", "MAX_FLAGGED_ROWS",
             "MAX_NOTIFICATIONS", "PAGE_SIZE", "MAX_PAGES")


def test_caps_are_in_thresholds_with_basis():
    for name in CAP_NAMES:
        assert name in c.THRESHOLDS, name
        assert c.THRESHOLDS[name]["value"] == getattr(c, name), name
        assert len(c.THRESHOLDS[name]["basis"].strip()) > 10, name
    assert c.LOOKBACK_DAYS == 2 * max(c.TREND_WINDOWS)


def test_modules_use_config_values_single_source():
    from routers import sell_smart as router
    from services.sell_smart import jobs, repo
    assert jobs.LOOKBACK_DAYS == c.LOOKBACK_DAYS
    assert repo.PAGE_SIZE == c.PAGE_SIZE
    assert repo.MAX_PAGES == c.MAX_PAGES
    assert router.MAX_ROAD_KM_OVERRIDES == c.MAX_ROAD_KM_OVERRIDES
    assert router.MAX_FLAGGED_ROWS == c.MAX_FLAGGED_ROWS
    assert router.MAX_NOTIFICATIONS == c.MAX_NOTIFICATIONS
