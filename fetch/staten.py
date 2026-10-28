"""WS4 Staten som arbeidsgiver: SSB tables 12623 (ansatte i staten) and 13472 (sektor), and the company tables of Statens eierrapport.

The Eierrapport page is stored as HTML (normalised, see common.normalize_html); the transform parses its tables.
"""

from __future__ import annotations

from . import common, ssb

EIERRAPPORT = "https://www.regjeringen.no/no/dokumenter/statens-eierrapport-2025/id3165665/?ch=2"
START = 2016


def _years(table_id: str) -> list[str]:
    meta = common.parse_jsonstat2(ssb.table_metadata(table_id), metadata_only=True)
    tid = next(d for d in meta.dimensions if d.role == "time" or d.id == "Tid")
    return [c for c in tid.codes if int(c) >= START]


def run() -> list[common.Snapshot]:
    snaps = []
    for source_id, table, selection in (
        ("ssb-12623", "12623", {"StatligEnhet": ["0"], "ContentsCode": ["Ansatte", "AvtalteArsverk"], "Tid": _years("12623")}),
        ("ssb-13472", "13472", {"Region": ["0"], "NACE2007": ["00-99"], "Sektor": ["*"], "ContentsCode": ["SysselEtterArbste"], "Tid": _years("13472")}),
    ):
        snap, js = ssb.fetch_and_snapshot(source_id, table, selection)
        print(f"{source_id}: {'unchanged' if snap.unchanged else 'new snapshot'} ({snap.path.name}), updated {js.updated}")
        snaps.append(snap)
    r = common.http_get(EIERRAPPORT)
    snap = common.write_snapshot("nfd-eierrapport-2025", common.normalize_html(r.content), ".html", url=EIERRAPPORT)
    print(f"nfd-eierrapport-2025: {'unchanged' if snap.unchanged else 'new snapshot'} ({len(r.content) // 1024} KB)")
    snaps.append(snap)
    return snaps
