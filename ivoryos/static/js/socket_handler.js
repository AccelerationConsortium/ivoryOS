document.addEventListener("DOMContentLoaded", function () {
    var socket = io();
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

    function updateGlobalStatus() {
        const activeErrorStr = localStorage.getItem('active_error');
        const icon = document.getElementById('global-status-icon');
        
        if (icon) {
            icon.style.display = 'flex'; // always visible
            if (activeErrorStr) {
                icon.style.backgroundColor = '#dc3545'; // red
                icon.setAttribute('title', 'View active error');
                icon.innerHTML = '<i class="bi bi-exclamation-triangle-fill text-white fs-5"></i> <span>Error</span>';
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

    function checkActiveError() {
        const activeErrorStr = localStorage.getItem('active_error');
        const progressBar = getProgressBar();
        
        updateGlobalStatus();

        if (activeErrorStr) {
            if (progressBar) {
                try {
                    const activeError = JSON.parse(activeErrorStr);
                    progressBar.classList.remove('bg-primary', 'bg-warning', 'bg-danger');
                    if (activeError.type === 'error') {
                        progressBar.classList.add('bg-danger');
                    } else if (activeError.type === 'warning' || activeError.type === 'human_intervention') {
                        progressBar.classList.add('bg-warning');
                    }
                } catch (e) {
                    console.error("Failed to parse active_error", e);
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
        
        const icon = document.getElementById('error-restore-icon');
        if (icon) icon.style.display = 'none';
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
            console.log("Server restart detected. Clearing old errors.");
            if (typeof window.clearActiveError === "function") {
                window.clearActiveError();
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

    socket.on('progress', function (data) {
        var progress = data.progress;
        console.log(progress);
        
        if (data.iteration && data.total) {
            document.getElementById('iteration-display').innerText = `(Iteration ${data.iteration}/${data.total})`;
        } else {
            document.getElementById('iteration-display').innerText = 'Currently not running any tasks';
        }

        // Update the progress bar's width and appearance
        var progressBar = document.getElementById('progress-bar-inner');
        if (progressBar) {
            progressBar.style.width = progress + '%';
            progressBar.setAttribute('aria-valuenow', progress);
            
            if (progress === 1) {
                progressBar.classList.remove('bg-success', 'bg-danger');
                progressBar.classList.add('progress-bar-animated');
            }
            if (progress === 100) {
                progressBar.classList.remove('progress-bar-animated');
                progressBar.classList.add('bg-success');
                
                document.querySelectorAll('pre code').forEach(el => el.style.backgroundColor = '');
            }
        }
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
            socket.emit('pause');
            console.log("Execution resumed.");

            setProgressBarClasses(['bg-primary'], ['bg-danger', 'bg-warning']);
        });
    }

    const retryBtn = document.getElementById('retry-btn');
    if (retryBtn) {
        retryBtn.addEventListener('click', function () {
            retryInFlight = true;
            socket.emit('retry');
            console.log("Execution resumed, retrying.");
        });
    }

    const stopBtn = document.getElementById('stop-btn');
    if (stopBtn) {
        stopBtn.addEventListener('click', function () {
            window.clearActiveError();
            // socket.emit('pause');
            socket.emit('abort_current');
            console.log("Execution stopped.");
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

            if (modalEl && typeof bootstrap !== 'undefined') {
                if (continueQueueEl) continueQueueEl.checked = false;
                const modal = new bootstrap.Modal(modalEl);
                modal.show();
            } else {
                var confirmation = confirm("Are you sure you want to stop after this step?");
                if (confirmation) {
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
            const modalEl = document.getElementById('stopWorkflowModal');
            if (modalEl) {
                const modal = bootstrap.Modal.getInstance(modalEl);
                if (modal) modal.hide();
            }
            socket.emit('abort_current', { continue_queue: continueQueue });
            console.log('Stop action sent to server. Continue queue:', continueQueue);
        });
    }

    socket.on('execution', function (data) {
        // Remove highlighting from all lines
        document.querySelectorAll('pre code').forEach(el => el.style.backgroundColor = '');

        // Highlight current step and all parent workflows
        let currentId = data.section;
        while (currentId.includes('-')) {
            let executingLine = document.getElementById(currentId);
            if (executingLine) {
                executingLine.style.backgroundColor = '#cce5ff'; // Highlight
                executingLine.style.transition = 'background-color 0.3s ease-in-out';

            }
            // Move up to parent ID (e.g., script-1-2 -> script-1)
            let lastIndex = currentId.lastIndexOf('-');
            if (lastIndex === -1) break;
            currentId = currentId.substring(0, lastIndex);
        }
    });

    socket.on('start_task', function (data) {
        console.log("New task started:", data.run_name);

        // Reset progress bar
        var progressBar = document.getElementById('progress-bar-inner');
        progressBar.style.width = '0%';
        // progressBar.textContent = 'Starting...';
        progressBar.classList.remove('bg-success', 'bg-danger', 'bg-warning');
        progressBar.classList.add('progress-bar-animated', 'bg-primary');

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
    });

    socket.on('request_input', function (data) {
        console.log("Request input:", data);
        var inputModalEl = document.getElementById('inputModal');
        if (!inputModalEl) return;
        var inputModal = new bootstrap.Modal(inputModalEl);
        
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
                inputModal.hide();
            };
        }
    });
});
