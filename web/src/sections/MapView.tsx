import { useMemo, useState } from "react";
import { Circle, CircleMarker, MapContainer, Popup, TileLayer, Tooltip } from "react-leaflet";
import { Bundle, Lot } from "../data";
import { CT_EN, VAC_EN, VEH_EN, yen } from "../format";

const COLORS: Record<string, string> = { open: "#0ca30c", waitlist: "#d03b3b", mixed: "#eda100", unknown: "#85837c" };

function lotStatus(l: Lot) {
  const v = new Set(l.listings.map((x) => x.vac).filter((x) => x !== "unknown"));
  if (!v.size) return "unknown";
  return v.size > 1 ? "mixed" : [...v][0];
}

export default function MapView({ d }: { d: Bundle }) {
  const [veh, setVeh] = useState("all");
  const [st, setSt] = useState("all");
  const [showAreas, setShowAreas] = useState(true);
  const lots = useMemo(() => d.lots.filter((l) => l.lat && l.lng)
    .map((l) => ({ ...l, listings: veh === "all" ? l.listings : l.listings.filter((x) => x.veh === veh) }))
    .filter((l) => l.listings.length)
    .map((l) => ({ ...l, status: lotStatus(l) }))
    .filter((l) => st === "all" || l.status === st), [d, veh, st]);
  const dark = typeof window !== "undefined" && (document.documentElement.dataset.theme === "dark" ||
    (!document.documentElement.dataset.theme && window.matchMedia?.("(prefers-color-scheme: dark)").matches));
  return (
    <>
      <div className="controls">
        <div className="seg">{[["all", "All vehicles"], ["自動車", "Car"], ["バイク", "Motorbike"], ["自転車", "Bicycle"]].map(([k, l]) =>
          <button key={k} className={veh === k ? "on" : ""} onClick={() => setVeh(k)}>{l}</button>)}</div>
        <div className="seg">{[["all", "All"], ["open", "Open"], ["mixed", "Mixed"], ["waitlist", "Waitlist"], ["unknown", "No flag"]].map(([k, l]) =>
          <button key={k} className={st === k ? "on" : ""} onClick={() => setSt(k)}>{l}</button>)}</div>
        <button className={showAreas ? "on" : ""} onClick={() => setShowAreas(!showAreas)}>Market radii</button>
        <span className="muted small">{lots.length} lots shown</span>
      </div>
      <div className="legend-row">
        {Object.entries({ open: "All listings open", mixed: "Some open", waitlist: "All waitlisted", unknown: "No vacancy flag" }).map(([k, l]) =>
          <span key={k}><span className="dot" style={{ background: COLORS[k], width: 10, height: 10 }} /> {l}</span>)}
        <span className="muted">· marker size ∝ number of listings (capacity is not published)</span>
      </div>
      <div className="mapbox">
        <MapContainer center={[35.68, 139.75]} zoom={6} scrollWheelZoom style={{ height: "100%", width: "100%" }} preferCanvas>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
            url={`https://{s}.basemaps.cartocdn.com/${dark ? "dark_all" : "light_all"}/{z}/{x}/{y}{r}.png`} />
          {showAreas && d.summary.areas.map((a) => (
            <Circle key={a.id} center={[a.lat, a.lng]} radius={a.radius_km * 1000}
              pathOptions={{ color: "#2a78d6", weight: 1, dashArray: "4 4", fillOpacity: a.lots ? 0.06 : 0.02 }}>
              <Tooltip>{a.name} · {a.lots} lots</Tooltip>
            </Circle>))}
          {lots.map((l) => (
            <CircleMarker key={l.id} center={[l.lat!, l.lng!]} radius={4 + Math.min(l.listings.length, 6) * 1.2}
              pathOptions={{ color: dark ? "#1a1a19" : "#fcfcfb", weight: 1.5, fillColor: COLORS[l.status], fillOpacity: 0.9 }}>
              <Popup>
                <b>{l.name}</b><br /><span style={{ color: "#85837c" }}>{l.pref} {l.addr}</span>
                <table style={{ marginTop: 6, borderCollapse: "collapse" }}><tbody>
                  {l.listings.map((x) => (
                    <tr key={x.id}>
                      <td style={{ paddingRight: 8 }}>{VEH_EN[x.veh] ?? x.veh} · {CT_EN[x.ct] ?? x.ct}{x.note ? <><br /><span style={{ color: "#85837c" }}>{x.note}</span></> : null}</td>
                      <td style={{ paddingRight: 8, fontFamily: "monospace" }}>{yen(x.rent)}</td>
                      <td style={{ color: COLORS[x.vac] }}>{VAC_EN[x.vac]}</td>
                    </tr>))}
                </tbody></table>
                <a href={`#lots`} onClick={() => { try { sessionStorage.setItem("lot", l.id); } catch { /* storage blocked */ } }}>Open in lot explorer →</a>
              </Popup>
            </CircleMarker>))}
        </MapContainer>
      </div>
    </>
  );
}
