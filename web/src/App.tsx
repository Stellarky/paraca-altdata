import { useEffect, useState } from "react";
import { Bundle, loadAll, REPO } from "./data";
import { AREA_OPTIONS } from "./panel/common";
import { AreasNow, Hero, Strongholds } from "./panel/Top";
import { Traffic } from "./panel/Traffic";
import { ByType, Official, Owned } from "./panel/Middle";
import { AreaDetail } from "./panel/Bottom";

const NAV = [["areas", "Areas"], ["traffic", "空/混/満"], ["bytype", "By type"], ["official", "Official figures"], ["owned", "Owned lots"], ["detail", "Area detail"], ["lots", "Lots"]];

function ThemeToggle() {
  const [t, setT] = useState<string>(() => { try { return localStorage.getItem("theme") || "auto"; } catch { return "auto"; } });
  useEffect(() => {
    if (t === "auto") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", t);
    try { localStorage.setItem("theme", t); } catch { /* storage unavailable */ }
  }, [t]);
  return (
    <div className="seg" aria-label="Theme">
      {[["light", "Light"], ["dark", "Dark"], ["auto", "Auto"]].map(([k, l]) => <button key={k} className={t === k ? "on" : ""} onClick={() => setT(k)}>{l}</button>)}
    </div>
  );
}

export default function App() {
  const [data, setData] = useState<Bundle | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [area, setAreaState] = useState<string>(() => { try { return localStorage.getItem("area") || "all"; } catch { return "all"; } });
  const setArea = (a: string) => { setAreaState(a); try { localStorage.setItem("area", a); } catch { /* ignore */ } };
  useEffect(() => { loadAll().then(setData).catch((e) => setErr(String(e))); }, []);
  useEffect(() => {
    if (!data) return;
    const h = window.location.hash.replace("#", "");
    if (h) setTimeout(() => document.getElementById(h)?.scrollIntoView(), 50);
  }, [data]);
  const props = data ? { d: data, area, setArea } : null;
  return (
    <>
      <div className="bar">
        <div className="bar-in">
          <a className="brand" href="#top"><span className="brand-mark">P</span>Paraca Panel Monitor</a>
          <nav className="nav">{NAV.map(([id, l]) => <a key={id} href={"#" + id}>{l}</a>)}</nav>
          <span className="grow" />
          {data && (
            <label className="picker">Area
              <select value={area} onChange={(e) => { setArea(e.target.value); document.getElementById("detail")?.scrollIntoView(); }}>
                {(() => { const o = AREA_OPTIONS(data); return <>
                  <option value="all">{o[0].label}</option>
                  {["Times-matched markets", "Paraca strongholds"].map((g) => <optgroup key={g} label={g}>{o.filter((x) => x.group === g).map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}</optgroup>)}
                </>; })()}
              </select>
            </label>)}
          <ThemeToggle />
        </div>
      </div>
      <main className="page" id="top">
        {err && <div className="err">Could not load data ({err}). The collector may not have published yet; see <a href={REPO + "/actions"}>Actions</a>.</div>}
        {!data && !err && <div className="loading">Loading observations…</div>}
        {props && !data!.panel && <div className="err">This data build has no panel.json yet; it appears after the next hourly run.</div>}
        {props && data!.panel && <>
          <Hero {...props} />
          <AreasNow {...props} />
          <Strongholds {...props} />
          <Traffic {...props} />
          <ByType {...props} />
          <Official {...props} />
          <Owned {...props} />
          <AreaDetail {...props} />
          <footer className="muted small" style={{ paddingTop: 20 }}>
            Independent research project; not affiliated with Paraca Inc. or Park24. Data: Paraca public pages and IR filings; map © OpenStreetMap contributors, © CARTO.
            {" "}<a href={REPO} target="_blank" rel="noreferrer">Source, methodology and data ↗</a>
          </footer>
        </>}
      </main>
    </>
  );
}
