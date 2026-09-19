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


def get_coordinates(state: str, district: str) -> tuple[float, float]:
    """Return (latitude, longitude) for the given state + district.

    Lookup order:
      1. Exact match on (state, district)
      2. State capital fallback
      3. India centre as last resort
    """
    key = (state.strip(), district.strip())
    if key in DISTRICT_COORDS:
        return DISTRICT_COORDS[key]

    # Try case-insensitive match
    for (s, d), coords in DISTRICT_COORDS.items():
        if s.lower() == state.lower() and d.lower() == district.lower():
            return coords

    # State capital fallback
    for s_name, coords in STATE_CAPITALS.items():
        if s_name.lower() == state.lower():
            return coords

    return INDIA_CENTRE
