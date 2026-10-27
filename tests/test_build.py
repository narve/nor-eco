import json
import shutil

import build as site_build
from checks import links, numbers
from paths import ROOT


def _build(tmp_path, name="site", **kw):
    out = tmp_path / name
    site_build.build(out, **kw)
    return out


def test_build_is_deterministic(tmp_path):
    a, b = _build(tmp_path, "a", include_fixture=True), _build(tmp_path, "b", include_fixture=True)
    fa = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
    assert fa == sorted(p.relative_to(b) for p in b.rglob("*") if p.is_file())
    for rel in fa:
        assert (a / rel).read_bytes() == (b / rel).read_bytes(), rel


def test_all_links_are_relative_and_resolve(tmp_path):
    out = _build(tmp_path, include_fixture=True)
    assert links.check_site_links(out) == []


def test_link_check_catches_root_absolute(tmp_path):
    out = _build(tmp_path)
    p = out / "index.html"
    p.write_text(p.read_text(encoding="utf-8").replace('href="kilder.html"', 'href="/kilder.html"', 1), encoding="utf-8")
    assert any("root-absolute" in e for e in links.check_site_links(out))


def test_site_works_from_a_subpath(tmp_path):
    """Moving the output under a prefix must not break any link (relative paths only)."""
    out = _build(tmp_path)
    nested = tmp_path / "host" / "nor-eco"
    shutil.copytree(out, nested)
    assert links.check_site_links(nested) == []


def test_fixture_dataset_bundle_is_published(tmp_path):
    out = _build(tmp_path, include_fixture=True)
    b = json.loads((out / "data/_fixture/test/utgifter.json").read_text(encoding="utf-8"))
    assert b["columns"][:4] == ["period", "value", "unit", "status"] and len(b["rows"]) == 54
    assert "formaal" in b["dimensions"] and "niva" in b["dimensions"]
    assert not (out / "data" / "test").exists()


def test_fixture_not_in_default_build(tmp_path):
    out = _build(tmp_path)
    assert not (out / "data" / "_fixture").exists()
    assert "Syntetisk" not in (out / "kilder.html").read_text(encoding="utf-8")


def test_goatcounter_only_in_base_and_https(tmp_path):
    out = _build(tmp_path)
    html = (out / "index.html").read_text(encoding="utf-8")
    assert 'src="https://gc.zgo.at/count.js"' in html and 'src="//' not in html


def test_template_numbers_lint_passes():
    assert numbers.lint_templates(ROOT / "site_src" / "templates") == []


def test_template_numbers_lint_catches_hardcoded_number():
    assert numbers.lint_template("<p>Underskuddet var 123,4 mrd.</p>", ["CC BY 4\\.0"], r"(19|20)\d\d") == ["123,4"]
    assert numbers.lint_template("<p>{{ fmt(x) }} i 2024, ring 3, CC BY 4.0</p>", ["CC BY 4\\.0", r"[Rr]ing [1-7]"], r"(19|20)\d\d") == []
