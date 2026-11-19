"""Every text key the Sell smart page uses exists in both English and Hindi."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
I18N = (ROOT / "js" / "sell-smart-i18n.js").read_text(encoding="utf-8")
HTML = (ROOT / "sell-smart.html").read_text(encoding="utf-8")
JS = (ROOT / "js" / "sell-smart.js").read_text(encoding="utf-8")
SVC = ROOT / "backend" / "services" / "sell_smart"

ENTRY = re.compile(r'^\s+"([A-Za-z0-9_]+)":\s*"((?:[^"\\]|\\.)*)",?\s*$', re.M)


def _block(name: str) -> dict:
    start = I18N.index(f"export const {name} = {{")
    end = I18N.index("\n};", start)
    return dict(ENTRY.findall(I18N[start:end]))


EN, HI = _block("SELL_EN"), _block("SELL_HI")


def _placeholders(text: str) -> set:
    return set(re.findall(r"\{(\w+)\}", text))


def test_both_languages_have_the_same_keys():
    assert EN and set(EN) == set(HI)


def test_placeholders_match_between_languages():
    bad = [k for k in EN if _placeholders(EN[k]) != _placeholders(HI[k])]
    assert bad == []


def test_no_empty_text():
    assert [k for k, v in {**EN, **HI}.items() if not v.strip()] == []


def test_hindi_is_not_a_copy_of_english():
    same = [k for k in EN if EN[k] == HI[k] and re.search(r"[A-Za-z]{4,}", EN[k])]
    assert set(same) <= {"sell_lang_en", "sell_lang_hi", "sell_trend_scope_mandi"}


def test_html_keys_exist_in_both():
    keys = set(re.findall(r'data-(?:i18n|i18n-placeholder|aria-i18n)="([^"]+)"', HTML))
    assert keys
    assert sorted(k for k in keys if k not in EN or k not in HI) == []


def test_literal_tr_keys_in_js_exist():
    keys = set(re.findall(r'\btr\(\s*"([A-Za-z0-9_]+)"', JS))
    keys |= set(re.findall(r'"(sell_[A-Za-z0-9_]+|needs_[a-z_]+)"', JS))
    assert keys
    assert sorted(k for k in keys if k not in EN or k not in HI) == []


def test_dynamic_key_families_are_complete():
    families = (
        [f"sell_flag_{f}" for f in ("ZERO_PRICE", "ORDER_VIOLATION", "UNIT_SUSPECT", "OUTLIER", "DUPLICATE_VALUES", "REVISED")]
        + [f"sell_conf_{c}" for c in ("High", "Medium", "Low")]
        + [f"sell_conf_expl_{c}" for c in ("High", "Medium", "Low")]
        + [f"sell_month_{m}" for m in range(1, 13)]
        + [f"sell_location_{b}" for b in ("farm_gps", "district_centre")]
        + [f"sell_dir_{d}" for d in ("at_or_above", "at_or_below")]
    )
    assert sorted(k for k in families if k not in EN or k not in HI) == []


def test_server_side_keys_have_text():
    stats_keys = set(re.findall(r'"(needs_[a-z_]+)"', (SVC / "stats.py").read_text(encoding="utf-8")))
    note_keys = set(re.findall(r'"key": "(\w+)"', (SVC / "fairness.py").read_text(encoding="utf-8")))
    reasons = {f"sell_fairness_{r}" for r in re.findall(r'_insufficient\(\s*"(\w+)"', (SVC / "fairness.py").read_text(encoding="utf-8"))}
    router = (ROOT / "backend" / "routers" / "sell_smart.py").read_text(encoding="utf-8")
    router_keys = set(re.findall(r'"(sell_(?:distance|notif)_[a-z_]+)"', router))
    expected = (stats_keys | note_keys | reasons | router_keys) - {"needs_key", "needs_params"}
    assert {"needs_more_days", "fairness_note_grade", "sell_fairness_no_sale", "sell_distance_straight"} <= expected
    assert sorted(k for k in expected if k not in EN or k not in HI) == []


def test_page_has_no_demo_base_outside_demo_mode():
    # The demo base URL appears once and is only used inside the DEMO branch of request().
    assert JS.count('const DEMO_BASE = "http://127.0.0.1:8001"') == 1
    assert JS.count("DEMO_BASE") == 2
    assert 'params.get("demo") === "1"' in JS


def test_i18n_does_not_edit_data_js():
    assert "Object.assign(TRANSLATIONS.en, SELL_EN)" in I18N
    assert "Object.assign(TRANSLATIONS.hi, SELL_HI)" in I18N
