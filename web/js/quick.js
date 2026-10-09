import { el } from "./dom.js";
import { todayIso } from "./dates.js";
import { loadToday, loadCal } from "./store.js";
import { loadSteps, stepInput } from "./steps.js";
import { dateField, fmtDate, onFormatChange } from "./datefmt.js";

let log = [];            // [{id, text, parsed, task_id}]
let status = "";
let busy = false;
let loaded = false;
let started = false;
const pane = el("div", { class: "plan-right" });

async function load() {
  try {
    const r = await fetch("/api/quick");
    if (!r.ok) throw new Error();
    log = await r.json();
  } catch (e) { status = "Could not load the chat."; }
  loaded = true; draw(true);
}

async function send(input) {
  const text = input.value.trim();
  if (!text || busy) return;
  busy = true; status = "Reading it...";
  try {
    const r = await fetch("/api/quick", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, today: todayIso() }) });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || "Could not parse that");
    log.push(j); status = ""; input.value = "";
  } catch (e) { status = e.message; }
  busy = false; draw(true);
}

// Pending cards only come back from the server; an added card shows "Added ✓" until you leave New plan.
async function discard(m) {
  try {
    const r = await fetch(`/api/quick/${m.id}`, { method: "DELETE" });
    if (!r.ok && r.status !== 404) throw new Error((await r.json().catch(() => ({}))).error || "Could not discard");
    log = log.filter((x) => x !== m); status = `Discarded "${m.parsed.title}".`;
  } catch (e) { status = e.message; }
  draw(); pane.querySelector("#qa-input")?.focus();
}

async function clearPending() {
  try {
    const r = await fetch("/api/quick", { method: "DELETE" });
    if (!r.ok) throw new Error("Could not clear");
    const n = (await r.json()).discarded;
    log = log.filter((x) => x.task_id); status = n ? `Cleared ${n} card${n > 1 ? "s" : ""}.` : "";
  } catch (e) { status = e.message; }
  draw(); pane.querySelector("#qa-input")?.focus();
}

async function add(m) {
  const c = m.parsed;
  try {
    const r = await fetch(`/api/quick/${m.id}/add`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: c.title, step: c.step || null, type: c.type, due_date: c.date, due_time: c.time || null }) });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || "Could not add");
    Object.assign(m, j.chat);
    status = `Added "${m.parsed.title}" to ${fmtDate(m.parsed.date)}.`;
    await Promise.all([loadToday(), loadCal(), loadSteps()]);
  } catch (e) { status = e.message; }
  draw();
}

function card(m) {
  const c = m.parsed, done = !!m.task_id, i = m.id;
  const field = (label, node) => el("div", { class: "fld" }, el("label", { for: node.id }, label), node);
  const when = done ? `${fmtDate(c.date)}${c.time ? " " + c.time : ""}` : null;
  return el("div", { class: "qa-card" },
    el("div", { class: "meta" }, el("span", { class: "badge" }, c.type.toUpperCase()),
      done ? el("span", {}, when) : null, done && c.step ? el("span", {}, c.step) : null, c.week ? el("span", {}, "week of") : null),
    done ? el("div", { class: "ttl" }, c.title) : el("div", { class: "qa-edit" },
      field("Title", el("input", { id: `qt-${i}`, type: "text", value: c.title, maxlength: 200, oninput: (e) => { c.title = e.target.value; } })),
      field("Step (tag)", stepInput({ id: `qs-${i}`, placeholder: "Optional" }, c.step, (v) => { c.step = v; })),
      el("div", { class: "fld" }, el("label", { for: `qd-${i}` }, "Date"),
        dateField({ id: `qd-${i}`, label: "date", value: c.date, onchange: (v) => { c.date = v; } })),
      field("Time", el("input", { id: `qh-${i}`, type: "time", value: c.time || "", onchange: (e) => { c.time = e.target.value || null; } })),
      field("Type", el("select", { id: `qy-${i}`, onchange: (e) => { c.type = e.target.value; } },
        ["task", "meeting"].map((v) => el("option", { value: v, selected: v === c.type }, v))))),
    c.note && !done ? el("div", { class: "qa-note" }, c.note) : null,
    el("div", { class: "set-actions" },
      el("button", { type: "button", class: "set-btn primary", disabled: done, onclick: () => add(m) }, done ? "Added ✓" : "Add to plan"),
      done ? null : el("button", { type: "button", class: "set-btn", "aria-label": `Discard: ${c.title}`, onclick: () => discard(m) }, "Discard")));
}

function draw(scroll) {
  const input = pane.querySelector("#qa-input");
  const keep = input ? input.value : "";
  const had = input && document.activeElement === input;
  const logEl = el("div", { class: "qa-log", role: "log", "aria-label": "Quick add chat", tabindex: "0" },
    !log.length && loaded ? el("p", { class: "empty" }, "Type a task. Try: call the bank at 4pm tomorrow.") : null,
    log.map((m) => el("div", { class: "qa-pair" }, el("div", { class: "qa-user" }, m.text), card(m))));
  const form = el("form", { class: "qa-form", onsubmit: (e) => { e.preventDefault(); send(e.target.querySelector("input")); } },
    el("label", { for: "qa-input" }, "Quick add"),
    el("input", { id: "qa-input", type: "text", maxlength: 300, autocomplete: "off", value: keep, placeholder: "Dentist on 14 Nov at 10:30am" }),
    el("button", { type: "submit", class: "set-btn primary", disabled: busy }, "Add ↵"));
  const pending = log.filter((m) => !m.task_id).length;
  pane.replaceChildren(
    el("div", { class: "qa-head" }, el("h2", {}, "03 Quick add"),
      pending > 1 ? el("button", { type: "button", class: "set-btn", onclick: clearPending }, `Clear ${pending}`) : null),
    logEl, form, el("p", { role: "status", class: "plan-status" }, status));
  if (scroll) logEl.scrollTop = logEl.scrollHeight;
  if (had) pane.querySelector("#qa-input").focus();
}

export function quickPane() {
  if (!started) {
    started = true; onFormatChange(() => draw()); draw(); load();
    addEventListener("hashchange", () => { if (/^#\/?new$/.test(location.hash)) { status = ""; load(); } });   // drop added cards on return
  }
  return pane;
}
