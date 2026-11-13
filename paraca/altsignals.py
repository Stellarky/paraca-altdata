"""Outside-in signals for Paraca, refreshed once a day: market, weather, satellite and attention.

Every source is public and needs no key. Each one fails on its own: an error is
recorded in signals.json and the other sources still publish.

  market     Stooq daily closes: Paraca (4809), Park24 (4666), Nippon Parking Development
             (2353), Azoom (3496) and TOPIX, for relative performance.
  weather    Open-Meteo daily rain, snow and temperature for all 26 panel markets,
             quarter-to-date against the same days last year and the next 7 days.
             Snow matters for Paraca's northern strongholds (Sapporo, Aomori, Akita, Niigata).
  satellite  NASA GIBS, VIIRS (Suomi NPP) day/night band: mean night-light brightness
             over each market, as a proxy for night-time activity. Daily scenes are noisy
             (cloud, moon), so the dashboard compares 7-day and 30-day medians.
  attention  Wikipedia (ja) daily page views for Paraca and its peers.

    python -m paraca.altsignals store          # runs if the last refresh is older than 20 h
    python -m paraca.altsignals store --force
"""
from __future__ import annotations

import io
import json
import statistics as st
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import requests

from . import config

JST = timezone(timedelta(hours=9))
UA = {"User-Agent": "paraca-altdata research collector (github.com/Stellarky/paraca-altdata)"}
TICKERS = {"4809.jp": "Paraca", "4666.jp": "Park24", "2353.jp": "Nippon Parking Dev.", "3496.jp": "Azoom", "^tpx": "TOPIX"}
WIKI = ["パラカ", "パーク24", "日本駐車場開発", "アズーム"]
GIBS_LAYER = "VIIRS_SNPP_DayNightBand_At_Sensor_Radiance"
SAT_BACKFILL_DAYS = 21
SAT_HALF_DEG = 0.03          # ~3 km box around each market centre


def _get(url, **kw):
    r = requests.get(url, headers=UA, timeout=kw.pop("timeout", 30), **kw)
    r.raise_for_status()
    return r


def market() -> dict:
    series, perf = {}, {}
    for sym, name in TICKERS.items():
        rows = []
        for line in _get("https://stooq.com/q/d/l/", params={"s": sym, "i": "d"}).text.strip().splitlines()[1:]:
            p = line.split(",")
            try:
                rows.append({"d": p[0], "c": float(p[4])})
            except (IndexError, ValueError):
                continue
        rows = rows[-260:]
        if not rows:
            raise ValueError(f"no rows for {sym}")
        series[sym] = rows
        last = rows[-1]["c"]
        ret = lambda n: round(last / rows[-1 - n]["c"] - 1, 4) if len(rows) > n else None
        perf[sym] = {"name": name, "last": last, "date": rows[-1]["d"], "r20": ret(20), "r60": ret(60), "r250": ret(250)}
        time.sleep(0.5)
    return {"names": TICKERS, "series": series, "perf": perf}


def _quarter_start(d: date) -> date:
    return date(d.year, ((d.month - 1) // 3) * 3 + 1, 1)


def weather() -> dict:
    areas = config.AREAS
    lats = ",".join(f"{a.lat:.4f}" for a in areas)
    lngs = ",".join(f"{a.lng:.4f}" for a in areas)
    daily = "precipitation_sum,snowfall_sum,temperature_2m_mean"
    today = datetime.now(JST).date()
    qs = _quarter_start(today)
    now = _get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": lats, "longitude": lngs, "daily": daily, "timezone": "Asia/Tokyo",
        "past_days": min(92, (today - qs).days + 1), "forecast_days": 7}).json()
    ly_end = today.replace(year=today.year - 1) - timedelta(days=1)
    ly = _get("https://archive-api.open-meteo.com/v1/archive", params={
        "latitude": lats, "longitude": lngs, "daily": daily, "timezone": "Asia/Tokyo",
        "start_date": qs.replace(year=qs.year - 1).isoformat(), "end_date": ly_end.isoformat()}).json()
    now = now if isinstance(now, list) else [now]
    ly = ly if isinstance(ly, list) else [ly]

    def agg(dly, lo: str, hi: str) -> dict:
        rows = [(t, p, s, tm) for t, p, s, tm in zip(dly["time"], dly["precipitation_sum"], dly["snowfall_sum"],
                                                      dly["temperature_2m_mean"]) if lo <= t <= hi]
        ps = [p or 0 for _, p, _, _ in rows]
        ts = [tm for *_, tm in rows if tm is not None]
        return {"days": len(rows), "rain_mm": round(sum(ps), 1), "rain_days": sum(p >= 1 for p in ps),
                "snow_cm": round(sum(s or 0 for _, _, s, _ in rows), 1), "temp_c": round(st.mean(ts), 1) if ts else None}

    out = []
    for a, n, l in zip(areas, now, ly):
        d, dl = n["daily"], l["daily"]
        y = today - timedelta(days=1)
        out.append({"id": a.area_id, "name": a.name, "ja": a.name_ja, "panel": a.panel,
                    "qtd": agg(d, qs.isoformat(), y.isoformat()),
                    "qtd_last_year": agg(dl, "0000", "9999"),
                    "next7": agg(d, today.isoformat(), (today + timedelta(days=6)).isoformat()),
                    "recent": [{"d": t, "rain": p, "snow": s} for t, p, s in
                               zip(d["time"], d["precipitation_sum"], d["snowfall_sum"])][-21:]})
    return {"quarter_start": qs.isoformat(), "areas": out,
            "note": "Open-Meteo forecast/ERA5 archive. Quarter-to-date is compared with the same calendar days a year earlier."}


def _brightness(png: bytes) -> float | None:
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("L")
    px = list(im.getdata())
    return round(sum(px) / len(px), 2) if px else None


def satellite(prev: dict | None) -> dict:
    hist: dict[str, dict[str, float]] = {k: dict(v) for k, v in ((prev or {}).get("history") or {}).items()}
    today = datetime.now(JST).date()
    errors = 0
    for a in config.AREAS:
        h = hist.setdefault(a.area_id, {})
        for k in range(2, SAT_BACKFILL_DAYS + 2):           # VIIRS daily scenes publish with ~1-2 day lag
            day = (today - timedelta(days=k)).isoformat()
            if day in h:
                continue
            bbox = f"{a.lat - SAT_HALF_DEG},{a.lng - SAT_HALF_DEG},{a.lat + SAT_HALF_DEG},{a.lng + SAT_HALF_DEG}"
            try:
                r = _get("https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi", params={
                    "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap", "LAYERS": GIBS_LAYER, "STYLES": "",
                    "CRS": "EPSG:4326", "BBOX": bbox, "WIDTH": 48, "HEIGHT": 48, "FORMAT": "image/png", "TIME": day}, timeout=40)
                if "image" not in r.headers.get("Content-Type", ""):
                    continue
                v = _brightness(r.content)
                if v is not None:
                    h[day] = v
            except Exception:
                errors += 1
                if errors > 25:
                    break
            time.sleep(0.2)
        keep = sorted(h)[-120:]
        hist[a.area_id] = {d: h[d] for d in keep}
    areas = []
    for a in config.AREAS:
        h = hist.get(a.area_id, {})
        vals = [h[d] for d in sorted(h)]
        r7, r30 = vals[-7:], vals[-30:]
        m7 = st.median(r7) if len(r7) >= 3 else None
        m30 = st.median(r30) if len(r30) >= 7 else None
        areas.append({"id": a.area_id, "name": a.name, "panel": a.panel, "days": len(vals),
                      "median_7d": m7, "median_30d": m30,
                      "change_pct": round((m7 / m30 - 1) * 100, 1) if m7 and m30 else None,
                      "series": [{"d": d, "v": h[d]} for d in sorted(h)][-60:]})
    return {"layer": GIBS_LAYER, "areas": areas, "history": hist, "fetch_errors": errors,
            "note": ("Mean pixel brightness (0-255) of NASA GIBS VIIRS day/night band images over a ~6 km box. "
                     "Single nights are affected by cloud and moonlight, so compare medians, not days.")}


def attention() -> dict:
    end = datetime.now(JST).date() - timedelta(days=1)
    start = end - timedelta(days=120)
    out = {}
    for t in WIKI:
        url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/ja.wikipedia/all-access/user/"
               f"{quote(t, safe='')}/daily/{start:%Y%m%d}/{end:%Y%m%d}")
        try:
            items = _get(url).json().get("items", [])
            out[t] = [{"d": f"{i['timestamp'][:4]}-{i['timestamp'][4:6]}-{i['timestamp'][6:8]}", "v": i["views"]} for i in items]
        except Exception as e:
            out[t] = {"error": e.__class__.__name__}
        time.sleep(0.3)
    return {"articles": out, "note": "Wikipedia (ja) daily user page views: a rough measure of public attention."}


def run(store: Path, force: bool = False) -> None:
    web = store / "web"
    path = web / "signals.json"
    prev = None
    try:
        prev = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    if prev and not force:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(prev["generated_utc"])
        if age < timedelta(hours=20):
            print(f"signals fresh ({age}), skipping")
            return
    out = {"generated_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "errors": {}}
    for name, fn in [("market", market), ("weather", weather), ("attention", attention),
                     ("satellite", lambda: satellite((prev or {}).get("satellite")))]:
        try:
            out[name] = fn()
            print(f"signals: {name} ok")
        except Exception as e:
            out["errors"][name] = f"{e.__class__.__name__}: {str(e)[:200]}"
            if prev and name in prev:
                out[name] = prev[name]          # keep yesterday's data rather than a hole
            print(f"signals: {name} failed: {out['errors'][name]}")
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    try:
        run(Path(args[0] if args else "store"), force="--force" in sys.argv)
    except Exception as e:
        print(f"signals error ignored: {e!r}")
