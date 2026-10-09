import { el } from "./dom.js";

// One shared <datalist id="step-list"> with steps already in use, for step inputs to suggest from.
const list = el("datalist", { id: "step-list" });

export async function loadSteps() {
  if (!list.isConnected) document.body.append(list);
  try {
    const r = await fetch("/api/steps");
    if (r.ok) list.replaceChildren(...(await r.json()).map((s) => el("option", { value: s })));
  } catch (e) { /* suggestions are optional */ }
}

export function stepInput(attrs, value, onchange) {
  return el("input", { type: "text", list: "step-list", maxlength: 30, autocomplete: "off", value: value || "",
    ...attrs, onchange: (e) => onchange(e.target.value.trim()) });
}
