import threading
import time
from datetime import datetime

from ivoryos.utils.db_models import db, SingleStep
from ivoryos.utils.global_config import GlobalConfig

global_config = GlobalConfig()
global deck
deck = None


class TaskRunner:
    def __init__(self, globals_dict=None):
        self.retry = False
        if globals_dict is None:
            globals_dict = globals()
        self.globals_dict = globals_dict
        self.lock = global_config.runner_lock


    def run_single_step(self, component, method, kwargs, wait=True, current_app=None):
        global deck
        if deck is None:
            deck = global_config.deck

        # Try to acquire lock without blocking
        if not self.lock.acquire(blocking=False):
            current_status = global_config.runner_status
            current_status["status"] = "busy"
            return current_status
        component = component.split(".")[1] if component.startswith("deck.") else component
        instrument = getattr(deck, component)
        function_executable = getattr(instrument, method)

        if wait:
            try:
                output = function_executable(**kwargs)
            except Exception as e:
                output = str(e)
            finally:
                self.lock.release()
        else:
            print("running with thread")
            thread = threading.Thread(
                target=self._run_single_step, args=(function_executable, kwargs, current_app)
            )
            thread.start()
            time.sleep(0.1)
            output = {"status": "task started", "task_id": global_config.runner_status.get("id")}

        return output

    def _run_single_step(self, function, kwargs, current_app=None):
        method_name = f"{function.__self__.__class__.__name__}.{function.__name__}"

        # with self.lock:
        with current_app.app_context():
            step = SingleStep(method_name=method_name, kwargs=kwargs, run_error=False, start_time=datetime.now())
            db.session.add(step)
            db.session.commit()
            global_config.runner_status = {"id":step.id, "type": "task"}
            try:
                output = function(**kwargs)
                step.output = output
                step.end_time = datetime.now()
            except Exception as e:
                step.run_error = e.__str__()
                step.end_time = datetime.now()
            db.session.commit()
        self.lock.release()