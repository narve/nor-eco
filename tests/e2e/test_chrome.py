import pytest

pytestmark = pytest.mark.e2e

PAGES = ["index.html", "statsbudsjett.html", "okonomi.html", "sysselsetting.html",
         "staten-som-arbeidsgiver.html", "begreper.html", "kilder.html", "metode.html", "galleri/index.html"]


@pytest.mark.parametrize("path", PAGES)
@pytest.mark.parametrize("fixture", ["mobile", "desktop"])
def test_no_horizontal_scroll(request, site_url, path, fixture):
    page = request.getfixturevalue(fixture)
    page.goto(site_url + path)
    sw, cw = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    assert sw <= cw, f"{path}: scrollWidth {sw} > clientWidth {cw}"


def test_no_failed_requests_on_subpath(mobile, site_url):
    failed = []
    mobile.on("requestfailed", lambda r: failed.append(r.url))
    mobile.on("response", lambda r: failed.append(r.url) if r.status >= 400 and "goatcounter" not in r.url and "zgo.at" not in r.url else None)
    mobile.goto(site_url + "galleri/index.html")
    assert [u for u in failed if "zgo.at" not in u and "goatcounter" not in u] == []


def test_hamburger_opens_and_links_work(mobile, site_url):
    mobile.goto(site_url + "index.html")
    assert not mobile.locator(".topnav").is_visible()
    mobile.locator(".menu summary").click()
    assert mobile.locator(".menu-panel").is_visible()
    mobile.locator(".menu-panel nav a", has_text="Kilder").click()
    mobile.wait_for_url("**/nor-eco/kilder.html")
    assert not mobile.locator(".menu-panel").is_visible()


def test_tap_targets_on_mobile(mobile, site_url):
    mobile.goto(site_url + "index.html")
    mobile.locator(".menu summary").click()
    for loc in (mobile.locator(".menu summary"), mobile.locator(".theme-toggle"), *mobile.locator(".menu-panel nav a").all()):
        box = loc.bounding_box()
        assert box["height"] >= 44 and box["width"] >= 44 or box["height"] >= 44, box


def test_desktop_shows_top_nav_not_hamburger(desktop, site_url):
    desktop.goto(site_url + "index.html")
    assert desktop.locator(".topnav").is_visible()
    assert not desktop.locator(".menu").is_visible()


def test_theme_toggle_switches_tokens(desktop, site_url):
    desktop.goto(site_url + "index.html")
    before = desktop.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()")
    desktop.locator(".theme-toggle").click()
    after = desktop.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()")
    assert before != after


def test_fonts_load(desktop, site_url):
    desktop.goto(site_url + "index.html")
    desktop.wait_for_function("document.fonts.status === 'loaded'")
    assert desktop.evaluate("document.fonts.check('16px \"Space Grotesk\"')")
