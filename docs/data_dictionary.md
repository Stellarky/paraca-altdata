# Data dictionary

All timestamps are ISO-8601 with an explicit offset. `*_utc` is UTC, and `*_jst` is Asia/Tokyo (+09:00). Unknown values are
empty or `null`, **never 0**.

## Cross-operator standard fields (shared with the Times/Park24 project)

| Field | Type | Definition |
|---|---|---|
| `operator` | text | `paraca` (the Park24 project uses `park24`) |
| `lot_id` | text | Stable id: `paraca-` + SHA-1 of normalised name, address and coordinates rounded to ~10 m |
| `timestamp_utc` / `timestamp_jst` | datetime | Collection time of the observation |
| `area_id` | text | Matched market (see `paraca/config.py`), or empty if outside every radius |
| `latitude`, `longitude` | float | WGS84, from the portal's map button |
| `capacity` | int | Spaces per lot. **Not published** by the Paraca portal: always empty |
| `availability_status` | enum | Hourly status: `available`, `crowded`, `full`, `unknown`. Always `unknown` for Paraca today |
| `hourly_rate_yen` | float | Only when a single uniform unit price exists; empty when prices vary by time or day |
| `daily_cap_yen` | int | Only an unambiguous 24h / same-day cap |
| `source_url` | text | Page the value was read from |
| `status_coverage` | float | Share of lots in the row's scope with a known hourly status (0–1) |
| `quality_flag` | text | `ok` or comma-separated flags (`no_coordinates`, `no_rent`, `no_vacancy_flag`, `hourly_status_unavailable`) |

## exports/parking_lots.csv
One row per lot ever seen. Adds `lot_name`, `address`, `prefecture`, `area_distance_km`, `first_seen_utc`, `last_seen_utc`,
`active` (0 once absent from a *complete* run), `source_name`.

## exports/parking_snapshots.csv
Change-log snapshots of each **listing** (one lot can have several: car, bike, pass…). A row is written when rent, deposit or
vacancy changes, plus a heartbeat on the first run of each JST day. The standard fields are joined with Paraca-specific ones:

| Field | Definition |
|---|---|
| `listing_id` | Portal detail id (`/parking/detail/{id}`) |
| `monthly_vacancy_status` | `open` (申込可能), `waitlist` (空き待ち), `unknown` (blank cell) |
| `monthly_rent_yen` | Monthly rent, tax included |
| `vehicle_type` | 自動車 / バイク / 自転車 |
| `contract_type` | 月極 / 全日パス / 平日パス |

## exports/area_daily_metrics.csv
One row per JST date × `area_id` (`national` + each matched market), using each listing's latest state that day.

| Field | Definition |
|---|---|
| `lots`, `listings`, `car_monthly_listings` | Counts of active units |
| `monthly_open_share` | open ÷ (open + waitlist), all listings |
| `car_monthly_open_share` | Same, car / 月極 only |
| `median_car_monthly_rent_yen` | Median rent, car / 月極 |
| `busy_share`, `full_share`, `capacity_weighted_busy_share`, `estimated_occupancy` | Defined in methodology.md; empty for Paraca (no hourly status) |

## exports/financials.csv
Long format, one value per row: `fiscal_year` (labelled by the year it ends; FY ends `09-30`), `period` (`Q1`, `H1`, `Q3`, `FY`
cumulative, or `Q1`–`Q4` standalone), `period_start`, `period_end`, `kind` (`actual`, `guidance_initial`,
`guidance_revised`), `metric`, `value`, `unit` (`JPY_mn` or `count`), `basis` (`cumulative`, `standalone_quarter`,
`period_end`), `source_url`, `release_date`, `derived` (1 = computed rather than read directly), `note`.

Metrics: `revenue`, `operating_profit`, `ordinary_profit`, `net_income`, `revenue_leased`, `revenue_owned`, `revenue_other`,
`gross_profit_leased`, `gross_profit_owned`, `lots_leased`, `spaces_leased`, `lots_owned`, `spaces_owned`, `lots_total`, `spaces_total`.

## SQLite (`paraca.sqlite` on the data branch)
`runs` (every collection run, including failures, with request counts and duration), `lots`, `listings`,
`listing_snapshots`, `events` (`lot_new`, `listing_new`, `rent_change`, `vacancy_change`, `listing_removed`, `lot_removed`,
`lot_reappeared`), `hourly_observations` (empty; ready for a permitted hourly source, with `rate_schedule_raw`,
`freshness_seconds`, `status_timestamp_utc`).
