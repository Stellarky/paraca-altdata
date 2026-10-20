import { Props, Delta, Spark, StatusBar } from "./common";
import { jst, num, pct } from "../format";

export function Hero({ d }: Props) {
  const p = d.panel!;
  const all = p.areas[0];
  const lr = d.summary.last_run;
  return (
    <header className="hero">
      <div className="eyebrow">Paraca (4809) · Coin parking · Alternative data</div>
      <h1>How tight is Paraca's parking right now?</h1>
      <div className="meta">Updated {jst(lr?.started_utc)} · {num(p.runs_total)} snapshots · {num(d.universe?.stats.union_lots ?? all.portal_lots)} known lots, {num(all.listings)} monthly listings in {d.summary.prefectures} prefectures</div>
      <p className="lede">
        Across all monthly listings, <b>{pct(all.waitlist_share)}</b> are waitlisted (空き待ち): no monthly space can be contracted.
        {p.busiest && <> At the latest snapshot <b>{p.busiest.name}</b> is the tightest market, with {pct(p.busiest.w)} waitlisted.</>}
        {p.quietest && <> <b>{p.quietest.name}</b> has the most room at {pct(p.quietest.w)}.</>}
        {" "}Live hourly occupancy is not published for Paraca lots, so this panel tracks monthly-contract supply instead.
      </p>
    </header>
  );
}

export function AreasNow(props: Props) {
  const p = props.d.panel!;
  return (
    <section className="sec" id="areas">
      <h2>Areas now</h2>
      <p className="sec-intro">Waitlist share = monthly listings shown 空き待ち, out of listings that show a flag. Same 16 markets as the Times panel, each 2.5 km around its centre. Lines show the last 7 days on one shared scale.</p>
      <Cards {...props} list={p.areas.filter((a) => a.id === "all" || a.panel !== "paraca")} />
    </section>
  );
}

export function Strongholds(props: Props) {
  const p = props.d.panel!;
  const list = p.areas.filter((a) => a.panel === "paraca");
  if (!list.length) return null;
  return (
    <section className="sec" id="strongholds">
      <h2>Paraca strongholds</h2>
      <p className="sec-intro">A second panel chosen by Paraca's own footprint: the ten densest clusters of known Paraca lots outside the Times markets, each 2.5 km around the cluster's centre. Most are regional cities where Paraca is strong and Times is not the reference.</p>
      <Cards {...props} list={list} />
    </section>
  );
}

function Cards({ area, setArea, list }: Props & { list: import("../data").PArea[] }) {
  const go = (id: string) => { setArea(id); document.getElementById("detail")?.scrollIntoView(); };
  return (
      <div className="areas">
        {list.map((a) => (
          <button key={a.id} type="button" className={"card acard" + (a.id === "all" ? " total" : "") + (area === a.id ? " sel" : "") + (a.listings ? "" : " empty")} onClick={() => go(a.id)}>
            <span className="nm">{a.name}</span>
            <span className="ja">{a.ja}</span>
            <span className="tag">{a.type}</span>
            {a.listings ? (
              <>
                <span className="big"><b>{pct(a.waitlist_share)}</b><span>waitlisted</span></span>
                <span className="sub2">{pct(a.waitlist + a.open ? a.open / (a.waitlist + a.open) : null)} open · <Delta now={a.waitlist_share} prev={a.prev_waitlist_share} /></span>
                <Spark s={a.series} />
                <StatusBar a={a} />
              </>
            ) : (
              <>
                <span className="big"><b>No monthly listings</b></span>
                <span className="sub2">{a.known_lots ? `${a.known_lots} owned lot${a.known_lots > 1 ? "s" : ""} known from opening releases` : "No Paraca lots known within 2.5 km"}</span>
                <div className="spark" />
              </>
            )}
            <span className="ft"><span>{num(a.known_lots)} known lots{a.owned_lots ? ` · ${a.owned_lots} owned` : ""}</span><span>{num(a.listings)} listings</span></span>
          </button>
        ))}
      </div>
  );
}
