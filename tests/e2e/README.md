# End-to-end tests (Playwright, Python)

Run with the site served from a **subpath** to prove the links are relative:

    uv run pytest tests/e2e

`conftest.py` builds the site (with the synthetic fixture) into a temp dir and serves it at
`http://127.0.0.1:<port>/nor-eco/`. One-time browser install: `uv run playwright install chromium`.
Mobile checks use a Pixel profile (360 px wide); desktop checks use 1280 px.
WS5 adds a test per view: no horizontal page scroll, tap targets >= 44 px, drill-down and back work.
