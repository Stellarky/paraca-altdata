"""Command line entry point.

  python -m paraca.cli collect   --db store/paraca.sqlite [--prefectures 13,27]
  python -m paraca.cli import-pilot data/pilot/paraca_pilot_20261020.json --db store/paraca.sqlite
  python -m paraca.cli export    --db store/paraca.sqlite --out store
"""
from __future__ import annotations

import argparse
import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path

from . import config
from .db import connect, ingest
from .http import PoliteClient, RequestBudgetExceeded
from .normalize import iso, monthly_vacancy, now_utc, parse_coord, parse_yen
from .sources import sweet

log = logging.getLogger("paraca")


def cmd_collect(args) -> int:
    con = connect(Path(args.db))
    started = now_utc()
    run_id = started.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    prefs = [int(p) for p in args.prefectures.split(",")] if args.prefectures else None
    client = PoliteClient(cache_dir=Path(args.cache) if args.cache else None)
    t0, pages, listings, status, note = time.monotonic(), 0, [], "ok", None
    try:
        for pid, page_no, sp in sweet.crawl(client, prefs):
            pages += 1
            listings.extend(sp.listings)
            log.info("pref %02d page %d: %d listings (total %s)", pid, page_no, len(sp.listings), sp.total)
    except (RequestBudgetExceeded, PermissionError, RuntimeError) as e:
        status, note = "partial", str(e)
        log.error("run incomplete: %s", e)
    complete = status == "ok" and prefs is None
    stats = ingest(con, run_id, started, listings, complete=complete)
    con.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?,?)", (run_id, "sweet", iso(started), iso(now_utc()), status,
                client.requests_made, client.errors, pages, len(listings), round(time.monotonic() - t0, 1),
                json.dumps({**stats, "note": note, "complete": complete}, ensure_ascii=False)))
    con.commit()
    log.info("run %s %s: %s", run_id, status, stats)
    return 0 if status == "ok" else 2


def cmd_import_pilot(args) -> int:
    """Load the browser-pane pilot (2026-10-20) captured with the same parsing rules."""
    d = json.loads(Path(args.file).read_text(encoding="utf-8"))
    con = connect(Path(args.db))
    started = datetime.fromisoformat(d["meta"]["started"].replace("Z", "+00:00")).replace(microsecond=0)
    run_id = "pilot-" + started.strftime("%Y%m%dT%H%M%SZ")
    if con.execute("SELECT 1 FROM runs WHERE run_id=?", (run_id,)).fetchone():
        log.info("pilot already imported")
        return 0
    rows = []
    for r in d["rows"]:
        rows.append(sweet.Listing(
            listing_id=str(r["listing_id"]), lot_name=r.get("name"), address=r.get("address"),
            lat=parse_coord(r.get("lat")), lng=parse_coord(r.get("lng")), prefecture_id=int(r["pref_id"]),
            prefecture_name=r.get("pref_name"), monthly_rent_yen=parse_yen(r.get("rent")),
            deposit_yen=parse_yen(r.get("deposit")), key_money_yen=parse_yen(r.get("key_money")),
            vehicle_type=r.get("vehicle"), contract_type=r.get("contract"), equipment=r.get("equipment") or [],
            size_note=None if r.get("size_note") in (None, "—", "") else r["size_note"],
            vacancy_label=r.get("availability") or None, vacancy_status=monthly_vacancy(r.get("availability")),
            source_url=config.SWEET_DETAIL.format(listing_id=r["listing_id"])))
    stats = ingest(con, run_id, started, rows, complete=True)
    fin = datetime.fromisoformat(d["meta"]["finished"].replace("Z", "+00:00")).replace(microsecond=0)
    con.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?,?)", (run_id, "sweet-pilot", iso(started), iso(fin), "ok",
                d["meta"]["requests"], 0, len(d["meta"]["log"]), len(rows), (fin - started).total_seconds(),
                json.dumps({**stats, "note": d["meta"].get("method"), "complete": True}, ensure_ascii=False)))
    con.commit()
    log.info("pilot imported: %s", stats)
    return 0


def cmd_export(args) -> int:
    from .export import export_all
    export_all(Path(args.db), Path(args.out), Path(args.financials))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="paraca")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect"); c.add_argument("--db", required=True); c.add_argument("--prefectures"); c.add_argument("--cache")
    c.set_defaults(fn=cmd_collect)
    i = sub.add_parser("import-pilot"); i.add_argument("file"); i.add_argument("--db", required=True); i.set_defaults(fn=cmd_import_pilot)
    e = sub.add_parser("export"); e.add_argument("--db", required=True); e.add_argument("--out", required=True)
    e.add_argument("--financials", default="data/financials.csv"); e.set_defaults(fn=cmd_export)
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
