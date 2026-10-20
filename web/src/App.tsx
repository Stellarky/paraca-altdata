import { useEffect, useState } from "react";
import { Bundle, loadAll, REPO } from "./data";
import { ago, jst } from "./format";
import Overview from "./sections/Overview";
import Markets from "./sections/Markets";
import Utilization from "./sections/Utilization";
import Prices from "./sections/Prices";
import Revenue from "./sections/Revenue";
import MapView from "./sections/MapView";
import Lots from "./sections/Lots";
import Quality from "./sections/Quality";
import Official from "./sections/Official";
import ForecastLab from "./sections/Forecast";

const ROUTES = [
  { id: "overview", key: "A", label: "Overview", group: "Monitor", title: "Overview", el: Overview },
  { id: "markets", key: "B", label: "Markets", group: "Monitor", title: "Market panel", el: Markets },
  { id: "utilization", key: "C", label: "Utilization", group: "Monitor", title: "Utilization trends", el: Utilization, locked: true },
  { id: "prices", key: "D", label: "Prices", group: "Monitor", title: "Prices", el: Prices },
  { id: "revenue", key: "E", label: "Revenue proxy", group: "Monitor", title: "Revenue proxy", el: Revenue, locked: true },
  { id: "map", key: "F", label: "Map", group: "Explore", title: "Map", el: MapView },
  { id: "lots", key: "G", label: "Lot explorer", group: "Explore", title: "Lot explorer", el: Lots },
  { id: "quality", key: "H", label: "Data quality", group: "Explore", title: "Quality diagnostics", el: Quality },
  { id: "official", key: "I", label: "Official IR", group: "Research", title: "Official results", el: Official },
  { id: "forecast", key: "J", label: "Forecast lab", group: "Research", title: "Forecast lab", el: ForecastLab },
] as const;

function useHash() {
  const get = () => (window.location.hash.replace("#", "") || "overview");
  const [h, setH] = useState(get);
  useEffect(() => {
    const f = () => { setH(get()); window.scrollTo(0, 0); };
    window.addEventListener("hashchange", f);
    return () => window.removeEventListener("hashchange", f);
  }, []);
  return h;
}

function ThemeToggle() {
  const [t, setT] = useState<string>(() => { try { return localStorage.getItem("theme") || "auto"; } catch { return "auto"; } });
  useEffect(() => {
    if (t === "auto") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", t);
    try { localStorage.setItem("theme", t); } catch { /* storage unavailable */ }
  }, [t]);
  return (
    <div className="seg" aria-label="Theme">
      {["auto", "light", "dark"].map((x) => <button key={x} className={t === x ? "on" : ""} onClick={() => setT(x)}>{x}</button>)}
    </div>
  );
}

export default function App() {
  const route = useHash();
  const [data, setData] = useState<Bundle | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { loadAll().then(setData).catch((e) => setErr(String(e))); }, []);
  const r = ROUTES.find((x) => x.id === route) ?? ROUTES[0];
  const El = r.el as any;
  const groups = Array.from(new Set(ROUTES.map((x) => x.group)));
  const lr = data?.summary.last_run;
  const fresh = lr && (Date.now() - new Date(lr.started_utc).getTime()) / 3.6e6 < 3;

  return (
    <div className="shell">
      <aside className="side">
        <div className="brand">
          <div className="brand-mark">P</div>
          <div><b>Paraca Monitor</b><span>TSE 4809 · alt-data</span></div>
        </div>
        <nav className="nav">
          {groups.map((g) => (
            <div key={g}>
              <div className="nav-group">{g}</div>
              {ROUTES.filter((x) => x.group === g).map((x) => (
                <a key={x.id} href={"#" + x.id} className={x.id === r.id ? "on" : ""}>
                  <span className="key">{x.key}</span>{x.label}{"locked" in x && x.locked && <span className="lock" title="Needs hourly availability data">n/a</span>}
                </a>))}
            </div>))}
        </nav>
        <div className="side-foot">
          Independent research project. Not affiliated with Paraca Inc. or Park24.<br />
          <a href={REPO} target="_blank" rel="noreferrer">Source &amp; methodology ↗</a>
          <div><ThemeToggle /></div>
        </div>
      </aside>
      <div className="main">
        <nav className="mobile-nav">{ROUTES.map((x) => <a key={x.id} href={"#" + x.id} className={x.id === r.id ? "on" : ""}>{x.key} · {x.label}</a>)}</nav>
        <header className="topbar">
          <div><h1>{r.title}</h1><div className="sub">Paraca Inc. (パラカ) · monthly-parking inventory, rents &amp; official results</div></div>
          <span className="grow" />
          {data && (
            <span className="pill" title={lr ? `Run ${lr.run_id}` : ""}>
              <span className="dot" style={{ background: fresh ? "var(--good)" : "var(--warning)" }} />
              {lr ? `Updated ${ago(lr.started_utc)} · ${jst(lr.started_utc)}` : "No runs yet"}
            </span>)}
        </header>
        <main className="content">
          {err && <div className="err">Could not load data ({err}). The collector may not have published yet; see <a href={REPO + "/actions"}>Actions</a>.</div>}
          {!data && !err && <div className="loading">Loading observations…</div>}
          {data && <El d={data} />}
        </main>
      </div>
    </div>
  );
}
