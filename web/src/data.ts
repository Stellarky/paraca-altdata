// Data contracts (mirror paraca/export.py) and loader.
export type Vac = "open" | "waitlist" | "unknown";

export interface ListingRec { id: string; veh: string; ct: string; eq: string[]; note: string | null; rent: number | null; dep: number | null; key: number | null; vac: Vac; url: string; seen: string; }
export interface Lot { id: string; name: string; addr: string; lat: number | null; lng: number | null; pref: string; area: string | null; dist: number | null; first: string; last: string; listings: ListingRec[]; }
export interface AreaPoint { d: string; listings: number; open: number | null; rent: number | null; }
export interface Area { id: string; name: string; ja: string; lat: number; lng: number; radius_km: number; lots: number; listings: number; open_share: number | null; median_car_rent: number | null; car_listings: number; displayed: boolean; series: AreaPoint[]; }
export interface Run { run_id: string; source: string; started_utc: string; finished_utc?: string; status: string; requests: number; errors: number; pages: number; listings_seen: number; duration_s: number; note: string; }
export interface Summary {
  generated_utc: string; operator: string; last_run: Run | null; runs_total: number; runs_ok: number;
  lots: number; listings: number; prefectures: number; car_monthly_listings: number; median_car_rent: number | null; open_share: number | null;
  first_observation_utc: string | null; official_lots_total: number | null; official_spaces_total: number | null; official_asof: string | null;
  hourly: { available: boolean; observations: number; reason: string };
  rent_hist: { bin: number; n: number }[]; price_changes: number; areas: Area[];
  prefectures_table: { pref: string; lots: number; listings: number; open_share: number | null; median_car_rent: number | null }[];
  national_series: { d: string; listings: number; open: number | null; car_open: number | null; rent: number | null }[];
}
export interface Event { event_utc: string; run_id: string; kind: string; lot_id: string; listing_id: string | null; old_value: string | null; new_value: string | null; }
export interface Quarter {
  fy: number; q: number; label: string; start: string; end: string; days: number; release_date: string; source_url: string;
  revenue: number | null; operating_profit: number | null; ordinary_profit: number | null; net_income: number | null;
  revenue_leased: number | null; revenue_owned: number | null; revenue_other: number | null;
  lots_leased: number | null; spaces_leased: number | null; lots_owned: number | null; spaces_owned: number | null; lots_total: number | null; spaces_total: number | null;
  avg_spaces: number | null; rev_per_space_day_yen: number | null; op_margin: number | null; spaces_interpolated?: boolean;
}
export interface Financials { quarters: Quarter[]; guidance: Record<string, any>; guidance_fy: number; annual: Record<string, any>[]; fiscal_year_end: string; notes: string[]; }
export interface ModelStat { mape: number | null; n: number; sd: number | null; bias: number | null; desc: string; }
export interface Forecast {
  backtest: { rows: Record<string, any>[]; models: Record<string, ModelStat>; best: string | null };
  next: null | { label: string; start: string; end: string; model: string; predictions: Record<string, number>; assumptions: Record<string, number>;
    revenue_point: number; revenue_lo: number; revenue_hi: number; interval_note: string; guidance_implied_q4?: number; full_year_model?: number; full_year_guidance?: number; cum_q1_q3?: number };
  altdata_link: { status: string; first_observation: string | null; note: string };
}
export interface Quality { generated_utc: string; flags: Record<string, number>; runs: Run[]; requests_total: number; failed_runs: number;
  coverage: { portal_lots: number; official_lots: number | null; share_of_official: number | null; hourly_status_coverage: number | null }; biases: string[]; }

export interface Bundle { summary: Summary; lots: Lot[]; events: Event[]; financials: Financials; forecast: Forecast; quality: Quality; source: string; }

export const REPO = "https://github.com/Stellarky/paraca-altdata";
const DEFAULT_BASE = "https://raw.githubusercontent.com/Stellarky/paraca-altdata/data/web/";

declare global { interface Window { __PARACA_DATA__?: Omit<Bundle, "source">; } }

export async function loadAll(): Promise<Bundle> {
  if (window.__PARACA_DATA__) return { ...window.__PARACA_DATA__, source: "embedded snapshot" };
  const base = (import.meta.env.VITE_DATA_BASE as string | undefined) || DEFAULT_BASE;
  const bust = `?t=${Math.floor(Date.now() / 300000)}`; // refresh at most every 5 min
  const get = async (f: string) => {
    const r = await fetch(base + f + bust);
    if (!r.ok) throw new Error(`${f}: HTTP ${r.status}`);
    return r.json();
  };
  const [summary, lots, events, financials, forecast, quality] = await Promise.all(
    ["summary.json", "lots.json", "events.json", "financials.json", "forecast.json", "quality.json"].map(get));
  return { summary, lots, events, financials, forecast, quality, source: base };
}
