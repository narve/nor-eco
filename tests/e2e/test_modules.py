"""waterfall, treemap and slope in the browser."""

import pytest

pytestmark = pytest.mark.e2e


def num(text):
    import re
    m = re.search(r"[−-]?[\d  ]+(?:,\d+)?", text.replace("−", "-"))
    return float(m.group(0).replace(" ", "").replace(" ", "").replace(",", "."))


def test_waterfall_chain_balances_and_has_no_unexplained_step(desktop, site_url):
    desktop.goto(site_url + "statsbudsjett.html")
    desktop.wait_for_selector("#kjede-waterfall .wf-row")
    rows = desktop.locator("#kjede-waterfall .wf-row")
    values = [num(v) for v in rows.locator(".wf-value").all_inner_texts()]
    assert len(values) == 5 and desktop.locator("#kjede-waterfall .is-residual").count() == 0
    assert values[0] + values[1] == pytest.approx(values[2], abs=0.06)  # 188,3 - 664,0 = -475,7
    assert values[2] + values[3] == pytest.approx(values[4], abs=0.06)  # -475,7 - 31,7 = -507,4
    assert rows.nth(2).get_attribute("class").count("is-total") == 1 and desktop.locator("#kjede-waterfall .wf-zero").count() >= 1


def test_waterfall_shows_unexplained_difference_when_a_checkpoint_does_not_add_up(desktop, site_url):
    desktop.goto(site_url + "galleri/fixture.html")
    out = desktop.evaluate("""async () => {
      const W = await import(new URL('../assets/js/views/waterfall.js', location.href).href);
      return W.buildRows([{label: 'a', role: 'start', value: 100}, {label: 'b', role: 'delta', value: -30},
                          {label: 'sum', role: 'total', value: 0, expected: 60}]).map((r) => [r.label, r.value, !!r.residual]);
    }""")
    assert out == [["a", 100, False], ["b", -30, False], ["Ikke forklart", -10, True], ["sum", 60, False]]


def test_treemap_tiles_cover_the_area_and_negative_values_are_reported(desktop, site_url):
    desktop.goto(site_url + "statsbudsjett.html?chart=utgifter-formaal&view=treemap&year=2023")
    desktop.wait_for_selector("#utgifter-formaal .tm-tile")
    assert desktop.locator("#utgifter-formaal .tm-tile").count() == 10
    areas = desktop.locator("#utgifter-formaal .tm-tile").evaluate_all("els => els.map(e => e.offsetWidth * e.offsetHeight)")
    plot = desktop.locator("#utgifter-formaal .tm-plot").evaluate("e => e.offsetWidth * e.offsetHeight")
    assert 0.85 * plot < sum(areas) <= plot  # squarified tiles fill the plot (minus the padding between them)
    assert desktop.locator("#utgifter-formaal .tm-tile.is-prelim").count() == 0
    # split by sector: the difference node is negative, cannot be drawn as area, and must be reported in text
    desktop.locator("#utgifter-formaal .crumbs select").select_option("sektor")
    desktop.wait_for_function("document.querySelectorAll('#utgifter-formaal .tm-tile').length === 2")
    assert "vises ikke som flate" in desktop.locator("#utgifter-formaal").inner_text() and "Differanse" in desktop.locator("#utgifter-formaal").inner_text()


def test_treemap_two_taps_drill(desktop, site_url):
    desktop.goto(site_url + "statsbudsjett.html?chart=forslag-utgifter-detalj&view=treemap")
    desktop.wait_for_selector("#forslag-utgifter-detalj .tm-tile")
    tile = desktop.locator('#forslag-utgifter-detalj .tm-tile[aria-label^="Sum folketrygden"]')
    tile.click()
    assert "Sum folketrygden" in desktop.locator("#forslag-utgifter-detalj .readout").inner_text()
    desktop.locator('#forslag-utgifter-detalj .tm-tile[aria-label^="Sum folketrygden"]').click()
    desktop.wait_for_selector('#forslag-utgifter-detalj .crumb:has-text("Sum folketrygden")')
    assert desktop.locator('#forslag-utgifter-detalj .tm-tile[aria-label^="Alderspensjon"]').count() == 1


def test_derived_difference_only_counts_towards_claim_when_it_is_looked_at(desktop, site_url):
    desktop.goto(site_url + "statsbudsjett.html?chart=utgifter-formaal&view=hier-bars&year=2023")
    desktop.wait_for_selector("#utgifter-formaal .hb-row")
    assert desktop.locator("#utgifter-formaal .hb-bar.claim-utledet").count() == 0  # purposes: all official
    desktop.locator("#utgifter-formaal .crumbs select").select_option("sektor")
    desktop.wait_for_function("document.querySelector('#utgifter-formaal .hb-row')?.textContent.includes('Statsforvaltningen')")
    rows = desktop.locator("#utgifter-formaal .hb-row")
    assert rows.last.locator(".hb-bar").get_attribute("class").count("claim-utledet") == 1  # the difference row is flagged
    assert "claim-utledet" not in rows.first.locator(".hb-bar").get_attribute("class")


def test_slope_uses_two_chosen_years_and_one_scale(desktop, site_url):
    desktop.goto(site_url + "statsbudsjett.html?chart=utgifter-formaal&view=slope&year=2023&year2=2005")
    desktop.wait_for_selector("#utgifter-formaal .sl-plot svg")
    assert desktop.locator("#utgifter-formaal .sl-plot svg line[stroke]").count() == 10
    assert "2005" in desktop.locator("#utgifter-formaal .sl-plot").inner_text() and "2023" in desktop.locator("#utgifter-formaal .sl-plot").inner_text()
    ys = desktop.locator("#utgifter-formaal .sl-plot text.sl-label").evaluate_all("els => els.map(e => +e.getAttribute('y'))")
    left = sorted(ys[:10])
    assert all(b - a >= 14.5 for a, b in zip(left, left[1:]))  # labels are nudged apart, none overlap
    desktop.locator("#utgifter-formaal select:near(:text('Fra år'))").first.select_option("2010")
    desktop.wait_for_function("location.search.includes('year2=2010')")


def test_slope_works_for_plain_series_and_has_no_console_errors(desktop, site_url):
    errors = []
    desktop.on("pageerror", lambda e: errors.append(str(e)))
    desktop.goto(site_url + "statsbudsjett.html?chart=utgifter-formaal&view=slope&year=2023&year2=2005")
    desktop.wait_for_selector("#utgifter-formaal .sl-plot svg")
    assert errors == []


@pytest.mark.parametrize("view", ["treemap", "slope"])
def test_new_views_fit_on_mobile(mobile, site_url, view):
    mobile.goto(site_url + f"statsbudsjett.html?chart=utgifter-formaal&view={view}&year=2023&year2=2005")
    mobile.wait_for_selector("#utgifter-formaal .chart-ui")
    mobile.wait_for_timeout(500)
    assert mobile.evaluate("document.documentElement.scrollWidth") <= mobile.evaluate("document.documentElement.clientWidth")


def test_slope_labels_stay_inside_the_svg_on_phone_and_desktop(site_url, browser):
    for width in (360, 900):
        ctx = browser.new_context(viewport={"width": width, "height": 800})
        pg = ctx.new_page()
        pg.goto(site_url + "statsbudsjett.html?chart=utgifter-formaal&view=slope&year=2023&year2=2005&dim=sektor")
        pg.wait_for_selector("#utgifter-formaal .sl-plot svg text.sl-label")
        pg.wait_for_timeout(300)
        box = pg.locator("#utgifter-formaal .sl-plot svg").bounding_box()
        for b in pg.locator("#utgifter-formaal .sl-plot text.sl-label").evaluate_all(
                "els => els.map(e => { const r = e.getBoundingClientRect(); return [r.left, r.right]; })"):
            assert b[0] >= box["x"] - 1 and b[1] <= box["x"] + box["width"] + 1, (width, b, box)
        ctx.close()


def test_gallery_mounts_every_view_without_errors(desktop, site_url):
    import yaml
    from paths import ROOT
    cfg = yaml.safe_load((ROOT / "site_src" / "gallery.yaml").read_text(encoding="utf-8"))["items"]
    expected = sum(len(g["views"]) for g in cfg)
    errors = []
    desktop.on("pageerror", lambda e: errors.append(str(e)))
    desktop.goto(site_url + "galleri/index.html")
    desktop.wait_for_function(f"document.querySelectorAll('.chart-ui').length === {expected}", timeout=15000)
    desktop.wait_for_timeout(800)
    empty = desktop.locator(".chart-body").evaluate_all("els => els.filter(e => !e.querySelector('.hb-row, .tm-tile, .receipt, svg')).map(e => e.closest('figure').id)")
    assert empty == [] and errors == []
    assert desktop.locator(".chart").count() == expected
    # the overview table lists every registered view
    reg = yaml.safe_load((ROOT / "site_src" / "views.yaml").read_text(encoding="utf-8"))["views"]
    assert desktop.locator("#oversikt tbody tr").count() == len(reg)


def test_gallery_charts_have_table_and_source_line(desktop, site_url):
    desktop.goto(site_url + "galleri/index.html")
    desktop.wait_for_selector(".chart-ui")
    bad = desktop.locator(".chart").evaluate_all("els => els.filter(e => !e.querySelector('details.datatable table') || !e.querySelector('.source')).map(e => e.id)")
    assert bad == []


@pytest.mark.parametrize("page", ["okonomi.html", "statsbudsjett.html", "sysselsetting.html", "staten-som-arbeidsgiver.html", "galleri/index.html"])
def test_no_readout_or_note_ever_shows_null_undefined_or_nan(desktop, site_url, page):
    """For every chart, switch through every view and click into it (first bar / tile / waffle key); check all chart text."""
    import re
    # «null» is ordinary Norwegian («ved null»); the defect is the literal glued onto text («foreløpignull»)
    bad = re.compile(r"[A-Za-zæøåÆØÅ0-9)]null\b|\bundefined\b|\bNaN\b|\[object ")
    desktop.goto(site_url + page)
    desktop.wait_for_selector(".chart-ui")
    desktop.wait_for_timeout(1200)
    checked = 0
    for i in range(desktop.locator(".chart-ui").count()):
        ui = desktop.locator(".chart-ui").nth(i)
        n_views = ui.locator('.seg[aria-label="Vis som"] button').count() or 1
        for v in range(n_views):
            if ui.locator('.seg[aria-label="Vis som"] button').count():
                ui.locator('.seg[aria-label="Vis som"] button').nth(v).click()
            for sel in (".hb-row", ".tm-tile", ".wf-key"):
                if ui.locator(sel).count():
                    ui.locator(sel).first.click()
                    checked += 1
            txt = ui.inner_text()
            assert not bad.search(txt), (page, i, v, bad.search(txt).group(0), txt[:300])
    assert checked > 0


def test_readout_of_a_preliminary_leaf_ends_cleanly(desktop, site_url):
    """The reported case: «… Offisielt tall · foreløpig» had a trailing «null»."""
    desktop.goto(site_url + "sysselsetting.html?chart=register-15-74&view=hier-bars&path=statusgruppe%3AA%2Fstatusgruppe%3AA.01")
    desktop.wait_for_selector('#register-15-74 .hb-row[data-path$="A.01xU03"]')
    desktop.locator('#register-15-74 .hb-row[data-path$="A.01xU03"]').click()
    t = desktop.locator("#register-15-74 .readout").inner_text()
    assert t.startswith("Sysselsatte og under ordinær utdanning") and "Offisielt tall" in t
    assert t.rstrip().endswith("foreløpig"), repr(t)
