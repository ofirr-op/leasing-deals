# השוואת ליסינג פרטי / Private leasing comparison

Daily-updated comparison of private-lease offers from **Shlomo Sixt**, **Pery** and **HTZone** (Shlomo + Albar club deals).

- **Live site (GitHub Pages):** https://ofirr-op.github.io/leasing-deals/
- **Repository:** https://github.com/ofirr-op/leasing-deals

The site opens in **Hebrew (RTL)** by default, with an English toggle. At the top it shows **price drops** since the previous snapshot, then new and removed offers, a sortable/filterable table (one row per model+trim, with a column for each provider/channel), yearly km / fuel / electricity / inflation inputs, a per-component cost breakdown, official 2026 licensing fees, a “comparable totals” toggle, contract notes and sources.

Nothing here is a binding quote. Columns marked “computed” are calculated from the inputs you enter, not prices published by the lessors.

## Requirements

- Python 3.12+ (3.11 is fine)
- `pip install -r requirements.txt`

## How to run

From the repository root:

```bash
python scrape.py          # scrape all sources, write data/history/YYYY-MM-DD.json
python build_site.py      # build the static site into docs/
```

Optional flags:

```bash
python scrape.py --source shlomo          # one source only (keeps the others from today's file)
python scrape.py --save-raw               # also write HTTP bodies under data/raw/ (gitignored)
python scrape.py --date 2026-11-14        # override the snapshot date
python build_site.py --date 2026-11-14    # publish a specific snapshot
```

Dates use **Asia/Jerusalem**. Open `docs/index.html` in a browser (paths are relative, so it works locally and on GitHub Pages).

## File layout

```
scrape.py                 CLI: scrape → data/history/YYYY-MM-DDTHHMMSS.json (never overwrites)
build_site.py             CLI: snapshot + history → docs/
leasing/                  Python package (HTTP, sources, normalize, calc, compare)
  sources/shlomo.py       Shlomo catalog (www.shlomo.co.il/leasing/catalog)
  sources/pery.py         Pery API (agents.pery.co.il)
  sources/htzone.py       HTZone sale/103 listing + item pages
data/reference/           Static reference data (not rediscovered every run)
  canonical.json          Make/model/trim mapping, HTZone groups, Hebrew names
  consumption.json        WLTP L/100 km, CO₂, registry codes, kWh/100 km
  licensing.json          MoT 2026 fee table, broadcasting levy, registry groups
  defaults.json           Default km, fuel, electricity, inflation
  contract terms live in copy.json; sources.json; i18n.json; pery_addons.json
data/history/             One file per scan, never overwritten
  2026-10-31.json         Baseline from the original scrape (legacy daily name)
  YYYY-MM-DDTHHMMSS.json  Each later scan, including a second scan on the same day
site_src/                 HTML/CSS/JS templates
docs/                     Generated GitHub Pages site (committed by the Action)
  data/history.json       Effective-price series built from every snapshot
.github/workflows/daily.yml
```

## History format

Each scan is its own file. Older daily files are named `data/history/YYYY-MM-DD.json`. Every run of `scrape.py` now writes `data/history/YYYY-MM-DDTHHMMSS.json` (Asia/Jerusalem) and leaves previous files untouched, so two scans on one day are both kept. A file looks like:

```json
{
  "date": "2026-11-14",
  "scraped_at": "2026-11-14T19:50:00+02:00",
  "timezone": "Asia/Jerusalem",
  "sources": {
    "shlomo": { "ok": true, "count": 46, "url": "…", "errors": [] },
    "pery":   { "ok": true, "count": 17, "url": "…", "errors": [] },
    "htzone": { "ok": true, "count": 41, "url": "…", "errors": [], "skipped_landing": ["116276", "160208"] }
  },
  "offers": [ { "key": "S-582", "co": "Shlomo Sixt", "ch": "Direct", "mo": 1999, "adv": 8900, "…": "…" } ]
}
```

Offer keys are stable: `S-{importerModel}`, `P-{id}`, `H-{itemId}`. A price drop is a fall in monthly payment, advance, or the computed total at the default inputs. If a source fails, its offers are copied from the newest snapshot that still has them (`sources.<name>.kept_previous` and `previous_date` record that), so they are not shown as removed. The scrape still exits 0. If every source fails and there is no earlier snapshot, the workflow restores `data/history` and continues.

## Daily GitHub Action

`.github/workflows/daily.yml` runs every day at **04:00 UTC** (06:00 IST in winter, 07:00 IDT in summer) and on `workflow_dispatch`. It installs dependencies, scrapes, writes a new timestamped snapshot, builds `docs/` (including `docs/data/history.json`), commits `data/history` and `docs/`, and deploys with `actions/deploy-pages`.

**One-time GitHub setup** (the repo must be public for free GitHub Pages, or the owner needs GitHub Pro for a private Pages site):

1. In the repo: **Settings → Pages → Source: GitHub Actions**.
2. Enable Actions if they are off.
3. Run **Actions → Daily scrape and publish → Run workflow** once.
4. The first Pages deploy may ask you to approve the `github-pages` environment.

If Shlomo, Pery or HTZone block GitHub’s runner IPs (403, empty catalogs, or a challenge page), that source’s previous offers are kept and the failure is recorded in the snapshot’s `sources` field. The Action still builds and deploys. Running `python scrape.py` on your own machine and pushing the new `data/history` file is a fallback when a source stays blocked.

## Regenerating or editing the site

- Change scrape or calculation logic in `leasing/` or the CLIs, then rerun `python scrape.py` (if the data changed) and `python build_site.py`.
- Change the page layout or behaviour in `site_src/` (`index.html`, `styles.css`, `app.js`) and run `python build_site.py`.
- Change default inputs, fee table, canonical names or copy in `data/reference/` and rebuild.
- There is **no** Cursor Canvas source in this repo. The comparable page that used to live at a Cursor canvas is not updated from here; this project is the source of truth and publishes only to GitHub Pages.

## Sources the scraper hits

- Shlomo Sixt catalog: https://www.shlomo.co.il/leasing/catalog (Next.js payload `leasingCars.items`)
- Pery API: `POST https://agents.pery.co.il/api/v1/leasing/get_cars`, then `get_car`, `get_excel_data`, `get_insurances`
- HTZone: `POST https://www.htzone.co.il/_ajax/ajax.index.php` (`act=get_sale_html`, `page_id=103`, private-leasing category 3), then each item page
