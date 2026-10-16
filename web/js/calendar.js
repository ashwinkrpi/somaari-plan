import { el, swap } from "./dom.js";
import { todayIso, addDays, addMonths, rangeLabel, rangeOf, weekStart, dayNum, fmtDay, DOW, dowIndex } from "./dates.js";
import { state, subscribe, loadCal } from "./store.js";
import { taskRow } from "./today.js";
import { onEditChange } from "./editor.js";

const cal = { view: "week", anchor: todayIso() };

function fetchRange() { return loadCal(rangeOf(cal.view, cal.anchor)); }
function step(n) {
  cal.anchor = cal.view === "month" ? addMonths(cal.anchor, n) : addDays(cal.anchor, cal.view === "week" ? 7 * n : n);
  fetchRange();
}
function byDate() {
  const m = {};
  for (const t of state.cal) (m[t.due_date] ||= []).push(t);
  return m;
}
const item = (t) => el("li", { class: "ci" + (t.closed ? " done" : t.priority === "High" ? " high" : "") }, t.title);

function weekView(m) {
  const s = weekStart(cal.anchor), today = todayIso();
  return el("div", { class: "scroll" }, el("div", { class: "week" },
    Array.from({ length: 7 }, (_, i) => {
      const d = addDays(s, i);
      return el("div", { class: "wcol" + (i >= 5 ? " weekend" : "") + (d === today ? " is-today" : "") },
        el("div", { class: "wdow" }, DOW[i]), el("div", { class: "wnum" }, dayNum(d)),
        el("ul", { class: "cis" }, (m[d] || []).map(item)));
    })));
}
function monthView(m) {
  const [from, to] = rangeOf("month", cal.anchor), today = todayIso(), cur = cal.anchor.slice(0, 7);
  const cells = [];
  for (let d = from; d <= to; d = addDays(d, 1)) {
    const n = (m[d] || []).length;
    cells.push(el("div", { class: "mcell" + (d.slice(0, 7) !== cur ? " out" : "") + (dowIndex(d) >= 5 ? " weekend" : "") + (d === today ? " is-today" : "") },
      el("span", { class: "mnum" }, String(+dayNum(d))), n ? el("span", { class: "mcount" }, `${n} task${n > 1 ? "s" : ""}`) : null));
  }
  return el("div", { class: "scroll" }, el("div", { class: "month" },
    DOW.map((x, i) => el("div", { class: "mdow" + (i >= 5 ? " weekend" : "") }, x)), cells));
}
function dayView(m) {
  const list = m[cal.anchor] || [];
  return list.length ? el("ol", { class: "rows" }, list.map((t, i) => taskRow(t, i, "c"))) : el("p", { class: "empty" }, "No tasks on " + fmtDay(cal.anchor) + ".");
}

export function renderCalendar() {
  const page = document.getElementById("page-calendar");
  document.getElementById("h-calendar").textContent = rangeLabel(cal.view, cal.anchor);
  for (const b of page.querySelectorAll("[data-view]")) b.setAttribute("aria-pressed", String(b.dataset.view === cal.view));
  const m = byDate();
  const body = state.error ? el("p", { class: "empty", role: "alert" }, state.error)
    : cal.view === "week" ? weekView(m) : cal.view === "month" ? monthView(m) : dayView(m);
  swap(page.querySelector(".cal-body"), body);
}

export function initCalendar() {
  const page = document.getElementById("page-calendar");
  for (const b of page.querySelectorAll("[data-view]")) b.addEventListener("click", () => { cal.view = b.dataset.view; fetchRange(); });
  page.querySelector("[data-nav=prev]").addEventListener("click", () => step(-1));
  page.querySelector("[data-nav=next]").addEventListener("click", () => step(1));
  page.querySelector("[data-nav=today]").addEventListener("click", () => { cal.anchor = todayIso(); fetchRange(); });
  subscribe(renderCalendar);
  onEditChange(renderCalendar);
  fetchRange();
}
