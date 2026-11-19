"""
test_geo_aliases.py — Name normalisation, aliases and mandi district coordinates.
"""
import pytest

from services import geo
from services.geo import (
    canonical_district,
    canonical_state,
    get_coordinates,
    get_exact_district_coordinates,
    haversine_km,
    same_district,
    same_state,
)


class TestNormalisation:
    @pytest.mark.parametrize("a,b", [
        ("Ahilyanagar", "Ahmednagar"),
        ("Ahmednagar", "Ahilyanagar"),
        ("Dharashiv", "Osmanabad"),
        ("Osmanabad", "Dharashiv"),
        ("Chattrapati Sambhajinagar", "Aurangabad"),
        ("Chhatrapati Sambhajinagar", "Aurangabad"),
        ("Chhatrapati  Sambhajinagar ", "Chattrapati Sambhajinagar"),
        ("Amarawati", "Amravati"),
        ("Amrawati", "Amravati"),
        ("Amravati", "Amarawati"),
        ("  NASHIK ", "nashik"),
        ("Mumbai", "Mumbai City"),
    ])
    def test_district_aliases_match_both_ways(self, a, b):
        assert canonical_district(a) == canonical_district(b)

    @pytest.mark.parametrize("a,b", [
        ("Keralam", "Kerala"),
        ("Kerala", "Keralam"),
        ("Chattisgarh", "Chhattisgarh"),
        ("Chhattisgarh", "Chattisgarh"),
        ("madhya  pradesh", "Madhya Pradesh"),
        ("Jammu & Kashmir", "Jammu and Kashmir"),
    ])
    def test_state_aliases_match_both_ways(self, a, b):
        assert same_state(a, b)

    def test_punctuation_and_case_ignored(self):
        assert canonical_district("Sangli(Phale)") == canonical_district("sangli phale")
        assert canonical_district("Sawai-Madhopur") == canonical_district("sawai madhopur")

    def test_different_places_do_not_match(self):
        assert not same_district("Maharashtra", "Pune", "Maharashtra", "Nashik")
        assert not same_district("Maharashtra", "Pune", "Madhya Pradesh", "Pune")
        assert not same_state("", "")
        assert not same_district("Maharashtra", "", "Maharashtra", "")

    def test_same_district_through_aliases(self):
        assert same_district("Maharashtra", "Ahilyanagar", "maharashtra", "Ahmednagar")


# District names exactly as seen in the live Agmarknet feed on 19 Nov 2026.
FEED_DISTRICTS = [
    ("Maharashtra", "Nashik"), ("Maharashtra", "Pune"), ("Maharashtra", "Mumbai"),
    ("Maharashtra", "Sangli"), ("Maharashtra", "Solapur"), ("Maharashtra", "Nagpur"),
    ("Maharashtra", "Amarawati"), ("Maharashtra", "Ahilyanagar"),
    ("Maharashtra", "Dharashiv"), ("Maharashtra", "Chattrapati Sambhajinagar"),
    ("Madhya Pradesh", "Sheopur"), ("Madhya Pradesh", "Morena"),
    ("Madhya Pradesh", "Sagar"), ("Madhya Pradesh", "Chhatarpur"),
]

# District names as farmers pick them (js/india-locations.js).
PROFILE_DISTRICTS = [
    ("Maharashtra", "Ahmednagar"), ("Maharashtra", "Osmanabad"), ("Maharashtra", "Aurangabad"),
    ("Maharashtra", "Amravati"), ("Maharashtra", "Mumbai City"), ("Maharashtra", "Mumbai Suburban"),
    ("Madhya Pradesh", "Sheopur"), ("Madhya Pradesh", "Chhatarpur"),
]


class TestMandiDistrictCoordinates:
    @pytest.mark.parametrize("state,district", FEED_DISTRICTS + PROFILE_DISTRICTS)
    def test_every_mandi_district_has_exact_coordinates(self, state, district):
        coords = get_exact_district_coordinates(state, district)
        assert coords is not None, f"{state}/{district} has no coordinates"
        lat, lon = coords
        assert 8 < lat < 37 and 68 < lon < 98     # inside India

    def test_renamed_districts_resolve_to_same_point_as_old_names(self):
        for new, old in [("Ahilyanagar", "Ahmednagar"), ("Dharashiv", "Osmanabad"),
                         ("Chattrapati Sambhajinagar", "Aurangabad"), ("Amarawati", "Amravati")]:
            assert get_exact_district_coordinates("Maharashtra", new) == \
                get_exact_district_coordinates("Maharashtra", old)

    def test_coordinates_are_district_headquarters(self):
        # Spot-check distances between headquarters (well-known road/air distances).
        pune = get_exact_district_coordinates("Maharashtra", "Pune")
        mumbai = get_exact_district_coordinates("Maharashtra", "Mumbai")
        nashik = get_exact_district_coordinates("Maharashtra", "Nashik")
        assert 110 <= haversine_km(pune, mumbai) <= 130      # ~120 km air
        assert 130 <= haversine_km(pune, nashik) <= 170      # ~150 km air
        sagar = get_exact_district_coordinates("Madhya Pradesh", "Sagar")
        bhopal = get_exact_district_coordinates("Madhya Pradesh", "Bhopal")
        assert 140 <= haversine_km(sagar, bhopal) <= 180     # ~155 km air

    def test_exact_lookup_never_falls_back(self):
        assert get_exact_district_coordinates("Maharashtra", "Nowhere") is None
        assert get_exact_district_coordinates("", "") is None

    def test_get_coordinates_resolves_aliases_then_falls_back(self):
        assert get_coordinates("Maharashtra", "Ahilyanagar") == get_coordinates("Maharashtra", "Ahmednagar")
        assert get_coordinates("Keralam", "Nowhere") == geo.INDIA_CENTRE  # Kerala has no capital entry
        assert get_coordinates("Maharashtra", "Nowhere") == geo.STATE_CAPITALS["Maharashtra"]
