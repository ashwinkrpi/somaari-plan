import { loadToday } from "./store.js";
import "./today.js";
import { initCalendar } from "./calendar.js";
import { initDashboard } from "./dashboard.js";
import { initSettings } from "./settings.js";
import { initPlan } from "./plan.js";
import { initDone } from "./done.js";
import { initAbout } from "./about.js";
import { loadDateFormat } from "./datefmt.js";
import { IST } from "./dates.js";

const ROUTES = ["today", "calendar", "dashboard", "done", "new", "settings", "about"];

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

for (const b of document.querySelectorAll(".nav")) {
  b.addEventListener("click", () => { location.hash = "#/" + b.dataset.route; });
}
window.addEventListener("hashchange", render);
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
