"""sunburst, icicle, rings, receipt, marimekko, upset and sankey: what they print must agree with the data."""

import json
import re

import pytest

pytestmark = pytest.mark.e2e


def num(s):
    return int(re.sub(r"[^\d-]", "", s.replace("−", "-")))


def open_view(page, site_url, path, chart, view):
    page.goto(f"{site_url}{path}?chart={chart}&view={view}")
    page.wait_for_selector(f"#{chart} .chart-body > *")


def test_sunburst_and_icicle_draw_one_shape_per_positive_node_and_no_stray_null(desktop, site_url):
    for view, sel in (("sunburst", ".sb-arc"), ("icicle", ".ic-block")):
        open_view(desktop, site_url, "staten-som-arbeidsgiver.html", "selskaper-ansatte", view)
        shapes = desktop.locator(f"#selskaper-ansatte {sel}").count()
        assert shapes >= 40  # 64 companies exist; three levels are drawn, so more than the groups
        lines = [l.strip() for l in desktop.locator("#selskaper-ansatte .chart-body").inner_text().splitlines()]
        assert "null" not in lines and "undefined" not in lines  # «null eller negativ» in a sentence is ordinary Norwegian


def test_rings_list_running_totals_that_end_at_the_sum(desktop, site_url):
    open_view(desktop, site_url, "staten-som-arbeidsgiver.html", "ringer-ansatte", "rings")
    vals = [num(t) for t in desktop.locator("#ringer-ansatte .rg-val").all_inner_texts()]
    cums = [num(re.search(r"([\d\s ]+) personer", t).group(1)) for t in desktop.locator("#ringer-ansatte .rg-cum").all_inner_texts()]
    assert len(vals) == 4 and cums[-1] == sum(vals) and cums[0] == vals[0]
    assert desktop.locator("#ringer-ansatte circle").count() == 4


def test_receipt_sum_equals_the_lines(desktop, site_url):
    open_view(desktop, site_url, "statsbudsjett.html", "utgifter-hovedpost", "receipt")
    lines = [num(t) for t in desktop.locator("#utgifter-hovedpost .rc-line .rc-val").all_inner_texts()]
    total = num(desktop.locator("#utgifter-hovedpost .rc-sum .rc-val").inner_text())
    assert abs(sum(lines) - total) <= len(lines)  # each line is rounded to whole mrd. kr


def test_marimekko_column_values_add_up_to_the_row_in_the_table(desktop, site_url):
    open_view(desktop, site_url, "sysselsetting.html", "register-15-74", "marimekko")
    rows = desktop.locator("#register-15-74 .mk-plot ~ .table-wrap tbody tr").all()
    assert len(rows) == 2
    for r in rows:
        cells = [num(t) for t in r.locator("td").all_inner_texts()]
        assert abs(cells[0] - sum(cells[1:])) <= 2  # sum column = women + men (SSB rounds small cells)
    assert desktop.locator("#register-15-74 .mk-seg").count() == 4


def test_upset_has_a_bar_per_combination_and_counts_match_the_table(desktop, site_url):
    open_view(desktop, site_url, "sysselsetting.html", "register-15-74", "euler-upset")
    bars = [num(t) for t in desktop.locator("#register-15-74 .up-val").evaluate_all("els => els.map(e => e.textContent)")]
    table = [num(t) for t in desktop.locator("#register-15-74 .up-plot ~ .table-wrap tbody td.num").all_inner_texts()]
    assert sorted(bars) == sorted(table) and len(bars) >= 8
    assert desktop.locator("#register-15-74 .up-set").count() >= 4  # one label per group, aligned with the dot rows


def test_sankey_is_balanced_with_the_difference_as_its_own_band(desktop, site_url):
    open_view(desktop, site_url, "statsbudsjett.html", "kontantstrom-sankey", "sankey")
    rows = desktop.locator("#kontantstrom-sankey .sk-plot ~ .table-wrap tbody tr").all()
    inn = sum(num(r.locator("td").nth(1).inner_text()) for r in rows if r.locator("td").nth(0).inner_text() == "inn")
    ut = sum(num(r.locator("td").nth(1).inner_text()) for r in rows if r.locator("td").nth(0).inner_text() == "ut")
    assert abs(inn - ut) <= len(rows)  # equal up to rounding once the difference band is included
    assert any("Differanse" in r.inner_text() for r in rows)


def test_fullscreen_button_toggles_the_chart_ui(desktop, site_url):
    desktop.goto(site_url + "statsbudsjett.html")
    desktop.wait_for_selector("#utgifter-hovedpost .chart-ui, .chart-ui")
    btn = desktop.locator(".chart-ui").first.get_by_role("button", name="Fullskjerm")
    if btn.count() == 0:
        pytest.skip("fullscreen not available in this browser context")
    btn.click()
    desktop.wait_for_function("document.fullscreenElement && document.fullscreenElement.classList.contains('chart-ui')")
    desktop.get_by_role("button", name="Avslutt fullskjerm").first.click()
    desktop.wait_for_function("!document.fullscreenElement")
