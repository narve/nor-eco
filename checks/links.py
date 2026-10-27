"""Relative-link check for a built site: no root-absolute href/src, and every relative link
(file and #fragment) resolves."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse


class _Collect(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []  # (attr, value)
        self.ids: set[str] = set()
        self.duplicate_ids: set[str] = set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            if a["id"] in self.ids:
                self.duplicate_ids.add(a["id"])
            self.ids.add(a["id"])
        if tag == "a" and a.get("name"):
            self.ids.add(a["name"])
        for k in ("href", "src"):
            if a.get(k) is not None:
                self.links.append((k, a[k]))
        if tag == "link" and a.get("href") is None:
            pass


def check_site_links(site: Path) -> list[str]:
    errors: list[str] = []
    pages = sorted(site.rglob("*.html"))
    parsed: dict[Path, _Collect] = {}
    for p in pages:
        c = _Collect()
        c.feed(p.read_text(encoding="utf-8"))
        parsed[p] = c
    for p, c in parsed.items():
        rel = p.relative_to(site)
        errors.extend(f"{rel}: duplicate id '{i}'" for i in sorted(c.duplicate_ids))
        for attr, value in c.links:
            if not value or value.startswith(("mailto:", "tel:", "javascript:", "data:")):
                continue
            u = urlparse(value)
            if u.scheme in ("http", "https"):
                continue  # external
            if value.startswith("//"):
                errors.append(f"{rel}: protocol-relative {attr}='{value}'")
                continue
            if value.startswith("/"):
                errors.append(f"{rel}: root-absolute {attr}='{value}' (use a relative path)")
                continue
            target = (p.parent / unquote(u.path)).resolve() if u.path else p.resolve()
            if u.path and not target.exists():
                errors.append(f"{rel}: broken {attr}='{value}'")
                continue
            if u.fragment:
                if target.suffix == ".html" and target in {q.resolve() for q in parsed}:
                    ids = next(c2.ids for q, c2 in parsed.items() if q.resolve() == target)
                    if u.fragment not in ids:
                        errors.append(f"{rel}: missing anchor '#{u.fragment}' in {value}")
    return errors
