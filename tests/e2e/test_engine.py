"""Dimension engine, URL state and number formatting, run in the browser against the synthetic dataset."""

import pytest

from transform.format import fmt as py_fmt

pytestmark = pytest.mark.e2e

JS = """
async ([body, arg]) => {
  const u = (p) => import(new URL('../assets/js/' + p, location.href).href);
  const E = await u('core/engine.js'), U = await u('core/url.js'), F = await u('core/format.js');
  const bundle = await (await fetch(new URL('../data/_fixture/test/utgifter.json', location.href))).json();
  const ds = E.createDataset(bundle);
  return await (new Function('E', 'U', 'F', 'ds', 'arg', 'return (async () => {' + body + '})()'))(E, U, F, ds, arg);
}
"""


@pytest.fixture
def pg(desktop, site_url):
    desktop.goto(site_url + "galleri/fixture.html")
    return desktop


def run(pg, body, arg=None):
    return pg.evaluate(JS, [body, arg])


def test_root_equals_children_plus_other_in_every_dimension(pg):
    out = run(pg, """
      const res = {};
      for (const dim of ds.dimIds) {
        const n = E.nodeFor(ds, {path: '', dim, period: '2023'});
        const sum = n.children.reduce((a, c) => a + c.value, 0) + (n.other ? n.other.value : 0);
        res[dim] = [n.value, sum];
      }
      return res;""")
    totals = {round(v[0], 6) for v in out.values()}
    assert len(totals) == 1  # every dimension gives the same total
    for total, summed in out.values():
        assert summed == pytest.approx(total, abs=1e-9)


def test_drill_and_switch_dimension_at_a_node(pg):
    out = run(pg, """
      const helse = E.nodeFor(ds, {path: 'formaal:helse', dim: 'formaal', period: '2023'});
      const byNiva = E.nodeFor(ds, {path: 'formaal:helse', dim: 'niva', period: '2023'});
      const stat = byNiva.children.find((c) => c.label === 'Stat');
      return {helse: helse.value, kids: helse.children.map((c) => c.label), other: helse.other.label,
              kidSum: helse.children.reduce((a, c) => a + c.value, 0) + helse.other.value,
              byNivaSum: byNiva.children.reduce((a, c) => a + c.value, 0) + byNiva.other.value,
              statPath: stat.path, statValue: stat.value};""")
    assert out["kids"] == ["Behandling", "Forebygging"] and out["other"].startswith("Øvrig")
    assert out["kidSum"] == pytest.approx(out["helse"], abs=1e-9)
    assert out["byNivaSum"] == pytest.approx(out["helse"], abs=1e-9)
    assert out["statPath"] == "formaal:helse/niva:stat"
    # (60 + 8 + 2) * 1.05 in 2023, stat share 0.6
    assert out["statValue"] == pytest.approx(70 * 1.05 * 0.6, abs=1e-6)


def test_claim_level_is_worst_of_and_status_follows_period(pg):
    out = run(pg, """
      const leaf = E.nodeFor(ds, {path: 'formaal:forebygging/niva:kommune', dim: 'formaal', period: '2024'});
      const helse = E.nodeFor(ds, {path: 'formaal:helse', dim: 'formaal', period: '2024'});
      const stat = E.nodeFor(ds, {path: 'formaal:forsvar', dim: 'niva', period: '2024'});
      return {leaf: leaf.claim_level, helse: helse.claim_level, forsvar: stat.claim_level, status: helse.status,
              sources: helse.source_ids};""")
    assert out["leaf"] == "estimat" and out["helse"] == "estimat" and out["forsvar"] == "offisiell"
    assert out["status"] == "vedtatt" and out["sources"] == ["test-kilde-a", "test-kilde-b"]


def test_units_percent_of_parent_sums_to_100_and_ratio_uses_denominator(pg):
    out = run(pg, """
      const pct = E.nodeFor(ds, {path: '', dim: 'formaal', period: '2023', unit: E.BUILTIN_UNITS['pct-parent']});
      const sum = pct.children.reduce((a, c) => a + c.value, 0) + pct.other.value;
      const ratio = {id: 'r', kind: 'ratio', unit: 'prosent', series: 'x', scale: 100, price_basis: 'løpende'};
      const r = E.nodeFor(ds, {path: '', dim: 'formaal', period: '2023', unit: ratio, denominators: {x: {'2023': 400}}});
      const faste = E.unitDisabledReason({meta: {price_basis: 'faste'}}, ratio);
      return {sum, top: pct.value, ratio: r.value, raw: r.raw, faste, ok: E.unitDisabledReason(ds, ratio)};""")
    assert out["sum"] == pytest.approx(100, abs=1e-9) and out["top"] == pytest.approx(100)
    assert out["ratio"] == pytest.approx(out["raw"] * 100 / 400)
    assert "løpende" in out["faste"] or "faste" in out["faste"]
    assert out["ok"] is None


def test_timeline_has_a_value_per_period_and_keeps_gaps_out_of_other_series(pg):
    out = run(pg, """
      const t = E.timeline(ds, {path: '', dim: 'formaal'});
      return {periods: t.periods, labels: t.series.map((s) => s.label),
              n: t.series.map((s) => s.values.length), st: t.series[0].values.map((v) => v.status)};""")
    assert out["periods"] == ["2022", "2023", "2024"]
    assert out["labels"][-1].startswith("Øvrig") and set(out["n"]) == {3}
    assert out["st"] == ["regnskap", "regnskap", "vedtatt"]


def test_unknown_path_is_an_error(pg):
    out = run(pg, "try { E.nodeFor(ds, {path: 'formaal:finnes_ikke', dim: 'formaal', period: '2023'}); return 'no error'; } catch (e) { return e.message; }")
    assert "unknown" in out


def test_url_path_roundtrip(pg):
    out = run(pg, """
      const segs = U.parsePath('formaal:helse/niva:stat');
      return [segs, U.formatPath(segs), U.parsePath('')];""")
    assert out[0] == [{"dim": "formaal", "code": "helse"}, {"dim": "niva", "code": "stat"}]
    assert out[1] == "formaal:helse/niva:stat" and out[2] == []


CASES = [0, 1, 12, 12.5, 999, 1000, 1234.5, 1234567.891, 0.25, 2.5, 0.125, 1.005, -3.25, -0.001, 5511.334, 4.6e-7, 99999.995, 1e6]


@pytest.mark.parametrize("decimals", [None, 0, 1, 2])
def test_js_and_python_format_numbers_identically(pg, decimals):
    js = run(pg, "return arg.cases.map((v) => F.fmt(v, arg.d));", {"cases": CASES, "d": decimals})
    assert js == [py_fmt(v, decimals) for v in CASES]


def test_js_and_python_period_labels_agree(pg):
    assert run(pg, "return [F.periodLabel('2025'), F.periodLabel('2026-06'), F.periodLabel('2024-02')];") == ["2025", "30. juni 2026", "29. februar 2024"]
