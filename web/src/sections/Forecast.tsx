import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Bundle } from "../data";
import { Card, Kpi, Legend, SortTable, Tip } from "../components/ui";
import { mn, num, pct, signedPct } from "../format";

const NAMES: Record<string, string> = { seasonal_naive: "Seasonal naive", space_yield: "Space × yield", space_yield_drift: "Space × yield (drift)" };
const COLORS: Record<string, string> = { actual: "var(--text-primary)", seasonal_naive: "var(--series-1)", space_yield: "var(--series-2)", space_yield_drift: "var(--series-3)" };

export default function ForecastLab({ d }: { d: Bundle }) {
  const fc = d.forecast;
  const n = fc.next;
  const bt = fc.backtest;
  const models = Object.entries(bt.models);
  return (
    <>
      <div className="callout info">
        <b>Observed vs modelled.</b> Everything on this page except "Actual" is a model output. The models use only disclosed
        figures (revenue and period-end space counts). The alternative-data signal is <b>not yet in any model</b>: it began on
        {" "}{fc.altdata_link.first_observation?.slice(0, 10)}, and testing whether it leads reported revenue needs several quarters of overlap.
      </div>
      {n && (
        <div className="grid g4">
          <Kpi label={`${n.label} revenue · model`} value={mn(n.revenue_point)} foot={`${NAMES[n.model]} · indicative band ${mn(n.revenue_lo)}–${mn(n.revenue_hi).slice(1)}`} />
          <Kpi label={`${n.label} implied by guidance`} value={mn(n.guidance_implied_q4)} foot={`Revised FY guidance ${mn(n.full_year_guidance)} − Q1–Q3 actual ${mn(n.cum_q1_q3)}`} />
          <Kpi label="Model vs guidance" value={signedPct(n.guidance_implied_q4 ? n.revenue_point / n.guidance_implied_q4 - 1 : null)} foot={`Full-year model ${mn(n.full_year_model)}`} />
          <Kpi label="Resolves" value="Early Nov" unit="2026" foot={`FY${n.label.slice(2, 6)} 決算短信 (FY ends ${n.end})`} />
        </div>)}
      <div className="grid g21">
        <Card title="Backtest: one-quarter-ahead revenue" note="¥ million, standalone quarters">
          <div style={{ height: 300 }}>
            <ResponsiveContainer>
              <LineChart data={bt.rows} margin={{ right: 16 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="label" tickFormatter={(v: string) => v.replace("FY20", "FY")} tickLine={false} axisLine={false} />
                <YAxis domain={["auto", "auto"]} tickLine={false} axisLine={false} width={48} tickFormatter={(v) => num(v)} />
                <Tooltip content={<Tip fmt={(v: number) => mn(v)} />} />
                <Line dataKey="actual" name="Actual" stroke={COLORS.actual} strokeWidth={2.5} dot={{ r: 4 }} />
                {Object.keys(NAMES).map((k) => <Line key={k} dataKey={k} name={NAMES[k]} stroke={COLORS[k]} strokeWidth={2} strokeDasharray="5 4" dot={{ r: 3 }} connectNulls={false} />)}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <Legend items={[{ label: "Actual", color: COLORS.actual }, ...Object.keys(NAMES).map((k) => ({ label: NAMES[k], color: COLORS[k] }))]} />
        </Card>
        <Card title="Model scorecard" note="Lower MAPE is better">
          <div className="tbl-wrap"><table className="tbl"><thead><tr><th>Model</th><th className="r">MAPE</th><th className="r">Bias</th><th className="r">n</th></tr></thead>
            <tbody>{models.map(([k, m]) => (
              <tr key={k} className={bt.best === k ? "sel" : ""}><td>{NAMES[k]}{bt.best === k ? " ★" : ""}<div className="small muted">{m.desc}</div></td>
                <td className="r num">{pct(m.mape)}</td><td className="r num">{signedPct(m.bias)}</td><td className="r num">{m.n}</td></tr>))}</tbody></table></div>
          <p className="small muted" style={{ marginBottom: 0 }}>With 6–10 observations no model is "proven". Space × yield overshoots because revenue per space has fallen steadily; the drift version corrects for that.</p>
        </Card>
      </div>
      {n && (
        <Card title={`${n.label} assumptions`} note="Every input shown">
          <div className="grid g4">
            <Kpi label="Spaces at start (Jun-26, IR)" value={num(n.assumptions.spaces_start)} />
            <Kpi label="Net adds / quarter" value={num(n.assumptions.net_adds_per_quarter)} foot="Mean of last 3 disclosed quarters" />
            <Kpi label="Average spaces (est.)" value={num(n.assumptions.avg_spaces_hat)} />
            <Kpi label="All model outputs" value={<span style={{ fontSize: 15 }}>{Object.entries(n.predictions).map(([k, v]) => <div key={k}>{NAMES[k]}: {mn(v)}</div>)}</span>} />
          </div>
          <p className="small muted">{n.interval_note}</p>
        </Card>)}
      <Card title="Alternative-data link" note={fc.altdata_link.status.replace(/_/g, " ")}>
        <p className="small" style={{ marginTop: 0 }}>{fc.altdata_link.note}</p>
        <p className="small muted" style={{ marginBottom: 0 }}>Planned test once history allows: regress quarterly revenue surprise (actual − seasonal naive) on the
          quarter's change in monthly open share and listing count, with walk-forward evaluation. Results will be reported with
          their sample size, including null results.</p>
      </Card>
      <Card title="Backtest detail">
        <SortTable rows={bt.rows} rowKey={(r) => r.label} initial={{ key: "l", dir: 1 }} cols={[
          { key: "l", label: "Quarter", sort: (r) => r.label, render: (r) => r.label },
          { key: "a", label: "Actual", right: true, render: (r) => mn(r.actual) },
          ...Object.keys(NAMES).map((k) => ({ key: k, label: NAMES[k], right: true, render: (r: any) => r[k] != null ? <>{mn(r[k])} <span className="muted">({signedPct(r[k + "_err"])})</span></> : "—" })),
        ]} />
        <div className="small muted" style={{ marginTop: 6 }}>Revenue per space-day used by the space models: see Revenue proxy. Spaces at quarter end are known at the release date.</div>
      </Card>
    </>
  );
}
