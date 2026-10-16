export function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v; else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) n.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat()) if (c != null) n.append(c);
  return n;
}

// Replace a host's children but keep keyboard focus on the same control.
const sig = (n) => (n.id ? "#" + n.id : n.tagName + "|" + (n.getAttribute("aria-label") || n.textContent.trim().slice(0, 40)));

export function swap(host, ...kids) {
  const a = document.activeElement;
  let key = null;
  if (a && a !== document.body && host.contains(a)) {
    const s = sig(a);
    const same = [...host.querySelectorAll(a.id ? "#" + CSS.escape(a.id) : a.tagName)].filter((n) => sig(n) === s);
    key = { s, i: same.indexOf(a), tag: a.tagName, id: a.id };
  }
  host.replaceChildren(...kids);
  if (!key) return;
  const cands = [...host.querySelectorAll(key.id ? "#" + CSS.escape(key.id) : key.tag)].filter((n) => sig(n) === key.s);
  const t = cands[key.i] || cands[0];
  if (t && !t.disabled) t.focus();
}
