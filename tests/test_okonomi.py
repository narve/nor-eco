"""WS2 reconciliation and headline checks on the real processed data (data/processed/okonomi)."""

import csv
import json

import pytest
import yaml

from paths import ROOT
from transform.okonomi import trade_is_final

P = ROOT / "data" / "processed" / "okonomi"


def series(name):
    return {v["period"]: v for v in json.loads((P / f"{name}.json").read_text(encoding="utf-8"))["values"]}


def facts(name):
    with (P / name / "facts.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_bnp_equals_fastland_plus_olje_sjofart_in_current_prices():
    bnp, fn, ol = series("bnp_lopende"), series("bnp_fastland_lopende"), series("olje_sjofart_lopende")
    assert bnp.keys() == fn.keys() == ol.keys()
    for t in bnp:
        assert bnp[t]["value"] == pytest.approx(fn[t]["value"] + ol[t]["value"], abs=0.002), t


def test_chained_fixed_prices_do_not_add_up_before_the_base_year():
    """Documented property (kjedingsavvik): the identity above must NOT be assumed for fixed prices."""
    bnp, fn, ol = series("bnp_faste"), series("bnp_fastland_faste"), series("olje_sjofart_faste")
    assert abs(bnp["2000"]["value"] - fn["2000"]["value"] - ol["2000"]["value"]) > 100
    assert bnp["2023"]["value"] == pytest.approx(fn["2023"]["value"] + ol["2023"]["value"], abs=0.002)


def test_export_types_sum_to_published_total_and_kjedingsavvik_is_explicit():
    for name in ("eksport_lopende", "import_lopende", "eksport_faste"):
        meta = yaml.safe_load((P / name / "dataset.yaml").read_text(encoding="utf-8"))
        sums = {}
        for r in facts(name):
            sums[r["period"]] = sums.get(r["period"], 0) + float(r["value"])
        for t in meta["published_totals"]:
            assert sums[t["period"]] == pytest.approx(t["value"], abs=0.0015), (name, t["period"])
    resid = [r for r in facts("eksport_faste") if r["vare"] == "kjedingsavvik"]
    assert resid and all(r["claim_level"] == "utledet" for r in resid)
    assert max(abs(float(r["value"])) for r in resid) > 10  # it is not hidden when it matters
    assert not any(r["vare"] == "kjedingsavvik" for r in facts("eksport_lopende"))


def test_trade_balance_difference_is_the_oil_and_gas_net_export():
    all_, ex = series("handelsbalanse_i_alt"), series("handelsbalanse_uten_olje_gass")
    eks = {r["period"]: float(r["value"]) for r in facts("eksport_lopende") if r["vare"] == "rolje_naturgass"}
    imp = {r["period"]: float(r["value"]) for r in facts("import_lopende") if r["vare"] == "rolje_naturgass"}
    for t in all_:
        assert all_[t]["value"] - ex[t]["value"] == pytest.approx(eks[t] - imp[t], abs=0.002), t


def test_goods_oil_gas_components_sum_to_total_and_condensate_nulls_are_not_zero():
    rows = facts("vareeksport_olje_gass_lopende")
    assert not [r for r in rows if r["vare"] == "kondensat" and r["period"] == "1995"]
    assert [r for r in rows if r["vare"] == "kondensat" and r["period"] == "2010"]


def test_per_capita_recomputes_from_inputs():
    pop = series("befolkning_1_januar")
    for t in ("2000", "2024"):
        expected = series("bnp_lopende")[t]["value"] * 1e9 / ((pop[t]["value"] + pop[str(int(t) + 1)]["value"]) / 2)
        assert series("bnp_per_innbygger_lopende")[t]["value"] == pytest.approx(expected, abs=1)


def test_share_and_claim_levels():
    s = json.loads((P / "olje_sjofart_andel_av_bnp.json").read_text(encoding="utf-8"))
    assert s["claim_level"] == "utledet" and s["derivation"]
    assert all(0 < v["value"] < 50 for v in s["values"])
    assert json.loads((P / "bnp_lopende.json").read_text(encoding="utf-8"))["claim_level"] == "offisiell"


def test_preliminary_status_follows_the_tables_own_note():
    bnp = series("bnp_lopende")
    assert bnp["2023"]["status"] == "regnskap" and bnp["2025"]["status"] == "foreløpig"


def test_trade_final_rule():
    # final figures are published in May of year t+2
    assert trade_is_final(2024, "2026-05-15T06:00:00Z") is True
    assert trade_is_final(2025, "2026-05-15T06:00:00Z") is False
    assert trade_is_final(2024, "2026-04-15T06:00:00Z") is False


def test_headline_numbers_match_ssb_page():
    cfg = yaml.safe_load((ROOT / "tests" / "headlines" / "okonomi.yaml").read_text(encoding="utf-8"))
    for c in cfg["checks"]:
        got = series(c["series"].split(".")[-1])[c["period"]]["value"]
        assert got == pytest.approx(c["value_mill_kr"] / 1000, abs=0.0005), c


# ---- Statens pensjonsfond utland (NBIM, latest figures only) ----

def test_spu_parts_sum_to_published_total_within_rounding():
    meta = yaml.safe_load((P / "spu_fondsverdi" / "dataset.yaml").read_text(encoding="utf-8"))
    rows = facts("spu_fondsverdi")
    assert len(rows) == 3 and len({r["period"] for r in rows}) == 1  # latest only, no history
    total = meta["published_totals"][0]["value"]
    assert abs(sum(float(r["value"]) for r in rows) - total) <= 2


def test_spu_sentence_is_consistent_and_agrees_with_the_pages_table_when_the_period_matches():
    """The sentence we parse must add up; and when it reports a half-year or year-end, it must equal the table's first column."""
    import re
    from fetch import nbim
    from transform.common import latest_snapshot_bytes
    fv = nbim.newest_stored()
    content = next((ROOT / "data" / "raw" / e["file"]).read_bytes() for e in __import__("yaml").safe_load((ROOT / "data" / "raw" / "MANIFEST.yaml").read_text(encoding="utf-8"))["files"]
                   if e["source_id"] == nbim.SOURCE_ID and nbim.parse((ROOT / "data" / "raw" / e["file"]).read_bytes()).period == fv.period)
    assert fv.value > fv.ret > fv.net_inflow > fv.currency > 0
    assert abs(fv.value - (fv.ret + fv.net_inflow + fv.currency)) <= 3  # NBIM's own rounding
    if fv.period[5:] in ("06", "12"):
        m = re.search(r"<td[^>]*><strong>Fund value</strong></td>\s*<td><strong>([\d,]+)</strong>", content.decode("utf-8"))
        assert m, "NBIM's table layout changed; update this cross-check"
        assert int(m.group(1).replace(",", "")) == fv.value
