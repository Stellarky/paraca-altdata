import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Props } from "./common";
import { Card, Legend, SortTable, Tip } from "../components/ui";
import { jst, num, signedPct, yen } from "../format";

const COLORS = ["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--series-4)", "var(--muted, #888)"];
const sp = (v: number | null | undefined) => (v == null ? "—" : signedPct(v));

/* ---------------- Agent debate ---------------- */
export function Debate({ d }: Props) {
  const db = d.debate, st = d.agentState;
  if (!db) return (
    <section className="sec" id="debate"><h2>Agent debate</h2>
      <div className="callout">The daily debate appears here after its first run on the collector.</div></section>);
  const r1 = db.debate.round1, r2 = db.debate.round2, dec = db.decision;
  const hist = (st?.history ?? []).map((h: any) => ({ ...h, d: h.d.slice(5) }));
  return (
    <section className="sec" id="debate">
      <h2>Agent debate</h2>
      <p className="sec-intro">Every day three agents argue Paraca's value from different evidence, rebut one another and revise.
        A judge weights them by confidence, and <b>fixed thresholds</b> decide whether the published target and rating actually change.</p>
      <div className="strip">
        <div className="stat"><b>{yen(dec.published_target)}</b><span>Published target · {dec.target_changed ? "updated today" : "held"}</span></div>
        <div className="stat"><b>{dec.published_rating}</b><span>Rating{dec.rating_changed ? " · changed today" : ""}</span></div>
        <div className="stat"><b>{yen(db.observation.price)}</b><span>Share price · {db.observation.price_date}</span></div>
        <div className="stat"><b>{sp(dec.expected_return)}</b><span>Expected return vs {sp(dec.required_return)} required</span></div>
        <div className="stat"><b>{yen(db.debate.combined_target)}</b><span>Combined view · spread {db.debate.spread_pct}%</span></div>
      </div>
      <div className="grid g3">
        {r2.map((a: any, i: number) => (
          <Card key={a.agent} title={a.title} right={<span className="mono small">conf {a.confidence.toFixed(2)}</span>}>
            <div className="big"><b>{yen(a.target)}</b><span>after rebuttal ({a.moved >= 0 ? "+" : "−"}{yen(Math.abs(a.moved)).slice(1)} from {yen(r1[i].target)})</span></div>
            <p className="small" style={{ margin: "10px 0 6px" }}><span className="muted">Round 1 · </span>{r1[i].argument}</p>
            <p className="small" style={{ margin: 0 }}><span className="muted">Round 2 · </span>{a.rebuttal}</p>
          </Card>))}
      </div>
      <div className="grid g2">
        <Card title="Decision rules applied today" note={`Run ${jst(db.generated_utc)}`}>
          <ul className="timeline">{dec.rules_applied.map((r: string) => <li key={r}>{r}</li>)}</ul>
          <p className="foot-note">Thresholds: target moves only on a ≥{db.thresholds.target_change_pct}% change or a new 決算短信; rating bands ±{db.thresholds.rating_band_pp}pp around the required return,
            confirmed on {db.thresholds.rating_confirm_days} days; hold if agents are &gt;{db.thresholds.max_spread_pct}% apart.</p>
        </Card>
        <Card title="Published target over time" note="Combined view (dashed) against the published target, which moves only when a threshold is crossed.">
          {hist.length < 2 ? <div className="small muted">The line starts after the second daily run.</div> :
            <div style={{ height: 220 }}><ResponsiveContainer>
              <LineChart data={hist} margin={{ left: 4, right: 12 }}>
                <CartesianGrid vertical={false} /><XAxis dataKey="d" tickLine={false} axisLine={false} />
                <YAxis domain={["auto", "auto"]} tickFormatter={(v) => yen(v)} width={70} tickLine={false} axisLine={false} />
                <Tooltip content={<Tip fmt={(v: number) => yen(v)} />} />
                <Line dataKey="target" name="Published" stroke="var(--series-1)" strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line dataKey="combined" name="Combined" stroke="var(--series-2)" strokeDasharray="4 3" dot={false} isAnimationActive={false} />
                <Line dataKey="price" name="Share price" stroke="var(--series-3)" dot={false} isAnimationActive={false} />
              </LineChart></ResponsiveContainer></div>}
        </Card>
      </div>
    </section>
  );
}

/* ---------------- Outside-in signals ---------------- */
export function Signals({ d }: Props) {
  const s = d.signals;
  if (!s) return (
    <section className="sec" id="signals"><h2>Outside-in signals</h2>
      <div className="callout">Market, weather, satellite and attention data appear here after the first daily refresh.</div></section>);
  const errs = Object.entries(s.errors ?? {});
  return (
    <section className="sec" id="signals">
      <h2>Outside-in signals</h2>
      <p className="sec-intro">Independent data refreshed daily: the market's view of Paraca against its peers, weather in every panel market,
        <b> satellite night-light activity</b>, and public attention. None of these is calibrated against revenue yet; they are context for the debate.</p>
      {errs.length > 0 && <div className="callout small">Not refreshed today: {errs.map(([k, v]) => `${k} (${String(v).slice(0, 60)})`).join(" · ")}. Showing the last good data where available.</div>}
      <MarketCard s={s} />
      <div className="grid g2"><WeatherCard s={s} /><SatelliteCard s={s} /></div>
      <AttentionCard s={s} />
    </section>
  );
}

function MarketCard({ s }: { s: any }) {
  const m = s.market;
  if (!m) return null;
  const syms = Object.keys(m.series);
  const base: Record<string, number> = {};
  const byDate: Record<string, any> = {};
  const start = m.series["4809.jp"]?.slice(-120)[0]?.d;
  syms.forEach((k) => m.series[k].filter((r: any) => !start || r.d >= start).forEach((r: any) => {
    base[k] ??= r.c; (byDate[r.d] ??= { d: r.d })[k] = +(100 * r.c / base[k]).toFixed(1);
  }));
  const rows = Object.values(byDate).sort((a: any, b: any) => a.d.localeCompare(b.d));
  return (
    <Card title="Share price vs peers" note="Rebased to 100 about six months ago (Stooq daily closes).">
      <div style={{ height: 260 }}><ResponsiveContainer>
        <LineChart data={rows} margin={{ left: 0, right: 12 }}>
          <CartesianGrid vertical={false} /><XAxis dataKey="d" tickFormatter={(v) => v.slice(5)} minTickGap={40} tickLine={false} axisLine={false} />
          <YAxis domain={["auto", "auto"]} width={40} tickLine={false} axisLine={false} />
          <Tooltip content={<Tip fmt={(v: number) => num(v, 1)} />} />
          {syms.map((k, i) => <Line key={k} dataKey={k} name={m.names[k]} stroke={COLORS[i]} strokeWidth={k === "4809.jp" ? 2.5 : 1.4} dot={false} isAnimationActive={false} />)}
        </LineChart></ResponsiveContainer></div>
      <Legend items={syms.map((k, i) => ({ label: m.names[k], color: COLORS[i] }))} />
      <SortTable rows={syms.map((k) => ({ k, ...m.perf[k] }))} rowKey={(r: any) => r.k} cols={[
        { key: "n", label: "Company", sort: (r: any) => r.name, render: (r: any) => r.name },
        { key: "l", label: "Last", right: true, render: (r: any) => num(r.last, 0) },
        { key: "a", label: "1 month", right: true, sort: (r: any) => r.r20, render: (r: any) => sp(r.r20) },
        { key: "b", label: "3 months", right: true, sort: (r: any) => r.r60, render: (r: any) => sp(r.r60) },
        { key: "c", label: "1 year", right: true, sort: (r: any) => r.r250, render: (r: any) => sp(r.r250) },
      ]} />
    </Card>);
}

function WeatherCard({ s }: { s: any }) {
  const w = s.weather;
  if (!w) return null;
  return (
    <Card title="Weather in Paraca's markets" note={`Quarter to date (from ${w.quarter_start}) against the same days last year, and the next 7 days. Snow matters most in the northern strongholds.`}>
      <SortTable rows={w.areas} rowKey={(r: any) => r.id} initial={{ key: "sn", dir: -1 }} max={30} cols={[
        { key: "n", label: "Market", sort: (r: any) => r.name, render: (r: any) => <span>{r.name}{r.panel === "paraca" && <span className="muted small"> · stronghold</span>}</span> },
        { key: "r", label: "Rain QTD", right: true, sort: (r: any) => r.qtd.rain_mm, render: (r: any) => `${num(r.qtd.rain_mm)} mm` },
        { key: "ry", label: "vs LY", right: true, sort: (r: any) => r.qtd.rain_mm - r.qtd_last_year.rain_mm, render: (r: any) => { const x = r.qtd.rain_mm - r.qtd_last_year.rain_mm; return <span className={x > 0 ? "up" : "down"}>{x >= 0 ? "+" : "−"}{num(Math.abs(x))}</span>; } },
        { key: "sn", label: "Snow QTD", right: true, sort: (r: any) => r.qtd.snow_cm, render: (r: any) => `${num(r.qtd.snow_cm, 1)} cm` },
        { key: "n7", label: "Next 7d", right: true, sort: (r: any) => r.next7.rain_mm + r.next7.snow_cm, render: (r: any) => `${num(r.next7.rain_mm)} mm${r.next7.snow_cm ? ` · ${num(r.next7.snow_cm, 1)} cm` : ""}` },
      ]} />
    </Card>);
}

function SatelliteCard({ s }: { s: any }) {
  const sat = s.satellite;
  if (!sat) return null;
  return (
    <Card title="Satellite night lights" note={sat.note}>
      <SortTable rows={sat.areas} rowKey={(r: any) => r.id} initial={{ key: "c", dir: -1 }} max={30} cols={[
        { key: "n", label: "Market", sort: (r: any) => r.name, render: (r: any) => <span>{r.name}{r.panel === "paraca" && <span className="muted small"> · stronghold</span>}</span> },
        { key: "m7", label: "7-day median", right: true, sort: (r: any) => r.median_7d, render: (r: any) => num(r.median_7d, 1) },
        { key: "m30", label: "30-day", right: true, sort: (r: any) => r.median_30d, render: (r: any) => num(r.median_30d, 1) },
        { key: "c", label: "Change", right: true, sort: (r: any) => r.change_pct, render: (r: any) => r.change_pct == null ? <span className="muted">building</span> : <span className={r.change_pct > 0 ? "up" : "down"}>{r.change_pct > 0 ? "+" : ""}{r.change_pct}%</span> },
        { key: "d", label: "Nights", right: true, sort: (r: any) => r.days, render: (r: any) => r.days },
      ]} />
      <p className="foot-note">Source: NASA GIBS, layer {sat.layer}.</p>
    </Card>);
}

function AttentionCard({ s }: { s: any }) {
  const a = s.attention?.articles;
  if (!a) return null;
  const names = Object.keys(a).filter((k) => Array.isArray(a[k]) && a[k].length);
  if (!names.length) return null;
  const byDate: Record<string, any> = {};
  names.forEach((k) => a[k].forEach((r: any) => { (byDate[r.d] ??= { d: r.d })[k] = r.v; }));
  const rows = Object.values(byDate).sort((x: any, y: any) => x.d.localeCompare(y.d));
  return (
    <Card title="Public attention" note={s.attention.note}>
      <div style={{ height: 220 }}><ResponsiveContainer>
        <LineChart data={rows} margin={{ left: 0, right: 12 }}>
          <CartesianGrid vertical={false} /><XAxis dataKey="d" tickFormatter={(v) => v.slice(5)} minTickGap={40} tickLine={false} axisLine={false} />
          <YAxis width={40} tickLine={false} axisLine={false} />
          <Tooltip content={<Tip fmt={(v: number) => num(v)} />} />
          {names.map((k, i) => <Line key={k} dataKey={k} name={k} stroke={COLORS[i]} dot={false} isAnimationActive={false} />)}
        </LineChart></ResponsiveContainer></div>
      <Legend items={names.map((k, i) => ({ label: k, color: COLORS[i] }))} />
    </Card>);
}
