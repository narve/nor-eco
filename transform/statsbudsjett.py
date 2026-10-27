"""WS1 Statsbudsjett: raw snapshots -> data/processed/statsbudsjett/.

Datasets (hierarchical): income and expenditure by hovedpost (accounts and budget side by side), the state's net
cash flow from petroleum activities by component. Series: surplus lines, the oil-corrected balance derived from
the accounts (utledet), and the official percentage series from Finansdepartementet's Excel files.
Status semantics: «regnskap» = statsregnskapet; «budsjett» = SSB's budget table (updated by SSB when Q3/Q4
accounts are published, so it is not a fixed adopted stage); Excel years after the last accounts year are
«anslag» (current year) and «forslag» (the proposed budget year).
"""

from __future__ import annotations

import html as htmllib
import re
from pathlib import Path

import openpyxl

from fetch.common import ensure_local

from .common import PROCESSED, latest_snapshot, latest_snapshot_bytes, mrd, write_dataset, write_series

TOPIC = "statsbudsjett"
ACC, BUD, PET = "ssb-10486", "ssb-10487", "ssb-11012"
K3, V1, KF = "fin-nb2027-kap3", "fin-nb2027-vedlegg1", "fin-nokkeltall-nb2027"

# Tree of SSB hovedposter (codes from tables 10486/10487). Children sum to the parent; checked against SSB's totals.
INCOME = ("INNT.IALT", "Inntekter i alt", [
    "INNT.SALG", "INNT.DR_RES_PETROL", "INNT.AVSKR_PETROL", "INNT.AVSKR_FORRETN", "INNT.ANDRE_BYGG",
    ("INNT.OVERF_IALT", ["INNT.SKATT_AVG", "INNT.MEDL_PR", "INNT.ARB_G_AVG", "INNT.RENTER_UTB", "INNT.ANDRE_STATL",
                         "INNT.KOMM_FYLK", "INNT.NORGES_BANK", "INNT.ANDRE_OVERF"])])
EXPENSE = ("UTG.IALT", "Utgifter i alt", [
    ("UTG.DRIFT_IALT", ["UTG.LONN", "UTG.VARER_TJ", "UTG.ANDRE_DRIFT"]),
    "UTG.DR_RES_FORRETN",
    ("UTG.BYGG_IALT", ["UTG.BYGG_PETROL", "UTG.BYGG_FORRETN", "UTG.BYGG_ELLERS"]),
    ("UTG.OVERF_IALT", ["UTG.ANDRE_STATL", "UTG.KOMM_FYLK", "UTG.PENSJ_TRYGD", "UTG.RENTER", "UTG.ANDRE_OVERF"])])

PETROLEUM_PARTS = [("skatt_utvinning", "Skatter på utvinning av petroleum", "SkatteUtvinning"),
                   ("avgift_utvinning", "Avgifter på utvinning av petroleum", "AvgiftUtvinning"),
                   ("sdoe", "Netto kontantstrøm fra SDØE", "NettoKontantstrom"),
                   ("equinor_utbytte", "Utbytte fra Equinor", "UtbytteStatoil")]


def _clean(label: str) -> str:
    return " ".join(label.split())


def _nodes(tree, labels):
    root_code, root_label, kids = tree
    nodes = [{"code": root_code, "label": root_label, "parent": None}]

    def add(spec, parent):
        if isinstance(spec, tuple):
            code, children = spec
            nodes.append({"code": code, "label": _clean(labels[code]), "parent": parent})
            for c in children:
                add(c, code)
        else:
            nodes.append({"code": spec, "label": _clean(labels[spec]), "parent": parent})

    for k in kids:
        add(k, root_code)
    return nodes


def _leaves(tree):
    out = []

    def walk(spec):
        if isinstance(spec, tuple):
            for c in spec[1]:
                walk(c)
        else:
            out.append(spec)

    for k in tree[2]:
        walk(k)
    return out


def parse_key_figures(content: bytes) -> dict[str, dict[str, float]]:
    """{row label: {year: value}} from the key-figures table (header row of years, then label + one value per year)."""
    text = content.decode("utf-8")
    out: dict[str, dict[str, float]] = {}
    years: list[str] | None = None
    for row in re.findall(r"<tr.*?</tr>", text, re.S):
        cells = [" ".join(htmllib.unescape(re.sub(r"<[^>]+>", "", c)).split()) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)]
        if len(cells) >= 2 and all(re.fullmatch(r"\d{4}", c) for c in cells[1:]):
            years = cells[1:]
        elif years and len(cells) == len(years) + 1:
            vals = {}
            for y, c in zip(years, cells[1:]):
                try:
                    vals[y] = float(c.replace("\u2212", "-"))
                except ValueError:
                    pass
            if vals:
                out[re.sub(r"\s*\d$", "", cells[0])] = vals  # drop a trailing footnote marker
    return out


def _sheet(path: Path, name: str) -> list[list]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return [list(r) for r in wb[name].iter_rows(values_only=True)]
    finally:
        wb.close()


def run(out: Path = PROCESSED) -> None:
    acc_js, acc_e = latest_snapshot(ACC)
    bud_js, bud_e = latest_snapshot(BUD)
    labels = acc_js.dimensions[0].labels
    val = {"regnskap": {(r["Hovedpost"], r["Tid"]): r["value"] for r in acc_js.rows()},
           "budsjett": {(r["Hovedpost"], r["Tid"]): r["value"] for r in bud_js.rows()}}
    src = {"regnskap": ACC, "budsjett": BUD}
    vintage = {"regnskap": acc_js.updated, "budsjett": bud_js.updated}
    periods = {st: sorted({t for (_, t) in v}) for st, v in val.items()}
    last_acc = int(periods["regnskap"][-1])

    # ---- hierarchical: income and expenditure by hovedpost, accounts and budget side by side ----
    for name, tree, title in (("inntekter", INCOME, "Statens inntekter etter hovedpost"), ("utgifter", EXPENSE, "Statens utgifter etter hovedpost")):
        rows, totals = [], []
        for st in ("regnskap", "budsjett"):
            for t in periods[st]:
                for code in _leaves(tree):
                    if (code, t) in val[st]:
                        rows.append({"period": t, "value": mrd(val[st][(code, t)]), "unit": "mrd. kr", "status": st, "hovedpost": code,
                                     "claim_level": "offisiell", "source_id": src[st]})
                totals.append({"period": t, "status": st, "value": mrd(val[st][(tree[0], t)]), "source_id": src[st]})
        meta = {"id": f"{TOPIC}.{name}", "title": title, "unit": "mrd. kr", "price_basis": "løpende", "claim_level": "offisiell",
                "source_ids": [ACC, BUD], "dimensions": ["hovedpost"], "default_dimension": "hovedpost", "published_totals": totals,
                "tolerance": 0.001,
                "notes": "Statsregnskapet (regnskap) og statsbudsjettet (budsjett) etter SSBs hovedposter. Kontantbasert; inntekter før eventuelle tilbakeføringer fra Statens pensjonsfond utland. Skatter og avgifter er ikke delt på petroleum og andre; se egen tabell for petroleumsvirksomhetens netto kontantstrøm."}
        dims = {"hovedpost": {"label": "Hovedpost", "nodes": _nodes(tree, labels)}}
        write_dataset(TOPIC, name, meta, dims, rows, out)

    # ---- surplus lines C and D, accounts and budget ----
    for code, sid, title in (("OF_PETROL_FOND", "overskudd_for_avsetning", "Overskudd før netto avsetning til Statens pensjonsfond utland"),
                             ("PETROL_FOND", "netto_avsetning_spu", "Netto avsetning til Statens pensjonsfond utland")):
        for st in ("regnskap", "budsjett"):
            values = [{"period": t, "value": mrd(val[st][(code, t)]), "status": st} for t in periods[st]]
            write_series(TOPIC, {"id": f"{TOPIC}.{sid}_{st}", "title": f"{title} ({st})", "unit": "mrd. kr", "price_basis": "løpende",
                                 "claim_level": "offisiell", "source_ids": [src[st]], "vintage": vintage[st][:10], "values": values}, out)

    # ---- petroleum: the state's net cash flow by component (accounts) ----
    pet_js, pet_e = latest_snapshot(PET)
    pv = {(r["ContentsCode"], r["Tid"]): r["value"] for r in pet_js.rows()}
    pyears = sorted({t for (_, t) in pv})
    rows = [{"period": t, "value": mrd(pv[(k, t)]), "unit": "mrd. kr", "status": "regnskap", "komponent": c, "claim_level": "offisiell", "source_id": PET}
            for t in pyears for c, _, k in PETROLEUM_PARTS]
    meta = {"id": f"{TOPIC}.petroleum_kontantstrom", "title": "Statens netto kontantstrøm fra petroleumsvirksomhet, etter komponent", "unit": "mrd. kr",
            "price_basis": "løpende", "claim_level": "offisiell", "source_ids": [PET], "dimensions": ["komponent"], "default_dimension": "komponent",
            "published_totals": [{"period": t, "status": "regnskap", "value": mrd(pv[("StatensNettoKont", t)]), "source_id": PET} for t in pyears],
            "tolerance": 0.001, "notes": "SDØE er netto kontantstrøm (ikke brutto). Skatter og avgifter på utvinning er også regnet med i «Skatter og avgifter» i statsregnskapets hovedposter."}
    dims = {"komponent": {"label": "Komponent", "nodes": [{"code": "statens_netto_kontantstrom", "label": "Statens netto kontantstrøm fra petroleumsvirksomhet", "parent": None}]
                          + [{"code": c, "label": l, "parent": "statens_netto_kontantstrom"} for c, l, _ in PETROLEUM_PARTS]}}
    write_dataset(TOPIC, "petroleum_kontantstrom", meta, dims, rows, out)

    # ---- derived: oil-corrected balance in kroner (accounts) ----
    both = [t for t in periods["regnskap"] if t in pyears]
    write_series(TOPIC, {
        "id": f"{TOPIC}.oljekorrigert_balanse_kr", "title": "Oljekorrigert budsjettbalanse, regnskap (negativ = underskudd)", "unit": "mrd. kr",
        "price_basis": "løpende", "claim_level": "utledet",
        "derivation": "Overskudd før netto avsetning til Statens pensjonsfond utland (statsregnskapet) minus statens netto kontantstrøm fra petroleumsvirksomhet. Dette er budsjettbalansen utenom netto inntekter fra petroleumsvirksomheten.",
        "source_ids": [ACC, PET], "vintage": acc_js.updated[:10],
        "values": [{"period": t, "value": mrd(val["regnskap"][("OF_PETROL_FOND", t)] - pv[("StatensNettoKont", t)]), "status": "regnskap"} for t in both],
        "notes": "Avviker fra Finansdepartementets prosenttall bare ved at nevneren er faktisk BNP Fastlands-Norge, ikke trend-BNP."}, out)

    # ---- official series from Finansdepartementet's Excel files ----
    def status_of(year: int) -> str:
        return "regnskap" if year <= last_acc else "anslag" if year == last_acc + 1 else "forslag"

    v1 = ensure_local(V1)
    k3 = ensure_local(K3)

    def series_from(path, sheet, columns, sid, title, unit, src_id, with_status=True, **extra):
        """columns: list of column indexes tried in order for each year (first non-empty wins)."""
        values = []
        for r in _sheet(path, sheet):
            if not isinstance(r[0], int):
                continue
            v = next((r[c] for c in columns if r[c] is not None), None)
            if v is not None:
                values.append({"period": str(r[0]), "value": float(v), **({"status": status_of(r[0])} if with_status else {})})
        write_series(TOPIC, {"id": f"{TOPIC}.{sid}", "title": title, "unit": unit, "price_basis": "ikke-relevant", "claim_level": "offisiell",
                             "source_ids": [src_id], "values": values, **extra}, out)

    series_from(v1, "Figv1-1", [1], "oljekorrigert_balanse_pst", "Oljekorrigert budsjettbalanse, prosent av trend-BNP for Fastlands-Norge (negativ = underskudd)", "prosent", V1,
                notes="Tall for året etter siste regnskapsår er anslag, og budsjettåret er forslag (Nasjonalbudsjettet 2027).")
    series_from(v1, "Figv1-1", [2], "strukturell_balanse_pst", "Strukturell oljekorrigert budsjettbalanse, prosent av trend-BNP for Fastlands-Norge (negativ = underskudd)", "prosent", V1,
                notes="Tall for året etter siste regnskapsår er anslag, og budsjettåret er forslag (Nasjonalbudsjettet 2027).")
    series_from(k3, "Fig3-3", [1, 4], "fondsbruk_pst_av_spu", "Strukturelt oljekorrigert underskudd, prosent av Statens pensjonsfond utland (uttaksprosent)", "prosent", K3)
    series_from(k3, "Fig3-4", [1, 2], "fondsbruk_pst_av_utgifter", "Bruk av fondsmidler, prosent av utgiftene i statsbudsjettet", "prosent", K3)
    series_from(k3, "Fig3-3", [2, 3], "handlingsregel_realavkastning", "Forventet realavkastning i Statens pensjonsfond utland (handlingsregelens rettesnor)", "prosent", K3, with_status=False,
                breaks=[{"period": "2018", "note": "Rettesnoren er 3 prosent fra og med 2018 (4 prosent til og med 2017), slik kolonnene i Finansdepartementets tabell er merket.", "source_id": K3}])

    # ---- official: structural oil-corrected deficit in kroner, from the key-figures table ----
    kf_bytes, kf_e = latest_snapshot_bytes(KF)
    kf = parse_key_figures(kf_bytes)
    label = "Structural non-oil fiscal deficit, billion, NOK, current prices"
    if label not in kf:
        raise ValueError(f"key-figures table no longer has the row '{label}'; check the page and update parse_key_figures/transform")
    write_series(TOPIC, {"id": f"{TOPIC}.strukturelt_underskudd_kr", "title": "Strukturelt oljekorrigert budsjettunderskudd, løpende priser", "unit": "mrd. kr",
                         "price_basis": "løpende", "claim_level": "offisiell", "source_ids": [KF],
                         "values": [{"period": y, "value": v, "status": status_of(int(y))} for y, v in sorted(kf[label].items())],
                         "notes": "Tabellen i nasjonalbudsjettet 2027 viser bare disse årene. Anslag for 2026 og forslag for 2027."}, out)

    # ---- derived: the step between the two deficits, where both exist in kroner ----
    sobu = {y: v for y, v in kf[label].items()}
    adj = [{"period": y, "value": round(sobu[y] + (val["regnskap"][("OF_PETROL_FOND", y)] - pv[("StatensNettoKont", y)]) / 1000, 3), "status": status_of(int(y))}
           for y in sorted(sobu) if y in both]
    write_series(TOPIC, {"id": f"{TOPIC}.aktivitetskorreksjon_kr", "title": "Aktivitetskorreksjon og andre justeringer: strukturelt minus oljekorrigert underskudd",
                         "unit": "mrd. kr", "price_basis": "løpende", "claim_level": "utledet",
                         "derivation": "Strukturelt oljekorrigert underskudd (Finansdepartementet, løpende priser) minus oljekorrigert underskudd regnet fra statsregnskapet (se serien «Oljekorrigert budsjettbalanse, regnskap»). Positivt tall = det strukturelle underskuddet er større.",
                         "source_ids": [KF, ACC, PET], "values": adj,
                         "notes": "Finansdepartementet publiserer ikke oljekorrigert underskudd i kroner i denne tabellen; differansen kan derfor også romme avvik mellom vår regning og Finansdepartementets."}, out)
