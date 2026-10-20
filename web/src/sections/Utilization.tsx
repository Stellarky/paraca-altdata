import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Bundle } from "../data";
import { Card, Legend, Tip, Unavailable } from "../components/ui";
import { pct } from "../format";

export default function Utilization({ d }: { d: Bundle }) {
  const s = d.summary;
  const ser = s.national_series;
  return (
    <>
      <Unavailable title="Hourly utilization, busy share and full share are not available"
        reason={s.hourly.reason}
        metrics={["Capacity-weighted busy share", "Full share", "Hourly profile (JST)", "Weekday vs weekend"]} />
      <div className="callout info">
        <b>What follows is a different signal.</b> The monthly-contract vacancy flag (申込可能 vs 空き待ち) shows whether a monthly space can
        be contracted today. It moves slowly and reflects both demand and how many spaces Paraca chooses to offer monthly. It is
        <b> not</b> hourly occupancy and is not comparable with Times' snapshot utilization or Park24's reported parked-time occupancy.
      </div>
      <Card title="Monthly-listing open share, national" note="Daily, JST · all vehicle types and car monthly only">
        {ser.length > 1 ? (
          <>
            <div style={{ height: 300 }}>
              <ResponsiveContainer>
                <LineChart data={ser} margin={{ right: 16 }}>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="d" tickLine={false} axisLine={false} minTickGap={28} />
                  <YAxis tickFormatter={(v) => pct(v, 0)} domain={[0, 1]} tickLine={false} axisLine={false} width={44} />
                  <Tooltip content={<Tip fmt={(v: number) => pct(v)} />} />
                  <Line dataKey="open" name="All listings" stroke="var(--series-1)" strokeWidth={2} dot={false} />
                  <Line dataKey="car_open" name="Car monthly" stroke="var(--series-2)" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <Legend items={[{ label: "All listings", color: "var(--series-1)" }, { label: "Car monthly", color: "var(--series-2)" }]} />
          </>
        ) : (
          <div className="muted small" style={{ padding: "30px 0" }}>
            One day of history so far ({ser[0]?.d}): open share {pct(ser[0]?.open)}, car monthly {pct(ser[0]?.car_open)}. The trend line
            draws itself as the hourly collector accumulates days.
          </div>
        )}
      </Card>
    </>
  );
}
