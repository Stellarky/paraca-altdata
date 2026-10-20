import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Props } from "./common";
import { Card, Legend, SortTable, Stat, Tip } from "../components/ui";
import { jst, num, pct } from "../format";
import { REPO } from "../data";

const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const ST: Record<string, string> = { available: "空", crowded: "混", full: "満" };
const STC: Record<string, string> = { available: "var(--avail)", crowded: "var(--nearly)", full: "var(--full)" };

export function Traffic({ d, area }: Props) {
  const s = d.panel?.status ?? { field: null, times: null };
  const f = s.field, t = s.times;
  const areaName = (id: string) => d.panel?.areas.find((a) => a.id === id)?.name ?? (id === "all" ? "All areas" : id === "other" ? "Outside markets" : id);
  const tSeries = t ? (t.areas[area]?.series ?? t.areas["all"]?.series ?? []) : [];
  const tLatest = tSeries[tSeries.length - 1];
  return (
    <section className="sec" id="traffic">
      <h2>Parking traffic: 空 / 混 / 満</h2>
      <p className="sec-intro">How busy lots are right now, on the same three levels Times uses. Paraca's own lot signs are not published anywhere that allows automated collection, so this section draws on three permitted sources. Each switches on by itself once it has data.</p>
      <div className="grid g3">
        <SourceCard n="1" title="Field checks at Paraca lots" on={!!f}
          body={f ? `${num(f.checks)} checks at ${num(f.lots)} lots by ${num(f.observers)} observers; latest ${jst(f.latest)}.` :
            "You and the seminar record 空/混/満 (or occupied ÷ total spaces) at Paraca lots, on a phone. Every hourly run reads the sheet."}
          how={<>Add rows to <a href={`${REPO}/blob/main/data/field_checks.csv`} target="_blank" rel="noreferrer">data/field_checks.csv</a>, or link a Google Form sheet (see <a href={`${REPO}/blob/main/docs/field_check.md`} target="_blank" rel="noreferrer">docs/field_check.md</a>).</>} />
        <SourceCard n="2" title="Times lots next to Paraca lots" on={!!t}
          body={t ? `${num(t.times_lots_near_paraca)} Times lots within ${t.nearby_m} m of a known Paraca lot, from the Times panel's export.` :
            "Busy share of Times lots within a 300 m walk of Paraca lots: a real reading of local parking traffic, labelled as Times, never as Paraca."}
          how={<>Set the repository variable <span className="mono">TIMES_SNAPSHOTS_URL</span> to the Times panel's <span className="mono">exports/parking_snapshots.csv</span>.</>} />
        <SourceCard n="3" title="Licensed feed (iPosNet / Paraca)" on={false}
          body="Paraca's own 満空 signals for part of its network are carried by iPosNet (日新電子サービス). A licence or Paraca's permission would make this the main source."
          how={<>Request letters are drafted in <a href={`${REPO}/blob/main/docs/feasibility.md`} target="_blank" rel="noreferrer">docs/feasibility.md</a>. The table is ready: <span className="mono">hourly_observations</span>.</>} />
      </div>
      {t && (
        <div className="grid g2">
          <Card title={`Nearby Times lots · ${areaName(t.areas[area] ? area : "all")}`} note={`Capacity-weighted busy share (混 + 満) and full share (満) of Times lots within ${t.nearby_m} m of a Paraca lot, at each Times snapshot.`}>
            <div className="strip">
              <Stat value={pct(tLatest?.busy)} label="busy now" /><Stat value={pct(tLatest?.full)} label="full now" /><Stat value={num(tLatest?.n)} label="Times lots read" />
            </div>
            <div style={{ height: 240, marginTop: 10 }}>
              <ResponsiveContainer>
                <LineChart data={tSeries.map((x) => ({ ...x, label: jst(x.t).slice(5, 16) }))} margin={{ right: 12 }}>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="label" tickLine={false} axisLine={false} minTickGap={50} />
                  <YAxis domain={[0, 1]} tickFormatter={(v) => pct(v, 0)} tickLine={false} axisLine={false} width={46} />
                  <Tooltip content={<Tip fmt={(v: number) => pct(v)} />} />
                  <Line dataKey="busy" name="Busy (混+満)" stroke="var(--series-1)" strokeWidth={2} dot={false} />
                  <Line dataKey="full" name="Full (満)" stroke="var(--full)" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <Legend items={[{ label: "Busy (混+満)", color: "var(--series-1)" }, { label: "Full (満)", color: "var(--full)" }]} />
          </Card>
          <Card title="By market" note="Latest busy share of Times lots near Paraca lots, per market.">
            <SortTable rows={Object.entries(t.areas).map(([a, v]) => ({ a, ...v.series[v.series.length - 1] }))} rowKey={(r) => r.a} initial={{ key: "b", dir: -1 }} cols={[
              { key: "a", label: "Market", render: (r) => areaName(r.a) },
              { key: "b", label: "Busy", right: true, sort: (r) => r.busy, render: (r) => pct(r.busy) },
              { key: "f", label: "Full", right: true, sort: (r) => r.full, render: (r) => pct(r.full) },
              { key: "n", label: "Lots", right: true, render: (r) => num(r.n) },
            ]} />
          </Card>
        </div>)}
      {f && (
        <div className="grid g2">
          <Card title="Field checks: when it is busy" note="Average busy share (混 + 満) of field checks by day and hour (JST).">
            <Heat cells={f.heat} />
            {f.occupancy != null && <p className="foot-note">Where counted, {pct(f.occupancy)} of spaces were occupied.</p>}
          </Card>
          <Card title="Latest field checks">
            <SortTable rows={f.recent} rowKey={(r) => r.observed_utc + r.lot_name + r.observer} max={50} cols={[
              { key: "t", label: "Time (JST)", render: (r) => jst(r.observed_utc) },
              { key: "l", label: "Lot", render: (r) => <>{r.lot_name}{r.operator !== "paraca" && <span className="muted small"> · {r.operator}</span>}</> },
              { key: "a", label: "Market", render: (r) => r.area_id ? areaName(r.area_id) : "—" },
              { key: "s", label: "Status", render: (r) => <span className="pillst"><span className="dot" style={{ background: STC[r.status] }} />{ST[r.status]}</span> },
              { key: "o", label: "Occupied", right: true, render: (r) => r.total ? `${r.occupied ?? "—"} / ${r.total}` : "—" },
            ]} />
          </Card>
        </div>)}
    </section>
  );
}

function SourceCard({ n, title, on, body, how }: { n: string; title: string; on: boolean; body: string; how: React.ReactNode }) {
  return (
    <div className={on ? "card" : "unavail"}>
      <span className="tag" style={{ margin: 0 }}>{on ? "● Live" : `Source ${n} · not connected yet`}</span>
      <h3 style={{ margin: "10px 0 6px", fontSize: 17 }}>{title}</h3>
      <p className="muted" style={{ margin: "0 0 10px", fontSize: 14.5 }}>{body}</p>
      <p className="small" style={{ margin: 0, color: "var(--text-secondary)" }}>{how}</p>
    </div>
  );
}

function Heat({ cells }: { cells: { dow: number; hour: number; busy: number | null; n: number }[] }) {
  const hours = Array.from(new Set(cells.map((c) => c.hour))).sort((a, b) => a - b);
  const get = (d: number, h: number) => cells.find((c) => c.dow === d && c.hour === h);
  const shade = (b: number | null | undefined) => b == null ? "var(--surface-2)" : `color-mix(in srgb, var(--series-1) ${Math.round(15 + b * 85)}%, var(--surface-2))`;
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ borderCollapse: "separate", borderSpacing: 3, fontSize: 13 }}>
        <thead><tr><th />{hours.map((h) => <th key={h} className="muted" style={{ fontWeight: 400 }}>{h}:00</th>)}</tr></thead>
        <tbody>{DOW.map((dn, d) => (
          <tr key={dn}><td className="muted" style={{ paddingRight: 8 }}>{dn}</td>
            {hours.map((h) => { const c = get(d, h); return <td key={h} title={c ? `${pct(c.busy)} busy · ${c.n} checks` : "no checks"} style={{ width: 44, height: 24, borderRadius: 4, background: shade(c?.busy) }} />; })}
          </tr>))}</tbody>
      </table>
    </div>
  );
}
