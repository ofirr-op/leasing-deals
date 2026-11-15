"""Turn raw source records into canonical offers and attach reference data."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from leasing.paths import REFERENCE, HISTORY

MAKE_FIX = {
    "Byd": "BYD", "BYD": "BYD", "Leap": "Leapmotor", "Ora": "Ora",
    "Lynk & Co": "Lynk & Co", "Lynk&Co": "Lynk & Co", "LYNKCO": "Lynk & Co",
    "Kgm": "KGM", "Mg": "MG", "MG": "MG", "Gwm": "GWM",
    "Avatr": "AVATR", "Avatar": "AVATR",
}


def _load(name: str) -> Any:
    return json.loads((REFERENCE / name).read_text(encoding="utf-8"))


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.lower()
    s = re.sub(r"[\"'׳״`]", "", s)
    s = re.sub(r"[^a-z0-9\u0590-\u05ff]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def load_reference() -> dict[str, Any]:
    can = _load("canonical.json")
    cons = _load("consumption.json")
    lic = _load("licensing.json")
    defaults = _load("defaults.json")
    addons = _load("pery_addons.json")
    # title index from the Oct 31 snapshot, when present
    titles: dict[str, str] = {}
    hist = HISTORY / "2026-10-31.json"
    if hist.exists():
        snap = json.loads(hist.read_text(encoding="utf-8"))
        for o in snap.get("offers") or []:
            if o.get("model"):
                titles[fold(o["model"])] = o["key"]
            if o.get("canon"):
                c = o["canon"]
                titles.setdefault(fold(" ".join(c[k] for k in ("make", "model", "trim") if c.get(k))), o["key"])
    return {
        "canonical": can,
        "consumption": cons,
        "licensing": lic,
        "defaults": defaults,
        "pery_addons": addons,
        "titles": titles,
    }


def _canon_of(key: str, ref: dict) -> dict | None:
    row = (ref["canonical"].get("by_key") or {}).get(key)
    if not row:
        return None
    return {"make": row[0], "model": row[1], "trim": row[2], "variant": row[3]}


def _match_title(title: str, ref: dict) -> tuple[str | None, dict | None]:
    f = fold(title)
    if not f:
        return None, None
    key = ref["titles"].get(f)
    if key:
        return key, _canon_of(key, ref)
    # loose contains against known titles
    best = None
    for t, k in ref["titles"].items():
        if not t or len(t) < 6:
            continue
        if t in f or f in t:
            best = k
            break
    if best:
        return best, _canon_of(best, ref)
    return None, None


def _group_for(canon: dict | None, ref: dict) -> str | None:
    if not canon:
        return None
    want = (canon["make"], canon["model"], canon["trim"])
    by_key = ref["canonical"].get("by_key") or {}
    groups = ref["canonical"].get("htz_group") or {}
    # invert: source key -> group name
    key_to_g = {}
    for g, keys in groups.items():
        for k in keys:
            key_to_g[k] = g
    for k, row in by_key.items():
        if (row[0], row[1], row[2]) == want:
            if k in key_to_g:
                return key_to_g[k]
    return None


def _attach_consumption(o: dict, ref: dict) -> None:
    cons = ref["consumption"]
    by_key = cons.get("by_key") or {}
    by_reg = cons.get("by_registry") or {}
    rec = by_key.get(o["key"])
    if not rec and o.get("g"):
        # copy from a direct offer in the same HTZone group
        for k in (ref["canonical"].get("htz_group") or {}).get(o["g"]) or []:
            rec = by_key.get(k)
            if rec and rec.get("l100") is not None:
                break
            rec = rec or by_key.get(k)
    if not rec and o.get("reg"):
        rec = by_reg.get(o["reg"])
    if not rec and o.get("canon"):
        c = o["canon"]
        want = (c["make"], c["model"], c["trim"])
        for k, row in (ref["canonical"].get("by_key") or {}).items():
            if (row[0], row[1], row[2]) == want and k in by_key:
                rec = by_key[k]
                if rec.get("l100") is not None:
                    break
    if rec:
        if o.get("l100") is None:
            o["l100"] = rec.get("l100")
        if o.get("co2") is None:
            o["co2"] = rec.get("co2")
        if o.get("rng") is None:
            o["rng"] = rec.get("rng")
        if o.get("reg") is None:
            o["reg"] = rec.get("reg")
        if o.get("kwh") is None and rec.get("kwh") is not None:
            o["kwh"] = rec.get("kwh")


def _fix_make(name: str, canon: dict | None) -> str:
    if canon:
        return canon["make"]
    return MAKE_FIX.get(name, name)


def normalize_offer(raw: dict, ref: dict) -> dict:
    co = raw["co"]
    ch = raw.get("ch") or "Direct"
    sid = str(raw["source_id"])
    if ch == "HTZone":
        key = "H-" + sid
    elif co == "Pery":
        key = "P-" + sid
    else:
        key = "S-" + sid

    canon = _canon_of(key, ref)
    matched = None
    if not canon:
        matched, canon = _match_title(raw.get("model") or raw.get("title") or "", ref)
        # Don't reuse another offer's key; only its canon/group
    g = raw.get("g")
    if not g and ch == "HTZone":
        g = _group_for(canon, ref)

    make = _fix_make(raw.get("make") or (canon["make"] if canon else ""), canon)
    o = {
        "key": key,
        "co": co,
        "ch": ch,
        "make": make or (canon["make"] if canon else (raw.get("make") or "")),
        "model": raw.get("model") or raw.get("title") or "",
        "year": raw.get("year"),
        "fuel": raw.get("fuel") or "Petrol",
        "list": raw.get("list"),
        "adv": raw.get("adv"),
        "mo": raw.get("mo"),
        "url": raw.get("url") or "",
        "l100": raw.get("l100"),
        "co2": raw.get("co2"),
        "rng": raw.get("rng"),
        "reg": raw.get("reg"),
        "ko": raw.get("ko"),
        "tiers": raw.get("tiers"),
        "ad": raw.get("ad"),
        "lowestTier": bool(raw.get("lowestTier")),
        "term": raw.get("term") or 36,
        "kwh": raw.get("kwh"),
        "g": g,
        "advReg": raw.get("advReg"),
        "note": raw.get("note") or "",
        "source_id": sid,
        "canon": canon,
        "basis": raw.get("basis"),
    }
    _attach_consumption(o, ref)
    return o


def normalize_all(raw_results: dict[str, dict], ref: dict | None = None) -> list[dict]:
    ref = ref or load_reference()
    out = []
    for src in ("shlomo", "pery", "htzone"):
        block = raw_results.get(src) or {}
        for raw in block.get("offers") or []:
            out.append(normalize_offer(raw, ref))
    # list-price discrepancy notes for HTZone vs Shlomo direct
    by_key = {o["key"]: o for o in out}
    groups = ref["canonical"].get("htz_group") or {}
    for o in out:
        if o["ch"] != "HTZone" or o["co"] != "Shlomo Sixt" or not o.get("g"):
            continue
        for k in groups.get(o["g"]) or []:
            if k.startswith("S-") and k in by_key:
                d = by_key[k]
                if o.get("list") and d.get("list") and o["list"] != d["list"]:
                    note = f"HTZone shows list price ₪{o['list']:,}; Shlomo's site shows ₪{d['list']:,}.".replace(",", ",")
                    # use en-US thousands
                    note = "HTZone shows list price ₪{:,}; Shlomo's site shows ₪{:,}.".format(o["list"], d["list"])
                    o["note"] = (o["note"] + " " + note).strip() if o["note"] else note
                if o.get("mo") and d.get("mo") and o["mo"] != d["mo"]:
                    note = "HTZone monthly is ₪{:+d} relative to Shlomo's site (₪{:,}).".format(o["mo"] - d["mo"], d["mo"])
                    # keep the historical wording when it's +20
                    if o["mo"] - d["mo"] > 0:
                        note = "HTZone monthly is ₪{} above Shlomo's site (₪{:,}).".format(o["mo"] - d["mo"], d["mo"])
                    o["note"] = (o["note"] + " " + note).strip() if o["note"] else note
                break
    return out
