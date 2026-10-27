"""`python -m fetch <command>`.

  check   report which SSB API version is live (v2 preferred)
  all     run every fetcher (okonomi; WS1, WS3, WS4 add theirs)
"""

from __future__ import annotations

import sys

from . import okonomi, ssb


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "all"
    if cmd == "check":
        print("SSB PxWebApi:", ssb.api_version())
        return 0
    if cmd == "all":
        okonomi.run()
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
