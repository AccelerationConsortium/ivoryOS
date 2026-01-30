// ============================================================================
// STATE MANAGEMENT
// ============================================================================

let previousHtmlState = null;  // Store previous instrument panel state
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

function updateInstrumentPanel(link) {
    const url = link.dataset.getUrl;

    fetch(url)
        .then(res => res.json())
        .then(data => {
            if (data.html) {
                document.getElementById("sidebar-wrapper").innerHTML = data.html;
                initializeDragHandlers();
            }
        })
        .catch(err => console.error("Error updating instrument panel:", err));
}

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

function editAction(uuid) {
    if (!uuid) {
        console.error('Invalid UUID');
        return;
    }

    // Store current state for rollback
    previousHtmlState = document.getElementById('instrument-panel').innerHTML;

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
                    // Restore panel so user isn't stuck
                    if (previousHtmlState) {
                        document.getElementById('instrument-panel').innerHTML = previousHtmlState;
                        previousHtmlState = null;
                    }
                    throw new Error("Step fetch failed: " + response.status);
                });
            }
            return response.text();
        })
        .then(html => {
            document.getElementById('instrument-panel').innerHTML = html;

            // Set up back button
            const backButton = document.getElementById('back');
            if (backButton) {
                backButton.addEventListener('click', function (e) {
                    e.preventDefault();
                    if (previousHtmlState) {
                        document.getElementById('instrument-panel').innerHTML = previousHtmlState;
                        previousHtmlState = null;
                    }
                });
            }
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
            if (html) {
                updateActionCanvas(html);

                // Restore previous instrument panel state
                if (previousHtmlState) {
                    document.getElementById('instrument-panel').innerHTML = previousHtmlState;
                    previousHtmlState = null;
                }

                // Check for warnings
                showWarningIfExists(html);
            }
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

function showWarningIfExists(html) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    const warningDiv = doc.querySelector('#warning');

    if (warningDiv && warningDiv.textContent.trim()) {
        alert(warningDiv.textContent.trim());
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

    const div = document.createElement("div");
    div.className = "input-group mb-2 dynamic-arg-row";
    div.innerHTML = `
        <input type="text" class="form-control" name="extra_key[]" placeholder="Parameter Name" required>
        <input type="text" class="form-control" name="extra_value[]" list="variables_datalist" placeholder="Value" required>
        <button type="button" class="btn btn-outline-danger" onclick="this.parentElement.remove()">X</button>
    `;
    container.appendChild(div);
}

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener("DOMContentLoaded", function () {
    getCodePreview();
});

// ============================================================================
// SEARCH BAR DELEGATION
// ============================================================================

document.addEventListener('input', function (e) {
    if (e.target && e.target.id === 'actionSearch') {
        const searchTerm = e.target.value.toLowerCase();
        const actions = document.querySelectorAll('.design-control');

        actions.forEach(action => {
            const button = action.querySelector('.accordion-button');
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