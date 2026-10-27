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
ACC, BUD, PET, COF = "ssb-10486", "ssb-10487", "ssb-11012", "ssb-14669"
K3, V1, KF, SB = "fin-nb2027-kap3", "fin-nb2027-vedlegg1", "fin-nokkeltall-nb2027", "fin-sb2027-inntekter-utgifter"

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
                             ("PETROL_FOND", "netto_avsetning_spu", "Netto avsetning til Statens pensjonsfond utland"),
                             # loan transactions are not spending in the sense above; shown as their own lines
                             ("UTLAN", "netto_utlan", "Netto utlån mv."), ("AVDRAG", "avdrag_statsgjeld", "Avdrag på statsgjelden"),
                             ("FIN_BEHOV", "finansieringsbehov", "Finansieringsbehov")):
        for st in ("regnskap", "budsjett"):
            values = [{"period": t, "value": mrd(val[st][(code, t)]), "status": st} for t in periods[st] if (code, t) in val[st]]  # a missing cell stays a gap
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

    write_series(TOPIC, {"id": f"{TOPIC}.petroleum_netto_kontantstrom", "title": "Statens netto kontantstrøm fra petroleumsvirksomhet", "unit": "mrd. kr",
                         "price_basis": "løpende", "claim_level": "offisiell", "source_ids": [PET], "vintage": pet_js.updated[:10],
                         "values": [{"period": t, "value": mrd(pv[("StatensNettoKont", t)]), "status": "regnskap"} for t in pyears]}, out)

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


def cofog(out: Path = PROCESSED) -> None:
    """Public expenditure by purpose (COFOG) x sector x type, from SSB 14669.

    Facts are leaf cells: 3-digit COFOG groups x {stat, kommune, differanse} x {10 types + not distributed}. Two
    residuals are explicit nodes, never hidden: the difference between «offentlig forvaltning» and the sum of state and
    municipalities (SSB gives no reason in the table), and the difference between the published total and the sum
    of the ten spending types (a few billion for the state)."""
    js, entry = latest_snapshot(COF)
    dim = {d.id: d for d in js.dimensions}
    V = {(r["Sektor"], r["Art"], r["Formaal"], r["Tid"]): r["value"] for r in js.rows()}
    years = sorted({t for (_, _, _, t) in V})
    arts = [c for c in dim["Art"].codes if c != "E"]
    leaves = [c for c in dim["Formaal"].codes if len(c) == 3]
    mains = [c for c in dim["Formaal"].codes if len(c) == 2]
    g = lambda sec, a, f, t: V.get((sec, a, f, t)) or 0  # noqa: E731  (SSB leaves empty cells for zero)

    def full(sec, a, f, t):
        """Value of (sector total, art or 'ikke_fordelt', formål leaf, year) in mill. kr."""
        if a == "ikke_fordelt":
            return g(sec, "E", f, t) - sum(g(sec, x, f, t) for x in arts)
        return g(sec, a, f, t)

    rows = []
    for t in years:
        for f in leaves:
            for a in arts + ["ikke_fordelt"]:
                stat, kom, tot = full("6100", a, f, t), full("6500", a, f, t), full("C_OFF", a, f, t)
                cells = (("6100", stat, "offisiell" if a != "ikke_fordelt" else "utledet"), ("6500", kom, "offisiell" if a != "ikke_fordelt" else "utledet"),
                         ("konsolidering", tot - stat - kom, "utledet"))
                for sec, v, claim in cells:
                    if round(v) != 0:
                        rows.append({"period": t, "value": mrd(v), "unit": "mrd. kr", "status": "regnskap", "formaal": f, "sektor": sec, "art": a,
                                     "claim_level": claim, "source_id": COF})
    totals = [{"period": t, "status": "regnskap", "value": mrd(g("C_OFF", "E", "0", t)), "source_id": COF} for t in years]
    meta = {"id": f"{TOPIC}.offentlige_utgifter_formaal", "title": "Offentlig forvaltnings utgifter etter formål, sektor og art", "unit": "mrd. kr",
            "price_basis": "løpende", "claim_level": "offisiell", "source_ids": [COF], "dimensions": ["formaal", "sektor", "art"], "default_dimension": "formaal",
            "published_totals": totals, "tolerance": 0.0005,
            "notes": "Formål etter COFOG. Offentlig forvaltning samlet er ikke lik summen av stat og kommune i tabellen; differansen er en egen post. Summen av de ti utgiftstypene avviker også litt fra publisert total, og avviket er en egen post. Poster med null er utelatt."}
    flabel = lambda c: _clean(dim["Formaal"].labels[c])  # noqa: E731
    dims = {
        "formaal": {"label": "Formål (COFOG)", "nodes": [{"code": "0", "label": "Alle formål", "parent": None}]
                    + [{"code": m, "label": flabel(m), "parent": "0"} for m in mains]
                    + [{"code": f, "label": flabel(f), "parent": f[:2]} for f in leaves]},
        "sektor": {"label": "Forvaltningsnivå", "nodes": [{"code": "C_OFF", "label": "Offentlig forvaltning", "parent": None},
                                                         {"code": "6100", "label": "Statsforvaltningen", "parent": "C_OFF"},
                                                         {"code": "6500", "label": "Kommuneforvaltningen", "parent": "C_OFF"},
                                                         {"code": "konsolidering", "label": "Differanse: offentlig forvaltning samlet minus stat og kommune", "parent": "C_OFF", "other": True,
                                                          "definition": "SSB oppgir ikke årsaken til differansen i tabellen. SSB skriver om kildene: «For eksempel er det vanskelig å få overføringene mellom stats- og kommuneregnskapene til å stemme overens.»",
                                                          "source_id": "ssb-offinnut-om"}]},
        "art": {"label": "Utgiftsart", "nodes": [{"code": "E", "label": "Totale utgifter", "parent": None}]
                + [{"code": a, "label": _clean(dim["Art"].labels[a]), "parent": "E"} for a in arts]
                + [{"code": "ikke_fordelt", "label": "Differanse: publisert total minus summen av utgiftsartene", "parent": "E", "other": True}]},
    }
    write_dataset(TOPIC, "offentlige_utgifter_formaal", meta, dims, rows, out)


# ---- Finansdepartementet: Statsbudsjettet 2027, statens inntekter og utgifter (page text and table 1) ----

def _num(text: str) -> float:
    return float(text.replace("\u00a0", "").replace(" ", "").replace("\u2212", "-").replace(",", "."))


def parse_sb_page(content: bytes) -> dict:
    """Sentences and table 1 of the page. Raises if the wording or layout has changed."""
    raw = content.decode("utf-8")
    body = re.sub(r"<script.*?</script>|<style.*?</style>", "", raw, flags=re.S)
    text = " ".join(htmllib.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"</(p|li|h\d|div)>", "\n", body))).replace("\u00ad", "").split())
    n = r"([\d\u00a0 ]+)"
    pats = {
        "inn_total": rf"samlede inntekter anslått til {n}milliarder kroner, og samlede utgifter til {n}milliarder kroner",
        "uten_pet": rf"er inntektene {n}milliarder kroner og utgiftene {n}milliarder kroner",
        "pet": rf"inntekter fra petroleumsvirksomheten er anslått til {n}milliarder kroner(?: i \d{{4}})?\. Utgiftene til petroleumsvirksomheten er anslått til {n}milliarder kroner\. Forskjellen mellom inntekter og utgifter gir en netto kontantstrøm fra petroleumsvirksomheten på {n}milliarder",
        "underskudd": rf"har statsbudsjettet et underskudd på {n}milliarder kroner",
    }
    out = {}
    for k, pat in pats.items():
        m = re.search(pat, text)
        if not m:
            raise ValueError(f"the page no longer contains the sentence for '{k}'; check the page and update parse_sb_page")
        out[k] = [_num(g) for g in m.groups()]
    # table 1: rows of (label, detail, group sum, total)
    rows = []
    for row in re.findall(r"<tr.*?</tr>", raw, re.S):
        cells = [" ".join(htmllib.unescape(re.sub(r"<[^>]+>", "", c)).split()) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)]
        if len(cells) == 4:
            rows.append((re.sub(r"\d$", "", cells[0]), *[(_num(c) if c else None) for c in cells[1:]]))
    if len(rows) < 20:
        raise ValueError("table 1 on the page has changed layout")
    out["table"] = rows
    return out


def _slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower().replace("æ", "ae").replace("ø", "o").replace("å", "a")).strip("_")


def sb2027(out: Path = PROCESSED) -> None:
    """Budget proposal 2027: with/without petroleum (excl. loan transactions) and the breakdown outside petroleum."""
    content, _ = latest_snapshot_bytes(SB)
    d = parse_sb_page(content)
    period, status = "2027", "forslag"
    # with / without petroleum
    for name, title, total, other, pet in (("inntekter", "inntekter", d["inn_total"][0], d["uten_pet"][0], d["pet"][0]),
                                           ("utgifter", "utgifter", d["inn_total"][1], d["uten_pet"][1], d["pet"][1])):
        rows = [{"period": period, "value": v, "unit": "mrd. kr", "status": status, "petroleum": c, "claim_level": "offisiell", "source_id": SB}
                for c, v in (("utenom_petroleum", other), ("petroleum", pet))]
        meta = {"id": f"{TOPIC}.budsjettforslag_2027_{name}_med_uten_petroleum", "title": f"Statsbudsjettet 2027: {title} med og uten petroleum", "unit": "mrd. kr",
                "price_basis": "løpende", "claim_level": "offisiell", "source_ids": [SB], "dimensions": ["petroleum"], "default_dimension": "petroleum",
                "published_totals": [{"period": period, "status": status, "value": total, "source_id": SB}], "tolerance": 0.0005,
                "notes": "Budsjettforslaget for 2027, utenom lånetransaksjoner. Hele milliarder, slik Finansdepartementet oppgir dem."}
        dims = {"petroleum": {"label": "Petroleum", "nodes": [{"code": "samlet", "label": f"Statens samlede {title}", "parent": None},
                                                             {"code": "utenom_petroleum", "label": f"{title.capitalize()} utenom petroleum", "parent": "samlet"},
                                                             {"code": "petroleum", "label": f"{title.capitalize()} fra petroleumsvirksomheten" if name == "inntekter" else "Utgifter til petroleumsvirksomheten", "parent": "samlet"}]}}
        write_dataset(TOPIC, f"budsjettforslag_2027_{name}_med_uten_petroleum", meta, dims, rows, out)
    # table 1: breakdown outside petroleum
    sections: dict[str, list] = {}
    cur = None
    for label, c1, c2, c3 in d["table"]:
        if c3 is not None and c1 is None and c2 is None and label.startswith("Statsbudsjettets"):
            cur = "inntekter" if "inntekter" in label else "utgifter" if "utgifter" in label else None
            if cur:
                sections[cur] = [("root", label, c3)]
        elif cur and (c1 is not None or c2 is not None):
            sections[cur].append(("detail" if c1 is not None else "group", label, c1 if c1 is not None else c2))
    for name in ("inntekter", "utgifter"):
        items = sections[name]
        root_label, root_val = items[0][1], items[0][2]
        nodes = [{"code": "samlet", "label": root_label, "parent": None}]
        rows = []
        group = None
        # a group's value is published; its details (if any) sum to it, so the group is a node and the details are its leaves
        for kind, label, v in items[1:]:
            code = _slug(label)
            if kind == "group":
                group = code
                nodes.append({"code": code, "label": label, "parent": "samlet"})
                rows.append((code, label, v))
            else:
                nodes.append({"code": code, "label": label, "parent": group})
                rows.append((code, label, v))
        parents = {n["parent"] for n in nodes}
        leaf_rows = [r for r in rows if r[0] not in parents]
        facts = [{"period": period, "value": v, "unit": "mrd. kr", "status": status, "post": c, "claim_level": "offisiell", "source_id": SB} for c, _, v in leaf_rows]
        meta = {"id": f"{TOPIC}.budsjettforslag_2027_{name}_detalj", "title": f"Statsbudsjettet 2027: {name} utenom petroleum og lånetransaksjoner", "unit": "mrd. kr",
                "price_basis": "løpende", "claim_level": "offisiell", "source_ids": [SB], "dimensions": ["post"], "default_dimension": "post",
                "published_totals": [{"period": period, "status": status, "value": root_val, "source_id": SB}], "tolerance": 0.0005,
                "notes": "Tabell 1 hos Finansdepartementet. «Andre utgifter» er en residual hos kilden. Avrundet til én desimal, så delene kan avvike fra totalen med noen tideler."}
        write_dataset(TOPIC, f"budsjettforslag_2027_{name}_detalj", meta, {"post": {"label": "Post", "nodes": nodes}}, facts, out)
    overskudd = next(c3 for label, c1, c2, c3 in d["table"] if label.startswith("Oljekorrigert overskudd"))
    write_series(TOPIC, {"id": f"{TOPIC}.oljekorrigert_balanse_kr_forslag", "title": "Oljekorrigert overskudd i budsjettforslaget for 2027 (negativ = underskudd)", "unit": "mrd. kr",
                         "price_basis": "løpende", "claim_level": "offisiell", "source_ids": [SB],
                         "values": [{"period": period, "value": overskudd, "status": status}],
                         "notes": "Utenom lånetransaksjoner og petroleumsvirksomheten."}, out)
