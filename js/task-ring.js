/**
 * task-ring.js - task progress helpers shared by tasks.html and plan.html.
 * Counts come only from the farmer's task list returned by the API.
 * Skipped and cancelled tasks are left out of the total, so they never count against the farmer.
 */
import { escapeHtml, t } from "./dom.js";

const CLOSED = new Set(["completed", "skipped", "cancelled"]);
const LEFT_OUT = new Set(["skipped", "cancelled"]);

export function taskProgress(tasks) {
  const counted = (tasks || []).filter((x) => !LEFT_OUT.has(x.status));
  return { done: counted.filter((x) => x.status === "completed").length, total: counted.length };
}

/** Earliest non-completed task by due date (tasks without a date come last). */
export function nextDueTask(tasks) {
  const open = (tasks || []).filter((x) => !CLOSED.has(x.status));
  open.sort((a, b) => {
    if (!a.due_date && !b.due_date) return 0;
    if (!a.due_date) return 1;
    if (!b.due_date) return -1;
    return String(a.due_date).localeCompare(String(b.due_date));
  });
  return open[0] || null;
}

/** Pure SVG ring plus the text "3 of 8 done". Hides the container when there are no tasks. */
export function renderTaskRing(el, tasks) {
  if (!el) return;
  const { done, total } = taskProgress(tasks);
  if (!total) {
    el.classList.add("hidden");
    el.innerHTML = "";
    return;
  }
  const r = 32;
  const circ = 2 * Math.PI * r;
  const text = t("tasks.ring.text", { done, total });
  const label = t("tasks.ring.label");
  el.classList.remove("hidden");
  el.innerHTML =
    `<p class="sf-home__label">${escapeHtml(label)}</p>` +
    `<div class="sf-taskring mt-2" role="img" aria-label="${escapeHtml(`${label}: ${text}`)}">` +
    `<svg viewBox="0 0 80 80" aria-hidden="true">` +
    `<circle class="sf-taskring__bg" cx="40" cy="40" r="${r}"></circle>` +
    `<circle class="sf-taskring__fg" cx="40" cy="40" r="${r}" stroke-dasharray="${((done / total) * circ).toFixed(1)} ${circ.toFixed(1)}"></circle>` +
    `</svg>` +
    `<p class="sf-taskring__text">${escapeHtml(text)}</p>` +
    `</div>`;
}
