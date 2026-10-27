"""The chart colours in tokens.css must equal the validated sets in palette.json (guards against silent drift)."""

import json
import re

from paths import ROOT

CSS = (ROOT / "site_src" / "assets" / "css" / "tokens.css").read_text(encoding="utf-8")
PAL = json.loads((ROOT / "site_src" / "assets" / "css" / "palette.json").read_text(encoding="utf-8"))


def block(start_pat: str) -> str:
    i = CSS.index(start_pat, CSS.index("Chart colours"))
    return CSS[i : CSS.index("}", i)]


def slots(b: str) -> list[str]:
    found = dict(re.findall(r"--c(\d): (#[0-9a-fA-F]{6})", b))
    return [found[str(i)].lower() for i in range(1, 9)]


def test_dark_slots_equal_the_validated_dark_set():
    assert slots(block(":root {")) == PAL["categorical"]["dark"]


def test_light_slots_equal_the_validated_light_set_in_both_scopes():
    assert slots(block(":root:not([data-theme=\"dark\"]) {")) == PAL["categorical"]["light"]
    assert slots(block(":root[data-theme=\"light\"] {")) == PAL["categorical"]["light"]


def test_no_unvalidated_series_colour_is_used_in_the_chart_css_or_js():
    allowed = {c for mode in PAL["categorical"].values() for c in mode}
    for p in list((ROOT / "site_src" / "assets" / "css").glob("charts.css")) + list((ROOT / "site_src" / "assets" / "js").rglob("*.js")):
        for hex_ in re.findall(r"#[0-9a-fA-F]{6}\b", p.read_text(encoding="utf-8")):
            assert hex_.lower() in allowed, f"{p.name} uses {hex_}, which is not in the validated palette"
