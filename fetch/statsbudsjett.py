"""WS1 Statsbudsjett: SSB state accounts (10486), state budget (10487), petroleum cash flow (11012), and the
Finansdepartementet Excel files behind the figures of Nasjonalbudsjettet 2027.

The Excel files are found by scanning the publisher's «Tallene bak figurene» page for the file names, so a
new edition is picked up by changing PAGE (and the registry). They are not committed: they are listed in
data/raw/MANIFEST.yaml and re-downloaded (and sha256-checked) by `common.ensure_local`.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from . import common, ssb

START_YEAR = 2000
PAGE = "https://www.regjeringen.no/no/statsbudsjett/2027/nasjonalbudsjettet-2027-tallene-bak-figurene/id3173281/"
SB_PAGE = "https://www.regjeringen.no/no/statsbudsjett/2027/statsbudsjettet-2027-statens-inntekter-og-utgifter/id3173250/"
KEY_FIGURES = "https://www.regjeringen.no/en/whats-new/key-figures-in-the-national-budget-for-2027/id3174610/"
EXCEL = {"fin-nb2027-kap3": "kap_3_nb_", "fin-nb2027-vedlegg1": "vedlegg_1_nb_"}


def _years(table_id: str) -> list[str]:
    meta = common.parse_jsonstat2(ssb.table_metadata(table_id), metadata_only=True)
    tid = next(d for d in meta.dimensions if d.role == "time" or d.id == "Tid")
    return [c for c in tid.codes if int(c) >= START_YEAR]


def excel_links(html: str) -> dict[str, str]:
    """{prefix: absolute url} for the .xlsx files whose name starts with one of EXCEL's prefixes."""
    out = {}
    for href in re.findall(r'href="([^"]+\.xlsx)"', html):
        name = href.rsplit("/", 1)[-1]
        for prefix in EXCEL.values():
            if name.startswith(prefix):
                out[prefix] = urljoin(PAGE, href)
    return out


def run() -> list[common.Snapshot]:
    snaps = []
    for source_id, table, selection in (
        ("ssb-10486", "10486", {"Hovedpost": ["*"], "ContentsCode": ["Belop"], "Tid": _years("10486")}),
        ("ssb-10487", "10487", {"Hovedpost": ["*"], "ContentsCode": ["Belop"], "Tid": _years("10487")}),
        ("ssb-11012", "11012", {"ContentsCode": ["*"], "Tid": _years("11012")}),
        ("ssb-14669", "14669", {"Sektor": ["*"], "Art": ["*"], "Formaal": ["*"], "ContentsCode": ["Belop"], "Tid": _years("14669")}),
    ):
        snap, js = ssb.fetch_and_snapshot(source_id, table, selection)
        print(f"{source_id}: {'unchanged' if snap.unchanged else 'new snapshot'} ({snap.path.name}), updated {js.updated}")
        snaps.append(snap)
    kf = common.http_get(KEY_FIGURES)
    snap = common.write_snapshot("fin-nokkeltall-nb2027", kf.content, ".html", url=KEY_FIGURES)
    print(f"fin-nokkeltall-nb2027: {'unchanged' if snap.unchanged else 'new snapshot'} ({len(kf.content) // 1024} KB)")
    snaps.append(snap)
    sb = common.http_get(SB_PAGE)
    snap = common.write_snapshot("fin-sb2027-inntekter-utgifter", sb.content, ".html", url=SB_PAGE)
    print(f"fin-sb2027-inntekter-utgifter: {'unchanged' if snap.unchanged else 'new snapshot'} ({len(sb.content) // 1024} KB)")
    snaps.append(snap)
    links = excel_links(common.http_get(PAGE).text)
    for source_id, prefix in EXCEL.items():
        url = links.get(prefix)
        if not url:
            raise common.FetchError(f"{source_id}: no .xlsx starting with '{prefix}' on {PAGE}; the page layout changed")
        r = common.http_get(url)
        snap = common.write_snapshot(source_id, r.content, ".xlsx", url=url)
        print(f"{source_id}: {'unchanged' if snap.unchanged else 'new snapshot'} ({url.rsplit('/', 1)[-1]}, {len(r.content) // 1024} KB, not committed)")
        snaps.append(snap)
    return snaps
