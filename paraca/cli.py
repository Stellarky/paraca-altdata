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


def _last_ok(con, source: str):
    r = con.execute("SELECT started_utc FROM runs WHERE source=? AND status='ok' ORDER BY started_utc DESC LIMIT 1", (source,)).fetchone()
    return datetime.fromisoformat(r[0]) if r else None


def _record(con, source, started, status, client, pages, n, note):
    run_id = started.strftime("%Y%m%dT%H%M%SZ") + "-" + source
    con.execute("INSERT OR REPLACE INTO runs VALUES(?,?,?,?,?,?,?,?,?,?,?)", (run_id, source, iso(started), iso(now_utc()), status,
                client.requests_made, client.errors, pages, n, (now_utc() - started).total_seconds(), json.dumps(note, ensure_ascii=False)))
    con.commit()


def _geocode_cached(con, client, address, allow_network):
    from .sources import owned
    r = con.execute("SELECT latitude, longitude, title, quality FROM geocode_cache WHERE address=?", (address,)).fetchone()
    if r and r[3] not in ("error",):
        return r[0], r[1], r[2], r[3]
    if not allow_network:
        return None, None, None, "not_geocoded"
    lat, lng, title, q = owned.geocode(client, address)
    if q != "error":
        con.execute("INSERT OR REPLACE INTO geocode_cache VALUES(?,?,?,?,?,?,?)", (address, lat, lng, title, q, "gsi", iso(now_utc())))
    return lat, lng, title, q


def _store_release(con, client, url, release_date, title, text, err, allow_geocode):
    from .sources import owned
    lots = owned.parse_release_text(text, release_date) if text else []
    tl, ts = owned.parse_totals(text) if text else (None, None)
    con.execute("""INSERT OR REPLACE INTO owned_releases(pdf_url, release_date, title, fetched_utc, n_lots, text, error,
                   owned_total_lots, owned_total_spaces) VALUES(?,?,?,?,?,?,?,?,?)""",
                (url, release_date, title, iso(now_utc()), len(lots), text, err, tl, ts))
    con.execute("DELETE FROM owned_lots WHERE pdf_url=?", (url,))
    for i, l in enumerate(lots):
        lat, lng, gt, q = _geocode_cached(con, client, l.address, allow_geocode)
        con.execute("INSERT INTO owned_lots VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (url, i, release_date, l.kind, l.lot_name, l.address, l.spaces, l.open_date,
                     lat, lng, gt, q, ",".join(l.flags), l.raw))
    con.commit()
    return len(lots)


def cmd_owned(args) -> int:
    """Owned-lot opening releases: full backfill once, then page 1 every `--every-hours`.
    --reparse re-reads stored PDF text with the current parser (no downloads)."""
    from .sources import owned
    con = connect(Path(args.db))
    client = PoliteClient(max_requests=args.max_requests)
    started = now_utc()
    # seed the geocode cache from earlier rows so re-parsing never re-geocodes known addresses
    con.execute("""INSERT OR IGNORE INTO geocode_cache SELECT address, latitude, longitude, geo_title, geo_quality, 'gsi', ?
                   FROM owned_lots WHERE latitude IS NOT NULL""", (iso(started),))
    if args.reparse or _parser_version(con) != owned.PARSER_VERSION:
        n_lots = 0
        for url, rd, title, text, err in con.execute("SELECT pdf_url, release_date, title, text, error FROM owned_releases").fetchall():
            n_lots += _store_release(con, client, url, rd, title, text, err, not args.no_geocode)
        con.execute("INSERT OR REPLACE INTO meta VALUES('owned_parser_version', ?)", (owned.PARSER_VERSION,))
        con.commit()
        log.info("re-parsed stored releases: %d lots", n_lots)
    last = _last_ok(con, "owned_pr")
    if last and not args.force and (started - last).total_seconds() < args.every_hours * 3600:
        log.info("owned_pr fresh (last %s); skipping download", last)
        return 0
    status, note, new_pdfs, new_lots = "ok", {}, 0, 0
    try:
        known = {r[0] for r in con.execute("SELECT pdf_url FROM owned_releases WHERE error IS NULL")}
        rels = owned.crawl_releases(client, max_pages=None if (not known or args.full) else 1)
        for rel in rels:
            if rel.url in known:
                continue
            try:
                text, err = owned.pdf_text(client.get_bytes(rel.url)), None
            except (RequestBudgetExceeded, PermissionError):
                raise
            except Exception as e:  # noqa: BLE001  keep going; record the error
                text, err = "", str(e)[:300]
            k = _store_release(con, client, rel.url, rel.release_date, rel.title, text, err, not args.no_geocode)
            new_pdfs += 1
            new_lots += k
            log.info("release %s %s: %d lots%s", rel.release_date, rel.url.rsplit('/', 1)[-1], k, f" ERROR {err}" if err else "")
        note = {"releases_seen": len(rels), "new_pdfs": new_pdfs, "new_lots": new_lots}
    except (RequestBudgetExceeded, PermissionError, RuntimeError) as e:
        status, note = "partial", {"error": str(e), "new_pdfs": new_pdfs, "new_lots": new_lots}
        log.error("owned_pr incomplete: %s", e)
    _record(con, "owned_pr", started, status, client, 0, new_lots, note)
    return 0


def _parser_version(con):
    r = con.execute("SELECT value FROM meta WHERE key='owned_parser_version'").fetchone()
    return r[0] if r else None


def cmd_osm(args) -> int:
    from .sources import osm
    con = connect(Path(args.db))
    last = _last_ok(con, "osm")
    started = now_utc()
    if last and not args.force and (started - last).total_seconds() < args.every_hours * 3600:
        log.info("osm fresh (last %s); skipping", last)
        return 0
    client = PoliteClient(max_requests=3)
    try:
        rows = osm.fetch(client)
        ts = iso(started)
        for r in rows:
            con.execute("""INSERT INTO osm_lots VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(osm_id) DO UPDATE SET
                name=excluded.name, operator=excluded.operator, latitude=excluded.latitude, longitude=excluded.longitude,
                capacity=excluded.capacity, tags=excluded.tags, last_seen_utc=excluded.last_seen_utc""",
                (r["osm_id"], r["name"], r["operator"], r["lat"], r["lng"], r["capacity"], r["tags"], ts, ts))
        _record(con, "osm", started, "ok", client, 1, len(rows), {"elements": len(rows)})
        log.info("osm: %d elements", len(rows))
    except Exception as e:  # noqa: BLE001
        _record(con, "osm", started, "failed", client, 1, 0, {"error": str(e)[:300]})
        log.error("osm failed: %s", e)
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
    o = sub.add_parser("owned"); o.add_argument("--db", required=True); o.add_argument("--every-hours", type=float, default=24)
    o.add_argument("--full", action="store_true"); o.add_argument("--force", action="store_true"); o.add_argument("--no-geocode", action="store_true")
    o.add_argument("--reparse", action="store_true")
    o.add_argument("--max-requests", type=int, default=900); o.set_defaults(fn=cmd_owned)
    m = sub.add_parser("osm"); m.add_argument("--db", required=True); m.add_argument("--every-hours", type=float, default=168)
    m.add_argument("--force", action="store_true"); m.set_defaults(fn=cmd_osm)
    e = sub.add_parser("export"); e.add_argument("--db", required=True); e.add_argument("--out", required=True)
    e.add_argument("--financials", default="data/financials.csv"); e.set_defaults(fn=cmd_export)
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
