"""Norwegian number formatting used by templates (`fmt`) and anywhere else a number is displayed.

The JavaScript twin is site_src/assets/js/core/format.js. Both round half away from zero on the value's
shortest decimal representation (2.25 -> '2,3'), and tests/e2e/test_engine.py checks that they agree.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

NBSP = " "
MINUS = "−"


def fmt(value: float | int | None, decimals: int | None = None, *, sign: bool = False) -> str:
    """1234.5 -> '1 234,5' (non-breaking space as thousands separator, comma as decimal mark).

    decimals=None keeps the value's own precision up to 2 decimals, trimming trailing zeros.
    Negative numbers use the proper minus sign. None renders as an en dash.
    """
    if value is None:
        return "–"
    places = 2 if decimals is None else decimals
    q = Decimal(repr(abs(value))).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    text = f"{q:f}"
    if decimals is None and "." in text:
        text = text.rstrip("0").rstrip(".")
    whole, _, frac = text.partition(".")
    groups = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    out = NBSP.join(groups) + ("," + frac if frac else "")
    if value < 0 and q != 0:
        return MINUS + out
    if sign and value > 0:
        return "+" + out
    return out
