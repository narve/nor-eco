"""WS4: the company tables reconcile with the report's own sums, and the rings agree with SSB's sector table."""

import json

import pytest
import yaml

from transform.common import PROCESSED, latest_snapshot_bytes
from transform.staten import parse_eierrapport

D = PROCESSED / "staten"


def series(name):
    return {v["period"]: v for v in json.loads((D / f"{name}.json").read_text(encoding="utf-8"))["values"]}


def facts(name):
    import csv
    return list(csv.DictReader((D / name / "facts.csv").open(encoding="utf-8")))


def test_company_tables_sum_to_the_reports_sums():
    t = parse_eierrapport(latest_snapshot_bytes("nfd-eierrapport-2025")[0])
    assert len(t["listed"]["rows"]) + len(t["unlisted"]["rows"]) == 20  # «Totalt var det 20 selskaper i kategori 1»
    assert len(t["cat2"]["rows"]) == 44                                   # «Det er totalt 44 selskaper i kategori 2»
    assert sum(r[2] for r in t["cat2"]["rows"]) == t["cat2"]["sum"]["Sum selskaper i kategori 2"]


def test_total_matches_the_figure_nfd_presents_for_the_whole_portfolio():
    # NFD's presentation for new board members (10 Sept 2026) gives 333 096 employees for the direct holdings
    assert sum(int(r["value"]) for r in facts("selskaper")) == 333_096


def test_weighted_is_never_larger_than_unweighted():
    a = {r["selskap"]: int(r["value"]) for r in facts("selskaper")}
    b = {r["selskap"]: int(r["value"]) for r in facts("selskaper_vektet")}
    assert a.keys() == b.keys() and all(b[k] <= a[k] for k in a) and sum(b.values()) < sum(a.values())
    assert {r["claim_level"] for r in facts("selskaper_vektet")} == {"estimat"}


def test_ring_one_plus_health_authorities_is_close_to_ssb_statsforvaltningen():
    rings = {r["ring"]: int(r["value"]) for r in facts("ringer")}
    sf = series("statsforvaltningen")["2025"]["value"]
    assert (rings["R1"] + rings["R2"]) == pytest.approx(sf, rel=0.03)  # different measures (annual mean vs 4th quarter), so only roughly equal


def test_sector_partition_sums_to_all_employed():
    by_year = {}
    for r in facts("sektorer"):
        by_year[r["period"]] = by_year.get(r["period"], 0) + int(r["value"])
    pub = yaml.safe_load((D / "sektorer" / "dataset.yaml").read_text(encoding="utf-8"))["published_totals"]
    for p in pub:
        assert by_year[p["period"]] == pytest.approx(p["value"], rel=0.0005)


def test_difference_is_statsforvaltningen_minus_state_employees():
    d, a, s = series("differanse_statsforvaltningen"), series("ansatte_staten"), series("statsforvaltningen")
    for y in d:
        assert d[y]["value"] == s[y]["value"] - a[y]["value"]
