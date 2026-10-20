"""Static configuration: sources, politeness limits and market (area) definitions.

Everything here is configuration, not observed data. Area centres are station /
district reference points chosen to mirror the Times (Park24) reference panel.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

OPERATOR = "paraca"
OPERATOR_NAME = "Paraca Inc. (TSE 4809)"

# --- Source: Paraca's own monthly-parking portal --------------------------------
SWEET_BASE = "https://sweet.paraca.co.jp"
SWEET_SEARCH = SWEET_BASE + "/parking/search"
SWEET_DETAIL = SWEET_BASE + "/parking/detail/{listing_id}"
SWEET_SOURCE_NAME = "sweet.paraca.co.jp (Paraca monthly-parking search)"
PAGE_SIZE = 50  # largest page size the portal offers

# --- Politeness ------------------------------------------------------------------
USER_AGENT = os.environ.get(
    "PARACA_USER_AGENT",
    "paraca-altdata/1.0 (academic equity research; contact: kyleiwami@gmail.com; "
    "+https://github.com/Stellarky/paraca-altdata)",
)
MIN_INTERVAL_SECONDS = float(os.environ.get("PARACA_MIN_INTERVAL", "3.0"))
TIMEOUT_SECONDS = float(os.environ.get("PARACA_TIMEOUT", "30"))
MAX_RETRIES = int(os.environ.get("PARACA_MAX_RETRIES", "3"))
# Hard cap so a parser bug can never turn into a request flood.
MAX_REQUESTS_PER_RUN = int(os.environ.get("PARACA_MAX_REQUESTS", "200"))

PREFECTURES = {
    1: "北海道", 2: "青森県", 3: "岩手県", 4: "宮城県", 5: "秋田県", 6: "山形県", 7: "福島県",
    8: "茨城県", 9: "栃木県", 10: "群馬県", 11: "埼玉県", 12: "千葉県", 13: "東京都", 14: "神奈川県",
    15: "新潟県", 16: "富山県", 17: "石川県", 18: "福井県", 19: "山梨県", 20: "長野県", 21: "岐阜県",
    22: "静岡県", 23: "愛知県", 24: "三重県", 25: "滋賀県", 26: "京都府", 27: "大阪府", 28: "兵庫県",
    29: "奈良県", 30: "和歌山県", 31: "鳥取県", 32: "島根県", 33: "岡山県", 34: "広島県", 35: "山口県",
    36: "徳島県", 37: "香川県", 38: "愛媛県", 39: "高知県", 40: "福岡県", 41: "佐賀県", 42: "長崎県",
    43: "熊本県", 44: "大分県", 45: "宮崎県", 46: "鹿児島県", 47: "沖縄県",
}


@dataclass(frozen=True)
class Area:
    area_id: str
    name: str
    name_ja: str
    lat: float
    lng: float
    radius_km: float
    panel: str = "matched"  # "matched" = same market as the Times reference panel


DEFAULT_RADIUS_KM = float(os.environ.get("PARACA_AREA_RADIUS_KM", "2.5"))

# Matched panel: the 16 markets used by the Times reference dashboard.
AREAS: list[Area] = [
    Area("tokyo_central", "Central Tokyo (Roppongi/Akasaka/Aoyama)", "六本木・赤坂・青山", 35.6655, 139.7320, DEFAULT_RADIUS_KM),
    Area("osaka_umeda", "Osaka Umeda", "梅田", 34.7025, 135.4959, DEFAULT_RADIUS_KM),
    Area("osaka_namba", "Osaka Namba", "難波", 34.6666, 135.5011, DEFAULT_RADIUS_KM),
    Area("nagoya_sakae", "Nagoya Sakae", "栄", 35.1709, 136.9084, DEFAULT_RADIUS_KM),
    Area("fukuoka_tenjin", "Fukuoka Tenjin", "天神", 33.5911, 130.3989, DEFAULT_RADIUS_KM),
    Area("kobe_sannomiya", "Kobe Sannomiya", "三宮", 34.6950, 135.1955, DEFAULT_RADIUS_KM),
    Area("kyoto_kawaramachi", "Kyoto Kawaramachi", "河原町", 35.0037, 135.7690, DEFAULT_RADIUS_KM),
    Area("setagaya_sangenjaya", "Setagaya / Sangenjaya", "世田谷・三軒茶屋", 35.6436, 139.6714, DEFAULT_RADIUS_KM),
    Area("yokohama_station", "Yokohama Station", "横浜駅", 35.4658, 139.6223, DEFAULT_RADIUS_KM),
    Area("omiya_station", "Omiya Station", "大宮駅", 35.9063, 139.6240, DEFAULT_RADIUS_KM),
    Area("funabashi_station", "Funabashi Station", "船橋駅", 35.7017, 139.9853, DEFAULT_RADIUS_KM),
    Area("tachikawa", "Tachikawa", "立川", 35.6980, 139.4136, DEFAULT_RADIUS_KM),
    Area("koshigaya", "Koshigaya", "越谷", 35.8911, 139.7909, DEFAULT_RADIUS_KM),
    Area("sendai", "Sendai", "仙台", 38.2601, 140.8822, DEFAULT_RADIUS_KM),
    Area("sapporo", "Sapporo", "札幌", 43.0687, 141.3508, DEFAULT_RADIUS_KM),
    Area("hiroshima", "Hiroshima", "広島", 34.3976, 132.4751, DEFAULT_RADIUS_KM),
]

# Minimum number of distinct lots before a market is shown on the dashboard.
MIN_LOTS_TO_DISPLAY = int(os.environ.get("PARACA_MIN_LOTS", "1"))
