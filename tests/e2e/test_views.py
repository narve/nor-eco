"""View behaviour in the browser: hier-bars drill-down and URL state, timeseries, units, consistency with the table."""

import re

import pytest

from transform.format import fmt

pytestmark = pytest.mark.e2e
NBSP = " "


def num(text):
    """'1 234,5 mrd. kr' -> 1234.5"""
    m = re.search(r"[−-]?[\d  ]+(?:,\d+)?", text.replace("−", "-"))
    return float(m.group(0).replace(NBSP, "").replace(" ", "").replace(",", "."))


@pytest.fixture
def fx(desktop, site_url):
    desktop.goto(site_url + "galleri/fixture.html")
    desktop.wait_for_selector(".hb-row")
    return desktop


def rows(page):
    return page.locator(".hb-row").evaluate_all("els => els.map(e => [e.querySelector('.hb-label').textContent.replace(' ›','').trim(), e.querySelector('.hb-value').textContent, e.className, e.dataset.path])")


def test_bars_are_sorted_and_other_is_last_and_grey(fx):
    r = rows(fx)
    values = [num(v) for _, v, _, _ in r[:-1]]
    assert values == sorted(values, reverse=True)
    assert r[-1][0].startswith("Øvrig") and "is-other" in r[-1][2]
    assert fx.locator(".hb-ref").is_visible()  # parent total as reference bar


def test_two_taps_drill_and_breadcrumb_and_back_work(fx):
    fx.locator('.hb-row[data-path="formaal:helse"]').click()
    assert "Helse" in fx.locator(".readout").inner_text() and "formaal:helse" not in fx.url  # first tap selects only
    fx.locator('.hb-row[data-path="formaal:helse"]').click()
    fx.wait_for_function("location.search.includes('path=formaal%3Ahelse')")
    assert "chart=syntetisk" in fx.url
    assert [r[0] for r in rows(fx)][:2] == ["Behandling", "Forebygging"]
    crumbs = fx.locator(".crumb").all_inner_texts()
    assert crumbs == ["Utgifter", "Helse"]
    fx.go_back()
    fx.wait_for_function("!location.search.includes('path=')")
    labels = [r[0] for r in rows(fx)]
    assert "Helse" in labels and "Behandling" not in labels and fx.locator(".crumb").count() == 1


def test_state_in_url_is_restored_on_reload_and_is_shareable(fx, site_url):
    fx.goto(site_url + "galleri/fixture.html?chart=syntetisk&view=hier-bars&year=2022&unit=pct-parent&path=formaal%3Ahelse&dim=niva")
    fx.wait_for_selector(".hb-row")
    labels = [r[0] for r in rows(fx)]
    assert labels[:2] == ["Stat", "Kommune"]  # helse split by nivå
    vals = [num(v) for _, v, _, _ in rows(fx)]
    assert sum(vals) == pytest.approx(100, abs=0.15)  # percent of the node, rounded per bar
    assert fx.locator(".chip").all_inner_texts()[1] == "2022"


def test_switching_dimension_at_a_node_keeps_the_total(fx):
    fx.locator('.hb-row[data-path="formaal:helse"]').click(click_count=2)
    fx.wait_for_selector('.crumb:has-text("Helse")')
    helse = num(fx.locator(".hb-ref .hb-value").inner_text())
    fx.locator(".crumbs select").select_option("niva")
    fx.wait_for_function("document.querySelectorAll('.hb-row')[0]?.textContent.includes('Stat')")
    assert num(fx.locator(".hb-ref .hb-value").inner_text()) == helse
    parts = sum(num(v) for _, v, _, _ in rows(fx))
    assert parts == pytest.approx(helse, abs=0.2)


def test_leaf_cannot_be_drilled_and_shows_readout(fx):
    fx.locator('.hb-row[data-path="formaal:utdanning"]').click()
    assert "Åpne" not in fx.locator(".readout").inner_text()
    fx.locator('.hb-row[data-path="formaal:utdanning"]').click()
    assert "path=" not in fx.url


def test_estimat_and_preliminary_are_marked_and_status_fallback_is_explained(fx):
    assert fx.locator(".hb-bar.is-prelim").count() == 0  # default: accounts, latest accounts year
    fx.locator('select:near(:text("År"))').first.select_option("2024")  # only «vedtatt» exists for 2024
    assert fx.locator(".hb-bar.is-prelim").count() > 0
    assert "Regnskap finnes ikke for 2024. Viser Vedtatt." in fx.locator(".chart-note").inner_text()
    fx.locator('.hb-row[data-path="formaal:helse"]').click(click_count=2)
    fx.wait_for_selector('.crumb:has-text("Helse")')
    assert fx.locator(".hb-ref .hb-bar.claim-estimat").count() == 1  # the parent is as weak as its weakest part
    assert fx.locator(".hb-row .hb-bar.claim-estimat").count() == 1  # forebygging contains the estimat fact


def test_timeseries_views_render_series_legend_and_readout(fx):
    fx.get_by_role("button", name="Stablet").click()
    fx.wait_for_selector(".ts-plot svg")
    assert fx.locator(".ts-key").count() == 4  # helse, forsvar, utdanning, øvrig
    assert fx.locator(".ts-plot svg rect").count() >= 12
    assert "2023" in fx.locator(".readout strong").first.inner_text()  # default year = latest accounts year
    fx.locator(".ts-plot svg").focus()
    fx.keyboard.press("ArrowRight")
    assert "2024" in fx.locator(".readout strong").first.inner_text()
    fx.keyboard.press("ArrowLeft")
    assert "2023" in fx.locator(".readout strong").first.inner_text()
    fx.get_by_role("button", name="Linjer").click()
    fx.wait_for_selector(".ts-plot svg circle")
    assert fx.locator(".ts-plot svg line[stroke-dasharray]").count() >= 1  # vedtatt segment is dashed
    assert "chart=syntetisk" in fx.url and "view=timeseries-lines" in fx.url


def test_bars_have_accessible_names(fx):
    names = fx.locator(".hb-row").evaluate_all("els => els.map(e => e.getAttribute('aria-label'))")
    assert all(n and "mrd. kr" in n for n in names)


def test_real_page_bars_agree_with_the_table(desktop, site_url):
    desktop.goto(site_url + "okonomi.html?chart=eksport-lopende&view=hier-bars&year=2023")
    desktop.wait_for_selector("#eksport-lopende .hb-row")
    shown = {r[0]: r[1] for r in desktop.locator("#eksport-lopende .hb-row").evaluate_all(
        "els => els.map(e => [e.querySelector('.hb-label').textContent.trim(), e.querySelector('.hb-value').textContent])")}
    table = desktop.locator("#eksport-lopende table")
    heads = table.locator("thead th").evaluate_all("els => els.map(e => e.childNodes[0].textContent.trim())")  # table is in a closed <details>
    cells = table.locator("tbody tr", has=desktop.locator("th", has_text="2023")).locator("td").all_text_contents()
    by_name = dict(zip(heads[1:], cells))
    assert set(shown) == set(heads[1:-1])
    for name, text in shown.items():
        decimals = len(text.split("mrd")[0].strip().split(",")[1]) if "," in text.split("mrd")[0] else 0
        assert text.split(" mrd")[0] == fmt(num(by_name[name].replace("f", "")), decimals), name


def test_unit_choices_disable_what_does_not_apply(desktop, site_url):
    desktop.goto(site_url + "okonomi.html")
    desktop.wait_for_selector("#eksport-faste .hb-row")
    opts = desktop.locator("#eksport-faste select").nth(1).locator("option").evaluate_all("o => o.map(x => [x.value, x.disabled])")
    assert dict(opts)["pct-bnp"] is True and dict(opts)["per-innb"] is False  # % av BNP needs løpende priser
    desktop.goto(site_url + "okonomi.html")
    desktop.wait_for_selector("#eksport-lopende .hb-row")
    desktop.locator("#eksport-lopende select").nth(1).select_option("pct-bnp")
    assert "%" in desktop.locator("#eksport-lopende .hb-ref .hb-value").inner_text()


@pytest.mark.parametrize("path", ["okonomi.html", "galleri/fixture.html"])
def test_no_horizontal_scroll_with_charts_on_mobile(mobile, site_url, path):
    mobile.goto(site_url + path)
    mobile.wait_for_load_state("networkidle")
    mobile.wait_for_selector(".chart-ui")
    sw, cw = mobile.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    assert sw <= cw


def test_timeseries_resizes_with_its_container(desktop, site_url):
    desktop.goto(site_url + "okonomi.html")
    desktop.wait_for_selector("#bnp-lopende svg")
    w1 = desktop.locator("#bnp-lopende .ts-plot svg").get_attribute("width")
    desktop.set_viewport_size({"width": 500, "height": 800})
    desktop.wait_for_function("(w) => document.querySelector('#bnp-lopende .ts-plot svg').getAttribute('width') != w", arg=w1)


def test_chart_controls_have_44px_tap_targets_on_mobile(mobile, site_url):
    mobile.goto(site_url + "galleri/fixture.html")
    mobile.wait_for_selector(".hb-row")
    mobile.locator(".settings > summary").click()
    targets = mobile.locator(".settings select, .settings button, .settings summary, .hb-row, .crumb, .ts-key")
    boxes = targets.evaluate_all("els => els.filter(e => e.offsetParent !== null).map(e => [e.className || e.tagName, e.getBoundingClientRect().height])")
    assert boxes and all(h >= 43.5 for _, h in boxes), [b for b in boxes if b[1] < 43.5]
    mobile.get_by_role("button", name="Stablet").click()
    mobile.wait_for_selector(".ts-key")
    assert all(h >= 43.5 for h in mobile.locator(".ts-key").evaluate_all("els => els.map(e => e.getBoundingClientRect().height)"))


def test_status_toggle_never_adds_statuses_together(fx):
    """Synthetic data: leaves sum to 210 in 2022; 2023 is 5 % higher (accounts); 2024 is 10 % higher (vedtatt only)."""
    ref = lambda: num(fx.locator(".hb-ref .hb-value").inner_text())  # noqa: E731
    assert ref() == pytest.approx(210 * 1.05, abs=0.1)  # default: accounts, latest accounts year (2023)
    fx.get_by_role("button", name="Vedtatt").click()
    fx.wait_for_function("location.search.includes('status=vedtatt')")
    assert ref() == pytest.approx(210 * 1.05, abs=0.1)  # no vedtatt for 2023: falls back, never 441 (= both added)
    assert "Vedtatt finnes ikke for 2023. Viser Regnskap." in fx.locator(".chart-note").inner_text()
    fx.locator('select:near(:text("År"))').first.select_option("2024")
    assert ref() == pytest.approx(210 * 1.10, abs=0.1)
    fx.get_by_role("button", name="Regnskap").click()
    assert ref() == pytest.approx(210 * 1.10, abs=0.1)  # accounts do not exist for 2024: shows vedtatt, says so
    assert "Regnskap finnes ikke for 2024. Viser Vedtatt." in fx.locator(".chart-note").inner_text()


def test_derived_series_are_marked_in_legend_and_on_bars(desktop, site_url):
    desktop.goto(site_url + "statsbudsjett.html")
    desktop.wait_for_selector("#oljekorrigert-kr svg")
    assert desktop.locator("#oljekorrigert-kr .ts-key").first.inner_text().startswith("ƒ ")
    assert desktop.locator('#oljekorrigert-kr svg rect[fill="url(#ts-derived)"]').count() >= 20
    assert not desktop.locator("#oljekorrigert-pst .ts-key").first.inner_text().startswith("ƒ")  # official series carry no mark
    desktop.locator("#oljekorrigert-pst").get_by_role("button", name="Søyler over tid").click()
    assert desktop.locator('#oljekorrigert-pst svg rect[fill="url(#ts-derived)"]').count() == 0


def test_formaal_chart_switches_dimension_keeps_total_and_shows_residual_last(desktop, site_url):
    desktop.goto(site_url + "statsbudsjett.html?chart=utgifter-formaal&view=hier-bars&year=2023")
    desktop.wait_for_selector("#utgifter-formaal .hb-row")
    total = num(desktop.locator("#utgifter-formaal .hb-ref .hb-value").inner_text())
    assert total == pytest.approx(2348.721, abs=0.6)  # SSB: «Alle formål» 2023, 2 348 721 mill. kr
    assert desktop.locator("#utgifter-formaal .hb-row").count() == 10  # the ten main purposes
    desktop.locator("#utgifter-formaal .crumbs select").select_option("sektor")
    desktop.wait_for_function("document.querySelector('#utgifter-formaal .hb-row')?.textContent.includes('Statsforvaltningen')")
    labels = desktop.locator("#utgifter-formaal .hb-row .hb-label").all_inner_texts()
    assert labels[-1].startswith("Differanse") and "is-other" in desktop.locator("#utgifter-formaal .hb-row").last.get_attribute("class")
    vals = [num(v) for v in desktop.locator("#utgifter-formaal .hb-row .hb-value").all_inner_texts()]
    assert sum(vals) == pytest.approx(total, abs=1.5)  # state + kommune + the (negative) difference
    assert min(vals) < 0  # the difference is negative and drawn from a visible zero line
    assert desktop.locator("#utgifter-formaal .hb-zero").count() >= 1


def test_large_dataset_timeseries_renders_quickly(desktop, site_url):
    desktop.goto(site_url + "statsbudsjett.html?chart=utgifter-formaal&view=timeseries-stacked")
    t = desktop.evaluate("""async () => {
      await new Promise((r) => { const i = setInterval(() => { if (document.querySelector('#utgifter-formaal .ts-plot svg rect')) { clearInterval(i); r(); } }, 20); });
      return performance.now();
    }""")
    assert t < 6000, t
    assert desktop.locator("#utgifter-formaal .ts-key").count() == 10


def test_folketrygden_can_be_opened_to_its_benefits(desktop, site_url):
    desktop.goto(site_url + "statsbudsjett.html")
    desktop.wait_for_selector("#forslag-utgifter-detalj .hb-row")
    desktop.locator('#forslag-utgifter-detalj .hb-row:has-text("Sum folketrygden")').click(click_count=2)
    desktop.wait_for_selector('#forslag-utgifter-detalj .crumb:has-text("Sum folketrygden")')
    labels = desktop.locator("#forslag-utgifter-detalj .hb-row .hb-label").all_inner_texts()
    assert labels[:3] == ["Alderspensjon", "Uføretrygd", "Sykepenger"]
    ref = num(desktop.locator("#forslag-utgifter-detalj .hb-ref .hb-value").inner_text())
    assert ref == pytest.approx(794.1, abs=0.6)
    assert "path=" in desktop.url and "chart=forslag-utgifter-detalj" in desktop.url
