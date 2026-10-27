"""Generic SSB PxWebApi fetch (JSON-stat2). One helper for all SSB tables.

Prefers API v2 (https://data.ssb.no/api/pxwebapi/v2/) and falls back to v0 if v2 is not live.
`selection` maps a dimension code to a list of value codes; the special forms `*` (all) and
`top(n)` (the n latest) are passed through to the API.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from . import common

V2 = "https://data.ssb.no/api/pxwebapi/v2"
V0 = "https://data.ssb.no/api/v0/{lang}/table/{table}"


def api_version() -> str:
    """Return 'v2' if the v2 config endpoint answers, otherwise 'v0'."""
    try:
        r = common.http_get(f"{V2}/config", timeout=20, retries=1)
        if r.json().get("apiVersion", "").startswith("2"):
            return "v2"
    except Exception:  # noqa: BLE001 - any failure means "fall back"
        pass
    return "v0"


@dataclass(frozen=True)
class SsbResponse:
    url: str
    content: bytes
    version: str

    def jsonstat(self) -> common.JsonStat:
        return common.parse_jsonstat2(self.content)


def table_metadata(table_id: str, *, lang: str = "no") -> dict:
    """Return the JSON-stat2 metadata (dimensions and codes, no values) for a table."""
    r = common.http_get(f"{V2}/tables/{table_id}/metadata", params={"lang": lang, "outputFormat": "json-stat2"})
    return r.json()


def _v2_params(selection: dict[str, list[str]] | None, lang: str) -> dict[str, str]:
    params = {"lang": lang, "outputFormat": "json-stat2"}
    for dim, values in (selection or {}).items():
        params[f"valuecodes[{dim}]"] = ",".join(values)
    return params


def _v0_body(selection: dict[str, list[str]] | None) -> dict:
    query = []
    for dim, values in (selection or {}).items():
        if len(values) == 1 and values[0].startswith("top("):
            sel = {"filter": "top", "values": [values[0][4:-1]]}
        elif values == ["*"]:
            sel = {"filter": "all", "values": ["*"]}
        else:
            sel = {"filter": "item", "values": values}
        query.append({"code": dim, "selection": sel})
    return {"query": query, "response": {"format": "json-stat2"}}


def fetch_table(
    table_id: str,
    selection: dict[str, list[str]] | None = None,
    *,
    lang: str = "no",
    version: str | None = None,
) -> SsbResponse:
    """Fetch one SSB table (optionally restricted by `selection`) as JSON-stat2 bytes."""
    version = version or api_version()
    if version == "v2":
        r = common.http_get(f"{V2}/tables/{table_id}/data", params=_v2_params(selection, lang))
        url = str(r.request.url)
    else:
        url = V0.format(lang=lang, table=table_id)
        r = common.http_post_json(url, _v0_body(selection))
        url += "#" + json.dumps(selection or {}, sort_keys=True)
    return SsbResponse(url=url, content=r.content, version=version)


def fetch_and_snapshot(
    source_id: str,
    table_id: str,
    selection: dict[str, list[str]] | None = None,
    *,
    lang: str = "no",
) -> tuple[common.Snapshot, common.JsonStat]:
    """Fetch a table for a registered source and store the raw snapshot."""
    common.source_record(source_id)
    resp = fetch_table(table_id, selection, lang=lang)
    js = resp.jsonstat()
    snap = common.write_snapshot(source_id, resp.content, ".json", url=resp.url, vintage=js.updated)
    return snap, js
