"""Build the static site: processed data + templates -> site/ (deterministic; committed).

    uv run python build.py                  # build site/
    uv run python build.py --fixture        # also publish the synthetic test dataset (tests, dev)

All internal links and asset paths are relative (each page gets `root`, e.g. '' or '../').
The output has no timestamps, so rebuilding unchanged inputs gives identical files.
"""

from __future__ import annotations

import argparse
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
            items.extend((yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("definitions", []))
    return sorted(items, key=lambda d: d["term"].casefold())


def make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(SRC / "templates"),
        autoescape=select_autoescape(["html"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["fmt"] = fmt
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
    for p in pages_cfg:
        p.setdefault("secondary", False)
    definitions = load_definitions(definitions_dir)

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
