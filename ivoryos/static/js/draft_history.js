// ============================================================================
// UNDO AND REDO
// ============================================================================
// The server keeps each draft's history (see services/draft_history.py). This file is the
// designer's side of it: the undo, redo and history buttons over the canvas, the keyboard
// shortcuts, and a short note of what was undone. Every canvas fragment the server sends
// carries what undo and redo would do now, in #draft-history-state.

const IS_MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
const UNDO_KEYS = IS_MAC ? "⌘Z" : "Ctrl+Z";
const REDO_KEYS = IS_MAC ? "⇧⌘Z" : "Ctrl+Y";

// one request at a time, so pressing Ctrl+Z three times quickly undoes three changes in order
let historyQueue = Promise.resolve();

function syncHistoryControls() {
    const state = document.getElementById("draft-history-state");
    if (!state) return;
    setHistoryButton("draftUndoButton", state.dataset.canUndo === "true", "Undo", state.dataset.undoLabel, UNDO_KEYS);
    setHistoryButton("draftRedoButton", state.dataset.canRedo === "true", "Redo", state.dataset.redoLabel, REDO_KEYS);
}

function setHistoryButton(id, enabled, verb, label, keys) {
    const button = document.getElementById(id);
    if (!button) return;
    button.disabled = !enabled;
    const text = enabled ? `${verb}${label ? " " + label : ""} (${keys})` : `Nothing to ${verb.toLowerCase()}`;
    button.title = text;
    button.setAttribute("aria-label", text);
}

function sendHistoryRequest(url, kind) {
    historyQueue = historyQueue
        .then(() => fetch(url, { method: "POST", headers: { "Accept": "application/json" } }))
        .then(res => res.json())
        .then(data => applyHistoryResponse(data, kind))
        .catch(err => console.error("Undo or redo failed:", err));
    return historyQueue;
}

function undoDraft() {
    return sendHistoryRequest(draftUndoUrl, "undo");
}

function redoDraft() {
    return sendHistoryRequest(draftRedoUrl, "redo");
}

function restoreDraftHistory(index) {
    return sendHistoryRequest(draftRestoreUrl.replace(/\/0$/, "/" + index), "restore");
}

function applyHistoryResponse(data, kind) {
    if (!data.success) {
        showHistoryToast(data.message);
        return;
    }
    // the whole canvas: the name, the tab and the footer can change as well as the steps
    document.getElementById("canvas-wrapper").innerHTML = data.html;
    initializeCanvas();
    if (typeof refreshSidebarVariables === "function") refreshSidebarVariables();
    const undoAgain = kind === "redo" ? { text: "Undo", run: undoDraft } : null;
    const redoAgain = kind === "undo" ? { text: "Redo", run: redoDraft } : null;
    showHistoryToast(data.message, undoAgain || redoAgain);
}

// ---------------------------------------------------------------------------
// what was just undone or redone, with a way straight back
// ---------------------------------------------------------------------------

function showHistoryToast(message, action) {
    if (!message) return;
    let toast = document.getElementById("draftHistoryToast");
    if (!toast) {
        toast = document.createElement("div");
        toast.id = "draftHistoryToast";
        toast.className = "history-toast";
        toast.setAttribute("role", "status");
        toast.setAttribute("aria-live", "polite");
        document.body.appendChild(toast);
    }
    toast.replaceChildren();
    const text = document.createElement("span");
    text.textContent = message;
    toast.appendChild(text);
    if (action) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = action.text;
        button.addEventListener("click", () => {
            toast.classList.remove("show");
            action.run();
        });
        toast.appendChild(button);
    }
    toast.classList.add("show");
    clearTimeout(toast.hideTimer);
    toast.hideTimer = setTimeout(() => toast.classList.remove("show"), 4000);
}

// ---------------------------------------------------------------------------
// the history menu: every change, newest first; picking one goes back (or forward) to it
// ---------------------------------------------------------------------------

function timeAgo(seconds) {
    const elapsed = Date.now() / 1000 - seconds;
    if (elapsed < 45) return "just now";
    if (elapsed < 90) return "1 min ago";
    if (elapsed < 3600) return `${Math.round(elapsed / 60)} min ago`;
    if (elapsed < 5400) return "1 hour ago";
    if (elapsed < 86400) return `${Math.round(elapsed / 3600)} hours ago`;
    return new Date(seconds * 1000).toLocaleString();
}

function renderHistoryMenu(menu, history) {
    menu.replaceChildren();
    const header = document.createElement("li");
    header.innerHTML = '<h6 class="dropdown-header">History</h6>';
    menu.appendChild(header);

    const entries = history.entries || [];
    if (entries.length < 2) {
        const empty = document.createElement("li");
        empty.innerHTML = '<span class="dropdown-item-text small text-muted">No changes yet</span>';
        menu.appendChild(empty);
        return;
    }
    for (let i = entries.length - 1; i >= 0; i--) {
        const entry = entries[i];
        const item = document.createElement("li");
        const button = document.createElement("button");
        button.type = "button";
        button.className = "dropdown-item draft-history-item";
        button.dataset.index = String(entry.index);
        if (entry.index === history.index) {
            button.classList.add("current");
            button.setAttribute("aria-current", "step");
        } else if (entry.index > history.index) {
            // undone, and still there to redo
            button.classList.add("undone");
        }
        const mark = document.createElement("i");
        mark.className = "bi bi-check2 draft-history-mark";
        mark.setAttribute("aria-hidden", "true");
        const label = document.createElement("span");
        label.className = "draft-history-label";
        label.textContent = entry.label;
        const time = document.createElement("span");
        time.className = "draft-history-time";
        time.textContent = timeAgo(entry.time);
        button.append(mark, label, time);
        item.appendChild(button);
        menu.appendChild(item);
    }
    if (history.trimmed) {
        const note = document.createElement("li");
        note.innerHTML = '<span class="dropdown-item-text small text-muted">Older changes are not kept</span>';
        menu.appendChild(note);
    }
}

document.addEventListener("show.bs.dropdown", function (event) {
    if (event.target.id !== "draftHistoryButton") return;
    const menu = document.getElementById("draftHistoryMenu");
    fetch(draftHistoryUrl, { headers: { "Accept": "application/json" } })
        .then(res => res.json())
        .then(history => renderHistoryMenu(menu, history))
        .catch(err => console.error("Failed to load the history:", err));
});

document.addEventListener("click", function (event) {
    const item = event.target.closest(".draft-history-item");
    if (!item || item.classList.contains("current")) return;
    restoreDraftHistory(Number(item.dataset.index));
});

// ---------------------------------------------------------------------------
// keyboard: Ctrl+Z / ⌘Z undoes, Ctrl+Y, Ctrl+Shift+Z or ⇧⌘Z redoes
// ---------------------------------------------------------------------------

// typing in a field keeps the browser's own undo for the text
function isEditingText(element) {
    if (!element) return false;
    if (element.isContentEditable) return true;
    const tag = element.tagName;
    if (tag === "TEXTAREA" || tag === "SELECT") return true;
    if (tag !== "INPUT") return false;
    const notText = ["checkbox", "radio", "button", "submit", "reset", "range", "color", "file", "image"];
    return !notText.includes((element.type || "").toLowerCase());
}

document.addEventListener("keydown", function (event) {
    if (!(event.ctrlKey || event.metaKey) || event.altKey) return;
    const key = event.key.toLowerCase();
    const undo = key === "z" && !event.shiftKey;
    const redo = key === "y" || (key === "z" && event.shiftKey);
    if (!undo && !redo) return;
    // nor while a pop-up is open: a step being edited there is not the canvas
    if (isEditingText(event.target) || document.querySelector(".modal.show")) return;
    event.preventDefault();
    if (undo) undoDraft();
    else redoDraft();
});
