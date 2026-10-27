"""Norwegian number formatting used by templates (`fmt`) and anywhere else a number is displayed."""

from __future__ import annotations

NBSP = " "
MINUS = "−"


def fmt(value: float | int | None, decimals: int | None = None, *, sign: bool = False) -> str:
    """1234.5 -> '1 234,5' (non-breaking space as thousands separator, comma as decimal mark).

    decimals=None keeps the value's own precision up to 2 decimals, trimming trailing zeros.
    Negative numbers use the proper minus sign. None renders as an en dash.
    """
    if value is None:
        return "–"
    if decimals is None:
        text = f"{abs(value):.2f}".rstrip("0").rstrip(".")
    else:
        text = f"{abs(value):.{decimals}f}"
    whole, _, frac = text.partition(".")
    groups = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    out = NBSP.join(groups) + ("," + frac if frac else "")
    if value < 0 and float(text) != 0:
        return MINUS + out
    if sign and value > 0:
        return "+" + out
    return out
