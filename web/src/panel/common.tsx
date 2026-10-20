import { Area, AreaChart, ResponsiveContainer, YAxis } from "recharts";
import { Bundle, Lot, PArea } from "../data";
import { pct } from "../format";

export type Props = { d: Bundle; area: string; setArea: (a: string) => void };

export const STATUS_COLORS = { full: "var(--full)", mixed: "var(--nearly)", open: "var(--avail)", none: "var(--nostatus)" } as const;
export const STATUS_LABEL = { full: "満 All waitlisted", mixed: "混 Some open", open: "空 All open", none: "— No flag / owned lot" } as const;

/** Lot-level status from its portal listings: all waitlisted = full, some open = mixed, all open = open. */
export function lotStatus(l: Lot | undefined): keyof typeof STATUS_COLORS {
  if (!l) return "none";
  const v = l.listings.map((x) => x.vac).filter((x) => x !== "unknown");
  if (!v.length) return "none";
  if (v.every((x) => x === "waitlist")) return "full";
  if (v.every((x) => x === "open")) return "open";
  return "mixed";
}

export function Spark({ s }: { s: PArea["series"] }) {
  const data = s.filter((p) => p.w != null);
  if (data.length < 2) return <div className="spark small muted" style={{ display: "flex", alignItems: "center" }}>Line appears from the second snapshot.</div>;
  return (
    <div className="spark">
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ top: 2, bottom: 2, left: 0, right: 0 }}>
          <YAxis hide domain={[0, 1]} />
          <Area dataKey="w" type="monotone" stroke="var(--series-1)" strokeWidth={2} fill="var(--series-1)" fillOpacity={0.14} isAnimationActive={false} dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function StatusBar({ a }: { a: PArea }) {
  const t = a.waitlist + a.open + a.noflag || 1;
  return (
    <div className="sbar" title={`${a.waitlist} waitlisted · ${a.open} open · ${a.noflag} no flag`}>
      {a.waitlist > 0 && <i style={{ width: `${(a.waitlist / t) * 100}%`, background: "var(--full)" }} />}
      {a.open > 0 && <i style={{ width: `${(a.open / t) * 100}%`, background: "var(--avail)" }} />}
      {a.noflag > 0 && <i style={{ width: `${(a.noflag / t) * 100}%`, background: "var(--nostatus)" }} />}
    </div>
  );
}

export function Delta({ now, prev }: { now: number | null; prev: number | null }) {
  if (now == null || prev == null) return <span>no earlier snapshot</span>;
  const d = now - prev;
  return <span className={d > 0.0005 ? "up" : d < -0.0005 ? "down" : ""}>{d >= 0 ? "+" : "−"}{pct(Math.abs(d))} vs previous</span>;
}

export const AREA_OPTIONS = (d: Bundle) => [{ id: "all", label: "All areas · every listed lot", group: "" },
  ...(d.panel?.areas.slice(1) ?? []).map((a) => ({ id: a.id, label: `${a.name} · ${a.ja}`, group: a.panel === "paraca" ? "Paraca strongholds" : "Times-matched markets" }))];
