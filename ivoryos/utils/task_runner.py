import inspect
import asyncio
import threading
import time
import ast
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
        elif component.startswith("blocks."):
            component = component.split(".")[1]
            return BUILDING_BLOCKS[component][method]["func"]
        else:
            temp_connections = global_config.defined_variables
            instrument = temp_connections.get(component)
        
        # Check for property setter convention: "<prop>_(setter)"
        if method.endswith("_(setter)"):
            prop_name = method[:-9] # remove "_(setter)"
            # Check trait on class to avoid triggering property
            if hasattr(type(instrument), prop_name):
                 attr = getattr(type(instrument), prop_name)
                 if isinstance(attr, property) and attr.fset:
                     def setter(**kwargs):
                         if len(kwargs) == 1:
                             val = next(iter(kwargs.values()))
                             setattr(instrument, prop_name, val)
                             return None
                         elif "value" in kwargs:
                             setattr(instrument, prop_name, kwargs["value"])
                             return None
                         raise ValueError(f"Setter for {prop_name} expects 1 argument")
                     
                     # Copy signature from fset but remove self
                     try:
                         sig = inspect.signature(attr.fset)
                         params = [p for n, p in sig.parameters.items() if n != 'self']
                         setter.__signature__ = sig.replace(parameters=params)
                     except Exception:
                         # Fallback if signature extraction fails
                         pass
                     
                     return setter
        
        # Check for property getter
        if hasattr(type(instrument), method):
            attr = getattr(type(instrument), method)
            if isinstance(attr, property):
                def getter(**kwargs):
                    return getattr(instrument, method)
                return getter

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
            if not isinstance(str_value, str):
                return str_value
                
            str_value = str_value.strip()
            
            # Try python evaluation first (handles ints, floats, lists, dicts, sets, tuples, booleans, None)
            try:
                return ast.literal_eval(str_value)
            except (ValueError, SyntaxError):
                pass
            
            # Fallback for unquoted strings lists: "a, b, c" -> ["a", "b", "c"]
            # We only split if it clearly looks like a list (has comma) and literal_eval failed
            if "," in str_value:
                 # Check if it might be a malformed structure vs just comma separated strings
                 # For safety, if literal_eval failed, we treat it as comma separated strings.
                 return [convert_guess(i) for i in str_value.split(",")]

            return str_value

        sig = inspect.signature(function_executable)
        converted = {}

        for name, value in kwargs.items():
            if name in sig.parameters:
                param = sig.parameters[name]
                # Check for explicit typing
                if param.annotation != inspect.Parameter.empty:
                    # If explicitly typed, we still want to try smart conversion if the value is a string
                    
                    if isinstance(value, str):
                       val = convert_guess(value)
                       
                       # Helper to check if target is a list type
                       target_type = param.annotation
                       is_list_target = target_type is list
                       if not is_list_target:
                           # Check for typing.List (e.g. List[int])
                           origin = getattr(target_type, "__origin__", None)
                           if origin is list:
                               is_list_target = True

                       # If we have a tuple (likely from "1,2,3") but want a list, cast it
                       if is_list_target and isinstance(val, tuple):
                           val = list(val)
                       
                       # Try to cast to target type if possible (e.g. valid for int, float, str, but fails for typing.List)
                       try:
                           converted[name] = target_type(val)
                       except Exception:
                           # Casting failed (common for typing generics), just use the guessed/casts val
                           converted[name] = val
                    else:
                        try:
                            converted[name] = param.annotation(value)
                        except Exception:
                            converted[name] = value
                else:
                    # no type hint → guess
                    converted[name] = convert_guess(value)
            else:
                 pass
                 
        return converted
