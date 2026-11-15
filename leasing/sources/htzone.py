"""Scrape HTZone private-leasing club offers (sale/103, category 3)."""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from leasing.httputil import get, polite_sleep, post, session

SALE_URL = "https://www.htzone.co.il/sale/103"
AJAX_URL = "https://www.htzone.co.il/_ajax/ajax.index.php"
ITEM_URL = "https://www.htzone.co.il/item/{id}/"
PAGE_ID = 103
CATEGORY = 3  # private leasing
COUNT = 15
LANDING_IDS = {"116276", "160208"}

SHEKEL = re.compile(
    r"(?:₪|ש[\"״']?ח)\s*([\d,]+)|([\d,]+)\s*(?:₪|ש[\"״']?ח)"
)
MONTHLY_SH = re.compile(r"רק\s*₪?\s*([\d,]+)\s*₪?\s*[בל]?חודש")
MONTHLY_GENERIC = re.compile(r"([\d,]+)\s*₪\s*ל[-־–]?חודש")
MONTHLY_AL = re.compile(r"החל\s*מ[־\-–]?\s*([\d,]+)\s*₪?\s*ל[־\-–]?\s*(\d+)\s*חודש")
LIST_RE = re.compile(r"מחירון\s*[:：]\s*([\d,]+)")
ADV_CLUB = re.compile(
    r"תשלום\s*ראשוני[^0-9]{0,20}([\d,]+)\s*ש[\"״']?ח.{0,40}במקום\s*([\d,]+)"
)
ADV_AL = re.compile(r"בתוספת\s*מקדמה\s*([\d,]+)")
NO_ADV = re.compile(r"ללא\s*מקדמה|תשלום\s*ראשוני\s*ב\s*0")
TERM_RE = re.compile(r"ל[־\-–]?\s*(\d+)\s*חודש")
YEAR_RE = re.compile(r"\b(202[0-9]|203[0-9])\b")
FUEL_LINE = re.compile(r"סוג\s*מנוע\s*[:：]?\s*([^\n<]+)")

FUEL = {
    "בנזין": "Petrol",
    "היברידי": "Hybrid",
    "פלאג אין": "PHEV",
    "פלאג-אין": "PHEV",
    "פלאג אין+בנזין": "PHEV",
    "דיזל": "Diesel",
    "חשמלי": "EV",
}


def _num(s: str | None) -> int | None:
    if not s:
        return None
    s = s.replace(",", "").replace(" ", "")
    if not s.isdigit():
        return None
    return int(s)


def _list_ids(html: str) -> list[str]:
    ids = []
    seen = set()
    for m in re.finditer(r"data-item=['\"](\d+)['\"]", html):
        i = m.group(1)
        if i not in seen:
            seen.add(i)
            ids.append(i)
    return ids


def _fetch_listing(s, start: int, filter_val) -> dict:
    r = post(
        s,
        AJAX_URL,
        data={
            "act": "get_sale_html",
            "start": start,
            "count": COUNT,
            "filter": filter_val,
            "page_id": PAGE_ID,
            "max_price": "",
            "min_price": "",
            "brand": "[]",
            "date": "[]",
            "area": "[]",
            "category": "[]",
            "file": "sale",
        },
        headers={
            "Referer": SALE_URL,
            "Origin": "https://www.htzone.co.il",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        },
    )
    r.raise_for_status()
    return r.json()


def _plain(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    return re.sub(r"\n{3,}", "\n\n", text)


def _fuel_from(s: str) -> str | None:
    if not s:
        return None
    if "MHEV" in s:
        return "Petrol MHEV"
    if any(x in s for x in ("פלאג", "PHEV", "DM-I", "DM-i", "DMI")):
        return "PHEV"
    if "חשמלי" in s or re.search(r"\bEV\b", s) or "AVATR" in s.upper():
        return "EV"
    if "היברידי" in s or "Hybrid" in s or re.search(r"\bHEV\b", s):
        return "Hybrid"
    if "דיזל" in s or "Diesel" in s:
        return "Diesel"
    if "בנזין" in s or "Petrol" in s or "Gasoline" in s:
        return "Petrol"
    return None


def _fuel(text: str, title: str) -> str:
    m = FUEL_LINE.search(text)
    return _fuel_from(title) or _fuel_from(m.group(1) if m else "") or _fuel_from(text[:1500]) or "Petrol"


def _provider(title: str, text: str) -> str:
    # The HTML has a long header, so look for distinctive body phrases.
    if "אלבר מאצ" in text or "אלבר Match" in text or "מיניליס" in text or "Minilease" in text:
        return "Albar"
    if "הליסינג הפרטיפעולי של שלמה" in text or "שלמה ליסינג פרטי" in text:
        return "Shlomo Sixt"
    if "אלבר" in text and ("החל מ-" in text or "החל מ־" in text):
        return "Albar"
    return "Shlomo Sixt"


def _is_landing(item_id: str, title: str, mo: int | None) -> bool:
    if item_id in LANDING_IDS:
        return True
    if mo is None:
        return True
    t = title.strip()
    if t in ("ליסינג רכב פרטי שלמה", "הליסינג הפרטי של אלבר מאצ'", "ליסינג פרטי תפעולי של שלמה"):
        return True
    if "מבחר רכבים" in t and mo is None:
        return True
    return False


def parse_item(item_id: str, html: str) -> dict[str, Any] | None:
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.find("h1") or soup.find("h2")
    title = h1.get_text(" ", strip=True) if h1 else ""
    if not title:
        og = soup.find("meta", property="og:title")
        title = og["content"].strip() if og and og.get("content") else ""
    text = _plain(html)
    # Cut related-items noise
    cut = re.search(r"אולי יעניין אותך", text)
    body = text[: cut.start()] if cut else text

    mo = None
    term = 36
    # Prefer the visible price badge on the item page.
    for sp in soup.select("span.price, .price.bg-gradient"):
        pt = re.sub(r"\s+", " ", sp.get_text(" ", strip=True))
        m = MONTHLY_SH.search(pt) or re.search(r"₪\s*([\d,]+)\s*[בל]?חודש", pt) or re.search(r"([\d,]+)\s*₪", pt)
        val = _num(m.group(1)) if m else None
        if val and val >= 200:
            mo = val
            break
    m = MONTHLY_SH.search(body)
    if m and _num(m.group(1)) and _num(m.group(1)) >= 200 and mo is None:
        mo = _num(m.group(1))
    if mo is None:
        m = MONTHLY_AL.search(body)
        if m and (_num(m.group(1)) or 0) >= 200:
            mo = _num(m.group(1))
            term = _num(m.group(2)) or 36
    if mo is None:
        cands = [(_num(x.group(1)), x) for x in MONTHLY_GENERIC.finditer(body)]
        cands = [c for c in cands if c[0] and c[0] >= 200]
        if cands:
            mo = cands[0][0]
    if mo is None:
        m = re.search(r"([\d,]+)\s*₪\s*ל[־\-–]?\s*(\d+)\s*חודש", body)
        if m and (_num(m.group(1)) or 0) >= 200:
            mo = _num(m.group(1))
            term = _num(m.group(2)) or 36
    tm = TERM_RE.search(body)
    if tm and mo is not None:
        # don't override Albar term already parsed; prefer explicit
        t = _num(tm.group(1))
        if t in (12, 18, 24, 30, 36) and "Minilease" in title or "מיניליס" in body or "יד שנייה" in title:
            term = t or term

    list_price = None
    lm = LIST_RE.search(body)
    if lm:
        list_price = _num(lm.group(1))

    adv = None
    adv_reg = None
    am = ADV_CLUB.search(body)
    if am:
        adv = _num(am.group(1))
        adv_reg = _num(am.group(2))
    elif ADV_AL.search(body):
        adv = _num(ADV_AL.search(body).group(1))
    elif NO_ADV.search(body):
        adv = 0
        if list_price is not None and list_price <= 184990:
            adv_reg = 8900
        elif list_price is not None and list_price <= 254990:
            adv_reg = 12900

    # Club-rule fallback for Shlomo when list is known but advance isn't.
    co = _provider(title, body)
    if co == "Shlomo Sixt" and adv is None and list_price is not None:
        if list_price <= 184990:
            adv, adv_reg = 0, 8900
        elif list_price <= 254990:
            adv, adv_reg = 6900, 12900

    if _is_landing(item_id, title, mo):
        return None

    year = None
    ym = YEAR_RE.search(title) or YEAR_RE.search(body[:800])
    if ym:
        year = int(ym.group(1))

    note = ""
    if "עמדת טעינה" in body or "VIMORE" in body:
        note = "Free VIMORE 11 kW home charger (unit only, installation not included; stated value ₪3,000). No car swap for EVs."
    if "מיניליס" in body or "יד שנייה" in title or "משומש" in body[:600]:
        extra = "Used fleet car refurbished by Albar; km quota not stated; no car swap. Lessor: Albar."
        note = (note + " " + extra).strip()

    kwh = None
    if "AVATR" in title.upper() or "אאווטר" in title:
        kwh = 21.6  # importer spec sheet (Ultra), kept as static reference

    make = ""
    # crude make from title — normalize later
    return {
        "source_id": item_id,
        "co": co,
        "ch": "HTZone",
        "make": make,
        "model": title,
        "year": year,
        "fuel": _fuel(body, title),
        "list": list_price,
        "mo": mo,
        "adv": adv,
        "advReg": adv_reg,
        "term": term or 36,
        "km": 20000,
        "url": ITEM_URL.format(id=item_id),
        "kwh": kwh,
        "note": note,
        "from_price": co == "Albar",
        "title": title,
    }


def scrape(sess=None, save_raw=None) -> dict[str, Any]:
    s = sess or session()
    # Warm up cookies from the sale page
    land = get(s, SALE_URL, headers={"Referer": "https://www.htzone.co.il/"})
    if save_raw:
        save_raw("htzone_sale.html", land.content)

    ids: list[str] = []
    last = False
    start = 0
    errors = []
    used_filter = CATEGORY
    # Some deployments want filter=3, others an empty filter + category nav.
    for attempt_filter in (CATEGORY, "", 3):
        try:
            page0 = _fetch_listing(s, 0, attempt_filter)
        except Exception as e:  # noqa: BLE001
            errors.append(f"listing start=0 filter={attempt_filter}: {e}")
            continue
        html = (page0 or {}).get("sale_html") or ""
        found = _list_ids(html)
        if found:
            used_filter = attempt_filter
            ids.extend(found)
            last = False
            if save_raw:
                save_raw("htzone_s_0.json", str(page0).encode("utf-8", "replace") if not isinstance(page0, (bytes, bytearray)) else page0)
                import json as _j
                save_raw("htzone_s_0.json", _j.dumps(page0, ensure_ascii=False).encode("utf-8"))
            break
    if not ids:
        raise ValueError("HTZone listing returned no items")

    start = COUNT
    while not last and start <= 200:
        polite_sleep(0.2)
        try:
            page = _fetch_listing(s, start, used_filter)
        except Exception as e:  # noqa: BLE001
            errors.append(f"listing start={start}: {e}")
            break
        html = (page or {}).get("sale_html") or ""
        batch = _list_ids(html)
        if save_raw:
            import json as _j
            save_raw(f"htzone_s_{start}.json", _j.dumps(page, ensure_ascii=False).encode("utf-8"))
        for i in batch:
            if i not in ids:
                ids.append(i)
        # Don't trust last_item alone — it has been seen True before the list was finished.
        last = not batch
        start += COUNT

    offers = []
    skipped = []
    for i, item_id in enumerate(ids):
        if item_id in LANDING_IDS:
            skipped.append(item_id)
            continue
        try:
            polite_sleep(0.25)
            r = get(
                s,
                ITEM_URL.format(id=item_id),
                headers={"Referer": SALE_URL},
            )
            r.raise_for_status()
            if save_raw:
                save_raw(f"htzone/item_{item_id}.html", r.content)
            rec = parse_item(item_id, r.text)
            if rec is None:
                skipped.append(item_id)
            else:
                offers.append(rec)
        except Exception as e:  # noqa: BLE001
            errors.append(f"H-{item_id}: {e}")

    return {
        "ok": bool(offers),
        "source": "htzone",
        "url": SALE_URL,
        "count": len(offers),
        "offers": offers,
        "errors": errors,
        "skipped_landing": skipped,
        "raw_count": len(ids),
        "filter": used_filter,
    }
