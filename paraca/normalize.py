"""Pure normalisation helpers: money, status, geography, identity, time and fees."""
from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable

from .config import AREAS, Area

JST = timezone(timedelta(hours=9))

# ----------------------------------------------------------------------------- time

def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def to_jst(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("naive datetime: refuse to guess a timezone")
    return dt.astimezone(JST)


def iso(dt: datetime) -> str:
    return dt.isoformat()


def jst_date(dt: datetime) -> str:
    return to_jst(dt).date().isoformat()

# ---------------------------------------------------------------------------- money

_DASHES = {"—", "-", "－", "―", "–", ""}


def parse_yen(text: str | None) -> int | None:
    """'33,000円' -> 33000; '—' / '' / None -> None (unknown, never 0)."""
    if text is None:
        return None
    t = unicodedata.normalize("NFKC", str(text)).strip()
    t = t.replace("円", "").replace("¥", "").replace(",", "").replace("税込", "").strip()
    if t in _DASHES:
        return None
    m = re.fullmatch(r"\d+", t)
    return int(t) if m else None

# --------------------------------------------------------------------------- status

# Monthly-contract vacancy flag on the portal. This is NOT hourly occupancy.
MONTHLY_VACANCY = {
    "申込可能": "open",       # a space can be contracted now
    "空き待ち": "waitlist",   # no space available; wait-list only
}


def monthly_vacancy(label: str | None) -> str:
    if not label:
        return "unknown"
    return MONTHLY_VACANCY.get(label.strip(), "unknown")


HOURLY_STATUS = {"空車": "available", "混雑": "crowded", "満車": "full"}


def hourly_status(label: str | None) -> str:
    """Map an hourly availability label to the cross-operator enum."""
    if not label:
        return "unknown"
    return HOURLY_STATUS.get(label.strip(), "unknown")

# ------------------------------------------------------------------------ geography

def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def assign_area(lat: float | None, lng: float | None, areas: Iterable[Area] = AREAS) -> tuple[str | None, float | None]:
    """Nearest configured market whose radius contains the point (ties -> nearest)."""
    if lat is None or lng is None:
        return None, None
    best: tuple[str | None, float | None] = (None, None)
    for a in areas:
        d = haversine_km(lat, lng, a.lat, a.lng)
        if d <= a.radius_km and (best[1] is None or d < best[1]):
            best = (a.area_id, round(d, 3))
    return best


def parse_coord(v: str | None) -> float | None:
    try:
        f = float(v) if v not in (None, "") else None
    except ValueError:
        return None
    if f is None or f == 0.0:
        return None
    return f

# ------------------------------------------------------------------------- identity

def norm_text(s: str | None) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"\s+", "", s).lower()


def lot_key(name: str | None, address: str | None, lat: float | None, lng: float | None) -> str:
    """Stable lot id from normalised name + address + ~10 m rounded coordinates.

    One physical lot can carry several portal listings (car / bike / pass ...);
    they collapse into one lot here. Renamed lots get a new id by design; the
    events table records the appearance/disappearance.
    """
    coord = f"{round(lat, 4)},{round(lng, 4)}" if lat is not None and lng is not None else ""
    raw = "|".join([norm_text(name), norm_text(address), coord])
    return "paraca-" + hashlib.sha1(raw.encode()).hexdigest()[:12]

# ------------------------------------------------------------------------------ fees

@dataclass
class FeeSchedule:
    """Normalised view of a raw hourly fee text. Raw text is always preserved."""
    raw: str
    units: list[dict] = field(default_factory=list)   # {"days","start","end","minutes","yen"}
    caps: list[dict] = field(default_factory=list)    # {"days","window","yen"}
    hourly_rate_yen: float | None = None              # only when ONE uniform unit price exists
    daily_cap_yen: int | None = None                  # only an explicit 24h / 当日 cap
    flags: list[str] = field(default_factory=list)


_UNIT = re.compile(r"(?P<days>全日|平日|月[～~]金|土日祝|土日|土|日祝)?\s*(?P<start>\d{1,2}:\d{2})\s*[～~\-]\s*(?P<end>\d{1,2}:\d{2})\s*(?P<min>\d+)\s*分\s*[¥￥]?\s*(?P<yen>[\d,]+)\s*円?")
_CAP = re.compile(r"最大料金\s*(?P<days>全日|平日|月[～~]金|土日祝|土日|土|日祝)?\s*(?P<window>入庫後\s*\d+\s*時間(?:迄|まで)?|当日\s*\d{1,2}:\d{2}\s*まで|\d{1,2}:\d{2}\s*[～~\-]\s*\d{1,2}:\d{2}|24時間)?\s*[¥￥]?\s*(?P<yen>[\d,]+)\s*円?")


def parse_fee_schedule(raw: str | None) -> FeeSchedule:
    """Parse a Japanese coin-parking fee string without inventing equivalences.

    hourly_rate_yen is set only when every unit price implies the same yen/hour;
    with time-of-day or weekday variation it stays None and a flag explains why.
    """
    fs = FeeSchedule(raw=raw or "")
    if not raw:
        fs.flags.append("no_fee_text")
        return fs
    t = unicodedata.normalize("NFKC", raw).replace("〜", "～")
    for m in _UNIT.finditer(t):
        fs.units.append({"days": m["days"] or "全日", "start": m["start"], "end": m["end"],
                         "minutes": int(m["min"]), "yen": int(m["yen"].replace(",", ""))})
    for m in _CAP.finditer(t):
        fs.caps.append({"days": m["days"] or "全日", "window": (m["window"] or "").replace(" ", ""),
                        "yen": int(m["yen"].replace(",", ""))})
    rates = {round(u["yen"] * 60 / u["minutes"], 2) for u in fs.units if u["minutes"]}
    if len(rates) == 1:
        fs.hourly_rate_yen = rates.pop()
    elif len(rates) > 1:
        fs.flags.append("time_or_day_varying_rate")
    else:
        fs.flags.append("no_unit_price_parsed")
    day_caps = [c for c in fs.caps if c["window"].startswith("入庫後24") or c["window"] in ("24時間",) or c["window"].startswith("当日")]
    if len({c["yen"] for c in day_caps}) == 1:
        fs.daily_cap_yen = day_caps[0]["yen"]
    elif len(day_caps) > 1:
        fs.flags.append("day_dependent_cap")
    if any(c["window"] and not (c in day_caps) for c in fs.caps):
        fs.flags.append("has_time_window_caps")
    return fs
