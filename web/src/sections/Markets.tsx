import { Line, LineChart, ResponsiveContainer } from "recharts";
import { Bundle } from "../data";
import { Card, SortTable } from "../components/ui";
import { num, pct, yen } from "../format";

export default function Markets({ d }: { d: Bundle }) {
  const areas = [...d.summary.areas].sort((a, b) => b.listings - a.listings);
  return (
    <>
      <p className="section-intro">
        The 16 markets of the Times (Park24) reference panel, each a fixed centre with a <b>2.5 km radius</b>. Lots are matched by
        straight-line distance to the nearest centre. Markets without any Paraca listing are shown greyed and contain no
        invented data. "Open" is the monthly-contract flag, not hourly occupancy.
      </p>
      <div className="grid g4">
        {areas.map((a) => {
          const op = a.open_share;
          return (
            <div key={a.id} className={"card mcard" + (a.lots ? "" : " empty")}>
              <div className="t"><b>{a.name}</b><span>{a.ja}</span></div>
              {a.lots ? (
                <>
                  <div className="row">
                    <div><b>{a.lots}</b>lots</div>
                    <div><b>{a.listings}</b>listings</div>
                    <div><b>{yen(a.median_car_rent)}</b>median car rent</div>
                  </div>
                  <div>
                    <div className="bar-track" title={`Open ${pct(op)}`}>
                      {op != null && <i style={{ width: `${op * 100}%`, background: "var(--good)", borderRadius: "3px 0 0 3px" }} />}
                      {op != null && <i style={{ flex: 1, background: "var(--critical)", opacity: .75, borderRadius: "0 3px 3px 0" }} />}
                    </div>
                    <div className="small muted" style={{ marginTop: 4 }}>{op == null ? "No vacancy flags" : `${pct(op, 0)} open · ${pct(1 - op, 0)} waitlist`}</div>
                  </div>
                  <div style={{ height: 34 }}>
                    {a.series.length > 1 ? (
                      <ResponsiveContainer><LineChart data={a.series}><Line dataKey="open" stroke="var(--series-1)" strokeWidth={2} dot={false} isAnimationActive={false} /></LineChart></ResponsiveContainer>
                    ) : <div className="small muted">Trend appears after the second day of collection.</div>}
                  </div>
                </>
              ) : <div className="small muted">No Paraca monthly listings within {a.radius_km} km of the centre.</div>}
            </div>);
        })}
      </div>
      <Card title="Strong-presence markets" note="Second panel: every prefecture where the portal lists Paraca lots">
        <SortTable rows={d.summary.prefectures_table} rowKey={(r) => r.pref} initial={{ key: "listings", dir: -1 }}
          cols={[
            { key: "pref", label: "Prefecture", sort: (r) => r.pref },
            { key: "lots", label: "Lots", right: true, sort: (r) => r.lots, render: (r) => num(r.lots) },
            { key: "listings", label: "Listings", right: true, sort: (r) => r.listings, render: (r) => num(r.listings) },
            { key: "open", label: "Open share", right: true, sort: (r) => r.open_share, render: (r) => pct(r.open_share) },
            { key: "rent", label: "Median car rent", right: true, sort: (r) => r.median_car_rent, render: (r) => yen(r.median_car_rent) },
          ]} />
      </Card>
    </>
  );
}
