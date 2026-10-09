import { todayIso } from "./dates.js";

const subs = new Set();
export const state = { today: [], cal: [], calRange: null, error: "", loaded: false };
export const subscribe = (fn) => { subs.add(fn); };
const emit = () => subs.forEach((fn) => fn());

async function getTasks(from, to) {
  const r = await fetch(`/api/tasks?from=${from}&to=${to}`);
  if (!r.ok) throw new Error("Could not load tasks");
  return r.json();
}
const PR = { High: 0, Medium: 1, Low: 2 };
export function sortToday(list) {
  return [...list].sort((a, b) => (a.closed - b.closed) || (PR[a.priority] - PR[b.priority]) || (a.sort_order - b.sort_order) || (a.id - b.id));
}
export async function loadToday() {
  const t = todayIso();
  try { state.today = sortToday(await getTasks(t, t)); state.error = ""; }
  catch (e) { state.error = e.message; }
  state.loaded = true;
  emit();
}
export async function loadCal(range) {
  if (range) state.calRange = range;
  if (!state.calRange) return;
  try { state.cal = await getTasks(...state.calRange); state.error = ""; }
  catch (e) { state.error = e.message; }
  emit();
}
export async function toggleDone(task) {
  const r = await fetch(`/api/tasks/${task.id}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ closed: !task.closed }),
  });
  if (!r.ok) { state.error = "Could not update task"; emit(); return; }
  await Promise.all([loadToday(), loadCal()]);
}
export const openToday = () => state.today.filter((t) => !t.closed).length;

// Edit / delete a saved task, then refresh every view (Dashboard and Done reload on emit).
export async function saveTask(id, fields) {
  const r = await fetch(`/api/tasks/${id}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(fields),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || "Could not save task");
  await Promise.all([loadToday(), loadCal()]);
  return j;
}
export async function deleteTask(id) {
  const r = await fetch(`/api/tasks/${id}`, { method: "DELETE" });
  if (!r.ok && r.status !== 404) throw new Error("Could not delete task");
  await Promise.all([loadToday(), loadCal()]);
}
