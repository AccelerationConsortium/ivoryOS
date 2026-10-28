// Runs a method form in the background: the page stays put, so it keeps getting socket
// events (plugin panels animate), and the server answers "busy" to other calls meanwhile
async function runInBackground(form) {
    var socket = window.socket;
    var data = new FormData(form);
    // without a socket nothing would say when the step ends, so the reply waits for it
    data.set('hidden_wait', socket ? 'false' : 'true');
    // a quick step can end before the reply naming it arrives; keep what ends meanwhile
    var endedEarly = {};
    function keep(result) { endedEarly[result.task_id] = result; }
    if (socket) socket.on('task_finished', keep);
    try {
        var response = await fetch(form.action, {
            method: 'POST',
            body: data,
            headers: { 'Accept': 'application/json' }
        });
        var result = await response.json();
        if (result.status === 'task started' && result.task_id != null) {
            return endedEarly[result.task_id] || await waitForStep(result.task_id);
        }
        return result;
    } catch (err) {
        return { success: false, output: err.message };
    } finally {
        if (socket) socket.off('task_finished', keep);
    }
}

// Resolves with a step's result once the task_finished socket event reports it. Events sent
// while the socket was cut off are lost, so on reconnecting it looks the step up once: it may
// have ended meanwhile, or the server restarted and marked it interrupted
function waitForStep(taskId) {
    return new Promise(function(resolve) {
        var socket = window.socket;

        function finish(result) {
            socket.off('task_finished', onFinished);
            socket.off('connect', lookUp);
            resolve(result);
        }

        function onFinished(data) {
            if (data && data.task_id === taskId) finish(data);
        }

        function lookUp() {
            fetch((window.URL_PREFIX || '') + '/instruments/task/' + taskId)
                .then(function(response) { return response.ok ? response.json() : null; })
                .then(function(step) {
                    // an interrupted step has an error but no end time (mark_interrupted_steps)
                    if (step && (step.end_time || step.run_error)) {
                        finish({ success: !step.run_error, output: step.run_error || step.output });
                    }
                })
                .catch(function() {}); // the next reconnect looks again
        }

        socket.on('task_finished', onFinished);
        socket.on('connect', lookUp);
    });
}

// Shows a step running on this page's instrument that the page did not start: it was opened
// or reloaded mid-call, or another tab or client started it. busy_status names the running
// step when the page connects and when a step starts
var followedStep = null;

function followRunningStep(step) {
    if (!step || typeof INSTRUMENT === 'undefined' || step.component !== INSTRUMENT) return;
    if (followedStep !== null || document.querySelector('form[data-running]')) return;
    followedStep = step.id;

    var overlay = document.getElementById('overlay');
    if (overlay) {
        overlay.style.display = 'block';
        var textEl = document.getElementById('overlay-text');
        if (textEl) textEl.innerText = `Processing ${step.method}...`;
    }
    waitForStep(step.id).then(function(result) {
        followedStep = null;
        if (overlay) overlay.style.display = 'none';
        showRunResult(result);
    });
}

document.addEventListener('DOMContentLoaded', function() {
    var waitForSocket = setInterval(function() {
        if (!window.socket) return;
        clearInterval(waitForSocket);
        // a step named before this listener was in place
        followRunningStep(window.platformState.task);
        window.socket.on('busy_status', function(data) { followRunningStep(data.task); });
    }, 100);
});

// Shows a call's result where the page used to flash it after a reload
function showRunResult(result) {
    var container = document.querySelector('.flash');
    if (!container) return;

    var message;
    if (result.status === 'busy') {
        message = 'Run Error! System is busy, a workflow or another task is running.';
    } else {
        var output = 'output' in result ? result.output : (result.msg || result.error);
        if (output === null || output === undefined) output = 'None';
        else if (typeof output === 'object') output = JSON.stringify(output);
        message = result.success ? `Run Success! Output: ${output}` : `Run Error! ${output}`;
    }

    var alert = document.createElement('div');
    alert.className = 'alert alert-warning';
    alert.textContent = message;
    container.replaceChildren(alert);
}

function addOverlayToButtons(buttonIds) {
    buttonIds.forEach(function(buttonId) {
        // Use querySelector to ensure we get the actual form, not a div with the same ID
        var form = document.querySelector('form[name="' + buttonId + '"]');

        if (form) {
            form.addEventListener('submit', async function(event) {
                event.preventDefault();
                if (form.dataset.running === "true") {
                    return; // e.g. Enter pressed in a field under the overlay
                }

                function showOverlayAndSubmit() {
                    var overlay = document.getElementById('overlay');
                    if (overlay) {
                        overlay.style.display = 'block';
                        var textEl = document.getElementById('overlay-text');
                        if (textEl) textEl.innerText = `Processing ${buttonId}...`;
                    }
                    form.dataset.running = "true";
                    runInBackground(form).then(function(result) {
                        if (overlay) overlay.style.display = 'none';
                        delete form.dataset.running;
                        // an override is for this one call, the next one asks again
                        form.querySelectorAll('input[name="override_busy"]').forEach(function(input) {
                            input.remove();
                        });
                        showRunResult(result);
                    });
                }
                
                try {
                    // Check if system is busy using global platform state (synced via sockets)
                    const isBusy = window.platformState && (window.platformState.is_running || window.platformState.is_paused);
                    
                    if (isBusy) {
                        if (typeof bootstrap !== 'undefined') {
                            try {
                                let modalEl = document.getElementById('manualOverrideModal');
                                if (!modalEl) {
                                    const modalHtml = `
                                        <div class="modal fade" id="manualOverrideModal" tabindex="-1" aria-labelledby="manualOverrideModalLabel" aria-hidden="true">
                                          <div class="modal-dialog">
                                            <div class="modal-content">
                                              <div class="modal-header">
                                                <h5 class="modal-title text-warning" id="manualOverrideModalLabel"><i class="bi bi-exclamation-triangle-fill me-2"></i>System Busy</h5>
                                                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                                              </div>
                                              <div class="modal-body">
                                                <p>The system is currently busy (a workflow or another task might be running, or paused).</p>
                                                <p><strong>Are you sure you want to override and execute this action manually?</strong></p>
                                              </div>
                                              <div class="modal-footer">
                                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                                <button type="button" class="btn btn-warning" id="manualOverrideConfirmBtn">Proceed with Override</button>
                                              </div>
                                            </div>
                                          </div>
                                        </div>
                                    `;
                                    document.body.insertAdjacentHTML('beforeend', modalHtml);
                                    modalEl = document.getElementById('manualOverrideModal');
                                }
                                
                                const confirmBtn = document.getElementById('manualOverrideConfirmBtn');
                                const newConfirmBtn = confirmBtn.cloneNode(true);
                                confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
                                
                                const modal = new bootstrap.Modal(modalEl);
                                
                                newConfirmBtn.addEventListener('click', function() {
                                    modal.hide();
                                    let overrideInput = document.createElement("input");
                                    overrideInput.type = "hidden";
                                    overrideInput.name = "override_busy";
                                    overrideInput.value = "true";
                                    form.appendChild(overrideInput);
                                    showOverlayAndSubmit();
                                });
                                
                                modal.show();
                            } catch (err) {
                                console.error("Error showing modal:", err);
                                if (confirm("System is currently busy (a workflow or another task might be running, or paused). Are you sure you want to override and execute this action manually?")) {
                                    let overrideInput = document.createElement("input");
                                    overrideInput.type = "hidden";
                                    overrideInput.name = "override_busy";
                                    overrideInput.value = "true";
                                    form.appendChild(overrideInput);
                                    showOverlayAndSubmit();
                                }
                            }
                        } else {
                            if (confirm("System is currently busy (a workflow or another task might be running, or paused). Are you sure you want to override and execute this action manually?")) {
                                let overrideInput = document.createElement("input");
                                overrideInput.type = "hidden";
                                overrideInput.name = "override_busy";
                                overrideInput.value = "true";
                                form.appendChild(overrideInput);
                                
                                showOverlayAndSubmit();
                            }
                        }
                    } else {
                        showOverlayAndSubmit();
                    }
                } catch (e) {
                    console.error("Error during status check:", e);
                    // Fallback to normal submission on error
                    showOverlayAndSubmit();
                }
            });
        }
    });
}

// buttonIds should be set dynamically in your HTML template
if (typeof buttonIds !== 'undefined') {
    addOverlayToButtons(buttonIds);
}

// Going Back to this page can restore it from the browser cache mid-call, overlay and all;
// reset it, and show the step again if one is still running
window.addEventListener('pageshow', function(event) {
    if (!event.persisted) return;
    var overlay = document.getElementById('overlay');
    if (overlay) overlay.style.display = 'none';
    document.querySelectorAll('form[data-running]').forEach(function(form) {
        delete form.dataset.running;
    });
    followedStep = null;
    if (window.platformState) followRunningStep(window.platformState.task);
});
