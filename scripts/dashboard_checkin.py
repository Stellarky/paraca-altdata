"""Check the Paraca agents in to the Fukuhara Seminar dashboard after each collection.

The class dashboard marks an agent live only when it checks in through the
agent API (POST /api/state). Collection kept running on GitHub Actions, but
nothing reported to the dashboard, so every agent there showed offline.

Each run:
  1. checks in every agent key in DASHBOARD_API_KEYS (comma or newline separated),
     declaring a daily check-in rhythm;
  2. once per JST day, posts a "daily_update" output with today's panel numbers,
     the change since yesterday, and whether a threshold was crossed that should
     make the debate re-run.

It never fails the collection job: network errors are printed and ignored.
Environment: DASHBOARD_API_KEYS (required), DASHBOARD_URL (optional).
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

URL = os.environ.get("DASHBOARD_URL", "https://fukuhara-seminar.onrender.com").rstrip("/")
CHECK_IN_EVERY = 86400            # seconds: daily rhythm shown on the dashboard
JST = timezone(timedelta(hours=9))

# Thresholds that decide whether today's data should change the agents' view.
WAITLIST_MOVE_PP = 2.0            # waitlisted share moves >= 2 points day on day
RENT_MOVE_PCT = 3.0               # median car monthly rent moves >= 3 %
LISTINGS_MOVE_PCT = 5.0           # active listings move >= 5 %


def _keys() -> list[str]:
    raw = os.environ.get("DASHBOARD_API_KEYS") or os.environ.get("DASHBOARD_API_KEY") or ""
    return [k.strip() for k in raw.replace("\n", ",").split(",") if k.strip()]


def _call(method: str, path: str, key: str, body: dict, tries: int = 3):
    for t in range(tries):
        try:
            r = requests.request(method, URL + path, json=body, headers={"X-API-Key": key}, timeout=90)
            if r.status_code < 500:
                return r
        except requests.RequestException as e:    # free Render instance may be asleep
            print(f"  {path}: {e.__class__.__name__}, retrying")
        time.sleep(20 * (t + 1))
    return None


def build_update(summary: dict) -> dict:
    series = summary.get("national_series") or []
    today, prev = (series[-1], series[-2]) if len(series) >= 2 else (series[-1] if series else {}, {})

    def pct(a, b):
        return round((a / b - 1) * 100, 2) if a and b else None

    wait_today = round((1 - today["open"]) * 100, 1) if today.get("open") is not None else None
    wait_prev = round((1 - prev["open"]) * 100, 1) if prev.get("open") is not None else None
    moves = {
        "waitlist_share_pp": round(wait_today - wait_prev, 2) if None not in (wait_today, wait_prev) else None,
        "median_car_rent_pct": pct(today.get("rent"), prev.get("rent")),
        "listings_pct": pct(today.get("listings"), prev.get("listings")),
    }
    crossed = []
    if moves["waitlist_share_pp"] is not None and abs(moves["waitlist_share_pp"]) >= WAITLIST_MOVE_PP:
        crossed.append(f"waitlist share moved {moves['waitlist_share_pp']:+} pp (>= {WAITLIST_MOVE_PP})")
    if moves["median_car_rent_pct"] is not None and abs(moves["median_car_rent_pct"]) >= RENT_MOVE_PCT:
        crossed.append(f"median rent moved {moves['median_car_rent_pct']:+} % (>= {RENT_MOVE_PCT})")
    if moves["listings_pct"] is not None and abs(moves["listings_pct"]) >= LISTINGS_MOVE_PCT:
        crossed.append(f"listings moved {moves['listings_pct']:+} % (>= {LISTINGS_MOVE_PCT})")
    if summary.get("price_changes"):
        crossed.append(f"{summary['price_changes']} rent change(s) recorded")
    return {
        "date_jst": today.get("d"),
        "data_as_of_utc": summary.get("generated_utc"),
        "collection_runs_ok": f"{summary.get('runs_ok')}/{summary.get('runs_total')}",
        "lots": summary.get("lots"),
        "listings": summary.get("listings"),
        "waitlist_share_pct": wait_today,
        "median_car_monthly_rent_yen": today.get("rent"),
        "change_vs_previous_day": moves,
        "thresholds_crossed": crossed,
        "decision": ("re-run debate: threshold crossed" if crossed
                     else "hold current view: no threshold crossed"),
    }


def main(store: Path) -> int:
    keys = _keys()
    if not keys:
        print("dashboard check-in skipped: DASHBOARD_API_KEYS not set")
        return 0
    try:
        summary = json.loads((store / "web" / "summary.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"dashboard check-in: no summary ({e}); checking in only")
        summary = None

    marker = store / "web" / "dashboard_last_update.txt"
    today = datetime.now(JST).date().isoformat()
    post_update = summary is not None and (not marker.exists() or marker.read_text().strip() != today)
    update = build_update(summary) if post_update else None

    sent_all = True
    for n, key in enumerate(keys, 1):
        r = _call("POST", "/api/state", key, {"check_in_every": CHECK_IN_EVERY})
        ok = r is not None and r.ok
        print(f"agent {n}: check-in {'ok' if ok else 'failed ' + str(getattr(r, 'status_code', 'no response'))}")
        if ok and update:
            r2 = _call("POST", "/api/outputs", key, {"category": "daily_update", "content": update})
            sent = r2 is not None and r2.ok
            sent_all &= sent
            print(f"agent {n}: daily update {'posted' if sent else 'failed'}")
        elif update:
            sent_all = False
    if update and sent_all:
        marker.write_text(today)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else "store")))
    except Exception as e:                         # never break collection
        print(f"dashboard check-in error ignored: {e!r}")
        sys.exit(0)
