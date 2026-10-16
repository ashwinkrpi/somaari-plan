import { loadToday } from "./store.js";
import "./today.js";
import { initCalendar } from "./calendar.js";
import { initDashboard } from "./dashboard.js";
import { initSettings } from "./settings.js";
import { initPlan } from "./plan.js";
import { initDone } from "./done.js";
import { initAbout } from "./about.js";
import { loadDateFormat } from "./datefmt.js";

const ROUTES = ["today", "calendar", "dashboard", "done", "new", "settings", "about"];
const IST = "Asia/Kolkata";

function route() {
  const r = location.hash.replace(/^#\/?/, "");
  return ROUTES.includes(r) ? r : "today";
}

function render() {
  const cur = route();
  for (const r of ROUTES) document.getElementById("page-" + r).hidden = r !== cur;
  for (const b of document.querySelectorAll(".nav")) {
    if (b.dataset.route === cur) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  }
  document.title = "somaari-plan";
}

function isoWeek(d) {
  const t = new Date(Date.UTC(d.y, d.m - 1, d.d));
  const day = t.getUTCDay() || 7;
  t.setUTCDate(t.getUTCDate() + 4 - day);
  const y0 = Date.UTC(t.getUTCFullYear(), 0, 1);
  return { week: Math.ceil(((t - y0) / 864e5 + 1) / 7), year: t.getUTCFullYear() };
}

function renderDate() {
  const now = new Date();
  const f = (o) => new Intl.DateTimeFormat("en-GB", { timeZone: IST, ...o }).format(now);
  document.getElementById("date-day").textContent = f({ day: "2-digit" });
  document.getElementById("date-rest").textContent = f({ weekday: "long" }) + " " + f({ month: "long" });
  const w = isoWeek({ y: +f({ year: "numeric" }), m: +f({ month: "numeric" }), d: +f({ day: "numeric" }) });
  document.getElementById("week-label").textContent =
    "Week " + String(w.week).padStart(2, "0") + " / " + w.year;
}

const MODES = ["auto", "light", "dark"];
function applyTheme(mode) {
  if (mode === "light" || mode === "dark") document.documentElement.dataset.theme = mode;
  else delete document.documentElement.dataset.theme;
  const b = document.getElementById("theme-toggle");
  b.textContent = "Theme: " + mode;
}
function initTheme() {
  let mode = "auto";
  try { mode = localStorage.getItem("theme") || "auto"; } catch (e) {}
  if (!MODES.includes(mode)) mode = "auto";
  applyTheme(mode);
  document.getElementById("theme-toggle").addEventListener("click", () => {
    mode = MODES[(MODES.indexOf(mode) + 1) % MODES.length];
    try {
      if (mode === "auto") localStorage.removeItem("theme");
      else localStorage.setItem("theme", mode);
    } catch (e) {}
    applyTheme(mode);
  });
}

for (const b of document.querySelectorAll(".nav")) {
  b.addEventListener("click", () => { location.hash = "#/" + b.dataset.route; });
}
window.addEventListener("hashchange", render);
initTheme();
renderDate();
render();
await loadDateFormat();   // before pages render dates
loadToday();
initCalendar();
initDashboard();
initSettings();
initPlan();
initDone();
initAbout();
