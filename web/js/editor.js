import { el } from "./dom.js";
import { saveTask, deleteTask } from "./store.js";
import { loadSteps, stepInput } from "./steps.js";
import { dateField } from "./datefmt.js";

// One task is edited at a time, in place, wherever its Edit button was pressed.
// ed.id = task id; ed.from = id of the Edit button to return focus to.
const ed = { id: null, from: null, draft: null, confirm: false, error: "", busy: false };
const subs = new Set();
export const onEditChange = (fn) => { subs.add(fn); };
const changed = () => subs.forEach((fn) => fn());
const focusLater = (sel) => requestAnimationFrame(() => document.querySelector(sel)?.focus());

export const isEditing = (t) => ed.id === t.id && !t.closed;

export function editButton(t, prefix) {
  const id = `${prefix}-edit-${t.id}`;
  // Done tasks can't be edited (like Move); reopen them first.
  return el("button", { type: "button", id, class: "edit-btn", "aria-label": `Edit: ${t.title}`, disabled: t.closed,
    title: t.closed ? "Reopen the task to edit it" : null,
    onclick: () => {
      const draft = { title: t.title, step: t.step || "", priority: t.priority, due_date: t.due_date, due_time: t.due_time || "" };
      Object.assign(ed, { id: t.id, from: id, draft, confirm: false, error: "", busy: false });
      loadSteps(); changed();
      focusLater(".page:not([hidden]) .edit-form [name=title]");
    } }, "Edit");
}

function close(focusBack = true) {
  const from = ed.from;
  Object.assign(ed, { id: null, from: null, draft: null, confirm: false, error: "", busy: false });
  changed();
  if (focusBack && from) focusLater("#" + CSS.escape(from));
  else focusLater("#main");
}

export function editForm(t) {
  const v = ed.draft;   // survives re-renders (errors, delete confirm, background reloads)
  const fld = (label, node) => el("label", { class: "ef" }, el("span", {}, label), node);
  async function save(e) {
    e.preventDefault();
    if (!v.title.trim()) { ed.error = "Title can't be empty."; changed(); return; }
    if (!v.due_date) { ed.error = "Pick a date."; changed(); return; }
    ed.busy = true; ed.error = ""; changed();
    try {
      await saveTask(t.id, { title: v.title, step: v.step || null, priority: v.priority, due_date: v.due_date, due_time: v.due_time || null });
      loadSteps(); close();
    } catch (err) { ed.busy = false; ed.error = err.message; changed(); }
  }
  async function del() {
    ed.busy = true; changed();
    try { await deleteTask(t.id); close(false); }
    catch (err) { ed.busy = false; ed.error = err.message; changed(); }
  }
  const actions = ed.confirm
    ? [el("span", { class: "ef-warn", role: "alert" }, "Delete this task? This can't be undone."),
       el("button", { type: "button", class: "set-btn danger", disabled: ed.busy, onclick: del }, "Delete"),
       el("button", { type: "button", class: "set-btn", id: "ef-keep", onclick: () => { ed.confirm = false; changed(); focusLater(".page:not([hidden]) .edit-form .ef-del"); } }, "Keep")]
    : [el("button", { type: "submit", class: "set-btn primary", disabled: ed.busy }, ed.busy ? "Saving…" : "Save"),
       el("button", { type: "button", class: "set-btn", onclick: () => close() }, "Cancel"),
       el("button", { type: "button", class: "set-btn ef-del", onclick: () => { ed.confirm = true; changed(); focusLater(".page:not([hidden]) #ef-keep"); } }, "Delete…")];
  return el("form", { class: "edit-form", "aria-label": `Edit task: ${t.title}`, onsubmit: save,
    onkeydown: (e) => { if (e.key === "Escape") { e.preventDefault(); close(); } } },
    fld("Title", el("input", { type: "text", name: "title", value: v.title, maxlength: 200, required: true, oninput: (e) => { v.title = e.target.value; } })),
    el("div", { class: "ef-row" },
      fld("Step (tag)", stepInput({ name: "step", placeholder: "None" }, v.step, (x) => { v.step = x; })),
      fld("Priority", el("select", { name: "priority", onchange: (e) => { v.priority = e.target.value; } },
        ["High", "Medium", "Low"].map((p) => el("option", { value: p, selected: p === v.priority }, p)))),
      fld("Date", dateField({ name: "due_date", label: "due date", value: v.due_date, required: true, onchange: (x) => { v.due_date = x; } })),
      fld("Time", el("input", { type: "time", name: "due_time", value: v.due_time, onchange: (e) => { v.due_time = e.target.value; } }))),
    ed.error ? el("p", { class: "ef-err", role: "alert" }, ed.error) : null,
    el("div", { class: "ef-actions" }, actions));
}
