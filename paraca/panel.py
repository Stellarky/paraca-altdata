"""panel.json: the data behind the single-page panel (areas now, per-run trends,
area detail, official decomposition, owned portfolio, coverage).

Vocabulary used on the page for Paraca's monthly-contract flag:
  waitlist (空き待ち)  -> "full"  : no monthly space can be contracted now
  open     (申込可能)  -> "open"
  blank               -> "no flag"
"waitlist share" = waitlisted listings / listings with a flag. It is a monthly
supply-tightness signal, not hourly occupancy.
"""
from __future__ import annotations

import bisect
import csv
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config

AREA_TYPE = {
    "tokyo_central": "Business district", "osaka_umeda": "Business district", "osaka_namba": "Shopping and nightlife",
    "nagoya_sakae": "Shopping and nightlife", "fukuoka_tenjin": "Shopping and nightlife", "kobe_sannomiya": "Shopping and nightlife",
    "kyoto_kawaramachi": "Tourist", "setagaya_sangenjaya": "Residential", "yokohama_station": "Commuter hub",
    "omiya_station": "Commuter hub", "funabashi_station": "Commuter hub", "tachikawa": "Suburban", "koshigaya": "Suburban",
    "sendai": "Regional city", "sapporo": "Regional city", "hiroshima": "Regional city",
    "niigata_central": "Regional city", "sapporo_east": "Residential", "aomori": "Regional city",
    "kameido_kinshicho": "Shopping and nightlife", "akita": "Regional city", "bunkyo_ueno": "Residential",
    "kofu": "Regional city", "gifu": "Regional city", "osaka_east": "Residential", "himeji": "Regional city",
}


def _share(vals):
    k = [v for v in vals if v in ("open", "waitlist")]
    return round(sum(v == "waitlist" for v in k) / len(k), 4) if k else None


def _med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def build(con, fin_quarters: list[dict], universe: list[dict], ustats: dict, street_csv: Path) -> dict:
    now = datetime.now(timezone.utc)
    lots = {r["lot_id"]: dict(r) for r in con.execute("SELECT * FROM lots")}
    listings = {r["listing_id"]: dict(r) for r in con.execute("SELECT * FROM listings")}
    snaps = defaultdict(list)                     # listing -> [(ts, vacancy, rent)]
    for r in con.execute("SELECT listing_id, collection_utc, vacancy_status, monthly_rent_yen FROM listing_snapshots ORDER BY collection_utc"):
        snaps[r[0]].append((r[1], r[2], r[3]))
    runs = [dict(r) for r in con.execute("SELECT run_id, started_utc, status, note FROM runs WHERE source IN ('sweet','sweet-pilot') ORDER BY started_utc")]

    def state_at(ts: str) -> dict:
        """listing -> (vacancy, rent) as of ts, for listings alive at ts."""
        out = {}
        for lid, ss in snaps.items():
            li = listings[lid]
            if li["first_seen_utc"] > ts:
                continue
            if not li["active"] and li["last_seen_utc"] < ts:
                continue
            i = bisect.bisect_right([s[0] for s in ss], ts) - 1
            if i >= 0:
                out[lid] = (ss[i][1], ss[i][2])
        return out

    area_of_listing = {lid: lots.get(li["lot_id"], {}).get("area_id") for lid, li in listings.items()}
    # ---- per-run series, last 7 days, every area ------------------------------------
    cut = (now - timedelta(days=7)).isoformat()
    recent = [r for r in runs if r["started_utc"] >= cut and r["status"] == "ok"]
    series = defaultdict(list)
    for r in recent:
        st = state_at(r["started_utc"])
        groups = defaultdict(list)
        for lid, (v, _) in st.items():
            groups["all"].append(v)
            if area_of_listing.get(lid):
                groups[area_of_listing[lid]].append(v)
        for g in ["all"] + [a.area_id for a in config.AREAS]:
            vs = groups.get(g, [])
            series[g].append({"t": r["started_utc"], "w": _share(vs), "n": len(vs)})

    # ---- current state per area -----------------------------------------------------
    cur = state_at(now.isoformat())
    prev_run = recent[-2]["started_utc"] if len(recent) > 1 else None
    prev = state_at(prev_run) if prev_run else {}
    u_by_area = defaultdict(list)
    for u in universe:
        u_by_area[u["area"] or "_none"].append(u)
        u_by_area["all"].append(u)

    def area_block(aid, sel):
        vs = [cur[l][0] for l in sel if l in cur]
        pv = [prev[l][0] for l in sel if l in prev]
        car_rents = [cur[l][1] for l in sel if l in cur and listings[l]["vehicle_type"] == "自動車" and listings[l]["contract_type"] == "月極"]
        us = u_by_area.get(aid, [])
        c = Counter(vs)
        return {"listings": len(vs), "waitlist": c["waitlist"], "open": c["open"], "noflag": c["unknown"],
                "waitlist_share": _share(vs), "prev_waitlist_share": _share(pv),
                "portal_lots": len({listings[l]["lot_id"] for l in sel if l in cur}),
                "known_lots": len(us), "owned_lots": sum(u["owned"] for u in us),
                "owned_spaces": sum(u["spaces"] or 0 for u in us if u["owned"]),
                "median_car_rent": _med(car_rents), "car_listings": len(car_rents)}

    areas = []
    all_sel = [l for l in cur]
    areas.append({"id": "all", "name": "All areas", "ja": "全国 · all listings", "type": "Panel total",
                  **area_block("all", all_sel), "series": series["all"]})
    for a in config.AREAS:
        sel = [l for l in cur if area_of_listing.get(l) == a.area_id]
        areas.append({"id": a.area_id, "name": a.name.split(" (")[0], "ja": a.name_ja, "type": AREA_TYPE.get(a.area_id, ""), "panel": a.panel,
                      "lat": a.lat, "lng": a.lng, "radius_km": a.radius_km, **area_block(a.area_id, sel), "series": series[a.area_id]})

    ranked = [a for a in areas[1:] if a.get("panel") == "matched" and a["listings"] >= 3 and a["waitlist_share"] is not None]
    busiest = max(ranked, key=lambda a: a["waitlist_share"]) if ranked else None
    quietest = min(ranked, key=lambda a: a["waitlist_share"]) if ranked else None

    # ---- by type (vehicle x contract) -----------------------------------------------
    bt = defaultdict(list)
    for lid, (v, rent) in cur.items():
        li = listings[lid]
        bt[(li["vehicle_type"], li["contract_type"])].append((v, rent))
    by_type = sorted([{"vehicle": k[0], "contract": k[1], "listings": len(x), "waitlist_share": _share([y[0] for y in x]),
                       "median_rent": _med([y[1] for y in x]), "min_rent": min([y[1] for y in x if y[1]] or [None]) if any(y[1] for y in x) else None,
                       "max_rent": max([y[1] for y in x if y[1]] or [0]) or None} for k, x in bt.items()], key=lambda r: -r["listings"])
    eq = Counter()
    eqw = defaultdict(list)
    import json as _json
    for lid, (v, _) in cur.items():
        for e in _json.loads(listings[lid]["equipment"] or "[]"):
            eq[e] += 1
            eqw[e].append(v)
    by_facility = [{"facility": k, "listings": n, "waitlist_share": _share(eqw[k])} for k, n in eq.most_common()]

    # ---- official decomposition: revenue growth = spaces growth + yield ---------------
    by = {(q["fy"], q["q"]): q for q in fin_quarters}
    decomp = []
    for q in fin_quarters:
        ly = by.get((q["fy"] - 1, q["q"]))
        if not (ly and q.get("revenue") and ly.get("revenue")):
            continue
        rec = {"label": q["label"], "total": round(q["revenue"] / ly["revenue"] - 1, 4)}
        if q.get("avg_spaces") and ly.get("avg_spaces"):
            gs = q["avg_spaces"] / ly["avg_spaces"] - 1
            rec["spaces"] = round(gs, 4)
            rec["yield_mix"] = round(rec["total"] - gs, 4)
        for seg in ("revenue_leased", "revenue_owned"):
            if q.get(seg) and ly.get(seg):
                rec[seg] = round(q[seg] / ly[seg] - 1, 4)
        if q.get("op_margin") is not None and ly.get("op_margin") is not None:
            rec["margin"], rec["margin_ly"] = q["op_margin"], ly["op_margin"]
        decomp.append(rec)
    last6 = [d for d in decomp if "spaces" in d][-6:]
    decomp_avg = {k: round(statistics.mean(d[k] for d in last6), 4) for k in ("total", "spaces", "yield_mix")} if last6 else None

    street = []
    if street_csv.exists():
        with open(street_csv, encoding="utf-8") as f:
            street = [r for r in csv.DictReader(f) if any(v.strip() for v in r.values())]

    # ---- owned portfolio ----------------------------------------------------------
    per_year = defaultdict(lambda: {"n": 0, "spaces": 0, "converted": 0})
    recent_open = []
    for r in con.execute("SELECT * FROM owned_lots WHERE kind='opened' ORDER BY open_date DESC"):
        y = (r["open_date"] or r["release_date"] or "")[:4]
        if y:
            per_year[y]["n"] += 1
            per_year[y]["spaces"] += r["spaces"] or 0
            per_year[y]["converted"] += "converted_from_leased" in (r["flags"] or "")
        if len(recent_open) < 40:
            recent_open.append({"name": r["lot_name"], "addr": r["address"], "spaces": r["spaces"], "opened": r["open_date"],
                                "converted": "converted_from_leased" in (r["flags"] or ""), "url": r["pdf_url"]})
    owned = {"per_year": [{"y": y, **v} for y, v in sorted(per_year.items())], "recent": recent_open,
             "last12": sum(1 for r in con.execute("SELECT open_date FROM owned_lots WHERE kind='opened' AND open_date >= ?",
                                                    ((now - timedelta(days=365)).date().isoformat(),)))}

    # ---- coverage by prefecture -----------------------------------------------------
    cov = defaultdict(lambda: {"portal": 0, "owned": 0, "known": 0})
    for u in universe:
        pref = None
        if "portal" in u["sources"]:
            pref = lots.get(u["sources"]["portal"], {}).get("prefecture")
        if not pref and u.get("addr"):
            for p in config.PREFECTURES.values():
                if u["addr"].startswith(p):
                    pref = p
                    break
        pref = pref or "unknown"
        cov[pref]["known"] += 1
        cov[pref]["portal"] += "portal" in u["sources"]
        cov[pref]["owned"] += u["owned"]
    coverage = sorted([{"pref": k, **v} for k, v in cov.items()], key=lambda r: -r["known"])

    # ---- events (openings/closures/changes) -------------------------------------------
    ev = [dict(r) for r in con.execute("SELECT * FROM events WHERE kind NOT IN ('lot_new','listing_new') OR run_id NOT LIKE 'pilot-%' ORDER BY event_utc DESC LIMIT 400")]
    for e in ev:
        l = lots.get(e["lot_id"], {})
        e["lot_name"], e["area"] = l.get("lot_name"), l.get("area_id")

    from .sources.status import status_panel
    return {"status": status_panel(con, universe), "generated_utc": now.isoformat(), "snapshots_7d": len(recent), "runs_total": len(runs),
            "last_snapshot": runs[-1]["started_utc"] if runs else None,
            "areas": areas, "busiest": busiest and {"id": busiest["id"], "name": busiest["name"], "w": busiest["waitlist_share"]},
            "quietest": quietest and {"id": quietest["id"], "name": quietest["name"], "w": quietest["waitlist_share"]},
            "by_type": by_type, "by_facility": by_facility, "decomp": decomp, "decomp_avg": decomp_avg,
            "street_estimates": street, "owned": owned, "coverage": coverage, "events": ev, "universe_stats": ustats}
