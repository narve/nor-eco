import json

import pytest

from paths import FIXTURES
from fetch.common import parse_jsonstat2


def test_parses_real_ssb_response():
    js = parse_jsonstat2((FIXTURES / "jsonstat2_ssb_07459_sample.json").read_bytes())
    assert [d.id for d in js.dimensions] == ["Region", "Kjonn", "Alder", "ContentsCode", "Tid"]
    rows = list(js.rows())
    assert len(rows) == 8
    # last dimension (Tid) varies fastest; first row is Region 0, Kjonn index 0, Alder 000, first year
    first = rows[0]
    assert first["Region"] == "0" and first["Alder"] == "000" and first["value"] == 26206
    assert js.dimensions[0].labels["0"] == "Hele landet"
    assert js.dimensions[0].role == "geo" and js.dimensions[-1].role == "time"


def test_sparse_values_and_nulls_are_skipped():
    obj = {
        "class": "dataset", "label": "x", "id": ["A", "T"], "size": [2, 2],
        "dimension": {
            "A": {"label": "a", "category": {"index": ["p", "q"], "label": {"p": "P", "q": "Q"}}},
            "T": {"label": "t", "category": {"index": {"2023": 0, "2024": 1}}},
        },
        "value": {"0": 1.5, "3": 4},
    }
    rows = list(parse_jsonstat2(obj).rows())
    assert [(r["A"], r["T"], r["value"]) for r in rows] == [("p", "2023", 1.5), ("q", "2024", 4)]


def test_size_mismatch_is_an_error():
    obj = json.loads((FIXTURES / "jsonstat2_ssb_07459_sample.json").read_text())
    obj["size"][0] = 3
    with pytest.raises(ValueError):
        parse_jsonstat2(obj)
