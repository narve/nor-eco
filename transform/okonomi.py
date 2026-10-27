"""WS2 Økonomi: raw SSB snapshots -> data/processed/okonomi/.

Series (plain): BNP, BNP Fastlands-Norge, oljevirksomhet og utenriks sjøfart (løpende og faste priser),
volumvekst, trade balance with/without råolje og naturgass, population, per-capita and shares (utledet).
Datasets (hierarchical): exports (løpende, faste), imports (løpende), goods exports of oil/gas/condensate.
"""

from __future__ import annotations

from pathlib import Path

from fetch import nbim
from fetch.common import JsonStat

from .common import PROCESSED, latest_snapshot, latest_snapshot_bytes, mrd, preliminary_after_year, write_dataset, write_series

TOPIC = "okonomi"
NA, TRADE, POP = "ssb-09189", "ssb-08800", "ssb-06913"
BASE_YEAR = 2023  # basis year of the fixed prices in table 09189 (stated in the table's contents code label)

NA_CODES = {
    "bnp": "bnpb.nr23_9",
    "bnp_fastland": "bnpb.nr23_9fn",
    "olje_sjofart": "bnpb.nr23oljsj",
    "eks_tot": "eks.nrtot", "eks_trad": "eks.nrtradvare", "eks_olje": "eks.puboljegs",
    "eks_skip": "eks.nrskiplfly", "eks_tjen": "eks.nrtjen",
    "imp_tot": "imp.nrtot", "imp_trad": "imp.nrtradvare", "imp_olje": "imp.puboljegs",
    "imp_skip": "imp.nrskiplfly", "imp_tjen": "imp.nrtjen",
}


def _na(js: JsonStat) -> dict[tuple[str, str, str], float]:
    """{(key, ContentsCode, year): value} for table 09189."""
    inv = {v: k for k, v in NA_CODES.items()}
    return {(inv[r["Makrost"]], r["ContentsCode"], r["Tid"]): r["value"] for r in js.rows()}


def trade_is_final(year: int, updated: str) -> bool:
    """Table 08800: first published January t+1, revised May t+1, final figures May t+2."""
    uy, um = int(updated[:4]), int(updated[5:7])
    return year + 2 < uy or (year + 2 == uy and um >= 5)


def _series(sid, title, unit, values, *, source_ids, claim="offisiell", price_basis="ikke-relevant", base_year=None,
            derivation=None, vintage=None, notes=None, breaks=None):
    s = {"id": f"{TOPIC}.{sid}", "title": title, "unit": unit, "price_basis": price_basis}
    if base_year:
        s["base_year"] = base_year
    s["claim_level"] = claim
    if derivation:
        s["derivation"] = derivation
    s["source_ids"] = source_ids
    if vintage:
        s["vintage"] = vintage[:10]
    s["values"] = values
    if notes:
        s["notes"] = notes
    if breaks:
        s["breaks"] = breaks
    return s


def run(out: Path = PROCESSED) -> None:
    na_js, na_e = latest_snapshot(NA)
    na = _na(na_js)
    years = sorted({t for (_, _, t) in na})
    prelim_after = preliminary_after_year(na_js.notes)
    na_status = {t: ("foreløpig" if int(t) > prelim_after else "regnskap") for t in years}
    vint = na_js.updated

    def na_series(key, cc):
        return [{"period": t, "value": na[(key, cc, t)], "status": na_status[t]} for t in years if (key, cc, t) in na]

    def mrd_series(key, cc):
        return [{**v, "value": mrd(v["value"])} for v in na_series(key, cc)]

    # ---- official series: BNP, BNP Fastland, olje og utenriks sjøfart ----
    labels = {"bnp": "BNP, markedsverdi", "bnp_fastland": "BNP Fastlands-Norge, markedsverdi",
              "olje_sjofart": "Oljevirksomhet og utenriks sjøfart"}
    for key, label in labels.items():
        write_series(TOPIC, _series(f"{key}_lopende", f"{label}, løpende priser", "mrd. kr", mrd_series(key, "Priser"),
                                    source_ids=[NA], price_basis="løpende", vintage=vint), out)
        write_series(TOPIC, _series(f"{key}_faste", f"{label}, faste {BASE_YEAR}-priser", "mrd. kr", mrd_series(key, "Faste"),
                                    source_ids=[NA], price_basis="faste", base_year=BASE_YEAR, vintage=vint,
                                    notes="Kjedede faste priser: delene summerer ikke til totalen (kjedingsavvik), så forskjellen mellom BNP og BNP Fastlands-Norge i faste priser er ikke lik oljevirksomhet og utenriks sjøfart."), out)
    for key, label in (("bnp", "BNP"), ("bnp_fastland", "BNP Fastlands-Norge")):
        write_series(TOPIC, _series(f"{key}_volumvekst", f"{label}, volumendring fra året før", "prosent", na_series(key, "Volum"),
                                    source_ids=[NA], vintage=vint), out)

    # ---- population and per capita (utledet) ----
    pop_js, pop_e = latest_snapshot(POP)
    pop = {r["Tid"]: r["value"] for r in pop_js.rows()}
    write_series(TOPIC, _series("befolkning_1_januar", "Befolkning 1. januar, hele landet", "personer",
                                [{"period": t, "value": v} for t, v in sorted(pop.items())], source_ids=[POP],
                                vintage=pop_js.updated), out)
    per_cap_years = [t for t in years if str(int(t) + 1) in pop and t in pop]
    avg_pop = {t: (pop[t] + pop[str(int(t) + 1)]) / 2 for t in per_cap_years}
    for key, label in (("bnp", "BNP"), ("bnp_fastland", "BNP Fastlands-Norge")):
        for cc, pb, tag, extra in (("Priser", "løpende", "lopende", "løpende priser"), ("Faste", "faste", "faste", f"faste {BASE_YEAR}-priser")):
            vals = [{"period": t, "value": round(na[(key, cc, t)] * 1_000_000 / avg_pop[t]), "status": na_status[t]} for t in per_cap_years]
            write_series(TOPIC, _series(f"{key}_per_innbygger_{tag}", f"{label} per innbygger, {extra}", "kr per innbygger", vals,
                                        source_ids=[NA, POP], claim="utledet", price_basis=pb,
                                        base_year=BASE_YEAR if pb == "faste" else None,
                                        derivation=f"{label} ({extra}, mill. kr) × 1 000 000 / gjennomsnitt av folkemengden 1. januar i året og 1. januar året etter (tilnærming til gjennomsnittsbefolkning)",
                                        vintage=vint), out)

    # ---- shares and trade balance (utledet, løpende priser only) ----
    share = [{"period": t, "value": round(100 * na[("olje_sjofart", "Priser", t)] / na[("bnp", "Priser", t)], 2), "status": na_status[t]} for t in years]
    write_series(TOPIC, _series("olje_sjofart_andel_av_bnp", "Oljevirksomhet og utenriks sjøfart som andel av BNP, løpende priser", "prosent", share,
                                source_ids=[NA], claim="utledet", price_basis="løpende",
                                derivation="Oljevirksomhet og utenriks sjøfart / BNP (begge løpende priser) × 100. Beregnes ikke i faste priser fordi kjedede faste priser ikke summerer.",
                                vintage=vint), out)
    bal_all = [{"period": t, "value": mrd(na[("eks_tot", "Priser", t)] - na[("imp_tot", "Priser", t)]), "status": na_status[t]} for t in years]
    bal_ex = [{"period": t, "value": mrd((na[("eks_tot", "Priser", t)] - na[("eks_olje", "Priser", t)]) - (na[("imp_tot", "Priser", t)] - na[("imp_olje", "Priser", t)])),
               "status": na_status[t]} for t in years]
    write_series(TOPIC, _series("handelsbalanse_i_alt", "Handelsbalanse (eksport minus import), alle varer og tjenester", "mrd. kr", bal_all,
                                source_ids=[NA], claim="utledet", price_basis="løpende",
                                derivation="Eksport i alt − import i alt, løpende priser (nasjonalregnskapet)", vintage=vint), out)
    write_series(TOPIC, _series("handelsbalanse_uten_olje_gass", "Handelsbalanse uten råolje og naturgass", "mrd. kr", bal_ex,
                                source_ids=[NA], claim="utledet", price_basis="løpende",
                                derivation="(Eksport i alt − eksport av råolje og naturgass) − (import i alt − import av råolje og naturgass), løpende priser (nasjonalregnskapet)",
                                vintage=vint), out)

    # ---- hierarchical datasets: exports/imports by type ----
    parts = [("tradisjonelle_varer", "Tradisjonelle varer", "trad"), ("rolje_naturgass", "Råolje og naturgass", "olje"),
             ("skip_plattformer_fly", "Skip, plattformer og fly", "skip"), ("tjenester", "Tjenester", "tjen")]
    olje_def = ("I publiseringen av tall for utenrikshandelen med varer gir vi tall for råolje, naturgass og naturlige gasskondensater, "
                "mens utenriksregnskapet bruker samlebegrepet ”råolje og naturgass” for varene råolje, naturgass, naturlige gasskondensater, nafta, propan og butan.")

    def dims_for(root_code, root_label, leaves, extra=()):
        nodes = [{"code": root_code, "label": root_label, "parent": None}]
        for code, label, *rest in leaves:
            n = {"code": code, "label": label, "parent": root_code}
            n.update(rest[0] if rest else {})
            nodes.append(n)
        nodes += list(extra)
        return nodes

    def na_dataset(name, title, flow, cc, pb, root_label):
        rows, totals = [], []
        for t in years:
            vals = {c: na[(f"{flow}_{k}", cc, t)] for c, _, k in parts}
            tot = na[(f"{flow}_tot", cc, t)]
            for c, v in vals.items():
                rows.append({"period": t, "value": mrd(v), "unit": "mrd. kr", "status": na_status[t], "vare": c,
                             "claim_level": "offisiell", "source_id": NA})
            resid = tot - sum(vals.values())
            if cc == "Faste":  # chain-linking: the residual is shown, never hidden
                rows.append({"period": t, "value": mrd(resid), "unit": "mrd. kr", "status": na_status[t], "vare": "kjedingsavvik",
                             "claim_level": "utledet", "source_id": NA})
            totals.append({"period": t, "status": na_status[t], "value": mrd(tot), "source_id": NA})
        leaves = [(c, l, {"definition": olje_def, "source_id": "ssb-utenrikshandel-varer-om"} if c == "rolje_naturgass" else {}) for c, l, _ in parts]
        extra = []
        if cc == "Faste":
            extra = [{"code": "kjedingsavvik", "label": "Kjedingsavvik (differanse i kjedede faste priser)", "parent": f"{flow}_i_alt", "other": True,
                      "definition": "De enkelte tallene i faste priser summerer seg ikke opp til del- og totalsummene på grunn av kjedingsavvik.",
                      "source_id": NA}]
        meta = {"id": f"{TOPIC}.{name}", "title": title, "unit": "mrd. kr", "price_basis": pb, **({"base_year": BASE_YEAR} if pb == "faste" else {}),
                "claim_level": "offisiell", "source_ids": [NA], "dimensions": ["vare"], "default_dimension": "vare",
                "published_totals": totals, "tolerance": 0.001,
                "notes": "Nasjonalregnskapets inndeling. Totalen er publisert av SSB; i løpende priser kan avrunding gi avvik på 1 mill. kr."
                         + (" I faste priser er kjedingsavviket tatt med som egen post (utledet: total minus summen av delene)." if cc == "Faste" else "")}
        dims = {"vare": {"label": "Type", "nodes": dims_for(f"{flow}_i_alt", root_label, leaves, extra)}}
        write_dataset(TOPIC, name, meta, dims, rows, out)

    na_dataset("eksport_lopende", "Eksport av varer og tjenester, løpende priser", "eks", "Priser", "løpende", "Eksport i alt")
    na_dataset("eksport_faste", f"Eksport av varer og tjenester, faste {BASE_YEAR}-priser", "eks", "Faste", "faste", "Eksport i alt")
    na_dataset("import_lopende", "Import av varer og tjenester, løpende priser", "imp", "Priser", "løpende", "Import i alt")

    # ---- goods exports of crude oil, natural gas and condensate (trade statistics, 08800) ----
    tr_js, tr_e = latest_snapshot(TRADE)
    tr = {(r["HovedVareStrommer"], r["Tid"]): r["value"] for r in tr_js.rows()}
    tr_years = sorted({t for (_, t) in tr})
    tr_status = {t: ("regnskap" if trade_is_final(int(t), tr_js.updated) else "foreløpig") for t in tr_years}
    leaves = [("rolje", "Råolje", "Eolje"), ("naturgass", "Naturgass", "Egass"), ("kondensat", "Naturlige gasskondensater", "Ekondens")]
    rows, totals = [], []
    for t in tr_years:
        for c, _, k in leaves:
            if (k, t) in tr:  # SSB marks years without condensate exports as «-» (null); no fact is written
                rows.append({"period": t, "value": mrd(tr[(k, t)]), "unit": "mrd. kr", "status": tr_status[t], "vare": c,
                             "claim_level": "offisiell", "source_id": TRADE})
        totals.append({"period": t, "status": tr_status[t], "value": mrd(tr[("Eoljegass", t)]), "source_id": TRADE})
    meta = {"id": f"{TOPIC}.vareeksport_olje_gass_lopende", "title": "Eksport av råolje, naturgass og kondensater (varehandelsstatistikken), løpende priser",
            "unit": "mrd. kr", "price_basis": "løpende", "claim_level": "offisiell", "source_ids": [TRADE], "dimensions": ["vare"],
            "default_dimension": "vare", "published_totals": totals, "tolerance": 0.001,
            "notes": "Utenrikshandelsstatistikken for varer. Omfatter ikke nafta, propan og butan, som nasjonalregnskapets «råolje og naturgass» omfatter. Kondensat er ikke oppgitt (null) for 1990–2000."}
    dims = {"vare": {"label": "Vare", "nodes": dims_for("olje_gass_kondensat", "Råolje, naturgass og kondensater", [(c, l) for c, l, _ in leaves])}}
    write_dataset(TOPIC, "vareeksport_olje_gass_lopende", meta, dims, rows, out)


def spu(out: Path = PROCESSED) -> None:
    """Statens pensjonsfond utland: only the latest figures, as stated in NBIM's own sentence (no history)."""
    content, entry = latest_snapshot_bytes(nbim.SOURCE_ID)
    fv = nbim.parse(content)
    parts = [("netto_tilforsel", "Netto tilførsel fra staten (akkumulert)", fv.net_inflow),
             ("avkastning", "Avkastning (akkumulert)", fv.ret),
             ("kronekurs", "Endringer på grunn av kronekurs (akkumulert)", fv.currency)]
    rows = [{"period": fv.period, "value": v, "unit": "mrd. kr", "status": "foreløpig", "komponent": c,
             "claim_level": "offisiell", "source_id": nbim.SOURCE_ID} for c, _, v in parts]
    meta = {"id": f"{TOPIC}.spu_fondsverdi", "title": "Statens pensjonsfond utland: fondets verdi, siste tall", "unit": "mrd. kr",
            "price_basis": "løpende", "claim_level": "offisiell", "source_ids": [nbim.SOURCE_ID], "dimensions": ["komponent"],
            "default_dimension": "komponent",
            "published_totals": [{"period": fv.period, "status": "foreløpig", "value": fv.value, "source_id": nbim.SOURCE_ID}],
            "tolerance": 0.0001,
            "notes": "Siste halvårstall fra NBIM; ingen historikk. Delene er avrundet av NBIM og kan avvike fra totalen med 1 mrd. kr."}
    dims = {"komponent": {"label": "Komponent", "nodes": [{"code": "fondsverdi", "label": "Fondets verdi", "parent": None}]
                          + [{"code": c, "label": l, "parent": "fondsverdi"} for c, l, _ in parts]}}
    write_dataset(TOPIC, "spu_fondsverdi", meta, dims, rows, out)
