import { el, swap } from "./dom.js";
import { setDateFormat } from "./datefmt.js";
import { loadToday, loadCal } from "./store.js";

const host = () => document.querySelector(".settings-host");
let data = null;
let chain = [];

async function api(path, opts) {
  const r = await fetch(path, opts);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || "Request failed");
  return j;
}

function field(id, label, input, hint) {
  return el("div", { class: "fld" }, el("label", { for: id }, label), input, hint ? el("span", { class: "hint" }, hint) : null);
}
const num = (id, v, step, min, max) => el("input", { id, type: "number", step, min, max, value: v });

function chainList(status, available) {
  const ul = el("ul", { class: "chain", "aria-label": "Generate chain order" });
  const move = (i, d) => { const j = i + d; if (j < 0 || j >= chain.length) return; [chain[i], chain[j]] = [chain[j], chain[i]]; render(`Moved ${chain[j]}.`); };
  chain.forEach((p, i) => ul.append(el("li", {},
    el("span", { class: "cname" }, `${i + 1}. ${p}`),
    el("button", { type: "button", "aria-label": `Move ${p} up`, onclick: () => move(i, -1) }, "↑"),
    el("button", { type: "button", "aria-label": `Move ${p} down`, onclick: () => move(i, 1) }, "↓"),
    el("button", { type: "button", "aria-label": `Remove ${p}`, onclick: () => { chain.splice(i, 1); render(`Removed ${p}.`); } }, "Remove"),
    el("button", { type: "button", onclick: () => testProvider(p, status) }, "Test"))));
  const rest = data.providers.filter((p) => !chain.includes(p));
  const add = el("div", { class: "set-actions" }, rest.map((p) => el("button", { type: "button", class: "set-btn", onclick: () => { chain.push(p); render(`Added ${p}.`); } }, "Add " + p)));
  return el("div", {}, ul, chain.length ? null : el("p", { class: "empty" }, "Empty: no LLM is used."), add);
}

async function testProvider(name, status) {
  status.textContent = `Testing ${name}…`;
  try {
    const r = await api("/api/ai/test", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ provider: name }) });
    status.textContent = r.ok ? `${name} works (${r.ms} ms${r.model ? ", " + r.model : ""}).` : `${name} failed: ${r.error || "no answer"}.`;
  } catch (e) { status.textContent = `${name} failed: ${e.message}.`; }
}

const sample = (f) => f === "yyyy-mm-dd" ? "2026-10-17" : f === "mm/dd/yyyy" ? "10/17/2026" : "17/10/2026";

function render(msg = "") {
  const a = data.ai, t = a.thresholds, s = data.server;
  const status = el("p", { class: "status", role: "status" }, msg);
  const mode = el("select", { id: "s-mode" }, data.modes.map((m) => el("option", { value: m, selected: m === a.mode }, m)));
  const form = el("form", { class: "set-form", onsubmit: save },
    el("fieldset", {}, el("legend", {}, "AI"),
      field("s-mode", "Mode", mode, "jev: Jev decides. llm: LLM chain extracts everything. off: code only, every line is a draft."),
      field("s-model", "Jev model", el("input", { id: "s-model", type: "text", value: a.jev_model }), "Pin a version such as jev-1.13.0 once thresholds are tuned."),
      el("div", { class: "fld" }, el("label", {}, el("input", { id: "s-prose", type: "checkbox", checked: a.rewrite_prose }), " Send loose prose to the generate chain")),
      field("s-timeout", "Timeout (seconds)", num("s-timeout", a.timeout_s, 1, 5, 300))),
    el("fieldset", {}, el("legend", {}, "Display"),
      field("s-datefmt", "Date format", el("select", { id: "s-datefmt" },
        data.date_formats.map((f) => el("option", { value: f, selected: f === data.ui.date_format }, f))),
        "Used everywhere dates are shown or typed. Example: 17 Oct 2026 → " + sample(data.ui.date_format) + ".")),
    el("fieldset", {}, el("legend", {}, "Generate chain"), el("p", { class: "hint" }, "Tried top to bottom."), chainList(status)),
    el("fieldset", {}, el("legend", {}, "Thresholds"),
      field("s-accept", "Task accept (noul at or above)", num("s-accept", t.task_accept, 0.05, 0, 1)),
      field("s-review", "Task review (flagged between review and accept)", num("s-review", t.task_review, 0.05, 0, 1)),
      field("s-conf", "Confidence review (choice below this is flagged)", num("s-conf", t.confidence_review, 0.05, 0, 1))),
    el("div", { class: "set-actions" },
      el("button", { type: "submit", class: "set-btn primary" }, "Save settings"),
      el("button", { type: "button", class: "set-btn", onclick: () => testProvider("jev", status) }, "Test Jev")),
    status,
    el("fieldset", {}, el("legend", {}, "Backup"),
      el("p", { class: "hint" }, "Export downloads all tasks as JSON. Import only adds tasks that are missing; nothing is changed or deleted."),
      el("div", { class: "set-actions" },
        el("a", { class: "set-btn", href: "/api/export", download: "" }, "Export backup")),
      field("s-import", "Import backup (.json)", el("input", { id: "s-import", type: "file", accept: ".json,application/json", onchange: importFile })),
      el("p", { class: "status", role: "status", id: "s-import-status" })),
    el("fieldset", {}, el("legend", {}, "Server (read-only)"),
      el("p", { class: "ro" }, `Host ${s.host} · Port ${s.port} · Threads ${s.threads}`),
      el("p", { class: "hint" }, s.note + " API keys live in .env and are never shown here.")));
  swap(host(), form);
}

async function importFile(ev) {
  const out = document.getElementById("s-import-status");
  const f = ev.target.files[0];
  if (!f) return;
  try {
    const body = JSON.parse(await f.text());
    const j = await api("/api/import", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    out.textContent = `Imported ${j.added} tasks, skipped ${j.skipped} already there.`;
    await Promise.all([loadToday(), loadCal()]);
  } catch (e) { out.textContent = "Not imported: " + (e instanceof SyntaxError ? "that file is not JSON" : e.message); }
  ev.target.value = "";
}

async function save(ev) {
  ev.preventDefault();
  const v = (id) => document.getElementById(id);
  const body = { ai: {
    mode: v("s-mode").value, jev_model: v("s-model").value, rewrite_prose: v("s-prose").checked,
    timeout_s: parseInt(v("s-timeout").value, 10), generate_chain: chain,
    thresholds: { task_accept: parseFloat(v("s-accept").value), task_review: parseFloat(v("s-review").value), confidence_review: parseFloat(v("s-conf").value) },
  }, ui: { date_format: v("s-datefmt").value } };
  try {
    data = await api("/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    chain = [...data.ai.generate_chain];
    setDateFormat(data.ui.date_format);
    render("Settings saved.");
  } catch (e) { document.querySelector(".settings-host .status").textContent = "Not saved: " + e.message; }
}

export async function initSettings() {
  try {
    data = await api("/api/settings");
    chain = [...data.ai.generate_chain];
    render();
  } catch (e) { host().replaceChildren(el("p", { class: "empty" }, "Could not load settings.")); }
}
