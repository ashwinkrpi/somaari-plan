import { el, swap } from "./dom.js";
import { todayIso, addDays, weekStart } from "./dates.js";
import { loadToday, loadCal } from "./store.js";
import { quickPane } from "./quick.js";
import { loadSteps, stepInput } from "./steps.js";
import { dateField, onFormatChange } from "./datefmt.js";

const host = () => document.querySelector(".plan-host");
const nextMonday = () => addDays(weekStart(todayIso()), 7);
let files = [];          // {file, schedule, anchor_date}
let text = { schedule: "in_text", anchor_date: nextMonday(), per_day: 4, value: "", step: "" };
let draft = null;        // preview response, edited in place
let msg = "";
let busy = false;

function sel(id, label, opts, value, onchange) {
  const s = el("select", { id, onchange: (e) => onchange(e.target.value) },
    opts.map(([v, t]) => el("option", { value: v, selected: v === value }, t)));
  return el("div", { class: "fld" }, el("label", { for: id }, label), s);
}
function dateInput(id, label, value, onchange) {
  return el("div", { class: "fld" }, el("label", { for: id }, label),
    dateField({ id, value, label, onchange }));
}

function fileRow(f, i) {
  const needs = f.schedule === "week";
  return el("li", { class: "plan-file" },
    el("strong", {}, f.file.name),
    sel(`fs-${i}`, "Schedule", [["week", "Week starting"], ["in_text", "Dates inside the file"]], f.schedule,
      (v) => { f.schedule = v; render(); }),
    needs ? dateInput(`fd-${i}`, "Date", f.anchor_date, (v) => { f.anchor_date = v; }) : null,
    el("button", { type: "button", class: "set-btn", onclick: () => { files.splice(i, 1); render(); } }, "Remove"));
}

function inputs() {
  const pick = el("input", { id: "plan-files", type: "file", multiple: true, accept: ".md,.markdown,.txt",
    onchange: (e) => { for (const f of e.target.files) files.push({ file: f, schedule: "week", anchor_date: nextMonday() }); render(); } });
  const ts = text.schedule;
  return el("div", { class: "plan-left" },
    el("h2", {}, "01 Upload plans"),
    el("div", { class: "fld" }, el("label", { for: "plan-files" }, ".md files (several at once)"), pick),
    files.length ? el("ul", { class: "plan-files" }, files.map(fileRow)) : null,
    el("p", { class: "plan-hint" }, "Tags: each ", el("code", {}, "## heading"), " tags the tasks under it. ",
      el("code", {}, "## Step 1: Domain (this week)"), " → Domain"),
    el("h2", {}, "02 Paste text"),
    el("div", { class: "fld" }, el("label", { for: "plan-text" }, "Plan text"),
      el("textarea", { id: "plan-text", rows: 6, oninput: (e) => { text.value = e.target.value; } }, text.value)),
    sel("ts", "Schedule", [["in_text", "Use dates in the text"], ["week", "Week starting"], ["day", "A single day"]], ts,
      (v) => { text.schedule = v; render(); }),
    ts !== "in_text" ? dateInput("td", "Date", text.anchor_date, (v) => { text.anchor_date = v; }) : null,
    el("div", { class: "fld" }, el("label", { for: "tpd" }, "Tasks per day"),
      el("input", { id: "tpd", type: "number", min: 1, max: 20, value: text.per_day, onchange: (e) => { text.per_day = +e.target.value || 4; } })),
    el("div", { class: "fld" }, el("label", { for: "tstep" }, "Step (tag)"),
      stepInput({ id: "tstep", placeholder: "e.g. Domain" }, text.step, (v) => { text.step = v; })),
    el("p", { class: "plan-hint" }, "Tags: same rule as files. Lines with no ", el("code", {}, "## heading"),
      " get the Step above, or no tag."),
    el("button", { type: "button", class: "set-btn primary", disabled: busy, onclick: generate }, busy ? "Working…" : "Generate plan →"));
}

async function generate() {
  const fd = new FormData();
  for (const f of files) fd.append("files", f.file);
  fd.append("text", text.value);
  fd.append("meta", JSON.stringify({
    files: files.map((f) => ({ schedule: f.schedule, anchor_date: f.anchor_date })),
    text: { schedule: text.schedule, anchor_date: text.anchor_date, per_day: text.per_day },
  }));
  busy = true; msg = "Reading your plan…"; render();
  try {
    const r = await fetch("/api/ingest/preview", { method: "POST", body: fd });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || "Preview failed");
    for (const t of j.tasks) if (!t.step && j.sources[t.source]?.kind === "text") t.step = text.step;
    draft = j; msg = `${j.tasks.length} tasks ready to review.` + (j.ai.fallback ? " The AI was unavailable, so check the dates and priorities." : "");
  } catch (e) { msg = e.message; }
  busy = false; render();
}

function taskRow(t) {
  const flagged = t.flags.length > 0 && !t.confirmed;
  return el("li", { class: "plan-task" + (flagged ? " flagged" : "") },
    el("input", { type: "text", "aria-label": "Title", value: t.title, onchange: (e) => { t.title = e.target.value; } }),
    stepInput({ class: "step", "aria-label": "Step (tag)", placeholder: "Step" }, t.step, (v) => { t.step = v; }),
    el("select", { "aria-label": "Priority", onchange: (e) => { t.priority = e.target.value; } },
      ["High", "Medium", "Low"].map((p) => el("option", { value: p, selected: p === t.priority }, p))),
    dateField({ "aria-label": "Due date", label: "due date", value: t.due_date || "", onchange: (v) => { t.due_date = v; } }),
    el("button", { type: "button", class: "set-btn", onclick: () => { draft.tasks.splice(draft.tasks.indexOf(t), 1); render("Removed."); } }, "Remove"),
    t.flags.length ? el("span", { class: "flag" }, t.flags.join(" · "),
      el("button", { type: "button", class: "set-btn", onclick: () => { t.confirmed = true; render("Confirmed."); } }, "Looks right")) : null);
}

function preview() {
  const tasks = draft.tasks, sk = draft.skipped;
  return el("div", { class: "plan-preview" },
    el("h2", {}, "Review"),
    draft.ai.notes.length ? el("p", { class: "hint" }, draft.ai.notes.join(" ")) : null,
    tasks.length ? el("ul", { class: "plan-tasks" }, tasks.map(taskRow)) : el("p", { class: "empty" }, "No tasks found."),
    sk.length ? el("details", { class: "plan-skipped" }, el("summary", {}, `${sk.length} skipped lines`),
      el("ul", {}, sk.map((s) => el("li", {}, el("span", {}, s.text),
        el("button", { type: "button", class: "set-btn", onclick: () => {
          draft.skipped.splice(draft.skipped.indexOf(s), 1);
          draft.tasks.push({ id: s.id, source: s.source, step: s.step, title: s.text, priority: "Medium", type: "task",
            due_date: null, due_time: null, ai_conf: s.t, flags: [] });
          render("Restored.");
        } }, "Restore"))))) : null,
    el("div", { class: "set-actions" },
      el("button", { type: "button", class: "set-btn primary", disabled: busy || !tasks.length, onclick: commit }, `Add ${tasks.length} tasks to plan`),
      el("button", { type: "button", class: "set-btn", onclick: () => { draft = null; msg = ""; render(); } }, "Discard")));
}

async function commit() {
  const body = {
    sources: draft.sources.map(({ kind, name, content_sha, schedule, anchor_date, per_day }) => ({ kind, name, content_sha, schedule, anchor_date, per_day })),
    tasks: draft.tasks.map((t) => ({ source: t.source, title: t.title, step: t.step, priority: t.priority, type: t.type,
      due_date: t.due_date || null, due_time: t.due_time, ai_conf: t.ai_conf, reviewed: !(t.flags.length && !t.confirmed) })),
  };
  busy = true; render();
  try {
    const r = await fetch("/api/ingest/commit", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || "Could not save");
    msg = `Added ${j.created} tasks.`; draft = null; files = []; text.value = "";
    await Promise.all([loadToday(), loadCal(), loadSteps()]);
  } catch (e) { msg = e.message; }
  busy = false; render();
}

function render(note) {
  if (typeof note === "string") msg = note;
  const h = host();
  if (!h) return;
  swap(h, el("div", { class: "plan-cols" }, draft ? preview() : inputs(),
    quickPane()),
    el("p", { role: "status", class: "plan-status" }, msg));
}

export function initPlan() { loadSteps(); onFormatChange(() => render()); render(); }
