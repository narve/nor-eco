"""Shared fetch helpers: HTTP with caching and throttling, raw snapshots, JSON-stat2 parsing.

Rules (see docs/PLAN.md):
- Every fetched response is stored as a raw snapshot with its retrieval date.
- Every git-tracked file is under 5 MB. Easily re-downloadable files (PDF, Excel, zip) are never
  committed; they are listed in data/raw/MANIFEST.yaml with a sha256 and can be re-downloaded.
- A source must be registered in sources/registry.yaml before it is used.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

import httpx
import yaml

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
LARGE_DIR = RAW_DIR / "_large"  # gitignored
REGISTRY = ROOT / "sources" / "registry.yaml"

USER_AGENT = "nor-eco/0.1 (+https://github.com/narve/nor-eco; static site built from official sources)"
MAX_COMMITTED_BYTES = 5 * 1024 * 1024
# Re-downloadable file types are never committed, whatever their size.
REDOWNLOADABLE_EXT = {".pdf", ".xlsx", ".xls", ".zip", ".gz"}
MIN_INTERVAL_S = 0.5  # per host

_last_request: dict[str, float] = {}


class FetchError(RuntimeError):
    pass


class UnregisteredSource(FetchError):
    pass


# --------------------------------------------------------------------------- registry


def load_registry(path: Path = REGISTRY) -> dict[str, dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sources = data.get("sources", [])
    by_id: dict[str, dict] = {}
    for s in sources:
        if s["id"] in by_id:
            raise ValueError(f"duplicate source id in registry: {s['id']}")
        by_id[s["id"]] = s
    return by_id


def source_record(source_id: str, registry: dict[str, dict] | None = None) -> dict:
    """Return the registry record for source_id, or raise if it is not registered."""
    registry = registry if registry is not None else load_registry()
    try:
        return registry[source_id]
    except KeyError:
        raise UnregisteredSource(
            f"source '{source_id}' is not in sources/registry.yaml; register it before fetching"
        ) from None


# --------------------------------------------------------------------------- HTTP


def _throttle(url: str) -> None:
    host = urlparse(url).netloc
    wait = MIN_INTERVAL_S - (time.monotonic() - _last_request.get(host, 0.0))
    if wait > 0:
        time.sleep(wait)
    _last_request[host] = time.monotonic()


def http_get(url: str, *, params: dict | None = None, timeout: float = 60.0, retries: int = 3) -> httpx.Response:
    last: Exception | None = None
    for attempt in range(retries):
        _throttle(url)
        try:
            r = httpx.get(
                url, params=params, timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}
            )
            if r.status_code == 403:
                # The sandbox firewall explains blocks in the body; surface it instead of retrying.
                raise FetchError(f"403 for {url}: {r.text[:500]}")
            if r.status_code >= 500 or r.status_code == 429:
                raise FetchError(f"{r.status_code} for {url}")
            r.raise_for_status()
            return r
        except (httpx.TransportError, FetchError) as e:
            if isinstance(e, FetchError) and str(e).startswith("403"):
                raise
            last = e
            time.sleep(2**attempt)
    raise FetchError(f"giving up on {url}: {last}")


def http_post_json(url: str, body: dict, *, timeout: float = 60.0) -> httpx.Response:
    _throttle(url)
    r = httpx.post(url, json=body, timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT})
    if r.status_code == 403:
        raise FetchError(f"403 for {url}: {r.text[:500]}")
    r.raise_for_status()
    return r


# --------------------------------------------------------------------------- snapshots


@dataclass(frozen=True)
class Snapshot:
    source_id: str
    path: Path
    sha256: str
    retrieved: str
    committed: bool
    unchanged: bool  # True if identical to the previous snapshot (nothing new was written)


def snapshot_order(entry: dict) -> tuple[str, int]:
    """Sort key: retrieval date, then the same-day sequence number («…-2.json» is newer than «….json»)."""
    m = re.search(r"\d{4}-\d{2}-\d{2}-(\d+)\.\w+$", entry["file"])
    return entry["retrieved"], int(m.group(1)) if m else 1


def _load_manifest(path: Path) -> list[dict]:
    if path.exists():
        return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("files", [])
    return []


def _write_manifest(path: Path, entries: list[dict]) -> None:
    entries = sorted(entries, key=lambda e: (e["source_id"], *snapshot_order(e)))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Raw snapshots. Committed files are in data/raw/<source_id>/; the rest are re-downloadable (see url).\n"
        + yaml.safe_dump({"files": entries}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def write_snapshot(
    source_id: str,
    content: bytes,
    ext: str,
    *,
    url: str,
    vintage: str | None = None,
    retrieved: str | None = None,
    raw_dir: Path = RAW_DIR,
    registry: dict[str, dict] | None = None,
) -> Snapshot:
    """Store a raw response. `vintage` is the source's own publication/update date, if known.

    The manifest lives in `raw_dir/MANIFEST.yaml`. If the newest snapshot for the same url has the same
    sha256, nothing is written and `Snapshot.unchanged` is True.
    """
    source_record(source_id, registry)
    ext = ext if ext.startswith(".") else "." + ext
    retrieved = retrieved or dt.date.today().isoformat()
    sha = hashlib.sha256(content).hexdigest()

    manifest = raw_dir / "MANIFEST.yaml"
    entries = _load_manifest(manifest)
    prev = sorted((e for e in entries if e["source_id"] == source_id and e["url"] == url), key=snapshot_order)
    same = [e for e in prev if e["sha256"] == sha]  # identical to ANY earlier snapshot (a source can flip between versions)
    if same:
        last = same[-1]
        return Snapshot(source_id, raw_dir / last["file"], sha, last["retrieved"], last["committed"], True)

    redownloadable = ext in REDOWNLOADABLE_EXT
    if not redownloadable and len(content) > MAX_COMMITTED_BYTES:
        raise FetchError(
            f"{source_id}: response is {len(content) / 1e6:.1f} MB (> 5 MB). Narrow the query "
            "(for example drop early years) instead of committing it."
        )
    committed = not redownloadable
    rel = f"{source_id}/{retrieved}{ext}"
    if not committed:
        rel = f"_large/{rel}"
    n = 1
    while (raw_dir / rel).exists():  # same day, different content: never overwrite an earlier snapshot
        n += 1
        rel = f"{source_id}/{retrieved}-{n}{ext}" if committed else f"_large/{source_id}/{retrieved}-{n}{ext}"
    target = raw_dir / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    entries.append(
        {
            "source_id": source_id,
            "file": rel,
            "url": url,
            "sha256": sha,
            "retrieved": retrieved,
            **({"vintage": vintage} if vintage else {}),
            "size": len(content),
            "committed": committed,
        }
    )
    _write_manifest(manifest, entries)
    return Snapshot(source_id, target, sha, retrieved, committed, False)


# --------------------------------------------------------------------------- JSON-stat2


@dataclass
class Dimension:
    id: str
    label: str
    codes: list[str]  # in index order
    labels: dict[str, str]
    role: str | None = None  # "time" | "geo" | "metric" | None
    units: dict[str, dict] | None = None


@dataclass
class JsonStat:
    label: str
    source: str | None
    updated: str | None
    notes: list[str]
    dimensions: list[Dimension]
    values: list[Any]
    status: dict[int, str]

    def rows(self) -> Iterator[dict[str, Any]]:
        """Yield one dict per cell: {dim_id: code, ..., 'value': v, 'status': s|None}. Null values are skipped."""
        sizes = [len(d.codes) for d in self.dimensions]
        n = 1
        for s in sizes:
            n *= s
        for flat in range(n):
            v = self.values[flat] if flat < len(self.values) else None
            if v is None:
                continue
            idx = flat
            row: dict[str, Any] = {}
            for d, size in zip(reversed(self.dimensions), reversed(sizes)):
                row[d.id] = d.codes[idx % size]
                idx //= size
            # restore dimension order
            row = {d.id: row[d.id] for d in self.dimensions}
            row["value"] = v
            row["status"] = self.status.get(flat)
            yield row


def _ordered_codes(category: dict) -> list[str]:
    index = category.get("index")
    if index is None:  # single-category dimension may omit index
        return list(category.get("label", {}).keys())
    if isinstance(index, list):
        return list(index)
    return [c for c, _ in sorted(index.items(), key=lambda kv: kv[1])]


def parse_jsonstat2(obj: dict | str | bytes, *, metadata_only: bool = False) -> JsonStat:
    if isinstance(obj, (str, bytes)):
        obj = json.loads(obj)
    if obj.get("class", "dataset") != "dataset":
        raise ValueError(f"unsupported JSON-stat class: {obj.get('class')}")
    ids: list[str] = obj["id"]
    sizes: list[int] = obj["size"]
    role = {}
    for r, dims in (obj.get("role") or {}).items():
        for d in dims or []:
            role[d] = r
    dims: list[Dimension] = []
    for did, size in zip(ids, sizes):
        dd = obj["dimension"][did]
        cat = dd["category"]
        codes = _ordered_codes(cat)
        if len(codes) != size:
            raise ValueError(f"dimension {did}: {len(codes)} codes but size {size}")
        labels = cat.get("label") or {c: c for c in codes}
        dims.append(Dimension(did, dd.get("label", did), codes, {c: labels.get(c, c) for c in codes}, role.get(did), cat.get("unit")))
    total = 1
    for s in sizes:
        total *= s
    raw_values = obj.get("value", [])
    if metadata_only and not raw_values:  # metadata responses carry dimensions but no values
        raw_values = {}
    if isinstance(raw_values, dict):  # sparse form
        values: list[Any] = [None] * total
        for k, v in raw_values.items():
            values[int(k)] = v
    else:
        values = list(raw_values)
        if len(values) != total:
            raise ValueError(f"expected {total} values, got {len(values)}")
    st = obj.get("status") or {}
    if isinstance(st, list):
        status = {i: s for i, s in enumerate(st) if s}
    elif isinstance(st, dict):
        status = {int(k): v for k, v in st.items()}
    else:  # a single string applies to all cells
        status = {i: st for i in range(total)}
    return JsonStat(
        label=obj.get("label", ""),
        source=obj.get("source"),
        updated=obj.get("updated"),
        notes=list(obj.get("note") or []),
        dimensions=dims,
        values=values,
        status=status,
    )


_VOLATILE = [
    (re.compile(rb'(<meta name="csp-nonce" content=")[^"]*(")'), rb"\1NONCE\2"),
    (re.compile(rb'(nonce=")[^"]*(")'), rb"\1NONCE\2"),
    (re.compile(rb"(fin-figur-)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"), rb"\1UUID"),
]


def normalize_html(content: bytes) -> bytes:
    """Replace per-request values (CSP nonces, generated chart ids) so an unchanged page hashes the same every time."""
    for pat, repl in _VOLATILE:
        content = pat.sub(repl, content)
    return content


def ensure_local(source_id: str, raw_dir: Path = RAW_DIR) -> Path:
    """Path of the newest snapshot of a source. Files that are not committed (PDF, Excel ...) are
    re-downloaded from the manifest url when missing, and verified against the recorded sha256."""
    entries = sorted((e for e in _load_manifest(raw_dir / "MANIFEST.yaml") if e["source_id"] == source_id), key=snapshot_order)
    if not entries:
        raise FileNotFoundError(f"no snapshot of {source_id} in the manifest; run `python -m fetch all`")
    e = entries[-1]
    path = raw_dir / e["file"]
    if path.exists():
        return path
    r = http_get(e["url"])
    if hashlib.sha256(r.content).hexdigest() != e["sha256"]:
        raise FetchError(f"{source_id}: {e['url']} no longer matches the recorded sha256 (the source changed); run `python -m fetch all` to take a new snapshot")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(r.content)
    return path
