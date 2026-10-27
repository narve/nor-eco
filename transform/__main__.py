"""`python -m transform all`: raw snapshots -> data/processed (WS1, WS3, WS4 add their topics here)."""

from __future__ import annotations

import shutil
import sys

from . import okonomi, statsbudsjett
from .common import PROCESSED


def main(argv: list[str]) -> int:
    if (argv[:1] or ["all"])[0] != "all":
        print(__doc__)
        return 2
    shutil.rmtree(PROCESSED / okonomi.TOPIC, ignore_errors=True)
    okonomi.run()
    okonomi.spu()
    shutil.rmtree(PROCESSED / statsbudsjett.TOPIC, ignore_errors=True)
    statsbudsjett.run()
    statsbudsjett.cofog()
    statsbudsjett.sb2027()
    print("statsbudsjett: done")
    print("okonomi: done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
