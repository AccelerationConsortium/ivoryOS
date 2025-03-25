document.addEventListener("DOMContentLoaded", function() {
    var socket = io.connect('http://' + document.domain + ':' + location.port);
    socket.on('connect', function() {
        console.log('Connected');
    });
    socket.on('progress', function(data) {
        var progress = data.progress;
        console.log(progress);
        // Update the progress bar's width and appearance
        var progressBar = document.getElementById('progress-bar-inner');
        progressBar.style.width = progress + '%';
        progressBar.setAttribute('aria-valuenow', progress);
        if (progress === 1) {
                    document.getElementById("run-panel").style.display = "none";
        document.getElementById("code-panel").style.display = "block";

        // Optional: Scroll to the code panel
        document.getElementById("code-panel").scrollIntoView({ behavior: "smooth" });
        }
        if (progress === 100) {
            // Remove animation and set green color when 100% is reached
            progressBar.classList.remove('progress-bar-animated');
            progressBar.classList.add('bg-success'); // Bootstrap class for green color
            setTimeout(() => {
            document.getElementById("code-panel").style.display = "none";
            document.getElementById("run-panel").style.display = "block";
        }, 1000);  // Small delay to let users see the completion
        }
    });

    socket.on('error', function(errorData) {
        console.error("Error received:", errorData);
        var progressBar = document.getElementById('progress-bar-inner');

        progressBar.classList.remove('bg-success');
        progressBar.classList.add('bg-danger'); // Red color for error
                // Show error modal
        var errorModal = new bootstrap.Modal(document.getElementById('error-modal'));
        document.getElementById('error-message').innerText = "An error occurred: " + errorData.message;
        errorModal.show();

    });

    // Handle Pause/Resume Button
    document.getElementById('pause-resume').addEventListener('click', function() {
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
    document.getElementById('continue-btn').addEventListener('click', function() {
        socket.emit('pause');  // Resume execution
        console.log("Execution resumed.");
    });

    document.getElementById('stop-btn').addEventListener('click', function() {
        socket.emit('pause');  // Resume execution
        socket.emit('abort_current');  // Stop execution
        console.log("Execution stopped.");

        // Reset UI back to initial state
        document.getElementById("code-panel").style.display = "none";
        document.getElementById("run-panel").style.display = "block";
    });

    socket.on('log', function(data) {
        var logMessage = data.message;
        console.log(logMessage);
        $('#logging-panel').append(logMessage + "<br>");
        $('#logging-panel').scrollTop($('#logging-panel')[0].scrollHeight);
    });

    document.getElementById('abort-pending').addEventListener('click', function() {
        var confirmation = confirm("Are you sure you want to stop after this iteration?");
        if (confirmation) {
            socket.emit('abort_pending');
            console.log('Abort action sent to server.');
        }
    });
    document.getElementById('abort-current').addEventListener('click', function() {
        var confirmation = confirm("Are you sure you want to stop after this step?");
        if (confirmation) {
            socket.emit('abort_current');
            console.log('Stop action sent to server.');
    }
    });

    socket.on('execution', function(data) {
        // Remove highlighting from all lines
        document.querySelectorAll('pre code').forEach(el => el.style.backgroundColor = '');

        // Get the currently executing line and highlight it
        let executingLine = document.getElementById(data.section);
        if (executingLine) {
            executingLine.style.backgroundColor = '#cce5ff'; // Highlight
            executingLine.style.transition = 'background-color 0.3s ease-in-out';

        }
    });
});
