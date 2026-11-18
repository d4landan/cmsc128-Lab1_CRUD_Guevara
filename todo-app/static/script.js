// script.js -- the To-Do List page.
//   1. Elements and state
//   2. Helpers (escaping, dates, toast, busy buttons)
//   3. Talking to the server (api)
//   4. Drawing the list
//   5. Add / edit
//   6. Toggle / delete / undo
//   7. Confirm dialog
//   8. Start-up
//
// The browser never decides who owns what: every request carries the login
// cookie and the SERVER only returns or changes the logged-in user's own tasks.

(function () {
  "use strict";

  // ---------------------------------------------------------- 1. elements --
  const $ = (id) => document.getElementById(id);

  const taskList = $("taskList");
  const taskForm = $("taskForm");
  const submitBtn = $("formSubmitBtn");
  const cancelEditBtn = $("cancelEditBtn");
  const listStatus = $("listStatus");
  const modal = $("confirmModal");
  const toast = $("toast");
  const toastMessage = $("toastMessage");
  const toastUndoBtn = $("toastUndoBtn");

  const UNDO_SECONDS = 6;

  let tasks = [];                 // what the server last sent
  let editingId = null;           // id of the task being edited, or null
  let hiddenIds = new Set();      // deleted on screen, still inside the undo window
  let pendingDelete = null;       // { id, timer } while the undo window is open
  let toastTimer = null;
  let loadSeq = 0;                // lets a slow, out-of-date response be ignored

  // ----------------------------------------------------------- 2. helpers --
  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value ?? "";
    return div.innerHTML;
  }

  function formatDue(value) {
    const date = new Date(value);
    if (isNaN(date)) return value;
    return "Due " + date.toLocaleString(undefined, {
      month: "short", day: "numeric", hour: "numeric", minute: "2-digit"
    });
  }

  function showToast(message, { undo = false, danger = false, duration = 3500 } = {}) {
    clearTimeout(toastTimer);
    toastMessage.textContent = message;
    toastUndoBtn.classList.toggle("hidden", !undo);
    toast.classList.toggle("toast-danger", danger);
    toast.classList.remove("hidden");
    if (!undo) toastTimer = setTimeout(hideToast, duration);
  }

  function hideToast() {
    clearTimeout(toastTimer);
    toast.classList.add("hidden");
  }

  // Shows "Saving…" and disables the button while `work` runs.
  async function withBusy(button, busyLabel, work) {
    const original = button.textContent;
    button.disabled = true;
    button.textContent = busyLabel;
    try {
      return await work();
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  function showStatus(message, retry = false) {
    listStatus.textContent = message;
    if (retry) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn-ghost";
      button.textContent = "Try again";
      button.addEventListener("click", loadTasks);
      listStatus.append(" ", button);
    }
    listStatus.classList.remove("hidden");
  }

  const dateEl = $("todayDate");
  if (dateEl) {
    dateEl.textContent = new Date().toLocaleDateString(undefined, {
      weekday: "long", month: "long", day: "numeric"
    });
  }

  // -------------------------------------------------------- 3. the server --
  // Every task request goes through here. A 401 means the login is gone (it
  // expired, or the user logged out in another tab), so go to the login page.
  async function api(path, { method = "GET", body } = {}) {
    let response;
    try {
      response = await fetch(path, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        credentials: "same-origin"
      });
    } catch (error) {
      return { ok: false, status: 0, data: { error: "Can't reach the server. Check your connection." } };
    }
    if (response.status === 401) {
      window.location.href = "/login";
    }
    let data = {};
    try { data = await response.json(); } catch (error) { /* empty body */ }
    return { ok: response.ok, status: response.status, data };
  }

  // The first problem the server reported, in plain words.
  function problemText(result, fallback) {
    const errors = result.data && result.data.errors;
    return (errors && Object.values(errors)[0]) || (result.data && result.data.error) || fallback;
  }

  function query() {
    const params = new URLSearchParams({ sort_by: $("sortBy").value });
    if ($("filterTag").value) params.append("tag", $("filterTag").value);
    if ($("filterPriority").value) params.append("priority", $("filterPriority").value);
    return params.toString();
  }

  async function loadTasks() {
    const seq = ++loadSeq;
    const result = await api(`/api/tasks?${query()}`);
    if (seq !== loadSeq) return;                       // a newer request is already in flight
    if (!result.ok) {
      showStatus("We couldn't load your tasks.", true);
      return;
    }
    tasks = result.data;
    render();
  }

  // -------------------------------------------------------- 4. the list --
  function render() {
    const visible = tasks.filter((task) => !hiddenIds.has(task.id));
    taskList.innerHTML = "";

    if (visible.length === 0) {
      showStatus($("filterTag").value || $("filterPriority").value
        ? "No tasks match these filters."
        : "Nothing here yet. Add your first task above.");
    } else {
      listStatus.classList.add("hidden");
    }

    visible.forEach((task) => {
      const li = document.createElement("li");
      li.className = `task-item priority-${(task.priority || "").toLowerCase()}${task.done ? " done" : ""}`;
      li.dataset.id = task.id;
      const name = escapeHtml(task.title);
      li.innerHTML = `
        <button type="button" class="check-btn" data-action="toggle" aria-pressed="${task.done ? "true" : "false"}"
                aria-label="Mark done: ${name}">${task.done ? "✓" : ""}</button>
        <div class="task-info">
          <p class="task-title">${name}</p>
          <div class="task-meta">
            <span class="chip">${escapeHtml(formatDue(task.due_date))}</span>
            <span class="chip">${escapeHtml(task.tag)}</span>
          </div>
        </div>
        <span class="priority-label"><span class="priority-dot" aria-hidden="true"></span>${escapeHtml(task.priority)} priority</span>
        <div class="task-actions">
          <button type="button" class="btn-icon" data-action="edit" aria-label="Edit task: ${name}">Edit</button>
          <button type="button" class="btn-icon btn-icon-danger" data-action="delete" aria-label="Delete task: ${name}">Delete</button>
        </div>`;
      taskList.appendChild(li);
    });
  }

  // ------------------------------------------------------ 5. add / edit --
  taskForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      title: $("title").value,
      due_date: $("dueDate").value,
      priority: $("priority").value,
      tag: $("tag").value
    };
    const wasEditing = editingId !== null;

    const result = await withBusy(submitBtn, "Saving…", () =>
      wasEditing
        ? api(`/api/tasks/${editingId}`, { method: "PUT", body: payload })
        : api("/api/tasks", { method: "POST", body: payload })
    );

    if (!result.ok) {
      if (result.status === 401) return;
      if (result.status === 404) {            // e.g. the task was deleted in another tab
        resetForm();
        loadTasks();
      }
      showToast(problemText(result, "Couldn't save the task. Please try again."), { danger: true });
      return;
    }

    resetForm();
    showToast(wasEditing ? "Task updated" : "Task added");
    loadTasks();
  });

  function resetForm() {
    taskForm.reset();
    $("priority").value = "Med";
    editingId = null;
    submitBtn.textContent = "Add task";
    cancelEditBtn.classList.add("hidden");
  }

  function startEdit(id) {
    const task = tasks.find((t) => t.id === id);
    if (!task) return;
    $("title").value = task.title;
    $("dueDate").value = task.due_date;
    $("priority").value = task.priority;
    $("tag").value = task.tag;
    editingId = id;
    submitBtn.textContent = "Save changes";
    cancelEditBtn.classList.remove("hidden");
    $("title").focus();
  }

  cancelEditBtn.addEventListener("click", resetForm);

  // ------------------------------------------- 6. toggle / delete / undo --
  taskList.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const id = Number(button.closest("li.task-item").dataset.id);

    if (button.dataset.action === "toggle") toggleTask(id);
    else if (button.dataset.action === "edit") startEdit(id);
    else if (button.dataset.action === "delete") deleteTask(id);
  });

  async function toggleTask(id) {
    const result = await api(`/api/tasks/${id}/toggle`, { method: "POST" });
    if (!result.ok && result.status !== 401) {
      showToast(problemText(result, "Couldn't update the task."), { danger: true });
    }
    loadTasks();
  }

  async function deleteTask(id) {
    if (!(await confirmDialog("Delete this task?", "Delete"))) return;

    await commitPendingDelete();                       // finish an earlier delete still in its undo window
    hiddenIds.add(id);
    render();
    showToast("Task deleted", { undo: true, danger: true });
    pendingDelete = { id, timer: setTimeout(commitPendingDelete, UNDO_SECONDS * 1000) };
  }

  // Really deletes the task whose undo window is open (on timeout, or before another delete).
  async function commitPendingDelete() {
    if (!pendingDelete) return;
    const { id, timer } = pendingDelete;
    pendingDelete = null;
    clearTimeout(timer);
    await api(`/api/tasks/${id}`, { method: "DELETE" });
    hiddenIds.delete(id);
    hideToast();
    loadTasks();
  }

  toastUndoBtn.addEventListener("click", () => {
    if (!pendingDelete) return;
    clearTimeout(pendingDelete.timer);
    hiddenIds.delete(pendingDelete.id);
    pendingDelete = null;
    hideToast();
    render();
  });

  // If the page is closed inside the undo window, still finish the delete.
  window.addEventListener("pagehide", () => {
    if (pendingDelete) {
      fetch(`/api/tasks/${pendingDelete.id}`, { method: "DELETE", keepalive: true });
    }
  });

  ["filterTag", "filterPriority", "sortBy"].forEach((id) => $(id).addEventListener("change", loadTasks));

  // ------------------------------------------------- 7. confirm dialog --
  // Returns a Promise<boolean>. Keyboard friendly: focus starts on Cancel (the
  // safe choice), Tab stays inside the dialog, Escape cancels.
  function confirmDialog(message, okLabel) {
    return new Promise((resolve) => {
      const opener = document.activeElement;
      const okBtn = $("confirmOkBtn");
      const cancelBtn = $("confirmCancelBtn");
      $("confirmMessage").textContent = message;
      okBtn.textContent = okLabel;
      modal.classList.remove("hidden");
      cancelBtn.focus();

      function finish(answer) {
        modal.classList.add("hidden");
        document.removeEventListener("keydown", onKey);
        okBtn.onclick = cancelBtn.onclick = null;
        if (opener && opener.focus) opener.focus();
        resolve(answer);
      }
      function onKey(event) {
        if (event.key === "Escape") finish(false);
        if (event.key === "Tab") {                    // keep focus inside the dialog
          const first = cancelBtn, last = okBtn;
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
          else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        }
      }
      document.addEventListener("keydown", onKey);
      okBtn.onclick = () => finish(true);
      cancelBtn.onclick = () => finish(false);
    });
  }

  // ----------------------------------------------------------- 8. start --
  loadTasks();
})();
