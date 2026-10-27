"""Local gate: `uv run python -m checks` (also installable as a git pre-push hook with --install-hook).

Runs: data validation, size guard, template number lint, build + relative-link check, site freshness
(committed site/ must equal a fresh build), registry link check (online), pytest.
pytest includes the Playwright tests in tests/e2e (needs: uv run playwright install chromium).
"""

from __future__ import annotations

import argparse
import filecmp
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx

import build as site_build
from transform.schema import validate_tree

from . import links, numbers, sizes

ROOT = Path(__file__).resolve().parent.parent


def _diff_trees(a: Path, b: Path) -> list[str]:
    out: list[str] = []
    cmp = filecmp.dircmp(a, b)

    def walk(c: filecmp.dircmp, prefix: str = "") -> None:
        out.extend(f"only in committed site/: {prefix}{n}" for n in c.left_only)
        out.extend(f"missing from committed site/: {prefix}{n}" for n in c.right_only)
        for n in c.diff_files:
            same = (Path(c.left) / n).read_bytes() == (Path(c.right) / n).read_bytes()
            if not same:
                out.append(f"differs: {prefix}{n}")
        for n, sub in c.subdirs.items():
            walk(sub, prefix + n + "/")

    walk(cmp)
    return out


def check_registry_urls() -> list[str]:
    import yaml

    errors = []
    reg = yaml.safe_load((ROOT / "sources" / "registry.yaml").read_text(encoding="utf-8")) or {}
    for s in reg.get("sources", []):
        try:
            r = httpx.get(s["url"], follow_redirects=True, timeout=30, headers={"User-Agent": "nor-eco link check"})
            if r.status_code != 200:
                errors.append(f"{s['id']}: {s['url']} returned {r.status_code}")
        except httpx.HTTPError as e:
            errors.append(f"{s['id']}: {s['url']} failed: {e}")
    return errors


def run(skip_online: bool, skip_tests: bool) -> int:
    failures = 0

    def step(name: str, errors: list[str]) -> None:
        nonlocal failures
        print(("FAIL " if errors else "ok   ") + name)
        for e in errors:
            print("     " + e)
        failures += bool(errors)

    step("processed data validates", validate_tree(ROOT / "data" / "processed", ROOT / "sources" / "registry.yaml").errors)
    step("file size guard", sizes.check_tracked_files(ROOT) + sizes.check_untracked_candidates(ROOT))
    step("template numbers", numbers.lint_templates(ROOT / "site_src" / "templates"))

    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp) / "site"
        site_build.build(fresh)
        step("relative links (fresh build)", links.check_site_links(fresh))
        committed = ROOT / "site"
        if committed.exists():
            step("committed site/ is up to date", _diff_trees(committed, fresh))
        else:
            step("committed site/ is up to date", ["site/ does not exist; run: uv run python build.py"])

    if skip_online:
        print("skip registry URL check (--skip-online)")
    else:
        step("registry URLs return 200", check_registry_urls())

    if skip_tests:
        print("skip pytest (--skip-tests)")
    else:
        r = subprocess.run([sys.executable, "-m", "pytest"], cwd=ROOT)
        step("pytest", [] if r.returncode == 0 else ["pytest failed"])

    print("\nFAILED" if failures else "\nall checks passed")
    return 1 if failures else 0


def install_hook() -> None:
    hook = ROOT / ".git" / "hooks" / "pre-push"
    hook.write_text("#!/bin/sh\nexec uv run python -m checks\n")
    hook.chmod(0o755)
    print(f"installed {hook}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-online", action="store_true")
    ap.add_argument("--skip-tests", action="store_true")
    ap.add_argument("--install-hook", action="store_true")
    args = ap.parse_args(argv)
    if args.install_hook:
        install_hook()
        return 0
    return run(args.skip_online, args.skip_tests)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
