"""Owned-lot openings from Paraca's own press releases (paraca.co.jp/news/pr/).

Since 2008 Paraca publishes a monthly PDF listing owned car parks opened (and,
in older releases, land acquired): name, address, spaces (台数), open date.
robots.txt on paraca.co.jp allows crawling. PDFs never change once published,
so each is fetched once and its extracted text is kept for audit.
"""
from __future__ import annotations

import io
import logging
import re
import unicodedata
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from ..http import PoliteClient

log = logging.getLogger(__name__)

PR_LIST = "https://paraca.co.jp/news/pr/"
PR_PAGE = "https://paraca.co.jp/news/pr/page/{n}/"
TITLE_RE = re.compile(r"保有駐車場|自社物件|自社保有")

PREF = r"(?:北海道|東京都|大阪府|京都府|(?:青森|岩手|宮城|秋田|山形|福島|茨城|栃木|群馬|埼玉|千葉|神奈川|新潟|富山|石川|福井|山梨|長野|岐阜|静岡|愛知|三重|滋賀|兵庫|奈良|和歌山|鳥取|島根|岡山|広島|山口|徳島|香川|愛媛|高知|福岡|佐賀|長崎|熊本|大分|宮崎|鹿児島|沖縄)県)"
ADDR_RE = re.compile(PREF + r"[^\s　,、（）()]{2,40}")
SPACES_RE = re.compile(r"(\d{1,4})\s*(?:台|車室)")
ERA = {"令和": 2018, "平成": 1988}
DATE_RE = re.compile(r"(令和|平成)\s*(\d{1,2}|元)\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日|(20\d\d)[年/.\-]\s*(\d{1,2})[月/.\-]\s*(\d{1,2})")


@dataclass
class Release:
    url: str
    release_date: str | None
    title: str


@dataclass
class OwnedLot:
    lot_name: str | None
    address: str
    spaces: int | None
    open_date: str | None
    kind: str = "opened"          # opened | acquired | unknown
    raw: str = ""
    flags: list[str] = field(default_factory=list)


def n(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "")


def parse_date(s: str) -> str | None:
    m = DATE_RE.search(n(s))
    if not m:
        return None
    if m.group(1):
        y = ERA[m.group(1)] + (1 if m.group(2) == "元" else int(m.group(2)))
        mo, d = int(m.group(3)), int(m.group(4))
    else:
        y, mo, d = int(m.group(5)), int(m.group(6)), int(m.group(7))
    return f"{y:04d}-{mo:02d}-{d:02d}"


def parse_list_page(html: str) -> tuple[list[Release], int]:
    """Releases on one /news/pr/ page and the highest page number seen."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for a in soup.select("a[href]"):
        t = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
        href = a["href"]
        if not TITLE_RE.search(t) or not href.lower().endswith(".pdf"):
            continue
        out.append(Release(url=href, release_date=parse_date(t), title=t))
    pages = [int(x) for x in re.findall(r"/news/pr/page/(\d+)/", html)]
    return out, max(pages or [1])


def crawl_releases(client: PoliteClient, max_pages: int | None = None) -> list[Release]:
    html = client.get(PR_LIST)
    rel, last = parse_list_page(html)
    last = min(last, max_pages) if max_pages else last
    for p in range(2, last + 1):
        r, _ = parse_list_page(client.get(PR_PAGE.format(n=p)))
        rel.extend(r)
    seen, out = set(), []
    for r in rel:
        if r.url not in seen:
            seen.add(r.url)
            out.append(r)
    return out


def pdf_text(data: bytes) -> str:
    import pdfplumber
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        parts = []
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
        return "\n".join(parts)


def parse_release_text(text: str, release_date: str | None = None) -> list[OwnedLot]:
    """Find lot rows: each must carry a prefecture-led address. Name = text just
    before the address on the same line (or the previous line); spaces and
    dates are read from the same line / next line."""
    lines = [n(l).strip() for l in text.splitlines() if n(l).strip()]
    out: list[OwnedLot] = []
    section = "opened"
    for i, line in enumerate(lines):
        if "取得" in line and "オープン" not in line and len(line) < 30:
            section = "acquired"
        elif "オープン" in line and len(line) < 30:
            section = "opened"
        m = ADDR_RE.search(line)
        if not m:
            continue
        # skip the company's own head-office address and letterhead lines
        if "愛宕" in m.group(0) and "港区" in m.group(0):
            continue
        ctx = line + " " + (lines[i + 1] if i + 1 < len(lines) and not ADDR_RE.search(lines[i + 1]) else "")
        before = line[: m.start()].strip(" :：・|")
        name = before or (lines[i - 1] if i > 0 and not ADDR_RE.search(lines[i - 1]) and len(lines[i - 1]) < 40 else None)
        after = line[m.end():] + " " + ctx[len(line):]
        sp = SPACES_RE.search(after) or SPACES_RE.search(before)
        lot = OwnedLot(lot_name=(name or None), address=m.group(0), spaces=int(sp.group(1)) if sp else None,
                       open_date=parse_date(after) or parse_date(before), kind=section, raw=ctx[:300])
        if lot.spaces is None:
            lot.flags.append("no_spaces")
        if lot.lot_name is None:
            lot.flags.append("no_name")
        out.append(lot)
    return out


# --------------------------------------------------------------------- geocoding
GSI = "https://msearch.gsi.go.jp/address-search/AddressSearch"


def geocode(client: PoliteClient, address: str) -> tuple[float | None, float | None, str | None, str]:
    """GSI (国土地理院) address search; free, no key. Returns lat, lng, matched title, quality."""
    import json
    try:
        res = json.loads(client.get(GSI, {"q": address}))
    except Exception as e:  # noqa: BLE001
        log.warning("geocode failed for %s: %s", address, e)
        return None, None, None, "error"
    if not res:
        return None, None, None, "no_match"
    best = res[0]
    lng, lat = best["geometry"]["coordinates"]
    title = best["properties"].get("title", "")
    na, nt = n(address).replace(" ", ""), n(title).replace(" ", "")
    q = "exact" if nt and na.startswith(nt[: max(6, len(nt) - 2)]) else "approx"
    return float(lat), float(lng), title, q
