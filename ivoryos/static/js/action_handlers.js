// ============================================================================
// STATE MANAGEMENT
// ============================================================================

let lastFocusedElement = null; // Track focus for modal management

// ============================================================================
// MODE & BATCH MANAGEMENT
// ============================================================================

function getMode() {
    return sessionStorage.getItem("mode") || "single";
}

function setMode(mode, triggerUpdate = true) {
    sessionStorage.setItem("mode", mode);

    const modeButtons = document.querySelectorAll(".mode-toggle");
    const batchOptions = document.getElementById("batch-options");

    modeButtons.forEach(b => b.classList.toggle("active", b.dataset.mode === mode));

    if (batchOptions) {
        batchOptions.style.display = (mode === "batch") ? "inline-flex" : "none";
    }

    if (triggerUpdate) updateCode();
}

function getBatch() {
    return sessionStorage.getItem("batch") || "sample";
}

function setBatch(batch, triggerUpdate = true) {
    sessionStorage.setItem("batch", batch);

    const batchButtons = document.querySelectorAll(".batch-toggle");
    batchButtons.forEach(b => b.classList.toggle("active", b.dataset.batch === batch));

    if (triggerUpdate) updateCode();
}

// ============================================================================
// CODE OVERLAY MANAGEMENT
// ============================================================================

async function updateCode() {
    try {
        const params = new URLSearchParams({ mode: getMode(), batch: getBatch() });
        const res = await fetch(scriptCompileUrl + "?" + params.toString());
        if (!res.ok) return;

        const data = await res.json();
        const codeElem = document.getElementById("python-code");

        const script = data.code?.script || "";
        const prep = data.code?.prep || "";
        const cleanup = data.code?.cleanup || "";
        const imports = data.code?.imports || "";

        let finalCode = "";
        if (imports.trim())
            finalCode += imports + "\n\n";

        if (prep.trim()) {
            finalCode += "# --- PREP CODE ---\n" + prep.trim() + "\n\n";
        }
        if (script.trim()) {
            finalCode += "# --- MAIN SCRIPT ---\n" + script.trim() + "\n\n";
        }
        if (cleanup.trim()) {
            finalCode += "# --- CLEANUP CODE ---\n" + cleanup.trim() + "\n";
        }

        codeElem.removeAttribute("data-highlighted");
        codeElem.textContent = finalCode || "# No code found";

        if (window.hljs) hljs.highlightElement(codeElem);
    } catch (err) {
        console.error("Error updating code:", err);
    }
}

function initializeCodeOverlay() {
    const codeElem = document.getElementById("python-code");
    const copyBtn = document.getElementById("copy-code");
    const downloadBtn = document.getElementById("download-code");

    if (!copyBtn || !downloadBtn) return; // Elements don't exist

    // Remove old listeners by cloning (prevents duplicate bindings)
    const newCopyBtn = copyBtn.cloneNode(true);
    const newDownloadBtn = downloadBtn.cloneNode(true);
    copyBtn.parentNode.replaceChild(newCopyBtn, copyBtn);
    downloadBtn.parentNode.replaceChild(newDownloadBtn, downloadBtn);

    // Copy to clipboard
    newCopyBtn.addEventListener("click", () => {
        navigator.clipboard.writeText(codeElem.textContent)
            .then(() => alert("Code copied!"))
            .catch(err => console.error("Failed to copy", err));
    });

    // Download current code
    newDownloadBtn.addEventListener("click", () => {
        const blob = new Blob([codeElem.textContent], { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "script.py";
        a.click();
        URL.revokeObjectURL(url);
    });
    updateCode();
}

// ============================================================================
// UI UPDATE FUNCTIONS
// ============================================================================
function getCodePreview() {

    const mode = getMode();
    const batch = getBatch();
    // Restore toggle UI state (without triggering updates)
    setMode(mode, false);
    setBatch(batch, false);
    // Rebind event handlers for mode/batch toggles
    document.querySelectorAll(".mode-toggle").forEach(btn => {
        btn.addEventListener("click", () => setMode(btn.dataset.mode));
    });
    document.querySelectorAll(".batch-toggle").forEach(btn => {
        btn.addEventListener("click", () => setBatch(btn.dataset.batch));
    });
    // Reinitialize code overlay buttons
    initializeCodeOverlay();
}

function updateActionCanvas(html) {
    document.getElementById("canvas-action-wrapper").innerHTML = html;
    initializeCanvas();
}

// ============================================================================
// TOOLBOX
// ============================================================================

// Every group's actions load with the page, folded ones too, so opening a group shows them at
// once instead of growing around a "Loading…" line.
function loadToolboxActions(container) {
    container.dataset.loaded = "loading";
    return fetch(container.dataset.url)
        .then(res => res.json())
        .then(data => {
            container.innerHTML = data.html || "";
            container.dataset.loaded = "true";
            initializeDragHandlers();
        })
        .catch(err => {
            container.dataset.loaded = "";
            console.error("Error loading toolbox actions:", err);
        });
}

function initializeToolbox() {
    document.querySelectorAll(".toolbox-actions").forEach(loadToolboxActions);
}

// load again what is already loaded, e.g. once auto fill changes how forms are filled
function reloadToolboxActions() {
    document.querySelectorAll('.toolbox-actions[data-loaded="true"]').forEach(loadToolboxActions);
}

// Folding is a plain show and hide, with no height animation to wait for or jump
function setToolboxOpen(button, open) {
    button.setAttribute("aria-expanded", open ? "true" : "false");
    document.getElementById(button.getAttribute("aria-controls")).hidden = !open;
}

document.addEventListener("click", function (event) {
    const divider = event.target.closest(".toolbox-divider");
    if (divider) {
        const open = divider.getAttribute("aria-expanded") !== "true";
        setToolboxOpen(divider, open);
        // a group whose actions failed to load tries again when opened
        const container = document.getElementById(divider.getAttribute("aria-controls")).querySelector(".toolbox-actions");
        if (open && container && !container.dataset.loaded) loadToolboxActions(container);
        return;
    }
    const toggle = event.target.closest(".toolbox-action-toggle");
    if (toggle) {
        const open = toggle.getAttribute("aria-expanded") !== "true";
        // one form open per group keeps the list short
        if (open) {
            toggle.closest(".toolbox-action-list")
                .querySelectorAll('.toolbox-action-toggle[aria-expanded="true"]')
                .forEach(other => setToolboxOpen(other, false));
        }
        setToolboxOpen(toggle, open);
    }
});

// ============================================================================
// WORKFLOW MANAGEMENT
// ============================================================================

function saveWorkflow(link) {
    const url = link.dataset.postUrl;

    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                window.location.reload();
            } else {
                alert("Failed to save workflow: " + data.error);
            }
        })
        .catch(err => {
            console.error("Save error:", err);
            alert("Something went wrong.");
        });
}

function clearDraft() {
    fetch(scriptDeleteUrl, {
        method: "DELETE",
        headers: {
            "Content-Type": "application/json",
        },
    })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                window.location.reload();
            } else {
                alert("Failed to clear draft");
            }
        })
        .catch(error => console.error("Failed to clear draft", error));
}

function refreshSidebarVariables() {
    fetch(variablesUrl)
        .then(res => res.json())
        .then(data => {
            const datalist = document.getElementById("variables_datalist");
            if (datalist) {
                datalist.innerHTML = "";
                data.variables.forEach(v => {
                    const option = document.createElement("option");
                    option.value = v;
                    option.textContent = v;
                    datalist.appendChild(option);
                });
            }
        })
        .catch(err => console.error("Failed to refresh variables:", err));
}

// ============================================================================
// ACTION MANAGEMENT (CRUD Operations)
// ============================================================================

function addMethodToDesign(event, form) {
    event.preventDefault();

    const formData = new FormData(form);

    fetch(form.action, {
        method: 'POST',
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateActionCanvas(data.html);
                hideModal();
                refreshSidebarVariables();
            } else {
                alert("Failed to add method: " + data.error);
            }
        })
        .catch(error => console.error('Error:', error));
}

// A step is edited in a pop-up, so the toolbox stays as it was left
function editAction(uuid) {
    if (window.isSorting) {
        return;
    }

    if (!uuid) {
        console.error('Invalid UUID');
        return;
    }

    fetch(scriptStepUrl.replace('0', uuid), {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json'
        }
    })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => {
                    if (err.warning) {
                        alert(err.warning);
                    }
                    throw new Error("Step fetch failed: " + response.status);
                });
            }
            return response.text();
        })
        .then(html => {
            const modal = document.getElementById('editStepModal');
            modal.querySelector('.modal-content').innerHTML = html;
            bootstrap.Modal.getOrCreateInstance(modal).show();
        })
        .catch(error => console.error('Error:', error));
}

function submitEditForm(event) {
    event.preventDefault();

    const form = event.target;
    const formData = new FormData(form);

    fetch(form.action, {
        method: 'POST',
        body: formData
    })
        .then(response => response.text())
        .then(html => {
            if (!html) return;
            updateActionCanvas(html);
            const warning = warningIn(html);
            if (warning) {
                // the pop-up stays open with the reason, so nothing typed is lost
                const box = document.getElementById('edit-step-warning');
                box.textContent = warning;
                box.classList.remove('d-none');
                return;
            }
            bootstrap.Modal.getInstance(document.getElementById('editStepModal'))?.hide();
            refreshSidebarVariables();
        })
        .catch(error => console.error('Error:', error));
}

function duplicateAction(uuid) {
    if (!uuid) {
        console.error('Invalid UUID');
        return;
    }

    fetch(scriptStepDupUrl.replace('0', uuid), {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
        .then(response => response.text())
        .then(html => {
            updateActionCanvas(html);
            showWarningIfExists(html);
            refreshSidebarVariables();
        })
        .catch(error => console.error('Error:', error));
}

function deleteAction(uuid) {
    if (!uuid) {
        console.error('Invalid UUID');
        return;
    }

    fetch(scriptStepUrl.replace('0', uuid), {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json'
        }
    })
        .then(response => response.text())
        .then(html => {
            updateActionCanvas(html);
            showWarningIfExists(html);
            refreshSidebarVariables();
        })
        .catch(error => console.error('Error:', error));
}

function toggleCommentAction(uuid) {
    if (!uuid) {
        console.error('Invalid UUID');
        return;
    }

    fetch(scriptStepToggleCommentUrl.replace('0', uuid), {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
        .then(response => response.text())
        .then(html => {
            updateActionCanvas(html);
            showWarningIfExists(html);
            updateCode(); // Update the python code overlay
        })
        .catch(error => console.error('Error:', error));
}

// ============================================================================
// MODAL MANAGEMENT
// ============================================================================

function hideModal() {
    if (document.activeElement) {
        document.activeElement.blur();
    }

    $('#dropModal').modal('hide');

    if (lastFocusedElement) {
        lastFocusedElement.focus();
    }
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

// The warning a re-rendered canvas carries, or null
function warningIn(html) {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const warningDiv = doc.querySelector('#warning');
    return warningDiv && warningDiv.textContent.trim() ? warningDiv.textContent.trim() : null;
}

function showWarningIfExists(html) {
    const warning = warningIn(html);
    if (warning) {
        alert(warning);
    }
}

// ============================================================================
// DYNAMIC ARGUMENTS MANAGEMENT
// ============================================================================

function addDynamicArg(btn) {
    let container = null;
    if (btn) {
        // Try to find relative container within the same form
        const form = btn.closest('form');
        if (form) {
            container = form.querySelector('.dynamic-args-container') || form.querySelector('#dynamic-args-container');
        }
    }
    // Fallback to ID for backward compatibility or if called without btn (though strict usage is better)
    if (!container) {
        container = document.getElementById("dynamic-args-container");
    }

    if (!container) return;

    // a step being edited suggests the variables set before it; a new action, all of them
    const listId = container.closest('form')?.querySelector('#step_variables') ? 'step_variables' : 'variables_datalist';
    const div = document.createElement("div");
    div.className = "input-group mb-2 dynamic-arg-row";
    div.innerHTML = `
        <input type="text" class="form-control" name="extra_key[]" placeholder="Parameter Name" required>
        <input type="text" class="form-control" name="extra_value[]" list="${listId}" placeholder="Value" required>
        <button type="button" class="btn btn-outline-danger" onclick="this.parentElement.remove()">X</button>
    `;
    container.appendChild(div);
}

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener("DOMContentLoaded", function () {
    getCodePreview();
    initializeToolbox();
});

// ============================================================================
// SEARCH BAR DELEGATION
// ============================================================================

// Each group with many actions has its own search box, which filters only that group
document.addEventListener('input', function (e) {
    if (e.target && e.target.classList.contains('action-search')) {
        const searchTerm = e.target.value.toLowerCase();
        const actions = e.target.closest('.toolbox-actions').querySelectorAll('.toolbox-action');

        actions.forEach(action => {
            const button = action.querySelector('.toolbox-action-toggle');
            if (button) {
                const name = button.innerText.toLowerCase();
                if (name.includes(searchTerm)) {
                    action.style.display = '';
                } else {
                    action.style.display = 'none';
                }
            }
        });
    }
});

// ============================================================================
// BATCH CONSOLIDATION UI
// ============================================================================

function updateConsolidateVisibility(input) {
    if (!input) return;
    const form = input.closest('form');
    if (!form) return;

    // Find batch action checkbox
    const batchBox = form.querySelector('input[name="ivoryos_batch_action"]');
    if (!batchBox) return;

    const isBatch = batchBox.checked;
    const isVar = input.value.trim().startsWith('#');

    // Find wrapper in the same input-group
    const group = input.closest('.input-group');
    if (!group) return;

    const wrapper = group.querySelector('.consolidate-wrapper');
    if (wrapper) {
        if (isBatch && isVar) {
            wrapper.style.display = 'flex';
        } else {
            wrapper.style.display = 'none';
        }
    }
}

function handleBatchActionChange(batchCheckbox) {
    const form = batchCheckbox.closest('form');
    if (!form) return;

    // Update all fields that have a consolidate wrapper
    const wrappers = form.querySelectorAll('.consolidate-wrapper');
    wrappers.forEach(wrapper => {
        const group = wrapper.closest('.input-group');
        const input = group.querySelector('input:not([type="checkbox"]):not([type="hidden"])');
        if (input) updateConsolidateVisibility(input);
    });
}