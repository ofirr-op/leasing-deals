"""Read and name scrape snapshots. Every scan is its own file; nothing is overwritten."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

from leasing.paths import HISTORY

# Legacy daily files (YYYY-MM-DD.json) and per-scan files (YYYY-MM-DDTHHMMSS.json,
# with an optional -2, -3… suffix if two scans share a second).
SNAP_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}(?:T\d{6}(?:-\d+)?)?\.json$")


def snapshot_day(name: str) -> str:
    """Calendar day from a snapshot filename or stem."""
    stem = name[:-5] if name.endswith(".json") else name
    return stem[:10]


def iter_snapshot_paths() -> list[Path]:
    if not HISTORY.is_dir():
        return []
    return [p for p in HISTORY.iterdir() if p.is_file() and SNAP_NAME.match(p.name)]


def _sort_key(path: Path, snap: dict) -> tuple:
    day = str(snap.get("date") or snapshot_day(path.name))
    at = str(snap.get("scraped_at") or day)
    return (day, at, path.name)


def load_snapshots() -> list[tuple[Path, dict]]:
    """All snapshots, oldest first. Unreadable files are skipped."""
    loaded: list[tuple[Path, dict]] = []
    for path in iter_snapshot_paths():
        try:
            snap = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"Skipping unreadable snapshot {path.name}: {e}", file=sys.stderr)
            continue
        loaded.append((path, snap))
    loaded.sort(key=lambda item: _sort_key(item[0], item[1]))
    return loaded


def unique_snapshot_path(day: str, when: datetime) -> Path:
    """A new path for this scan. Never returns a file that already exists."""
    HISTORY.mkdir(parents=True, exist_ok=True)
    stamp = when.strftime("%H%M%S")
    base = f"{day}T{stamp}"
    path = HISTORY / f"{base}.json"
    n = 2
    while path.exists():
        path = HISTORY / f"{base}-{n}.json"
        n += 1
    return path
