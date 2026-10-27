"""WS3 reconciliation and headline checks on the real processed data (data/processed/sysselsetting)."""

import csv
import json

import pytest
import yaml

from paths import ROOT
from transform.common import latest_snapshot

P = ROOT / "data" / "processed" / "sysselsetting"


def series(name):
    return {v["period"]: v for v in json.loads((P / f"{name}.json").read_text(encoding="utf-8"))["values"]}


def facts(name):
    with (P / name / "facts.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def reg(year, nodes, sex=None, age="15_74"):
    rows = facts(f"registerstatus_{age}")
    return sum(float(r["value"]) for r in rows if r["period"] == year and r["statusgruppe"] in nodes and (sex is None or r["kjonn"] == sex))


EMPLOYED = ["A.01x00", "A.01xU03", "A.01xU04", "A.01xU05", "A.01xU06-07", "A.01.90A"]
OUTSIDE = ["U.01.00", "U.03.00", "U.04.00", "U.05.00", "U.06.00", "U.07.00", "U.90A.00", "UX.00"]


def test_register_groups_equal_ssbs_published_aggregates():
    """Independent of how the tree was built: A, A.01 and U as published by SSB equal the sums of our leaves."""
    js, _ = latest_snapshot("ssb-12423")
    pub = {(r["Alder"], r["Kjonn"], r["HovArbStyrkStatus"], r["Tid"]): r["value"] for r in js.rows()}
    for age_code, age in (("15-74", "15_74"), ("20-66", "20_66")):
        for y in ("2015", "2024", "2025"):
            both = lambda nodes: reg(y, nodes, None, age)  # noqa: E731
            assert both(EMPLOYED) == pytest.approx(pub[(age_code, "0", "A.01", y)], abs=12), (age, y, "sysselsatte")
            assert both(EMPLOYED + ["A.09.00"]) == pytest.approx(pub[(age_code, "0", "A", y)], abs=12)
            assert both(OUTSIDE) == pytest.approx(pub[(age_code, "0", "U", y)], abs=12)
            assert both(EMPLOYED + ["A.09.00"] + OUTSIDE) == pytest.approx(pub[(age_code, "0", "TOT", y)], abs=15)


def test_every_person_has_one_status_so_overlap_leaves_are_part_of_the_partition():
    import yaml as y
    dims = y.safe_load((P / "registerstatus_15_74" / "dimensions.yaml").read_text(encoding="utf-8"))["dimensions"]["statusgruppe"]["nodes"]
    by = {n["code"]: n for n in dims}
    assert by["A.01xU05"]["overlap"] == ["U.05.00"] and by["A.01xU06-07"]["overlap"] == ["U.06.00", "U.07.00"]
    assert all(by[o]["parent"] == "U" for n in dims for o in n.get("overlap", []))  # overlaps point at groups outside the labour force
    assert reg("2024", ["A.01xU05"]) > 0 and reg("2024", ["U.05.00"]) > 0  # employed with disability benefit, and recipients outside work


def test_men_and_women_add_up_to_both_sexes():
    js, _ = latest_snapshot("ssb-12423")
    pub = {(r["Alder"], r["Kjonn"], r["HovArbStyrkStatus"], r["Tid"]): r["value"] for r in js.rows()}
    for y in ("2015", "2025"):
        assert reg(y, EMPLOYED + ["A.09.00"] + OUTSIDE, "1") + reg(y, EMPLOYED + ["A.09.00"] + OUTSIDE, "2") == pytest.approx(pub[("15-74", "0", "TOT", y)], abs=15)


def test_last_register_year_is_marked_preliminary():
    rows = facts("registerstatus_15_74")
    last = max(r["period"] for r in rows)
    assert {r["status"] for r in rows if r["period"] == last} == {"foreløpig"}
    assert {r["status"] for r in rows if r["period"] != last} == {"regnskap"}
    assert min(r["period"] for r in rows) == "2015"  # a-ordningen: no break inside the series


def test_aku_workforce_is_employed_plus_unemployed_within_rounding():
    js, _ = latest_snapshot("ssb-13618")
    pub = {(r["Alder"], r["Kjonn"], r["ArbStyrkStatus"], r["ContentsCode"], r["Tid"]): r["value"] for r in js.rows()}
    for y in ("2015", "2021", "2025"):
        assert pub[("15-74", "0", "1", "Personer", y)] + pub[("15-74", "0", "2", "Personer", y)] == pytest.approx(pub[("15-74", "0", "0", "Personer", y)], abs=2)
    assert series("aku_sysselsatte_feilmargin")["2025"]["value"] == 12 and "2020" not in series("aku_sysselsatte_feilmargin")  # margins exist from 2021


def test_aku_and_register_employment_are_close_but_unemployment_is_not():
    """Documented property: the register counts about half of AKU's unemployed (different definitions and sources)."""
    emp_a, emp_r = series("sysselsatte_aku_tusen"), series("sysselsatte_register_tusen")
    led_a, led_r = series("ledige_aku_tusen"), series("ledige_register_tusen")
    for y in ("2019", "2024", "2025"):
        assert abs(emp_a[y]["value"] - emp_r[y]["value"]) / emp_a[y]["value"] < 0.02
        assert led_a[y]["value"] > 1.8 * led_r[y]["value"]
    assert emp_r["2025"]["claim_level"] == "utledet" if "claim_level" in emp_r["2025"] else True


def test_headline_numbers_match_ssb_page_for_residents_15_and_over():
    js, _ = latest_snapshot("ssb-12423")
    h = yaml.safe_load((ROOT / "tests" / "headlines" / "sysselsetting.yaml").read_text(encoding="utf-8"))
    pub = {(r["Alder"], r["Kjonn"], r["HovArbStyrkStatus"], r["Tid"]): r["value"] for r in js.rows()}
    for code, page in h["page_values"].items():
        assert pub[("15+", "0", code, h["year"])] == pytest.approx(page, abs=h["tolerance_persons"]), code


def test_national_accounts_persons_year_works_and_hours():
    persons, arsverk, hours = series("sysselsatte_personer_na"), series("arsverk_na"), series("timeverk_na")
    ratio = series("arsverk_per_sysselsatt")
    for y in ("2000", "2024"):
        assert ratio[y]["value"] == pytest.approx(arsverk[y]["value"] / persons[y]["value"], abs=0.001)
        assert 0.7 < ratio[y]["value"] < 1.0  # part-time work and absence: fewer year-works than persons
    assert persons["2025"]["status"] == "foreløpig" and persons["2023"]["status"] == "regnskap"
    assert hours["2024"]["value"] > 3000  # million hours
