/**
 * tasks.js — Task list with status badges, due-date display, and status updates.
 *
 * Handles:
 *  - GET /api/farmers/me/tasks/today  → "Today's Tasks" section
 *  - GET /api/farmers/me/tasks        → full task list with filters
 *  - POST /api/farmers/me/tasks       → create a new task
 *  - PUT /api/farmers/me/tasks/{id}/status → update task status
 *
 * Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
 */

import { routeGuard, signOut } from "./auth.js";
import { apiFetch, showError } from "./api.js";
import {
  applyI18n, errorMessage, escapeHtml, getLang, initPage, renderLoadError, setBusy, t,
} from "./dom.js";
import { translateApiText } from "./api-text.js";
import { formatDate, formatNumber } from "./translator.js";
import { icon } from "./icons.js";
import { renderTaskRing } from "./task-ring.js";

// ── Status metadata ───────────────────────────────────────────────────────────
const STATUS_META = {
  suggested:      { key: "tasks.status.suggested",   bg: "bg-blue-100",   text: "text-blue-800",   icon: "💡" },
  planned:        { key: "tasks.status.planned",     bg: "bg-purple-100", text: "text-purple-800", icon: "📅" },
  due:            { key: "tasks.status.due",         bg: "bg-amber-100",  text: "text-amber-800",  icon: "⏰" },
  completed:      { key: "tasks.status.completed",   bg: "bg-green-100",  text: "text-green-800",  icon: "✅" },
  skipped:        { key: "tasks.status.skipped",     bg: "bg-gray-100",   text: "text-gray-700",   icon: "⏭️" },
  cancelled:      { key: "tasks.status.cancelled",   bg: "bg-red-100",    text: "text-red-800",    icon: "❌" },
  "needs-review": { key: "tasks.status.needsReview", bg: "bg-orange-100", text: "text-orange-800", icon: "⚠️" },
};

// Valid next-status transitions a farmer can trigger
const ALLOWED_TRANSITIONS = {
  suggested:      ["planned", "skipped"],
  planned:        ["completed", "skipped", "cancelled"],
  due:            ["completed", "skipped", "cancelled"],
  "needs-review": ["planned", "cancelled"],
  completed:      [],
  skipped:        [],
  cancelled:      [],
};

// ── State ─────────────────────────────────────────────────────────────────────
let _tasks = [];
let _todayTasks = [];

// ── DOM refs ──────────────────────────────────────────────────────────────────
const todayList       = document.getElementById("today-task-list");
const todayEmpty      = document.getElementById("today-empty");
const todayLoading    = document.getElementById("today-loading");
const headlineToday   = document.getElementById("headline-today");

const allLoading      = document.getElementById("all-tasks-loading");
const allList         = document.getElementById("all-task-list");
const allEmpty        = document.getElementById("all-tasks-empty");

const taskFormWrap    = document.getElementById("task-form-wrap");
const taskFormToggle  = document.getElementById("btn-show-task-form");
const taskFormCancel  = document.getElementById("btn-cancel-task-form");
const taskForm        = document.getElementById("task-form");
const taskFormError   = document.getElementById("task-form-error");
const taskFormBtn     = document.getElementById("btn-save-task");

const filterStatus    = document.getElementById("filter-status");
const taskRingEl      = document.getElementById("task-ring");

// ── Utilities ─────────────────────────────────────────────────────────────────
function setHidden(el, hidden) {
  if (el) el.classList.toggle("hidden", hidden);
}

function showFormError(message) {
  taskFormError.textContent = message;
  taskFormError.classList.remove("hidden");
}

// ── Status badge HTML ─────────────────────────────────────────────────────────
function statusBadge(status) {
  const m = STATUS_META[status];
  const label = m ? t(m.key) : status;
  const cls = m ? `${m.bg} ${m.text}` : "bg-gray-100 text-gray-700";
  return `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-sm font-semibold ${cls}">
    ${m ? m.icon : "•"} ${escapeHtml(label)}
  </span>`;
}

// ── Status update buttons HTML ────────────────────────────────────────────────
function transitionButtons(task) {
  const transitions = ALLOWED_TRANSITIONS[task.status] || [];
  if (transitions.length === 0) return "";
  return `
    <div class="flex flex-wrap gap-2 mt-3">
      ${transitions.map((s) => {
        const m = STATUS_META[s];
        return `<button type="button"
          class="task-status-btn text-sm font-semibold px-3 py-1.5 rounded-lg border border-gray-400 text-gray-800 hover:bg-gray-100 transition"
          data-task-id="${escapeHtml(task.id)}"
          data-new-status="${escapeHtml(s)}">${escapeHtml(t("tasks.markAs", { status: m ? t(m.key) : s }))}</button>`;
      }).join("")}
    </div>
  `;
}

// ── Render a single task card ─────────────────────────────────────────────────
function taskCardHtml(task) {
  const isHighRisk = task.risk_level === "HIGH";
  const borderClass = task.status === "due" ? "border-l-4 border-l-amber-400"
    : task.status === "needs-review" ? "border-l-4 border-l-orange-400"
    : task.status === "completed" ? "border-l-4 border-l-green-400"
    : "border-l-4 border-l-gray-200";
  const source = task.source === "ai" ? t("tasks.source.ai") : task.source === "manual" ? t("tasks.source.manual") : task.source;

  return `
    <div class="bg-white border border-gray-200 rounded-xl p-4 shadow-sm ${borderClass}" data-task-id="${escapeHtml(task.id)}">
      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-2 mb-1">
          ${statusBadge(task.status)}
          ${isHighRisk ? `<span class="text-sm font-semibold bg-red-100 text-red-800 px-2 py-0.5 rounded-full">⚠️ ${escapeHtml(t("tasks.highRisk.badge"))}</span>` : ""}
        </div>
        <p class="font-semibold text-emerald-900 text-base mt-1 break-words">${escapeHtml(translateApiText(task.title, getLang()))}</p>
        ${task.description ? `<p class="text-sm text-gray-600 mt-0.5 leading-relaxed break-words">${escapeHtml(translateApiText(task.description, getLang()))}</p>` : ""}
        <div class="flex flex-wrap gap-x-4 gap-y-0.5 mt-2 text-sm text-gray-600">
          ${task.due_date ? `<span>📅 ${escapeHtml(t("tasks.due"))}: ${escapeHtml(formatDate(task.due_date))}</span>` : ""}
          ${task.plot_name ? `<span>🌿 ${escapeHtml(task.plot_name)}</span>` : ""}
          ${source ? `<span>📋 ${escapeHtml(source)}</span>` : ""}
        </div>
      </div>
      ${transitionButtons(task)}
    </div>
  `;
}

// ── Render task lists ─────────────────────────────────────────────────────────
function renderHeadline() {
  if (headlineToday) headlineToday.textContent = formatNumber(_todayTasks.length);
}

function renderTodayTasks() {
  setHidden(todayLoading, true);
  renderHeadline();
  if (!_todayTasks || _todayTasks.length === 0) {
    setHidden(todayEmpty, false);
    todayList.innerHTML = "";
    return;
  }
  setHidden(todayEmpty, true);
  todayList.innerHTML = _todayTasks.map(taskCardHtml).join("");
  applyI18n(todayList);
  bindStatusButtons(todayList);
}

function renderAllTasks(tasks) {
  setHidden(allLoading, true);
  if (!tasks || tasks.length === 0) {
    setHidden(allEmpty, false);
    allList.innerHTML = "";
    return;
  }
  setHidden(allEmpty, true);
  allList.innerHTML = tasks.map(taskCardHtml).join("");
  applyI18n(allList);
  bindStatusButtons(allList);
}

// ── Bind status update buttons ────────────────────────────────────────────────
function bindStatusButtons(container) {
  container.querySelectorAll(".task-status-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      const ok = await updateTaskStatus(btn.getAttribute("data-task-id"), btn.getAttribute("data-new-status"));
      if (!ok) btn.disabled = false;
    });
  });
}

// ── Gentle celebration: a small check and "Well done". No streaks, no guilt text. ─
// The check animation is switched off in css/style.src.css under prefers-reduced-motion.
function celebrate() {
  document.querySelector(".sf-toast[data-celebrate]")?.remove();
  const toast = document.createElement("div");
  toast.className = "sf-toast";
  toast.setAttribute("role", "status");
  toast.setAttribute("data-celebrate", "1");
  toast.innerHTML = `<span class="sf-celebrate" aria-hidden="true">${icon("check")}</span>${escapeHtml(t("tasks.celebrate"))}`;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

// ── Update task status ────────────────────────────────────────────────────────
async function updateTaskStatus(taskId, newStatus) {
  try {
    const res = await apiFetch(`/api/farmers/me/tasks/${encodeURIComponent(taskId)}/status`, {
      method: "PUT",
      body: JSON.stringify({ status: newStatus }),
    });
    if (!res.ok) {
      showError(await errorMessage(res));
      return false;
    }
    if (newStatus === "completed") celebrate();
    await Promise.all([loadTodayTasks(), loadAllTasks()]);
    return true;
  } catch {
    showError(t("common.error.network"));
    return false;
  }
}

// ── Load today's tasks ────────────────────────────────────────────────────────
async function loadTodayTasks() {
  setHidden(todayLoading, false);
  setHidden(todayEmpty, true);
  try {
    const res = await apiFetch("/api/farmers/me/tasks/today");
    if (!res.ok) {
      setHidden(todayLoading, true);
      renderLoadError(todayList, loadTodayTasks);
      return;
    }
    _todayTasks = await res.json();
    renderTodayTasks();
  } catch {
    setHidden(todayLoading, true);
    renderLoadError(todayList, loadTodayTasks, "common.error.network");
  }
}

// ── Load all tasks ────────────────────────────────────────────────────────────
async function loadAllTasks() {
  setHidden(allLoading, false);
  setHidden(allEmpty, true);
  allList.innerHTML = "";

  const statusVal = filterStatus?.value || "";
  const params = statusVal ? `?status=${encodeURIComponent(statusVal)}` : "";

  try {
    const res = await apiFetch(`/api/farmers/me/tasks${params}`);
    if (!res.ok) {
      setHidden(allLoading, true);
      renderLoadError(allList, loadAllTasks);
      return;
    }
    _tasks = await res.json();
    renderAllTasks(_tasks);
    // The ring counts the full list, so it only updates when no status filter is applied.
    if (!statusVal) renderTaskRing(taskRingEl, _tasks);
  } catch {
    setHidden(allLoading, true);
    renderLoadError(allList, loadAllTasks, "common.error.network");
  }
}

// ── Create task ───────────────────────────────────────────────────────────────
async function handleSaveTask(e) {
  e.preventDefault();
  taskFormError.classList.add("hidden");

  const body = {
    title:       document.getElementById("task-title").value.trim(),
    due_date:    document.getElementById("task-due-date").value || null,
    description: document.getElementById("task-description").value.trim() || null,
    priority:    document.getElementById("task-priority").value || null,
    status:      "planned",
    source:      "manual",
  };

  if (!body.title) {
    showFormError(t("tasks.error.titleRequired"));
    return;
  }

  setBusy(taskFormBtn, true);
  try {
    const res = await apiFetch("/api/farmers/me/tasks", { method: "POST", body: JSON.stringify(body) });
    if (!res.ok) {
      showFormError(await errorMessage(res));
      return;
    }
    taskForm.reset();
    taskFormWrap.classList.add("hidden");
    await Promise.all([loadTodayTasks(), loadAllTasks()]);
  } catch {
    showFormError(t("common.error.network"));
  } finally {
    setBusy(taskFormBtn, false);
  }
}

// ── Initialise ────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  initPage();
  await routeGuard("tasks");

  document.getElementById("btn-signout")?.addEventListener("click", signOut);

  taskFormToggle?.addEventListener("click", () => {
    taskFormWrap.classList.toggle("hidden");
    taskFormError.classList.add("hidden");
  });
  taskFormCancel?.addEventListener("click", () => taskFormWrap.classList.add("hidden"));
  taskForm?.addEventListener("submit", handleSaveTask);

  filterStatus?.addEventListener("change", loadAllTasks);

  await Promise.all([loadTodayTasks(), loadAllTasks()]);
});
