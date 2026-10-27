import build as site_build
from paths import SYNTH


def test_cite_and_chart_macros_render(tmp_path):
    env = site_build.make_env()
    srcs = site_build.load_registry(SYNTH / "registry.yaml")
    for s in srcs:
        s.setdefault("table_id", None)
    tpl = env.from_string(
        '{% from "macros.html" import chart, cite with context %}'
        '{% call chart("c1", "Tittel", ["test-kilde-a"], definition="Slik telles det.", level="utledet") %}<table></table>{% endcall %}'
    )
    html = tpl.render(root="../", sources_by_id={s["id"]: s for s in srcs}, views_cfg=[], explainers={})
    assert 'href="https://example.org/kilde-a"' in html
    assert 'href="../kilder.html#kilde-test-kilde-a"' in html
    assert "Vis tallene" in html and "Hva telles?" in html and "claim-utledet" in html
