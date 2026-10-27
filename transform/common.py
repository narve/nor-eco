"""Helpers shared by the topic transforms: latest raw snapshot lookup and writers for processed data."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import yaml

from fetch.common import JsonStat, parse_jsonstat2

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"


def latest_snapshot(source_id: str, raw_dir: Path = RAW_DIR) -> tuple[JsonStat, dict]:
    """Parse the newest committed JSON snapshot of a source. Returns (JsonStat, manifest entry)."""
    manifest = yaml.safe_load((raw_dir / "MANIFEST.yaml").read_text(encoding="utf-8"))["files"]
    entries = sorted((e for e in manifest if e["source_id"] == source_id and e["committed"]), key=lambda e: e["retrieved"])
    if not entries:
        raise FileNotFoundError(f"no committed snapshot for {source_id}; run `python -m fetch all`")
    e = entries[-1]
    return parse_jsonstat2((raw_dir / e["file"]).read_bytes()), e


def mrd(mill_kr: float) -> float:
    """mill. kr -> mrd. kr (exact to the source's precision)."""
    return round(mill_kr / 1000, 3)


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_series(topic: str, series: dict, out: Path = PROCESSED) -> None:
    write_json(out / topic / f"{series['id'].split('.')[-1]}.json", series)


def write_dataset(topic: str, name: str, meta: dict, dimensions: dict, rows: list[dict], out: Path = PROCESSED) -> None:
    d = out / topic / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "dataset.yaml").write_text(yaml.safe_dump(meta, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (d / "dimensions.yaml").write_text(yaml.safe_dump({"dimensions": dimensions}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    cols = ["period", "value", "unit", "status"] + meta["dimensions"] + ["claim_level", "source_id"]
    with (d / "facts.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols)
        for r in rows:
            w.writerow([r[c] for c in cols])


def preliminary_after_year(notes: list[str]) -> int:
    """Read «Tallene etter år 2023 (basisåret) er foreløpige.» from the source's own notes."""
    for n in notes:
        m = re.search(r"Tallene etter år (\d{4})\b.*foreløpige", n)
        if m:
            return int(m.group(1))
    raise ValueError("source notes no longer state which years are preliminary; check the table and update the transform")
