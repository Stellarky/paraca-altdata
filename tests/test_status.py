from datetime import datetime, timezone

from paraca.db import connect
from paraca.sources.status import busy, ingest_field, match_lot, norm_status, parse_jst, status_panel

UNIVERSE = [{"id": "u00001", "lat": 35.6655, "lng": 139.7320, "name": "六本木第1", "sources": {"portal": "paraca-abc"}, "area": "tokyo_central"},
            {"id": "u00002", "lat": 34.7025, "lng": 135.4959, "name": "梅田第3", "sources": {"owned_pr": "x.pdf"}, "area": "osaka_umeda"}]


def test_status_aliases():
    assert [norm_status(s) for s in ["空", "混", "満", "空車", "満車", "混雑", "Full", "?"]] == \
        ["available", "crowded", "full", "available", "full", "crowded", "full", "unknown"]


def test_parse_jst_formats():
    assert parse_jst("2026/10/20 14:05").isoformat() == "2026-10-20T14:05:00+09:00"
    assert parse_jst("bad") is None


def test_match_by_ref_coords_and_name():
    assert match_lot({"lot_ref": "paraca-abc"}, UNIVERSE)[0] == "u00001"
    assert match_lot({"latitude": "34.70252", "longitude": "135.49595"}, UNIVERSE)[0] == "u00002"
    assert match_lot({"lot_name": "パラカ梅田第3"}, UNIVERSE)[0] == "u00002"
    assert match_lot({"lot_name": "unknown"}, UNIVERSE)[0] is None


def test_busy_is_capacity_weighted():
    assert busy([("full", 10), ("available", 30)]) == (0.25, 0.25, 2)
    assert busy([("crowded", 5), ("full", 5), ("unknown", 50)]) == (1.0, 0.5, 2)
    assert busy([]) == (None, None, 0)


def test_ingest_field_and_panel(tmp_path):
    con = connect(tmp_path / "t.sqlite")
    rows = [{"observed_at_jst": "2026-10-20 12:00", "observer": "kyle", "lot_ref": "paraca-abc", "status": "満", "total_spaces": "8"},
            {"observed_at_jst": "2026-10-20 12:10", "observer": "kyle", "lot_name": "梅田第3", "occupied_spaces": "4", "total_spaces": "10"},
            {"observed_at_jst": "", "status": "空"}]                        # rejected: no time
    r = ingest_field(con, UNIVERSE, rows)
    assert r == {"field_rows": 2, "field_rejected": 1}
    obs = con.execute("SELECT lot_id, availability_status FROM hourly_observations ORDER BY lot_id").fetchall()
    assert [tuple(x) for x in obs] == [("u00001", "full"), ("u00002", "available")]      # 4/10 -> available
    p = status_panel(con, UNIVERSE)
    assert p["field"]["checks"] == 2 and p["field"]["by_area"]["tokyo_central"]["busy"] == 1.0
    assert p["field"]["occupancy"] == 0.4 and p["times"] is None


def test_times_nearby(tmp_path):
    con = connect(tmp_path / "t.sqlite")
    con.execute("CREATE TABLE times_snapshots(lot_id TEXT, timestamp_utc TEXT, latitude REAL, longitude REAL, capacity INTEGER, status TEXT, PRIMARY KEY(lot_id, timestamp_utc))")
    ts = datetime(2026, 10, 20, 3, tzinfo=timezone.utc).isoformat()
    con.executemany("INSERT INTO times_snapshots VALUES(?,?,?,?,?,?)", [
        ("t1", ts, 35.6660, 139.7320, 10, "full"),        # ~55 m from u00001 -> counted
        ("t2", ts, 35.6656, 139.7325, 30, "available"),   # counted
        ("t3", ts, 35.7000, 139.8000, 50, "full")])       # far -> ignored
    p = status_panel(con, UNIVERSE)
    s = p["times"]["areas"]["tokyo_central"]["series"][0]
    assert p["times"]["times_lots_near_paraca"] == 2 and s["busy"] == 0.25 and s["n"] == 2
