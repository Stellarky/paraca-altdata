import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Bundle } from "../data";
import { Card, Kpi, Tip, Unavailable } from "../components/ui";
import { num, signedPct, yen } from "../format";

export default function Revenue({ d }: { d: Bundle }) {
  const qs = d.financials.quarters.filter((q) => q.rev_per_space_day_yen);
  const first = qs[0], last = qs[qs.length - 1];
  const yoy = (() => {
    const ly = qs.find((q) => q.fy === last.fy - 1 && q.q === last.q);
    return ly ? last.rev_per_space_day_yen! / ly.rev_per_space_day_yen! - 1 : null;
  })();
  return (
    <>
      <Unavailable title="Fee × utilized space-hours proxy is switched off"
        reason="A revenue proxy needs both an hourly fee and an observed utilization rate per lot. Neither is available from a compliant source, and the panel will not substitute assumed occupancy. The benchmark below uses official disclosures only."
        metrics={["Est. utilized space-hours", "Est. revenue / lot / day", "Proxy vs reported revenue", "Proxy YoY"]} />
      <p className="section-intro">
        <b>Official unit economics.</b> Revenue per average operating space per day, from 決算短信 revenue and period-end space
        counts (average of opening and closing). This is the yardstick any future alt-data proxy will be calibrated against.
      </p>
      <div className="grid g3">
        <Kpi label={`Revenue / space / day · ${last.label}`} value={yen(last.rev_per_space_day_yen)} foot={`${num(last.avg_spaces)} average spaces`} />
        <Kpi label="Year-on-year change" value={signedPct(yoy)} foot="Same quarter last year" />
        <Kpi label={`Change since ${first.label}`} value={signedPct(last.rev_per_space_day_yen! / first.rev_per_space_day_yen! - 1)}
          foot="Spaces have grown faster than revenue. Possible drivers (not tested here): ramp-up of new lots, mix shift toward larger or lower-yield sites" />
      </div>
      <Card title="Revenue per space-day" note="¥ per average operating space per day, standalone quarters">
        <div style={{ height: 300 }}>
          <ResponsiveContainer>
            <LineChart data={qs} margin={{ right: 16 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="label" tickLine={false} axisLine={false} tickFormatter={(v: string) => v.replace("FY20", "FY")} />
              <YAxis domain={["auto", "auto"]} tickFormatter={(v) => `¥${v}`} tickLine={false} axisLine={false} width={56} />
              <Tooltip content={<Tip fmt={(v: number) => yen(v)} labelFmt={(l: string, p: any) => l + (p?.[0]?.payload?.spaces_interpolated ? " · Jun-25 spaces interpolated" : "")} />} />
              <Line dataKey="rev_per_space_day_yen" name="Revenue / space-day" stroke="var(--series-1)" strokeWidth={2} dot={{ r: 4, strokeWidth: 2, fill: "var(--surface-1)" }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="small muted">The FY2025 Q3 average uses an interpolated June-2025 space count (not disclosed in that report).</div>
      </Card>
    </>
  );
}
