"""Validation of processed data against the schemas in schema/ plus the structural rules of
schema/README.md. Used by `python -m checks`, the tests, and `build.py`."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schema"
FACT_FIXED_COLUMNS = ["period", "value", "unit", "status"]
FACT_TAIL_COLUMNS = ["claim_level", "source_id"]
STATUSES = {"regnskap", "saldert", "vedtatt", "budsjett", "forslag", "anslag", "foreløpig"}
CLAIM_LEVELS = {"offisiell", "utledet", "estimat"}


def _schema(name: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8")))


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)

    def add(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    def extend(self, other: "Report") -> None:
        self.errors.extend(other.errors)

    @property
    def ok(self) -> bool:
        return not self.errors


def _schema_errors(validator: Draft202012Validator, instance: object, where: str, rep: Report) -> None:
    for e in sorted(validator.iter_errors(instance), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in e.path) or "(root)"
        rep.add(where, f"{loc}: {e.message}")


# --------------------------------------------------------------------------- series


def validate_series(path: Path, registry_ids: set[str]) -> Report:
    rep = Report()
    data = json.loads(path.read_text(encoding="utf-8"))
    _schema_errors(_schema("series.schema.json"), data, str(path), rep)
    if not rep.ok:
        return rep
    for sid in data["source_ids"]:
        if sid not in registry_ids:
            rep.add(str(path), f"source_id '{sid}' is not in the registry")
    for b in data.get("breaks", []):
        if "source_id" in b and b["source_id"] not in registry_ids:
            rep.add(str(path), f"break source_id '{b['source_id']}' is not in the registry")
    periods = [v["period"] for v in data["values"]]
    if len(periods) != len(set(periods)):
        rep.add(str(path), "duplicate periods in values")
    if periods != sorted(periods):
        rep.add(str(path), "values are not sorted by period")
    if path.stem != data["id"].split(".")[-1]:
        rep.add(str(path), f"file name must match the last part of id ('{data['id']}')")
    return rep


# --------------------------------------------------------------------------- dataset


def _load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _check_tree(dim_id: str, dim: dict, registry_ids: set[str], where: str, rep: Report) -> dict[str, dict]:
    nodes = {}
    for n in dim["nodes"]:
        if n["code"] in nodes:
            rep.add(where, f"dimension {dim_id}: duplicate code '{n['code']}'")
        nodes[n["code"]] = n
        if "source_id" in n and n["source_id"] not in registry_ids:
            rep.add(where, f"dimension {dim_id}: node '{n['code']}' has unknown source_id")
    roots = [c for c, n in nodes.items() if n["parent"] is None]
    if len(roots) != 1:
        rep.add(where, f"dimension {dim_id}: expected exactly one root, found {roots}")
    for c, n in nodes.items():
        if n["parent"] is not None and n["parent"] not in nodes:
            rep.add(where, f"dimension {dim_id}: node '{c}' has unknown parent '{n['parent']}'")
    # cycles / unreachable
    for c in nodes:
        seen, cur = set(), c
        while cur is not None and cur in nodes:
            if cur in seen:
                rep.add(where, f"dimension {dim_id}: cycle at '{c}'")
                break
            seen.add(cur)
            cur = nodes[cur]["parent"]
    children: dict[str, list[str]] = {}
    for c, n in nodes.items():
        if n["parent"]:
            children.setdefault(n["parent"], []).append(c)
    for c, n in nodes.items():
        if n.get("other") and c in children:
            rep.add(where, f"dimension {dim_id}: 'other' node '{c}' must be a leaf")
    for c, n in nodes.items():
        for o in n.get("overlap", []):
            if o not in nodes or o in children or c in children:
                rep.add(where, f"dimension {dim_id}: overlap '{o}' of '{c}' must name another leaf of the same dimension")
    return nodes


def validate_dataset(directory: Path, registry_ids: set[str]) -> Report:
    rep = Report()
    where = str(directory)
    meta_path, dims_path, facts_path = directory / "dataset.yaml", directory / "dimensions.yaml", directory / "facts.csv"
    for p in (meta_path, dims_path, facts_path):
        if not p.exists():
            rep.add(where, f"missing {p.name}")
    if not rep.ok:
        return rep
    meta = _load_yaml(meta_path)
    dims_doc = _load_yaml(dims_path)
    _schema_errors(_schema("dataset.schema.json"), meta, str(meta_path), rep)
    _schema_errors(_schema("dimensions.schema.json"), dims_doc, str(dims_path), rep)
    if not rep.ok:
        return rep
    if meta["claim_level"] in ("utledet", "estimat") and "derivation" not in meta:
        rep.add(str(meta_path), "claim_level utledet/estimat requires 'derivation'")
    for sid in meta["source_ids"]:
        if sid not in registry_ids:
            rep.add(str(meta_path), f"source_id '{sid}' is not in the registry")
    for t in meta.get("published_totals", []):
        if t["source_id"] not in registry_ids:
            rep.add(str(meta_path), f"published_totals source_id '{t['source_id']}' is not in the registry")

    dim_ids = meta["dimensions"]
    for d in dim_ids:
        if d not in dims_doc["dimensions"]:
            rep.add(where, f"dimension '{d}' is listed in dataset.yaml but missing in dimensions.yaml")
    if not rep.ok:
        return rep
    trees = {d: _check_tree(d, dims_doc["dimensions"][d], registry_ids, str(dims_path), rep) for d in dim_ids}
    leaves = {}
    for d, nodes in trees.items():
        parents = {n["parent"] for n in nodes.values() if n["parent"]}
        leaves[d] = {c for c in nodes if c not in parents}
    if meta.get("default_dimension") and meta["default_dimension"] not in dim_ids:
        rep.add(str(meta_path), "default_dimension is not one of dimensions")
    if not rep.ok:
        return rep

    with facts_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        expected = FACT_FIXED_COLUMNS + dim_ids + FACT_TAIL_COLUMNS
        if reader.fieldnames != expected:
            rep.add(str(facts_path), f"columns must be exactly {expected}, got {reader.fieldnames}")
            return rep
        seen: set[tuple] = set()
        sums: dict[tuple[str, str], float] = {}
        for i, row in enumerate(reader, start=2):
            loc = f"{facts_path}:{i}"
            try:
                value = float(row["value"])
            except ValueError:
                rep.add(loc, f"value '{row['value']}' is not a number")
                continue
            if row["status"] not in STATUSES:
                rep.add(loc, f"unknown status '{row['status']}'")
            if row["claim_level"] not in CLAIM_LEVELS:
                rep.add(loc, f"unknown claim_level '{row['claim_level']}'")
            if row["unit"] != meta["unit"]:
                rep.add(loc, f"unit '{row['unit']}' differs from dataset unit '{meta['unit']}'")
            if row["source_id"] not in registry_ids:
                rep.add(loc, f"unknown source_id '{row['source_id']}'")
            for d in dim_ids:
                if row[d] not in leaves[d]:
                    rep.add(loc, f"'{row[d]}' is not a leaf code of dimension '{d}'")
            key = (row["period"], row["status"], *[row[d] for d in dim_ids])
            if key in seen:
                rep.add(loc, f"duplicate fact key {key}")
            seen.add(key)
            sums[(row["period"], row["status"])] = sums.get((row["period"], row["status"]), 0.0) + value
    tol = meta.get("tolerance", 0.001)
    for t in meta.get("published_totals", []):
        key = (t["period"], t.get("status", "regnskap"))
        got = sums.get(key)
        if got is None:
            rep.add(str(meta_path), f"published total for {key} has no facts")
        elif abs(got - t["value"]) > tol * max(1.0, abs(t["value"])):
            rep.add(str(meta_path), f"sum of facts for {key} is {got}, published total is {t['value']}")
    return rep


# --------------------------------------------------------------------------- registry


def validate_registry(registry_path: Path) -> tuple[Report, set[str]]:
    rep = Report()
    doc = _load_yaml(registry_path) or {}
    ids: set[str] = set()
    required = ("id", "publisher", "title", "url", "licence")
    for s in doc.get("sources", []):
        for k in required:
            if not s.get(k):
                rep.add(str(registry_path), f"source {s.get('id', '?')}: missing '{k}'")
        sid = s.get("id", "")
        if sid in ids:
            rep.add(str(registry_path), f"duplicate source id '{sid}'")
        ids.add(sid)
        if not str(s.get("url", "")).startswith("https://"):
            rep.add(str(registry_path), f"source {sid}: url must be https")
    return rep, ids


# --------------------------------------------------------------------------- whole tree


def validate_tree(processed_dir: Path, registry_path: Path) -> Report:
    rep, ids = validate_registry(registry_path)
    if not processed_dir.exists():
        return rep
    for p in sorted(processed_dir.rglob("*.json")):
        rep.extend(validate_series(p, ids))
    for p in sorted(processed_dir.rglob("dataset.yaml")):
        rep.extend(validate_dataset(p.parent, ids))
    return rep
