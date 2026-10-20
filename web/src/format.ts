export const yen = (v: number | null | undefined) => (v == null ? "—" : "¥" + Math.round(v).toLocaleString("en-US"));
export const num = (v: number | null | undefined, d = 0) => (v == null ? "—" : v.toLocaleString("en-US", { maximumFractionDigits: d, minimumFractionDigits: d }));
export const pct = (v: number | null | undefined, d = 1) => (v == null ? "—" : (v * 100).toFixed(d) + "%");
export const mn = (v: number | null | undefined) => (v == null ? "—" : "¥" + Math.round(v).toLocaleString("en-US") + "mn");
export const signedPct = (v: number | null | undefined, d = 1) => (v == null ? "—" : (v >= 0 ? "+" : "") + (v * 100).toFixed(d) + "%");

const JST = "Asia/Tokyo";
export const jst = (iso: string | null | undefined, withTime = true) => {
  if (!iso) return "—";
  const d = new Date(iso);
  const s = d.toLocaleString("sv-SE", { timeZone: JST, hour12: false });
  return (withTime ? s.slice(0, 16) : s.slice(0, 10)) + (withTime ? " JST" : "");
};
export const ago = (iso: string | null | undefined) => {
  if (!iso) return "—";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 90) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400 * 2) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} days ago`;
};
export const median = (xs: (number | null | undefined)[]) => {
  const a = xs.filter((x): x is number => x != null).sort((p, q) => p - q);
  if (!a.length) return null;
  const m = Math.floor(a.length / 2);
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
};
export const openShare = (vs: string[]) => {
  const k = vs.filter((v) => v === "open" || v === "waitlist");
  return k.length ? k.filter((v) => v === "open").length / k.length : null;
};
export const VEH_EN: Record<string, string> = { 自動車: "Car", バイク: "Motorbike", 自転車: "Bicycle" };
export const CT_EN: Record<string, string> = { 月極: "Monthly", 全日パス: "All-day pass", 平日パス: "Weekday pass" };
export const VAC_EN: Record<string, string> = { open: "Open", waitlist: "Waitlist", unknown: "No flag" };
