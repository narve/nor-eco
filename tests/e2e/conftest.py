import functools
import http.server
import threading

import pytest

import build as site_build

pytest.importorskip("playwright")


@pytest.fixture(scope="session")
def site_url(tmp_path_factory):
    """Build the site and serve it under /nor-eco/ (a subpath, like GitHub Pages)."""
    base = tmp_path_factory.mktemp("host")
    site_build.build(base / "nor-eco", include_fixture=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(base))
    handler.log_message = lambda *a, **k: None
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/nor-eco/"
    httpd.shutdown()


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch()
        original = b.new_context

        def new_context(*args, **kwargs):
            """Tests talk only to the local server: external requests (analytics) are aborted, so tests are
            deterministic, cannot stall on the network, and never send hits to the real counter."""
            ctx = original(*args, **kwargs)
            ctx.route(lambda url: not url.startswith("http://127.0.0.1"), lambda route: route.abort())
            return ctx

        b.new_context = new_context
        yield b
        b.close()


@pytest.fixture
def mobile(browser):
    ctx = browser.new_context(viewport={"width": 360, "height": 740}, device_scale_factor=2, has_touch=True, is_mobile=True)
    page = ctx.new_page()
    yield page
    ctx.close()


@pytest.fixture
def desktop(browser):
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    page = ctx.new_page()
    yield page
    ctx.close()
