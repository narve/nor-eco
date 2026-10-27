"""WS3 Sysselsetting: raw SSB snapshots -> data/processed/sysselsetting/.

- registerstatus_<age>: SSB's register-based priority status (table 12423) for residents 15-74 and 20-66, by status x sex.
  Every person has one status (employed persons also carry their second-highest status), so all leaves are a
  partition; the leaves that combine two statuses carry `overlap` so a view can draw them striped.
- aku_<age>: the labour-force survey (13618), 1000 persons, break-adjusted, by status x sex.
- series: employed and unemployed in AKU vs the register (same unit, 1000 persons), AKU margins of error,
  persons / man-years / hours worked from the national accounts.
Both survey and register start in 2015 (a-ordningen replaced the Aa- and LTO-registers).
"""

from __future__ import annotations

import re
from pathlib import Path

from .common import PROCESSED, latest_snapshot, preliminary_after_year, write_dataset, write_series

TOPIC = "sysselsetting"
REG, AKU, NA = "ssb-12423", "ssb-13618", "ssb-09174"
REG_OM, AKU_OM = "ssb-arbstatus-om", "ssb-aku-om"
SEX = [("2", "Kvinner"), ("1", "Menn")]

# register status tree: (code, children | None, overlap)
EMPLOYED_LEAVES = [("A.01x00", []), ("A.01xU03", ["U.03.00"]), ("A.01xU04", ["U.04.00"]), ("A.01xU05", ["U.05.00"]), ("A.01xU06-07", ["U.06.00", "U.07.00"]), ("A.01.90A", [])]
OUTSIDE_LEAVES = ["U.01.00", "U.03.00", "U.04.00", "U.05.00", "U.06.00", "U.07.00", "U.90A.00", "UX.00"]
# Wording for nodes where SSB's own label is long or unclear; definitions are quoted from SSB's «Om statistikken»
NODE_DEF = {
    "A.01": ("«Sysselsatte» i registerstatistikken", "ssb-arbstatus-om"),
    "A.09.00": ("Registrerte arbeidsledige", "ssb-arbstatus-om"),
}
AGES = {"15-74": "15–74 år", "20-66": "20–66 år"}


def _clean(s: str) -> str:
    return " ".join(s.split())


def _last_year_preliminary(notes: list[str]) -> bool:
    if not any(re.search(r"Tallene for siste årgang er foreløpige", n) for n in notes):
        raise ValueError("table 12423 no longer says the last year is preliminary; check the notes and update the transform")
    return True


def register(out: Path = PROCESSED) -> dict:
    js, entry = latest_snapshot(REG)
    _last_year_preliminary(js.notes)
    lab = next(d for d in js.dimensions if d.id == "HovArbStyrkStatus").labels
    V = {(r["Alder"], r["Kjonn"], r["HovArbStyrkStatus"], r["Tid"]): r["value"] for r in js.rows()}
    years = sorted({t for (_, _, _, t) in V})
    last = years[-1]
    leaves = [c for c, _ in EMPLOYED_LEAVES] + ["A.09.00"] + OUTSIDE_LEAVES
    for age, age_label in AGES.items():
        nodes = [{"code": "TOT", "label": f"Bosatte {age_label}", "parent": None},
                 {"code": "A", "label": "Arbeidsstyrken", "parent": "TOT"},
                 {"code": "A.01", "label": "Sysselsatte", "parent": "A", "definition": "Se definisjonen av sysselsatte i SSBs registerstatistikk (sitat på siden).", "source_id": REG_OM}]
        for code, ov in EMPLOYED_LEAVES:
            n = {"code": code, "label": _clean(lab[code]), "parent": "A.01"}
            if ov:
                n["overlap"] = ov
            nodes.append(n)
        nodes += [{"code": "A.09.00", "label": "Registrerte arbeidsledige (Nav)", "parent": "A", "source_id": REG_OM},
                  {"code": "U", "label": "Utenfor arbeidsstyrken", "parent": "TOT"}]
        nodes += [{"code": c, "label": _clean(lab[c]), "parent": "U"} for c in OUTSIDE_LEAVES]
        rows = []
        for t in years:
            for sex, _ in SEX:
                for c in leaves:
                    v = V.get((age, sex, c, t))
                    if v is None:
                        raise ValueError(f"missing cell {age} {sex} {c} {t} in table 12423")
                    rows.append({"period": t, "value": v, "unit": "personer", "status": "foreløpig" if t == last else "regnskap", "status_": None,
                                 "statusgruppe": c, "kjonn": sex, "claim_level": "offisiell", "source_id": REG})
        meta = {"id": f"{TOPIC}.registerstatus_{age.replace('-', '_')}", "title": f"Befolkningen {age_label} etter prioritert arbeidsstyrkestatus (registerbasert)", "unit": "personer",
                "price_basis": "ikke-relevant", "claim_level": "offisiell", "source_ids": [REG], "dimensions": ["statusgruppe", "kjonn"], "default_dimension": "statusgruppe",
                "published_totals": [{"period": t, "status": "foreløpig" if t == last else "regnskap", "value": V[(age, "0", "TOT", t)], "source_id": REG} for t in years],
                "tolerance": 0.0005,
                "notes": "Registerbasert, én status per person: for personer som er aktive i flere statuser vises den høyest prioriterte (for sysselsatte de to høyest prioriterte). SSB avrunder celler med én eller to personer til null eller tre, så summen kan avvike litt fra totalen. Tall for siste år er foreløpige. Serien starter i 2015, da a-ordningen erstattet Aa- og LTO-registrene.",
                "breaks": [{"period": years[0], "note": "Serien starter i 2015, da a-ordningen erstattet Aa- og LTO-registrene.", "source_id": REG_OM}]}
        dims = {"statusgruppe": {"label": "Status", "nodes": nodes},
                "kjonn": {"label": "Kjønn", "nodes": [{"code": "0", "label": "Begge kjønn", "parent": None}] + [{"code": c, "label": l, "parent": "0"} for c, l in SEX]}}
        for r in rows:
            r.pop("status_")
        write_dataset(TOPIC, f"registerstatus_{age.replace('-', '_')}", meta, dims, rows, out)
    return {"years": years, "last": last, "V": V}


def aku(out: Path = PROCESSED) -> dict:
    js, entry = latest_snapshot(AKU)
    labs = js.dimensions[0].labels
    V = {(r["Alder"], r["Kjonn"], r["ArbStyrkStatus"], r["ContentsCode"], r["Tid"]): r["value"] for r in js.rows()}
    years = sorted({t for (*_, t) in V})
    for age, age_label in AGES.items():
        rows = [{"period": t, "value": V[(age, sex, c, "Personer", t)], "unit": "1000 personer", "status": "regnskap", "statusgruppe": c, "kjonn": sex,
                 "claim_level": "offisiell", "source_id": AKU} for t in years for sex, _ in SEX for c in ("1", "2", "6")]
        meta = {"id": f"{TOPIC}.aku_{age.replace('-', '_')}", "title": f"AKU: personer {age_label} etter arbeidsstyrkestatus", "unit": "1000 personer", "price_basis": "ikke-relevant",
                "claim_level": "offisiell", "source_ids": [AKU], "dimensions": ["statusgruppe", "kjonn"], "default_dimension": "statusgruppe",
                "published_totals": [{"period": t, "status": "regnskap", "value": V[(age, "0", "99", "Personer", t)], "source_id": AKU} for t in years], "tolerance": 0.002,
                "notes": "Utvalgsundersøkelse: tallene er anslag med feilmargin. Bruddjustert for omleggingen mellom 2020 og 2021; for undergrupper bygger justeringen på en forutsetning om proporsjonal fordeling og bør tolkes varsomt.",
                "breaks": [{"period": "2021", "note": "Brudd mellom 2020 og 2021 (omlegging av AKU). Tallene før 2021 er justert til nivået etter bruddet.", "source_id": AKU_OM}]}
        nodes = [{"code": "99", "label": f"Personer {age_label}", "parent": None},
                 {"code": "0", "label": "Arbeidsstyrken", "parent": "99"},
                 {"code": "1", "label": "Sysselsatte", "parent": "0"}, {"code": "2", "label": "Arbeidsledige", "parent": "0"},
                 {"code": "6", "label": "Utenfor arbeidsstyrken", "parent": "99"}]
        dims = {"statusgruppe": {"label": "Status", "nodes": nodes},
                "kjonn": {"label": "Kjønn", "nodes": [{"code": "0", "label": "Begge kjønn", "parent": None}] + [{"code": c, "label": l, "parent": "0"} for c, l in SEX]}}
        write_dataset(TOPIC, f"aku_{age.replace('-', '_')}", meta, dims, rows, out)
    # margins of error (95 %), 15-74, both sexes
    for code, sid, title in (("1", "aku_sysselsatte_feilmargin", "AKU: feilmargin for sysselsatte"), ("2", "aku_arbeidsledige_feilmargin", "AKU: feilmargin for arbeidsledige")):
        write_series(TOPIC, {"id": f"{TOPIC}.{sid}", "title": f"{title} (± på 95 %-nivå)", "unit": "1000 personer", "price_basis": "ikke-relevant", "claim_level": "offisiell",
                             "source_ids": [AKU], "values": [{"period": t, "value": V[("15-74", "0", code, "Feilmargin", t)], "status": "regnskap"} for t in years if V.get(("15-74", "0", code, "Feilmargin", t)) is not None],
                             "notes": "Feilmarginer er publisert fra 2021 (etter omleggingen); tidligere år er ikke oppgitt. Et estimat på 100 000 med feilmargin ±12 000 har et 95 %-konfidensintervall fra 88 000 til 112 000."}, out)
    return {"years": years, "V": V}


def comparison(reg: dict, ak: dict, out: Path = PROCESSED) -> None:
    last = reg["last"]
    def reg_series(code, sid, title):
        write_series(TOPIC, {"id": f"{TOPIC}.{sid}", "title": title, "unit": "1000 personer", "price_basis": "ikke-relevant", "claim_level": "utledet",
                             "derivation": f"Antall personer i registerstatistikken (tabell 12423, {code}) delt på 1 000, 15–74 år, begge kjønn",
                             "source_ids": [REG], "values": [{"period": t, "value": round(reg["V"][("15-74", "0", code, t)] / 1000, 3), "status": "foreløpig" if t == last else "regnskap"} for t in reg["years"]]}, out)
    reg_series("A.01", "sysselsatte_register_tusen", "Sysselsatte 15–74 år, registerbasert")
    reg_series("A.09", "ledige_register_tusen", "Registrerte arbeidsledige 15–74 år (Nav), registerbasert")
    for code, sid, title in (("1", "sysselsatte_aku_tusen", "Sysselsatte 15–74 år, AKU"), ("2", "ledige_aku_tusen", "Arbeidsledige 15–74 år, AKU")):
        write_series(TOPIC, {"id": f"{TOPIC}.{sid}", "title": title, "unit": "1000 personer", "price_basis": "ikke-relevant", "claim_level": "offisiell", "source_ids": [AKU],
                             "values": [{"period": t, "value": ak["V"][("15-74", "0", code, "Personer", t)], "status": "regnskap"} for t in ak["years"]]}, out)


def national_accounts(out: Path = PROCESSED) -> None:
    js, entry = latest_snapshot(NA)
    after = preliminary_after_year(js.notes)
    V = {(r["ContentsCode"], r["Tid"]): r["value"] for r in js.rows()}
    years = sorted({t for (_, t) in V})
    st = {t: ("foreløpig" if int(t) > after else "regnskap") for t in years}
    for code, sid, title, unit in (("Sysselsatte", "sysselsatte_personer_na", "Sysselsatte personer (lønnstakere og selvstendige), nasjonalregnskapet", "1000 personer"),
                                   ("SysselsattNorm", "arsverk_na", "Årsverk (heltidsekvivalenter), nasjonalregnskapet", "1000 årsverk"),
                                   ("Timeverk", "timeverk_na", "Utførte timeverk, nasjonalregnskapet", "mill. timeverk")):
        write_series(TOPIC, {"id": f"{TOPIC}.{sid}", "title": title, "unit": unit, "price_basis": "ikke-relevant", "claim_level": "offisiell", "source_ids": [NA],
                             "vintage": js.updated[:10], "values": [{"period": t, "value": V[(code, t)], "status": st[t]} for t in years]}, out)
    write_series(TOPIC, {"id": f"{TOPIC}.arsverk_per_sysselsatt", "title": "Årsverk per sysselsatt person", "unit": "årsverk per person", "price_basis": "ikke-relevant",
                         "claim_level": "utledet", "derivation": "Årsverk (heltidsekvivalenter) delt på sysselsatte personer, begge fra nasjonalregnskapet (tabell 09174)",
                         "source_ids": [NA], "vintage": js.updated[:10],
                         "values": [{"period": t, "value": round(V[("SysselsattNorm", t)] / V[("Sysselsatte", t)], 3), "status": st[t]} for t in years]}, out)


def run(out: Path = PROCESSED) -> None:
    reg = register(out)
    ak = aku(out)
    comparison(reg, ak, out)
    national_accounts(out)
