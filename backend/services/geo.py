"""
geo.py — District-to-coordinates lookup for Indian guava-growing regions.

Used to get lat/lon for the Open-Meteo weather API based on the farmer's
stored district and state. Coordinates are approximate district centroids
sourced from public geographic data.

When a district is not found, returns the state capital coordinates as fallback.
If neither is found, returns the centroid of India as a last resort.
"""

from __future__ import annotations

# District coordinates: (latitude, longitude)
# Source: approximate centroids from public geographic data (Bhuvan, OSM, Wikipedia)
# Priority guava-growing districts are covered; others use state capital fallback.
DISTRICT_COORDS: dict[tuple[str, str], tuple[float, float]] = {
    # Madhya Pradesh
    ("Madhya Pradesh", "Dhar"):         (22.60, 75.30),
    ("Madhya Pradesh", "Indore"):        (22.72, 75.86),
    ("Madhya Pradesh", "Ratlam"):        (23.33, 75.04),
    ("Madhya Pradesh", "Ujjain"):        (23.18, 75.77),
    ("Madhya Pradesh", "Khargone"):      (21.82, 75.61),
    ("Madhya Pradesh", "Jhabua"):        (22.77, 74.59),
    ("Madhya Pradesh", "Barwani"):       (22.03, 74.90),
    ("Madhya Pradesh", "Alirajpur"):     (22.31, 74.36),
    ("Madhya Pradesh", "Dewas"):         (22.97, 76.05),
    ("Madhya Pradesh", "Sehore"):        (23.20, 77.08),
    ("Madhya Pradesh", "Bhopal"):        (23.26, 77.41),
    ("Madhya Pradesh", "Vidisha"):       (23.53, 77.82),
    ("Madhya Pradesh", "Jabalpur"):      (23.17, 79.94),
    ("Madhya Pradesh", "Gwalior"):       (26.22, 78.18),
    ("Madhya Pradesh", "Morena"):        (26.50, 78.00),
    ("Madhya Pradesh", "Shivpuri"):      (25.43, 77.66),
    # Districts that have Agmarknet guava mandis (coordinates: district
    # headquarters town as listed on Wikipedia, rounded to 2 decimals;
    # Sheopur uses the Wikipedia "Sheopur district" page coordinate because the
    # town's own page has none).
    ("Madhya Pradesh", "Sheopur"):       (25.70, 76.70),
    ("Madhya Pradesh", "Sagar"):         (23.84, 78.74),
    ("Madhya Pradesh", "Chhatarpur"):    (24.90, 79.59),
    # Uttar Pradesh
    ("Uttar Pradesh", "Allahabad"):      (25.44, 81.84),
    ("Uttar Pradesh", "Prayagraj"):      (25.44, 81.84),
    ("Uttar Pradesh", "Lucknow"):        (26.85, 80.95),
    ("Uttar Pradesh", "Varanasi"):       (25.32, 83.01),
    ("Uttar Pradesh", "Agra"):           (27.18, 78.01),
    ("Uttar Pradesh", "Mathura"):        (27.49, 77.67),
    ("Uttar Pradesh", "Muzaffarnagar"):  (29.47, 77.70),
    ("Uttar Pradesh", "Meerut"):         (28.98, 77.71),
    ("Uttar Pradesh", "Kanpur"):         (26.47, 80.35),
    ("Uttar Pradesh", "Bahraich"):       (27.57, 81.60),
    # Maharashtra
    ("Maharashtra", "Pune"):             (18.52, 73.86),
    ("Maharashtra", "Nashik"):           (19.99, 73.79),
    ("Maharashtra", "Amravati"):         (20.93, 77.75),
    ("Maharashtra", "Nagpur"):           (21.15, 79.09),
    ("Maharashtra", "Satara"):           (17.68, 74.00),
    # Districts that have Agmarknet guava mandis (coordinates: district
    # headquarters city as listed on Wikipedia, rounded to 2 decimals;
    # Mumbai Suburban uses the Wikipedia district-page coordinate).
    # Profiles use the older names (Ahmednagar, Osmanabad, Aurangabad); the
    # renamed forms are matched through DISTRICT_ALIASES below.
    ("Maharashtra", "Mumbai City"):      (19.08, 72.88),
    ("Maharashtra", "Mumbai Suburban"):  (19.05, 72.83),
    ("Maharashtra", "Sangli"):           (16.85, 74.58),
    ("Maharashtra", "Solapur"):          (17.67, 75.90),
    ("Maharashtra", "Ahmednagar"):       (19.08, 74.73),
    ("Maharashtra", "Osmanabad"):        (18.19, 76.04),
    ("Maharashtra", "Aurangabad"):       (19.88, 75.32),
    # Rajasthan
    ("Rajasthan", "Sawai Madhopur"):     (26.02, 76.36),
    ("Rajasthan", "Kota"):               (25.18, 75.83),
    ("Rajasthan", "Alwar"):              (27.56, 76.61),
    ("Rajasthan", "Jaipur"):             (26.91, 75.79),
    # Bihar
    ("Bihar", "Muzaffarpur"):            (26.12, 85.39),
    ("Bihar", "Vaishali"):               (25.69, 85.18),
    ("Bihar", "Samastipur"):             (25.87, 85.78),
    ("Bihar", "Patna"):                  (25.59, 85.14),
    # Gujarat
    ("Gujarat", "Surat"):                (21.17, 72.83),
    ("Gujarat", "Vadodara"):             (22.31, 73.19),
    ("Gujarat", "Navsari"):              (20.95, 72.92),
    # West Bengal
    ("West Bengal", "Murshidabad"):      (24.18, 88.27),
    ("West Bengal", "Nadia"):            (23.47, 88.56),
    ("West Bengal", "North 24 Parganas"): (22.86, 88.57),
    # Punjab
    ("Punjab", "Amritsar"):              (31.63, 74.87),
    ("Punjab", "Ludhiana"):              (30.91, 75.85),
    # Haryana
    ("Haryana", "Hisar"):                (29.14, 75.72),
    ("Haryana", "Sirsa"):                (29.53, 75.02),
    # Andhra Pradesh
    ("Andhra Pradesh", "Krishna"):       (16.52, 80.63),
    ("Andhra Pradesh", "Guntur"):        (16.30, 80.44),
    # Karnataka
    ("Karnataka", "Bangalore"):          (12.97, 77.56),
    ("Karnataka", "Bengaluru Urban"):    (12.97, 77.56),
    ("Karnataka", "Tumkur"):             (13.34, 77.10),
}

# State capital fallbacks
STATE_CAPITALS: dict[str, tuple[float, float]] = {
    "Madhya Pradesh":  (23.26, 77.41),  # Bhopal
    "Uttar Pradesh":   (26.85, 80.95),  # Lucknow
    "Maharashtra":     (18.97, 72.83),  # Mumbai
    "Rajasthan":       (26.91, 75.79),  # Jaipur
    "Bihar":           (25.59, 85.14),  # Patna
    "Gujarat":         (23.02, 72.57),  # Ahmedabad
    "West Bengal":     (22.57, 88.36),  # Kolkata
    "Punjab":          (30.73, 76.78),  # Chandigarh
    "Haryana":         (30.73, 76.78),  # Chandigarh
    "Andhra Pradesh":  (15.91, 79.74),  # Amaravati
    "Karnataka":       (12.97, 77.56),  # Bengaluru
    "Tamil Nadu":      (13.08, 80.27),  # Chennai
    "Telangana":       (17.38, 78.49),  # Hyderabad
    "Odisha":          (20.27, 85.84),  # Bhubaneswar
    "Jharkhand":       (23.35, 85.33),  # Ranchi
    "Chhattisgarh":    (21.25, 81.63),  # Raipur
    "Uttarakhand":     (30.32, 78.04),  # Dehradun
    "Himachal Pradesh":(31.10, 77.17),  # Shimla
    "Jammu and Kashmir":(34.09, 74.79), # Srinagar
    "Assam":           (26.14, 91.74),  # Dispur
}

# Centre of India as last-resort fallback
INDIA_CENTRE = (22.59, 82.31)


# ── Name normalisation and aliases ────────────────────────────────────────────
# The Agmarknet feed and farmer profiles spell some places differently
# (renamed districts, spelling variants). Every comparison and lookup goes
# through canonical_state / canonical_district so both directions match.
# Keys and values are normalised names (see normalise_name). The canonical form
# is the name used in DISTRICT_COORDS / india-locations.js (farmer profiles).

STATE_ALIASES: dict[str, str] = {
    "keralam": "kerala",
    "chattisgarh": "chhattisgarh",
    "chhatisgarh": "chhattisgarh",
    "orissa": "odisha",
    "uttaranchal": "uttarakhand",
}

DISTRICT_ALIASES: dict[str, str] = {
    # Maharashtra renames (2022-2025)
    "ahilyanagar": "ahmednagar",
    "ahmadnagar": "ahmednagar",
    "ahilya nagar": "ahmednagar",
    "dharashiv": "osmanabad",
    "dharashiva": "osmanabad",
    "chattrapati sambhajinagar": "aurangabad",
    "chhatrapati sambhajinagar": "aurangabad",
    "chhatrapati sambhaji nagar": "aurangabad",
    "chattrapati sambhaji nagar": "aurangabad",
    "sambhajinagar": "aurangabad",
    # Spelling variants
    "amarawati": "amravati",
    "amrawati": "amravati",
    "nasik": "nashik",
    "mumbai": "mumbai city",
}


def normalise_name(value) -> str:
    """Lower-case, turn '&' into 'and', drop punctuation, collapse spaces."""
    import re
    text = str(value or "").strip().lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def canonical_state(value) -> str:
    """Normalised state name with known aliases (e.g. Keralam) resolved."""
    name = normalise_name(value)
    return STATE_ALIASES.get(name, name)


def canonical_district(value) -> str:
    """Normalised district name with known aliases (e.g. Dharashiv) resolved."""
    name = normalise_name(value)
    return DISTRICT_ALIASES.get(name, name)


def same_state(a, b) -> bool:
    ca = canonical_state(a)
    return bool(ca) and ca == canonical_state(b)


def same_district(state_a, district_a, state_b, district_b) -> bool:
    """True when both state and district match after normalisation."""
    cd = canonical_district(district_a)
    return same_state(state_a, state_b) and bool(cd) and cd == canonical_district(district_b)


def get_coordinates(state: str, district: str) -> tuple[float, float]:
    """Return (latitude, longitude) for the given state + district.

    Lookup order:
      1. Match on (state, district) after normalisation and alias resolution
      2. State capital fallback
      3. India centre as last resort
    """
    coords = get_exact_district_coordinates(state, district)
    if coords is not None:
        return coords
    cs = canonical_state(state)
    for s_name, c in STATE_CAPITALS.items():
        if canonical_state(s_name) == cs:
            return c
    return INDIA_CENTRE


def get_exact_district_coordinates(state: str, district: str):
    """Return (lat, lon) only when the district is in DISTRICT_COORDS, else None.

    Unlike get_coordinates this never falls back to a state capital, so callers
    that measure distance do not report a made-up number for unlisted districts.
    Names are matched after normalisation, so "Ahilyanagar" finds "Ahmednagar".
    """
    cs, cd = canonical_state(state), canonical_district(district)
    if not cs or not cd:
        return None
    for (ks, kd), coords in DISTRICT_COORDS.items():
        if canonical_state(ks) == cs and canonical_district(kd) == cd:
            return coords
    return None


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in km between two (lat, lon) points."""
    from math import asin, cos, radians, sin, sqrt
    lat1, lon1, lat2, lon2 = map(radians, (a[0], a[1], b[0], b[1]))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0088 * asin(sqrt(h))
