#!/usr/bin/env python3
"""Scrape Shlomo Sixt, Pery and HTZone private-leasing offers and write a dated snapshot.

Usage (from the repo root):

    python scrape.py
    python scrape.py --source shlomo
    python scrape.py --save-raw
    python scrape.py --date 2026-11-14   # override the snapshot date (Asia/Jerusalem)
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Allow running without installing the package.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from leasing.httputil import session  # noqa: E402
from leasing.normalize import load_reference, normalize_all  # noqa: E402
from leasing.paths import HISTORY, RAW  # noqa: E402
from leasing.sources import htzone, pery, shlomo  # noqa: E402

TZ = ZoneInfo("Asia/Jerusalem")
SOURCES = {"shlomo": shlomo, "pery": pery, "htzone": htzone}


def _offer_source(offer: dict) -> str:
    if offer.get("ch") == "HTZone":
        return "htzone"
    if offer.get("co") == "Pery":
        return "pery"
    return "shlomo"


def _load_history() -> list[tuple[str, dict]]:
    snaps: list[tuple[str, dict]] = []
    if not HISTORY.is_dir():
        return snaps
    for path in sorted(HISTORY.glob("????-??-??.json")):
        try:
            snaps.append((path.stem, json.loads(path.read_text(encoding="utf-8"))))
        except json.JSONDecodeError as e:
            print(f"Skipping unreadable snapshot {path.name}: {e}", file=sys.stderr)
    return snaps


def _previous_offers(name: str, snaps: list[tuple[str, dict]], date: str) -> tuple[list[dict], str | None]:
    """Newest snapshot on or before `date` that still has offers for `name`."""
    for snap_date, snap in reversed(snaps):
        if snap_date > date:
            continue
        offers = [o for o in (snap.get("offers") or []) if _offer_source(o) == name]
        if offers:
            return offers, snap_date
    return [], None


def _save_raw(rel: str, content: bytes) -> None:
    p = RAW / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)


def run_source(name: str, sess, save_raw) -> dict:
    mod = SOURCES[name]
    try:
        result = mod.scrape(sess=sess, save_raw=save_raw)
        result.setdefault("ok", bool(result.get("offers")))
        result.setdefault("errors", [])
        return result
    except Exception as e:  # noqa: BLE001
        return {
            "ok": False,
            "source": name,
            "count": 0,
            "offers": [],
            "errors": [f"{type(e).__name__}: {e}"],
            "traceback": traceback.format_exc(),
        }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Scrape private-leasing offers and write data/history/YYYY-MM-DD.json")
    ap.add_argument("--source", choices=list(SOURCES), action="append", help="Limit to one or more sources (default: all)")
    ap.add_argument("--save-raw", action="store_true", help="Write raw HTTP bodies under data/raw/ (gitignored)")
    ap.add_argument("--date", help="Snapshot date YYYY-MM-DD (defaults to today in Asia/Jerusalem)")
    ap.add_argument("--out", help="Override output path")
    args = ap.parse_args(argv)

    now = datetime.now(TZ)
    date = args.date or now.date().isoformat()
    wanted = args.source or list(SOURCES)
    saver = _save_raw if args.save_raw else None
    sess = session()

    results = {}
    for name in wanted:
        print(f"Scraping {name}…", flush=True)
        results[name] = run_source(name, sess, saver)
        r = results[name]
        status = "ok" if r.get("ok") else "FAILED"
        print(f"  {status}: {r.get('count', 0)} offers", flush=True)
        for err in (r.get("errors") or [])[:8]:
            print(f"    ! {err}", flush=True)

    ref = load_reference()
    offers = normalize_all(results, ref)

    # A partial rerun (--source) must not drop other sources from today's file.
    # A source that failed keeps its offers from the newest snapshot that has them,
    # so one blocked site does not wipe that column or fail the daily job.
    snaps = _load_history()
    out_preview = Path(args.out) if args.out else HISTORY / f"{date}.json"
    if args.source and out_preview.exists():
        prev = json.loads(out_preview.read_text(encoding="utf-8"))
        fresh = {o["key"] for o in offers}
        for o in prev.get("offers") or []:
            src = _offer_source(o)
            if src not in results and o["key"] not in fresh:
                offers.append(o)

    for name, result in results.items():
        if result.get("ok"):
            continue
        kept, kept_date = _previous_offers(name, snaps, date)
        if not kept:
            continue
        offers = [o for o in offers if _offer_source(o) != name]
        seen = {o["key"] for o in offers}
        for o in kept:
            if o["key"] not in seen:
                offers.append(o)
                seen.add(o["key"])
        result["kept_previous"] = True
        result["previous_date"] = kept_date
        result["count"] = sum(1 for o in offers if _offer_source(o) == name)
        print(
            f"  kept {result['count']} {name} offers from {kept_date} (source failed)",
            flush=True,
        )

    sources_meta = {}
    for name in SOURCES:
        if name not in results:
            n = sum(
                1
                for o in offers
                if (name == "htzone" and o.get("ch") == "HTZone")
                or (name == "pery" and o.get("co") == "Pery")
                or (name == "shlomo" and o.get("co") == "Shlomo Sixt" and o.get("ch") == "Direct")
            )
            sources_meta[name] = {"ok": None if n == 0 else True, "count": n, "skipped": True, "kept_from_existing_snapshot": True}
            continue
        r = results[name]
        sources_meta[name] = {
            "ok": bool(r.get("ok")),
            "count": r.get("count") or 0,
            "url": r.get("url"),
            "errors": r.get("errors") or [],
            "raw_count": r.get("raw_count"),
            "skipped_landing": r.get("skipped_landing"),
        }
        if r.get("kept_previous"):
            sources_meta[name]["kept_previous"] = True
            sources_meta[name]["previous_date"] = r.get("previous_date")

    snap = {
        "date": date,
        "scraped_at": now.isoformat(),
        "timezone": "Asia/Jerusalem",
        "sources": sources_meta,
        "offers": offers,
    }
    HISTORY.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else HISTORY / f"{date}.json"
    out.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out} ({len(offers)} normalized offers)")

    failed = [n for n, m in sources_meta.items() if m.get("ok") is False]
    if failed and not offers:
        print("All requested sources failed.", file=sys.stderr)
        return 1
    if failed:
        print(f"Warning: sources failed: {', '.join(failed)}", file=sys.stderr)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
