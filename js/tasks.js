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

// ── Status metadata ───────────────────────────────────────────────────────────
const STATUS_META = {
  suggested:    { label: "Suggested",    bg: "bg-blue-100",   text: "text-blue-700",   icon: "💡" },
  planned:      { label: "Planned",      bg: "bg-purple-100", text: "text-purple-700", icon: "📅" },
  due:          { label: "Due",          bg: "bg-amber-100",  text: "text-amber-700",  icon: "⏰" },
  completed:    { label: "Completed",    bg: "bg-green-100",  text: "text-green-700",  icon: "✅" },
  skipped:      { label: "Skipped",      bg: "bg-gray-100",   text: "text-gray-500",   icon: "⏭️" },
  cancelled:    { label: "Cancelled",    bg: "bg-red-100",    text: "text-red-500",    icon: "❌" },
  "needs-review": { label: "Needs Review", bg: "bg-orange-100", text: "text-orange-700", icon: "⚠️" },
};

// Valid next-status transitions a farmer can trigger
const ALLOWED_TRANSITIONS = {
  suggested:    ["planned", "skipped"],
  planned:      ["completed", "skipped", "cancelled"],
  due:          ["completed", "skipped", "cancelled"],
  "needs-review": ["planned", "cancelled"],
  completed:    [],
  skipped:      [],
  cancelled:    [],
};

// ── State ─────────────────────────────────────────────────────────────────────
let _tasks = [];
let _todayTasks = [];

// ── DOM refs ──────────────────────────────────────────────────────────────────
const todaySection    = document.getElementById("today-tasks-section");
const todayList       = document.getElementById("today-task-list");
const todayEmpty      = document.getElementById("today-empty");
const todayLoading    = document.getElementById("today-loading");

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

// ── Utilities ─────────────────────────────────────────────────────────────────
function setHidden(el, hidden) {
  if (el) el.classList.toggle("hidden", hidden);
}

function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatDate(isoStr) {
  if (!isoStr) return "—";
  const d = new Date(isoStr);
  return `${String(d.getDate()).padStart(2,"0")}/${String(d.getMonth()+1).padStart(2,"0")}/${d.getFullYear()}`;
}

// ── Status badge HTML ─────────────────────────────────────────────────────────
function statusBadge(status) {
  const m = STATUS_META[status] || { label: status, bg: "bg-gray-100", text: "text-gray-600", icon: "•" };
  return `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${m.bg} ${m.text}">
    ${m.icon} ${escapeHtml(m.label)}
  </span>`;
}

// ── Status update dropdown HTML ───────────────────────────────────────────────
function transitionButtons(task) {
  const transitions = ALLOWED_TRANSITIONS[task.status] || [];
  if (transitions.length === 0) return "";
  return `
    <div class="flex flex-wrap gap-1.5 mt-2">
      ${transitions.map(s => {
        const m = STATUS_META[s] || { label: s };
        return `<button
          class="task-status-btn text-xs font-semibold px-2.5 py-1 rounded-lg border border-gray-300 hover:bg-gray-100 transition"
          data-task-id="${task.id}"
          data-new-status="${s}">
          Mark ${escapeHtml(m.label)}
        </button>`;
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

  return `
    <div class="bg-white border border-gray-200 rounded-xl p-4 shadow-sm ${borderClass}" data-task-id="${task.id}">
      <div class="flex items-start justify-between gap-3">
        <div class="flex-1 min-w-0">
          <div class="flex flex-wrap items-center gap-2 mb-1">
            ${statusBadge(task.status)}
            ${isHighRisk ? '<span class="text-xs font-semibold bg-red-100 text-red-700 px-2 py-0.5 rounded-full">⚠️ HIGH RISK — review required</span>' : ""}
          </div>
          <p class="font-semibold text-emerald-900 text-sm mt-1">${escapeHtml(task.title)}</p>
          ${task.description ? `<p class="text-xs text-gray-500 mt-0.5 leading-relaxed">${escapeHtml(task.description)}</p>` : ""}
          <div class="flex flex-wrap gap-x-4 gap-y-0.5 mt-2 text-xs text-gray-400">
            ${task.due_date ? `<span>📅 Due: ${formatDate(task.due_date)}</span>` : ""}
            ${task.plot_name ? `<span>🌿 ${escapeHtml(task.plot_name)}</span>` : ""}
            ${task.source ? `<span>📋 ${escapeHtml(task.source)}</span>` : ""}
          </div>
        </div>
      </div>
      ${transitionButtons(task)}
    </div>
  `;
}

// ── Render task lists ─────────────────────────────────────────────────────────
function renderTodayTasks() {
  setHidden(todayLoading, true);
  if (!_todayTasks || _todayTasks.length === 0) {
    setHidden(todayEmpty, false);
    todayList.innerHTML = "";
    return;
  }
  setHidden(todayEmpty, true);
  todayList.innerHTML = _todayTasks.map(taskCardHtml).join("");
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
  bindStatusButtons(allList);
}

// ── Bind status update buttons ────────────────────────────────────────────────
function bindStatusButtons(container) {
  container.querySelectorAll(".task-status-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const taskId   = btn.getAttribute("data-task-id");
      const newStatus = btn.getAttribute("data-new-status");
      await updateTaskStatus(taskId, newStatus);
    });
  });
}

// ── Update task status ────────────────────────────────────────────────────────
async function updateTaskStatus(taskId, newStatus) {
  try {
    const res = await apiFetch(`/api/farmers/me/tasks/${taskId}/status`, {
      method: "PUT",
      body: JSON.stringify({ status: newStatus }),
    });
    if (!res.ok) {
      showError("Failed to update task status.");
      return;
    }
    // Reload both lists to reflect the change
    await Promise.all([loadTodayTasks(), loadAllTasks()]);
  } catch {
    showError("Could not update task. Please try again.");
  }
}

// ── Load today's tasks ────────────────────────────────────────────────────────
async function loadTodayTasks() {
  setHidden(todayLoading, false);
  try {
    const res = await apiFetch("/api/farmers/me/tasks/today");
    if (!res.ok) {
      setHidden(todayLoading, true);
      return;
    }
    _todayTasks = await res.json();
    renderTodayTasks();
  } catch {
    setHidden(todayLoading, true);
    // Today section is non-critical; silently skip if offline
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
      showError("Failed to load tasks.");
      setHidden(allLoading, true);
      return;
    }
    _tasks = await res.json();
    renderAllTasks(_tasks);
  } catch {
    showError("Could not connect to server.");
    setHidden(allLoading, true);
  }
}

// ── Create task ───────────────────────────────────────────────────────────────
async function handleSaveTask(e) {
  e.preventDefault();
  taskFormError.classList.add("hidden");
  taskFormBtn.disabled = true;
  taskFormBtn.textContent = "Saving…";

  const body = {
    title:       document.getElementById("task-title").value.trim(),
    due_date:    document.getElementById("task-due-date").value || null,
    description: document.getElementById("task-description").value.trim() || null,
    priority:    document.getElementById("task-priority").value || null,
    status:      "planned",
    source:      "manual",
  };

  if (!body.title) {
    taskFormError.textContent = "Task title is required.";
    taskFormError.classList.remove("hidden");
    taskFormBtn.disabled = false;
    taskFormBtn.textContent = "Save Task";
    return;
  }

  try {
    const res = await apiFetch("/api/farmers/me/tasks", {
      method: "POST",
      body: JSON.stringify(body),
    });

    if (res.status === 422) {
      const data = await res.json();
      const detail = data.detail;
      taskFormError.textContent = typeof detail === "string"
        ? detail : Array.isArray(detail)
        ? detail.map(d => d.msg).join(". ")
        : "Validation error. Check the form.";
      taskFormError.classList.remove("hidden");
      return;
    }
    if (!res.ok) {
      taskFormError.textContent = "Failed to save task. Please try again.";
      taskFormError.classList.remove("hidden");
      return;
    }

    taskForm.reset();
    taskFormWrap.classList.add("hidden");
    await Promise.all([loadTodayTasks(), loadAllTasks()]);
  } catch {
    taskFormError.textContent = "Network error. Please try again.";
    taskFormError.classList.remove("hidden");
  } finally {
    taskFormBtn.disabled = false;
    taskFormBtn.textContent = "Save Task";
  }
}

// ── Initialise ────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  await routeGuard("tasks");

  document.getElementById("btn-signout")?.addEventListener("click", signOut);

  // Task form
  taskFormToggle?.addEventListener("click", () => {
    taskFormWrap.classList.toggle("hidden");
    taskFormError.classList.add("hidden");
    taskForm.reset();
  });
  taskFormCancel?.addEventListener("click", () => taskFormWrap.classList.add("hidden"));
  taskForm?.addEventListener("submit", handleSaveTask);

  // Filter
  filterStatus?.addEventListener("change", loadAllTasks);

  await Promise.all([loadTodayTasks(), loadAllTasks()]);
});
