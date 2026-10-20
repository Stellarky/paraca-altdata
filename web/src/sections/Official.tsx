import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Bundle } from "../data";
import { Card, Kpi, Legend, SortTable, Tip } from "../components/ui";
import { mn, num, pct, signedPct } from "../format";

const short = (v: string) => v.replace("FY20", "FY");

export default function Official({ d }: { d: Bundle }) {
  const f = d.financials;
  const qs = f.quarters.filter((q) => q.revenue != null);
  const last = qs[qs.length - 1];
  const ly = qs.find((q) => q.fy === last.fy - 1 && q.q === last.q);
  const annual = f.annual;
  const fy = annual[annual.length - 1];
  const g = f.guidance;
  const counts = f.quarters.filter((q) => q.spaces_total);
  return (
    <>
      <p className="section-intro">
        Paraca reports non-consolidated JGAAP results; the fiscal year ends <b>30 September</b> (Park24: 31 October), so FY2026 Q4 = Jul–Sep 2026.
        Paraca does not publish Park24-style monthly operating indicators. Standalone quarters are cumulative figures differenced; every value links to its 決算短信.
      </p>
      <div className="grid g4">
        <Kpi label={`Revenue · ${last.label}`} value={mn(last.revenue)} foot={`${signedPct(ly ? last.revenue! / ly.revenue! - 1 : null)} YoY`} />
        <Kpi label={`Operating margin · ${last.label}`} value={pct(last.op_margin)} foot={`${ly ? pct(ly.op_margin) : "—"} a year earlier`} />
        <Kpi label={`Lots / spaces · ${last.end}`} value={num(last.lots_total)} unit="lots" foot={`${num(last.spaces_total)} spaces · ${num(last.lots_owned)} owned lots`} />
        <Kpi label={`FY${f.guidance_fy} guidance (${g._kind === "guidance_revised" ? "revised " + g._date : "initial"})`} value={mn(g.revenue)}
          foot={`OP ${mn(g.operating_profit)} · NI ${mn(g.net_income)}`} />
      </div>
      <div className="grid g2">
        <Card title="Quarterly revenue by parking type" note="¥ million, standalone quarters">
          <div style={{ height: 290 }}>
            <ResponsiveContainer>
              <BarChart data={qs.filter((q) => q.revenue_leased != null)} margin={{ right: 8 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="label" tickFormatter={short} tickLine={false} axisLine={false} interval={0} angle={-35} textAnchor="end" height={46} />
                <YAxis tickLine={false} axisLine={false} width={48} tickFormatter={(v) => num(v)} />
                <Tooltip cursor={{ fill: "var(--surface-2)" }} content={<Tip fmt={(v: number) => mn(v)} />} />
                <Bar dataKey="revenue_leased" name="Leased (賃借)" stackId="a" fill="var(--series-1)" stroke="var(--surface-1)" strokeWidth={2} />
                <Bar dataKey="revenue_owned" name="Owned (保有)" stackId="a" fill="var(--series-2)" stroke="var(--surface-1)" strokeWidth={2} />
                <Bar dataKey="revenue_other" name="Other" stackId="a" fill="var(--series-3)" stroke="var(--surface-1)" strokeWidth={2} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <Legend items={[{ label: "Leased (賃借)", color: "var(--series-1)" }, { label: "Owned (保有)", color: "var(--series-2)" }, { label: "Other", color: "var(--series-3)" }]} />
        </Card>
        <Card title="Operating margin" note="Standalone quarters">
          <div style={{ height: 290 }}>
            <ResponsiveContainer>
              <LineChart data={qs} margin={{ right: 16 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="label" tickFormatter={short} tickLine={false} axisLine={false} interval={0} angle={-35} textAnchor="end" height={46} />
                <YAxis tickFormatter={(v) => pct(v, 0)} domain={[0.1, 0.25]} ticks={[0.1, 0.15, 0.2, 0.25]} tickLine={false} axisLine={false} width={44} />
                <Tooltip content={<Tip fmt={(v: number) => pct(v)} />} />
                <Line dataKey="op_margin" name="Operating margin" stroke="var(--series-1)" strokeWidth={2} dot={{ r: 4, strokeWidth: 2, fill: "var(--surface-1)" }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
      <div className="grid g2">
        <Card title="Operating spaces" note="Period end, leased vs owned">
          <div style={{ height: 270 }}>
            <ResponsiveContainer>
              <BarChart data={counts} margin={{ right: 8 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="label" tickFormatter={short} tickLine={false} axisLine={false} interval={0} angle={-35} textAnchor="end" height={46} />
                <YAxis tickLine={false} axisLine={false} width={52} tickFormatter={(v) => `${Math.round(v / 1000)}k`} />
                <Tooltip cursor={{ fill: "var(--surface-2)" }} content={<Tip fmt={(v: number) => num(v)} />} />
                <Bar dataKey="spaces_leased" name="Leased spaces" stackId="s" fill="var(--series-1)" stroke="var(--surface-1)" strokeWidth={2} />
                <Bar dataKey="spaces_owned" name="Owned spaces" stackId="s" fill="var(--series-2)" stroke="var(--surface-1)" strokeWidth={2} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <Legend items={[{ label: "Leased spaces", color: "var(--series-1)" }, { label: "Owned spaces", color: "var(--series-2)" }]} />
          <div className="small muted">FY2022 year-end counts are derived from FY2023 net additions. The June-2025 count was not disclosed and is omitted here.</div>
        </Card>
        <Card title="Owned vs leased economics" note={`FY${fy.fy}, gross profit ÷ revenue`}>
          <div className="tbl-wrap"><table className="tbl"><thead><tr><th>Type</th><th className="r">Revenue</th><th className="r">Gross profit</th><th className="r">GP margin</th><th className="r">Lots</th></tr></thead>
            <tbody>
              <tr><td>Leased (賃借)</td><td className="r num">{mn(fy.revenue_leased)}</td><td className="r num">{mn(fy.gross_profit_leased)}</td><td className="r num">{pct(fy.gross_profit_leased / fy.revenue_leased)}</td><td className="r num">{num(fy.lots_leased)}</td></tr>
              <tr><td>Owned (保有)</td><td className="r num">{mn(fy.revenue_owned)}</td><td className="r num">{mn(fy.gross_profit_owned)}</td><td className="r num">{pct(fy.gross_profit_owned / fy.revenue_owned)}</td><td className="r num">{num(fy.lots_owned)}</td></tr>
            </tbody></table></div>
          <p className="small muted" style={{ marginBottom: 0 }}>Owned lots pay no land rent, which is why their gross margin is several times the leased margin. Compare
            with Park24 with care: Park24 consolidates mobility and overseas businesses and reports a different fiscal year.</p>
        </Card>
      </div>
      {d.universe && d.universe.owned_totals.length > 0 && (
        <Card title="Owned portfolio since 2008" note="Owned lots as stated in each monthly opening release (paraca.co.jp)">
          <div style={{ height: 260 }}>
            <ResponsiveContainer>
              <LineChart data={d.universe.owned_totals} margin={{ right: 16 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="d" tickLine={false} axisLine={false} minTickGap={40} tickFormatter={(v: string) => v.slice(0, 4)} />
                <YAxis tickLine={false} axisLine={false} width={40} />
                <Tooltip content={<Tip fmt={(v: number) => num(v)} />} />
                <Line dataKey="lots" name="Owned lots" stroke="var(--series-2)" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="small muted">
            {num(d.universe.stats.owned_pr_rows)} individual openings parsed from {num(d.universe.stats.owned_releases)} releases ({num(d.universe.stats.owned_pr_spaces)} spaces;
            {" "}{num(d.universe.stats.owned_converted)} were leased lots converted to owned). The latest stated total, {num(d.universe.stats.owned_total_stated)} lots /
            {" "}{num(d.universe.stats.owned_total_spaces_stated)} spaces, matches the 決算短信. Releases start in 2008, when 81 lots were already owned, and none were published for 2016–17.
          </div>
        </Card>)}
      <Card title="Annual results" note="¥ million · source documents linked">
        <SortTable rows={annual} rowKey={(r) => String(r.fy)} initial={{ key: "fy", dir: -1 }} cols={[
          { key: "fy", label: "Fiscal year (to Sep)", sort: (r) => r.fy, render: (r) => `FY${r.fy}` },
          { key: "rev", label: "Revenue", right: true, render: (r) => mn(r.revenue) },
          { key: "op", label: "Operating profit", right: true, render: (r) => mn(r.operating_profit) },
          { key: "m", label: "OP margin", right: true, render: (r) => pct(r.operating_profit / r.revenue) },
          { key: "ni", label: "Net income", right: true, render: (r) => mn(r.net_income) },
          { key: "lots", label: "Lots", right: true, render: (r) => r.lots_total ? num(r.lots_total) + (r.derived_counts ? "*" : "") : "—" },
          { key: "sp", label: "Spaces", right: true, render: (r) => r.spaces_total ? num(r.spaces_total) + (r.derived_counts ? "*" : "") : "—" },
          { key: "src", label: "Source", render: (r) => <a href={r.source_url} target="_blank" rel="noreferrer">決算短信 {r.release_date} ↗</a> },
        ]} />
        <div className="small muted" style={{ marginTop: 6 }}>* derived from the following year's disclosed net additions. {f.notes.join(" ")}</div>
      </Card>
      <Card title="Quarterly detail" note="Standalone quarters, ¥ million">
        <SortTable rows={qs} rowKey={(r) => r.label} initial={{ key: "l", dir: -1 }} cols={[
          { key: "l", label: "Quarter", sort: (r) => r.fy * 10 + r.q, render: (r) => r.label },
          { key: "p", label: "Period", render: (r) => <span className="small mono">{r.start} → {r.end}</span> },
          { key: "rev", label: "Revenue", right: true, render: (r) => mn(r.revenue) },
          { key: "op", label: "OP", right: true, render: (r) => mn(r.operating_profit) },
          { key: "sp", label: "Spaces (end)", right: true, render: (r) => num(r.spaces_total) },
          { key: "y", label: "¥/space-day", right: true, render: (r) => num(r.rev_per_space_day_yen) },
          { key: "src", label: "Released", render: (r) => <a href={r.source_url} target="_blank" rel="noreferrer">{r.release_date} ↗</a> },
        ]} />
      </Card>
    </>
  );
}
