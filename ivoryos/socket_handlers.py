import os
from flask import current_app
from flask_socketio import SocketIO
from ivoryos.utils.script_runner import ScriptRunner

socketio = SocketIO(cors_allowed_origins="*")
runner = ScriptRunner()

def abort_pending():
    runner.abort_pending()
    socketio.emit('log', {'message': "aborted pending iterations, move on to cleanup"})

def abort_cleanup():
    runner.abort_cleanup()
    socketio.emit('log', {'message': "aborted cleanup"})


def abort_current():
    runner.stop_execution()
    socketio.emit('log', {'message': "stopped next task"})

def pause():
    runner.retry = False
    msg = runner.toggle_pause()
    socketio.emit('log', {'message': msg})
    return msg

def retry():
    runner.retry = True
    msg = runner.toggle_pause()
    socketio.emit('log', {'message': msg})

# Socket.IO Event Handlers
@socketio.on('abort_pending')
def handle_abort_pending(data):
    cleanup = data.get("cleanup", True)
    abort_pending()
    if not cleanup:
        abort_cleanup()


@socketio.on('abort_current')
def handle_abort_current():
    abort_current()

@socketio.on('pause')
def handle_pause():
    pause()

@socketio.on('retry')
def handle_retry():
    retry()

@socketio.on('submit_input')
def handle_input_submission(data):
    value = data.get('value')
    runner.handle_input_submission(value)
    socketio.emit('log', {'message': f"User input received: {value}"})

@socketio.on('connect')
def handle_connect():
    # Fetch log messages from local file
    filename = os.path.join(current_app.config["OUTPUT_FOLDER"], current_app.config["LOGGERS_PATH"])
    with open(filename, 'r') as log_file:
        log_history = log_file.readlines()
    for message in log_history[-10:]:
        socketio.emit('log', {'message': message})

    # Emit last known progress and last known execution section
    if 0 < runner.last_progress < 100:
        socketio.emit('progress', {'progress': runner.last_progress})
        if runner.last_execution_section:
            socketio.emit('execution', {'section': runner.last_execution_section}) 