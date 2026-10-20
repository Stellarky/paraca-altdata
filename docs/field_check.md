# Field checks: 空 / 混 / 満 at Paraca lots

Paraca's lot signs show 空車 / 混雑 / 満車, but no permitted source publishes them online. Field checks are
the project's own primary data: a person at the lot records what the sign (or the lot) shows. Every hourly
collection run reads them, and the dashboard's "Parking traffic" section switches on automatically.

## Option A: Google Form (recommended for a group)

1. Create a Google Form with these questions, using exactly these titles:

   | Question title | Type | Notes |
   |---|---|---|
   | `observed_at_jst` | Short answer | `2026-10-24 12:30` (or leave it and use the form's Timestamp, see step 3) |
   | `observer` | Short answer | initials |
   | `lot_name` | Short answer | as on the sign, e.g. `パラカ新潟市西堀第12` |
   | `latitude`, `longitude` | Short answer | optional; long-press the spot in Google Maps and copy the numbers |
   | `operator` | Dropdown | `paraca`, `times`, `other` (checking a neighbouring Times lot is useful too) |
   | `status` | Multiple choice | `空`, `混`, `満` |
   | `occupied_spaces`, `total_spaces` | Short answer | optional, but much richer than three levels |
   | `hourly_fee_text` | Paragraph | the tariff sign, e.g. `8:00-20:00 20分200円 最大1,200円` |
   | `notes` | Paragraph | anything unusual (event, construction, closure) |

2. Responses → link to a Google Sheet.
3. In the sheet, rename the `Timestamp` column to `observed_at_jst` if you did not ask for the time.
4. File → Share → **Publish to web** → choose the response sheet, format **CSV** → Publish. Copy the URL.
5. On GitHub: repo **Settings → Secrets and variables → Actions → New repository secret**:
   name `FIELD_CSV_URL`, value = that URL. (A secret, so the sheet address is not public.)

Only lot-level facts go in the sheet: no names of drivers, no number plates, no photos of people.

## Option B: edit the CSV in the repo

Add rows to `data/field_checks.csv` (same columns) directly on GitHub and commit.

## How the rows are used

- A row is matched to a known Paraca lot by `lot_ref` (the lot id from the dashboard), else by
  coordinates within 60 m, else by exact name. Unmatched rows are kept and shown, but not counted per lot.
- `occupied_spaces / total_spaces` without a status is converted: 100% = 満, ≥80% = 混, else 空.
- Busy share = spaces at lots shown 混 or 満, divided by spaces at checked lots (capacity-weighted when
  `total_spaces` is given), the same definition the Times panel uses.
- Paraca rows also go into `hourly_observations` with `source_name = "field check"`, the same table a licensed
  feed would fill, so every downstream metric works unchanged.

## A useful protocol

Pick 10–20 Paraca lots in one market (the dashboard's lot map lists them) and walk the same route at fixed
times, for example weekdays 12:00 and 19:00 and Saturdays 14:00, for four weeks. Record the nearest Times
lot as well: matched pairs let you calibrate Paraca against the Times panel's automated readings.
