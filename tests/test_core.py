from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from paraca import finmodel
from paraca.db import connect, ingest
from paraca.fiscal import fiscal_quarter, quarter_bounds
from paraca.http import PoliteClient, RequestBudgetExceeded
from paraca.normalize import (assign_area, haversine_km, hourly_status, jst_date, lot_key, monthly_vacancy,
                              parse_fee_schedule, parse_yen, to_jst)
from paraca.sources.sweet import Listing, parse_search_page

FIX = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).parent.parent


# ------------------------------------------------------------------ parser
@pytest.fixture
def page():
    return parse_search_page((FIX / "sweet_search_tokyo_p1.html").read_text(encoding="utf-8"), 13)


def test_page_counts(page):
    assert page.total == 121 and page.first == 1 and page.last == 50
    assert [l.listing_id for l in page.listings] == ["580", "1401", "1425", "1427", "1406", "1611"]


def test_rowspan_carries_lot_fields(page):
    sakura = [l for l in page.listings if l.lot_name == "Shibuya Sakura Stage"]
    assert len(sakura) == 3
    assert all(l.lat == pytest.approx(35.656819) and l.address == "渋谷区桜丘町" for l in sakura)
    assert [l.vehicle_type for l in sakura] == ["自転車", "自動車", "自動車"]


def test_money_and_status(page):
    first = page.listings[0]
    assert first.monthly_rent_yen == 30555 and first.deposit_yen == 30555 and first.key_money_yen is None
    assert first.vacancy_status == "waitlist" and first.equipment == ["平置き", "車庫証明"] and first.size_note is None
    ginza = next(l for l in page.listings if l.listing_id == "1406")
    assert ginza.key_money_yen == 66000 and ginza.deposit_yen == 60000
    assert ginza.vacancy_status == "unknown" and ginza.vacancy_label is None   # blank cell -> unknown, not 'open'
    assert next(l for l in page.listings if l.listing_id == "1611").vacancy_status == "open"


def test_empty_page():
    sp = parse_search_page("<html><body>該当なし</body></html>", 18)
    assert sp.listings == [] and sp.total == 0


@pytest.mark.parametrize("raw,exp", [("33,000円", 33000), ("—", None), ("", None), (None, None), ("¥1,200", 1200), ("３３，０００円", 33000), ("要相談", None)])
def test_parse_yen(raw, exp):
    assert parse_yen(raw) == exp


def test_status_maps():
    assert monthly_vacancy("申込可能") == "open" and monthly_vacancy("空き待ち") == "waitlist" and monthly_vacancy("??") == "unknown"
    assert hourly_status("満車") == "full" and hourly_status("混雑") == "crowded" and hourly_status("空車") == "available"
    assert hourly_status(None) == "unknown"


# ------------------------------------------------------------------ time zones
def test_jst_conversion_crosses_midnight():
    t = datetime(2026, 10, 19, 15, 30, tzinfo=timezone.utc)
    assert to_jst(t).isoformat() == "2026-10-20T00:30:00+09:00" and jst_date(t) == "2026-10-20"


def test_naive_datetime_rejected():
    with pytest.raises(ValueError):
        to_jst(datetime(2026, 1, 1))


# ------------------------------------------------------------------ fiscal quarters
@pytest.mark.parametrize("d,label", [(date(2025, 10, 1), "FY2026 Q1"), (date(2025, 12, 31), "FY2026 Q1"), (date(2026, 1, 1), "FY2026 Q2"),
                                     (date(2026, 6, 30), "FY2026 Q3"), (date(2026, 9, 30), "FY2026 Q4"), (date(2026, 10, 1), "FY2027 Q1")])
def test_paraca_fiscal_quarter(d, label):
    assert fiscal_quarter(d).label == label


def test_park24_october_year_end():
    assert fiscal_quarter(date(2026, 10, 31), fy_end_month=10).label == "FY2026 Q4"
    assert fiscal_quarter(date(2026, 11, 1), fy_end_month=10).label == "FY2027 Q1"


def test_quarter_bounds():
    b = quarter_bounds(2026, 2)
    assert (b.start, b.end) == (date(2026, 1, 1), date(2026, 3, 31))
    assert quarter_bounds(2024, 1).start == date(2023, 10, 1)


# ------------------------------------------------------------------ fees
def test_fee_uniform_rate_and_cap():
    fs = parse_fee_schedule("全日 0:00～24:00 60分¥200 最大料金 月～金 入庫後24時間迄¥900 最大料金 土日祝 入庫後24時間迄¥1200")
    assert fs.hourly_rate_yen == 200 and fs.daily_cap_yen is None and "day_dependent_cap" in fs.flags
    assert fs.raw.startswith("全日")


def test_fee_time_varying_has_no_universal_rate():
    fs = parse_fee_schedule("全日 8:00～20:00 20分¥300 全日 20:00～8:00 60分¥100 最大料金 全日 7:00～18:00 ¥700")
    assert fs.hourly_rate_yen is None and "time_or_day_varying_rate" in fs.flags
    assert len(fs.units) == 2 and fs.caps[0]["yen"] == 700 and "has_time_window_caps" in fs.flags


def test_fee_missing():
    assert parse_fee_schedule(None).flags == ["no_fee_text"]


# ------------------------------------------------------------------ geography & identity
def test_haversine_and_area():
    assert haversine_km(35.0, 135.0, 35.0, 135.0) == 0
    assert 400 < haversine_km(35.6812, 139.7671, 34.7025, 135.4959) < 410        # Tokyo-Umeda ~403km
    assert assign_area(34.7030, 135.4960)[0] == "osaka_umeda"
    assert assign_area(36.0, 138.0) == (None, None) and assign_area(None, 1.0) == (None, None)


def test_lot_key_stable_and_normalised():
    a = lot_key("KAMEIDO CLOCK", "江東区亀戸6-31-6", 35.695893, 139.82925)
    assert a == lot_key("ＫＡＭＥＩＤＯ　ＣＬＯＣＫ", "江東区亀戸６−31−6".replace("−", "-"), 35.69589, 139.82925)
    assert a != lot_key("KAMEIDO CLOCK", "江東区亀戸6-31-6", 35.70, 139.83)


# ------------------------------------------------------------------ ingest: duplicates, changes, removals
def _l(lid, rent=10000, vac="open", name="A", lat=35.0):
    return Listing(listing_id=lid, lot_name=name, address="x", lat=lat, lng=139.0, prefecture_id=13, prefecture_name="東京都",
                   monthly_rent_yen=rent, deposit_yen=rent, key_money_yen=None, vehicle_type="自動車", contract_type="月極",
                   vacancy_label=None, vacancy_status=vac)


def test_ingest_dedup_change_and_removal(tmp_path):
    con = connect(tmp_path / "t.sqlite")
    t1 = datetime(2026, 10, 20, 1, 0, tzinfo=timezone.utc)
    s1 = ingest(con, "r1", t1, [_l("1"), _l("1"), _l("2", name="B", lat=35.1)], complete=True)
    assert s1["dupes"] == 1 and s1["lots"] == 2 and s1["new_listings"] == 2
    # same day, unchanged -> no new snapshot rows (change-log storage)
    ingest(con, "r2", t1.replace(hour=2), [_l("1"), _l("2", name="B", lat=35.1)], complete=True)
    assert con.execute("SELECT COUNT(*) FROM listing_snapshots").fetchone()[0] == 2
    # rent + vacancy change, listing 2 disappears
    ingest(con, "r3", t1.replace(hour=3), [_l("1", rent=12000, vac="waitlist")], complete=True)
    kinds = [r[0] for r in con.execute("SELECT kind FROM events ORDER BY rowid")]
    assert "rent_change" in kinds and "vacancy_change" in kinds and "listing_removed" in kinds and "lot_removed" in kinds
    assert con.execute("SELECT active FROM listings WHERE listing_id='2'").fetchone()[0] == 0


def test_partial_run_never_infers_closures(tmp_path):
    con = connect(tmp_path / "t.sqlite")
    t = datetime(2026, 10, 20, tzinfo=timezone.utc)
    ingest(con, "r1", t, [_l("1"), _l("2", name="B", lat=35.1)], complete=True)
    ingest(con, "r2", t.replace(hour=5), [_l("1")], complete=False)
    assert con.execute("SELECT active FROM listings WHERE listing_id='2'").fetchone()[0] == 1


def test_new_day_writes_heartbeat(tmp_path):
    con = connect(tmp_path / "t.sqlite")
    t = datetime(2026, 10, 20, 1, tzinfo=timezone.utc)
    ingest(con, "r1", t, [_l("1")], complete=True)
    ingest(con, "r2", t.replace(day=21), [_l("1")], complete=True)
    assert con.execute("SELECT COUNT(*) FROM listing_snapshots").fetchone()[0] == 2


# ------------------------------------------------------------------ http politeness
class _Resp:
    def __init__(self, code=200, text="ok"):
        self.status_code, self.text, self.content, self.headers, self.encoding = code, text, text.encode(), {}, "utf-8"

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(str(self.status_code))


class _Sess:
    def __init__(self, codes):
        self.codes, self.headers, self.calls = list(codes), {}, 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        return _Resp(self.codes.pop(0))


def test_client_interval_retry_and_cap():
    sleeps, clock = [], iter(range(0, 1000))
    c = PoliteClient(min_interval=3, session=_Sess([500, 200, 200]), sleep=sleeps.append, clock=lambda: next(clock), max_requests=3)
    assert c.get("http://x") == "ok"          # retried after a 500
    c.get("http://x")
    assert any(s >= 1 for s in sleeps)        # waited between requests
    with pytest.raises(RequestBudgetExceeded):
        c.get("http://x")


def test_client_stops_on_403():
    c = PoliteClient(session=_Sess([403]), sleep=lambda s: None)
    with pytest.raises(PermissionError):
        c.get("http://x")


# ------------------------------------------------------------------ financial aggregation
def test_standalone_quarters_and_totals():
    qs = finmodel.standalone_quarters(finmodel.load(ROOT / "data/financials.csv"))
    by = {(q["fy"], q["q"]): q for q in qs}
    assert by[(2025, 4)]["revenue"] == 17630 - 13059
    assert by[(2026, 2)]["revenue"] == 9142 - 4637
    fy25 = sum(by[(2025, k)]["revenue"] for k in range(1, 5))
    assert fy25 == 17630
    assert by[(2025, 3)].get("spaces_interpolated") is True        # Jun-2025 count not disclosed
    assert by[(2026, 3)]["spaces_total"] == 52199


def test_backtest_and_forecast_are_honest():
    rows = finmodel.load(ROOT / "data/financials.csv")
    qs = finmodel.standalone_quarters(rows)
    bt = finmodel.backtest(qs)
    assert bt["best"] in finmodel.MODELS and bt["models"][bt["best"]]["n"] >= 4
    nxt = finmodel.forecast_next(qs, finmodel.guidance(rows, 2026))
    assert nxt["label"] == "FY2026 Q4" and nxt["revenue_lo"] < nxt["revenue_point"] < nxt["revenue_hi"]
    assert nxt["guidance_implied_q4"] == 18700 - 13810
