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


        if wait:
            output = self._run_single_step(component, method, kwargs, current_app)
        else:
            print("running with thread")
            thread = threading.Thread(
                target=self._run_single_step, args=(component, method, kwargs, current_app)
            )
            thread.start()
            time.sleep(0.1)
            output = {"status": "task started", "task_id": global_config.runner_status.get("id")}

        return output

    def _get_executable(self, component, deck, method):
        if component.startswith("deck."):
            component = component.split(".")[1]
            instrument = getattr(deck, component)
        else:
            temp_connections = global_config.defined_variables
            instrument = temp_connections.get(component)
        function_executable = getattr(instrument, method)
        return function_executable

    def _run_single_step(self, component, method, kwargs, current_app=None):
        try:
            function_executable = self._get_executable(component, deck, method)
            method_name = f"{function_executable.__self__.__class__.__name__}.{function_executable.__name__}"
        except Exception as e:
            self.lock.release()
            return {"status": "error", "msg": e.__str__()}

        # with self.lock:
        with current_app.app_context():
            step = SingleStep(method_name=method_name, kwargs=kwargs, run_error=False, start_time=datetime.now())
            db.session.add(step)
            db.session.commit()
            global_config.runner_status = {"id":step.id, "type": "task"}
            try:
                output = function_executable(**kwargs)
                step.output = output
                step.end_time = datetime.now()
            except Exception as e:
                step.run_error = e.__str__()
                step.end_time = datetime.now()
            finally:
                db.session.commit()
                self.lock.release()
            return output