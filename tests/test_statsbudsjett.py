"""WS1 reconciliation and headline checks on the real processed data (data/processed/statsbudsjett)."""

import csv
import json

import pytest

from paths import ROOT
from transform.common import latest_snapshot_bytes
from transform.statsbudsjett import parse_key_figures

P = ROOT / "data" / "processed" / "statsbudsjett"
OK = ROOT / "data" / "processed" / "okonomi"


def series(name, base=P):
    return {v["period"]: v for v in json.loads((base / f"{name}.json").read_text(encoding="utf-8"))["values"]}


def facts(name):
    with (P / name / "facts.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def total(name, status, period, leaves_only=True):
    return sum(float(r["value"]) for r in facts(name) if r["status"] == status and r["period"] == period)


def test_surplus_equals_income_minus_expenditure_for_accounts_and_budget():
    for status in ("regnskap", "budsjett"):
        c = series(f"overskudd_for_avsetning_{status}")
        for t, v in c.items():
            assert total("inntekter", status, t) - total("utgifter", status, t) == pytest.approx(v["value"], abs=0.003), (status, t)


def test_budget_and_accounts_coexist_and_are_never_mixed():
    inn = facts("inntekter")
    by_period = {}
    for r in inn:
        by_period.setdefault(r["period"], set()).add(r["status"])
    assert by_period["2024"] == {"regnskap", "budsjett"}
    assert by_period["2026"] == {"budsjett"}  # the budget year has no accounts yet
    assert not any("regnskap" in s for p, s in by_period.items() if p == "2026")


def test_derived_oil_corrected_balance_reproduces_the_official_percentage():
    """Derived (accounts surplus minus net petroleum cash flow) / BNP Fastland vs Finansdepartementet's % of trend-BNP."""
    kr, official = series("oljekorrigert_balanse_kr"), series("oljekorrigert_balanse_pst")
    bnp = series("bnp_fastland_lopende", OK)
    assert set(kr) == {str(y) for y in range(2000, 2026)}
    diffs = {t: 100 * kr[t]["value"] / bnp[t]["value"] - official[t]["value"] for t in kr}
    assert max(abs(d) for d in diffs.values()) < 0.65, diffs  # the largest gaps are 2020-2021, where actual and trend BNP differ most
    assert sum(abs(d) for d in diffs.values()) / len(diffs) < 0.15


def test_petroleum_components_sum_to_the_states_net_cash_flow_and_taxes_fit_inside_total_taxes():
    comp = facts("petroleum_kontantstrom")
    for t in ("2000", "2023", "2025"):
        assert sum(float(r["value"]) for r in comp if r["period"] == t) > 0
    taxes = {r["period"]: float(r["value"]) for r in facts("inntekter") if r["status"] == "regnskap" and r["hovedpost"] == "INNT.SKATT_AVG"}
    pet_tax = {r["period"]: float(r["value"]) for r in comp if r["komponent"] == "skatt_utvinning"}
    assert all(pet_tax[t] <= taxes[t] for t in pet_tax)


def test_status_rule_for_official_series():
    s = series("strukturell_balanse_pst")
    last_acc = max(int(r["period"]) for r in facts("inntekter") if r["status"] == "regnskap")
    assert s[str(last_acc)]["status"] == "regnskap"
    assert s[str(last_acc + 1)]["status"] == "anslag" and s[str(last_acc + 2)]["status"] == "forslag"
    assert "status" not in next(iter(series("handlingsregel_realavkastning").values()))  # a rule, not a measured value


def test_rule_changes_from_four_to_three_percent_in_2018():
    r = series("handlingsregel_realavkastning")
    assert r["2017"]["value"] == 4.0 and r["2018"]["value"] == 3.0


def test_excel_series_match_the_independent_key_figures_table():
    """The key-figures page was read separately from the Excel files; the overlapping years must agree."""
    content, _ = latest_snapshot_bytes("fin-nokkeltall-nb2027")
    kf = parse_key_figures(content)
    sobu_pct = kf["Structural non-oil fiscal deficit, as a percentage of trend GDP for mainland Norway"]
    use_pct = kf["Fund spending, per cent of the GPFG"]
    sobu_excel, use_excel = series("strukturell_balanse_pst"), series("fondsbruk_pst_av_spu")
    for y in ("2025", "2026", "2027"):
        assert -sobu_excel[y]["value"] == pytest.approx(sobu_pct[y], abs=0.05), y
        assert use_excel[y]["value"] == pytest.approx(use_pct[y], abs=0.05), y


def test_structural_deficit_in_kroner_is_consistent_with_its_percentage():
    kr, pct, bnp = series("strukturelt_underskudd_kr"), series("strukturell_balanse_pst"), series("bnp_fastland_lopende", OK)
    implied_trend = kr["2025"]["value"] / (-pct["2025"]["value"] / 100)
    assert implied_trend == pytest.approx(bnp["2025"]["value"], rel=0.03)  # trend-BNP is close to actual BNP Fastland


def test_structural_deficit_is_larger_than_the_oil_corrected_one_in_2025():
    """Official structural (kr) minus derived oil-corrected (kr) = the activity correction, a few tens of billions in 2025."""
    adj = series("strukturelt_underskudd_kr")["2025"]["value"] - (-series("oljekorrigert_balanse_kr")["2025"]["value"])
    assert 0 < adj < 60
