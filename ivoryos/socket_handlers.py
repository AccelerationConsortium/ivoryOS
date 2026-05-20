import os
import uuid
from flask import current_app
from flask_socketio import SocketIO
from ivoryos.runtime.script_runner import ScriptRunner

SERVER_BOOT_ID = str(uuid.uuid4())

socketio = SocketIO(cors_allowed_origins="*")
runner = ScriptRunner()
runner.socketio = socketio

def abort_pending(continue_queue=True):
    runner.abort_pending(continue_queue)
    socketio.emit('log', {'message': f"aborted pending iterations, move on to cleanup. continue_queue={continue_queue}"})

def abort_cleanup():
    runner.abort_cleanup()
    socketio.emit('log', {'message': "aborted cleanup"})


def abort_current(continue_queue=True):
    runner.stop_execution(continue_queue)
    socketio.emit('log', {'message': f"stopped next task. continue_queue={continue_queue}"})

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
def handle_abort_pending(data=None):
    if data is None:
        data = {}
    cleanup = data.get("cleanup", True)
    continue_queue = data.get("continue_queue", True)
    abort_pending(continue_queue)
    if not cleanup:
        abort_cleanup()


@socketio.on('abort_current')
def handle_abort_current(data=None):
    if data is None:
        data = {}
    continue_queue = data.get('continue_queue', True)
    abort_current(continue_queue)

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
    socketio.emit('server_boot_id', {'boot_id': SERVER_BOOT_ID})
    runner._emit_busy_status()
    runner._emit_queue_status()
    socketio.emit('pause_status', {'paused': runner.paused or runner.queue_paused})
    
    # Fetch log messages from local file
    filename = os.path.join(current_app.config["OUTPUT_FOLDER"], current_app.config["LOGGERS_PATH"])
    with open(filename, 'r') as log_file:
        log_history = log_file.readlines()
    for message in log_history[-10:]:
        socketio.emit('log', {'message': message})

    # Emit last known progress and last known execution section
    if 0 < runner.last_progress < 100:
        payload = {'progress': runner.last_progress}
        if getattr(runner, 'last_iteration', None) is not None:
            payload['iteration'] = runner.last_iteration
        if getattr(runner, 'last_total', None) is not None:
            payload['total'] = runner.last_total
        socketio.emit('progress', payload)
        
        if runner.last_execution_section:
            socketio.emit('execution', {'section': runner.last_execution_section}) 