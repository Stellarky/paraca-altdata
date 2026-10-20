"""Exports: cross-operator CSVs (exports/) and dashboard JSON (web/).

Cross-operator standard fields: operator, lot_id, timestamp_utc, timestamp_jst,
area_id, latitude, longitude, capacity, availability_status, hourly_rate_yen,
daily_cap_yen, source_url, status_coverage, quality_flag.
"""
from __future__ import annotations

import csv
import json
import sqlite3
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config, finmodel
from .normalize import JST

HOURLY_UNAVAILABLE_REASON = (
    "No compliant source publishes real-time availability for Paraca hourly (coin) lots: "
    "Paraca runs no public hourly-lot search; iPosNet and paraca.pro disallow automated access "
    "in robots.txt; NAVITIME blocks bots and shows no live status for sampled Paraca lots. "
    "See docs/feasibility.md. These metrics switch on automatically once hourly_observations has rows."
)


def _w(path: Path, rows: list[dict], cols: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _j(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str), encoding="utf-8")


def _median(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def _open_share(statuses):
    known = [s for s in statuses if s in ("open", "waitlist")]
    return round(sum(s == "open" for s in known) / len(known), 4) if known else None


def export_all(db: Path, out: Path, fin_csv: Path) -> None:
    from .db import connect
    con = connect(db)                     # ensures every table exists
    now = datetime.now(timezone.utc).replace(microsecond=0)
    lots = [dict(r) for r in con.execute("SELECT * FROM lots ORDER BY prefecture_id, lot_name")]
    listings = {r["listing_id"]: dict(r) for r in con.execute("SELECT * FROM listings")}
    snaps = [dict(r) for r in con.execute("SELECT * FROM listing_snapshots ORDER BY collection_utc")]
    runs = [dict(r) for r in con.execute("SELECT * FROM runs ORDER BY started_utc")]
    events = [dict(r) for r in con.execute("SELECT * FROM events ORDER BY event_utc DESC LIMIT 2000")]
    hourly_n = con.execute("SELECT COUNT(*) FROM hourly_observations").fetchone()[0]
    lot_by_id = {l["lot_id"]: l for l in lots}

    latest: dict[str, dict] = {}
    for s in snaps:
        latest[s["listing_id"]] = s

    # ---------------------------------------------------------------- CSV exports
    _w(out / "exports/parking_lots.csv", [dict(l, operator=config.OPERATOR, status_coverage=0.0,
       quality_flag="ok" if l["latitude"] else "no_coordinates") for l in lots],
       ["operator", "lot_id", "lot_name", "address", "latitude", "longitude", "prefecture", "area_id", "area_distance_km",
        "capacity", "first_seen_utc", "last_seen_utc", "active", "source_name", "source_url", "status_coverage", "quality_flag"])

    snap_rows = []
    for s in snaps:
        l, li = lot_by_id.get(s["lot_id"], {}), listings.get(s["listing_id"], {})
        snap_rows.append({"operator": config.OPERATOR, "lot_id": s["lot_id"], "listing_id": s["listing_id"],
            "timestamp_utc": s["collection_utc"], "timestamp_jst": s["collection_jst"], "area_id": l.get("area_id"),
            "latitude": l.get("latitude"), "longitude": l.get("longitude"), "capacity": None,
            "availability_status": "unknown", "hourly_rate_yen": None, "daily_cap_yen": None,
            "monthly_vacancy_status": s["vacancy_status"], "monthly_rent_yen": s["monthly_rent_yen"],
            "vehicle_type": li.get("vehicle_type"), "contract_type": li.get("contract_type"),
            "source_url": li.get("source_url"), "status_coverage": 0.0, "quality_flag": s["data_quality_flag"]})
    _w(out / "exports/parking_snapshots.csv", snap_rows, list(snap_rows[0]) if snap_rows else ["operator"])

    # area daily metrics: state as of the last snapshot on or before each JST day
    days = sorted({s["collection_jst"][:10] for s in snaps})
    state: dict[str, dict] = {}
    per_day_state = {}
    it = iter(snaps)
    pending = next(it, None)
    for d in days:
        while pending and pending["collection_jst"][:10] <= d:
            state[pending["listing_id"]] = pending
            pending = next(it, None)
        per_day_state[d] = {k: v for k, v in state.items() if listings.get(k, {}).get("first_seen_utc", "") <= d + "T23:59:59+09:00"}
    area_rows = []
    groups = {"national": lambda l: True}
    for a in config.AREAS:
        groups[a.area_id] = (lambda aid: (lambda l: l.get("area_id") == aid))(a.area_id)
    for d, st in per_day_state.items():
        active = {k: v for k, v in st.items() if listings.get(k, {}).get("active") or listings[k]["last_seen_utc"][:10] >= d}
        for gid, pred in groups.items():
            sel = [v for v in active.values() if pred(lot_by_id.get(v["lot_id"], {}))]
            car = [v for v in sel if listings[v["listing_id"]]["vehicle_type"] == "自動車" and listings[v["listing_id"]]["contract_type"] == "月極"]
            area_rows.append({"date_jst": d, "operator": config.OPERATOR, "area_id": gid, "lots": len({v["lot_id"] for v in sel}),
                "listings": len(sel), "car_monthly_listings": len(car), "monthly_open_share": _open_share([v["vacancy_status"] for v in sel]),
                "car_monthly_open_share": _open_share([v["vacancy_status"] for v in car]),
                "median_car_monthly_rent_yen": _median([v["monthly_rent_yen"] for v in car]),
                "capacity": None, "busy_share": None, "full_share": None, "capacity_weighted_busy_share": None,
                "estimated_occupancy": None, "status_coverage": 0.0,
                "quality_flag": "hourly_status_unavailable" if hourly_n == 0 else "ok"})
    _w(out / "exports/area_daily_metrics.csv", area_rows, list(area_rows[0]) if area_rows else ["date_jst"])

    fin_rows = finmodel.load(fin_csv)
    qs = finmodel.standalone_quarters(fin_rows)
    fin_export = [dict(r, operator=config.OPERATOR, fiscal_year_end="09-30") for r in fin_rows]
    for q in qs:
        for m in finmodel.FLOW:
            if q.get(m) is not None:
                fin_export.append({"operator": config.OPERATOR, "fiscal_year_end": "09-30", "fiscal_year": q["fy"], "period": f"Q{q['q']}",
                    "period_start": q["start"], "period_end": q["end"], "kind": "actual", "metric": m, "value": q[m], "unit": "JPY_mn",
                    "basis": "standalone_quarter", "source_url": q["source_url"], "release_date": q["release_date"], "derived": 1,
                    "note": "derived: cumulative minus previous cumulative"})
    _w(out / "exports/financials.csv", fin_export, ["operator", "fiscal_year_end", "fiscal_year", "period", "period_start", "period_end",
        "kind", "metric", "value", "unit", "basis", "source_url", "release_date", "derived", "note"])

    # ---------------------------------------------------------------- web JSON
    web = out / "web"
    last_run = runs[-1] if runs else None
    ok_runs = [r for r in runs if r["status"] == "ok"]
    active_lots = [l for l in lots if l["active"]]
    act_listings = [li for li in listings.values() if li["active"]]
    lot_cards = []
    for l in active_lots:
        ls = [dict(li, **{k: latest[li["listing_id"]][k] for k in ("monthly_rent_yen", "deposit_yen", "key_money_yen", "vacancy_status",
              "vacancy_label", "collection_utc")}) for li in act_listings if li["lot_id"] == l["lot_id"] and li["listing_id"] in latest]
        lot_cards.append({"id": l["lot_id"], "name": l["lot_name"], "addr": l["address"], "lat": l["latitude"], "lng": l["longitude"],
            "pref": l["prefecture"], "area": l["area_id"], "dist": l["area_distance_km"], "first": l["first_seen_utc"], "last": l["last_seen_utc"],
            "listings": [{"id": x["listing_id"], "veh": x["vehicle_type"], "ct": x["contract_type"], "eq": json.loads(x["equipment"] or "[]"),
                          "note": x["size_note"], "rent": x["monthly_rent_yen"], "dep": x["deposit_yen"], "key": x["key_money_yen"],
                          "vac": x["vacancy_status"], "url": x["source_url"], "seen": x["collection_utc"]} for x in ls]})
    _j(web / "lots.json", lot_cards)

    nat = [r for r in area_rows if r["area_id"] == "national"]
    area_out = []
    for a in config.AREAS:
        mine = [c for c in lot_cards if c["area"] == a.area_id]
        lst = [x for c in mine for x in c["listings"]]
        car = [x for x in lst if x["veh"] == "自動車" and x["ct"] == "月極"]
        area_out.append({"id": a.area_id, "name": a.name, "ja": a.name_ja, "lat": a.lat, "lng": a.lng, "radius_km": a.radius_km,
            "lots": len(mine), "listings": len(lst), "open_share": _open_share([x["vac"] for x in lst]),
            "median_car_rent": _median([x["rent"] for x in car]), "car_listings": len(car),
            "displayed": len(mine) >= config.MIN_LOTS_TO_DISPLAY,
            "series": [{"d": r["date_jst"], "listings": r["listings"], "open": r["monthly_open_share"], "rent": r["median_car_monthly_rent_yen"]}
                       for r in area_rows if r["area_id"] == a.area_id]})
    by_pref = defaultdict(list)
    for c in lot_cards:
        by_pref[c["pref"]].extend(c["listings"])
    pref_out = sorted([{"pref": p, "lots": sum(1 for c in lot_cards if c["pref"] == p), "listings": len(v),
        "open_share": _open_share([x["vac"] for x in v]),
        "median_car_rent": _median([x["rent"] for x in v if x["veh"] == "自動車" and x["ct"] == "月極"])} for p, v in by_pref.items()],
        key=lambda r: -r["listings"])

    rents = [x["rent"] for c in lot_cards for x in c["listings"] if x["veh"] == "自動車" and x["ct"] == "月極" and x["rent"]]
    price_events = [e for e in events if e["kind"] == "rent_change"]
    fin_latest = qs[-1] if qs else {}
    _j(web / "summary.json", {
        "generated_utc": now.isoformat(), "operator": config.OPERATOR_NAME,
        "last_run": last_run, "runs_total": len(runs), "runs_ok": len(ok_runs),
        "lots": len(active_lots), "listings": len(act_listings), "prefectures": len(by_pref),
        "car_monthly_listings": len(rents), "median_car_rent": _median(rents),
        "open_share": _open_share([x["vac"] for c in lot_cards for x in c["listings"]]),
        "first_observation_utc": snaps[0]["collection_utc"] if snaps else None,
        "official_lots_total": fin_latest.get("lots_total"), "official_spaces_total": fin_latest.get("spaces_total"),
        "official_asof": fin_latest.get("end"),
        "hourly": {"available": hourly_n > 0, "observations": hourly_n, "reason": HOURLY_UNAVAILABLE_REASON},
        "rent_hist": _hist(rents, 5000), "price_changes": len(price_events),
        "areas": area_out, "prefectures_table": pref_out,
        "national_series": [{"d": r["date_jst"], "listings": r["listings"], "open": r["monthly_open_share"],
                             "car_open": r["car_monthly_open_share"], "rent": r["median_car_monthly_rent_yen"]} for r in nat],
    })
    _j(web / "events.json", events[:500])
    universe, ustats = build_universe(con, lots)
    _j(web / "universe.json", {"lots": universe, "stats": ustats, "owned_timeline": owned_timeline(con),
        "osm_attribution": "© OpenStreetMap contributors (ODbL)"})
    _w(out / "exports/known_lots.csv", [{"operator": config.OPERATOR, "universe_id": c["id"], "lot_name": c["name"], "address": c["addr"],
        "latitude": c["lat"], "longitude": c["lng"], "area_id": c["area"], "capacity": c["spaces"], "opened": c["opened"],
        "owned": int(c["owned"]), "sources": "|".join(sorted(c["sources"])), "portal_lot_id": c["sources"].get("portal"),
        "osm_id": c["sources"].get("osm"), "owned_release_url": c["sources"].get("owned_pr")} for c in universe],
        ["operator", "universe_id", "lot_name", "address", "latitude", "longitude", "area_id", "capacity", "opened", "owned",
         "sources", "portal_lot_id", "osm_id", "owned_release_url"])

    # quality diagnostics
    stale_cut = (now - timedelta(hours=26)).isoformat()
    flags = Counter()
    for c in lot_cards:
        for x in c["listings"]:
            if x["vac"] == "unknown":
                flags["no_vacancy_flag"] += 1
            if x["rent"] is None:
                flags["no_rent"] += 1
            if x["seen"] and x["seen"] < stale_cut:
                flags["stale_over_26h"] += 1
        if c["lat"] is None:
            flags["no_coordinates"] += 1
    _j(web / "quality.json", {"generated_utc": now.isoformat(), "flags": flags,
        "runs": [{k: r[k] for k in ("run_id", "source", "started_utc", "status", "requests", "errors", "pages", "listings_seen", "duration_s", "note")} for r in runs[-300:]],
        "requests_total": sum(r["requests"] or 0 for r in runs), "failed_runs": sum(r["status"] != "ok" for r in runs),
        "coverage": {"portal_lots": len(active_lots), "official_lots": fin_latest.get("lots_total"),
                     "share_of_official": round(len(active_lots) / fin_latest["lots_total"], 4) if fin_latest.get("lots_total") else None,
                     "hourly_status_coverage": 0.0 if hourly_n == 0 else None},
        "biases": [
            "Portal lists only lots offering monthly / pass contracts: a small, non-random subset of Paraca's hourly network.",
            "Listings are concentrated in Tokyo and Osaka; many matched markets have zero or very few lots.",
            "Vacancy is a binary monthly-contract flag (open / waitlist), not a measure of hourly occupancy.",
            "No capacity per lot is published on the portal, so capacity weighting is impossible.",
            "Waitlist can reflect operator choice (few monthly spaces offered) as well as demand."]})

    gfy = max((r["fiscal_year"] for r in fin_rows if r["kind"].startswith("guidance")), default=None)
    g = finmodel.guidance(fin_rows, gfy) if gfy else {}
    _j(web / "financials.json", {"quarters": qs, "guidance": g, "guidance_fy": gfy,
        "annual": _annual(fin_rows), "fiscal_year_end": "30 September",
        "notes": ["Figures in ¥ million (truncated), non-consolidated JGAAP, from 決算短信.",
                  "Standalone quarters are derived by differencing cumulative figures.",
                  "Lot/space counts are period-end operating figures disclosed in the text of each 決算短信."]})
    _j(web / "forecast.json", {"backtest": finmodel.backtest(qs), "next": finmodel.forecast_next(qs, g),
        "altdata_link": {"status": "insufficient_history", "first_observation": snaps[0]["collection_utc"] if snaps else None,
            "note": "The monthly-portal signal starts on 2026-10-20. At least ~8 quarters of overlap with reported results are "
                    "needed before testing whether it leads revenue; no predictive claim is made."}})
    con.close()


def build_universe(con, lots: list[dict]) -> tuple[list[dict], dict]:
    """Merge every source into one deduplicated list of known Paraca lots.

    Two records within 60 m are treated as the same lot. Sources:
      portal   - monthly-contract listings (sweet.paraca.co.jp)
      owned_pr - owned-lot opening releases (geocoded addresses)
      osm      - OpenStreetMap features tagged Paraca
    """
    from .normalize import haversine_km, assign_area
    recs = []
    for l in lots:
        if l["active"] and l["latitude"]:
            recs.append({"src": "portal", "name": l["lot_name"], "lat": l["latitude"], "lng": l["longitude"], "ref": l["lot_id"],
                         "addr": l["address"], "spaces": None, "date": None})
    for r in con.execute("SELECT * FROM owned_lots WHERE kind='opened'"):
        if r["latitude"]:
            recs.append({"src": "owned_pr", "name": r["lot_name"], "lat": r["latitude"], "lng": r["longitude"], "ref": r["pdf_url"],
                         "addr": r["address"], "spaces": r["spaces"], "date": r["open_date"] or r["release_date"], "geo": r["geo_quality"]})
    for r in con.execute("SELECT * FROM osm_lots"):
        if r["latitude"]:
            recs.append({"src": "osm", "name": r["name"], "lat": r["latitude"], "lng": r["longitude"], "ref": r["osm_id"],
                         "addr": None, "spaces": r["capacity"], "date": None})
    clusters: list[dict] = []
    grid: dict = {}
    for rec in recs:
        key = (round(rec["lat"], 2), round(rec["lng"], 2))
        cand = [c for dk in [(key[0] + a / 100, key[1] + b / 100) for a in (-1, 0, 1) for b in (-1, 0, 1)]
                for c in grid.get((round(dk[0], 2), round(dk[1], 2)), [])]
        hit = next((c for c in cand if rec["src"] not in c["sources"]
                    and haversine_km(c["lat"], c["lng"], rec["lat"], rec["lng"]) <= 0.06), None)
        if hit:
            hit["sources"][rec["src"]] = rec["ref"]
            hit["name"] = hit["name"] or rec["name"]
            hit["spaces"] = hit["spaces"] or rec["spaces"]
            hit["opened"] = hit["opened"] or rec["date"]
            hit["addr"] = hit["addr"] or rec["addr"]
            continue
        c = {"lat": rec["lat"], "lng": rec["lng"], "name": rec["name"], "addr": rec["addr"], "spaces": rec["spaces"],
             "opened": rec["date"], "sources": {rec["src"]: rec["ref"]}, "geo": rec.get("geo")}
        clusters.append(c)
        grid.setdefault(key, []).append(c)
    for i, c in enumerate(clusters):
        c["id"] = f"u{i:05d}"
        c["area"], c["dist"] = assign_area(c["lat"], c["lng"])
        c["owned"] = "owned_pr" in c["sources"]
    by_src = Counter(s for c in clusters for s in c["sources"])
    owned_rows = con.execute("SELECT COUNT(*), SUM(spaces), SUM(latitude IS NOT NULL) FROM owned_lots WHERE kind='opened'").fetchone()
    stats = {"union_lots": len(clusters), "by_source": dict(by_src),
             "multi_source": sum(len(c["sources"]) > 1 for c in clusters),
             "owned_pr_rows": owned_rows[0], "owned_pr_spaces": owned_rows[1], "owned_pr_geocoded": owned_rows[2],
             "owned_releases": con.execute("SELECT COUNT(*) FROM owned_releases").fetchone()[0],
             "owned_release_errors": con.execute("SELECT COUNT(*) FROM owned_releases WHERE error IS NOT NULL").fetchone()[0],
             "osm_rows": con.execute("SELECT COUNT(*) FROM osm_lots").fetchone()[0]}
    return clusters, stats


def owned_timeline(con) -> list[dict]:
    """Owned lots opened per month according to the releases (cumulative)."""
    rows = con.execute("""SELECT substr(COALESCE(open_date, release_date),1,7) m, COUNT(*), SUM(COALESCE(spaces,0))
                          FROM owned_lots WHERE kind='opened' AND COALESCE(open_date, release_date) IS NOT NULL GROUP BY m ORDER BY m""").fetchall()
    out, cl, cs = [], 0, 0
    for m, n, sp in rows:
        cl += n
        cs += sp
        out.append({"m": m, "n": n, "spaces": sp, "cum_lots": cl, "cum_spaces": cs})
    return out


def _hist(xs, step):
    c = Counter(int(x // step) * step for x in xs)
    return [{"bin": k, "n": c[k]} for k in sorted(c)]


def _annual(rows):
    out = defaultdict(dict)
    for r in rows:
        if r["kind"] == "actual" and r["period"] == "FY":
            out[r["fiscal_year"]][r["metric"]] = r["value"]
            out[r["fiscal_year"]]["source_url"] = r["source_url"]
            out[r["fiscal_year"]]["release_date"] = r["release_date"]
            if r["metric"].startswith(("lots", "spaces")):
                out[r["fiscal_year"]]["derived_counts"] = bool(r["derived"]) or out[r["fiscal_year"]].get("derived_counts", False)
    return [dict(v, fy=k) for k, v in sorted(out.items())]
