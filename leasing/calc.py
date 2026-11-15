"""Cost calculations — kept in lockstep with the comparison page."""

from __future__ import annotations

import math
from typing import Any

INCLUDED_KM = 20000


def lic_group(o: dict, lic: dict) -> int | None:
    reg = o.get("reg")
    rg = (lic or {}).get("registry_group") or {}
    if reg and rg.get(reg):
        return int(rg[reg])
    lst = o.get("list")
    if lst is None:
        return None
    bands = lic.get("bands") or []
    return 1 + sum(1 for b in bands if lst > b)


def lic_from_reg(o: dict, lic: dict) -> bool:
    reg = o.get("reg")
    return bool(reg and (lic or {}).get("registry_group", {}).get(reg) is not None)


def lic_official(o: dict, inp: dict) -> bool:
    if o.get("co") == "Albar":
        return False
    ad = o.get("ad") or []
    if o.get("co") == "Pery" and inp.get("cmp") and len(ad) > 4 and ad[4] is not None:
        return False
    return True


def is_cpi(o: dict) -> bool:
    if o.get("co") == "Shlomo Sixt":
        return True
    if o.get("co") == "Albar":
        return o.get("key") != "H-166284"
    return False


def calc(o: dict, inp: dict, lic: dict) -> dict[str, Any]:
    flags: list[str] = []
    pkg_km = int(inp.get("included_km") or INCLUDED_KM)
    mo_at = o.get("mo")
    ko = o.get("ko") or []
    if o.get("co") == "Pery" and ko:
        opts = sorted(({"km": p[0] * 1000, "mo": p[1]} for p in ko), key=lambda x: x["km"])
        fit = next((p for p in opts if p["km"] >= inp["km"]), opts[-1])
        pkg_km = fit["km"]
        mo_at = fit["mo"]
    if o.get("key") == "H-166284":
        flags.append("included km not stated (20,000/yr assumed)")
    excess_km = max(0, inp["km"] - pkg_km)
    excess_yr: float | None = 0
    if excess_km > 0:
        if inp.get("xRate"):
            excess_yr = excess_km * inp["xRate"]
        else:
            excess_yr = None
            flags.append("excess km not priced")
    fuel_price = inp.get("diesel") if o.get("fuel") == "Diesel" else inp.get("petrol")
    per_km = None
    if o.get("kwh") is not None:
        if inp.get("elec") is not None:
            per_km = (o["kwh"] / 100) * inp["elec"]
        else:
            flags.append("no electricity price")
    elif o.get("l100") is not None and fuel_price is not None:
        per_km = (o["l100"] / 100) * fuel_price
    else:
        flags.append("no official consumption" if o.get("l100") is None else "no fuel price")
    if o.get("fuel") in ("PHEV", "EREV"):
        flags.append("charging electricity not included")
    energy_yr = per_km * inp["km"] if per_km is not None else None
    lgrp = lic_group(o, lic)
    fees = lic.get("fee_up_to_3_years") or []
    tv = lic.get("broadcasting_levy") or 0
    use_off = lic_official(o, inp)
    lic_yr = (fees[lgrp - 1] + tv) if (use_off and lgrp is not None and 0 < lgrp <= len(fees)) else None
    if use_off and lgrp is None:
        flags.append("licensing fee not stated (no list price)")
    term = o.get("term") or 36
    lic_n = math.ceil(term / 12)
    extra_mo = 0
    if o.get("co") == "Pery" and o.get("ad"):
        ad = o["ad"]
        if (inp.get("peryMaint") or inp.get("cmp")) and len(ad) > 3 and ad[3] is not None:
            extra_mo += ad[3]
        if inp.get("cmp") and len(ad) > 4 and ad[4] is not None:
            extra_mo += ad[4]
    empty = {
        "pkgKm": pkg_km, "moAtKm": mo_at, "excessKm": excess_km, "excessYr": excess_yr,
        "perKm": per_km, "energyYr": energy_yr, "lease": None, "totalNom": None,
        "totalInf": None, "effNom": None, "effInf": None, "flags": flags,
        "licYr": lic_yr, "licN": lic_n, "licGroup": lgrp,
    }
    if mo_at is None or o.get("adv") is None:
        return empty
    disc = 3000 if (o.get("co") == "Shlomo Sixt" and o.get("ch") == "Direct" and inp.get("shDisc")) else 0
    monthly = mo_at + extra_mo
    lease = o["adv"] + monthly * term - disc
    years = term / 12
    cpi = is_cpi(o)
    total_nom = lease
    total_inf = o["adv"] - disc
    infl = float(inp.get("infl") or 0)
    for y in range(int(years) if years == int(years) else math.ceil(years)):
        # For non-integer years (e.g. 12-month is 1), loop once per full year of the term.
        if y >= years:
            break
        f = (1 + infl / 100) ** y
        total_nom += (energy_yr or 0) + (excess_yr or 0) + (lic_yr or 0)
        total_inf += 12 * mo_at * (f if cpi else 1) + 12 * extra_mo + (energy_yr or 0) * f + (excess_yr or 0) + (lic_yr or 0) * f
    # 12-month term: years=1, one iteration. 36-month: 3 iterations. Matches the page.
    return {
        "pkgKm": pkg_km, "moAtKm": mo_at, "excessKm": excess_km, "excessYr": excess_yr,
        "perKm": per_km, "energyYr": energy_yr, "lease": lease, "totalNom": total_nom,
        "totalInf": total_inf, "effNom": total_nom / term, "effInf": total_inf / term,
        "flags": flags, "licYr": lic_yr, "licN": lic_n, "licGroup": lgrp,
    }


def default_inputs(defaults: dict) -> dict:
    return {
        "km": int(defaults.get("km") or 20000),
        "petrol": defaults.get("petrol"),
        "diesel": defaults.get("diesel"),
        "elec": defaults.get("elec"),
        "infl": float(defaults.get("infl") or 0),
        "xRate": defaults.get("xRate"),
        "shDisc": bool(defaults.get("shDisc")),
        "peryMaint": bool(defaults.get("peryMaint")),
        "cmp": bool(defaults.get("cmp")),
        "included_km": int(defaults.get("included_km") or 20000),
    }
