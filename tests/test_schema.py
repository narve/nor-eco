import csv
import shutil

import yaml

from paths import SYNTH
from transform.schema import validate_dataset, validate_registry, validate_series, validate_tree


def _ids():
    rep, ids = validate_registry(SYNTH / "registry.yaml")
    assert rep.ok
    return ids


def test_fixture_tree_is_valid():
    assert validate_tree(SYNTH / "processed", SYNTH / "registry.yaml").ok


def test_real_data_tree_is_valid():
    from paths import ROOT
    rep = validate_tree(ROOT / "data" / "processed", ROOT / "sources" / "registry.yaml")
    assert rep.ok, rep.errors


def test_series_with_unknown_source_fails(tmp_path):
    p = tmp_path / "bnp.json"
    shutil.copy(SYNTH / "processed/test/bnp.json", p)
    assert not validate_series(p, {"nothing"}).ok


def test_derived_series_requires_derivation(tmp_path):
    import json
    d = json.loads((SYNTH / "processed/test/utledet_andel.json").read_text())
    del d["derivation"]
    p = tmp_path / "utledet_andel.json"
    p.write_text(json.dumps(d))
    assert any("derivation" in e for e in validate_series(p, _ids()).errors)


def _copy_dataset(tmp_path):
    dst = tmp_path / "utgifter"
    shutil.copytree(SYNTH / "processed/test/utgifter", dst)
    return dst


def test_dataset_sum_must_match_published_total(tmp_path):
    d = _copy_dataset(tmp_path)
    rows = list(csv.reader((d / "facts.csv").open(encoding="utf-8")))
    rows[1][1] = str(float(rows[1][1]) + 5)
    csv.writer((d / "facts.csv").open("w", encoding="utf-8", newline=""), lineterminator="\n").writerows(rows)
    assert any("published total" in e for e in validate_dataset(d, _ids()).errors)


def test_non_leaf_code_in_facts_fails(tmp_path):
    d = _copy_dataset(tmp_path)
    text = (d / "facts.csv").read_text(encoding="utf-8").replace(",behandling,", ",helse,", 1)
    (d / "facts.csv").write_text(text, encoding="utf-8")
    assert any("not a leaf" in e for e in validate_dataset(d, _ids()).errors)


def test_duplicate_fact_key_fails(tmp_path):
    d = _copy_dataset(tmp_path)
    lines = (d / "facts.csv").read_text(encoding="utf-8").splitlines()
    (d / "facts.csv").write_text("\n".join(lines + [lines[1]]) + "\n", encoding="utf-8")
    assert any("duplicate fact key" in e for e in validate_dataset(d, _ids()).errors)


def test_other_node_must_be_leaf(tmp_path):
    d = _copy_dataset(tmp_path)
    dims = yaml.safe_load((d / "dimensions.yaml").read_text(encoding="utf-8"))
    dims["dimensions"]["formaal"]["nodes"].append({"code": "x", "label": "X", "parent": "ovrig_formaal"})
    (d / "dimensions.yaml").write_text(yaml.safe_dump(dims, allow_unicode=True), encoding="utf-8")
    assert any("must be a leaf" in e for e in validate_dataset(d, _ids()).errors)


def test_every_dimension_gives_the_same_total():
    """Rows are fully specified leaves, so any dimension's roll-up equals the dataset total."""
    rows = list(csv.DictReader((SYNTH / "processed/test/utgifter/facts.csv").open(encoding="utf-8")))
    total = sum(float(r["value"]) for r in rows if r["period"] == "2023")
    for dim in ("formaal", "niva"):
        by_code = {}
        for r in rows:
            if r["period"] == "2023":
                by_code[r[dim]] = by_code.get(r[dim], 0) + float(r["value"])
        assert abs(sum(by_code.values()) - total) < 1e-9
