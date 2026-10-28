"""WS4 Staten som arbeidsgiver: raw snapshots -> data/processed/staten/.

- sektorer: SSB 13472, employed persons by workplace in 4th quarter, by sector (a partition of all employed).
- selskaper: Statens eierrapport 2025, employees of the companies in category 1 and 2 (the group's employees, not weighted).
- selskaper_vektet: the same, times the state's ownership share (an estimate).
- ringer: the narrow rings 1-4 side by side, each from its own source (no common measure; see the dataset notes).
- series: SSB 12623 (employees in the state, annual average) and its comparison with the sector table.
"""

from __future__ import annotations

import html
import re
import unicodedata
from pathlib import Path

from .common import PROCESSED, latest_snapshot, latest_snapshot_bytes, write_dataset, write_series

TOPIC = "staten"
EMP, SEC, EIER = "ssb-12623", "ssb-13472", "nfd-eierrapport-2025"
# (SSB code, our node code, label); SSB's sector codes contain «+», which node codes may not
SECTORS = [("6100", "STAT", "Statsforvaltningen (inkl. helseforetak)"), ("6500.6", "KOMM", "Kommunal forvaltning"), ("6500.7", "FYLK", "Fylkeskommunal forvaltning"),
           ("A+B+D+E.5-7", "OFFF", "Offentlig eide foretak"), ("A+B+D+E.0-1+9", "PRIV", "Privat sektor")]
RHF = ("Helse Sør-Øst RHF", "Helse Vest RHF", "Helse Midt-Norge RHF", "Helse Nord RHF")


def _int(s: str) -> int:
    return int(re.sub(r"[^\d-]", "", s))


def _share(s: str) -> float:
    return float(s.replace("%", "").replace("\xa0", "").replace(" ", "").replace(",", ".")) / 100


def _cells(row_html: str) -> list[str]:
    return [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", c)).split()) for c in re.findall(r"<t[hd].*?</t[hd]>", row_html, re.S)]


def parse_eierrapport(content: bytes) -> dict:
    """The three company tables: {'listed'|'unlisted'|'cat2': {'rows': [(name, share, employees)], 'sum': employees}}, plus the category 1 sum."""
    text = content.decode("utf-8")
    want = {"Børsnoterte selskaper": "listed", "Unoterte selskaper": "unlisted", "Sektorpolitiske selskaper": "cat2"}
    out: dict = {}
    for table in re.findall(r"<table.*?</table>", text, re.S):
        rows = [_cells(r) for r in re.findall(r"<tr.*?</tr>", table, re.S)]
        rows = [r for r in rows if r]
        key = want.get(re.sub(r"\s+", " ", rows[0][0]).replace("Børsnoterte selskaper", "Børsnoterte selskaper")) if rows else None
        if key is None or key in out:
            continue
        if rows[0][-1] != "Antall ansatte" or rows[0][1] != "Statens eierandel":
            raise ValueError(f"columns of the {key} table in Statens eierrapport have changed: {rows[0]}")
        body, sums = [], {}
        for r in rows[1:]:
            if len(r) == len(rows[0]) and not r[0].startswith("Sum"):
                body.append((r[0], _share(r[1]), _int(r[-1])))
            elif r[0].startswith("Sum"):
                sums[r[0]] = _int(r[-1])
        out[key] = {"rows": body, "sum": sums}
    if set(out) != set(want.values()):
        raise ValueError(f"did not find all company tables in Statens eierrapport (found {sorted(out)})")
    return out


def _slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", name.lower().replace("æ", "ae").replace("ø", "o").replace("å", "a"))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40]


def _pct(x: float) -> str:
    return f"{x * 100:.4g}".replace(".", ",") + " %"


def sektorer(out: Path) -> dict:
    js, _ = latest_snapshot(SEC)
    V = {(r["Sektor"], r["Tid"]): r["value"] for r in js.rows()}
    years = sorted({t for (_, t) in V})
    rows = [{"period": t, "value": V[(c, t)], "unit": "personer", "status": "regnskap", "sektor": n, "claim_level": "offisiell", "source_id": SEC} for t in years for c, n, _ in SECTORS]
    meta = {"id": f"{TOPIC}.sektorer", "title": "Sysselsatte personer etter arbeidssted og sektor, 4. kvartal", "unit": "personer", "price_basis": "ikke-relevant", "claim_level": "offisiell",
            "source_ids": [SEC], "dimensions": ["sektor"], "default_dimension": "sektor",
            "published_totals": [{"period": t, "status": "regnskap", "value": V[("ALLE", t)], "source_id": SEC} for t in years], "tolerance": 0.0005,
            "notes": "Sysselsatte 15–74 år etter arbeidssted, 4. kvartal. Statsforvaltningen omfatter stats- og trygdeforvaltningen og inkluderer helseforetakene. Offentlig eide foretak omfatter foretak der det offentlige kontrollerer mer enn 50 prosent av aksjekapitalen, både statlig og kommunalt eide. SSB runder av celler med få personer, så summen kan avvike litt fra totalen."}
    dims = {"sektor": {"label": "Sektor", "nodes": [{"code": "ALLE", "label": "Alle sysselsatte", "parent": None}] + [{"code": n, "label": l, "parent": "ALLE"} for _, n, l in SECTORS]}}
    write_dataset(TOPIC, "sektorer", meta, dims, rows, out)
    return {"V": V, "years": years}


def selskaper(out: Path) -> dict:
    content, entry = latest_snapshot_bytes(EIER)
    t = parse_eierrapport(content)
    k1 = t["listed"]["rows"] + t["unlisted"]["rows"]
    cat2_rhf = [r for r in t["cat2"]["rows"] if r[0] in RHF]
    cat2_other = [r for r in t["cat2"]["rows"] if r[0] not in RHF]
    if len(cat2_rhf) != len(RHF):
        raise ValueError("the four regional health authorities are not all in the category 2 table")
    # reconcile with the report's own sums before writing anything
    for key, name in (("listed", "Sum børsnoterte selskaper"), ("unlisted", "Sum unoterte selskaper"), ("cat2", "Sum selskaper i kategori 2")):
        got, pub = sum(r[2] for r in t[key]["rows"]), t[key]["sum"][name]
        if got != pub:
            raise ValueError(f"{key}: companies sum to {got}, the report prints {pub}")
    cat1_pub = t["unlisted"]["sum"]["Sum alle selskaper i kategori 1"]
    if cat1_pub != sum(r[2] for r in k1):
        raise ValueError("category 1 sum does not match")
    groups = [("K1", "Kategori 1: høyest mulig avkastning", "TOT"), ("K1L", "Børsnoterte", "K1"), ("K1U", "Unoterte", "K1"), ("K2", "Kategori 2: sektorpolitiske mål", "TOT"),
              ("K2H", "Regionale helseforetak", "K2"), ("K2A", "Øvrige sektorpolitiske selskaper", "K2")]
    place = [(t["listed"]["rows"], "K1L"), (t["unlisted"]["rows"], "K1U"), (cat2_rhf, "K2H"), (cat2_other, "K2A")]
    nodes = [{"code": "TOT", "label": "Selskaper i kategori 1 og 2", "parent": None}] + [{"code": c, "label": l, "parent": p} for c, l, p in groups]
    facts, weighted = [], []
    for rows, parent in place:
        for name, share, n in rows:
            code = _slug(name)
            nodes.append({"code": code, "label": f"{name} ({_pct(share)})", "parent": parent})
            facts.append((code, n))
            weighted.append((code, round(n * share)))
    common = {"price_basis": "ikke-relevant", "source_ids": [EIER], "dimensions": ["selskap"], "default_dimension": "selskap"}
    mk = lambda vals, unit, claim: [{"period": "2025", "value": v, "unit": unit, "status": "foreløpig", "selskap": c, "claim_level": claim, "source_id": EIER} for c, v in vals]  # noqa: E731
    total = sum(v for _, v in facts)
    write_dataset(TOPIC, "selskaper", {**common, "id": f"{TOPIC}.selskaper", "title": "Ansatte i selskaper med statlig eierandel (kategori 1 og 2), 2025", "unit": "personer", "claim_level": "offisiell",
        "published_totals": [{"period": "2025", "status": "foreløpig", "value": cat1_pub + t["cat2"]["sum"]["Sum selskaper i kategori 2"], "source_id": EIER}], "tolerance": 0,
        "notes": "Antall ansatte i konsernet slik Statens eierrapport 2025 oppgir det, uten vekting med eierandel. Eierandelen står i parentes. Tallene i kategori 2-tabellen omtales i rapporten som anslag som senere kan bli revidert. Rapporten oppgir ikke hvor mange av de ansatte som er i Norge."},
        {"selskap": {"label": "Selskap", "nodes": nodes}}, mk(facts, "personer", "offisiell"), out)
    write_dataset(TOPIC, "selskaper_vektet", {**common, "id": f"{TOPIC}.selskaper_vektet", "title": "Ansatte i selskaper med statlig eierandel, vektet med eierandel, 2025", "unit": "personer (vektet)", "claim_level": "estimat",
        "derivation": "Antall ansatte i konsernet multiplisert med statens eierandel, avrundet til hele personer",
        "notes": "Anslag: ansatte multiplisert med statens eierandel. Det er et regnestykke, ikke en telling; ingen ansatte er faktisk «delvis» statlig ansatt."},
        {"selskap": {"label": "Selskap", "nodes": nodes}}, mk(weighted, "personer (vektet)", "estimat"), out)
    return {"total": total, "rhf": sum(r[2] for r in cat2_rhf), "cat2_other": sum(r[2] for r in cat2_other), "cat1": cat1_pub, "weighted": sum(v for _, v in weighted)}


def ringer(out: Path, ssb_staten: int, eier: dict) -> None:
    leaves = [("R1", "Ansatte i staten (SSB)", ssb_staten, EMP, "offisiell"),
              ("R2", "Regionale helseforetak (Statens eierrapport)", eier["rhf"], EIER, "utledet"),
              ("R3", "Øvrige sektorpolitiske selskaper, kategori 2", eier["cat2_other"], EIER, "utledet"),
              ("R4", "Selskaper med mål om høyest mulig avkastning, kategori 1", eier["cat1"], EIER, "offisiell")]
    rows = [{"period": "2025", "value": v, "unit": "personer", "status": "foreløpig", "ring": c, "claim_level": cl, "source_id": s} for c, _, v, s, cl in leaves]
    nodes = [{"code": "SUM", "label": "Fire grupper lagt sammen", "parent": None}] + [{"code": c, "label": l, "parent": "SUM"} for c, l, *_ in leaves]
    meta = {"id": f"{TOPIC}.ringer", "title": "Ansatte i fire grupper rundt staten, 2025", "unit": "personer", "price_basis": "ikke-relevant", "claim_level": "utledet",
            "derivation": "Fire tall fra to kilder lagt ved siden av hverandre. Ansatte i staten er årsgjennomsnitt (SSB); de tre andre er antall ansatte i konsernene ved årsskiftet (Statens eierrapport), uten vekting med eierandel og inkludert ansatte utenfor Norge.",
            "source_ids": [EMP, EIER], "dimensions": ["ring"], "default_dimension": "ring",
            "notes": "Gruppene har ikke felles målemetode. Ansatte i staten er ansatte i statlige virksomheter i Norge (årsgjennomsnitt). De tre andre er konsernenes ansatte og kan inkludere ansatte utenfor Norge. Summen er derfor en samlet oversikt, ikke en offisiell telling. Kommunesektoren er vist for seg, og privat finansierte tjenesteytere og arbeidsmarkedstiltak har ikke en samlet offisiell kilde og er ikke med."}
    write_dataset(TOPIC, "ringer", meta, {"ring": {"label": "Ring", "nodes": nodes}}, rows, out)


def series(out: Path, sec: dict) -> int:
    js, _ = latest_snapshot(EMP)
    V = {(r["ContentsCode"], r["Tid"]): r["value"] for r in js.rows()}
    years = sorted({t for (_, t) in V})
    note = "Årsgjennomsnitt (gjennomsnitt av månedene). Dekker enhetene i statsregnskapet; helseforetak og statlig eide selskaper inngår ikke. Endring i rapporteringen av arbeidstid mellom 2015 og 2016 gjør at avtalte årsverk må tolkes med forsiktighet over tid."
    for code, sid, title, unit in (("Ansatte", "ansatte_staten", "Ansatte i staten", "personer"), ("AvtalteArsverk", "arsverk_staten", "Avtalte årsverk i staten", "årsverk")):
        write_series(TOPIC, {"id": f"{TOPIC}.{sid}", "title": title, "unit": unit, "price_basis": "ikke-relevant", "claim_level": "offisiell", "source_ids": [EMP], "notes": note,
                             "values": [{"period": t, "value": V[(code, t)], "status": "regnskap"} for t in years]}, out)
    S = sec["V"]
    write_series(TOPIC, {"id": f"{TOPIC}.statsforvaltningen", "title": "Sysselsatte i statsforvaltningen (inkl. helseforetak), 4. kvartal", "unit": "personer", "price_basis": "ikke-relevant",
                         "claim_level": "offisiell", "source_ids": [SEC], "values": [{"period": t, "value": S[("6100", t)], "status": "regnskap"} for t in years if ("6100", t) in S]}, out)
    write_series(TOPIC, {"id": f"{TOPIC}.differanse_statsforvaltningen", "title": "Statsforvaltningen minus ansatte i staten", "unit": "personer", "price_basis": "ikke-relevant", "claim_level": "utledet",
                         "derivation": "Sysselsatte i statsforvaltningen (tabell 13472, 4. kvartal) minus ansatte i staten (tabell 12623, årsgjennomsnitt)", "source_ids": [SEC, EMP],
                         "notes": "De to tabellene måler ikke likt: 4. kvartal mot årsgjennomsnitt, sysselsatte 15–74 år mot alle ansatte. Differansen er derfor bare en pekepinn. SSB skriver at den største forskjellen er at statsforvaltningen også inkluderer helseforetakene.",
                         "values": [{"period": t, "value": S[("6100", t)] - V[("Ansatte", t)], "status": "regnskap"} for t in years if ("6100", t) in S]}, out)
    return V[("Ansatte", years[-1])]


def run(out: Path = PROCESSED) -> None:
    sec = sektorer(out)
    eier = selskaper(out)
    last = series(out, sec)
    ringer(out, last, eier)
