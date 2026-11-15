"""Scrape Pery private-leasing offers via the agents.pery.co.il API."""

from __future__ import annotations

from typing import Any

from leasing.httputil import get, polite_sleep, post, session

API = "https://agents.pery.co.il/api/v1/leasing"
SITE = "https://leasing.pery.co.il"

FUEL = {
    "בנזין": "Petrol",
    "בנזין / היברידי": "Hybrid",
    "היברידי": "Hybrid",
    "פלאג אין": "PHEV",
    "פלאג אין+בנזין": "PHEV",
    "דיזל": "Diesel",
}


def _as_list(data: Any) -> list:
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return list(data.values())
    return []


def _pos(x) -> float:
    try:
        if x in (None, ""):
            return 0.0
        v = float(x)
        return v if v > 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


def scrape(sess=None, save_raw=None) -> dict[str, Any]:
    s = sess or session()
    s.headers.update(
        {
            "Origin": SITE,
            "Referer": SITE + "/",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    )
    cars_r = post(
        s,
        f"{API}/get_cars",
        json={"sort_column": "private_leasing_cars.sort_order", "sort_direction": "ASC"},
    )
    cars_r.raise_for_status()
    cars_json = cars_r.json()
    if save_raw:
        save_raw("pery_cars.json", cars_r.content)
    cars = _as_list(cars_json.get("data") if isinstance(cars_json, dict) else cars_json)
    if not cars:
        raise ValueError("Pery get_cars returned no cars")

    ins_r = get(s, f"{API}/get_insurances")
    ins_r.raise_for_status()
    ins_json = ins_r.json()
    if save_raw:
        save_raw("pery_ins.json", ins_r.content)
    ins = ins_json.get("data") or {}
    svcs = _as_list(ins.get("sub_insurances")) + _as_list(ins.get("vip_services"))

    offers = []
    errors = []
    for c in cars:
        cid = str(c.get("id") or "")
        try:
            polite_sleep(0.15)
            car_r = get(s, f"{API}/get_car", params={"id": cid})
            car_r.raise_for_status()
            cd = (car_r.json() or {}).get("data") or {}
            code = str(cd.get("manufacturer_model_code") or "").strip()
            ex_r = post(
                s,
                f"{API}/get_excel_data",
                json={"manufacturer_code": code, "period": 36},
            )
            ex_r.raise_for_status()
            ex = _as_list((ex_r.json() or {}).get("data"))
            if save_raw:
                save_raw(f"pery/car_{cid}.json", car_r.content)
                save_raw(f"pery/excel_{cid}.json", ex_r.content)

            rows = sorted(
                [
                    r
                    for r in ex
                    if code and str(r.get("manufacturer_code") or "").strip() == code and _pos(r.get("advance")) > 0
                ],
                key=lambda r: float(r["advance"]),
            )
            hasov = _pos(cd.get("override_monthly")) > 0 or _pos(cd.get("override_starting_price")) > 0
            if hasov:
                mo = _pos(cd.get("override_monthly")) or _pos(cd.get("override_starting_price"))
                adv = _pos(cd.get("override_advance")) or (float(rows[0]["advance"]) if rows else 0) or _pos(
                    cd.get("lowest_advance")
                )
                basis = "site override price"
            elif rows:
                mo = float(rows[0]["mileage_20000"])
                adv = float(rows[0]["advance"])
                basis = "lowest-advance tier (API)"
            else:
                mo = None
                adv = None
                basis = "not stated"
            row = rows[0] if rows else None
            kmopts = []
            for km in (10000, 15000, 20000, 25000, 30000):
                f = f"mileage_{km}"
                if not row or _pos(row.get(f)) <= 0:
                    continue
                d = cd.get(f"override_{f}")
                if hasov and d not in (None, ""):
                    val = round(mo + float(d))
                elif not hasov:
                    val = round(float(row[f]))
                else:
                    val = round(mo)
                kmopts.append([km // 1000, val])
            addons = []
            for svc in svcs:
                pr = None
                sid = str(svc.get("id"))
                ov = cd.get("servicePrices") or {}
                if sid in ov and ov[sid] not in (None, ""):
                    pr = float(ov[sid])
                elif row and _pos(row.get(svc.get("excel_name"))) > 0:
                    pr = float(row[svc["excel_name"]])
                note = ""
                if svc.get("excel_name") == "new_driver" and pr is not None and pr <= 1:
                    note = f'API value "{row.get(svc.get("excel_name"))}" – unclear, not a usable price'
                    pr = None
                addons.append(
                    {
                        "id": svc.get("id"),
                        "excel_name": svc.get("excel_name"),
                        "name": (svc.get("description") or "").strip(),
                        "price": pr,
                        "note": note,
                        "info": (svc.get("info") or "").strip(),
                    }
                )
            # Keep the historical 9-slot order used by the comparison page.
            slot_by_excel = {
                "new_driver": 0,
                "young_driver": 0,
                "cancellation_self_participation": 1,
                "self_participation": 1,
                "cancellation_return_to_advance": 2,
                "return_to_value": 2,
                "maintenance_package": 3,
                "movement_for_maintenance": 4,  # Pery's name for the licensing add-on
                "replace_breaks": 5,
                "replace_tires": 6,
                "monthly_wash": 7,
                "replace_battery": 8,
            }
            ad = [None] * 9
            # Prefer name matching when excel_name is unknown
            name_slots = [
                ("נהג", 0),
                ("השתתפות", 1),
                ("השבה", 2),
                ("טיפול", 3),
                ("רישוי", 4),
                ("בלמ", 5),
                ("צמיג", 6),
                ("שטיפ", 7),
                ("מצבר", 8),
            ]
            used = set()
            for a in addons:
                exn = (a.get("excel_name") or "").lower()
                slot = None
                for key, idx in slot_by_excel.items():
                    if key in exn:
                        slot = idx
                        break
                if slot is None:
                    nm = a.get("name") or ""
                    for frag, idx in name_slots:
                        if frag in nm and idx not in used:
                            slot = idx
                            break
                if slot is not None and slot not in used:
                    ad[slot] = None if a["price"] is None else (int(a["price"]) if float(a["price"]).is_integer() else a["price"])
                    used.add(slot)

            tiers = [
                [int(float(r["advance"])), round(float(r["mileage_20000"]))]
                for r in rows
                if _pos(r.get("mileage_20000")) > 0
            ]
            ft = FUEL.get(c.get("engine_type_name") or "", c.get("engine_type_name") or "Petrol")
            slug = c.get("slug") or cid
            offers.append(
                {
                    "source_id": cid,
                    "co": "Pery",
                    "ch": "Direct",
                    "make": c.get("car_manufacturer_name") or "",
                    "model": (c.get("car_model") or "").strip(),
                    "year": int(c["year_on_road"]) if c.get("year_on_road") else None,
                    "fuel": ft,
                    "list": int(float(c["price_list"])) if c.get("price_list") not in (None, "") else None,
                    "mo": round(mo) if mo else None,
                    "adv": round(adv) if adv else None,
                    "term": 36,
                    "km": 20000,
                    "url": f"{SITE}/leasing/{slug}",
                    "ko": kmopts or None,
                    "tiers": tiers or None,
                    "ad": ad,
                    "addons": addons,
                    "lowestTier": False,
                    "basis": basis,
                    "code": code,
                }
            )
        except Exception as e:  # noqa: BLE001
            errors.append(f"P-{cid}: {e}")

    return {
        "ok": bool(offers),
        "source": "pery",
        "url": SITE,
        "count": len(offers),
        "offers": offers,
        "errors": errors,
        "raw_count": len(cars),
    }
