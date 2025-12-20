document.addEventListener("DOMContentLoaded", function () {
    var socket = io();
    socket.on('connect', function () {
        console.log('Connected');
    });
    socket.on('progress', function (data) {
        var progress = data.progress;
        console.log(progress);
        // Update the progress bar's width and appearance
        var progressBar = document.getElementById('progress-bar-inner');
        progressBar.style.width = progress + '%';
        progressBar.setAttribute('aria-valuenow', progress);
        const runPanel = document.getElementById("run-panel");
        const codePanel = document.getElementById("code-panel");
        if (progress === 1) {
            progressBar.classList.remove('bg-success');
            progressBar.classList.remove('bg-danger');
            progressBar.classList.add('progress-bar-animated');
        }
        if (progress === 100) {
            // Remove animation and set green color when 100% is reached
            progressBar.classList.remove('progress-bar-animated');
            progressBar.classList.add('bg-success'); // Bootstrap class for green color

            // Clear all execution highlights
            document.querySelectorAll('pre code').forEach(el => el.style.backgroundColor = '');

            // Reset config container height if it exists
            const configContainer = document.getElementById('config-container');
            if (configContainer) {
                configContainer.style.height = '70vh';
                // console.log(configContainer.style.height);
            }
            // Reset flag so it can resize again next run
            hasAutoResized = false;
        }
    });

    socket.on('error', function (errorData) {
        console.error("Error received:", errorData);
        var progressBar = document.getElementById('progress-bar-inner');

        progressBar.classList.remove('bg-success', 'bg-warning');
        progressBar.classList.add('bg-danger');

        var errorModal = new bootstrap.Modal(document.getElementById('error-modal'));
        document.getElementById('errorModalLabel').innerText = "Error Detected";
        document.getElementById('error-message').innerText =
            "An error occurred: " + errorData.message;

        // Show all buttons again
        document.getElementById('retry-btn').style.display = "inline-block";
        document.getElementById('continue-btn').style.display = "inline-block";
        document.getElementById('stop-btn').style.display = "inline-block";

        errorModal.show();
    });


    socket.on('human_intervention', function (data) {
        console.warn("Human intervention required:", data);
        var progressBar = document.getElementById('progress-bar-inner');

        // Set progress bar to yellow
        progressBar.classList.remove('bg-success', 'bg-danger');
        progressBar.classList.add('bg-warning');

        // Reuse error modal but update content
        var errorModal = new bootstrap.Modal(document.getElementById('error-modal'));
        document.getElementById('errorModalLabel').innerText = "Human Intervention Required";
        document.getElementById('error-message').innerText =
            "Workflow paused: " + (data.message || "Please check and manually resume.");

        // Optionally: hide retry button, since it may not apply
        document.getElementById('retry-btn').style.display = "none";
        document.getElementById('continue-btn').style.display = "inline-block";
        document.getElementById('stop-btn').style.display = "inline-block";

        errorModal.show();
    });

    // Handle Pause/Resume Button
    document.getElementById('pause-resume').addEventListener('click', function () {
        socket.emit('pause');
        console.log('Pause/Resume is toggled.');
        var button = this;
        var icon = button.querySelector("i");

        // Toggle Pause and Resume
        if (icon.classList.contains("bi-pause-circle")) {
            icon.classList.remove("bi-pause-circle");
            icon.classList.add("bi-play-circle");
            button.innerHTML = '<i class="bi bi-play-circle"></i>';
            button.setAttribute("title", "Resume execution");
        } else {
            icon.classList.remove("bi-play-circle");
            icon.classList.add("bi-pause-circle");
            button.innerHTML = '<i class="bi bi-pause-circle"></i>';
            button.setAttribute("title", "Pause execution");
        }
    });

    // Handle Modal Buttons
    document.getElementById('continue-btn').addEventListener('click', function () {
        socket.emit('pause');  // Resume execution
        console.log("Execution resumed.");

        // Reset progress bar color to running (blue)
        var progressBar = document.getElementById('progress-bar-inner');
        progressBar.classList.remove('bg-danger', 'bg-warning');
        progressBar.classList.add('bg-primary');
    });

    document.getElementById('retry-btn').addEventListener('click', function () {
        socket.emit('retry');  // Resume execution
        console.log("Execution resumed, retrying.");
    });

    document.getElementById('stop-btn').addEventListener('click', function () {
        socket.emit('pause');  // Resume execution
        socket.emit('abort_current');  // Stop execution
        console.log("Execution stopped.");

        console.log("Execution stopped.");
    });

    socket.on('log', function (data) {
        var logMessage = data.message;
        console.log(logMessage);
        $('#logging-panel').append(logMessage + "<br>");
        $('#logging-panel').scrollTop($('#logging-panel')[0].scrollHeight);
    });

    document.getElementById('abort-pending').addEventListener('click', function () {
        var modal = new bootstrap.Modal(document.getElementById('abortPendingModal'));
        modal.show();
    });

    // When user presses confirm
    document.getElementById('abortPendingConfirm').addEventListener('click', function () {
        const doCleanup = document.getElementById('cleanup-checkbox').checked;

        socket.emit('abort_pending', { cleanup: doCleanup });
        console.log("Abort pending sent. Cleanup:", doCleanup);

        // Close modal
        bootstrap.Modal.getInstance(document.getElementById('abortPendingModal')).hide();
    });

    document.getElementById('abort-current').addEventListener('click', function () {
        var confirmation = confirm("Are you sure you want to stop after this step?");
        if (confirmation) {
            socket.emit('abort_current');
            console.log('Stop action sent to server.');
        }
    });

    // Flag to track if we've already auto-resized the panel
    let hasAutoResized = false;

    socket.on('execution', function (data) {
        // Auto-resize logic: shrink config panel to show more logs
        if (!hasAutoResized) {
            const configContainer = document.getElementById('config-container');
            if (configContainer) {
                // Set to a smaller height (e.g., 20vh) to prioritize logs
                configContainer.style.height = '20vh';
                hasAutoResized = true;
            }
        }

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

    socket.on('request_input', function (data) {
        console.log("Request input:", data);
        var inputModal = new bootstrap.Modal(document.getElementById('inputModal'));
        document.getElementById('input-prompt').innerText = data.prompt;

        var container = document.getElementById('input-container');
        container.innerHTML = ''; // Clear previous

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

        inputModal.show();

        // Handle Submit
        document.getElementById('submit-input-btn').onclick = function () {
            var val;
            var inputEl = document.getElementById('user-input-value');
            if (data.type === 'bool') {
                val = inputEl.checked;
            } else {
                val = inputEl.value;
                if (data.type === 'int') val = parseInt(val);
                if (data.type === 'float') val = parseFloat(val);
            }
            socket.emit('submit_input', { value: val });
            inputModal.hide();
        };
    });
});
