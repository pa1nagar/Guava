"""
sell_smart_examples.py - print the Sell smart ranking for a Pune-area farmer.

    cd backend
    python scripts/sell_smart_examples.py

(a) on the synthetic DEMO dataset, (b) on tests/fixtures/mandi_guava_live_shape.json.
No network, no database, no keys. The farmer's costs below are ENTERED example
values, not recommendations; they are printed with the results.
"""
import json
import sys
import uuid
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.mandi_prices import parse_records  # noqa: E402
from services.sell_smart import locations, quality, ranking  # noqa: E402
from services.sell_smart.demo import generate_price_rows  # noqa: E402

FIXTURE = BACKEND_DIR / "tests" / "fixtures" / "mandi_guava_live_shape.json"
TODAY = date(2026, 11, 12)
COMPARE = ("Pune", "Mumbai", "Nashik", "Solapur")
FARM = ("Maharashtra", "Pune")
ENTERED = {
    "transport_mode": ranking.MODE_PER_KM,
    "transport_value": 2.5,            # Rs per quintal per km, entered by the farmer
    "handling_rs_per_quintal": 40.0,   # entered
    "commission_pct": 4.0,             # entered
    "road_km_overrides": {},
}


def fixture_rows() -> list[dict]:
    """market_prices-shaped rows built from the live-shape feed fixture."""
    records = json.loads(FIXTURE.read_text(encoding="utf-8"))["records"]
    rows, _skipped = parse_records(records)
    for r in rows:
        r["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{r['market_name']}|{r['variety']}|{r['arrival_date']}|{r['modal_price']}"))
    return rows


def rank_pune(rows: list[dict], today: date = TODAY) -> dict:
    """Rank the four mandis for a farmer whose location is the Pune district centre."""
    origin = locations.resolve_district(*FARM)
    annotated = quality.annotate([r for r in rows if r["district"] in COMPARE], {})
    return ranking.rank_mandis(annotated, (origin[0], origin[1]), ENTERED, 300.0, today)


def render(title: str, result: dict) -> str:
    lines = [
        title,
        f"  Farmer: {FARM[1]}, {FARM[0]} (distances from the {FARM[1]} district centre, so {FARM[1]} is 0 km)",
        f"  Entered costs: transport Rs {ENTERED['transport_value']} per quintal per km, "
        f"handling Rs {ENTERED['handling_rs_per_quintal']:g} per quintal, commission {ENTERED['commission_pct']:g}%",
        f"  Formula: {ranking.FORMULA['text_en']}",
        f"  {'#':<2} {'Mandi':<9} {'Date':<10} {'km':>5} {'Gross':>7} {'Transp':>7} {'Handl':>6} {'Comm':>6} {'NET':>7}   (Rs per kg)",
    ]
    for e in result["ranked"]:
        lines.append(
            f"  {e['rank']:<2} {e['market_name']:<9} {e['trade_date']:<10} {e['distance_km']:>5.0f} {e['gross_per_kg']:>7.2f} "
            f"{e['transport_per_kg']:>7.2f} {e['handling_per_kg']:>6.2f} {e['commission_per_kg']:>6.2f} {e['net_per_kg']:>7.2f}")
    for e in result["unranked"]:
        lines.append(f"  -  {e['market_name']:<9} not ranked (stale={e['stale']}, location_known={e['location_known']})")
    lines.append(f"  Distance basis: {ranking.DISTANCE_LABEL_STRAIGHT}")
    return "\n".join(lines)


def main() -> None:
    demo_rows = generate_price_rows(TODAY)
    print(render("(a) DEMO DATA (synthetic, not market prices), as of 2026-11-12", rank_pune(demo_rows)))
    print()
    print(render("(b) LIVE-SHAPE fixture tests/fixtures/mandi_guava_live_shape.json (derived from the feed shape, test values), as of 2026-11-12",
                 rank_pune(fixture_rows())))


if __name__ == "__main__":
    main()
