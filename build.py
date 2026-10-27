"""Build the static site: processed data + templates -> site/ (deterministic; committed).

    uv run python build.py                  # build site/
    uv run python build.py --fixture        # also publish the synthetic test dataset (tests, dev)

All internal links and asset paths are relative (each page gets `root`, e.g. '' or '../').
The output has no timestamps, so rebuilding unchanged inputs gives identical files.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import json
import shutil
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from transform.format import fmt
from transform.schema import validate_tree

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "site_src"
OUT = ROOT / "site"
PROCESSED = ROOT / "data" / "processed"
REGISTRY = ROOT / "sources" / "registry.yaml"
RAW_MANIFEST = ROOT / "data" / "raw" / "MANIFEST.yaml"
DEFINITIONS = ROOT / "definitions"
FIXTURE = ROOT / "tests" / "fixtures" / "synthetic"

SITE_TITLE = "Norsk statsøkonomi – fra kildene"


def load_registry(path: Path) -> list[dict]:
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("sources", [])


def retrieval_dates(manifest: Path) -> dict[str, str]:
    """Latest retrieval date per source id, from the raw manifest (empty if nothing fetched yet)."""
    if not manifest.exists():
        return {}
    files = (yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}).get("files", [])
    out: dict[str, str] = {}
    for f in files:
        if f["retrieved"] > out.get(f["source_id"], ""):
            out[f["source_id"]] = f["retrieved"]
    return out


def load_definitions(directory: Path) -> list[dict]:
    items: list[dict] = []
    if directory.exists():
        for p in sorted(directory.glob("*.yaml")):
            for d in (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("definitions", []):
                items.append({**d, "topic": p.stem})
    return sorted(items, key=lambda d: d["term"].casefold())


TOPIC_PAGES = {"okonomi": "okonomi.html", "statsbudsjett": "statsbudsjett.html",
               "sysselsetting": "sysselsetting.html", "staten": "staten-som-arbeidsgiver.html"}


def load_processed(processed: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    """Series by id, and hierarchical datasets by id ({meta, dimensions, rows})."""
    series: dict[str, dict] = {}
    for p in sorted(processed.rglob("*.json")):
        obj = json.loads(p.read_text(encoding="utf-8"))
        obj["by_period"] = {v["period"]: v for v in obj["values"]}
        obj["topic"] = p.relative_to(processed).parts[0]
        series[obj["id"]] = obj
    datasets: dict[str, dict] = {}
    for ds in sorted(processed.rglob("dataset.yaml")):
        meta = yaml.safe_load(ds.read_text(encoding="utf-8"))
        dims = yaml.safe_load((ds.parent / "dimensions.yaml").read_text(encoding="utf-8"))["dimensions"]
        with (ds.parent / "facts.csv").open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        datasets[meta["id"]] = {"meta": meta, "dimensions": dims, "rows": rows,
                                "topic": ds.relative_to(processed).parts[0]}
    return series, datasets


def series_table(series: dict[str, dict], ids: list[str], newest_first: bool = True) -> dict:
    """Periods as rows, one column per series: {headers, units, periods, rows[[{value,status,claim}]]}."""
    cols = [series[i] for i in ids]
    periods = sorted({p for c in cols for p in c["by_period"]}, reverse=newest_first)
    rows = []
    for p in periods:
        row = []
        for c in cols:
            v = c["by_period"].get(p)
            row.append(None if v is None else {"value": v["value"], "status": v.get("status"),
                                               "claim": v.get("claim_level", c["claim_level"])})
        rows.append(row)
    return {"headers": [c["title"] for c in cols], "units": [c["unit"] for c in cols], "claims": [c["claim_level"] for c in cols],
            "periods": periods, "rows": rows}


def dataset_table(datasets: dict[str, dict], dataset_id: str, dim: str = "vare", newest_first: bool = True, status: str | None = None) -> dict:
    """Periods as rows, one column per leaf of `dim` plus the sum («I alt»)."""
    ds = datasets[dataset_id]
    nodes = ds["dimensions"][dim]["nodes"]
    leaves = [n for n in nodes if n["parent"] is not None and not any(m["parent"] == n["code"] for m in nodes)]
    root = next(n for n in nodes if n["parent"] is None)
    cell: dict[tuple[str, str], dict] = {}
    for r in ds["rows"]:
        if status and r["status"] != status:
            continue
        cell[(r["period"], r[dim])] = {"value": float(r["value"]), "status": r["status"], "claim": r["claim_level"]}
    periods = sorted({r["period"] for r in ds["rows"] if not status or r["status"] == status}, reverse=newest_first)
    rows = []
    for p in periods:
        row = [cell.get((p, n["code"])) for n in leaves]
        have = [c for c in row if c]
        total = {"value": round(sum(c["value"] for c in have), 3), "status": have[0]["status"], "claim": "offisiell"} if have else None
        rows.append(row + [total])
    return {"headers": [n["label"] for n in leaves] + [root["label"]], "units": [ds["meta"]["unit"]] * (len(leaves) + 1),
            "claims": [("utledet" if n["code"] == "kjedingsavvik" else "offisiell") for n in leaves] + ["offisiell"],
            "periods": periods, "rows": rows}


def dataset_value(datasets: dict[str, dict], dataset_id: str, code: str | None, period: str, dim: str = "vare", status: str | None = None) -> float:
    """One fact (code given) or the sum over all leaves (code None) for a period, as a number. `status` picks one status."""
    rows = [r for r in datasets[dataset_id]["rows"] if r["period"] == period and (code is None or r[dim] == code) and (status is None or r["status"] == status)]
    return round(sum(float(r["value"]) for r in rows), 3)


MONTHS = ["januar", "februar", "mars", "april", "mai", "juni", "juli", "august", "september", "oktober", "november", "desember"]


def period_label(period: str) -> str:
    """'2025' -> '2025'; '2026-06' -> '30. juni 2026' (end of the month)."""
    if len(period) == 7 and period[4] == "-":
        year, month = int(period[:4]), int(period[5:])
        return f"{calendar.monthrange(year, month)[1]}. {MONTHS[month - 1]} {year}"
    return period


def make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(SRC / "templates"),
        autoescape=select_autoescape(["html"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["fmt"] = fmt
    env.globals["period_label"] = period_label
    env.globals["dict"] = dict
    return env


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def write_json(path: Path, obj: object) -> None:
    write_text(path, json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")


def publish_data(processed: Path, out: Path, prefix: str = "") -> list[str]:
    """Copy series JSON and write columnar bundles for hierarchical datasets under out/data/."""
    published: list[str] = []
    for p in sorted(processed.rglob("*.json")):
        rel = p.relative_to(processed)
        dest = out / "data" / prefix / rel
        write_json(dest, json.loads(p.read_text(encoding="utf-8")))
        published.append(str(Path("data") / prefix / rel))
    for ds in sorted(processed.rglob("dataset.yaml")):
        d = ds.parent
        meta = yaml.safe_load(ds.read_text(encoding="utf-8"))
        dims = yaml.safe_load((d / "dimensions.yaml").read_text(encoding="utf-8"))["dimensions"]
        with (d / "facts.csv").open(encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            columns = next(reader)
            rows = []
            for r in reader:
                rows.append([float(c) if columns[i] == "value" else c for i, c in enumerate(r)])
        rel = d.relative_to(processed)
        dest = out / "data" / prefix / rel.parent / f"{rel.name}.json"
        write_json(dest, {"meta": meta, "dimensions": dims, "columns": columns, "rows": rows})
        published.append(str(dest.relative_to(out)))
    return published


def build(
    out: Path = OUT,
    processed: Path = PROCESSED,
    registry_path: Path = REGISTRY,
    manifest: Path = RAW_MANIFEST,
    definitions_dir: Path = DEFINITIONS,
    *,
    include_fixture: bool = False,
    validate: bool = True,
) -> list[Path]:
    """Build the whole site into `out` (which is wiped first). Returns the pages written."""
    if validate:
        report = validate_tree(processed, registry_path)
        if include_fixture:
            fr = validate_tree(FIXTURE / "processed", FIXTURE / "registry.yaml")
            report.errors.extend(fr.errors)
        if not report.ok:
            raise SystemExit("processed data failed validation:\n  " + "\n  ".join(report.errors))

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copytree(SRC / "assets", out / "assets")

    sources = load_registry(registry_path)
    if include_fixture:
        sources = sources + load_registry(FIXTURE / "registry.yaml")
    sources = sorted(sources, key=lambda s: s["id"])
    dates = retrieval_dates(manifest)
    for s in sources:
        s["retrieved"] = dates.get(s["id"])
        s.setdefault("table_id", None)
        s.setdefault("notes", None)
    pages_cfg = yaml.safe_load((SRC / "pages.yaml").read_text(encoding="utf-8"))["pages"]
    if include_fixture:  # test-only page showing the synthetic dataset; never part of the real site
        pages_cfg.append({"path": "galleri/fixture.html", "template": "fixture.html", "title": "Syntetiske testdata", "nav": "Testdata", "secondary": True})
    for p in pages_cfg:
        p.setdefault("secondary", False)
    definitions = load_definitions(definitions_dir)
    series, datasets = load_processed(processed)
    if include_fixture:
        fs, fd = load_processed(FIXTURE / "processed")
        series, datasets = {**series, **fs}, {**datasets, **fd}
    used_by: dict[str, set[str]] = {}
    for obj in list(series.values()) + [d["meta"] | {"topic": d["topic"]} for d in datasets.values()]:
        for sid in obj["source_ids"]:
            used_by.setdefault(sid, set()).add(obj["topic"])
    for d in definitions:
        used_by.setdefault(d["source_id"], set()).add(d["topic"])
    titles = {p["path"]: p["nav"] for p in pages_cfg}
    for s_ in sources:
        s_["used_on"] = [{"path": TOPIC_PAGES[t], "nav": titles[TOPIC_PAGES[t]]} for t in sorted(used_by.get(s_["id"], ())) if t in TOPIC_PAGES]

    env = make_env()
    written: list[Path] = []
    for page in pages_cfg:
        depth = page["path"].count("/")
        root = "../" * depth
        html = env.get_template(f"pages/{page['template']}").render(
            root=root,
            page=page,
            pages=pages_cfg,
            site_title=SITE_TITLE,
            sources=sources,
            sources_by_id={s["id"]: s for s in sources},
            definitions=definitions,
            defs_by_id={d["id"]: d for d in definitions},
            series=series,
            datasets=datasets,
            series_table=lambda ids, **kw: series_table(series, ids, **kw),
            dataset_table=lambda ds_id, **kw: dataset_table(datasets, ds_id, **kw),
            datasets_value=lambda ds_id, code, period, dim="vare", status=None: dataset_value(datasets, ds_id, code, period, dim, status),
        )
        dest = out / page["path"]
        write_text(dest, html)
        written.append(dest)

    publish_data(processed, out)
    if include_fixture:
        publish_data(FIXTURE / "processed", out, prefix="_fixture")
    return written


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fixture", action="store_true", help="also publish the synthetic test dataset")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    pages = build(args.out, include_fixture=args.fixture)
    print(f"built {len(pages)} pages into {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
