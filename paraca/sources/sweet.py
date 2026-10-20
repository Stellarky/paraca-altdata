"""Parser + collector for Paraca's monthly-parking portal (sweet.paraca.co.jp).

Page structure (verified 2026-10-20): /parking/search?prefectureId=N&pageSize=50&page=K
returns <table class="result_tbl">. A lot spans several <tr> via rowspan on
td.parking_name_col; each <tr> is one *listing* (vehicle/contract type) with a
detail link /parking/detail/{id}. Coordinates sit on span.map_btn data-lat/lng.
"""
from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from typing import Iterator

from bs4 import BeautifulSoup

from .. import config
from ..http import PoliteClient
from ..normalize import monthly_vacancy, parse_coord, parse_yen

log = logging.getLogger(__name__)

_COUNT = re.compile(r"(\d+)～(\d+)件\s*/\s*(\d+)件中")


@dataclass
class Listing:
    listing_id: str
    lot_name: str | None
    address: str | None
    lat: float | None
    lng: float | None
    prefecture_id: int
    prefecture_name: str | None
    monthly_rent_yen: int | None
    deposit_yen: int | None
    key_money_yen: int | None
    vehicle_type: str | None
    contract_type: str | None
    equipment: list[str] = field(default_factory=list)
    size_note: str | None = None
    vacancy_label: str | None = None
    vacancy_status: str = "unknown"
    source_url: str = ""


@dataclass
class SearchPage:
    listings: list[Listing]
    total: int | None
    first: int | None
    last: int | None


def _txt(el) -> str | None:
    if el is None:
        return None
    t = re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()
    return t or None


def parse_search_page(html: str, prefecture_id: int) -> SearchPage:
    soup = BeautifulSoup(html, "html.parser")
    m = _COUNT.search(soup.get_text(" "))
    total = int(m.group(3)) if m else None
    first, last = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    table = soup.select_one("table.result_tbl")
    out: list[Listing] = []
    if table is None:
        return SearchPage(out, total if total is not None else 0, first, last)
    lot: dict = {}
    for tr in table.select("tbody > tr"):
        name_td = tr.select_one("td.parking_name_col")
        if name_td is not None:  # first row of a new lot (rowspan group)
            mb = name_td.select_one(".map_btn")
            addr = name_td.select_one(".address span")
            lot = {
                "lot_name": _txt(name_td.select_one(".parking_name")),
                "address": _txt(addr),
                "lat": parse_coord(mb.get("data-lat")) if mb else None,
                "lng": parse_coord(mb.get("data-lng")) if mb else None,
                "prefecture_name": mb.get("data-prefecture-name") if mb else None,
            }
        a = tr.select_one("td.detal_btn_col a[href]")
        mid = re.search(r"/parking/detail/(\d+)", a["href"]) if a else None
        if not mid:
            log.warning("row without detail id skipped")
            continue
        prices = tr.select("td.price_col")
        rent_el = prices[0].select_one("b.price") if prices else None
        av = tr.select_one("td.availability_col span")
        label = _txt(av)
        lid = mid.group(1)
        out.append(Listing(
            listing_id=lid,
            prefecture_id=prefecture_id,
            monthly_rent_yen=parse_yen(_txt(rent_el)),
            deposit_yen=parse_yen(_txt(prices[1])) if len(prices) > 1 else None,
            key_money_yen=parse_yen(_txt(prices[2])) if len(prices) > 2 else None,
            vehicle_type=_txt(tr.select_one("td.vertical_type_col")),
            contract_type=_txt(tr.select_one("td.contract_type_col")),
            equipment=[_txt(li) for li in tr.select("td.eq_col li") if _txt(li)],
            size_note=None if _txt(tr.select_one("td.vertical_size_col")) in (None, "—") else _txt(tr.select_one("td.vertical_size_col")),
            vacancy_label=label,
            vacancy_status=monthly_vacancy(label),
            source_url=config.SWEET_DETAIL.format(listing_id=lid),
            **lot,
        ))
    return SearchPage(out, total, first, last)


def crawl(client: PoliteClient, prefectures: list[int] | None = None) -> Iterator[tuple[int, int, SearchPage]]:
    """Yield (prefecture_id, page_no, SearchPage) for every result page."""
    for pid in prefectures or list(config.PREFECTURES):
        page_no, pages = 1, 1
        while page_no <= pages:
            html = client.get(config.SWEET_SEARCH, {"prefectureId": pid, "pageSize": config.PAGE_SIZE, "page": page_no})
            sp = parse_search_page(html, pid)
            pages = max(1, math.ceil((sp.total or 0) / config.PAGE_SIZE))
            yield pid, page_no, sp
            page_no += 1
