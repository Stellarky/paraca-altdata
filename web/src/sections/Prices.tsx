import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Bundle } from "../data";
import { Card, Kpi, SortTable, Tip, Unavailable } from "../components/ui";
import { CT_EN, jst, median, num, VEH_EN, yen } from "../format";

export default function Prices({ d }: { d: Bundle }) {
  const all = useMemo(() => d.lots.flatMap((l) => l.listings.map((x) => ({ ...x, pref: l.pref, lot: l.name, lotId: l.id }))), [d]);
  const car = all.filter((x) => x.veh === "自動車" && x.ct === "月極");
  const groups = useMemo(() => {
    const m = new Map<string, number[]>();
    all.forEach((x) => { const k = `${VEH_EN[x.veh] ?? x.veh} · ${CT_EN[x.ct] ?? x.ct}`; if (x.rent) m.set(k, [...(m.get(k) ?? []), x.rent]); });
    return [...m].map(([k, v]) => ({ k, n: v.length, med: median(v), min: Math.min(...v), max: Math.max(...v) })).sort((a, b) => b.n - a.n);
  }, [all]);
  const byPref = d.summary.prefectures_table.filter((p) => p.median_car_rent).slice(0, 14).map((p) => ({ name: p.pref, rent: p.median_car_rent }));
  const changes = d.events.filter((e) => e.kind === "rent_change");
  const lotName = new Map(d.lots.map((l) => [l.id, l.name]));
  return (
    <>
      <Unavailable title="Hourly fees and daily caps are not available"
        reason="Paraca's hourly tariffs (e.g. 20分¥200, 最大料金) are published only on on-site signs and on third-party sites that disallow automated collection. The collector already stores raw fee schedules alongside normalised rates (it never forces a single hourly equivalent when prices vary by time or day); it fills in once a permitted source exists."
        metrics={["Median hourly rate", "Median daily cap", "Fee distribution", "Tariff changes"]} />
      <div className="grid g4">
        <Kpi label="Median car monthly rent" value={yen(median(car.map((x) => x.rent)))} foot={`${car.length} car / 月極 listings`} />
        <Kpi label="Interquartile range" value={(() => { const r = car.map((x) => x.rent!).filter(Boolean).sort((a, b) => a - b); return r.length ? `${yen(r[Math.floor(r.length * .25)])}–${yen(r[Math.floor(r.length * .75)]).slice(1)}` : "—"; })()} foot="25th–75th percentile, car monthly" />
        <Kpi label="Observed rent changes" value={num(changes.length)} foot="Since collection began" />
        <Kpi label="Listings without rent" value={num(all.filter((x) => x.rent == null).length)} foot="Recorded as missing, never as ¥0" />
      </div>
      <div className="grid g2">
        <Card title="Monthly rent distribution" note="Car / 月極, ¥5,000 bins">
          <div style={{ height: 280 }}>
            <ResponsiveContainer>
              <BarChart data={d.summary.rent_hist} margin={{ right: 8 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="bin" tickFormatter={(v) => `${v / 1000}k`} tickLine={false} axisLine={false} />
                <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={32} />
                <Tooltip cursor={{ fill: "var(--surface-2)" }} content={<Tip labelFmt={(l: number) => `${yen(l)}–${yen(l + 4999)}`} fmt={(v: number) => `${v} listings`} />} />
                <Bar dataKey="n" name="Listings" fill="var(--series-1)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title="Median car rent by prefecture" note="Car / 月極">
          <div style={{ height: 280 }}>
            <ResponsiveContainer>
              <BarChart data={byPref} layout="vertical" margin={{ right: 24 }}>
                <CartesianGrid horizontal={false} />
                <XAxis type="number" tickFormatter={(v) => `${v / 1000}k`} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="name" width={72} tickLine={false} axisLine={false} interval={0} />
                <Tooltip cursor={{ fill: "var(--surface-2)" }} content={<Tip fmt={(v: number) => yen(v)} />} />
                <Bar dataKey="rent" name="Median rent" fill="var(--series-1)" radius={[0, 4, 4, 0]} barSize={12} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
      <Card title="Rent by product" note="All active listings with a rent">
        <SortTable rows={groups} rowKey={(r) => r.k} initial={{ key: "n", dir: -1 }} cols={[
          { key: "k", label: "Vehicle · contract", sort: (r) => r.k },
          { key: "n", label: "Listings", right: true, sort: (r) => r.n },
          { key: "med", label: "Median", right: true, sort: (r) => r.med, render: (r) => yen(r.med) },
          { key: "min", label: "Min", right: true, sort: (r) => r.min, render: (r) => yen(r.min) },
          { key: "max", label: "Max", right: true, sort: (r) => r.max, render: (r) => yen(r.max) },
        ]} />
      </Card>
      <Card title="Observed price changes" note="Rent changes detected between collection runs">
        {changes.length ? (
          <SortTable rows={changes} rowKey={(r) => r.event_utc + r.listing_id} initial={{ key: "t", dir: -1 }} cols={[
            { key: "t", label: "Detected (JST)", sort: (r) => r.event_utc, render: (r) => jst(r.event_utc) },
            { key: "lot", label: "Lot", render: (r) => lotName.get(r.lot_id) ?? r.lot_id },
            { key: "o", label: "Old", right: true, render: (r) => yen(Number(r.old_value)) },
            { key: "n", label: "New", right: true, render: (r) => yen(Number(r.new_value)) },
          ]} />
        ) : <div className="muted small">No rent changes observed yet. Each hourly run compares every listing with its previous value.</div>}
      </Card>
    </>
  );
}
