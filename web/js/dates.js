export const IST = "Asia/Kolkata";
const MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const MONL = ["January","February","March","April","May","June","July","August","September","October","November","December"];
const DOW = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
export { MON, MONL, DOW };

export function todayIso() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: IST, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
}
const toUtc = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(Date.UTC(y, m - 1, d)); };
const fromUtc = (t) => t.toISOString().slice(0, 10);
export function addDays(s, n) { const t = toUtc(s); t.setUTCDate(t.getUTCDate() + n); return fromUtc(t); }
export function addMonths(s, n) {
  const t = toUtc(s); const d = t.getUTCDate(); t.setUTCDate(1); t.setUTCMonth(t.getUTCMonth() + n);
  const last = new Date(Date.UTC(t.getUTCFullYear(), t.getUTCMonth() + 1, 0)).getUTCDate();
  t.setUTCDate(Math.min(d, last)); return fromUtc(t);
}
export function weekStart(s) { const t = toUtc(s); return addDays(s, -((t.getUTCDay() + 6) % 7)); }
export function monthStart(s) { return s.slice(0, 8) + "01"; }
export function monthEnd(s) { const t = toUtc(s); return fromUtc(new Date(Date.UTC(t.getUTCFullYear(), t.getUTCMonth() + 1, 0))); }
export function dowIndex(s) { return (toUtc(s).getUTCDay() + 6) % 7; }
export function dayNum(s) { return s.slice(8); }
export function fmtDay(s) { return `${DOW[dowIndex(s)]} ${+s.slice(8)} ${MON[+s.slice(5, 7) - 1]}`; }
// created_at / closed_at are already IST ISO strings; no timezone conversion needed.
export function fmtStamp(iso) {
  if (!iso) return "";
  return `${+iso.slice(8, 10)} ${MON[+iso.slice(5, 7) - 1]} ${iso.slice(11, 16)}`;
}
export function rangeLabel(view, a) {
  if (view === "month") return `${MONL[+a.slice(5, 7) - 1]} ${a.slice(0, 4)}`;
  if (view === "day") return `${fmtDay(a)} ${a.slice(0, 4)}`;
  const s = weekStart(a), e = addDays(s, 6);
  return `${+s.slice(8)} ${MON[+s.slice(5, 7) - 1]} – ${+e.slice(8)} ${MON[+e.slice(5, 7) - 1]}`;
}
export function rangeOf(view, a) {
  if (view === "day") return [a, a];
  if (view === "week") { const s = weekStart(a); return [s, addDays(s, 6)]; }
  const s = weekStart(monthStart(a)), e = addDays(weekStart(monthEnd(a)), 6);
  return [s, e];
}
