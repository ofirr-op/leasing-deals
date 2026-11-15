"""Scrape Shlomo Sixt private-leasing catalog (www.shlomo.co.il/leasing/catalog)."""

from __future__ import annotations

import json
import re
from typing import Any

from leasing.httputil import get, session

CATALOG_URL = "https://www.shlomo.co.il/leasing/catalog"
SITE = "https://www.shlomo.co.il"

FUEL = {
    "בנזין": "Petrol",
    "היברידי": "Hybrid",
    "פלאג אין+בנזין": "PHEV",
    "פלאג אין": "PHEV",
    "דיזל": "Diesel",
}


def _unescape_js(s: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            n = s[i + 1]
            if n == "u" and i + 6 <= len(s):
                try:
                    out.append(chr(int(s[i + 2 : i + 6], 16)))
                    i += 6
                    continue
                except ValueError:
                    pass
            out.append({"n": "\n", "t": "\t", "r": "\r", '"': '"', "'": "'", "/": "/", "\\": "\\"}.get(n, n))
            i += 2
            continue
        out.append(s[i])
        i += 1
    return "".join(out)


def _parse_items(text: str) -> list[dict[str, Any]]:
    # The Next.js catalog page embeds the payload inside a JS string, so quotes
    # are escaped as \\". Fall back to a raw JSON object if it is unescaped.
    markers = ['\\"leasingCars\\":{\\"items\\":', '"leasingCars":{"items":']
    arr = -1
    escaped = False
    for needle in markers:
        i = text.find(needle)
        if i >= 0:
            arr = text.find("[", i)
            escaped = needle.startswith("\\")
            break
    if arr < 0:
        raise ValueError("leasingCars.items not found in catalog page")
    chunk = text[arr : arr + 2_000_000]
    payload = _unescape_js(chunk) if escaped else chunk
    data, _ = json.JSONDecoder().raw_decode(payload)
    if not isinstance(data, list):
        raise ValueError("leasingCars.items is not a list")
    return data


def scrape(sess=None, save_raw=None) -> dict[str, Any]:
    s = sess or session()
    r = get(s, CATALOG_URL)
    if r.status_code != 200 or not r.text:
        # fallback: RSC/flight-style request
        r = get(
            s,
            CATALOG_URL,
            headers={"RSC": "1", "Accept": "text/x-component, text/html;q=0.9,*/*;q=0.8"},
        )
    r.raise_for_status()
    text = r.text
    if save_raw:
        save_raw("shlomo_catalog.html", text.encode("utf-8", "replace"))
    items = _parse_items(text)
    offers = []
    errors = []
    for v in items:
        try:
            k = str(v.get("importerModel") or "")
            if not k:
                continue
            nm = v.get("modelName") or ""
            ft = FUEL.get(v.get("engineType") or "", v.get("engineType") or "Petrol")
            if "היברידי" in nm and ft == "Petrol":
                ft = "Hybrid"
            if str(k).startswith("B1099"):
                ft = "EREV"
            if "MHEV" in nm and ft == "Petrol":
                ft = "Petrol MHEV"
            slug = re.sub(r"[^A-Za-z0-9.]+", "-", (v.get("modelNameEN") or "car")).strip("-") or "car"
            offers.append(
                {
                    "source_id": k,
                    "co": "Shlomo Sixt",
                    "ch": "Direct",
                    "make": v.get("manufacturerDescEN") or v.get("manufacturerDesc") or "",
                    "make_he": v.get("manufacturerDesc") or "",
                    "model": nm,
                    "year": v.get("modelYear"),
                    "fuel": ft,
                    "list": v.get("importerPrice"),
                    "mo": v.get("monthlyPaymentPrivateLeasing"),
                    "adv": v.get("advancePaymentPrivateLeasing"),
                    "term": v.get("privatePeriod") or 36,
                    "km": v.get("privateKM") or 20000,
                    "url": f"{SITE}/leasing/catalog/{slug}/{k}",
                    "engine": v.get("engineSize"),
                    "raw": {
                        "engineType": v.get("engineType"),
                        "modelNameEN": v.get("modelNameEN"),
                    },
                }
            )
        except Exception as e:  # noqa: BLE001
            errors.append(f"{v.get('importerModel')}: {e}")
    return {
        "ok": bool(offers),
        "source": "shlomo",
        "url": CATALOG_URL,
        "count": len(offers),
        "offers": offers,
        "errors": errors,
        "raw_count": len(items),
    }
