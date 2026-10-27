"""WS2 Økonomi: SSB national accounts (09189), trade in goods (08800) and population (06913).

Only the series the site uses are requested, from START_YEAR onwards (earlier years are not needed).
"""

from __future__ import annotations

from . import common, ssb

START_YEAR = 1990

# 09189 Makroøkonomiske hovedstørrelser (annual). ContentsCode: Priser=løpende, Faste=faste 2023-priser, Volum=volumendring.
MAKROST = [
    "bnpb.nr23_9",       # BNP, markedsverdi
    "bnpb.nr23_9fn",     # BNP Fastlands-Norge, markedsverdi
    "bnpb.nr23oljsj",    # Oljevirksomhet og utenriks sjøfart
    "eks.nrtot", "eks.nrtradvare", "eks.puboljegs", "eks.nrskiplfly", "eks.nrtjen",
    "imp.nrtot", "imp.nrtradvare", "imp.puboljegs", "imp.nrskiplfly", "imp.nrtjen",
]
# 08800 Utenrikshandel med varer, hovedtall (mill. kr)
VARESTROMMER = ["Eoljegass", "Eolje", "Egass", "Ekondens", "Etot", "Etotusorn"]


def _years(table_id: str, since: int = START_YEAR) -> list[str]:
    meta = common.parse_jsonstat2(ssb.table_metadata(table_id), metadata_only=True)
    tid = next(d for d in meta.dimensions if d.role == "time" or d.id == "Tid")
    return [c for c in tid.codes if int(c) >= since]


def run() -> list[common.Snapshot]:
    snaps = []
    for source_id, table, selection in (
        ("ssb-09189", "09189", {"Makrost": MAKROST, "ContentsCode": ["Priser", "Faste", "Volum"], "Tid": _years("09189")}),
        ("ssb-08800", "08800", {"HovedVareStrommer": VARESTROMMER, "ContentsCode": ["Verdi"], "Tid": _years("08800")}),
        ("ssb-06913", "06913", {"Region": ["0"], "ContentsCode": ["Folkemengde"], "Tid": _years("06913")}),
    ):
        snap, js = ssb.fetch_and_snapshot(source_id, table, selection)
        print(f"{source_id}: {'unchanged' if snap.unchanged else 'new snapshot'} ({snap.path.name}), updated {js.updated}")
        snaps.append(snap)
    return snaps
