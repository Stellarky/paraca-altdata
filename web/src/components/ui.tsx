import { ReactNode, useMemo, useState } from "react";
import { VAC_EN } from "../format";

export function Card({ title, note, right, children, className = "" }: { title?: ReactNode; note?: ReactNode; right?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={"card " + className}>
      {(title || right) && (
        <div className="card-h">
          {title && <h3>{title}</h3>}
          {note && <span className="note">{note}</span>}
          <span className="grow" />
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

export function Kpi({ label, value, unit, foot, disabled }: { label: ReactNode; value: ReactNode; unit?: string; foot?: ReactNode; disabled?: boolean }) {
  return (
    <div className={"card kpi" + (disabled ? " disabled" : "")}>
      <div className="label">{label}</div>
      <div className="value">{value}{unit && <small>{unit}</small>}</div>
      {foot && <div className="foot">{foot}</div>}
    </div>
  );
}

export function Unavailable({ title, reason, metrics }: { title: string; reason: string; metrics?: string[] }) {
  return (
    <div className="unavail" role="note">
      <span className="tag">⊘ Not available from a compliant source</span>
      <h3>{title}</h3>
      <p>{reason}</p>
      {metrics && (
        <div className="ghost-metrics">
          {metrics.map((m) => (<div key={m}><b>— —</b>{m}</div>))}
        </div>
      )}
    </div>
  );
}

export function Status({ v }: { v: string }) {
  return <span className={"status " + v}><span className="dot" />{VAC_EN[v] ?? v}</span>;
}

export function Tip({ active, payload, label, fmt, labelFmt }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="tt">
      <div className="h">{labelFmt ? labelFmt(label, payload) : label}</div>
      {payload.map((p: any) => (
        <div className="r" key={p.dataKey ?? p.name}>
          <span><span className="swatch" style={{ background: p.color ?? p.fill, marginRight: 6 }} />{p.name}</span>
          <b>{fmt ? fmt(p.value, p) : p.value}</b>
        </div>
      ))}
    </div>
  );
}

export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return <div className="chart-legend">{items.map((i) => <span key={i.label}><span className="swatch" style={{ background: i.color }} />{i.label}</span>)}</div>;
}

export interface Col<T> { key: string; label: ReactNode; render?: (r: T) => ReactNode; sort?: (r: T) => number | string | null; right?: boolean; }

export function SortTable<T>({ rows, cols, initial, rowKey, onRow, selected, max = 500 }: { rows: T[]; cols: Col<T>[]; initial?: { key: string; dir: 1 | -1 }; rowKey: (r: T) => string; onRow?: (r: T) => void; selected?: string | null; max?: number }) {
  const [s, setS] = useState(initial ?? { key: cols[0].key, dir: 1 as 1 | -1 });
  const sorted = useMemo(() => {
    const c = cols.find((x) => x.key === s.key);
    if (!c?.sort) return rows;
    return [...rows].sort((a, b) => {
      const va = c.sort!(a), vb = c.sort!(b);
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      return (va < vb ? -1 : va > vb ? 1 : 0) * s.dir;
    });
  }, [rows, cols, s]);
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead><tr>{cols.map((c) => (
          <th key={c.key} className={(c.sort ? "sortable " : "") + (c.right ? "r" : "")}
              onClick={() => c.sort && setS({ key: c.key, dir: s.key === c.key ? (-s.dir as 1 | -1) : 1 })}>
            {c.label}{s.key === c.key ? (s.dir === 1 ? " ↑" : " ↓") : ""}
          </th>))}</tr></thead>
        <tbody>
          {sorted.slice(0, max).map((r) => (
            <tr key={rowKey(r)} className={selected === rowKey(r) ? "sel" : ""} onClick={() => onRow?.(r)} style={onRow ? { cursor: "pointer" } : undefined}>
              {cols.map((c) => <td key={c.key} className={c.right ? "r num" : ""}>{c.render ? c.render(r) : (r as any)[c.key]}</td>)}
            </tr>))}
        </tbody>
      </table>
      {sorted.length > max && <div className="muted small" style={{ padding: 8 }}>Showing {max} of {sorted.length}. Refine the search to see more.</div>}
    </div>
  );
}
