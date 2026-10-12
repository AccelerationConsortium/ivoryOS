import os
import uuid
from flask import current_app
from flask_socketio import SocketIO, emit
from ivoryos.runtime import run_events
from ivoryos.runtime.script_runner import ScriptRunner

SERVER_BOOT_ID = str(uuid.uuid4())

socketio = SocketIO(cors_allowed_origins="*")
runner = ScriptRunner()
runner.socketio = socketio

def abort_pending(continue_queue=True):
    runner.abort_pending(continue_queue)
    runner.record_event(run_events.STOP_AFTER_ITERATION)
    socketio.emit('log', {'message': f"aborted pending iterations, move on to cleanup. continue_queue={continue_queue}"})

def abort_cleanup():
    runner.abort_cleanup()
    runner.record_event(run_events.CLEANUP_SKIPPED)
    socketio.emit('log', {'message': "aborted cleanup"})


def abort_current(continue_queue=True, cleanup=False):
    runner.stop_execution(continue_queue, cleanup=cleanup)
    runner.record_event(run_events.STOP_NOW, "Cleanup will run." if cleanup else "Cleanup skipped.")
    socketio.emit('log', {'message': f"stopped next task. continue_queue={continue_queue}, cleanup={cleanup}"})

def pause():
    runner.retry = False
    msg = runner.toggle_pause()
    runner.record_event(run_events.PAUSED if msg == "Paused" else run_events.RESUMED)
    socketio.emit('log', {'message': msg})
    return msg

def retry():
    runner.retry = True
    msg = runner.toggle_pause()
    runner.record_event(run_events.RETRIED)
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
    cleanup = data.get('cleanup', False)
    abort_current(continue_queue, cleanup)

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
    
    # the last lines of the log, to this page only: every other open page already shows
    # them, and would append them again
    filename = os.path.join(current_app.config["OUTPUT_FOLDER"], current_app.config["LOGGERS_PATH"])
    with open(filename, 'r') as log_file:
        log_history = log_file.readlines()
    for message in log_history[-10:]:
        emit('log', {'message': message})

    # where the run is, to this page only: a page that connects, reconnects or is reloaded
    # mid-run is shown what one that watched from the start shows (see run_progress)
    emit('progress', runner.progress.snapshot())
    if runner.progress.state == "running" and runner.last_execution_section:
        emit('execution', {'section': runner.last_execution_section}) 