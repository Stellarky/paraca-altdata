# Paraca (4809) Alternative-Data Feasibility Assessment

*Checked 19 Oct 2026 (JST). Phase 1 deliverable. Each finding names its source and how it was verified.*

## Bottom line

**Real-time hourly-lot availability for Paraca cannot currently be collected reliably and compliantly.** Paraca runs no public hourly (時間貸) lot search of its own. The third-party sites that list Paraca hourly lots either forbid automated access (iPosNet, NAVITIME, paraca.pro) or show no live status for the Paraca lots sampled. So the Times-style "busy share / full share" panel **cannot be replicated for Paraca from public data today.**

Two things *can* be built with real data:

1. **Paraca's own monthly-parking portal (sweet.paraca.co.jp)**: a first-party list of monthly (月極) and pass-card listings, with rent, deposit, facility type and a per-listing **vacancy flag (申込可能 / 空き待ち)**. Tracked over time, this gives a genuine, if narrow, demand-tightness signal for Paraca's monthly inventory. **It does not measure the hourly business.**
2. **Official IR**: fiscal-year/quarter financials, segment revenue (賃借 / 保有 / その他), lot and space counts where disclosed, and monthly owned-lot opening press releases (保有駐車場オープンのお知らせ).

## Source-by-source findings

| Source | What it offers | Access rules | Verdict |
|---|---|---|---|
| **paraca.co.jp** (corporate) | IR, news, owned-lot opening PDFs. **No hourly lot search.** | robots.txt allows all except `/mg/wp-admin/`. | ✅ Use for IR and lot-opening events |
| **sweet.paraca.co.jp** (月極 search) | Monthly/pass listings by prefecture (Tokyo: 120 listings, 10/25/50 per page). Fields: lot name, address, rent (tax incl.), deposit, key money, vehicle type, contract type, facility, size limits, **vacancy (申込可能 / 空き待ち)**. Detail page `/parking/detail/{id}` has an embedded map (coordinates likely in page script, still to confirm). No timestamps. | No real robots.txt (path redirects to login page). Pages are `noindex,nofollow` (a search-engine indexing directive, not an access ban). Terms (利用規約) contain **no explicit scraping ban**, but do bar acts that burden servers or disrupt operations (第5条(3)(4)) and include a catch-all for "acts the company deems inappropriate" (5条(8)). | ⚠️ **Usable with care**: low rate (≥3 s between requests), once-daily cadence, public pages only, honest User-Agent with contact. Stop if asked. Asking Paraca IR for permission is recommended. |
| **paraca.pro/car, /bus**, **paraca.biz** (reservations) | Reservation-only lots | **robots.txt disallows automated access** | ❌ Do not collect |
| **iPosNet** (search.ipos-land.jp) | Lists *some* Paraca hourly lots with hourly fees, caps, capacity and a 満車/空車 field. A sample Paraca lot page (Morioka) states "2020年12月 更新", so static fields may be years old. | **robots.txt disallows automated access** | ❌ Do not collect. Manual spot checks only. A data licence from Nisshin Electronics Service (the operator) would be the legitimate route. |
| **NAVITIME parking** | Lists Paraca hourly lots with capacity. Sampled Paraca lots (Chofu, Kanazawa, Kochi) show **満空情報 "--"** (no live status), while nearby Times lots do show status. | Blocks automated requests (bot detection) | ❌ Do not collect; also no Paraca status to collect |
| Consumer parking apps (e.g. App Store "駐車場・検索"; lists Paraca as covered) | A generic "real-time" claim; per-lot Paraca coverage not established | App-only / undocumented APIs | ❌ Out of scope (undocumented endpoints) |
| OpenStreetMap (Overpass) | Possibly some lots tagged operator=パラカ | Open licence (ODbL) | ❓ Not verifiable from this environment (host blocked by proxy). Worth a test from GitHub Actions; coverage likely sparse. |

## Field coverage

| Field | Monthly portal | IR | Hourly lots (any compliant source) |
|---|---|---|---|
| lot name / address | ✅ high | — | ❌ |
| lat / lng | ⚠️ probable (map embed), unconfirmed | — | ❌ |
| capacity (spaces) | ❌ not shown per listing | ✅ company totals, where disclosed | ❌ |
| availability status | ⚠️ monthly vacancy only (2 states) | — | ❌ **unavailable** |
| status timestamp | ❌ (use collection time) | — | ❌ |
| hourly rate / daily cap | ❌ (monthly rent instead) | — | ❌ |
| update frequency | changes on contract events; daily snapshot is enough | quarterly | — |

## Other constraints found

- **This build environment cannot reach paraca.co.jp.** The egress proxy blocks it, so I can't run a live pilot collection from here. Collection has to run on **your GitHub Actions** (or your machine), and the scraper's parsing will be written against the page structure seen above and verified on the first live run.
- **Paraca's revenue mix (FY2025/9, per kabuyoho):** leased lots ¥14.09bn (79.9%), owned ¥2.91bn (16.5%), other ¥0.63bn (3.6%), total ¥17.63bn. Almost all of it is hourly parking, so a monthly-only signal covers a small slice of what drives earnings. This has to be stated clearly in any forecasting claim.

## Recommended plan (strongest feasible version)

1. **Collector**: a Python ETL for sweet.paraca.co.jp, run once daily, at ≥3 s/request, with retries, caching, logging, stable `lot_id` = portal detail ID, and change history (new listings, removals, rent changes, vacancy flips). Hourly-only fields stay `NULL` with `quality_flag = not_available_from_source`; nothing is imputed.
2. **IR module**: hand-verified CSV of annual/quarterly results from 決算短信 with source URLs and release dates; fiscal periods stored explicitly (FY ends Sep 30). Plus a parser for the monthly 保有駐車場オープン PDFs as a lot-growth series.
3. **Storage**: SQLite committed to a `data` branch of your repo on each run (durable; GitHub Actions runners don't keep files), plus CSV exports in the standard cross-operator schema.
4. **Dashboard** (React/TS, Cloudflare Pages): Overview, monthly-vacancy market cards, rent explorer + map, lot explorer, quality diagnostics, Official IR, and a Forecast lab that starts as "insufficient history". The utilization, busy-share and revenue-proxy sections ship **greyed out with the reason shown**.
5. **Geographic matching**: the 16 Times markets with fixed centers and radius, showing only markets where real Paraca listings are found. Most will likely be thin, since the monthly inventory is concentrated in large facility car parks.
6. **Upgrade path** (outside this build): ask Paraca IR for data access, or license iPosNet data. The schema already has slots for hourly status if either comes through.
