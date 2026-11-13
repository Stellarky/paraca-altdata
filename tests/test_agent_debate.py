import json
from pathlib import Path

from paraca import agent_debate as ad


def obs(**kw):
    o = {"date": "2026-11-13", "price": 1985.0, "price_date": "2026-11-13", "price_source": "test",
         "waitlist_now_pct": 63.7, "waitlist_change_14d_pp": -0.1, "waitlist_daily_sd_pp": 0.4, "waitlist_z": -0.1,
         "days_of_history": 25, "listings": 461, "rent_changes": 0, "runs_ok": 10, "runs_total": 10,
         "portal_lots": 377, "official_lots": 2701, "owned_spaces_q3": 5912, "owned_spaces_now": 5976,
         "owned_lots_now": 354, "owned_asof": "2026-11-06", "revenue_owned_share": 0.166,
         "q4_model": 4824, "q4_lo": 4699, "q4_hi": 4949, "q4_guidance_implied": 4890,
         "fy_model": 18634, "fy_guidance": 18700, "latest_release": "2026-08-06"}
    o.update(kw)
    return o


def state(**kw):
    s = {"published_target": 1991.0, "published_rating": "UNDERWEIGHT", "history": [], "last_release_seen": "2026-08-06"}
    s.update(kw)
    return s


def test_quiet_day_holds():
    o = obs(); d = ad.debate(o, 1991.0); dec = ad.decide(o, d, state())
    assert len(d["round1"]) == 3 and all("rebuttal" in a for a in d["round2"])
    assert not dec["target_changed"] and dec["published_target"] == 1991.0


def test_strong_demand_signal_updates_target():
    o = obs(waitlist_change_14d_pp=6.0, waitlist_z=3.5, days_of_history=120, portal_lots=900)
    d = ad.debate(o, 1991.0); dec = ad.decide(o, d, state())
    assert d["combined_target"] > 1991 * 1.03 and dec["target_changed"]


def test_new_release_forces_update():
    o = obs(latest_release="2026-11-12"); d = ad.debate(o, 1991.0)
    assert ad.decide(o, d, state())["rules_applied"][0].startswith("UPDATE: new")


def test_rating_change_needs_two_days():
    o = obs(price=1500.0); d = ad.debate(o, 1991.0)
    day1 = ad.decide(o, d, state())
    assert day1["published_rating"] == "UNDERWEIGHT" and day1["_pending"] == "OVERWEIGHT"
    day2 = ad.decide(o, d, state(pending_rating="OVERWEIGHT", pending_streak=1))
    assert day2["published_rating"] == "OVERWEIGHT" and day2["rating_changed"]
