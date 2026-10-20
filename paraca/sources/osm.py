"""OpenStreetMap car parks tagged as Paraca (open data, ODbL; attribution required).

Queried through the public Overpass API in one request per run (well within
its usage policy). Coverage depends on volunteer mapping and is incomplete.
"""
from __future__ import annotations

import json
import logging

from ..http import PoliteClient

log = logging.getLogger(__name__)

OVERPASS = "https://overpass-api.de/api/interpreter"
QUERY = """
[out:json][timeout:180];
area["ISO3166-1"="JP"][admin_level=2]->.jp;
(
  nwr["amenity"~"^(parking|parking_space)$"]["operator"~"パラカ|Paraca|PARACA",i](area.jp);
  nwr["amenity"~"^(parking|parking_space)$"]["name"~"パラカ|Paraca|PARACA",i](area.jp);
  nwr["amenity"~"^(parking|parking_space)$"]["brand"~"パラカ|Paraca|PARACA",i](area.jp);
);
out center tags;
"""


def fetch(client: PoliteClient) -> list[dict]:
    r = client.s.post(OVERPASS, data={"data": QUERY}, timeout=240)
    client.requests_made += 1
    r.raise_for_status()
    out = []
    for e in r.json().get("elements", []):
        lat = e.get("lat") or (e.get("center") or {}).get("lat")
        lng = e.get("lon") or (e.get("center") or {}).get("lon")
        t = e.get("tags", {})
        cap = t.get("capacity")
        out.append({"osm_id": f"{e['type']}/{e['id']}", "name": t.get("name"), "operator": t.get("operator"),
                    "lat": lat, "lng": lng, "capacity": int(cap) if cap and str(cap).isdigit() else None,
                    "tags": json.dumps(t, ensure_ascii=False)})
    return out
