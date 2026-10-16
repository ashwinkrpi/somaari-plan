import { el, swap } from "./dom.js";
import { todayIso, addDays, weekStart, rangeLabel, DOW, dayNum, dowIndex } from "./dates.js";
import { fmtDate, onFormatChange } from "./datefmt.js";
import { subscribe, toggleDone, saveTask } from "./store.js";
import { editButton, editForm, isEditing, onEditChange } from "./editor.js";

const LANES = ["High", "Medium", "Low"];
const db = { anchor: weekStart(todayIso()), tasks: [], lastMoved: 0, error: "", moving: null, status: "" };

async function load() {
  const from = addDays(db.anchor, -7), to = addDays(db.anchor, 6);
  try {
    const [r, m] = await Promise.all([fetch(`/api/tasks?from=${from}&to=${to}`),
      fetch(`/api/moved?from=${from}&to=${addDays(db.anchor, -1)}`)]);
    if (!r.ok || !m.ok) throw new Error("Could not load tasks");
    db.tasks = await r.json(); db.lastMoved = (await m.json()).moved; db.error = "";
  } catch (e) { db.error = e.message; }
  render();
}

async function moveTask(id, due_date, priority) {
  db.moving = null;
  db.status = `Moved to ${fmtDate(due_date)}, ${priority}.`;
  try { await saveTask(id, { due_date, priority }); }   // the store emit reloads the board
  catch (e) { db.status = "Could not move task."; render(); }
}

export function summarise(tasks, anchor, lastMoved = 0) {
  const end = addDays(anchor, 6), prev = addDays(anchor, -7);
  const cur = tasks.filter((t) => t.due_date >= anchor && t.due_date <= end);
  const last = tasks.filter((t) => t.due_date >= prev && t.due_date < anchor);
  const steps = {};
  for (const t of cur) {
    const k = t.step || "No step";
    steps[k] ||= { done: 0, total: 0 };
    steps[k].total++; if (t.closed) steps[k].done++;
  }
  return {
    done: cur.filter((t) => t.closed).length, planned: cur.length, steps,
    lastDone: last.filter((t) => t.closed).length, lastPlanned: last.length,
    carried: last.filter((t) => !t.closed).length, lastMoved,
  };
}

function band(s) {
  const steps = Object.entries(s.steps);
  return el("div", { class: "band" },
    el("div", { class: "bcell" }, el("div", { class: "blab" }, "This week"),
      el("div", { class: "bbig" }, `${s.done}/${s.planned}`), el("div", { class: "bsub" }, "done / planned")),
    el("div", { class: "bcell" }, el("div", { class: "blab" }, "Progress by step"),
      steps.length ? steps.map(([k, v]) => el("div", { class: "step" },
        el("div", { class: "steptxt" }, el("span", {}, k), el("span", {}, `${v.done}/${v.total}`)),
        el("div", { class: "bar", role: "progressbar", "aria-label": k, "aria-valuemin": "0", "aria-valuemax": String(v.total), "aria-valuenow": String(v.done) },
          el("div", { class: "fill", style: `width:${Math.round((100 * v.done) / v.total)}%` }))))
        : el("div", { class: "bsub" }, "No tasks this week")),
    el("div", { class: "bcell" }, el("div", { class: "blab" }, "Last week"),
      el("div", { class: "bbig" }, `${s.lastDone}/${s.lastPlanned}`),
      el("div", { class: "bsub" }, `done / planned, ${s.lastMoved} moved, ${s.carried} not done`)));
}

async function markDone(t) {
  db.status = `Done: ${t.title}.`;
  await toggleDone(t); // reloads Today/Calendar; the store emit reloads the board
}

function card(t, today) {
  const sel = db.moving === t.id;
  const due = !t.closed && t.due_date <= today;
  if (isEditing(t)) return el("li", { class: "card editing" }, editForm(t));
  return el("li", { class: "card" + (sel ? " selected" : "") + (t.closed ? " is-done" : ""), draggable: String(!t.closed),
    ondragstart: (e) => { e.dataTransfer.setData("text/plain", String(t.id)); e.dataTransfer.effectAllowed = "move"; } },
    el("div", { class: "ctitle" }, t.title), t.step ? el("div", { class: "cstep" }, t.step) : null,
    el("div", { class: "cact" },
      el("button", { type: "button", class: "mv", "aria-pressed": String(sel), disabled: t.closed,
        title: t.closed ? "Reopen the task to move it" : null,
        onclick: () => { db.moving = sel ? null : t.id; db.status = sel ? "" : `Moving: ${t.title}. Choose a cell.`; render(); } },
        sel ? "Selected" : "Move"),
      due ? el("button", { type: "button", class: "mv", "aria-label": `Mark done: ${t.title}`, onclick: () => markDone(t) }, "Done") : null,
      Object.assign(editButton(t, "d"), { className: "mv" })));
}

function cell(d, lane, list, today) {
  const go = (id) => moveTask(id, d, lane);
  return el("div", { class: "bcellx" + (dowIndex(d) >= 5 ? " weekend" : "") + (d === today ? " is-today" : ""), role: "group", "aria-label": `${fmtDate(d)} ${lane}`,
    ondragover: (e) => { e.preventDefault(); e.currentTarget.classList.add("over"); },
    ondragleave: (e) => e.currentTarget.classList.remove("over"),
    ondrop: (e) => { e.preventDefault(); e.currentTarget.classList.remove("over"); const id = +e.dataTransfer.getData("text/plain"); if (id) go(id); } },
    el("ul", { class: "cards" }, list.map((t) => card(t, today))),
    db.moving != null ? el("button", { type: "button", class: "here", onclick: () => go(db.moving) }, "Move here") : null);
}

function board() {
  const today = todayIso(), days = Array.from({ length: 7 }, (_, i) => addDays(db.anchor, i));
  const wk = db.tasks.filter((t) => t.due_date >= db.anchor && t.due_date <= days[6]);
  const grid = [el("div", { class: "bhead" })];
  days.forEach((d, i) => grid.push(el("div", { class: "bhead" + (i >= 5 ? " weekend" : "") + (d === today ? " is-today" : "") }, `${DOW[i]} ${+dayNum(d)}`)));
  for (const lane of LANES) {
    grid.push(el("div", { class: "lane" }, lane));
    for (const d of days) grid.push(cell(d, lane, wk.filter((t) => t.due_date === d && t.priority === lane), today));
  }
  return el("div", { class: "scroll" }, el("div", { class: "board" }, grid));
}

function render() {
  const page = document.getElementById("page-dashboard");
  const s = summarise(db.tasks, db.anchor, db.lastMoved);
  const cur = db.anchor === weekStart(todayIso());
  document.getElementById("nav-dash").textContent = cur ? `${s.done}/${s.planned}` : "";
  const host = page.querySelector(".dash-host");
  if (db.error) { swap(host, el("p", { class: "empty", role: "alert" }, db.error)); return; }
  swap(host,
    el("div", { class: "cal-bar" }, el("div", { class: "seg" }, el("strong", {}, rangeLabel("week", db.anchor)),
      el("button", { type: "button", "data-nav": "prev", "aria-label": "Previous week", onclick: () => step(-1) }, "←"),
      el("button", { type: "button", "data-nav": "today", onclick: () => { db.anchor = weekStart(todayIso()); load(); } }, "This week"),
      el("button", { type: "button", "data-nav": "next", "aria-label": "Next week", onclick: () => step(1) }, "→")),
      db.moving != null ? el("button", { type: "button", class: "mv", onclick: () => { db.moving = null; db.status = "Move cancelled."; render(); } }, "Cancel") : null),
    band(s),
    el("p", { class: "status", role: "status" }, db.status),
    s.planned ? board() : el("p", { class: "empty" }, "No tasks this week."));
}
function step(n) { db.anchor = addDays(db.anchor, 7 * n); db.status = ""; load(); }

export function initDashboard() { subscribe(load); onEditChange(render); onFormatChange(render); load(); }
