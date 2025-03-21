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

    document.getElementById('pause-resume').addEventListener('click', function() {

        socket.emit('pause');
        console.log('Pause/Resume is toggled.');
        var button = this;
        var icon = button.querySelector("i");

        // Toggle between Pause and Resume
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
});
