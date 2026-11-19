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
    # District headquarters for every MP / Maharashtra district in js/india-locations.js.
    # Source: OpenStreetMap place=city|town node of the HQ town (ODbL, via Overpass API,
    # queried 19 Nov 2026), cross-checked against the Wikipedia town coordinate; the two
    # agree within ~3 km except where noted. Rounded to 4 decimals.
    # Singrauli = Waidhan (district HQ), Raigad = Alibag, Sindhudurg = Oros,
    # Hoshangabad = Narmadapuram (renamed 2022), Agar Malwa = Agar.
    # Madhya Pradesh (headquarters)
    ("Madhya Pradesh", "Agar Malwa"):         (23.7155, 76.0075),
    ("Madhya Pradesh", "Anuppur"):            (23.1185, 81.6992),
    ("Madhya Pradesh", "Ashoknagar"):         (24.5762, 77.7303),
    ("Madhya Pradesh", "Balaghat"):           (21.8133, 80.1917),
    ("Madhya Pradesh", "Betul"):              (21.8998, 77.8959),
    ("Madhya Pradesh", "Bhind"):              (26.5652, 78.7890),
    ("Madhya Pradesh", "Burhanpur"):          (21.3119, 76.2292),
    ("Madhya Pradesh", "Chhindwara"):         (22.0578, 78.9386),
    ("Madhya Pradesh", "Damoh"):              (23.8396, 79.4444),
    ("Madhya Pradesh", "Datia"):              (25.6689, 78.4582),
    ("Madhya Pradesh", "Dindori"):            (22.9447, 81.0775),
    ("Madhya Pradesh", "Guna"):               (24.6477, 77.3162),
    ("Madhya Pradesh", "Harda"):              (22.3389, 77.0930),
    ("Madhya Pradesh", "Hoshangabad"):        (22.7546, 77.7198),
    ("Madhya Pradesh", "Katni"):              (23.8340, 80.3925),
    ("Madhya Pradesh", "Khandwa"):            (21.8204, 76.3555),
    ("Madhya Pradesh", "Maihar"):             (24.2604, 80.7593),
    ("Madhya Pradesh", "Mandla"):             (22.5978, 80.3721),
    ("Madhya Pradesh", "Mandsaur"):           (24.0683, 75.0742),
    ("Madhya Pradesh", "Mauganj"):            (24.6679, 81.8812),
    ("Madhya Pradesh", "Narsimhapur"):        (22.9467, 79.1980),
    ("Madhya Pradesh", "Neemuch"):            (24.4650, 74.8690),
    ("Madhya Pradesh", "Niwari"):             (25.3512, 78.7994),
    ("Madhya Pradesh", "Pandhurna"):          (21.5955, 78.5258),
    ("Madhya Pradesh", "Panna"):              (24.7196, 80.1861),
    ("Madhya Pradesh", "Raisen"):             (23.3301, 77.7843),
    ("Madhya Pradesh", "Rajgarh"):            (24.0051, 76.7337),
    ("Madhya Pradesh", "Rewa"):               (24.5359, 81.2934),
    ("Madhya Pradesh", "Satna"):              (24.5751, 80.8326),
    ("Madhya Pradesh", "Seoni"):              (22.0910, 79.5508),
    ("Madhya Pradesh", "Shahdol"):            (23.3002, 81.3648),
    ("Madhya Pradesh", "Shajapur"):           (23.4241, 76.2839),
    ("Madhya Pradesh", "Sidhi"):              (24.4109, 81.8795),
    ("Madhya Pradesh", "Singrauli"):          (24.0658, 82.6269),
    ("Madhya Pradesh", "Tikamgarh"):          (24.7429, 78.8322),
    ("Madhya Pradesh", "Umaria"):             (23.5247, 80.8361),
    # Maharashtra (headquarters)
    ("Maharashtra", "Akola"):                 (20.7117, 77.0026),
    ("Maharashtra", "Beed"):                  (18.9904, 75.7542),
    ("Maharashtra", "Bhandara"):              (21.1707, 79.6566),
    ("Maharashtra", "Buldhana"):              (20.5321, 76.1799),
    ("Maharashtra", "Chandrapur"):            (19.9508, 79.2987),
    ("Maharashtra", "Dhule"):                 (20.8980, 74.7732),
    ("Maharashtra", "Gadchiroli"):            (20.1854, 80.0035),
    ("Maharashtra", "Gondia"):                (21.4552, 80.1963),
    ("Maharashtra", "Hingoli"):               (19.7158, 77.1388),
    ("Maharashtra", "Jalgaon"):               (21.0101, 75.5696),
    ("Maharashtra", "Jalna"):                 (19.8393, 75.8819),
    ("Maharashtra", "Kolhapur"):              (16.7028, 74.2405),
    ("Maharashtra", "Latur"):                 (18.3982, 76.5626),
    ("Maharashtra", "Nanded"):                (19.1693, 77.3110),
    ("Maharashtra", "Nandurbar"):             (21.3638, 74.2411),
    ("Maharashtra", "Palghar"):               (19.6967, 72.7695),
    ("Maharashtra", "Parbhani"):              (19.2625, 76.7718),
    ("Maharashtra", "Raigad"):                (18.6498, 72.8765),
    ("Maharashtra", "Ratnagiri"):             (16.9934, 73.2954),
    ("Maharashtra", "Sindhudurg"):            (16.1163, 73.7079),
    ("Maharashtra", "Thane"):                 (19.1943, 72.9702),
    ("Maharashtra", "Wardha"):                (20.7465, 78.5998),
    ("Maharashtra", "Washim"):                (20.1029, 77.1354),
    ("Maharashtra", "Yavatmal"):              (20.3903, 78.1329),
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
