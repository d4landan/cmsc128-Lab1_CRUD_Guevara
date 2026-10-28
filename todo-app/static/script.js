const taskList = document.getElementById("taskList");
const taskForm = document.getElementById("taskForm");
const formSubmitBtn = document.getElementById("formSubmitBtn");
const cancelEditBtn = document.getElementById("cancelEditBtn");
const emptyState = document.getElementById("emptyState");
const confirmModal = document.getElementById("confirmModal");
const toast = document.getElementById("toast");
const toastMessage = document.getElementById("toastMessage");
const toastUndoBtn = document.getElementById("toastUndoBtn");
const todayDateEl = document.getElementById("todayDate");

let taskToDelete = null;
let lastDeletedTask = null;
let undoTimer = null;
let toastTimer = null;
let hiddenTaskIds = new Set();
let currentTasks = [];

// Helpers 

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function formatDue(value) {
  const d = new Date(value);
  if (isNaN(d)) return value;
  return "Due " + d.toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit"
  });
}

function showToast(message, { undo = false, danger = false, duration = 3500 } = {}) {
  clearTimeout(toastTimer);
  toastMessage.textContent = message;
  toastUndoBtn.classList.toggle("hidden", !undo);
  toast.classList.toggle("toast-danger", danger);
  toast.classList.remove("hidden");
  if (!undo) {
    toastTimer = setTimeout(() => toast.classList.add("hidden"), duration);
  }
}

function hideToast() {
  clearTimeout(toastTimer);
  toast.classList.add("hidden");
}

if (todayDateEl) {
  todayDateEl.textContent = new Date().toLocaleDateString(undefined, {
    weekday: "long", month: "long", day: "numeric"
  });
}

// Data loading

// task requests goes through here 
async function apiFetch(url, options) {
  const res = await fetch(url, options);
  if (res.status === 401) window.location.href = "/login";
  return res;
}

function buildQuery() {
  const tag = document.getElementById("filterTag").value;
  const priority = document.getElementById("filterPriority").value;
  const sortBy = document.getElementById("sortBy").value;
  const params = new URLSearchParams({ sort_by: sortBy });
  if (tag) params.append("tag", tag);
  if (priority) params.append("priority", priority);
  return params.toString();
}

async function loadTasks() {
  const res = await apiFetch(`/api/tasks?${buildQuery()}`);
  if (!res.ok) return;
  currentTasks = await res.json();
  renderTasks(currentTasks);
}

function renderTasks(tasks) {
  taskList.innerHTML = "";
  const visible = tasks.filter(task => !hiddenTaskIds.has(task.id));

  emptyState.classList.toggle("hidden", visible.length !== 0);

  visible.forEach(task => {
    const li = document.createElement("li");
    li.className = `task-item priority-${(task.priority || "").toLowerCase()} ${task.done ? "done" : ""}`;
    li.dataset.id = task.id;
    li.innerHTML = `
      <button class="check-btn" data-action="toggle" aria-label="${task.done ? "Mark as not done" : "Mark as done"}">${task.done ? "✓" : ""}</button>
      <div class="task-info">
        <p class="task-title">${escapeHtml(task.title)}</p>
        <div class="task-meta">
          <span class="chip chip-due">${escapeHtml(formatDue(task.due_date))}</span>
          <span class="chip chip-tag">${escapeHtml(task.tag)}</span>
        </div>
      </div>
      <span class="priority-label"><span class="priority-dot"></span>${escapeHtml(task.priority)}</span>
      <div class="task-actions">
        <button class="btn-icon" data-action="edit" aria-label="Edit task">Edit</button>
        <button class="btn-icon btn-icon-danger" data-action="delete" aria-label="Delete task">Delete</button>
      </div>
    `;
    taskList.appendChild(li);
  });
}

// Add / edit 

taskForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    title: document.getElementById("title").value,
    due_date: document.getElementById("dueDate").value,
    priority: document.getElementById("priority").value,
    tag: document.getElementById("tag").value
  };

  const isEditing = Boolean(taskForm.dataset.editingId);

  const res = isEditing
    ? await apiFetch(`/api/tasks/${taskForm.dataset.editingId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      })
    : await apiFetch("/api/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

  if (!res.ok) {
    showToast("Couldn't save the task. Please try again.", { danger: true });
    return;
  }
  if (isEditing) exitEditMode();
  showToast(isEditing ? "Task updated" : "Task added");

  taskForm.reset();
  document.getElementById("priority").value = "Med";
  loadTasks();
});

function startEdit(id) {
  const task = currentTasks.find(t => t.id === id);
  if (!task) return;
  document.getElementById("title").value = task.title;
  document.getElementById("dueDate").value = task.due_date;
  document.getElementById("priority").value = task.priority;
  document.getElementById("tag").value = task.tag;
  taskForm.dataset.editingId = id;
  formSubmitBtn.textContent = "Save changes";
  cancelEditBtn.classList.remove("hidden");
  document.getElementById("title").focus();
}

function exitEditMode() {
  delete taskForm.dataset.editingId;
  formSubmitBtn.textContent = "Add task";
  cancelEditBtn.classList.add("hidden");
}

cancelEditBtn.addEventListener("click", () => {
  taskForm.reset();
  exitEditMode();
});

// Toggle / delete

taskList.addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-action]");
  if (!btn) return;
  const li = e.target.closest("li.task-item");
  const id = Number(li.dataset.id);
  const action = btn.dataset.action;

  if (action === "toggle") toggleTask(id);
  else if (action === "edit") startEdit(id);
  else if (action === "delete") askDelete(id);
});

async function toggleTask(id) {
  await apiFetch(`/api/tasks/${id}/toggle`, { method: "POST" });
  loadTasks();
}

function askDelete(id) {
  taskToDelete = id;
  confirmModal.classList.remove("hidden");
}

document.getElementById("cancelDeleteBtn").onclick = () => {
  confirmModal.classList.add("hidden");
  taskToDelete = null;
};

document.getElementById("confirmDeleteBtn").onclick = () => {
  confirmModal.classList.add("hidden");
  lastDeletedTask = taskToDelete;

  hiddenTaskIds.add(lastDeletedTask);
  renderTasks(currentTasks);

  showToast("Task deleted", { undo: true, danger: true });

  // 8 seconds undo
  undoTimer = setTimeout(async () => {
    await apiFetch(`/api/tasks/${lastDeletedTask}`, { method: "DELETE" });
    hiddenTaskIds.delete(lastDeletedTask);
    hideToast();
    loadTasks();
  }, 8000);
};

toastUndoBtn.onclick = () => {
  clearTimeout(undoTimer);
  hiddenTaskIds.delete(lastDeletedTask);
  hideToast();
  renderTasks(currentTasks);
  lastDeletedTask = null;
};

["filterTag", "filterPriority", "sortBy"].forEach(id =>
  document.getElementById(id).addEventListener("change", loadTasks)
);

loadTasks();
