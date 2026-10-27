"""waffle view and the employment page."""

import pytest

pytestmark = pytest.mark.e2e


def test_allocate_sums_to_exactly_the_number_of_cells_and_keeps_order_of_shares(desktop, site_url):
    desktop.goto(site_url + "galleri/fixture.html")
    out = desktop.evaluate("""async () => {
      const W = await import(new URL('../assets/js/views/waffle.js', location.href).href);
      return {a: W.allocate([1, 1, 1]), b: W.allocate([50, 30, 20]), c: W.allocate([0.4, 99.6]), d: W.allocate([0, 0]), e: W.allocate([2912303, 1273426])};
    }""")
    assert out["a"] == [134, 133, 133] and sum(out["a"]) == 400  # leftover square goes to the first of equal fractions
    assert out["b"] == [200, 120, 80]
    assert out["c"] == [2, 398] and out["d"] == [0, 0]
    assert sum(out["e"]) == 400 and out["e"][0] == 278  # 2 912 303 / 4 185 729 of 400 = 278.3 (the labour force)


def test_register_waffle_has_400_squares_and_striped_overlap_groups(desktop, site_url):
    desktop.goto(site_url + "sysselsetting.html")
    desktop.wait_for_selector("#register-15-74 .wf-cell")
    assert desktop.locator("#register-15-74 .wf-cell").count() == 400
    striped = desktop.locator("#register-15-74 .wf-cell").evaluate_all("els => els.filter(e => e.style.background.includes('repeating-linear-gradient')).length")
    assert striped > 0  # «sysselsatte og under utdanning» etc. are drawn striped
    legend = desktop.locator("#register-15-74 .wf-key").all_inner_texts()
    assert len(legend) == 12 and any("uføretrygd" in l for l in legend)
    assert any("Kun sysselsatte" in l for l in legend)


def test_waffle_shares_in_the_legend_add_up_to_100(desktop, site_url):
    import re
    desktop.goto(site_url + "sysselsetting.html")
    desktop.wait_for_selector("#register-15-74 .wf-key")
    pcts = [float(re.search(r"([\d ]+,\d) %", t.replace("\n", " ")).group(1).replace(",", ".")) for t in desktop.locator("#register-15-74 .wf-pct").all_inner_texts()]
    assert sum(pcts) == pytest.approx(100, abs=0.7)


def test_waffle_legend_isolates_a_group_on_hover(desktop, site_url):
    desktop.goto(site_url + "sysselsetting.html")
    desktop.wait_for_selector("#register-15-74 .wf-key")
    desktop.locator("#register-15-74 .wf-key").nth(5).hover()  # registrerte arbeidsledige
    assert desktop.locator("#register-15-74 .wf-cell.is-dim").count() > 300
    desktop.mouse.move(5, 5)
    assert desktop.locator("#register-15-74 .wf-cell.is-dim").count() == 0


def test_groups_not_covering_a_leaf_is_an_error_not_a_silent_drop(desktop, site_url):
    desktop.goto(site_url + "galleri/fixture.html")
    msg = desktop.evaluate("""async () => {
      const W = await import(new URL('../assets/js/views/waffle.js', location.href).href);
      const n = {label: 'x', unit: 'personer', path: '', value: 10, claim_level: 'offisiell', children: [
        {label: 'a', unit: 'personer', path: 'd:a', value: 6, claim_level: 'offisiell'}, {label: 'b', unit: 'personer', path: 'd:b', value: 4, claim_level: 'offisiell'}]};
      try { W.renderWaffle(document.createElement('div'), n, {groups: [{label: 'A', codes: ['a'], color: 1}]}); return 'no error'; } catch (e) { return e.message; }
    }""")
    assert "do not cover: b" in msg


def test_employment_page_numbers_and_waffle_agree(desktop, site_url):
    """The register waffle's total (both sexes, latest year) is the sum the legend prints; the key figure for employed matches the legend."""
    import re
    desktop.goto(site_url + "sysselsetting.html")
    desktop.wait_for_selector("#register-15-74 .wf-key")
    def n(t):
        return float(re.sub(r"[^\d,]", "", t).replace(",", "."))
    values = [n(v) for v in desktop.locator("#register-15-74 .wf-num").all_inner_texts()]
    total = sum(values)
    assert 4.0e6 < total < 4.4e6  # residents 15-74
    card = desktop.locator("#nokkeltall .card").first.inner_text()
    employed_thousand = n(re.search(r"([\d ]+)\s*tusen", card).group(1))
    assert sum(values[:5]) / 1000 == pytest.approx(employed_thousand, abs=1.5)  # the five employed groups = «Sysselsatte, registerbasert»


def test_waffle_fits_on_phone(mobile, site_url):
    mobile.goto(site_url + "sysselsetting.html")
    mobile.wait_for_selector("#register-15-74 .wf-cell")
    mobile.wait_for_timeout(300)
    assert mobile.evaluate("document.documentElement.scrollWidth") <= mobile.evaluate("document.documentElement.clientWidth")
    box = mobile.locator("#register-15-74 .wf-grid").bounding_box()
    assert box["width"] > 300 and box["width"] <= 360
