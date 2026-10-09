import { el, swap } from "./dom.js";
import { fmtStamp, fmtDay, weekStart, rangeLabel, todayIso, addDays } from "./dates.js";
import { subscribe, saveTask } from "./store.js";
import { dateField, onFormatChange } from "./datefmt.js";

// Done page: finished tasks, newest first, grouped by the week they were closed (D-09). Archive = done.
const LIMIT = 500;
const dn = { q: "", tasks: [], loaded: false, error: "", status: "", picking: null, pickDate: "" };
let timer = null;

async function load() {
  try {
    const r = await fetch(`/api/done?limit=${LIMIT}` + (dn.q ? `&q=${encodeURIComponent(dn.q)}` : ""));
    if (!r.ok) throw new Error("Could not load done tasks");
    dn.tasks = await r.json(); dn.error = "";
  } catch (e) { dn.error = e.message; }
  dn.loaded = true; render();
}

// Reopened tasks never land in the past: plain Reopen moves a past due date to today (the server enforces it too);
// "Reopen on…" picks today or a later day.
async function reopen(t, day) {
  try {
    const r = await saveTask(t.id, day ? { closed: false, due_date: day } : { closed: false });
    dn.picking = null;
    dn.status = `Reopened for ${r.due_date === todayIso() ? "today" : fmtDay(r.due_date)}: ${t.title}.`;   // emit reloads this list
  } catch (e) { dn.status = e.message; render(); return; }
  requestAnimationFrame(() => document.getElementById("done-q")?.focus());
}

function pickRow(t) {
  const today = todayIso();
  const close = () => { dn.picking = null; render(); requestAnimationFrame(() => document.getElementById(`reopen-on-${t.id}`)?.focus()); };
  return el("form", { class: "reopen-pick", onsubmit: (e) => { e.preventDefault(); if (dn.pickDate >= today) reopen(t, dn.pickDate); },
    onkeydown: (e) => { if (e.key === "Escape") { e.preventDefault(); close(); } } },
    el("label", { for: `pick-${t.id}` }, "Reopen on"),
    dateField({ id: `pick-${t.id}`, label: "reopen date", min: today, value: dn.pickDate, required: true,
      onchange: (v) => { dn.pickDate = v; } }),
    el("button", { type: "submit", class: "set-btn primary" }, "Reopen"),
    el("button", { type: "button", class: "set-btn", onclick: close }, "Cancel"));
}

function row(t) {
  return el("li", { class: "row" },
    el("div", { class: "body" }, el("div", { class: "ttl" }, t.title),
      el("div", { class: "meta" },
        el("span", { class: "badge p-" + t.priority.toLowerCase() }, t.priority),
        t.step ? el("span", {}, t.step) : null,
        el("span", {}, "Due " + fmtDay(t.due_date)),
        el("span", {}, "Closed " + fmtStamp(t.closed_at)))),
    dn.picking === t.id ? pickRow(t) : el("div", { class: "row-act" },
      el("button", { type: "button", class: "done-btn", "aria-label": `Reopen: ${t.title}`,
        title: t.due_date < todayIso() ? "Reopens for today" : `Reopens for ${fmtDay(t.due_date)}`, onclick: () => reopen(t) }, "Reopen"),
      el("button", { type: "button", id: `reopen-on-${t.id}`, class: "edit-btn", "aria-label": `Reopen on a date: ${t.title}`,
        onclick: () => {
          dn.picking = t.id; dn.pickDate = t.due_date > todayIso() ? t.due_date : addDays(todayIso(), 1); render();
          requestAnimationFrame(() => document.getElementById(`pick-${t.id}`)?.focus());
        } }, "Reopen on…")));
}

function groups() {
  const out = [];
  for (const t of dn.tasks) {
    const wk = weekStart(t.closed_at.slice(0, 10));
    if (!out.length || out[out.length - 1].wk !== wk) out.push({ wk, list: [] });
    out[out.length - 1].list.push(t);
  }
  return out;
}

function render() {
  const page = document.getElementById("page-done");
  document.getElementById("h-done").textContent = dn.loaded && !dn.q ? `Done (${dn.tasks.length}${dn.tasks.length >= LIMIT ? "+" : ""})` : "Done";
  const body = dn.error ? el("p", { class: "empty", role: "alert" }, dn.error + " ", el("button", { type: "button", class: "set-btn", onclick: load }, "Try again"))
    : !dn.loaded ? el("p", { class: "empty" }, "Loading…")
    : !dn.tasks.length ? el("p", { class: "empty" }, dn.q ? `No done tasks match “${dn.q}”.` : "Nothing done yet. Finished tasks show up here.")
    : el("div", {}, groups().map((g) => el("section", { class: "done-week", "aria-label": "Week of " + rangeLabel("week", g.wk) },
        el("h2", {}, rangeLabel("week", g.wk), el("small", {}, ` · ${g.list.length} done`)),
        el("ol", { class: "rows" }, g.list.map(row)))),
      dn.tasks.length >= LIMIT ? el("p", { class: "hint" }, `Showing the latest ${LIMIT}. Search to find older ones.`) : null);
  swap(page.querySelector(".done-host"), el("p", { class: "status", role: "status" }, dn.status), body);
}

export function initDone() {
  const q = document.getElementById("done-q");
  q.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => { dn.q = q.value.trim(); dn.status = ""; load(); }, 250);
  });
  subscribe(load);
  onFormatChange(render);
  load();
}
