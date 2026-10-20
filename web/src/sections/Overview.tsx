import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Bundle } from "../data";
import { Card, Kpi, Tip } from "../components/ui";
import { ago, jst, num, pct, yen } from "../format";

export default function Overview({ d }: { d: Bundle }) {
  const s = d.summary;
  const days = new Set(s.national_series.map((x) => x.d)).size;
  const matched = s.areas.filter((a) => a.lots > 0).length;
  const prefs = s.prefectures_table.slice(0, 14).map((p) => ({ ...p, name: p.pref }));
  const coverage = s.official_lots_total ? s.lots / s.official_lots_total : null;
  return (
    <>
      <p className="section-intro">
        Independent monitor of Paraca's publicly listed parking inventory, built for equity research. Real-time hourly availability
        is <b>not</b> published by any compliant source, so this panel tracks the signals that are observable: Paraca's own
        monthly-contract listings (vacancy flag and rent), plus the official results disclosed in its 決算短信.
      </p>
      <div className="grid g4">
        <Kpi label="Monitored lots" value={num(s.lots)} foot={<>{pct(coverage)} of {num(s.official_lots_total)} lots in operation (IR, {s.official_asof})</>} />
        <Kpi label="Active listings" value={num(s.listings)} foot={`${num(s.car_monthly_listings)} car monthly · ${s.prefectures} prefectures`} />
        <Kpi label="Monthly listings open" value={pct(s.open_share)} foot="Share of flagged listings with 申込可能 (can contract now)" />
        <Kpi label="Median car monthly rent" value={yen(s.median_car_rent)} foot="Tax incl., car / 月極 listings" />
      </div>
      <div className="grid g4">
        <Kpi label="Data freshness" value={s.last_run ? ago(s.last_run.started_utc) : "—"} foot={s.last_run ? `Last run ${jst(s.last_run.started_utc)} · ${s.last_run.status}` : ""} />
        <Kpi label="Matched markets with data" value={`${matched}/16`} foot="Times reference markets with ≥1 Paraca listing within 2.5 km" />
        <Kpi label="History" value={days} unit={days === 1 ? "day" : "days"} foot={`Since ${jst(s.first_observation_utc, false)} · ${s.runs_total} collection runs`} />
        <Kpi label="Hourly status coverage" value="0%" disabled foot="No compliant real-time source (see Utilization)" />
      </div>
      <div className="grid g21">
        <Card title="Listings by prefecture" note="Active monthly / pass listings on sweet.paraca.co.jp">
          <div style={{ height: 360 }}>
            <ResponsiveContainer>
              <BarChart data={prefs} layout="vertical" margin={{ left: 8, right: 24 }}>
                <CartesianGrid horizontal={false} />
                <XAxis type="number" tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="name" width={72} tickLine={false} axisLine={false} interval={0} />
                <Tooltip cursor={{ fill: "var(--surface-2)" }} content={<Tip fmt={(v: number) => num(v)} />} />
                <Bar dataKey="listings" name="Listings" fill="var(--series-1)" radius={[0, 4, 4, 0]} barSize={14} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title="What this panel can and cannot see">
          <div className="small" style={{ display: "grid", gap: 10 }}>
            <div><b>✓ Observed</b> <span className="muted">· monthly-contract listings, rents, deposits, vacancy flag, coordinates, openings/removals; official revenue, lots and spaces per quarter.</span></div>
            <div><b>⊘ Not observable</b> <span className="muted">· hourly coin-parking availability, hourly fees, per-lot capacity. Utilization and revenue-proxy panels stay greyed until a licensed or permitted source exists.</span></div>
            <div><b>△ Bias</b> <span className="muted">· the portal covers about {pct(coverage, 0)} of Paraca's network, skewed to Tokyo and Osaka and to lots that offer monthly contracts.</span></div>
            <div><b>↻ Cadence</b> <span className="muted">· hourly batch via GitHub Actions; unchanged listings are stored once per JST day plus every change.</span></div>
          </div>
        </Card>
      </div>
    </>
  );
}
