"""WS3 Sysselsetting: register-based status (12423), AKU (13618) and national accounts persons / man-years / hours (09174).

The register series starts in 2015, when the a-ordningen replaced the Aa- and LTO-registers (SSB: «Fra og med 2015
ble Aa- og LTO-registrene erstattet av a-ordningen»), so no break has to be bridged. AKU is taken from the same year
so the two can be compared; national accounts from 2000.
"""

from __future__ import annotations

from . import common, ssb

REGISTER_START, NA_START = 2015, 2000


def _years(table_id: str, since: int) -> list[str]:
    meta = common.parse_jsonstat2(ssb.table_metadata(table_id), metadata_only=True)
    tid = next(d for d in meta.dimensions if d.role == "time" or d.id == "Tid")
    return [c for c in tid.codes if int(c) >= since]


def run() -> list[common.Snapshot]:
    snaps = []
    for source_id, table, selection in (
        ("ssb-12423", "12423", {"Kjonn": ["0", "1", "2"], "Alder": ["15-74", "20-66", "15+"], "UtdNivaa": ["TOT"], "InnvandrKat": ["A-G"], "HovArbStyrkStatus": ["*"],
                                "ContentsCode": ["Bosatte"], "Tid": _years("12423", REGISTER_START)}),
        ("ssb-13618", "13618", {"ArbStyrkStatus": ["*"], "Kjonn": ["0", "1", "2"], "Alder": ["15-74", "20-66"], "ContentsCode": ["Personer", "Feilmargin"],
                                "Tid": _years("13618", REGISTER_START)}),
        ("ssb-09174", "09174", {"NACE": ["nr23_6"], "ContentsCode": ["Sysselsatte", "SysselsattNorm", "Timeverk"], "Tid": _years("09174", NA_START)}),
    ):
        snap, js = ssb.fetch_and_snapshot(source_id, table, selection)
        print(f"{source_id}: {'unchanged' if snap.unchanged else 'new snapshot'} ({snap.path.name}, {snap.path.stat().st_size // 1024} KB), updated {js.updated}")
        snaps.append(snap)
    return snaps
