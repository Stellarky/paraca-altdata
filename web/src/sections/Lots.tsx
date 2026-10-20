import { useMemo, useState } from "react";
import { Bundle, Lot } from "../data";
import { Card, SortTable, Status } from "../components/ui";
import { CT_EN, jst, median, openShare, pct, VEH_EN, yen } from "../format";

const KIND: Record<string, string> = { lot_new: "Lot first observed", listing_new: "Listing first observed", rent_change: "Rent changed",
  vacancy_change: "Vacancy changed", listing_removed: "Listing removed", lot_removed: "Lot no longer listed", lot_reappeared: "Lot listed again" };

export default function Lots({ d }: { d: Bundle }) {
  const [q, setQ] = useState("");
  const [pref, setPref] = useState("all");
  const [sel, setSel] = useState<string | null>(() => { try { return sessionStorage.getItem("lot"); } catch { return null; } });
  const prefs = useMemo(() => Array.from(new Set(d.lots.map((l) => l.pref))).sort(), [d]);
  const rows = useMemo(() => {
    const t = q.trim().toLowerCase();
    return d.lots.filter((l) => (pref === "all" || l.pref === pref) &&
      (!t || (l.name + l.addr + l.pref + (l.area ?? "")).toLowerCase().includes(t)))
      .map((l) => ({ ...l, n: l.listings.length, rent: median(l.listings.filter((x) => x.veh === "自動車").map((x) => x.rent)),
                     open: openShare(l.listings.map((x) => x.vac)) }));
  }, [d, q, pref]);
  const lot = d.lots.find((l) => l.id === sel) as Lot | undefined;
  const hist = lot ? d.events.filter((e) => e.lot_id === lot.id).sort((a, b) => b.event_utc.localeCompare(a.event_utc)) : [];
  const area = (id: string | null) => d.summary.areas.find((a) => a.id === id)?.name ?? "—";
  return (
    <>
      <div className="controls">
        <input className="search" placeholder="Search lot name, address, area…" value={q} onChange={(e) => setQ(e.target.value)} />
        <select value={pref} onChange={(e) => setPref(e.target.value)}>
          <option value="all">All prefectures</option>{prefs.map((p) => <option key={p}>{p}</option>)}
        </select>
        <span className="muted small">{rows.length} lots</span>
      </div>
      {lot && (
        <div className="drawer">
          <div className="card-h">
            <h3>{lot.name}</h3><span className="note">{lot.pref} {lot.addr}</span><span className="grow" />
            <button onClick={() => setSel(null)}>Close</button>
          </div>
          <div className="grid g2">
            <div>
              <div className="small muted" style={{ marginBottom: 8 }}>
                Lot ID <span className="mono">{lot.id}</span> · market {area(lot.area)}{lot.dist != null ? ` (${lot.dist} km)` : ""} · {lot.lat?.toFixed(5)}, {lot.lng?.toFixed(5)}<br />
                First seen {jst(lot.first)} · last seen {jst(lot.last)} · capacity not published
              </div>
              <div className="tbl-wrap"><table className="tbl"><thead><tr><th>Product</th><th className="r">Rent</th><th className="r">Deposit</th><th>Status</th><th>Source</th></tr></thead>
                <tbody>{lot.listings.map((x) => (
                  <tr key={x.id}><td>{VEH_EN[x.veh] ?? x.veh} · {CT_EN[x.ct] ?? x.ct}<div className="small muted">{[...x.eq, x.note].filter(Boolean).join(" · ")}</div></td>
                    <td className="r num">{yen(x.rent)}</td><td className="r num">{yen(x.dep)}</td><td><Status v={x.vac} /></td>
                    <td><a href={x.url} target="_blank" rel="noreferrer">#{x.id} ↗</a></td></tr>))}</tbody></table></div>
            </div>
            <div>
              <div className="small" style={{ fontWeight: 600, marginBottom: 8 }}>History</div>
              {hist.length ? <ul className="timeline">{hist.map((e, i) => (
                <li key={i}><span className="mono small muted">{jst(e.event_utc)}</span><br />{KIND[e.kind] ?? e.kind}
                  {e.listing_id ? <span className="muted"> · #{e.listing_id}</span> : null}
                  {e.kind === "rent_change" && <> · {yen(Number(e.old_value))} → {yen(Number(e.new_value))}</>}
                  {e.kind === "vacancy_change" && <> · {e.old_value} → {e.new_value}</>}</li>))}</ul>
                : <div className="muted small">No events recorded.</div>}
            </div>
          </div>
        </div>
      )}
      <Card>
        <SortTable rows={rows} rowKey={(r) => r.id} selected={sel} onRow={(r) => setSel(r.id)} initial={{ key: "pref", dir: 1 }} cols={[
          { key: "name", label: "Lot", sort: (r) => r.name, render: (r) => <><b style={{ fontWeight: 500 }}>{r.name}</b><div className="small muted">{r.addr}</div></> },
          { key: "pref", label: "Prefecture", sort: (r) => r.pref },
          { key: "area", label: "Matched market", sort: (r) => r.area ?? "~", render: (r) => r.area ? area(r.area) : <span className="muted">—</span> },
          { key: "n", label: "Listings", right: true, sort: (r) => r.n },
          { key: "rent", label: "Median car rent", right: true, sort: (r) => r.rent, render: (r) => yen(r.rent) },
          { key: "open", label: "Open", right: true, sort: (r) => r.open, render: (r) => pct(r.open, 0) },
          { key: "first", label: "First seen", sort: (r) => r.first, render: (r) => <span className="small mono">{jst(r.first, false)}</span> },
        ]} />
      </Card>
    </>
  );
}
