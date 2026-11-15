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
from leasing.paths import DOCS, HISTORY, SITE_SRC  # noqa: E402

TZ = ZoneInfo("Asia/Jerusalem")
PAGES_URL = "https://ofirr-op.github.io/leasing-deals/"
REPO_URL = "https://github.com/ofirr-op/leasing-deals"


def _snapshots() -> list[dict]:
    files = sorted(HISTORY.glob("????-??-??.json"))
    out = []
    for f in files:
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except json.JSONDecodeError as e:
            print(f"Skipping {f.name}: {e}", file=sys.stderr)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build docs/ for GitHub Pages")
    ap.add_argument("--date", help="Snapshot date to publish (default: latest)")
    args = ap.parse_args(argv)

    snaps = _snapshots()
    if not snaps:
        print("No snapshots in data/history/", file=sys.stderr)
        return 1
    if args.date:
        curr = next((s for s in snaps if s.get("date") == args.date), None)
        if not curr:
            print(f"No snapshot for {args.date}", file=sys.stderr)
            return 1
        prev_list = [s for s in snaps if s.get("date") < args.date]
        prev = prev_list[-1] if prev_list else None
        hist_for_drops = prev_list + [curr]
    else:
        curr = snaps[-1]
        prev = snaps[-2] if len(snaps) > 1 else None
        hist_for_drops = snaps

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

    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "assets").mkdir(parents=True, exist_ok=True)
    shutil.copy2(SITE_SRC / "index.html", DOCS / "index.html")
    shutil.copy2(SITE_SRC / "styles.css", DOCS / "assets" / "styles.css")
    shutil.copy2(SITE_SRC / "app.js", DOCS / "assets" / "app.js")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    payload = "window.PAGE_DATA = " + json.dumps(page, ensure_ascii=False, separators=(",", ":")) + ";\n"
    (DOCS / "data.js").write_text(payload, encoding="utf-8")

    failed = [k for k, v in (curr.get("sources") or {}).items() if v.get("ok") is False]
    print(
        f"Built {DOCS} — {len(page['offers'])} offers, "
        f"{changes['counts']['drops']} drops, {changes['counts']['new']} new, "
        f"{changes['counts']['removed']} removed"
        + (f", failed sources: {', '.join(failed)}" if failed else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
