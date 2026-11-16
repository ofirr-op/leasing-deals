"""Scrape HTZone private-leasing club offers (sale/103, "ליסינג פרטי" tab)."""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from leasing.httputil import get, polite_sleep, session

SALE_URL = "https://www.htzone.co.il/sale/103"
# Next.js listing. The old POST /_ajax/ajax.index.php?act=get_sale_html now 404s.
SALE_ITEMS_URL = "https://www.htzone.co.il/api/sale-items"
ITEM_URL = "https://www.htzone.co.il/item/{id}/"
PAGE_ID = 103
# sale/103 is the whole "הטבות רכב" page. Private leasing is one tab
# (label "ליסינג פרטי", id 2 as of 2026-11-16). The id is read from the page.
PRIVATE_TAB_LABEL = "ליסינג פרטי"
PRIVATE_TAB_FALLBACK = 2
LANDING_IDS = {"116276", "160208"}
_TAB_RE = re.compile(r'\{"id"\s*:\s*(\d+)\s*,\s*"label"\s*:\s*"([^"]*)"\}')

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


def _private_tab_id(html: str) -> int | None:
    """Tab id for private leasing, from the sale page's Next.js payload."""
    text = html.replace('\\"', '"')
    for m in _TAB_RE.finditer(text):
        label = re.sub(r"\s+", " ", m.group(2)).strip()
        if label == PRIVATE_TAB_LABEL:
            return int(m.group(1))
    return None


def _fetch_sale_items(s, cat: int, page: int) -> dict:
    r = get(
        s,
        SALE_ITEMS_URL,
        params={"id": PAGE_ID, "cat": cat, "page": page},
        headers={
            "Referer": SALE_URL,
            "Accept": "application/json",
        },
    )
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        raise ValueError(f"HTZone sale-items returned {type(data).__name__}")
    return data


def _is_private_lease(item: dict) -> bool:
    ga = item.get("ga") or {}
    folded = re.sub(r"\s+", "", str(ga.get("item_category2") or ""))
    if not folded:
        return True
    return "ליסינגפרטי" in folded


def _item_id(item: dict) -> str | None:
    ga = item.get("ga") or {}
    iid = item.get("id")
    if iid is None:
        iid = ga.get("item_id")
    if iid is None:
        return None
    return str(iid)


def _collect_ids(s, cat: int, save_raw) -> tuple[list[str], list[str]]:
    ids: list[str] = []
    seen: set[str] = set()
    errors: list[str] = []
    page = 1
    total = 0
    raw_seen = 0
    while page <= 40:
        if page > 1:
            polite_sleep(0.15)
        try:
            data = _fetch_sale_items(s, cat, page)
        except Exception as e:  # noqa: BLE001
            errors.append(f"listing cat={cat} page={page}: {e}")
            break
        if save_raw:
            import json as _j

            save_raw(
                f"htzone_sale_items_c{cat}_p{page}.json",
                _j.dumps(data, ensure_ascii=False).encode("utf-8"),
            )
        batch = data.get("data") or []
        if not isinstance(batch, list):
            errors.append(f"listing cat={cat} page={page}: data is not a list")
            break
        if page == 1:
            try:
                total = int(data.get("total") or 0)
            except (TypeError, ValueError):
                total = 0
        for item in batch:
            if not isinstance(item, dict) or not _is_private_lease(item):
                continue
            iid = _item_id(item)
            if iid and iid not in seen:
                seen.add(iid)
                ids.append(iid)
        raw_seen += len(batch)
        if not batch or (total and raw_seen >= total):
            break
        page += 1
    return ids, errors


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
    errors: list[str] = []
    html = ""
    try:
        land = get(s, SALE_URL, headers={"Referer": "https://www.htzone.co.il/"})
        land.raise_for_status()
        html = land.text
        if save_raw:
            save_raw("htzone_sale.html", land.content)
    except Exception as e:  # noqa: BLE001
        errors.append(f"sale page: {e}")

    tab = _private_tab_id(html) if html else None
    if tab is None:
        errors.append(
            f"private-leasing tab not found; using category {PRIVATE_TAB_FALLBACK}"
        )
        tab = PRIVATE_TAB_FALLBACK

    ids, list_errors = _collect_ids(s, tab, save_raw)
    errors.extend(list_errors)
    if not ids and tab != PRIVATE_TAB_FALLBACK:
        ids, list_errors = _collect_ids(s, PRIVATE_TAB_FALLBACK, save_raw)
        errors.extend(list_errors)
        if ids:
            tab = PRIVATE_TAB_FALLBACK
    if not ids:
        raise ValueError("HTZone listing returned no items")

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
        "filter": tab,
    }
