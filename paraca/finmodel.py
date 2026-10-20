"""Official financials -> standalone quarters, unit economics, and a transparent
space-driven revenue model with a walk-forward backtest.

Three deliberately simple models, every input disclosed (see MODELS):
  seasonal_naive     last year's quarter x trailing YoY growth
  space_yield        avg spaces x last year's same-quarter revenue per space-day
  space_yield_drift  space_yield x trailing change in yield
The headline forecast uses whichever has the lowest backtest MAPE (n >= 4).
"""
from __future__ import annotations

import csv
import math
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

from .fiscal import quarter_bounds

CUM = {"Q1": 1, "H1": 2, "Q3": 3, "FY": 4}


def load(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [dict(r, value=float(r["value"]), fiscal_year=int(r["fiscal_year"]), derived=int(r["derived"])) for r in csv.DictReader(f)]


def cumulative_table(rows: list[dict]) -> dict:
    """{(fy, q_index): {metric: value}} for actual cumulative P&L and period-end counts."""
    t: dict = defaultdict(dict)
    for r in rows:
        if r["kind"] != "actual":
            continue
        t[(r["fiscal_year"], CUM[r["period"]])][r["metric"]] = r["value"]
        t[(r["fiscal_year"], CUM[r["period"]])].setdefault("_src", r["source_url"])
        t[(r["fiscal_year"], CUM[r["period"]])].setdefault("_rel", r["release_date"])
    return t


FLOW = ["revenue", "operating_profit", "ordinary_profit", "net_income", "revenue_leased", "revenue_owned", "revenue_other"]
STOCK = ["lots_leased", "spaces_leased", "lots_owned", "spaces_owned", "lots_total", "spaces_total"]


def standalone_quarters(rows: list[dict]) -> list[dict]:
    cum = cumulative_table(rows)
    out = []
    for (fy, q) in sorted(cum):
        b = quarter_bounds(fy, q)
        rec = {"fy": fy, "q": q, "label": f"FY{fy} Q{q}", "start": b.start.isoformat(), "end": b.end.isoformat(),
               "days": (b.end - b.start).days + 1, "release_date": cum[(fy, q)].get("_rel"), "source_url": cum[(fy, q)].get("_src")}
        for m in FLOW:
            cur = cum[(fy, q)].get(m)
            prev = cum.get((fy, q - 1), {}).get(m) if q > 1 else 0.0
            rec[m] = None if cur is None or prev is None else round(cur - prev, 1)
        for m in STOCK:
            rec[m] = cum[(fy, q)].get(m)
        out.append(rec)
    _fill_space_bases(out)
    for r in out:
        if r["revenue"] and r.get("avg_spaces"):
            r["rev_per_space_day_yen"] = round(r["revenue"] * 1e6 / r["avg_spaces"] / r["days"], 1)
        else:
            r["rev_per_space_day_yen"] = None
        r["op_margin"] = round(r["operating_profit"] / r["revenue"], 4) if r["revenue"] and r["operating_profit"] is not None else None
    return out


def _fill_space_bases(qs: list[dict]) -> None:
    """Average spaces per quarter; linearly interpolate a missing quarter-end (flagged)."""
    ends = {(r["fy"], r["q"]): r.get("spaces_total") for r in qs}
    order = sorted(ends)
    for i, k in enumerate(order):
        if ends[k] is None and 0 < i < len(order) - 1:
            a, b = ends.get(order[i - 1]), ends.get(order[i + 1])
            if a is not None and b is not None:
                ends[k] = (a + b) / 2
                next(r for r in qs if (r["fy"], r["q"]) == k)["spaces_interpolated"] = True
    for r in qs:
        k = (r["fy"], r["q"])
        pk = (r["fy"], r["q"] - 1) if r["q"] > 1 else (r["fy"] - 1, 4)
        e, s = ends.get(k), ends.get(pk)
        r["spaces_end_used"] = e
        r["avg_spaces"] = (e + s) / 2 if e is not None and s is not None else None


def _mape(errs):
    return round(statistics.mean(abs(e) for e in errs), 4) if errs else None


MODELS = {
    "seasonal_naive": "Last year's same quarter x trailing YoY growth (previous quarter)",
    "space_yield": "Avg spaces x last year's same-quarter revenue per space-day",
    "space_yield_drift": "Avg spaces x last year's yield x trailing yield change (previous quarter YoY)",
}


def _predict(by: dict, fy: int, q: int, avg_spaces: float | None, days: int) -> dict:
    ly = by.get((fy - 1, q))
    pk = (fy, q - 1) if q > 1 else (fy - 1, 4)
    p, pl = by.get(pk), by.get((pk[0] - 1, pk[1]))
    out = {}
    if ly and ly.get("revenue") and p and pl and p.get("revenue") and pl.get("revenue"):
        out["seasonal_naive"] = ly["revenue"] * p["revenue"] / pl["revenue"]
    if avg_spaces and ly and ly.get("rev_per_space_day_yen"):
        out["space_yield"] = avg_spaces * ly["rev_per_space_day_yen"] * days / 1e6
        if p and pl and p.get("rev_per_space_day_yen") and pl.get("rev_per_space_day_yen"):
            out["space_yield_drift"] = avg_spaces * ly["rev_per_space_day_yen"] * p["rev_per_space_day_yen"] / pl["rev_per_space_day_yen"] * days / 1e6
    return {k: round(v, 1) for k, v in out.items()}


def backtest(qs: list[dict]) -> dict:
    """One-step-ahead backtest. Uses the quarter's actual average space base (known at
    quarter end from disclosures), i.e. a nowcast of revenue before the release."""
    by = {(r["fy"], r["q"]): r for r in qs}
    rows, errs = [], {m: [] for m in MODELS}
    for r in qs:
        if not r.get("revenue"):
            continue
        pred = _predict(by, r["fy"], r["q"], r.get("avg_spaces"), r["days"])
        if not pred:
            continue
        rec = {"label": r["label"], "actual": r["revenue"], **pred}
        for m, v in pred.items():
            e = round((v - r["revenue"]) / r["revenue"], 4)
            rec[m + "_err"] = e
            errs[m].append(e)
        rows.append(rec)
    stats = {m: {"mape": _mape(e), "n": len(e), "sd": round(statistics.pstdev(e), 4) if len(e) > 1 else None,
                 "bias": round(statistics.mean(e), 4) if e else None, "desc": MODELS[m]} for m, e in errs.items()}
    eligible = {m: s for m, s in stats.items() if s["n"] >= 4}
    best = min(eligible, key=lambda m: eligible[m]["mape"]) if eligible else None
    return {"rows": rows, "models": stats, "best": best}


def forecast_next(qs: list[dict], guidance: dict) -> dict | None:
    """Forecast the first quarter not yet reported (e.g. FY2026 Q4)."""
    last = max(qs, key=lambda r: (r["fy"], r["q"]))
    fy, q = (last["fy"], last["q"] + 1) if last["q"] < 4 else (last["fy"] + 1, 1)
    by = {(r["fy"], r["q"]): r for r in qs}
    b = quarter_bounds(fy, q)
    days = (b.end - b.start).days + 1
    ends = [(k, r["spaces_end_used"]) for k, r in sorted(by.items()) if r.get("spaces_end_used")]
    if len(ends) < 4:
        return None
    adds = [ends[-i][1] - ends[-i - 1][1] for i in range(1, 4)]
    net_add = statistics.mean(adds)
    end_hat = ends[-1][1] + net_add
    avg = (ends[-1][1] + end_hat) / 2
    pred = _predict(by, fy, q, avg, days)
    bt = backtest(qs)
    best = bt["best"]
    if not best or best not in pred:
        return None
    point, sd = pred[best], bt["models"][best]["sd"] or 0.03
    out = {"label": f"FY{fy} Q{q}", "start": b.start.isoformat(), "end": b.end.isoformat(), "model": best,
           "predictions": pred,
           "assumptions": {"spaces_start": ends[-1][1], "net_adds_per_quarter": round(net_add), "spaces_end_hat": round(end_hat),
                           "avg_spaces_hat": round(avg), "days": days},
           "revenue_point": round(point), "revenue_lo": round(point * (1 - 1.96 * sd)), "revenue_hi": round(point * (1 + 1.96 * sd)),
           "interval_note": f"Point = best backtested model ({best}); band = ±1.96×SD of its {bt['models'][best]['n']} "
                            "backtest errors. Very few observations: indicative only, not a validated confidence interval."}
    rev_g = guidance.get("revenue")
    cum = sum(by[(fy, k)]["revenue"] for k in range(1, q) if by.get((fy, k)) and by[(fy, k)]["revenue"])
    if rev_g and q == 4:
        out["guidance_implied_q4"] = round(rev_g - cum)
        out["full_year_model"] = round(cum + point)
        out["full_year_guidance"] = rev_g
        out["cum_q1_q3"] = cum
    return out


def guidance(rows: list[dict], fy: int) -> dict:
    g: dict = {}
    for kind in ("guidance_initial", "guidance_revised"):
        for r in rows:
            if r["kind"] == kind and r["fiscal_year"] == fy:
                g[r["metric"]] = r["value"]
                g["_kind"], g["_date"], g["_src"] = kind, r["release_date"], r["source_url"]
    return g
