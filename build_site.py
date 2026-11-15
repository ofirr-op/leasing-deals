#!/usr/bin/env python3
"""Build the static comparison site into docs/ for GitHub Pages.

Usage (from the repo root):

    python build_site.py
    python build_site.py --date 2026-11-14
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from leasing.compare import compare, latest_drops_from_history  # noqa: E402
from leasing.normalize import load_reference  # noqa: E402
from leasing.paths import DOCS, SITE_SRC  # noqa: E402
from leasing.price_history import history_from_files  # noqa: E402
from leasing.snapshots import load_snapshots  # noqa: E402

TZ = ZoneInfo("Asia/Jerusalem")
PAGES_URL = "https://ofirr-op.github.io/leasing-deals/"
REPO_URL = "https://github.com/ofirr-op/leasing-deals"


def _snapshots() -> list[dict]:
    """Every saved scan, oldest first (daily files and timestamped scans)."""
    return [snap for _, snap in load_snapshots()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build docs/ for GitHub Pages")
    ap.add_argument("--date", help="Snapshot date to publish (default: latest)")
    args = ap.parse_args(argv)

    snaps = _snapshots()
    if not snaps:
        print("No snapshots in data/history/", file=sys.stderr)
        return 1
    if args.date:
        matches = [i for i, s in enumerate(snaps) if s.get("date") == args.date]
        if not matches:
            print(f"No snapshot for {args.date}", file=sys.stderr)
            return 1
        # The latest scan on that day is the published page; earlier scans stay in the chart.
        idx = matches[-1]
        curr = snaps[idx]
        prev = snaps[idx - 1] if idx else None
        hist_for_drops = snaps[: idx + 1]
    else:
        curr = snaps[-1]
        prev = snaps[-2] if len(snaps) > 1 else None
        hist_for_drops = snaps
        idx = len(snaps) - 1

    ref = load_reference()
    defaults, lic = ref["defaults"], ref["licensing"]
    changes = compare(prev, curr, defaults, lic) if prev else {
        "previous_date": None,
        "current_date": curr.get("date"),
        "drops": [],
        "increases": [],
        "unchanged": 0,
        "new": [],
        "removed": [],
        "counts": {"previous": 0, "current": len(curr.get("offers") or []), "drops": 0, "increases": 0, "new": 0, "removed": 0},
    }
    last_drops = None
    if not changes.get("drops"):
        last_drops = latest_drops_from_history(hist_for_drops, defaults, lic)

    copy = json.loads((ROOT / "data/reference/copy.json").read_text(encoding="utf-8"))
    sources_list = json.loads((ROOT / "data/reference/sources.json").read_text(encoding="utf-8"))
    i18n = json.loads((ROOT / "data/reference/i18n.json").read_text(encoding="utf-8"))
    canonical = json.loads((ROOT / "data/reference/canonical.json").read_text(encoding="utf-8"))

    page = {
        "generated_at": datetime.now(TZ).isoformat(),
        "pages_url": PAGES_URL,
        "repo_url": REPO_URL,
        "dates": {
            "current": curr.get("date"),
            "previous": prev.get("date") if prev else None,
            "scraped_at": curr.get("scraped_at"),
        },
        "source_status": curr.get("sources") or {},
        "offers": curr.get("offers") or [],
        "changes": changes,
        "last_drops": last_drops,
        "defaults": defaults,
        "licensing": lic,
        "i18n": i18n,
        "canonical": {
            "make_he": canonical.get("make_he") or {},
            "model_he": canonical.get("model_he") or {},
            "trim_he": canonical.get("trim_he") or {},
            "variant_he": canonical.get("variant_he") or {},
        },
        "copy": copy,
        "sources_list": sources_list,
    }

    history = history_from_files(load_snapshots()[: idx + 1], defaults, lic)
    history_payload = json.dumps(history, ensure_ascii=False, separators=(",", ":"))

    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "assets").mkdir(parents=True, exist_ok=True)
    (DOCS / "data").mkdir(parents=True, exist_ok=True)
    shutil.copy2(SITE_SRC / "index.html", DOCS / "index.html")
    shutil.copy2(SITE_SRC / "styles.css", DOCS / "assets" / "styles.css")
    shutil.copy2(SITE_SRC / "app.js", DOCS / "assets" / "app.js")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    payload = "window.PAGE_DATA = " + json.dumps(page, ensure_ascii=False, separators=(",", ":")) + ";\n"
    (DOCS / "data.js").write_text(payload, encoding="utf-8")
    (DOCS / "data" / "history.json").write_text(history_payload + "\n", encoding="utf-8")
    (DOCS / "data" / "history.js").write_text("window.PRICE_HISTORY = " + history_payload + ";\n", encoding="utf-8")

    failed = [k for k, v in (curr.get("sources") or {}).items() if v.get("ok") is False]
    print(
        f"Built {DOCS} — {len(page['offers'])} offers, "
        f"{changes['counts']['drops']} drops, {changes['counts']['new']} new, "
        f"{changes['counts']['removed']} removed, "
        f"{len(history['models'])} models × {len(history['scans'])} scans in price history"
        + (f", failed sources: {', '.join(failed)}" if failed else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
