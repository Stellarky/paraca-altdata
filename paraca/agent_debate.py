"""Daily three-agent debate on Paraca (4809): observe -> debate -> decide by threshold -> update.

Runs once per JST day after collection. Three agents argue from different evidence,
read each other's case, rebut and revise, and a judge combines them. Fixed thresholds
decide whether the published target price and rating actually change, so the view
moves only when the data justifies it. State is kept in store/web/agent_state.json
(published on the data branch), so each day is compared with the last.

The agents are rule-based: every number they state is computed from the collected
data, the 決算短信 figures or the daily share price. No language model is involved.

    python -m paraca.agent_debate store            # run once (skips if already ran today)
    python -m paraca.agent_debate store --force    # run again today
"""
from __future__ import annotations

import json
import math
import statistics as st
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))

# Starting point: the last published valuation panel (dashboard, 16 Oct 2026).
ANCHOR_TARGET = 1991.0
ANCHOR_RATING = "UNDERWEIGHT"
ANCHOR_DATE = "2026-10-16"
FALLBACK_PRICE = 1985.0            # 14 Oct close, used only if no daily price can be fetched
REQUIRED_RETURN = 0.086            # CAPM required return from the week-2 valuation
EPS_PER_LEASED_REV = 4.5           # 1% leased revenue per space ~ ¥141 mn ~ 4.5% of guided OP
LEASED_SHARE = 3731 / 4668         # FY2026 Q3 leased share of revenue

THRESHOLDS = {
    "target_change_pct": 3.0,      # publish a new target only if it moves >= 3 %
    "max_spread_pct": 15.0,        # agents further apart than this: hold, no update
    "rating_band_pp": 3.0,         # OVERWEIGHT / UNDERWEIGHT if expected return is +/-3pp from required
    "rating_confirm_days": 2,      # a rating change must hold on 2 consecutive days
    "signal_z": 2.0,               # alt-data move must beat daily noise by 2 SD to count in full
    "demand_rev_per_pp": 0.5,      # +1pp waitlist share -> +0.5 % leased revenue per space
    "demand_rev_cap_pct": 3.0,
}


def _load(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def fetch_price(state: dict) -> tuple[float, str, str]:
    """Latest Paraca close from Stooq (independent daily data). Falls back to the last known price."""
    try:
        import requests
        r = requests.get("https://stooq.com/q/d/l/", params={"s": "4809.jp", "i": "d"}, timeout=20)
        r.raise_for_status()
        rows = [l.split(",") for l in r.text.strip().splitlines()[1:]]
        d, close = rows[-1][0], float(rows[-1][4])
        return close, d, "stooq 4809.jp daily close"
    except Exception as e:                      # network blocked or no data
        last = state.get("last_price")
        if last:
            return float(last["close"]), last["date"], f"last known price (fetch failed: {e.__class__.__name__})"
        return FALLBACK_PRICE, "2026-10-14", "fallback 14 Oct close (fetch failed)"


def observe(web: Path, state: dict) -> dict:
    s = _load(web / "summary.json", {}) or {}
    f = _load(web / "forecast.json", {}) or {}
    u = _load(web / "universe.json", {}) or {}
    fin = _load(web / "financials.json", {}) or {}
    series = [r for r in s.get("national_series", []) if r.get("open") is not None]
    wait = [round((1 - r["open"]) * 100, 2) for r in series]
    diffs = [b - a for a, b in zip(wait, wait[1:])]
    n14 = min(14, len(wait) - 1)
    d14 = wait[-1] - wait[-1 - n14] if n14 > 0 else 0.0
    sd = st.pstdev(diffs) if len(diffs) >= 3 else None
    z = d14 / (sd * math.sqrt(n14)) if sd and n14 else 0.0
    totals = u.get("owned_totals") or []
    q = (fin.get("quarters") or [{}])[-1]
    nxt = f.get("next") or {}
    price, price_date, price_src = fetch_price(state)
    sig = _load(web / "signals.json", {}) or {}
    perf = ((sig.get("market") or {}).get("perf") or {})
    rel_1m = (perf["4809.jp"]["r20"] - perf["4666.jp"]["r20"]) if perf.get("4809.jp", {}).get("r20") is not None and perf.get("4666.jp", {}).get("r20") is not None else None
    north = [a for a in ((sig.get("weather") or {}).get("areas") or []) if a["id"] in ("sapporo", "sapporo_east", "aomori", "akita", "niigata_central", "sendai")]
    snow_qtd = round(sum(a["qtd"]["snow_cm"] for a in north), 1) if north else None
    snow_ly = round(sum(a["qtd_last_year"]["snow_cm"] for a in north), 1) if north else None
    lights = [a["change_pct"] for a in ((sig.get("satellite") or {}).get("areas") or []) if a.get("change_pct") is not None]
    light_chg = round(st.median(lights), 1) if lights else None
    return {
        "date": datetime.now(JST).date().isoformat(),
        "price": price, "price_date": price_date, "price_source": price_src,
        "waitlist_now_pct": wait[-1] if wait else None,
        "waitlist_change_14d_pp": round(d14, 2), "waitlist_daily_sd_pp": round(sd, 3) if sd else None,
        "waitlist_z": round(z, 2), "days_of_history": len(wait),
        "listings": s.get("listings"), "rent_changes": s.get("price_changes", 0),
        "runs_ok": s.get("runs_ok"), "runs_total": s.get("runs_total"),
        "portal_lots": s.get("lots"), "official_lots": q.get("lots_total"),
        "owned_spaces_q3": q.get("spaces_owned"), "owned_spaces_now": totals[-1]["spaces"] if totals else None,
        "owned_lots_now": totals[-1]["lots"] if totals else None, "owned_asof": totals[-1]["d"] if totals else None,
        "revenue_owned_share": (q["revenue_owned"] / q["revenue"]) if q.get("revenue") else None,
        "q4_model": nxt.get("revenue_point"), "q4_lo": nxt.get("revenue_lo"), "q4_hi": nxt.get("revenue_hi"),
        "q4_guidance_implied": nxt.get("guidance_implied_q4"),
        "fy_model": nxt.get("full_year_model"), "fy_guidance": nxt.get("full_year_guidance"),
        "latest_release": q.get("release_date"),
        "paraca_vs_park24_1m": round(rel_1m, 4) if rel_1m is not None else None,
        "north_snow_qtd_cm": snow_qtd, "north_snow_ly_cm": snow_ly, "night_light_change_pct": light_chg,
    }


def _t(anchor: float, eps_pct: float) -> float:
    return round(anchor * (1 + eps_pct / 100))


def debate(o: dict, anchor: float) -> dict:
    T = THRESHOLDS
    # ---------- Round 1: opening cases, each from its own evidence ----------
    rev_demand = max(-T["demand_rev_cap_pct"], min(T["demand_rev_cap_pct"], T["demand_rev_per_pp"] * o["waitlist_change_14d_pp"]))
    owned_growth = ((o["owned_spaces_now"] / o["owned_spaces_q3"] - 1) * 100) if o["owned_spaces_now"] and o["owned_spaces_q3"] else 0.0
    eps_dem = EPS_PER_LEASED_REV * rev_demand * LEASED_SHARE
    eps_own = owned_growth * (o["revenue_owned_share"] or 0) * EPS_PER_LEASED_REV
    eps_a = eps_dem + eps_own
    a1 = {"agent": "demand", "title": "Demand analyst (alt data)",
          "target": _t(anchor, eps_a), "confidence": 0.45 + (0.2 if abs(o["waitlist_z"]) >= T["signal_z"] else 0),
          "argument": (f"Waitlisted share is {o['waitlist_now_pct']}% ({o['waitlist_change_14d_pp']:+} pp over 14 days, z = {o['waitlist_z']}). "
                       f"Owned spaces are {o['owned_spaces_now']:,.0f} vs {o['owned_spaces_q3']:,.0f} at Q3 ({owned_growth:+.1f}%). "
                       f"That implies leased revenue per space {rev_demand:+.2f}% and EPS {eps_a:+.2f}%."
                       + (f" Satellite night lights over the panel markets are {o['night_light_change_pct']:+}% (7-day vs 30-day median)." if o.get("night_light_change_pct") is not None else "")
                       + (f" Snow in the northern strongholds is {o['north_snow_qtd_cm']} cm quarter to date vs {o['north_snow_ly_cm']} cm a year ago." if o.get("north_snow_qtd_cm") is not None else ""))}

    gap_pct = ((o["fy_model"] / o["fy_guidance"] - 1) * 100) if o["fy_model"] and o["fy_guidance"] else 0.0
    eps_b = gap_pct * EPS_PER_LEASED_REV
    inside_band = bool(o["q4_lo"] and o["q4_hi"] and o["q4_guidance_implied"] and o["q4_lo"] <= o["q4_guidance_implied"] <= o["q4_hi"])
    b1 = {"agent": "valuation", "title": "Valuation analyst (official data)",
          "target": _t(anchor, eps_b), "confidence": 0.6,
          "argument": (f"The run-rate model puts FY2026 revenue at ¥{o['fy_model']:,} mn against guidance of ¥{o['fy_guidance']:,.0f} mn "
                       f"({gap_pct:+.2f}%). At 4.5x operating leverage that is EPS {eps_b:+.2f}%. "
                       f"Q4 model ¥{o['q4_model']:,} mn, band ¥{o['q4_lo']:,}–{o['q4_hi']:,} mn."
                       + (f" Over the past month Paraca has moved {o['paraca_vs_park24_1m']:+.1%} relative to Park24." if o.get("paraca_vs_park24_1m") is not None else ""))}

    coverage = (o["portal_lots"] / o["official_lots"]) if o["portal_lots"] and o["official_lots"] else 0.0
    reliability = round(min(1.0, coverage / 0.30) * min(1.0, o["days_of_history"] / 90), 3)
    healthy = o["runs_ok"] == o["runs_total"]
    c1 = {"agent": "skeptic", "title": "Skeptic (measurement and risk)",
          "target": round(anchor), "confidence": 0.55,
          "argument": (f"The portal covers {coverage:.0%} of Paraca's {o['official_lots']:,.0f} lots and has only {o['days_of_history']} days of history, "
                       f"so its reliability weight is {reliability}. {o['rent_changes']} rent changes have been seen. "
                       f"Collection is {'healthy' if healthy else 'failing'} ({o['runs_ok']}/{o['runs_total']} runs ok). "
                       f"Nothing yet justifies moving from ¥{anchor:,.0f}. Weather, satellite and attention signals are context only: "
                       f"none has been calibrated against revenue.")}

    # ---------- Round 2: each reads the others, rebuts one, and revises ----------
    strong = abs(o["waitlist_z"]) >= T["signal_z"]
    a2t = a1["target"] if strong else _t(anchor, eps_dem * 0.5 + eps_own)
    a2 = dict(a1, target=a2t, rebuttal=(
        "To the skeptic: the move beats daily noise by more than 2 SD, so I keep my full adjustment." if strong else
        f"To the skeptic: fair, the 14-day move is only {o['waitlist_z']} SD of daily noise. I halve my adjustment, "
        f"but the owned-lot additions are official and stay in."), moved=a2t - a1["target"])
    b2t = _t(anchor, eps_b * 0.5) if inside_band else b1["target"]
    b2 = dict(b1, target=b2t, rebuttal=(
        f"To the demand analyst: guidance-implied Q4 (¥{o['q4_guidance_implied']:,} mn) sits inside my model's own error band, "
        f"so the shortfall is not significant. I halve it." if inside_band else
        "To the demand analyst: the guidance gap is outside my model's error band, so official data outweighs the portal signal."),
        moved=b2t - b1["target"])
    c2t = _t(anchor, eps_a * reliability + (eps_b * 0.5 if not inside_band else 0))
    c2 = dict(c1, target=c2t, rebuttal=(
        f"To the valuation analyst: I accept official data over portal data. I let the demand case in at my reliability weight "
        f"({reliability}), which moves me to ¥{c2t:,}."), moved=c2t - c1["target"])

    finals = [a2, b2, c2]
    wsum = sum(x["confidence"] for x in finals)
    combined = round(sum(x["target"] * x["confidence"] for x in finals) / wsum)
    spread_pct = round((max(x["target"] for x in finals) - min(x["target"] for x in finals)) / anchor * 100, 2)
    return {"round1": [a1, b1, c1], "round2": finals, "combined_target": combined, "spread_pct": spread_pct,
            "reliability": reliability, "guidance_gap_inside_band": inside_band}


def rating_for(target: float, price: float) -> tuple[str, float]:
    er = target / price - 1
    band = THRESHOLDS["rating_band_pp"] / 100
    if er >= REQUIRED_RETURN + band:
        return "OVERWEIGHT", er
    if er <= REQUIRED_RETURN - band:
        return "UNDERWEIGHT", er
    return "NEUTRAL", er


def decide(o: dict, d: dict, state: dict) -> dict:
    T = THRESHOLDS
    pub = state["published_target"]
    change_pct = (d["combined_target"] / pub - 1) * 100
    seen = state.get("last_release_seen")
    new_release = bool(seen and o["latest_release"] and o["latest_release"] != seen)
    rules = []
    if d["spread_pct"] > T["max_spread_pct"]:
        target, why = pub, f"HOLD: agents disagree by {d['spread_pct']}% (> {T['max_spread_pct']}%)"
    elif abs(change_pct) >= T["target_change_pct"] or new_release:
        target = d["combined_target"]
        why = (f"UPDATE: combined target moved {change_pct:+.2f}% (>= {T['target_change_pct']}%)" if not new_release
               else f"UPDATE: new 決算短信 ({o['latest_release']}) forces a re-mark")
    else:
        target, why = pub, f"HOLD: combined target ¥{d['combined_target']:,} is {change_pct:+.2f}% from published (< {T['target_change_pct']}%)"
    rules.append(why)

    candidate, er = rating_for(target, o["price"])
    pending = state.get("pending_rating")
    streak = state.get("pending_streak", 0)
    if candidate == state["published_rating"]:
        rating, pending, streak = candidate, None, 0
        rules.append(f"Rating stays {rating}: expected return {er:+.1%} vs required {REQUIRED_RETURN:.1%} ±{T['rating_band_pp']}pp")
    else:
        streak = streak + 1 if pending == candidate else 1
        pending = candidate
        if streak >= T["rating_confirm_days"]:
            rating, pending, streak = candidate, None, 0
            rules.append(f"Rating changes to {rating}: band crossed on {T['rating_confirm_days']} consecutive days")
        else:
            rating = state["published_rating"]
            rules.append(f"Rating would move to {candidate} (expected return {er:+.1%}); waiting for day {streak + 1} of "
                         f"{T['rating_confirm_days']} to confirm")
    return {"published_target": target, "published_rating": rating, "expected_return": round(er, 4),
            "required_return": REQUIRED_RETURN, "target_changed": target != pub,
            "rating_changed": rating != state["published_rating"], "rules_applied": rules,
            "_pending": pending, "_streak": streak}


def run(store: Path, force: bool = False) -> dict | None:
    web = store / "web"
    state_p = web / "agent_state.json"
    state = _load(state_p, None) or {"published_target": ANCHOR_TARGET, "published_rating": ANCHOR_RATING,
                                     "since": ANCHOR_DATE, "history": []}
    today = datetime.now(JST).date().isoformat()
    if state.get("last_run_date") == today and not force:
        print(f"debate already ran today ({today})")
        return None
    o = observe(web, state)
    d = debate(o, state["published_target"])
    dec = decide(o, d, state)
    out = {"date": today, "generated_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
           "observation": o, "debate": d, "decision": {k: v for k, v in dec.items() if not k.startswith("_")},
           "thresholds": THRESHOLDS, "previous": {"target": state["published_target"], "rating": state["published_rating"]}}
    (web / "debate.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    hist = (state.get("history") or [])[-89:] + [{"d": today, "target": dec["published_target"], "rating": dec["published_rating"],
                                                  "combined": d["combined_target"], "price": o["price"]}]
    state.update({"published_target": dec["published_target"], "published_rating": dec["published_rating"],
                  "pending_rating": dec["_pending"], "pending_streak": dec["_streak"], "last_run_date": today,
                  "last_release_seen": o["latest_release"], "last_price": {"close": o["price"], "date": o["price_date"]},
                  "history": hist})
    state_p.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"debate {today}: combined ¥{d['combined_target']:,} spread {d['spread_pct']}% -> "
          f"published ¥{dec['published_target']:,.0f} {dec['published_rating']} | {' / '.join(dec['rules_applied'])}")
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    try:
        run(Path(args[0] if args else "store"), force="--force" in sys.argv)
    except Exception as e:        # never break collection
        print(f"debate error ignored: {e!r}")
