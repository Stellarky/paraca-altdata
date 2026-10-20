import { Bundle } from "../data";
import { Card, Kpi, SortTable } from "../components/ui";
import { jst, num, pct } from "../format";

const FLAG: Record<string, string> = { no_vacancy_flag: "Listings with no vacancy flag", no_rent: "Listings with no rent", stale_over_26h: "Listings not seen for >26 h", no_coordinates: "Lots without coordinates" };

export default function Quality({ d }: { d: Bundle }) {
  const q = d.quality;
  const runs = [...q.runs].reverse();
  const meanDur = runs.length ? runs.reduce((s, r) => s + (r.duration_s || 0), 0) / runs.length : null;
  return (
    <>
      <div className="grid g4">
        <Kpi label="Collection runs" value={num(runs.length)} foot={`${q.failed_runs} failed or partial`} />
        <Kpi label="Requests to source (total)" value={num(q.requests_total)} foot={`≈${num(runs[0]?.requests)} per full run at ≥3 s spacing`} />
        <Kpi label="Mean run duration" value={meanDur ? `${Math.round(meanDur)}s` : "—"} foot="GitHub Actions; public repo minutes are free" />
        <Kpi label="Network coverage" value={pct(q.coverage.share_of_official)} foot={`${num(q.coverage.portal_lots)} portal lots vs ${num(q.coverage.official_lots)} operating (IR)`} />
      </div>
      <div className="grid g2">
        <Card title="Field completeness">
          <div className="tbl-wrap"><table className="tbl"><tbody>
            {Object.keys(FLAG).map((k) => (<tr key={k}><td>{FLAG[k]}</td><td className="r num">{num(q.flags[k] ?? 0)}</td></tr>))}
            <tr><td>Hourly availability status coverage</td><td className="r num">{pct(q.coverage.hourly_status_coverage ?? 0)}</td></tr>
            <tr><td>Per-lot capacity published</td><td className="r num">0%</td></tr>
          </tbody></table></div>
        </Card>
        <Card title="Known sampling biases">
          <ul style={{ margin: 0, paddingLeft: 18 }} className="small">{q.biases.map((b) => <li key={b} style={{ marginBottom: 6 }}>{b}</li>)}</ul>
        </Card>
      </div>
      <Card title="Run log" note="Latest first · every run is kept, including failures">
        <SortTable rows={runs} rowKey={(r) => r.run_id} initial={{ key: "t", dir: -1 }} max={200} cols={[
          { key: "t", label: "Started (JST)", sort: (r) => r.started_utc, render: (r) => <span className="mono small">{jst(r.started_utc)}</span> },
          { key: "src", label: "Source", render: (r) => r.source },
          { key: "st", label: "Status", sort: (r) => r.status, render: (r) => <span className={"status " + (r.status === "ok" ? "open" : "waitlist")}><span className="dot" />{r.status}</span> },
          { key: "rq", label: "Requests", right: true, sort: (r) => r.requests },
          { key: "er", label: "Errors", right: true, sort: (r) => r.errors },
          { key: "ls", label: "Listings", right: true, sort: (r) => r.listings_seen },
          { key: "du", label: "Duration", right: true, sort: (r) => r.duration_s, render: (r) => `${Math.round(r.duration_s)}s` },
          { key: "note", label: "Detail", render: (r) => { try { const n = JSON.parse(r.note); return <span className="small muted">+{n.new_listings ?? 0} new · {n.changes ?? 0} changes{n.note && !String(n.note).startsWith("browser") ? ` · ${n.note}` : ""}</span>; } catch { return null; } } },
        ]} />
      </Card>
    </>
  );
}
