"""Compare two snapshots: price drops, increases, new and removed offers."""

from __future__ import annotations

from typing import Any

from leasing.calc import calc, default_inputs


def _totals(offers: list[dict], defaults: dict, lic: dict) -> dict[str, dict]:
    inp = default_inputs(defaults)
    out = {}
    for o in offers:
        c = calc(o, inp, lic)
        out[o["key"]] = {
            "offer": o,
            "mo": o.get("mo"),
            "adv": o.get("adv"),
            "total": c.get("totalNom"),
            "lease": c.get("lease"),
        }
    return out


def _delta(old, new) -> dict | None:
    if old is None or new is None:
        return None
    d = new - old
    pct = (d / old * 100) if old else None
    return {"old": old, "new": new, "delta": d, "pct": pct}


def _canon_label(o: dict) -> str:
    c = o.get("canon")
    if c:
        bits = [c.get("make") or "", c.get("model") or "", c.get("trim") or ""]
        name = " ".join(x for x in bits if x)
        if c.get("variant"):
            name += f" ({c['variant']})"
        return name
    return o.get("model") or o.get("key")


def _row(old: dict, new: dict, kind: str) -> dict:
    o = (new or old)["offer"]
    return {
        "key": o["key"],
        "name": _canon_label(o),
        "co": o.get("co"),
        "ch": o.get("ch"),
        "url": o.get("url"),
        "kind": kind,
        "monthly": _delta((old or {}).get("mo"), (new or {}).get("mo")),
        "advance": _delta((old or {}).get("adv"), (new or {}).get("adv")),
        "total": _delta((old or {}).get("total"), (new or {}).get("total")),
    }


def is_drop(row: dict) -> bool:
    for field in ("monthly", "advance", "total"):
        d = row.get(field)
        if d and d.get("delta") is not None and d["delta"] < 0:
            return True
    return False


def is_increase(row: dict) -> bool:
    # A pure increase: no field dropped, and monthly or advance or total rose.
    if is_drop(row):
        return False
    for field in ("monthly", "advance", "total"):
        d = row.get(field)
        if d and d.get("delta") is not None and d["delta"] > 0:
            return True
    return False


def compare(prev: dict, curr: dict, defaults: dict, lic: dict) -> dict:
    old_m = _totals(prev.get("offers") or [], defaults, lic)
    new_m = _totals(curr.get("offers") or [], defaults, lic)
    old_keys = set(old_m)
    new_keys = set(new_m)
    drops, increases, unchanged = [], [], []
    for k in sorted(old_keys & new_keys):
        row = _row(old_m[k], new_m[k], "changed")
        if is_drop(row):
            drops.append(row)
        elif is_increase(row):
            increases.append(row)
        else:
            unchanged.append(row)
    def _sort_drop(r):
        t = r.get("total") or {}
        return t.get("delta") if t.get("delta") is not None else 0

    drops.sort(key=_sort_drop)  # most negative first
    increases.sort(key=lambda r: -((r.get("total") or {}).get("delta") or 0))

    new_offers = [
        {
            "key": new_m[k]["offer"]["key"],
            "name": _canon_label(new_m[k]["offer"]),
            "co": new_m[k]["offer"].get("co"),
            "ch": new_m[k]["offer"].get("ch"),
            "url": new_m[k]["offer"].get("url"),
            "mo": new_m[k]["mo"],
            "adv": new_m[k]["adv"],
            "total": new_m[k]["total"],
        }
        for k in sorted(new_keys - old_keys)
    ]
    removed = [
        {
            "key": old_m[k]["offer"]["key"],
            "name": _canon_label(old_m[k]["offer"]),
            "co": old_m[k]["offer"].get("co"),
            "ch": old_m[k]["offer"].get("ch"),
            "url": old_m[k]["offer"].get("url"),
            "mo": old_m[k]["mo"],
            "adv": old_m[k]["adv"],
            "total": old_m[k]["total"],
        }
        for k in sorted(old_keys - new_keys)
    ]
    return {
        "previous_date": prev.get("date"),
        "current_date": curr.get("date"),
        "drops": drops,
        "increases": increases,
        "unchanged": len(unchanged),
        "new": new_offers,
        "removed": removed,
        "counts": {
            "previous": len(old_keys),
            "current": len(new_keys),
            "drops": len(drops),
            "increases": len(increases),
            "new": len(new_offers),
            "removed": len(removed),
        },
    }


def latest_drops_from_history(history: list[dict], defaults: dict, lic: dict) -> dict | None:
    """Walk snapshots newest-first and return the most recent comparison that had drops."""
    # history should be sorted oldest → newest
    for i in range(len(history) - 1, 0, -1):
        ch = compare(history[i - 1], history[i], defaults, lic)
        if ch["drops"]:
            return ch
    return None
