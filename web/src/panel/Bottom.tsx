import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { lotStatus, Props, STATUS_COLORS, STATUS_LABEL } from "./common";
import { Card, SortTable, Stat, Tip, Unavailable } from "../components/ui";
import { jst, median, num, pct, yen } from "../format";
import MapView from "../sections/MapView";
import Lots from "../sections/Lots";

const KIND: Record<string, string> = { rent_change: "Rent change", vacancy_change: "Vacancy change", listing_removed: "Listing removed",
  lot_removed: "Lot no longer listed", lot_reappeared: "Lot listed again", lot_new: "New lot", listing_new: "New listing" };

export function AreaDetail(props: Props) {
  const { d, area } = props;
  const p = d.panel!;
  const a = p.areas.find((x) => x.id === area) ?? p.areas[0];
  const lotsHere = d.lots.filter((l) => area === "all" || l.area === area);
  const carRents = lotsHere.flatMap((l) => l.listings.filter((x) => x.veh === "自動車" && x.ct === "月極").map((x) => x.rent)).filter((x): x is number => x != null);
  const hist = useMemo(() => {
    const m = new Map<number, number>();
    carRents.forEach((r) => { const b = Math.floor(r / 5000) * 5000; m.set(b, (m.get(b) ?? 0) + 1); });
    return [...m].sort((x, y) => x[0] - y[0]).map(([bin, n]) => ({ bin, n }));
  }, [carRents]);
  const series = a.series.filter((s) => s.w != null).map((s) => ({ ...s, label: jst(s.t).slice(5, 16) }));
  return (
    <section className="sec" id="detail">
      <div className="eyebrow">{area === "all" ? "Panel total" : a.type}</div>
      <h2 style={{ fontSize: 34 }}>{a.name} · {a.ja}</h2>
      <div className="strip">
        <Stat value={pct(a.waitlist_share)} label="waitlisted now" />
        <Stat value={pct(a.waitlist + a.open ? a.open / (a.waitlist + a.open) : null)} label="open now" />
        <Stat value={num(a.known_lots)} label="known lots" />
        <Stat value={num(a.portal_lots)} label="lots with monthly listings" />
        <Stat value={num(a.owned_lots)} label={`owned lots (${num(a.owned_spaces)} spaces)`} />
        <Stat value={yen(a.median_car_rent)} label="median car rent / month" />
        <Stat value="—" label="busy now (hourly)" off />
        <Stat value="—" label="median ¥/hour" off />
      </div>
      <div className="grid g2">
        <Card title="Waitlist share, last 7 days" note="Share of monthly listings shown 空き待ち at each hourly snapshot. Monthly vacancy moves slowly; flat stretches are normal.">
          {series.length > 1 ? (
            <div style={{ height: 260 }}>
              <ResponsiveContainer>
                <LineChart data={series} margin={{ right: 12 }}>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="label" tickLine={false} axisLine={false} minTickGap={50} />
                  <YAxis domain={[0, 1]} tickFormatter={(v) => pct(v, 0)} tickLine={false} axisLine={false} width={46} />
                  <Tooltip content={<Tip fmt={(v: number) => pct(v)} />} />
                  <Line dataKey="w" name="Waitlisted" stroke="var(--series-1)" strokeWidth={2} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : <p className="muted">More points appear as hourly snapshots build up.</p>}
        </Card>
        <Card title="Monthly rents" note={`Car / 月極 listings in ${area === "all" ? "all areas" : a.name}, ¥5,000 bins. Median ${yen(median(carRents))}.`}>
          {hist.length ? (
            <div style={{ height: 260 }}>
              <ResponsiveContainer>
                <BarChart data={hist} margin={{ right: 12 }}>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="bin" tickFormatter={(v) => `${v / 1000}k`} tickLine={false} axisLine={false} />
                  <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={32} />
                  <Tooltip cursor={{ fill: "var(--surface-2)" }} content={<Tip labelFmt={(l: number) => `${yen(l)}–${yen(l + 4999)}`} fmt={(v: number) => `${v} listings`} />} />
                  <Bar dataKey="n" name="Listings" fill="var(--series-1)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : <p className="muted">No car monthly listings here.</p>}
        </Card>
      </div>
      <div className="grid g2">
        <Unavailable title="Busy share and estimated occupancy (hourly)" reason={d.summary.hourly.reason} metrics={["busy now", "full now", "est. occupancy", "when it is busy"]} />
        <Unavailable title="Hourly prices and fee × occupancy" reason="Paraca's hourly tariffs are posted on site signs and on third-party sites that disallow automated collection. The fee parser and price-index logic are built and switch on with a permitted source." metrics={["median ¥/hour", "daily cap", "price index", "¥ per space-hour"]} />
      </div>
      <LotMaps {...props} />
      <Card title="Interactive map" note="Every known Paraca lot: portal lots colored by their monthly status, owned lots from opening releases as blue rings. Click a lot for its listings or release.">
        <MapView d={d} />
      </Card>
      <div id="lots" />
      <Card title="Lots" note="Click a lot to see its listings and every recorded change. Click a column to sort.">
        <Lots d={d} area={area} />
      </Card>
      <Events {...props} />
      <Coverage {...props} />
      <Measured {...props} />
    </section>
  );
}

function LotMaps({ d, area, setArea }: Props) {
  const p = d.panel!;
  const lotById = new Map(d.lots.map((l) => [l.id, l]));
  const uni = d.universe?.lots ?? [];
  return (
    <Card title="Lot map" note="Each known lot at its location within 2.5 km of the market centre, colored by its monthly listings' status; rings are owned lots without monthly listings. The cross is the centre; the dashed ring is 2.5 km. Click a market to select it.">
      <div className="minimaps">
        {p.areas.slice(1).map((a) => {
          const R = a.radius_km ?? 2.5, W = 200, k = (W / 2 - 8) / R;
          const pts = uni.filter((u) => u.area === a.id).map((u) => {
            const dx = (u.lng - a.lng!) * 111.32 * Math.cos((a.lat! * Math.PI) / 180), dy = (u.lat - a.lat!) * 110.57;
            const portal = u.sources.portal ? lotById.get(u.sources.portal) : undefined;
            return { x: W / 2 + dx * k, y: W / 2 - dy * k, st: portal ? lotStatus(portal) : "none", owned: !portal, n: u.spaces ?? portal?.listings.length ?? 2, name: u.name };
          });
          const full = pts.filter((x) => x.st === "full" || x.st === "mixed").length;
          return (
            <div key={a.id} className={"minimap" + (area === a.id ? " sel" : "")} onClick={() => setArea(a.id)} role="button" tabIndex={0}
                 onKeyDown={(e) => e.key === "Enter" && setArea(a.id)}>
              <b>{a.name}</b>
              <div className="s">{pts.length ? `${full} of ${pts.length} lots fully or partly waitlisted` : "No known Paraca lots"}</div>
              <svg viewBox={`0 0 ${W} ${W}`} aria-label={`${a.name} lot map`}>
                <circle cx={W / 2} cy={W / 2} r={W / 2 - 8} fill="none" stroke="var(--border-strong)" strokeDasharray="4 4" />
                <path d={`M${W / 2 - 6} ${W / 2}h12M${W / 2} ${W / 2 - 6}v12`} stroke="var(--text-muted)" strokeWidth={1.5} />
                {pts.map((pt, i) => pt.owned
                  ? <circle key={i} cx={pt.x} cy={pt.y} r={3 + Math.min(Math.sqrt(pt.n), 5)} fill="none" stroke="var(--series-1)" strokeWidth={1.6}><title>{pt.name}</title></circle>
                  : <circle key={i} cx={pt.x} cy={pt.y} r={4.5} fill={STATUS_COLORS[pt.st]}><title>{pt.name}</title></circle>)}
              </svg>
            </div>
          );
        })}
      </div>
      <div className="legend-row" style={{ marginTop: 12 }}>
        {(Object.keys(STATUS_COLORS) as (keyof typeof STATUS_COLORS)[]).filter((k) => k !== "none").map((k) =>
          <span key={k}><span className="dot" style={{ background: STATUS_COLORS[k] }} />{STATUS_LABEL[k]}</span>)}
        <span><span className="dot" style={{ border: "1.6px solid var(--series-1)" }} />Owned lot, no monthly listing</span>
      </div>
    </Card>
  );
}

function Events({ d, area }: Props) {
  const ev = d.panel!.events.filter((e) => area === "all" || e.area === area);
  const areaName = (id: string | null) => d.panel!.areas.find((a) => a.id === id)?.name ?? "—";
  return (
    <Card title="Changes, openings and closures" note="Rent changes, vacancy flips, new and removed listings detected between hourly snapshots. Owned-lot openings are in the Owned lots section.">
      {ev.length ? (
        <SortTable rows={ev} rowKey={(e) => e.event_utc + e.kind + (e.listing_id ?? e.lot_id)} max={200} cols={[
          { key: "t", label: "Time (JST)", sort: (e) => e.event_utc, render: (e) => jst(e.event_utc) },
          { key: "k", label: "Event", render: (e) => KIND[e.kind] ?? e.kind },
          { key: "l", label: "Lot", render: (e) => e.lot_name ?? e.lot_id },
          { key: "a", label: "Area", render: (e) => areaName(e.area) },
          { key: "d", label: "Detail", render: (e) => e.kind === "rent_change" ? `${yen(Number(e.old_value))} → ${yen(Number(e.new_value))}` : e.kind === "vacancy_change" ? `${e.old_value} → ${e.new_value}` : e.listing_id ? `listing #${e.listing_id}` : "" },
        ]} />
      ) : <p className="muted">No changes recorded yet{area !== "all" ? " in this area" : ""}. Each hourly run compares every listing with its previous state.</p>}
    </Card>
  );
}

function Coverage({ d }: Props) {
  const s = d.universe?.stats;
  return (
    <Card title="Coverage of Paraca's network" note={s ? `${num(s.union_lots)} known lots against ${num(d.summary.official_lots_total)} in operation (IR, ${d.summary.official_asof}): ${num(s.by_source.portal ?? 0)} from monthly listings, ${num(s.by_source.owned_pr ?? 0)} owned lots from opening releases, ${num(s.multi_source)} in both. Leased lots without monthly listings (most of the network) are not published anywhere that allows automated collection.` : ""}>
      <SortTable rows={d.panel!.coverage} rowKey={(r) => r.pref} initial={{ key: "k", dir: -1 }} max={60} cols={[
        { key: "p", label: "Prefecture", sort: (r) => r.pref, render: (r) => r.pref },
        { key: "k", label: "Known lots", right: true, sort: (r) => r.known, render: (r) => num(r.known) },
        { key: "m", label: "With monthly listings", right: true, sort: (r) => r.portal, render: (r) => num(r.portal) },
        { key: "o", label: "Owned (releases)", right: true, sort: (r) => r.owned, render: (r) => num(r.owned) },
      ]} />
    </Card>
  );
}

function Measured({ d }: Props) {
  const q = d.quality;
  const runs = [...q.runs].reverse().slice(0, 48);
  return (
    <Card title="How this is measured" note={`A panel of ${num(d.universe?.stats.union_lots ?? d.summary.lots)} known Paraca lots, refreshed every hour.`}>
      <dl className="deflist">
        <dt>Source</dt><dd>Paraca's monthly-parking search (sweet.paraca.co.jp), every prefecture, 50 listings per page. Each listing shows 申込可能 (open) or 空き待ち (waitlisted). Owned lots come from Paraca's monthly opening releases on paraca.co.jp, geocoded with GSI (国土地理院).</dd>
        <dt>Waitlist share</dt><dd>Listings shown 空き待ち, divided by listings that show a flag. Listings with no flag are left out. A listing is one product at a lot (car, bike, pass), so large lots count more than once.</dd>
        <dt>Markets</dt><dd>The 16 Times reference markets, each a fixed centre with a 2.5 km radius, matched by straight-line distance.</dd>
        <dt>Not measured</dt><dd>Hourly occupancy, hourly fees and per-lot capacity. No permitted source publishes them for Paraca lots (see docs/feasibility.md). The waitlist flag is a monthly supply signal and is not comparable with Times' 空/混/満 or Park24's occupancy.</dd>
        <dt>Schedule</dt><dd>One batch every hour at :17 UTC on GitHub Actions (about 50 requests at 3-second spacing). Each job runs for about three hours and starts the next; a cron safety net restarts the chain. Unchanged listings are stored once per JST day, and every change is kept.</dd>
        <dt>Limits</dt><dd>Covers the part of the network that offers monthly contracts or was opened as an owned lot since 2008. Owned lots may have been sold since they opened. Private research use; not affiliated with Paraca.</dd>
      </dl>
      <h3 style={{ margin: "22px 0 10px", fontSize: 16 }}>Recent runs</h3>
      <SortTable rows={runs} rowKey={(r) => r.run_id} max={48} cols={[
        { key: "t", label: "Started (JST)", render: (r) => jst(r.started_utc) },
        { key: "s", label: "Source", render: (r) => r.source },
        { key: "st", label: "Status", render: (r) => <span className={"status " + (r.status === "ok" ? "open" : "waitlist")}><span className="dot" />{r.status}</span> },
        { key: "rq", label: "Requests", right: true, render: (r) => num(r.requests) },
        { key: "er", label: "Errors", right: true, render: (r) => num(r.errors) },
        { key: "ls", label: "Rows", right: true, render: (r) => num(r.listings_seen) },
        { key: "du", label: "Duration", right: true, render: (r) => `${Math.round(r.duration_s)}s` },
      ]} />
    </Card>
  );
}
