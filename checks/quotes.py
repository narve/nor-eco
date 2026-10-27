"""Verify that every quote in definitions/*.yaml still appears at its source (online).

SSB statbank table notes are checked against the PxWebApi metadata notes for the source's table_id;
other sources against the visible text of the registered page. Whitespace and quote marks are normalised."""

from __future__ import annotations

import html
import re
from pathlib import Path

import httpx
import yaml

from fetch import common, ssb

ROOT = Path(__file__).resolve().parent.parent


def _norm(s: str) -> str:
    s = html.unescape(s)
    s = s.replace("”", '"').replace("“", '"').replace("«", '"').replace("»", '"')
    return " ".join(s.split())


def _page_text(url: str) -> str:
    r = httpx.get(url, follow_redirects=True, timeout=60, headers={"User-Agent": common.USER_AGENT})
    r.raise_for_status()
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", r.text, flags=re.S)
    t = re.sub(r"</(p|li|h\d|div|tr|td)>", "\n", t)
    return re.sub(r"<[^>]+>", " ", t)


def verify_definitions(definitions_dir: Path = ROOT / "definitions", registry: Path = ROOT / "sources" / "registry.yaml") -> list[str]:
    reg = common.load_registry(registry)
    errors, cache = [], {}
    for p in sorted(definitions_dir.glob("*.yaml")):
        for d in (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("definitions", []):
            src = reg.get(d["source_id"])
            if src is None:
                errors.append(f"{d['id']}: unknown source_id {d['source_id']}")
                continue
            key = d["source_id"]
            if key not in cache:
                if src.get("table_id"):
                    meta = common.parse_jsonstat2(ssb.table_metadata(src["table_id"]), metadata_only=True)
                    cache[key] = _norm(" ".join(meta.notes))
                else:
                    cache[key] = _norm(_page_text(src["url"]))
            if _norm(d["quote"]) not in cache[key]:
                errors.append(f"{d['id']}: quote not found at {src['url']}")
    return errors
