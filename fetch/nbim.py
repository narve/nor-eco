"""NBIM «The fund's value» page: the latest value of Statens pensjonsfond utland and its split.

Only the sentence NBIM prints at the top of the page is used («At end of the third quarter of 2026, the fund's
value was 22,014 billion kroner. ... 14,932 ... 5,589 ... 1,493 ...»). The page has no machine-readable
history, and its history table contains typos, so no history is taken from it.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from . import common

SOURCE_ID = "nbim-fondsverdi"
URL = "https://www.nbim.no/en/investments/the-funds-value/"
SENTENCE = re.compile(
    r"At end of (?P<when>the (?:first|second|third|fourth) (?:quarter|half) of \d{4}|\d{4}), the fund[’']s value was (?P<value>[\d,]+) billion kroner\."
    r".*?totaled to (?P<ret>[\d,]+) billion kroner\. (?P<inflow>[\d,]+) billion kroner was net inflows from the government"
    r" and (?P<fx>[\d,]+) billion kroner came from currency"
)


@dataclass(frozen=True)
class FundValue:
    period: str          # end of the reported period: "2026-09" (third quarter), "2026-06" (first half), "2025-12" (year)
    value: int           # billion kroner
    net_inflow: int
    ret: int
    currency: int


def page_text(content: bytes) -> str:
    t = content.decode("utf-8")
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", t, flags=re.S)
    t = re.sub(r"</(p|li|h\d|div|tr|td|span)>", "\n", t)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", t)).split())


def parse(content: bytes) -> FundValue:
    m = SENTENCE.search(page_text(content))
    if not m:
        raise ValueError("NBIM's wording of the fund-value sentence has changed; check the page and update fetch/nbim.py")
    when = m["when"]
    year = re.search(r"\d{4}", when).group(0)
    ends = {"first quarter": "03", "second quarter": "06", "third quarter": "09", "fourth quarter": "12", "first half": "06", "second half": "12"}
    key = next((k for k in ends if k in when), None)
    period = f"{year}-{ends[key]}" if key else f"{year}-12"
    n = lambda s: int(s.replace(",", ""))  # noqa: E731
    return FundValue(period, n(m["value"]), n(m["inflow"]), n(m["ret"]), n(m["fx"]))


def newest_stored(raw_dir=common.RAW_DIR) -> FundValue | None:
    """The newest period among the stored snapshots (the site sometimes serves an older version of the page)."""
    best = None
    for e in common._load_manifest(raw_dir / "MANIFEST.yaml"):
        if e["source_id"] == SOURCE_ID and e["committed"]:
            fv = parse((raw_dir / e["file"]).read_bytes())
            if best is None or fv.period > best.period:
                best = fv
    return best


def run() -> common.Snapshot | None:
    r = common.http_get(URL)
    fv = parse(r.content)  # fail before storing anything if the page no longer parses
    stored = newest_stored()
    if stored and fv.period < stored.period:
        print(f"{SOURCE_ID}: NBIM served an older version ({fv.period}); keeping the newer stored one ({stored.period})")
        return None
    snap = common.write_snapshot(SOURCE_ID, r.content, ".html", url=URL)
    print(f"{SOURCE_ID}: {'unchanged' if snap.unchanged else 'new snapshot'}; fund value {fv.value} bn kr at {fv.period}")
    return snap
