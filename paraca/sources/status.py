"""空車 / 混雑 / 満車 status from sources this project may legitimately use.

1. Field checks  - observations you or the seminar record at Paraca lots
   (data/field_checks.csv in the repo, and/or a published Google Sheet CSV in
   the FIELD_CSV_URL secret). Primary data, owned by the project.
2. Nearby Times  - the Times panel's own cross-operator export
   (parking_snapshots.csv, standard fields) at TIMES_SNAPSHOTS_URL. For every
   Paraca market and lot we compute the busy share of Times lots nearby: a
   measure of local parking traffic, labelled as Times lots, never as Paraca's.
3. Licensed feed - rows written straight into hourly_observations by a future
   iPosNet / Paraca connector (schema already in db.py).
"""
from __future__ import annotations

import csv
import io
import logging
import os
import unicodedata
from datetime import datetime, timedelta, timezone

from .. import config
from ..normalize import JST, assign_area, haversine_km, hourly_status, iso

log = logging.getLogger(__name__)

STATUS_ALIASES = {"空": "available", "空車": "available", "available": "available", "empty": "available",
                  "混": "crowded", "混雑": "crowded", "crowded": "crowded", "nearly full": "crowded",
                  "満": "full", "満車": "full", "full": "full"}
FIELD_COLUMNS = ["observed_at_jst", "observer", "lot_ref", "lot_name", "latitude", "longitude", "operator",
                 "status", "occupied_spaces", "total_spaces", "hourly_fee_text", "notes"]


def norm_status(s: str | None) -> str:
    t = unicodedata.normalize("NFKC", (s or "")).strip().lower()
    return STATUS_ALIASES.get(t, hourly_status(t))


def _rows_from_csv_text(text: str) -> list[dict]:
    return [r for r in csv.DictReader(io.StringIO(text)) if any((v or "").strip() for v in r.values())]


def load_field_rows(repo_csv, client=None) -> list[dict]:
    rows = []
    if repo_csv.exists():
        rows += _rows_from_csv_text(repo_csv.read_text(encoding="utf-8"))
    url = os.environ.get("FIELD_CSV_URL")
    if url and client:
        try:
            rows += _rows_from_csv_text(client.get(url))
        except Exception as e:  # noqa: BLE001
            log.warning("field sheet unavailable: %s", e)
    return rows


def parse_jst(s: str) -> datetime | None:
    s = unicodedata.normalize("NFKC", (s or "")).strip().replace("/", "-")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=JST)
        except ValueError:
            continue
    try:
        d = datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=JST)
    except ValueError:
        return None


def match_lot(row: dict, universe: list[dict]) -> tuple[str | None, float | None, float | None]:
    """Universe id by explicit ref, then nearest known lot within 60 m, then exact name."""
    ref = (row.get("lot_ref") or "").strip()
    if ref:
        for u in universe:
            if u["id"] == ref or ref in u["sources"].values():
                return u["id"], u["lat"], u["lng"]
    try:
        lat, lng = float(row.get("latitude") or ""), float(row.get("longitude") or "")
    except ValueError:
        lat = lng = None
    if lat is not None:
        best = min(universe, key=lambda u: haversine_km(lat, lng, u["lat"], u["lng"]), default=None)
        if best and haversine_km(lat, lng, best["lat"], best["lng"]) <= 0.06:
            return best["id"], lat, lng
    name = unicodedata.normalize("NFKC", row.get("lot_name") or "").replace(" ", "").replace("パラカ", "")
    if name:
        for u in universe:
            if u["name"] and unicodedata.normalize("NFKC", u["name"]).replace(" ", "") == name:
                return u["id"], u["lat"], u["lng"]
    return None, lat, lng


def ingest_field(con, universe: list[dict], rows: list[dict]) -> dict:
    """Store field checks; Paraca rows also go into hourly_observations (source 'field')."""
    con.execute("""CREATE TABLE IF NOT EXISTS field_checks(
        observed_utc TEXT, observer TEXT, universe_id TEXT, lot_name TEXT, latitude REAL, longitude REAL, operator TEXT,
        status TEXT, occupied INTEGER, total INTEGER, fee_text TEXT, notes TEXT, area_id TEXT,
        PRIMARY KEY(observed_utc, lot_name, observer))""")
    ok = bad = 0
    for r in rows:
        t = parse_jst(r.get("observed_at_jst", ""))
        st = norm_status(r.get("status"))
        occ = int(r["occupied_spaces"]) if (r.get("occupied_spaces") or "").strip().isdigit() else None
        tot = int(r["total_spaces"]) if (r.get("total_spaces") or "").strip().isdigit() else None
        if st == "unknown" and occ is not None and tot:
            st = "full" if occ >= tot else ("crowded" if occ / tot >= 0.8 else "available")
        if not t or st == "unknown":
            bad += 1
            continue
        uid, lat, lng = match_lot(r, universe)
        area = assign_area(lat, lng)[0] if lat is not None else None
        op = (r.get("operator") or "paraca").strip().lower() or "paraca"
        ts = iso(t.astimezone(timezone.utc))
        con.execute("INSERT OR REPLACE INTO field_checks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (ts, r.get("observer"), uid, r.get("lot_name"), lat, lng, op, st, occ, tot, r.get("hourly_fee_text"), r.get("notes"), area))
        if op == "paraca" and uid:
            con.execute("""INSERT OR REPLACE INTO hourly_observations VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (uid, ts, ts, iso(t), st, None, None, r.get("hourly_fee_text"), None, "field check", 0, "field_observation"))
        ok += 1
    con.commit()
    return {"field_rows": ok, "field_rejected": bad}


# ------------------------------------------------------------------ nearby Times lots
def ingest_times(con, client, url: str | None = None, days: int = 14) -> dict:
    """Load the Times panel's standard snapshot export and keep the last `days` days."""
    url = url or os.environ.get("TIMES_SNAPSHOTS_URL")
    if not url:
        return {"times": "not_configured"}
    con.execute("""CREATE TABLE IF NOT EXISTS times_snapshots(
        lot_id TEXT, timestamp_utc TEXT, latitude REAL, longitude REAL, capacity INTEGER, status TEXT,
        PRIMARY KEY(lot_id, timestamp_utc))""")
    text = client.get(url)
    cut = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    n = 0
    for r in csv.DictReader(io.StringIO(text)):
        ts = r.get("timestamp_utc") or ""
        if ts < cut:
            continue
        try:
            lat, lng = float(r["latitude"]), float(r["longitude"])
        except (KeyError, ValueError):
            continue
        cap = int(float(r["capacity"])) if (r.get("capacity") or "").replace(".", "").isdigit() else None
        con.execute("INSERT OR REPLACE INTO times_snapshots VALUES(?,?,?,?,?,?)",
                    (r.get("lot_id"), ts, lat, lng, cap, norm_status(r.get("availability_status"))))
        n += 1
    con.execute("DELETE FROM times_snapshots WHERE timestamp_utc < ?", (cut,))
    con.commit()
    return {"times_rows": n}


def busy(rows: list[tuple]) -> tuple[float | None, float | None, int]:
    """Capacity-weighted busy (混+満) and full (満) share; rows = (status, capacity)."""
    k = [(s, c or 1) for s, c in rows if s in ("available", "crowded", "full")]
    tot = sum(c for _, c in k)
    if not tot:
        return None, None, 0
    return (round(sum(c for s, c in k if s in ("crowded", "full")) / tot, 4),
            round(sum(c for s, c in k if s == "full") / tot, 4), len(k))


def status_panel(con, universe: list[dict], nearby_m: float = 300) -> dict:
    """Area-level 空/混/満 metrics from field checks and nearby Times lots."""
    out: dict = {"field": None, "times": None}
    tabs = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "field_checks" in tabs and con.execute("SELECT COUNT(*) FROM field_checks").fetchone()[0]:
        rows = [dict(r) for r in con.execute("SELECT * FROM field_checks ORDER BY observed_utc DESC")]
        by_area: dict = {}
        for r in rows:
            by_area.setdefault(r["area_id"] or "other", []).append((r["status"], r["total"]))
        heat: dict = {}
        for r in rows:
            t = datetime.fromisoformat(r["observed_utc"]).astimezone(JST)
            heat.setdefault((t.weekday(), t.hour), []).append((r["status"], r["total"]))
        out["field"] = {"checks": len(rows), "lots": len({r["universe_id"] or r["lot_name"] for r in rows}),
                        "observers": len({r["observer"] for r in rows if r["observer"]}),
                        "latest": rows[0]["observed_utc"], "recent": rows[:100],
                        "by_area": {a: dict(zip(("busy", "full", "n"), busy(v))) for a, v in by_area.items()},
                        "heat": [{"dow": k[0], "hour": k[1], "busy": busy(v)[0], "n": len(v)} for k, v in heat.items()],
                        "occupancy": round(sum(r["occupied"] for r in rows if r["occupied"] is not None and r["total"]) /
                                           max(1, sum(r["total"] for r in rows if r["occupied"] is not None and r["total"])), 4)
                                     if any(r["occupied"] is not None and r["total"] for r in rows) else None}
    if "times_snapshots" in tabs and con.execute("SELECT COUNT(*) FROM times_snapshots").fetchone()[0]:
        tlots = {r[0]: (r[1], r[2]) for r in con.execute("SELECT lot_id, AVG(latitude), AVG(longitude) FROM times_snapshots GROUP BY lot_id")}
        # Times lots within `nearby_m` of any known Paraca lot, per market
        near: dict = {}
        for tid, (la, ln) in tlots.items():
            for u in universe:
                if abs(u["lat"] - la) < 0.005 and abs(u["lng"] - ln) < 0.006 and haversine_km(la, ln, u["lat"], u["lng"]) * 1000 <= nearby_m:
                    near[tid] = u["area"] or "other"
                    break
        series: dict = {}
        latest: dict = {}
        for tid, ts, st, cap in con.execute("SELECT lot_id, timestamp_utc, status, capacity FROM times_snapshots ORDER BY timestamp_utc"):
            if tid not in near:
                continue
            series.setdefault((near[tid], ts), []).append((st, cap))
            series.setdefault(("all", ts), []).append((st, cap))
        for (a, ts), v in series.items():
            latest[a] = ts
        areas = sorted({a for a, _ in series})
        out["times"] = {"nearby_m": nearby_m, "times_lots_near_paraca": len(near),
                        "areas": {a: {"series": [{"t": ts, "busy": busy(v)[0], "full": busy(v)[1], "n": busy(v)[2]}
                                                 for (aa, ts), v in sorted(series.items()) if aa == a][-200:]} for a in areas}}
    return out
