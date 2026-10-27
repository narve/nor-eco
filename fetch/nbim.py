"""NBIM «The fund's value» page: the latest value of Statens pensjonsfond utland and its split.

Only the sentence NBIM prints at the top of the page is used («At end of the first half of 2026, the fund's
value was 22,683 billion kroner. ... 15,210 ... 5,509 ... 1,965 ...»). The page has no machine-readable
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
    r"At end of (?P<when>the first half of \d{4}|\d{4}), the fund[’']s value was (?P<value>[\d,]+) billion kroner\."
    r".*?totaled to (?P<ret>[\d,]+) billion kroner\. (?P<inflow>[\d,]+) billion kroner was net inflows from the government"
    r" and (?P<fx>[\d,]+) billion kroner came from currency"
)


@dataclass(frozen=True)
class FundValue:
    period: str          # "2026-06" (end of June) or "2025-12"
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
    period = f"{year}-06" if "first half" in when else f"{year}-12"
    n = lambda s: int(s.replace(",", ""))  # noqa: E731
    return FundValue(period, n(m["value"]), n(m["inflow"]), n(m["ret"]), n(m["fx"]))


def run() -> common.Snapshot:
    r = common.http_get(URL)
    fv = parse(r.content)  # fail before storing anything if the page no longer parses
    snap = common.write_snapshot(SOURCE_ID, r.content, ".html", url=URL)
    print(f"{SOURCE_ID}: {'unchanged' if snap.unchanged else 'new snapshot'}; fund value {fv.value} bn kr at {fv.period}")
    return snap
