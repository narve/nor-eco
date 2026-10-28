"""Every real chart has a «Slik leser du figuren» entry; entries are neutral, number-free and point at real definitions."""

import re
from html.parser import HTMLParser

import yaml

import build as site_build
from checks import numbers
from paths import ROOT

EX = yaml.safe_load((ROOT / "site_src" / "explainers.yaml").read_text(encoding="utf-8"))["explainers"]
PAGES = ["okonomi.html", "statsbudsjett.html", "sysselsetting.html", "staten-som-arbeidsgiver.html"]  # the gallery reuses the same data, with generic help only


class _Charts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.with_explain = set()
        self._fig = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "figure" and "chart" in (a.get("class") or ""):
            self._fig = a["id"]
        if tag == "div" and "chart-mount" in (a.get("class") or "") and self._fig:
            self.ids.append(self._fig)
        if tag == "aside" and "explain" in (a.get("class") or "") and self._fig:
            self.with_explain.add(self._fig)


def _charts(out, page):
    p = _Charts()
    p.feed((out / page).read_text(encoding="utf-8"))
    return p


def test_every_chart_on_the_content_pages_has_an_explainer_entry_and_no_entry_is_orphaned(tmp_path):
    out = tmp_path / "site"
    site_build.build(out)
    seen = set()
    for page in PAGES:
        c = _charts(out, page)
        assert c.ids and set(c.ids) == c.with_explain, (page, set(c.ids) - c.with_explain)  # the aside is rendered for each
        missing = [i for i in c.ids if i not in EX]
        assert not missing, f"{page}: charts without an explainers.yaml entry: {missing}"
        seen |= set(c.ids)
    assert set(EX) == seen, f"explainers for charts that do not exist: {sorted(set(EX) - seen)}"


def test_explainer_text_has_no_hard_coded_numbers():
    cfg = yaml.safe_load(numbers.ALLOWLIST.read_text(encoding="utf-8"))
    for cid, e in EX.items():
        for t in e["text"]:
            assert numbers.lint_template(t, cfg["allow_phrases"], cfg["year"]) == [], (cid, t)


def test_explainer_quotes_exist_in_definitions():
    defs = {d["id"] for p in (ROOT / "definitions").glob("*.yaml") for d in yaml.safe_load(p.read_text(encoding="utf-8"))["definitions"]}
    for cid, e in EX.items():
        for q in e.get("quotes", []):
            assert q in defs, (cid, q)


def test_view_help_is_generated_for_each_view_a_chart_offers(tmp_path):
    out = tmp_path / "site"
    site_build.build(out)
    html = (out / "sysselsetting.html").read_text(encoding="utf-8")
    fig = html[html.index('id="register-15-74"'):]
    fig = fig[: fig.index("</figure>")]
    for label in ("Rutenett:", "Søyler:", "Flisekart:", "Stablet:"):
        assert label in fig
    assert re.search(r"Slik leser du figuren", fig)
