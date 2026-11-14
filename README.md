# data branch (machine-written)

Rolling single-commit branch rewritten by the `collect` GitHub Action after every run.

- `paraca.sqlite` — durable store (lots, listings, change-log snapshots, events, runs)
- `exports/` — cross-operator CSVs (see docs/data_dictionary.md on `main`)
- `web/` — JSON consumed by the dashboard

Do not edit by hand. Backups of each run's database are kept as workflow artifacts.
