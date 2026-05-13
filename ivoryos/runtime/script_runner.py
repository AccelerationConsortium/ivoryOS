import threading

from ivoryos.runtime.runner_runtime import global_state
from ivoryos.runtime.script_runner_queue import ScriptRunnerQueueMixin
from ivoryos.runtime.script_runner_steps import ScriptRunnerStepMixin
from ivoryos.runtime.script_runner_workflow import ScriptRunnerWorkflowMixin


class ScriptRunner(ScriptRunnerQueueMixin, ScriptRunnerWorkflowMixin, ScriptRunnerStepMixin):
    def __init__(self, globals_dict=None):
        self.logger = None
        self.socketio = None
        self.retry = False
        if globals_dict is None:
            globals_dict = globals()
        self.globals_dict = globals_dict
        self.execution_queue = []  # List to hold pending tasks
        self.pause_event = threading.Event()  # A threading event to manage pause/resume
        self.pause_event.set()
        self.stop_pending_event = threading.Event()
        self.stop_current_event = threading.Event()
        self.stop_cleanup_event = threading.Event()
        self.is_running = False
        self.lock = global_state.runner_lock
        self.paused = False
        self.queue_paused = False
        self.current_app = None
        self.last_progress = 0
        self.last_iteration = None
        self.last_total = None
        self.last_execution_section = None
        self.waiting_for_input = False
        self.input_value = None
        self.current_task = None

