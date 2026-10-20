# Paraca Monitor: alternative data for Paraca Inc. (TSE 4809)

An independent, reproducible alternative-data platform for equity research on **Paraca Inc. (パラカ)**, a Japanese coin-parking
operator. It collects what Paraca publicly lists, stores the history durably, and puts it next to the company's official
results and a transparent forecasting model. It is designed to sit beside an independent Times (Park24) monitor and be
compared with it through shared exports, without sharing collectors or GitHub Actions quota.

> **Key limitation (read first).** No compliant source publishes real-time availability for Paraca's *hourly* lots
> (see [docs/feasibility.md](docs/feasibility.md)). Utilization, busy/full share and the fee × utilization revenue proxy
> are therefore built but **switched off**, and show why. Nothing is estimated from invented status values.

## What is collected

| Source | Fields | Cadence | Status |
|---|---|---|---|
| `sweet.paraca.co.jp` (Paraca's monthly-parking search) | lot name, address, lat/lng, listing id, vehicle & contract type, monthly rent, deposit, key money, equipment, size notes, vacancy flag (申込可能 / 空き待ち) | hourly batch, ~50 requests at ≥3 s spacing | ✅ live |
| Paraca IR 決算短信 | revenue, OP, ordinary, NI, revenue & GP by leased/owned, lots & spaces by type, guidance | per release (hand-verified CSV) | ✅ FY2022–FY2026 Q3 |
| Owned-lot opening releases (paraca.co.jp, 2008–) | name, address, spaces, open date, stated owned totals | daily check | ✅ 245 openings |
| 空/混/満 — field checks | status or occupied/total, fee text | hourly read of `data/field_checks.csv` / `FIELD_CSV_URL` | ⏳ ready, see docs/field_check.md |
| 空/混/満 — nearby Times lots | busy/full share of Times lots ≤300 m from Paraca lots | hourly, `TIMES_SNAPSHOTS_URL` | ⏳ ready, needs the Times export URL |
| 空/混/満 — Paraca's own signs | hourly status | — | ⊘ no permitted source (iPosNet licence requested) |

Pilot on 2026-10-20: **460 listings / 376 lots / 30 prefectures from 50 requests, 0 errors, 2.7 minutes.**

## Repository layout

```
paraca/               Python package (collector, storage, exports, financial model)
  sources/sweet.py    portal parser + crawler
  http.py             polite client: min interval, retries, backoff, 403 stop, request cap, cache
  db.py               SQLite schema, change-log ingest, events, closure inference
  normalize.py        yen, statuses, haversine/area matching, stable lot ids, fee-schedule parser
  fiscal.py           September (Paraca) / October (Park24) fiscal quarters
  finmodel.py         standalone quarters, revenue per space-day, 3-model backtest, next-quarter forecast
  export.py           exports/*.csv (cross-operator) + web/*.json (dashboard)
data/financials.csv   hand-verified IR figures, one row per value with source URL and release date
data/pilot/           raw pilot capture (2026-10-20)
web/                  React + TypeScript dashboard (Vite, Recharts, Leaflet) for Cloudflare Pages
tests/                pytest suite (parsers, time zones, fiscal quarters, fees, duplicates, missing data, aggregation)
docs/                 feasibility, methodology, data dictionary
.github/workflows/    collect.yml (hourly) and ci.yml
```

The **`data` branch** is the durable store: `paraca.sqlite`, `exports/*.csv` and `web/*.json`. It is rewritten as a
single rolling commit after each run, so repository history doesn't grow with every snapshot. Each run's database is also
uploaded as a workflow artifact (30-day retention) as a backup.

## Run locally

```bash
pip install -r requirements.txt pytest
python -m pytest -q
python -m paraca.cli collect --db store/paraca.sqlite --prefectures 13     # small pilot (Tokyo)
python -m paraca.cli export  --db store/paraca.sqlite --out store
cd web && npm ci && VITE_DATA_BASE=/store/web/ npm run dev                     # or use the default (GitHub data branch)
```

## Deploy the dashboard (Cloudflare Pages, free)

1. Cloudflare dashboard → **Workers & Pages → Create → Pages → Connect to Git** → choose `Stellarky/paraca-altdata`.
2. Production branch `main`; framework preset **None**; root directory **`web`**; build command **`npm ci && npm run build`**;
   output directory **`dist`**.
3. Deploy. The site reads data at runtime from
   `https://raw.githubusercontent.com/Stellarky/paraca-altdata/data/web/`, so hourly data updates do **not** trigger
   rebuilds (this keeps you far below Cloudflare's 500 builds/month). Rebuilds happen only when you change code on `main`.

Optional: set the env var `VITE_DATA_BASE` in Cloudflare to point at another data location.

## Scheduling & costs

- `collect.yml` runs hourly at :17 UTC (edit the cron to change cadence). GitHub can delay scheduled jobs under load.
- A full run is ~50 requests and ~3 minutes. Public repositories get free, unmetered Actions minutes on standard runners. A
  private repo would use about 24 × 3 = 72 minutes/day (~2,200/month, above the 2,000 free minutes), so keep it public or
  reduce the cadence to every 2 hours.
- `concurrency: collect` prevents overlapping writers; runs that hit errors are recorded as `partial` and never used to
  infer closures. The request cap (`PARACA_MAX_REQUESTS`, default 200) bounds a single run.
- Cloudflare Pages free tier: unlimited bandwidth, 500 builds/month.

## Compliance

- Only public pages; no login, no CAPTCHA, no undocumented APIs. `paraca.pro`, iPosNet and NAVITIME are **not** collected
  (robots.txt disallow / bot blocking).
- Honest User-Agent with contact address; ≥3 s between requests; exponential backoff; honours `Retry-After`; stops on HTTP 401/403.
- The portal's terms (利用規約) contain no scraping clause but forbid burdening the service. Collection is light, and the
  recommended next step is to ask Paraca IR for explicit permission (template in `docs/feasibility.md`).

## Known limitations

- Portal coverage is ~14% of Paraca's ~2,700 operating lots and skewed to Tokyo and Osaka and to lots offering monthly contracts.
- The vacancy flag is binary and slow-moving; it is **not** occupancy (see `docs/methodology.md`).
- No per-lot capacity, so no capacity weighting is possible.
- Financials are non-consolidated JGAAP; some period-end counts are derived or interpolated and flagged.
- Forecasts rest on 6–10 backtest observations; they are indicative only.

Independent research project, not affiliated with Paraca Inc. or Park24 Co., Ltd.
