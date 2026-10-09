import { el, swap } from "./dom.js";
import { fmtStamp } from "./dates.js";
import { state, subscribe, openToday, toggleDone, loadToday } from "./store.js";
import { editButton, editForm, isEditing, onEditChange } from "./editor.js";

// prefix keeps Edit button ids unique per page ("t" Today, "c" Calendar day view).
export function taskRow(t, i, prefix = "t") {
  const idx = el("span", { class: "idx" }, String(i + 1).padStart(2, "0"));
  if (isEditing(t)) return el("li", { class: "row editing" }, idx, el("div", { class: "body" }, editForm(t)));
  const meta = el("div", { class: "meta" },
    el("span", { class: "badge p-" + t.priority.toLowerCase() }, t.priority),
    t.step ? el("span", {}, t.step) : null,
    el("span", {}, "Created " + fmtStamp(t.created_at)),
    t.closed ? el("span", {}, "Closed " + fmtStamp(t.closed_at)) : el("span", { class: "tag-open" }, "Open"));
  const btn = el("button", { type: "button", class: "done-btn", "aria-pressed": String(t.closed),
    onclick: () => toggleDone(t) }, t.closed ? "Done ✓" : "Mark done");
  return el("li", { class: "row" + (t.closed ? " is-done" : "") }, idx,
    el("div", { class: "body" }, el("div", { class: "ttl" }, t.title), meta),
    el("div", { class: "row-act" }, editButton(t, prefix), btn));
}

export function renderToday() {
  const page = document.getElementById("page-today");
  const n = openToday();
  document.getElementById("h-today").textContent = `Today (${n} open)`;
  document.getElementById("nav-today").textContent = `${n} open`;
  swap(page.querySelector(".list-host"),
    state.error ? el("div", { class: "empty", role: "alert" }, state.error + " ", el("button", { type: "button", class: "set-btn", onclick: loadToday }, "Try again"))
    : !state.loaded ? el("p", { class: "empty" }, "Loading…")
    : state.today.length ? el("ol", { class: "rows" }, state.today.map((t, i) => taskRow(t, i, "t")))
    : el("p", { class: "empty" }, "Nothing planned for today."));
}
subscribe(renderToday);
onEditChange(renderToday);
