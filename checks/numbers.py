"""Template lint: numbers on the site come from processed data through fmt()/cite(), never typed into
template text. Flags digit sequences in template text outside the allow-list."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ALLOWLIST = Path(__file__).with_name("number_allowlist.yaml")
_STRIP = [
    r"\{#.*?#\}",
    r"\{%.*?%\}",
    r"\{\{.*?\}\}",
    r"<!--.*?-->",
    r"<script\b.*?</script>",
    r"<style\b.*?</style>",
    r"<[^>]+>",
]
_NUM = re.compile(r"\d+(?:[  .,]\d+)*")


def lint_template(text: str, allow_phrases: list[str], year_re: str) -> list[str]:
    for pat in _STRIP:
        text = re.sub(pat, " ", text, flags=re.S)
    problems = []
    for line in text.splitlines():
        for pat in allow_phrases:
            line = re.sub(pat, " ", line)
        for m in _NUM.finditer(line):
            tok = m.group(0)
            if re.fullmatch(year_re, tok):
                continue
            problems.append(tok)
    return problems


def lint_templates(template_dir: Path) -> list[str]:
    cfg = yaml.safe_load(ALLOWLIST.read_text(encoding="utf-8"))
    errors = []
    for p in sorted(template_dir.rglob("*.html")):
        for tok in lint_template(p.read_text(encoding="utf-8"), cfg["allow_phrases"], cfg["year"]):
            errors.append(f"{p}: hard-coded number '{tok}' (use fmt()/cite() with processed data, or extend checks/number_allowlist.yaml)")
    return errors
