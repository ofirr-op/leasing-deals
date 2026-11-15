"""Compact effective-price series, one point per saved scan.

Effective price is the nominal effective monthly (`effNom`) from leasing.calc
at the default assumptions: advance + quoted monthly × term, plus fuel or
electricity and the official licensing fee for each year of the term, divided
by the term in months. Inflation, the Shlomo online discount, Pery add-ons and
excess kilometres are not included. The monthly figure stored beside it is the
quoted monthly payment (`mo`), not the effective price.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from leasing.calc import calc, default_inputs

# Same short powertrain codes as site_src/app.js `PT` / `grpKey`.
PT = {
    "Petrol": "Petrol",
    "Petrol MHEV": "MHEV",
    "Hybrid": "HEV",
    "PHEV": "PHEV",
    "EREV": "EREV",
    "EV": "EV",
    "Diesel": "Diesel",
}

# One line per lessor/channel. Shlomo direct and Shlomo via HTZone are separate
# because the prices differ, and Albar only publishes through HTZone.
COMPANIES = [
    {"id": "shlomo", "en": "Shlomo Sixt", "he": "שלמה SIXT", "color": "#0f6e62"},
    {"id": "shlomo_htz", "en": "Shlomo via HTZone", "he": "שלמה ב-HTZone", "color": "#7c3aed"},
    {"id": "pery", "en": "Pery", "he": "פרי", "color": "#e06a12"},
    {"id": "albar", "en": "Albar via HTZone", "he": "אלבר ב-HTZone", "color": "#1d4ed8"},
]

_SOURCE_COMPANIES = {
    "shlomo": ("shlomo",),
    "pery": ("pery",),
    "htzone": ("shlomo_htz", "albar"),
}


def company_id(offer: dict) -> str:
    co = offer.get("co")
    if co == "Pery":
        return "pery"
    if co == "Albar":
        return "albar"
    if offer.get("ch") == "HTZone":
        return "shlomo_htz"
    return "shlomo"


def canon_parts(offer: dict) -> tuple[str, str, str, str]:
    """make, model, trim, powertrain — the same key the offers table uses."""
    canon = offer.get("canon") or {}
    fuel = offer.get("fuel") or ""
    pt = PT.get(fuel, fuel)
    if canon:
        return (canon.get("make") or "", canon.get("model") or "", canon.get("trim") or "", pt or "")
    return (offer.get("make") or "", offer.get("model") or "", "", pt or "")


def _carried(snap: dict) -> set[str]:
    """Companies whose offers in this scan were copied from an older snapshot."""
    out: set[str] = set()
    for name, meta in (snap.get("sources") or {}).items():
        if isinstance(meta, dict) and meta.get("kept_previous"):
            out.update(_SOURCE_COMPANIES.get(name, ()))
    return out


def _shekel(value) -> int | None:
    if value is None:
        return None
    return int(round(float(value)))


def _definition(defaults: dict) -> dict[str, str]:
    km = int(defaults.get("km") or 20000)
    petrol = defaults.get("petrol")
    elec = defaults.get("elec")
    km_s = f"{km:,}"
    en = (
        "Each point is one saved scan; earlier scans are kept and are never overwritten. "
        f"Effective price is the nominal effective monthly at the default assumptions "
        f"({km_s} km/year, petrol ₪{petrol}/L, electricity ₪{elec}/kWh): "
        "advance + the quoted monthly payment × the term, plus fuel or electricity and the official "
        "licensing fee for each year of the term, divided by the number of months. "
        "The Shlomo ₪3,000 online discount and the Pery add-ons are off, excess kilometres are not priced, "
        "and inflation is not included. “Monthly” in the tooltip is the quoted monthly payment. "
        "Shlomo direct, Shlomo via HTZone, Pery and Albar via HTZone each have their own line, "
        "because those are different prices."
    )
    he = (
        "כל נקודה היא סריקה שנשמרה; סריקות קודמות נשמרות ואינן נדרסות. "
        f"המחיר האפקטיבי הוא התשלום החודשי האפקטיבי הנומינלי לפי ברירות המחדל "
        f"({km_s} ק\"מ בשנה, בנזין ₪{petrol} לליטר, חשמל ₪{elec} לקוט\"ש): "
        "מקדמה + התשלום החודשי שפורסם × התקופה, ועוד דלק או חשמל ואגרת הרישוי הרשמית "
        "לכל שנת תקופה, חלקי מספר החודשים. "
        "הנחת ₪3,000 של שלמה ותוספות פרי כבויות, ק\"מ עודף לא מתומחר, ואינפלציה לא נכללת. "
        "\"חודשי\" בחלון הריחוף הוא התשלום החודשי שפורסם. "
        "לשלמה ישיר, לשלמה ב-HTZone, לפרי ולאלבר ב-HTZone יש קו נפרד, כי אלה מחירים שונים."
    )
    return {"metric": "effNom", "en": en, "he": he}


def _labels(snaps: list[dict]) -> list[dict]:
    counts: dict[str, int] = defaultdict(int)
    for snap in snaps:
        counts[str(snap.get("date") or "")] += 1
    rows = []
    for snap in snaps:
        day = str(snap.get("date") or "")
        at = str(snap.get("scraped_at") or "")
        clock = at[11:16] if len(at) >= 16 else ""
        label = f"{day} {clock}" if counts[day] > 1 and clock else day
        tip = f"{day} {clock}" if clock and clock != "00:00" else day
        rows.append({"date": day, "label": label, "tip": tip})
    # Two scans in the same minute would share a label and collapse on the axis.
    seen: dict[str, list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        seen[row["label"]].append(i)
    for label, idxs in seen.items():
        if len(idxs) < 2:
            continue
        for n, i in enumerate(idxs, start=1):
            rows[i]["label"] = f"{label} #{n}"
            rows[i]["tip"] = rows[i]["label"]
    return rows


def build_price_history(snaps: list[dict], defaults: dict, lic: dict) -> dict:
    """snaps: oldest first. Offers copied after a failed source are not plotted."""
    inp = default_inputs(defaults)
    # model id -> company id -> list of (scan_index, eff, monthly)
    series: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    parts_of: dict[str, tuple[str, str, str, str]] = {}

    for index, snap in enumerate(snaps):
        carried = _carried(snap)
        best: dict[tuple[str, str], tuple[int, int | None]] = {}
        for offer in snap.get("offers") or []:
            company = company_id(offer)
            if company in carried:
                continue
            priced = calc(offer, inp, lic)
            eff = _shekel(priced.get("effNom"))
            if eff is None:
                continue
            parts = canon_parts(offer)
            model_id = "|".join(parts)
            monthly = _shekel(offer.get("mo"))
            slot = (model_id, company)
            prev = best.get(slot)
            if prev is None or eff < prev[0] or (eff == prev[0] and (monthly or 0) < (prev[1] or 0)):
                best[slot] = (eff, monthly)
            parts_of[model_id] = parts
        for (model_id, company), (eff, monthly) in best.items():
            series[model_id][company].append([index, eff, monthly])

    models = []
    for model_id in sorted(series, key=lambda mid: parts_of[mid]):
        make, model, trim, pt = parts_of[model_id]
        packed = {cid: pts for cid, pts in series[model_id].items() if pts}
        if not packed:
            continue
        models.append({
            "id": model_id,
            "make": make,
            "model": model,
            "trim": trim,
            "pt": pt,
            "series": packed,
        })

    assumptions = {
        "km": int(defaults.get("km") or 20000),
        "petrol": defaults.get("petrol"),
        "diesel": defaults.get("diesel"),
        "elec": defaults.get("elec"),
        "infl_included": False,
        "shDisc": False,
        "peryMaint": False,
        "cmp": False,
        "xRate": None,
    }
    return {
        "definition": _definition(defaults),
        "assumptions": assumptions,
        "companies": COMPANIES,
        "scans": _labels(snaps),
        "models": models,
    }


def history_from_files(loaded: list[tuple[Path, dict]], defaults: dict, lic: dict) -> dict:
    return build_price_history([snap for _, snap in loaded], defaults, lic)
