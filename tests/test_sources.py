from paraca.sources.owned import parse_date, parse_list_page, parse_release_text


def test_release_date_formats():
    assert parse_date("令和8年9月3日") == "2026-09-03"
    assert parse_date("令和元年10月1日") == "2019-10-01"
    assert parse_date("平成20年7月4日") == "2008-07-04"
    assert parse_date("2026年10月5日PR情報") == "2026-10-05"
    assert parse_date("none") is None


from pathlib import Path
from paraca.sources.owned import parse_totals

FIX = Path(__file__).parent / "fixtures"


def _lots(name, date):
    return parse_release_text((FIX / name).read_text(encoding="utf-8"), date)


def test_release_2008_no_dates_uses_release_month():
    lots = _lots("pr_2008.txt", "2008-07-04")
    assert [(l.lot_name, l.address, l.spaces) for l in lots] == [("いわき市平第1", "福島県いわき市平字田町73-1", 10)]
    assert lots[0].open_date == "2008-07-04" and "date_from_release" in lots[0].flags
    assert parse_totals((FIX / "pr_2008.txt").read_text()) == (85, 2145)


def test_release_2024_all_blocks_flags_and_dates():
    lots = _lots("pr_2024_07.txt", "2024-07-02")
    assert len(lots) == 7 and sum(l.spaces for l in lots) == 13 + 5 + 2 + 46 + 6 + 17 + 44
    first = lots[0]
    assert (first.lot_name, first.open_date) == ("秋田市中通第4", "2024-06-24") and "acq_2024-05-13" in first.flags
    assert sum("converted_from_leased" in l.flags for l in lots) == 4
    assert "bicycle" in lots[-1].flags
    assert not any("港区" in l.address and "愛宕" in l.address for l in lots)       # no letterhead rows


def test_release_2025_and_totals():
    lots = _lots("pr_2025.txt", "2025-01-07")
    assert [l.lot_name for l in lots] == ["新潟市西堀第12", "名古屋市中区金山第4", "札幌市麻生町第3", "川崎市新丸子町第2"]
    assert [l.open_date for l in lots] == ["2024-12-03", "2024-12-09", "2024-12-10", "2024-12-25"]
    assert parse_totals((FIX / "pr_2025.txt").read_text()) == (305, 5435)


def test_release_2013_fullwidth_digits():
    lots = _lots("pr_2013.txt", "2013-03-21")
    assert lots[0].lot_name == "大阪市松崎町第1" and lots[0].spaces == 7


def test_list_page_filters_lot_releases():
    html = """<a href="https://paraca.co.jp/x/20261005_ir_pr.pdf">2026年10月5日PR情報 保有駐車場オープンのお知らせ</a>
    <a href="https://paraca.co.jp/news/1700/">2026年10月5日 山林取得のお知らせ</a>
    <a href="https://paraca.co.jp/x/20080704_ir_pr_01.pdf">2008年7月4日PR情報 6月自社物件 取得・オープン状況</a>
    <a href="https://paraca.co.jp/news/pr/page/15/">15</a>"""
    rel, last = parse_list_page(html)
    assert [r.release_date for r in rel] == ["2026-10-05", "2008-07-04"] and last == 15
