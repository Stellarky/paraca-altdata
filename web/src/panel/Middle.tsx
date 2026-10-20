import { Bar, BarChart, CartesianGrid, ComposedChart, Line, LineChart, ReferenceLine, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from "recharts";
import { Props } from "./common";
import { Card, Legend, SortTable, Stat, Tip } from "../components/ui";
import { CT_EN, mn, num, pct, signedPct, VEH_EN, yen } from "../format";

const q = (v: string) => v.replace("FY20", "FY").replace(" ", " ");

export function ByType({ d }: Props) {
  const p = d.panel!;
  const rows = p.by_type.map((r) => ({ ...r, k: `${VEH_EN[r.vehicle] ?? r.vehicle} · ${CT_EN[r.contract] ?? r.contract}` }));
  return (
    <section className="sec" id="bytype">
      <h2>By type</h2>
      <p className="sec-intro">The same listings split by vehicle and contract, and by facility. Cars on 月極 contracts are the core product; passes (パスカード) let a driver use a coin lot's free spaces at a monthly price.</p>
      <div className="grid g2">
        <Card title="Waitlist share by product" note="Share of listings with a flag that are 空き待ち.">
          <div style={{ height: 260 }}>
            <ResponsiveContainer>
              <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 30 }}>
                <CartesianGrid horizontal={false} />
                <XAxis type="number" domain={[0, 1]} tickFormatter={(v) => pct(v, 0)} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="k" width={170} tickLine={false} axisLine={false} interval={0} />
                <Tooltip cursor={{ fill: "var(--surface-2)" }} content={<Tip fmt={(v: number) => pct(v)} />} />
                <Bar dataKey="waitlist_share" name="Waitlisted" fill="var(--full)" radius={[0, 4, 4, 0]} barSize={14} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title="Rents by product" note="Monthly rent, tax included, across active listings.">
          <SortTable rows={rows} rowKey={(r) => r.k} initial={{ key: "n", dir: -1 }} cols={[
            { key: "k", label: "Product", sort: (r) => r.k },
            { key: "n", label: "Listings", right: true, sort: (r) => r.listings, render: (r) => num(r.listings) },
            { key: "m", label: "Median", right: true, sort: (r) => r.median_rent, render: (r) => yen(r.median_rent) },
            { key: "lo", label: "Range", right: true, render: (r) => r.min_rent ? `${yen(r.min_rent)}–${yen(r.max_rent).slice(1)}` : "—" },
          ]} />
        </Card>
      </div>
      <Card title="By facility" note="Self-park (自走式), mechanical (機械式) and flat (平置き) lots, and listings that allow a garage certificate (車庫証明).">
        <div className="strip">
          {p.by_facility.map((f) => <div className="stat" key={f.facility}><b>{pct(f.waitlist_share, 0)}</b><span>{f.facility} waitlisted · {f.listings} listings</span></div>)}
        </div>
      </Card>
    </section>
  );
}

export function Official({ d }: Props) {
  const f = d.financials, p = d.panel!, fc = d.forecast;
  const qs = f.quarters.filter((x) => x.revenue != null);
  const last = qs[qs.length - 1];
  const ly = qs.find((x) => x.fy === last.fy - 1 && x.q === last.q);
  const n = fc.next;
  const g = f.guidance;
  const nly = n ? qs.find((x) => x.fy === Number(n.label.slice(2, 6)) - 1 && x.q === Number(n.label.slice(-1))) : undefined;
  const dec = p.decomp.filter((x) => x.spaces != null).map((x) => ({ ...x, label: q(x.label) }));
  const yoy = p.decomp.map((x) => ({ ...x, label: q(x.label) }));
  return (
    <section className="sec" id="official">
      <h2>Paraca's official figures</h2>
      <p className="sec-intro">Quarterly 決算短信 results: revenue by parking type, operating profit, and lots and spaces in operation. These are the numbers the panel tries to anticipate. Paraca's year runs <b>October to September</b> (Park24: November to October). Paraca does not publish monthly figures.</p>
      <div className="strip">
        <Stat value={signedPct(ly ? last.revenue! / ly.revenue! - 1 : null)} label={`revenue vs year earlier · ${last.label}`} />
        <Stat value={pct(last.op_margin)} label={`operating margin (year earlier ${pct(ly?.op_margin)})`} />
        <Stat value={num(last.lots_total)} label={`lots in operation (${num(last.lots_owned)} owned)`} />
        <Stat value={num(last.spaces_total)} label={`spaces at ${last.end.slice(0, 7)}`} />
        <Stat value={yen(last.rev_per_space_day_yen)} label="revenue per space per day" />
      </div>
      <div className="grid g2">
        <Card title="This quarter so far" note={n ? `${n.label} (${n.start} to ${n.end}) ended; results are due in early November. The model estimate uses disclosed revenue and space counts only, not the panel yet.` : ""}>
          {n && <>
            <div className="strip">
              <Stat value={mn(n.revenue_point)} label={`estimated ${n.label} revenue`} />
              <Stat value={signedPct(nly?.revenue ? n.revenue_point / nly.revenue - 1 : null)} label="vs same quarter last year" />
              <Stat value={`${num(n.revenue_lo)}–${num(n.revenue_hi)}`} label="indicative band, ¥m" />
            </div>
            <p className="foot-note">Guidance implies {mn(n.guidance_implied_q4)} ({g._kind === "guidance_revised" ? `revised ${g._date}` : "initial"}: FY {mn(n.full_year_guidance)} − Q1–Q3 {mn(n.cum_q1_q3)}). Model: {n.model.replace(/_/g, " ")}, backtest error {pct(fc.backtest.models[n.model]?.mape)} over {fc.backtest.models[n.model]?.n} quarters.</p>
          </>}
        </Card>
        <Card title="Street estimates" note={<>Analyst consensus for the same quarter, typed into <span className="mono">data/street_estimates.csv</span> (quarter, metric, value, unit, source, date).</>}>
          {p.street_estimates.length ? (
            <SortTable rows={p.street_estimates} rowKey={(r) => r.quarter + r.metric + r.source} cols={["quarter", "metric", "value", "unit", "source", "date"].map((k) => ({ key: k, label: k[0].toUpperCase() + k.slice(1), right: k === "value" }))} />
          ) : <p className="muted">None entered yet. Add a row per estimate, for example FY2026 Q4 · revenue · 4,900 · ¥mn · broker or consensus source · date.</p>}
        </Card>
      </div>
      <div className="grid g2">
        <Card title="Revenue growth vs a year earlier" note="Each quarter against the same quarter a year before, total and by parking type. 0% means flat.">
          <div style={{ height: 280 }}>
            <ResponsiveContainer>
              <LineChart data={yoy} margin={{ right: 12 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="label" tickLine={false} axisLine={false} minTickGap={20} />
                <YAxis tickFormatter={(v) => pct(v, 0)} tickLine={false} axisLine={false} width={46} />
                <ReferenceLine y={0} stroke="var(--border-strong)" />
                <Tooltip content={<Tip fmt={(v: number) => signedPct(v)} />} />
                <Line dataKey="total" name="Total" stroke="var(--series-1)" strokeWidth={2} dot={{ r: 3 }} />
                <Line dataKey="revenue_leased" name="Leased (賃借)" stroke="var(--series-3)" strokeWidth={2} dot={{ r: 3 }} />
                <Line dataKey="revenue_owned" name="Owned (保有)" stroke="var(--series-2)" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <Legend items={[{ label: "Total", color: "var(--series-1)" }, { label: "Leased (賃借)", color: "var(--series-3)" }, { label: "Owned (保有)", color: "var(--series-2)" }]} />
        </Card>
        <Card title="Operating margin, this year vs last" note="Operating profit ÷ revenue each quarter, with the same quarter a year earlier.">
          <div style={{ height: 280 }}>
            <ResponsiveContainer>
              <LineChart data={yoy.filter((x) => x.margin != null)} margin={{ right: 12 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="label" tickLine={false} axisLine={false} minTickGap={20} />
                <YAxis tickFormatter={(v) => pct(v, 0)} domain={[0.1, 0.25]} ticks={[0.1, 0.15, 0.2, 0.25]} tickLine={false} axisLine={false} width={46} />
                <Tooltip content={<Tip fmt={(v: number) => pct(v)} />} />
                <Line dataKey="margin" name="This year" stroke="var(--series-1)" strokeWidth={2} dot={{ r: 3 }} />
                <Line dataKey="margin_ly" name="Year earlier" stroke="var(--avail)" strokeWidth={2} strokeDasharray="5 4" dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <Legend items={[{ label: "This year", color: "var(--series-1)" }, { label: "Year earlier", color: "var(--avail)", dashed: true }]} />
        </Card>
      </div>
      <div className="grid g2">
        <Card title="Where revenue growth comes from" note="Each quarter's revenue growth vs a year earlier, split into more spaces (average spaces in operation) and everything else (yield per space: price, occupancy, mix, ramp-up of new lots). The dot is total growth.">
          <div style={{ height: 280 }}>
            <ResponsiveContainer>
              <ComposedChart data={dec} margin={{ right: 12 }} stackOffset="sign">
                <CartesianGrid vertical={false} />
                <XAxis dataKey="label" tickLine={false} axisLine={false} />
                <YAxis tickFormatter={(v) => pct(v, 0)} ticks={[-0.2, -0.1, 0, 0.1, 0.2]} domain={[-0.2, 0.25]} tickLine={false} axisLine={false} width={46} />
                <ReferenceLine y={0} stroke="var(--border-strong)" />
                <Tooltip cursor={{ fill: "var(--surface-2)" }} content={<Tip fmt={(v: number) => signedPct(v)} />} />
                <Bar dataKey="spaces" name="More spaces" stackId="a" fill="var(--series-1)" />
                <Bar dataKey="yield_mix" name="Yield per space" stackId="a" fill="var(--series-2)" />
                <Scatter dataKey="total" name="Total" fill="var(--text-primary)" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          {p.decomp_avg && <p className="foot-note">Last {Math.min(6, dec.length)} quarters on average: total {signedPct(p.decomp_avg.total)}, of which more spaces {signedPct(p.decomp_avg.spaces)}, yield per space {signedPct(p.decomp_avg.yield_mix)}.</p>}
          <Legend sq items={[{ label: "More spaces", color: "var(--series-1)" }, { label: "Yield per space", color: "var(--series-2)" }, { label: "Total", color: "var(--text-primary)" }]} />
        </Card>
        <Card title="Revenue per space-day" note="Standalone quarterly revenue ÷ average spaces in operation ÷ days.">
          <div style={{ height: 280 }}>
            <ResponsiveContainer>
              <LineChart data={qs.filter((x) => x.rev_per_space_day_yen).map((x) => ({ ...x, label: q(x.label) }))} margin={{ right: 12 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="label" tickLine={false} axisLine={false} minTickGap={20} />
                <YAxis domain={["auto", "auto"]} tickFormatter={(v) => `¥${v}`} tickLine={false} axisLine={false} width={56} />
                <Tooltip content={<Tip fmt={(v: number) => yen(v)} />} />
                <Line dataKey="rev_per_space_day_yen" name="¥ per space-day" stroke="var(--series-1)" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="foot-note">FY2025 Q3 uses an interpolated June-2025 space count (not disclosed).</p>
        </Card>
      </div>
      <Card title="By fiscal quarter" note="Standalone quarters derived from cumulative 決算短信 figures. ¥ million.">
        <SortTable rows={[...qs].reverse()} rowKey={(r) => r.label} cols={[
          { key: "l", label: "Quarter", render: (r) => r.label },
          { key: "p", label: "Months", render: (r) => <span className="muted">{r.start.slice(0, 7)} → {r.end.slice(0, 7)}</span> },
          { key: "rev", label: "Revenue ¥m", right: true, render: (r) => num(r.revenue) },
          { key: "y", label: "vs year earlier", right: true, render: (r) => { const l = qs.find((x) => x.fy === r.fy - 1 && x.q === r.q); return signedPct(l ? r.revenue! / l.revenue! - 1 : null); } },
          { key: "op", label: "Operating profit", right: true, render: (r) => num(r.operating_profit) },
          { key: "m", label: "Margin", right: true, render: (r) => pct(r.op_margin) },
          { key: "lots", label: "Lots at end", right: true, render: (r) => num(r.lots_total) },
          { key: "sp", label: "Spaces at end", right: true, render: (r) => num(r.spaces_total) },
          { key: "s", label: "Source", render: (r) => <a href={r.source_url} target="_blank" rel="noreferrer">{r.release_date} ↗</a> },
        ]} />
        <p className="foot-note">Non-consolidated JGAAP. Lot and space counts are period-end figures stated in each report; FY2025 Q3 counts were not disclosed.</p>
      </Card>
      <Card title="Forecast backtest" note="One quarter ahead, three transparent models. Lower error is better; the best model sets the estimate above. Few observations, so treat as indicative.">
        <div className="tbl-wrap"><table className="tbl"><thead><tr><th>Model</th><th>How it works</th><th className="r">Mean abs. error</th><th className="r">Bias</th><th className="r">Quarters</th></tr></thead>
          <tbody>{Object.entries(fc.backtest.models).map(([k, m]) => (
            <tr key={k} className={fc.backtest.best === k ? "sel" : ""}><td>{k.replace(/_/g, " ")}{fc.backtest.best === k ? " ★" : ""}</td><td className="muted">{m.desc}</td>
              <td className="r">{pct(m.mape)}</td><td className="r">{signedPct(m.bias)}</td><td className="r">{m.n}</td></tr>))}</tbody></table></div>
      </Card>
    </section>
  );
}

export function Owned({ d }: Props) {
  const p = d.panel!, u = d.universe;
  if (!u) return null;
  const s = u.stats;
  return (
    <section className="sec" id="owned">
      <h2>Owned lots (保有駐車場)</h2>
      <p className="sec-intro">Paraca's distinctive asset: car parks on land it owns, which pay no rent and earn several times the gross margin of leased lots. Each month Paraca publishes the owned lots it opened, with address and spaces. This section reads all of those releases since 2008.</p>
      <div className="strip">
        <Stat value={num(s.owned_total_stated)} label={`owned lots · stated ${s.owned_total_asof}`} />
        <Stat value={num(s.owned_total_spaces_stated)} label="owned spaces" />
        <Stat value={num(p.owned.last12)} label="opened in the last 12 months" />
        <Stat value={num(s.owned_pr_rows)} label={`openings parsed from ${s.owned_releases} releases`} />
        <Stat value={num(s.owned_converted)} label="leased lots converted to owned" />
      </div>
      <div className="grid g2">
        <Card title="Owned portfolio" note="Owned lots as stated in each release. Releases start in March 2008; none were published for 2016–17.">
          <div style={{ height: 260 }}>
            <ResponsiveContainer>
              <LineChart data={u.owned_totals} margin={{ right: 12 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="d" tickFormatter={(v: string) => v.slice(0, 4)} tickLine={false} axisLine={false} minTickGap={40} />
                <YAxis tickLine={false} axisLine={false} width={40} />
                <Tooltip content={<Tip fmt={(v: number) => num(v)} />} />
                <Line dataKey="lots" name="Owned lots" stroke="var(--series-2)" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title="Openings per year" note="Owned-lot openings found in the releases, split into new sites and leased lots bought by Paraca.">
          <div style={{ height: 260 }}>
            <ResponsiveContainer>
              <BarChart data={p.owned.per_year.map((y) => ({ ...y, fresh: y.n - y.converted }))} margin={{ right: 12 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="y" tickLine={false} axisLine={false} />
                <YAxis tickLine={false} axisLine={false} width={34} />
                <Tooltip cursor={{ fill: "var(--surface-2)" }} content={<Tip />} />
                <Bar dataKey="fresh" name="New sites" stackId="o" fill="var(--series-2)" />
                <Bar dataKey="converted" name="Converted from leased" stackId="o" fill="var(--series-4)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <Legend sq items={[{ label: "New sites", color: "var(--series-2)" }, { label: "Converted from leased", color: "var(--series-4)" }]} />
        </Card>
      </div>
      <Card title="Latest openings" note="Most recent owned-lot openings with a link to each release.">
        <SortTable rows={p.owned.recent} rowKey={(r) => r.url + r.name} max={40} cols={[
          { key: "o", label: "Opened", render: (r) => r.opened },
          { key: "n", label: "Lot", render: (r) => <>{r.name}{r.converted && <span className="muted small"> · converted from leased</span>}</> },
          { key: "a", label: "Address", render: (r) => <span className="muted">{r.addr}</span> },
          { key: "s", label: "Spaces", right: true, render: (r) => num(r.spaces) },
          { key: "u", label: "Release", render: (r) => <a href={r.url} target="_blank" rel="noreferrer">PDF ↗</a> },
        ]} />
      </Card>
    </section>
  );
}
