import { el, swap } from "./dom.js";

const host = () => document.querySelector(".about-host");
const LINKS = { website: (v) => v, github: (v) => v, email: (v) => "mailto:" + v };
const DEV_LABELS = [["name", "Name"], ["brand", "Brand"], ["website", "Website"], ["github", "GitHub"], ["email", "Email"], ["license_note", "License"], ["bug_report", "Bug reports"]];

const fmt = (v) => Array.isArray(v) ? (v.length ? v.join(", ") : "none") : String(v ?? "unknown");
const pair = (label, value) => [el("dt", {}, label), el("dd", {}, value)];

// navigator.clipboard needs a secure context; plain-http LAN access falls back to execCommand.
async function copyText(text) {
  try { await navigator.clipboard.writeText(text); return true; } catch (e) {}
  const ta = el("textarea", { class: "about-copy-buf", readonly: true, "aria-hidden": "true" });
  ta.value = text;
  document.body.append(ta);
  ta.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch (e) {}
  ta.remove();
  return ok;
}

function render(d) {
  const i = d.info, dev = d.developer;
  const status = el("p", { class: "status", role: "status" });
  const copy = async () => {
    status.textContent = (await copyText(d.text)) ? "Debug info copied." : "Copy failed: select the text below and copy it.";
  };
  const devRows = DEV_LABELS.filter(([k]) => dev[k]).flatMap(([k, label]) =>
    pair(label, LINKS[k] ? el("a", { href: LINKS[k](dev[k]), rel: "noopener" }, dev[k]) : dev[k]));
  swap(host(), el("div", { class: "about" },
    el("div", { class: "about-app" },
      el("p", { class: "about-name" }, i.app_name),
      el("p", { class: "about-ver" }, "v" + i.app_version + " · build " + i.build_commit + " · " + i.build_date)),
    el("section", { class: "about-sec", "aria-labelledby": "about-dev" },
      el("h2", { id: "about-dev" }, "Developer"), el("dl", { class: "about-dl" }, devRows)),
    el("section", { class: "about-sec", "aria-labelledby": "about-debug" },
      el("h2", { id: "about-debug" }, "Debug info"),
      el("dl", { class: "about-dl" }, d.fields.flatMap((f) => pair(f.label, fmt(i[f.key])))),
      el("div", { class: "set-actions" }, el("button", { type: "button", class: "set-btn primary", onclick: copy }, "Copy debug info")),
      status,
      el("details", { class: "about-raw" }, el("summary", {}, "Show copied text"), el("pre", {}, d.text)))));
}

export async function initAbout() {
  try {
    const r = await fetch("/api/about");
    if (!r.ok) throw new Error();
    render(await r.json());
  } catch (e) { host().replaceChildren(el("p", { class: "empty" }, "Could not load About.")); }
}
