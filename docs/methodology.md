# Methodology

## 1. Universe and matching
- **Universe:** every lot listed on Paraca's monthly-parking portal, crawled by prefecture (47 search pages plus extra pages, 50 rows each).
- **Lot identity:** listings sharing a lot block (HTML `rowspan`) belong to one lot. `lot_id` hashes the normalised name
  (NFKC, whitespace removed), address and ~10 m coordinates. Duplicate listing ids within a run are dropped and counted.
- **Openings and closures:** a listing or lot is marked removed only after a *complete* run (all prefectures fetched without
  error) no longer contains it. Partial runs never infer closures. Reappearance is logged.
- **Markets:** the 16 Times reference markets, each a fixed centre and a uniform **2.5 km** radius. A lot belongs to the
  nearest centre whose radius contains it (haversine distance). Markets with zero lots are shown empty. The radius and
  match rule are stored in `paraca/config.py` and exported with each lot (`area_distance_km`).

## 2. Signals

**Monthly open share (observed).**
`open_share = n(open) / (n(open) + n(waitlist))`, over listings in scope. Blank flags are excluded and reported as
`no_vacancy_flag`.

**Busy share, full share, capacity-weighted busy share (defined; not computable for Paraca).**
For hourly snapshot status *s<sub>i</sub>* ∈ {available, crowded, full} of lot *i* with capacity *c<sub>i</sub>*:

- `busy_share = Σ 1[s_i ∈ {crowded, full}] / N_known`
- `full_share = Σ 1[s_i = full] / N_known`
- `capacity_weighted_busy_share = Σ c_i·1[s_i ∈ {crowded, full}] / Σ c_i` (over lots with known status and capacity)
- `estimated_occupancy` (only if explicitly assumed): `Σ c_i·w(s_i) / Σ c_i` with stated weights, e.g. w(available)=a,
  w(crowded)=b, w(full)=1, published with the assumption. **Not used.**
- `status_coverage = N_known / N_lots` accompanies every value.

### Why a categorical signal is not occupancy
1. A status flag is a threshold indicator. "Full" can mean 100% or "above the operator's display threshold". "Available"
   can mean 5% or 85% occupied, so the mean occupancy within each state is unknown and varies by lot.
2. Snapshots sample points in time. Park24 reports **parked-time occupancy** (occupied space-hours ÷ available
   space-hours over a period), which weights long stays and the night-time hours a snapshot panel may miss.
3. Paraca's monthly flag is different again: it says whether *one more monthly contract* can be signed, which depends
   on how many spaces Paraca allocates to monthly use (a business choice) as well as on demand.

So these series are compared by **direction and timing** (does a change lead revenue?), never by level.

## 3. Prices
- Monthly rents are parsed as integers (yen, tax included). "—" or blank → null, never 0.
- Hourly fee texts (for any future permitted source) are stored raw, and a structured view is kept beside them: unit
  prices per time band and day type, and caps with their windows. `hourly_rate_yen` is filled **only** when all unit prices
  imply the same ¥/hour. Otherwise it stays null with the flag `time_or_day_varying_rate`. `daily_cap_yen` is filled only
  for one unambiguous 24-hour or same-day cap. No universal hourly equivalent is invented.

## 4. Storage and time
- UTC is canonical; JST is derived and stored alongside it. Naive datetimes raise errors.
- Snapshot storage is a change log: a row is written when anything changes, and once per JST day as a heartbeat. The
  `runs` table records every run (requests, errors, duration), so "observed, unchanged" is recoverable.

## 5. Official financials and fiscal calendar
- Paraca's FY ends **30 September**; FY*N* runs 1 Oct *N-1* to 30 Sep *N*. Q1 = Oct–Dec … Q4 = Jul–Sep. Park24's FY ends
  31 October, so cross-operator comparisons must align on calendar months, not fiscal quarter labels.
- Standalone quarters = cumulative(Q) − cumulative(Q−1). Q4 = full year − 9-month cumulative.
- Revenue per space-day = standalone revenue ÷ ((opening spaces + closing spaces)/2) ÷ days. The June-2025 space count
  was not disclosed and is linearly interpolated (flagged). FY2022 year-end counts are derived from FY2023 net additions (flagged).
- Unavailable figures are null and labelled; they are never zero.
- Comparability: Paraca is non-consolidated and parking-only. Park24 consolidates mobility (car-sharing) and overseas
  operations. Revenue, margins and occupancy definitions are not directly comparable.

## 6. Forecast lab
Three transparent models, walk-forward, one quarter ahead:

| Model | Formula |
|---|---|
| seasonal naive | R̂(t) = R(t−4) × R(t−1)/R(t−5) |
| space × yield | R̂(t) = S̄(t) × y(t−4) × days(t) |
| space × yield (drift) | R̂(t) = S̄(t) × y(t−4) × y(t−1)/y(t−5) × days(t) |

with *S̄* the average operating spaces and *y* the revenue per space-day. The space models use the quarter's actual space
base, known at quarter end from disclosures (a nowcast). The headline forecast uses the model with the lowest backtest MAPE
(n ≥ 4). The band is ±1.96 × the SD of that model's backtest errors, which is indicative only, given 6–10 observations.
Guidance-implied Q4 = full-year guidance − Q1–Q3 actual.

**Alternative data in the model:** not yet. The monthly-portal series starts on 2026-10-20. The planned test regresses the
quarterly revenue surprise (actual − seasonal naive) on quarterly changes in open share and listing counts, with
walk-forward evaluation, once roughly 8 quarters overlap. Null results will be reported.
