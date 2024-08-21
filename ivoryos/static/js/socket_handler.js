document.addEventListener("DOMContentLoaded", function() {
    var socket = io.connect('http://' + document.domain + ':' + location.port);
    socket.on('connect', function() {
        console.log('Connected');
    });
    socket.on('progress', function(data) {
        var progress = data.progress;
        console.log(progress);
        $('#progress-bar-inner').css('width', progress + '%')
    });
    socket.on('log', function(data) {
        var logMessage = data.message;
        console.log(logMessage);
        $('#logging-panel').append(logMessage + "<br>");
        $('#logging-panel').scrollTop($('#logging-panel')[0].scrollHeight);
    });

    document.getElementById('abort').addEventListener('click', function() {
        var confirmation = confirm("Are you sure you want to abort pending actions?");
        if (confirmation) {
            socket.emit('abort_action');
            console.log('Abort action sent to server.');
        }
    });
});
