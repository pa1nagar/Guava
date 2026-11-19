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
