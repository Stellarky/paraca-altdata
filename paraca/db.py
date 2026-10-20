"""SQLite store: lots, listings, snapshots (append-only), change events, runs.

Durability: the SQLite file lives on the repo's `data` branch and is committed
after each GitHub Actions run (runners do not keep files between runs).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

from . import config
from .normalize import assign_area, iso, lot_key, to_jst

SCHEMA = """
PRAGMA journal_mode=DELETE;
CREATE TABLE IF NOT EXISTS runs(
  run_id TEXT PRIMARY KEY, source TEXT, started_utc TEXT, finished_utc TEXT,
  status TEXT, requests INTEGER, errors INTEGER, pages INTEGER, listings_seen INTEGER,
  duration_s REAL, note TEXT);
CREATE TABLE IF NOT EXISTS lots(
  lot_id TEXT PRIMARY KEY, operator TEXT NOT NULL, lot_name TEXT, address TEXT,
  latitude REAL, longitude REAL, prefecture_id INTEGER, prefecture TEXT,
  area_id TEXT, area_distance_km REAL, capacity INTEGER,
  first_seen_utc TEXT, last_seen_utc TEXT, active INTEGER DEFAULT 1,
  source_name TEXT, source_url TEXT);
CREATE TABLE IF NOT EXISTS listings(
  listing_id TEXT PRIMARY KEY, lot_id TEXT REFERENCES lots(lot_id),
  vehicle_type TEXT, contract_type TEXT, equipment TEXT, size_note TEXT,
  first_seen_utc TEXT, last_seen_utc TEXT, active INTEGER DEFAULT 1, source_url TEXT);
CREATE TABLE IF NOT EXISTS listing_snapshots(
  run_id TEXT, listing_id TEXT, lot_id TEXT,
  collection_utc TEXT, collection_jst TEXT,
  monthly_rent_yen INTEGER, deposit_yen INTEGER, key_money_yen INTEGER,
  vacancy_label TEXT, vacancy_status TEXT, data_quality_flag TEXT,
  PRIMARY KEY(run_id, listing_id));
CREATE INDEX IF NOT EXISTS ix_snap_listing ON listing_snapshots(listing_id, collection_utc);
CREATE TABLE IF NOT EXISTS events(
  event_utc TEXT, run_id TEXT, kind TEXT, lot_id TEXT, listing_id TEXT,
  old_value TEXT, new_value TEXT);
CREATE TABLE IF NOT EXISTS owned_releases(
  pdf_url TEXT PRIMARY KEY, release_date TEXT, title TEXT, fetched_utc TEXT, n_lots INTEGER, text TEXT, error TEXT);
CREATE TABLE IF NOT EXISTS owned_lots(
  pdf_url TEXT, seq INTEGER, release_date TEXT, kind TEXT, lot_name TEXT, address TEXT, spaces INTEGER,
  open_date TEXT, latitude REAL, longitude REAL, geo_title TEXT, geo_quality TEXT, flags TEXT, raw TEXT,
  PRIMARY KEY(pdf_url, seq));
CREATE TABLE IF NOT EXISTS osm_lots(
  osm_id TEXT PRIMARY KEY, name TEXT, operator TEXT, latitude REAL, longitude REAL, capacity INTEGER,
  tags TEXT, first_seen_utc TEXT, last_seen_utc TEXT);
-- Hourly coin-parking observations. Empty until a licensed/permitted source exists.
CREATE TABLE IF NOT EXISTS hourly_observations(
  lot_id TEXT, status_timestamp_utc TEXT, collection_utc TEXT, collection_jst TEXT,
  availability_status TEXT CHECK(availability_status IN ('available','crowded','full','unknown')),
  hourly_rate_yen REAL, daily_cap_yen INTEGER, rate_schedule_raw TEXT,
  source_url TEXT, source_name TEXT, freshness_seconds INTEGER, data_quality_flag TEXT,
  PRIMARY KEY(lot_id, collection_utc));
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def _quality(l) -> str:
    flags = []
    if l.lat is None or l.lng is None:
        flags.append("no_coordinates")
    if l.monthly_rent_yen is None:
        flags.append("no_rent")
    if l.vacancy_status == "unknown":
        flags.append("no_vacancy_flag")
    return ",".join(flags) or "ok"


def ingest(con: sqlite3.Connection, run_id: str, collected: datetime, listings: Iterable, complete: bool) -> dict:
    """Upsert one run's listings, append snapshots, and record change events.

    Removals are only inferred when `complete` is True (every prefecture page
    fetched without error) so a partial run never fakes closures.
    """
    ts, ts_jst = iso(collected), iso(to_jst(collected))
    seen_listings, seen_lots, stats = set(), set(), {"new_lots": 0, "new_listings": 0, "changes": 0, "dupes": 0}
    cur = con.cursor()

    def event(kind, lot_id, listing_id=None, old=None, new=None):
        cur.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?)", (ts, run_id, kind, lot_id, listing_id,
                    None if old is None else str(old), None if new is None else str(new)))

    for l in listings:
        if l.listing_id in seen_listings:            # same listing on two pages
            stats["dupes"] += 1
            continue
        seen_listings.add(l.listing_id)
        lid = lot_key(l.lot_name, l.address, l.lat, l.lng)
        if lid not in seen_lots:
            seen_lots.add(lid)
            area_id, dist = assign_area(l.lat, l.lng)
            row = cur.execute("SELECT lot_id, active FROM lots WHERE lot_id=?", (lid,)).fetchone()
            if row is None:
                cur.execute("""INSERT INTO lots(lot_id, operator, lot_name, address, latitude, longitude,
                    prefecture_id, prefecture, area_id, area_distance_km, capacity, first_seen_utc, last_seen_utc,
                    active, source_name, source_url) VALUES(?,?,?,?,?,?,?,?,?,?,NULL,?,?,1,?,?)""",
                    (lid, config.OPERATOR, l.lot_name, l.address, l.lat, l.lng, l.prefecture_id,
                     l.prefecture_name or config.PREFECTURES.get(l.prefecture_id), area_id, dist, ts, ts,
                     config.SWEET_SOURCE_NAME, l.source_url))
                event("lot_new", lid, new=l.lot_name)
                stats["new_lots"] += 1
            else:
                if not row["active"]:
                    event("lot_reappeared", lid)
                cur.execute("UPDATE lots SET last_seen_utc=?, active=1, area_id=?, area_distance_km=? WHERE lot_id=?",
                            (ts, area_id, dist, lid))
        prev = cur.execute("""SELECT monthly_rent_yen, deposit_yen, vacancy_status, collection_jst FROM listing_snapshots
                              WHERE listing_id=? ORDER BY collection_utc DESC LIMIT 1""", (l.listing_id,)).fetchone()
        lrow = cur.execute("SELECT listing_id, active FROM listings WHERE listing_id=?", (l.listing_id,)).fetchone()
        if lrow is None:
            cur.execute("INSERT INTO listings VALUES(?,?,?,?,?,?,?,?,1,?)", (l.listing_id, lid, l.vehicle_type,
                        l.contract_type, json.dumps(l.equipment, ensure_ascii=False), l.size_note, ts, ts, l.source_url))
            if prev is None:
                event("listing_new", lid, l.listing_id, new=l.monthly_rent_yen)
                stats["new_listings"] += 1
        else:
            cur.execute("UPDATE listings SET last_seen_utc=?, active=1, lot_id=? WHERE listing_id=?", (ts, lid, l.listing_id))
        if prev is not None:
            if prev["monthly_rent_yen"] != l.monthly_rent_yen:
                event("rent_change", lid, l.listing_id, prev["monthly_rent_yen"], l.monthly_rent_yen)
                stats["changes"] += 1
            if prev["vacancy_status"] != l.vacancy_status:
                event("vacancy_change", lid, l.listing_id, prev["vacancy_status"], l.vacancy_status)
                stats["changes"] += 1
        # Change-log storage: write a snapshot when anything changed, or as the
        # first observation of the JST day (daily heartbeat). Runs table keeps
        # every run, so "observed and unchanged" is still recoverable.
        unchanged = prev is not None and prev["monthly_rent_yen"] == l.monthly_rent_yen and \
            prev["deposit_yen"] == l.deposit_yen and prev["vacancy_status"] == l.vacancy_status and \
            prev["collection_jst"][:10] == ts_jst[:10]
        if unchanged:
            stats["unchanged"] = stats.get("unchanged", 0) + 1
            continue
        cur.execute("INSERT OR REPLACE INTO listing_snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (run_id, l.listing_id, lid, ts, ts_jst, l.monthly_rent_yen, l.deposit_yen, l.key_money_yen,
                     l.vacancy_label, l.vacancy_status, _quality(l)))
    if complete:
        for r in cur.execute("SELECT listing_id, lot_id FROM listings WHERE active=1").fetchall():
            if r["listing_id"] not in seen_listings:
                cur.execute("UPDATE listings SET active=0 WHERE listing_id=?", (r["listing_id"],))
                event("listing_removed", r["lot_id"], r["listing_id"])
        for r in cur.execute("SELECT lot_id FROM lots WHERE active=1").fetchall():
            if r["lot_id"] not in seen_lots:
                cur.execute("UPDATE lots SET active=0 WHERE lot_id=?", (r["lot_id"],))
                event("lot_removed", r["lot_id"])
    con.commit()
    stats["listings"] = len(seen_listings)
    stats["lots"] = len(seen_lots)
    return stats
