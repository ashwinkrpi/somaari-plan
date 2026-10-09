import { el } from "./dom.js";

// User-chosen date format ([ui] date_format in config.toml, set on the Settings page).
// Native <input type=date> shows the browser's locale format (often mm/dd/yyyy) and can't be changed,
// so dates are typed in a text box in this format; the 📅 button opens the browser's calendar.
export const FORMATS = ["dd/mm/yyyy", "mm/dd/yyyy", "yyyy-mm-dd"];
let fmt = "dd/mm/yyyy";
const subs = new Set();
export const onFormatChange = (fn) => { subs.add(fn); };
export const dateFormat = () => fmt;

export async function loadDateFormat() {
  try {
    const r = await fetch("/api/settings");
    if (r.ok) setDateFormat((await r.json()).ui?.date_format, false);
  } catch (e) { /* keep the default */ }
}
export function setDateFormat(f, notify = true) {
  if (!FORMATS.includes(f) || f === fmt) return;
  fmt = f;
  if (notify) subs.forEach((fn) => fn());
}

// "2026-10-17" -> "17/10/2026" (or the chosen format). Empty in, empty out.
export function fmtDate(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.slice(0, 10).split("-");
  return fmt === "yyyy-mm-dd" ? `${y}-${m}-${d}` : fmt === "mm/dd/yyyy" ? `${m}/${d}/${y}` : `${d}/${m}/${y}`;
}

// Typed text -> "YYYY-MM-DD" or null. Accepts / - . or spaces, 1–2 digit day/month, 2- or 4-digit year,
// and always accepts ISO "2026-10-17".
export function parseDate(text) {
  const s = (text || "").trim();
  let y, m, d;
  const iso = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (iso) [, y, m, d] = iso;
  else {
    const p = s.split(/[\/.\-\s]+/);
    if (p.length !== 3 || p.some((x) => !/^\d+$/.test(x))) return null;
    if (fmt === "yyyy-mm-dd") [y, m, d] = p;
    else if (fmt === "mm/dd/yyyy") [m, d, y] = p;
    else [d, m, y] = p;
  }
  y = +y; m = +m; d = +d;
  if (y < 100) y += 2000;
  const t = new Date(Date.UTC(y, m - 1, d));
  if (t.getUTCFullYear() !== y || t.getUTCMonth() !== m - 1 || t.getUTCDate() !== d) return null;
  return t.toISOString().slice(0, 10);
}

// A date input that shows and accepts the chosen format. value/min are ISO; onchange(iso) fires with a valid date.
// attrs go on the text box (id, aria-label, name, required).
export function dateField({ value = "", min = "", onchange, label = "date", ...attrs }) {
  const text = el("input", {
    type: "text", inputmode: "numeric", autocomplete: "off", class: "date-text", value: fmtDate(value),
    placeholder: fmt.toUpperCase(), title: "Format " + fmt, ...attrs,
    onchange: (e) => {
      const raw = e.target.value.trim();
      if (!raw) { e.target.setCustomValidity(""); return; }   // `required` covers empty
      const v = parseDate(raw);
      const msg = !v ? `Use ${fmt}` : min && v < min ? `Pick ${fmtDate(min)} or later` : "";
      e.target.setCustomValidity(msg);
      if (msg) { e.target.reportValidity(); return; }
      e.target.value = fmtDate(v);
      onchange(v);
    },
  });
  const native = el("input", { type: "date", class: "date-native", tabindex: "-1", "aria-hidden": "true", min: min || null,
    onchange: (e) => {
      if (!e.target.value) return;
      text.value = fmtDate(e.target.value); text.setCustomValidity("");
      onchange(e.target.value); text.focus();
    } });
  const btn = el("button", { type: "button", class: "date-btn", "aria-label": `Choose ${label} from a calendar`,
    onclick: () => {
      native.value = parseDate(text.value) || value || "";
      try { native.showPicker(); } catch (e) { text.focus(); }
    } }, "📅");
  return el("span", { class: "date-field" }, text, btn, native);
}
