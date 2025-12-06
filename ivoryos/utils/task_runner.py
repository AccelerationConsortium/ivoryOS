import inspect
import asyncio
import threading
import time
from datetime import datetime

from ivoryos.utils import utils
from ivoryos.utils.decorators import BUILDING_BLOCKS
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

    async def run_single_step(self, component, method, kwargs, wait=True, current_app=None):
        global deck
        if deck is None:
            deck = global_config.deck

        # Try to acquire lock without blocking
        if not self.lock.acquire(blocking=False):
            current_status = global_config.runner_status
            current_status["status"] = "busy"
            current_status["output"] = "busy"
            return current_status

        if wait:
            output = await self._run_single_step(component, method, kwargs, current_app)
        else:
            # Create background task properly
            async def background_runner():
                await self._run_single_step(component, method, kwargs, current_app)

            asyncio.create_task(background_runner())
            await asyncio.sleep(0.1)  # Change time.sleep to await asyncio.sleep
            output = {"status": "task started", "task_id": global_config.runner_status.get("id")}

        return output

    def _get_executable(self, component, deck, method):
        if component.startswith("deck."):
            component = component.split(".")[1]
            instrument = getattr(deck, component)
            function_executable = getattr(instrument, method)
        elif component.startswith("blocks."):
            component = component.split(".")[1]
            function_executable = BUILDING_BLOCKS[component][method]["func"]
        else:
            temp_connections = global_config.defined_variables
            instrument = temp_connections.get(component)
            function_executable = getattr(instrument, method)
        return function_executable

    async def _run_single_step(self, component, method, kwargs, current_app=None):
        try:
            function_executable = self._get_executable(component, deck, method)
            method_name = f"{component}.{method}"
        except Exception as e:
            self.lock.release()
            return {"status": "error", "msg": str(e)}

        # Flask context is NOT async → just use normal "with"
        with current_app.app_context():
            step = SingleStep(
                method_name=method_name,
                kwargs=kwargs,
                run_error=None,
                start_time=datetime.now()
            )
            db.session.add(step)
            db.session.flush()
            global_config.runner_status = {"id": step.id, "type": "task"}

            try:
                kwargs = self._convert_kwargs_type(kwargs, function_executable)

                if inspect.iscoroutinefunction(function_executable):
                    output = await function_executable(**kwargs)
                else:
                    output = function_executable(**kwargs)
                output = utils.safe_dump(output)
                step.output = output
                step.end_time = datetime.now()
                success = True
            except Exception as e:
                step.run_error = str(e)
                step.end_time = datetime.now()
                success = False
                output = str(e)
            finally:
                db.session.commit()
                self.lock.release()

            return dict(success=success, output=output)

    @staticmethod
    def _convert_kwargs_type(kwargs, function_executable):
        def convert_guess(str_value):
            str_value = str_value.strip()
            if str_value.isdigit() or (str_value.startswith('-') and str_value[1:].isdigit()):
                return int(str_value)
            try:
                return float(str_value)
            except ValueError:
                return str_value

        sig = inspect.signature(function_executable)
        converted = {}

        for name, value in kwargs.items():
            if name in sig.parameters:
                param = sig.parameters[name]
                if param.annotation != inspect.Parameter.empty:
                    # convert using type hint
                    try:
                        converted[name] = param.annotation(value)
                    except Exception:
                        converted[name] = value
                else:
                    # no type hint → guess
                    converted[name] = convert_guess(value)
        return converted
