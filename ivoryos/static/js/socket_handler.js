document.addEventListener("DOMContentLoaded", function () {
    var socketPath = window.URL_PREFIX ? window.URL_PREFIX + "/socket.io" : "/socket.io";
    var socket = io({ path: socketPath });
    window.socket = socket;

    window.platformState = { is_running: false, is_paused: false };
    let retryInFlight = false;

    function getProgressBar() {
        return document.getElementById('progress-bar-inner');
    }

    function setProgressBarClasses(addClasses, removeClasses) {
        const progressBar = getProgressBar();
        if (!progressBar) return;

        if (removeClasses && removeClasses.length) {
            progressBar.classList.remove(...removeClasses);
        }
        if (addClasses && addClasses.length) {
            progressBar.classList.add(...addClasses);
        }
    }

    function clearStepHighlights() {
        document.querySelectorAll('.executing-step').forEach(el => {
            el.classList.remove('executing-step');
        });
        // Also clear any legacy inline background colors
        document.querySelectorAll('pre code').forEach(el => {
            el.style.backgroundColor = '';
        });
    }

    function updateGlobalStatus() {
        const activeErrorStr = localStorage.getItem('active_error');
        const activeInputStr = localStorage.getItem('active_input');
        const icon = document.getElementById('global-status-icon');
        
        if (icon) {
            icon.style.display = 'flex'; // always visible
            if (activeErrorStr) {
                icon.style.backgroundColor = '#dc3545'; // red
                icon.setAttribute('title', 'View active error');
                icon.innerHTML = '<i class="bi bi-exclamation-triangle-fill text-white fs-5"></i> <span>Error</span>';
                icon.style.cursor = 'pointer';
            } else if (activeInputStr) {
                icon.style.backgroundColor = '#0dcaf0'; // info cyan
                icon.setAttribute('title', 'View active input prompt');
                icon.innerHTML = '<i class="bi bi-keyboard-fill text-white fs-5"></i> <span>Input</span>';
                icon.style.cursor = 'pointer';
            } else if (window.platformState.is_paused) {
                icon.style.backgroundColor = '#fd7e14'; // orange
                icon.setAttribute('title', 'Platform is paused');
                icon.innerHTML = '<span>Paused</span>';
                icon.style.cursor = 'default';
            } else if (window.platformState.is_running) {
                icon.style.backgroundColor = '#198754'; // green
                icon.setAttribute('title', 'Platform is running');
                icon.innerHTML = '<span>Running</span>';
                icon.style.cursor = 'default';
            } else {
                icon.style.backgroundColor = '#6c757d'; // grey
                icon.setAttribute('title', 'Platform is idle');
                icon.innerHTML = '<span>Idle</span>';
                icon.style.cursor = 'default';
            }
        }
    }
    
    window.handleGlobalStatusClick = function() {
        if (localStorage.getItem('active_error')) {
            window.restoreErrorModal();
        } else if (localStorage.getItem('active_input')) {
            window.restoreInterventionModal();
        }
    };

    function checkActiveError() {
        const activeErrorStr = localStorage.getItem('active_error');
        const activeInputStr = localStorage.getItem('active_input');
        const progressBar = getProgressBar();
        
        updateGlobalStatus();

        if (activeErrorStr || activeInputStr) {
            if (progressBar) {
                try {
                    progressBar.classList.remove('bg-primary', 'bg-warning', 'bg-danger');
                    if (activeErrorStr) {
                        const activeError = JSON.parse(activeErrorStr);
                        if (activeError.type === 'error') {
                            progressBar.classList.add('bg-danger');
                        } else if (activeError.type === 'warning' || activeError.type === 'human_intervention') {
                            progressBar.classList.add('bg-warning');
                        }
                    } else if (activeInputStr) {
                        progressBar.classList.add('bg-warning');
                    }
                } catch (e) {
                    console.error("Failed to parse active state", e);
                }
            }
        } else {
            if (progressBar) {
                progressBar.classList.remove('bg-warning', 'bg-danger');
                if (!progressBar.classList.contains('bg-primary')) {
                    progressBar.classList.add('bg-primary');
                }

            }
        }
    }

    window.restoreInterventionModal = function() {
        const activeInputStr = localStorage.getItem('active_input');
        if (activeInputStr) {
            try {
                const data = JSON.parse(activeInputStr);
                showInputModal(data);
                return;
            } catch (e) {
                console.error("Failed to parse active_input", e);
                localStorage.removeItem('active_input');
            }
        }
        window.restoreErrorModal();
    };

    window.restoreErrorModal = function() {
        const activeErrorStr = localStorage.getItem('active_error');
        if (!activeErrorStr) return;
        
        let activeError;
        try {
            activeError = JSON.parse(activeErrorStr);
        } catch (e) {
            console.error("Failed to parse active_error", e);
            localStorage.removeItem('active_error');
            checkActiveError();
            return;
        }
        const errorModalEl = document.getElementById('error-modal');
        if (!errorModalEl) return;
        
        var errorModal = bootstrap.Modal.getInstance(errorModalEl) || new bootstrap.Modal(errorModalEl, {
            backdrop: 'static',
            keyboard: false
        });
        
        document.getElementById('errorModalLabel').innerText = activeError.title;
        document.getElementById('error-message').innerText = activeError.message;
        
        if (activeError.type === 'error') {
            const retryBtn = document.getElementById('retry-btn');
            if (retryBtn) retryBtn.style.display = "inline-block";
        } else {
            const retryBtn = document.getElementById('retry-btn');
            if (retryBtn) retryBtn.style.display = "none";
        }
        
        const continueBtn = document.getElementById('continue-btn');
        if (continueBtn) continueBtn.style.display = "inline-block";
        
        const stopBtn = document.getElementById('stop-btn');
        if (stopBtn) stopBtn.style.display = "inline-block";
        
        errorModal.show();
    };

    window.clearActiveError = function() {
        localStorage.removeItem('active_error');
        checkActiveError();
        
        const errorModalEl = document.getElementById('error-modal');
        if (errorModalEl) {
            var errorModal = bootstrap.Modal.getInstance(errorModalEl);
            if (errorModal) {
                errorModal.hide();
            }
        }
    };

    window.clearActiveInput = function() {
        localStorage.removeItem('active_input');
        checkActiveError();
        
        const inputModalEl = document.getElementById('inputModal');
        if (inputModalEl) {
            var inputModal = bootstrap.Modal.getInstance(inputModalEl);
            if (inputModal) {
                inputModal.hide();
            }
        }
    };

    checkActiveError();

    const errorModalEl = document.getElementById('error-modal');
    if (errorModalEl) {
        errorModalEl.addEventListener('hidden.bs.modal', function () {
            checkActiveError();
        });
    }

    socket.on('connect', function () {
        console.log('Connected');
    });

    socket.on('server_boot_id', function (data) {
        let lastBootId = localStorage.getItem('server_boot_id');
        if (lastBootId && lastBootId !== data.boot_id) {
            console.log("Server restart detected. Clearing old errors and inputs.");
            if (typeof window.clearActiveError === "function") {
                window.clearActiveError();
            }
            if (typeof window.clearActiveInput === "function") {
                window.clearActiveInput();
            }
        }
        localStorage.setItem('server_boot_id', data.boot_id);
    });

    socket.on('busy_status', function(data) {
        window.platformState.is_running = data.is_running;
        if (data.paused !== undefined) {
            window.platformState.is_paused = data.paused;
        }
        updateGlobalStatus();
    });

    // ---- Where the run is ----
    // Every move of the run arrives as one `progress` event holding the whole picture
    // (ivoryos/runtime/run_progress.py), and a page that connects, reconnects or is reloaded
    // mid-run is sent the same picture at once. The percentage is worked out here.

    var PHASE_NAMES = { prep: 'Prep', script: 'Experiment', cleanup: 'Clean up' };

    // The step running now out of every step in the run, plus one: the first step already
    // shows progress, and only the end of the run fills the bar. Each phase counts as its steps,
    // the experiment phase once per iteration, so the bar moves through prep and cleanup too,
    // and follows a config table that grows or shrinks while it runs.
    function runPercent(p) {
        var steps = p.steps || {};
        var prep = steps.prep || 0, main = steps.script || 0, cleanup = steps.cleanup || 0;
        var iterations = p.iterations || 0;
        var total = prep + main * iterations + cleanup;
        if (!total) return 0;
        var step = p.step || 0;
        var position = 0;
        if (p.phase === 'prep') position = step;
        else if (p.phase === 'script') position = prep + main * Math.max((p.iteration || 1) - 1, 0) + step;
        else if (p.phase === 'cleanup') position = prep + main * iterations + step;
        return Math.min(100, 100 * position / (total + 1));
    }
    window.runPercent = runPercent;

    // Where the run is, kept short: the action list already marks the step running.
    function runLabel(p) {
        if (!p || p.state === 'idle') return 'Currently not running any tasks';
        if (p.state === 'done') return 'Finished: ' + p.run_name;
        if (p.state === 'stopped') return 'Stopped: ' + p.run_name;
        if (p.state === 'failed') return 'Ended with an error: ' + p.run_name;
        if (p.phase === 'script' && p.iterations) return 'Iteration: ' + p.iteration + '/' + p.iterations;
        return PHASE_NAMES[p.phase] || 'Starting…';
    }

    socket.on('progress', function (p) {
        window.runProgress = p;

        // this script runs on every page, but only the execution page shows progress
        var iterationDisplay = document.getElementById('iteration-display');
        if (iterationDisplay) {
            iterationDisplay.innerText = runLabel(p);
            // a batch only runs in the experiment phase; prep and cleanup run once
            if (p.state !== 'running' || p.phase !== 'script') {
                var batchDisplay = document.getElementById('batch-display');
                if (batchDisplay) batchDisplay.innerText = '';
            }
        }

        var progressBar = getProgressBar();
        if (!progressBar) return;
        // a run that stopped or failed stays where it got to
        var percent = p.state === 'done' ? 100 : p.state === 'idle' ? 0 : runPercent(p);
        progressBar.style.width = percent + '%';
        progressBar.setAttribute('aria-valuenow', Math.round(percent));
        if (p.state === 'running') {
            // the pause and error handlers keep their own colours while it runs
            setProgressBarClasses(['progress-bar-animated'], ['bg-success']);
            return;
        }
        progressBar.classList.remove('progress-bar-animated');
        clearStepHighlights();
        if (p.state === 'done') setProgressBarClasses(['bg-success'], ['bg-danger', 'bg-warning']);
        else if (p.state === 'stopped') setProgressBarClasses(['bg-warning'], ['bg-success', 'bg-danger']);
        else if (p.state === 'failed') setProgressBarClasses(['bg-danger'], ['bg-success', 'bg-warning']);
    });

    socket.on('error', function (errorData) {
        console.error("Error received:", errorData);
        retryInFlight = false;

        setProgressBarClasses(['bg-danger'], ['bg-success', 'bg-warning']);

        localStorage.setItem('active_error', JSON.stringify({
            type: 'error',
            title: "Error Detected",
            message: "An error occurred: " + errorData.message
        }));

        if (errorModalEl) {
            var errorModal = bootstrap.Modal.getInstance(errorModalEl) || new bootstrap.Modal(errorModalEl, {
                backdrop: 'static',
                keyboard: false
            });
            document.getElementById('errorModalLabel').innerText = "Error Detected";
            document.getElementById('error-message').innerText = "An error occurred: " + errorData.message;

            const retryBtn = document.getElementById('retry-btn');
            if (retryBtn) retryBtn.style.display = "inline-block";
            const continueBtn = document.getElementById('continue-btn');
            if (continueBtn) continueBtn.style.display = "inline-block";
            const stopBtn = document.getElementById('stop-btn');
            if (stopBtn) stopBtn.style.display = "inline-block";

            errorModal.show();
        }
    });

    socket.on('human_intervention', function (data) {
        console.warn("Human intervention required:", data);

        // Set progress bar to yellow
        setProgressBarClasses(['bg-warning'], ['bg-success', 'bg-danger']);

        localStorage.setItem('active_error', JSON.stringify({
            type: 'human_intervention',
            title: "Human Intervention Required",
            message: "Workflow paused: " + (data.message || "Please check and manually resume.")
        }));

        if (errorModalEl) {
            var errorModal = bootstrap.Modal.getInstance(errorModalEl) || new bootstrap.Modal(errorModalEl, {
                backdrop: 'static',
                keyboard: false
            });
            document.getElementById('errorModalLabel').innerText = "Human Intervention Required";
            document.getElementById('error-message').innerText = "Workflow paused: " + (data.message || "Please check and manually resume.");

            const retryBtn = document.getElementById('retry-btn');
            if (retryBtn) retryBtn.style.display = "none";
            const continueBtn = document.getElementById('continue-btn');
            if (continueBtn) continueBtn.style.display = "inline-block";
            const stopBtn = document.getElementById('stop-btn');
            if (stopBtn) stopBtn.style.display = "inline-block";

            errorModal.show();
        }
    });

    socket.on('error_resolved', function () {
        retryInFlight = false;
        window.clearActiveError();
    });

    const pauseBtn = document.getElementById('pause-resume');
    if (pauseBtn) {
        pauseBtn.addEventListener('click', function () {
            socket.emit('pause');
            console.log('Pause/Resume action requested.');
        });
    }

    socket.on('pause_status', function (data) {
        window.platformState.is_paused = data.paused;
        updateGlobalStatus();

        if (pauseBtn) {
            var icon = pauseBtn.querySelector("i");
            if (data.paused) {
                icon.classList.remove("bi-pause-circle");
                icon.classList.add("bi-play-circle");
                pauseBtn.innerHTML = '<i class="bi bi-play-circle"></i>';
                pauseBtn.setAttribute("title", "Resume execution");
            } else {
                icon.classList.remove("bi-play-circle");
                icon.classList.add("bi-pause-circle");
                pauseBtn.innerHTML = '<i class="bi bi-pause-circle"></i>';
                pauseBtn.setAttribute("title", "Pause execution");
            }
        }
        
        // If the platform resumed (not paused anymore), clear any active human intervention error modals
        if (!data.paused) {
            if (!retryInFlight && typeof window.clearActiveError === "function") {
                window.clearActiveError();
            }
        }
    });

    const continueBtn = document.getElementById('continue-btn');
    if (continueBtn) {
        continueBtn.addEventListener('click', function () {
            window.clearActiveError();
            
            // Delay emitting slightly to allow the modal's hide animation to finish
            // This prevents a race condition if the next step fails instantly
            setTimeout(function() {
                socket.emit('pause');
                console.log("Execution resumed.");
                setProgressBarClasses(['bg-primary'], ['bg-danger', 'bg-warning']);
            }, 350);
        });
    }

    const retryBtn = document.getElementById('retry-btn');
    if (retryBtn) {
        retryBtn.addEventListener('click', function () {
            window.clearActiveError();
            retryInFlight = true;
            // Delay emitting the retry just slightly to allow the modal's hide animation to finish
            // This prevents a race condition if the step fails instantly and tries to show the modal again
            setTimeout(function() {
                socket.emit('retry');
                console.log("Execution resumed, retrying.");
            }, 350);
        });
    }

    const stopBtn = document.getElementById('stop-btn');
    if (stopBtn) {
        stopBtn.addEventListener('click', function () {
            window.clearActiveError();
            if (typeof window.clearActiveInput === 'function') window.clearActiveInput();
            socket.emit('abort_current', { continue_queue: false });
            console.log("Execution stopped.");
            
            // const modalEl = document.getElementById('stopWorkflowModal');
            // const continueQueueEl = document.getElementById('continueQueueCheckbox');

            // if (modalEl && typeof bootstrap !== 'undefined') {
            //     if (continueQueueEl) continueQueueEl.checked = false;
            //     const modal = new bootstrap.Modal(modalEl);
            //     modal.show();
            // } else {
            //     socket.emit('abort_current', { continue_queue: false });
            //     console.log("Execution stopped.");
            // }
        });
    }

    socket.on('log', function (data) {
        var logMessage = data.message;
        console.log(logMessage);
        var logPanel = $('#logging-panel');
        if (logPanel.length) {
            logPanel.append(logMessage + "<br>");
            logPanel.scrollTop(logPanel[0].scrollHeight);
        }
    });

    // Something the user should know that does not stop the run, such as config
    // rows that cannot run. Notices that arrive while one is open are added to it.
    socket.on('notice', function (data) {
        const modalEl = document.getElementById('flashModal');
        if (!modalEl) return;
        const body = document.getElementById('flashModalBody');
        const title = document.getElementById('flashModalLabel');
        const open = modalEl.classList.contains('show');
        const entry = document.createElement('div');
        entry.style.whiteSpace = 'pre-line';
        entry.textContent = data.message;
        if (open) {
            entry.classList.add('mt-3', 'pt-3', 'border-top');
            body.appendChild(entry);
        } else {
            body.replaceChildren(entry);
            title.innerText = data.title || 'Notification';
            bootstrap.Modal.getOrCreateInstance(modalEl).show();
        }
    });

    const abortPendingBtn = document.getElementById('abort-pending');
    if (abortPendingBtn) {
        abortPendingBtn.addEventListener('click', function () {
            var modal = new bootstrap.Modal(document.getElementById('abortPendingModal'));
            modal.show();
        });
    }

    const abortPendingConfirm = document.getElementById('abortPendingConfirm');
    if (abortPendingConfirm) {
        abortPendingConfirm.addEventListener('click', function () {
            const cleanupEl = document.getElementById('cleanup-checkbox');
            const doCleanup = cleanupEl ? cleanupEl.checked : false;
            
            const continueQueueEl = document.getElementById('continueQueuePendingCheckbox');
            const continueQueue = continueQueueEl ? continueQueueEl.checked : false;
            socket.emit('abort_pending', { cleanup: doCleanup, continue_queue: continueQueue });
            console.log("Abort pending sent. Cleanup:", doCleanup, "Continue queue:", continueQueue);

            var modalEl = document.getElementById('abortPendingModal');
            if (modalEl) {
                var modal = bootstrap.Modal.getInstance(modalEl);
                if (modal) modal.hide();
            }
        });
    }

    const abortCurrentBtn = document.getElementById('abort-current');
    if (abortCurrentBtn) {
        abortCurrentBtn.addEventListener('click', function () {
            const modalEl = document.getElementById('stopWorkflowModal');
            const continueQueueEl = document.getElementById('continueQueueCheckbox');
            const cleanupEl = document.getElementById('stopCleanupCheckbox');

            if (modalEl && typeof bootstrap !== 'undefined') {
                if (continueQueueEl) continueQueueEl.checked = false;
                if (cleanupEl) cleanupEl.checked = false;
                const modal = new bootstrap.Modal(modalEl);
                modal.show();
            } else {
                var confirmation = confirm("Are you sure you want to stop after this step?");
                if (confirmation) {
                    if (typeof window.clearActiveInput === 'function') window.clearActiveInput();
                    // if (typeof window.clearActiveError === 'function') window.clearActiveError();
                    socket.emit('abort_current', { continue_queue: true });
                    console.log('Stop action sent to server.');
                }
            }
        });
    }

    const stopWorkflowConfirmBtn = document.getElementById('stopWorkflowConfirmBtn');
    if (stopWorkflowConfirmBtn) {
        stopWorkflowConfirmBtn.addEventListener('click', function() {
            const continueQueueEl = document.getElementById('continueQueueCheckbox');
            const continueQueue = continueQueueEl ? continueQueueEl.checked : false;
            const cleanupEl = document.getElementById('stopCleanupCheckbox');
            const doCleanup = cleanupEl ? cleanupEl.checked : false;
            const modalEl = document.getElementById('stopWorkflowModal');
            if (modalEl) {
                const modal = bootstrap.Modal.getInstance(modalEl);
                if (modal) modal.hide();
            }
            if (typeof window.clearActiveInput === 'function') window.clearActiveInput();
            socket.emit('abort_current', { continue_queue: continueQueue, cleanup: doCleanup });
            console.log('Stop action sent to server. Continue queue:', continueQueue, 'Cleanup:', doCleanup);
        });
    }

    socket.on('execution', function (data) {
        // Remove highlighting from all lines
        clearStepHighlights();

        // Highlight current step and all parent workflows
        let currentId = data.section;
        while (currentId.includes('-')) {
            let executingLine = document.getElementById(currentId);
            if (executingLine) {
                executingLine.classList.add('executing-step');
            }
            // Move up to parent ID (e.g., script-1-2 -> script-1)
            let lastIndex = currentId.lastIndexOf('-');
            if (lastIndex === -1) break;
            currentId = currentId.substring(0, lastIndex);
        }
    });

    socket.on('start_task', function (data) {
        console.log("New task started:", data.run_name);

        // Reset progress bar, on the pages that have one
        var progressBar = document.getElementById('progress-bar-inner');
        if (progressBar) {
            progressBar.style.width = '0%';
            // progressBar.textContent = 'Starting...';
            progressBar.classList.remove('bg-success', 'bg-danger', 'bg-warning');
            progressBar.classList.add('progress-bar-animated', 'bg-primary');
        }

        clearStepHighlights();

        // Update progress panel with the new script
        if (data.progress_panel_html) {
            const currentCodePanel = document.getElementById('code-panel');
            if (currentCodePanel) {
                const parser = new DOMParser();
                const doc = parser.parseFromString(data.progress_panel_html, 'text/html');
                const newCodePanel = doc.getElementById('code-panel');
                if (newCodePanel) {
                    currentCodePanel.innerHTML = newCodePanel.innerHTML;
                } else {
                    // fallback if the template doesn't have the id wrapper (e.g. just children)
                    currentCodePanel.innerHTML = data.progress_panel_html;
                }
                if (typeof hljs !== 'undefined') hljs.highlightAll();
            }
        }
        
        var batchDisplay = document.getElementById('batch-display');
        if (batchDisplay) {
            if (data.batch_size && data.batch_size > 1) {
                window.currentBatchSize = data.batch_size;
                batchDisplay.innerText = ` | Batch: ${data.batch_size}`;
            } else {
                window.currentBatchSize = 1;
                batchDisplay.innerText = '';
            }
        }
    });

    // the sample's place in its batch: only the experiment phase runs in batches
    socket.on('batch_progress', function (data) {
        var batchDisplay = document.getElementById('batch-display');
        if (window.runProgress && window.runProgress.phase !== 'script') return;
        if (batchDisplay && window.currentBatchSize > 1) {
            if (data.shared) {
                batchDisplay.innerText = ` | Batch: -/${data.batch_total}`;
            } else if (data.batch_total) {
                batchDisplay.innerText = ` | Batch: ${data.batch_index}/${data.batch_total}`;
            }
        }
    });

    window.showInputModal = function(data) {
        console.log("Request input:", data);
        localStorage.setItem('active_input', JSON.stringify(data));
        checkActiveError();

        var inputModalEl = document.getElementById('inputModal');
        if (!inputModalEl) return;
        var inputModal = bootstrap.Modal.getInstance(inputModalEl) || new bootstrap.Modal(inputModalEl);
        
        var promptEl = document.getElementById('input-prompt');
        if (promptEl) promptEl.innerText = data.prompt;

        var container = document.getElementById('input-container');
        if (container) {
            container.innerHTML = '';

            var inputField;
            if (data.type === 'bool') {
                inputField = document.createElement('div');
                inputField.className = 'form-check';
                inputField.innerHTML = `
                    <input class="form-check-input" type="checkbox" id="user-input-value">
                    <label class="form-check-label" for="user-input-value">Check for True</label>
                 `;
            } else {
                inputField = document.createElement('input');
                inputField.className = 'form-control';
                inputField.id = 'user-input-value';
                if (data.type === 'int' || data.type === 'float') {
                    inputField.type = 'number';
                    if (data.type === 'float') inputField.step = 'any';
                } else {
                    inputField.type = 'text';
                }
            }
            container.appendChild(inputField);
        }

        inputModal.show();

        const submitBtn = document.getElementById('submit-input-btn');
        if (submitBtn) {
            submitBtn.onclick = function () {
                var val;
                var inputEl = document.getElementById('user-input-value');
                if (inputEl) {
                    if (data.type === 'bool') {
                        val = inputEl.checked;
                    } else {
                        val = inputEl.value;
                        if (data.type === 'int') val = parseInt(val);
                        if (data.type === 'float') val = parseFloat(val);
                    }
                    socket.emit('submit_input', { value: val });
                }
                localStorage.removeItem('active_input');
                checkActiveError();
                inputModal.hide();
            };
        }
    };

    socket.on('request_input', function (data) {
        window.showInputModal(data);
    });
    
    const inputModalEl2 = document.getElementById('inputModal');
    if (inputModalEl2) {
        inputModalEl2.addEventListener('hidden.bs.modal', function () {
            checkActiveError();
        });
    }
});
