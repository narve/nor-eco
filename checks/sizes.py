"""Repo size guard: every git-tracked file under 5 MB, and no tracked PDFs under data/raw/."""

from __future__ import annotations

import subprocess
from pathlib import Path

LIMIT = 5 * 1024 * 1024


def check_tracked_files(root: Path) -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True).stdout
    errors = []
    for name in out.split(b"\0"):
        if not name:
            continue
        rel = name.decode()
        f = root / rel
        if not f.is_file():
            continue
        if f.stat().st_size > LIMIT:
            errors.append(f"{rel}: {f.stat().st_size / 1e6:.1f} MB exceeds the 5 MB limit")
        if rel.startswith("data/raw/") and rel.lower().endswith(".pdf"):
            errors.append(f"{rel}: PDFs must not be committed; list them in data/raw/MANIFEST.yaml")
    return errors


def check_untracked_candidates(root: Path) -> list[str]:
    """Also catch files that are about to be added (untracked, not ignored) if they are too large."""
    out = subprocess.run(
        ["git", "ls-files", "-z", "--others", "--exclude-standard"], cwd=root, capture_output=True, check=True
    ).stdout
    errors = []
    for name in out.split(b"\0"):
        if name and (root / name.decode()).is_file() and (root / name.decode()).stat().st_size > LIMIT:
            errors.append(f"{name.decode()}: untracked file exceeds 5 MB; do not add it")
    return errors
