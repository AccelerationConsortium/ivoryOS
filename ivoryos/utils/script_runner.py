import ast
import os
import csv
import threading
import time
from datetime import datetime

from ivoryos.utils import utils, bo_campaign
from ivoryos.utils.db_models import Script, WorkflowRun, WorkflowStep, db, SingleStep
from ivoryos.utils.global_config import GlobalConfig

global_config = GlobalConfig()
global deck
deck = None
# global deck, registered_workflows
# deck, registered_workflows = None, None

class ScriptRunner:
    def __init__(self, globals_dict=None):
        self.retry = False
        if globals_dict is None:
            globals_dict = globals()
        self.globals_dict = globals_dict
        self.pause_event = threading.Event()  # A threading event to manage pause/resume
        self.pause_event.set()
        self.stop_pending_event = threading.Event()
        self.stop_current_event = threading.Event()
        self.is_running = False
        self.lock = global_config.runner_lock
        self.paused = False
        self.current_app = None

    def toggle_pause(self):
        """Toggles between pausing and resuming the script"""
        self.paused = not self.paused
        if self.pause_event.is_set():
            self.pause_event.clear()  # Pause the script
            return "Paused"
        else:
            self.pause_event.set()  # Resume the script
            return "Resumed"

    def pause_status(self):
        """Toggles between pausing and resuming the script"""
        return self.paused

    def reset_stop_event(self):
        """Resets the stop event"""
        self.stop_pending_event.clear()
        self.stop_current_event.clear()
        self.pause_event.set()

    def abort_pending(self):
        """Abort the pending iteration after the current is finished"""
        self.stop_pending_event.set()
        # print("Stop pending tasks")

    def stop_execution(self):
        """Force stop everything, including ongoing tasks."""
        self.stop_current_event.set()
        self.abort_pending()


    def run_script(self, script, repeat_count=1, run_name=None, logger=None, socketio=None, config=None, bo_args=None,
                   output_path="", compiled=False, current_app=None):
        global deck
        if deck is None:
            deck = global_config.deck

        if self.current_app is None:
            self.current_app = current_app
        # time.sleep(1)  # Optional: may help ensure deck readiness

        # Try to acquire lock without blocking
        if not self.lock.acquire(blocking=False):
            if logger:
                logger.info("System is busy. Please wait for it to finish or stop it before starting a new one.")
            return None

        self.reset_stop_event()

        thread = threading.Thread(
            target=self._run_with_stop_check,
            args=(script, repeat_count, run_name, logger, socketio, config, bo_args, output_path, current_app, compiled)
        )
        thread.start()
        return thread

    def exec_steps(self, script, section_name, logger, socketio, run_id, i_progress, **kwargs):
        """
        Executes a function defined in a string line by line
        :param func_str: The function as a string
        :param kwargs: Arguments to pass to the function
        :return: The final result of the function execution
        """
        _func_str = script.python_script or script.compile()
        step_list: list = script.convert_to_lines(_func_str).get(section_name, [])
        global deck
        # global deck, registered_workflows
        if deck is None:
            deck = global_config.deck
        # if registered_workflows is None:
        #     registered_workflows = global_config.registered_workflows

        # for i, line in enumerate(step_list):
        #     if line.startswith("registered_workflows"):
        #
        # func_str = script.compile()
        # Parse function body from string
        temp_connections = global_config.defined_variables
        # Prepare execution environment
        exec_globals = {"deck": deck, "time":time}  # Add required global objects
        # exec_globals = {"deck": deck, "time": time, "registered_workflows":registered_workflows}  # Add required global objects
        exec_globals.update(temp_connections)
        exec_locals = {}  # Local execution scope

        # Define function arguments manually in exec_locals
        exec_locals.update(kwargs)
        index = 0

        # Execute each line dynamically
        while index < len(step_list):
            if self.stop_current_event.is_set():
                logger.info(f'Stopping execution during {section_name}')
                step = WorkflowStep(
                    workflow_id=run_id,
                    phase=section_name,
                    repeat_index=i_progress,
                    step_index=index,
                    method_name="stop",
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    run_error=False,
                )
                db.session.add(step)
                break
            line = step_list[index]
            method_name = line.strip().split("(")[0] if "(" in line else line.strip()
            start_time = datetime.now()
            step = WorkflowStep(
                workflow_id=run_id,
                phase=section_name,
                repeat_index=i_progress,
                step_index=index,
                method_name=method_name,
                start_time=start_time,
            )
            db.session.add(step)
            db.session.commit()
            logger.info(f"Executing: {line}")
            socketio.emit('execution', {'section': f"{section_name}-{index}"})
            # self._emit_progress(socketio, 100)
            # if line.startswith("registered_workflows"):
            #     line = line.replace("registered_workflows.", "")
            try:
                if line.startswith("time.sleep("): # add safe sleep for time.sleep lines
                    duration_str = line[len("time.sleep("):-1]
                    duration = float(duration_str)
                    self.safe_sleep(duration)
                else:
                    exec(line, exec_globals, exec_locals)
                step.run_error = False
            except Exception as e:
                logger.error(f"Error during script execution: {e}")
                socketio.emit('error', {'message': str(e)})

                step.run_error = True
                self.toggle_pause()
            step.end_time = datetime.now()
            # db.session.add(step)
            db.session.commit()

            self.pause_event.wait()

            # todo update script during the run
            # _func_str = script.compile()
            # step_list: list = script.convert_to_lines(_func_str).get(section_name, [])
            if not step.run_error:
                index += 1
            elif not self.retry:
                index += 1
        return exec_locals  # Return the 'results' variable

    def _run_with_stop_check(self, script: Script, repeat_count: int, run_name: str, logger, socketio, config, bo_args,
                             output_path, current_app, compiled):
        time.sleep(1)
        # _func_str = script.compile()
        # step_list_dict: dict = script.convert_to_lines(_func_str)
        self._emit_progress(socketio, 1)

        # Run "prep" section once
        script_dict = script.script_dict
        with current_app.app_context():

            run = WorkflowRun(name=script.name or "untitled", platform=script.deck or "deck",start_time=datetime.now())
            db.session.add(run)
            db.session.commit()
            run_id = run.id  # Save the ID
            global_config.runner_status = {"id":run_id, "type": "workflow"}
            self._run_actions(script, section_name="prep", logger=logger, socketio=socketio, run_id=run_id)
            output_list = []
            _, arg_type = script.config("script")
            _, return_list = script.config_return()

            # Run "script" section multiple times
            if repeat_count:
                self._run_repeat_section(repeat_count, arg_type, bo_args, output_list, script,
                                         run_name, return_list, compiled, logger, socketio, run_id=run_id)
            elif config:
                self._run_config_section(config, arg_type, output_list, script, run_name, logger,
                                         socketio, run_id=run_id, compiled=compiled)

            # Run "cleanup" section once
            self._run_actions(script, section_name="cleanup", logger=logger, socketio=socketio,run_id=run_id)
            # Reset the running flag when done
            self.lock.release()
            # Save results if necessary
            filename = None
            if not script.python_script and output_list:
                filename = self._save_results(run_name, arg_type, return_list, output_list, logger, output_path)
            self._emit_progress(socketio, 100)
        with current_app.app_context():
            run = db.session.get(WorkflowRun, run_id)  # SQLAlchemy 1.4+ recommended method
            run.end_time = datetime.now()
            run.data_path = filename
            db.session.commit()

    def _run_actions(self, script, section_name="", logger=None, socketio=None, run_id=None):
        _func_str = script.python_script or script.compile()
        step_list: list = script.convert_to_lines(_func_str).get(section_name, [])
        logger.info(f'Executing {section_name} steps') if step_list else logger.info(f'No {section_name} steps')
        if self.stop_pending_event.is_set():
            logger.info(f"Stopping execution during {section_name} section.")
            return
        if step_list:
            self.exec_steps(script, section_name, logger, socketio, run_id=run_id, i_progress=0)

    def _run_config_section(self, config, arg_type, output_list, script, run_name, logger, socketio, run_id, compiled=True):
        if not compiled:
            for i in config:
                try:
                    i = utils.convert_config_type(i, arg_type)
                    compiled = True
                except Exception as e:
                    logger.info(e)
                    compiled = False
                    break
        if compiled:
            for i, kwargs in enumerate(config):
                kwargs = dict(kwargs)
                if self.stop_pending_event.is_set():
                    logger.info(f'Stopping execution during {run_name}: {i + 1}/{len(config)}')
                    break
                logger.info(f'Executing {i + 1} of {len(config)} with kwargs = {kwargs}')
                progress = (i + 1) * 100 / len(config)
                self._emit_progress(socketio, progress)
                # fname = f"{run_name}_script"
                # function = self.globals_dict[fname]
                output = self.exec_steps(script, "script", logger, socketio, run_id, i, **kwargs)
                if output:
                    # kwargs.update(output)
                    output_list.append(output)

    def _run_repeat_section(self, repeat_count, arg_types, bo_args, output_list, script, run_name, return_list, compiled,
                            logger, socketio, run_id):
        if bo_args:
            logger.info('Initializing optimizer...')
            if compiled:
                ax_client = bo_campaign.ax_init_opc(bo_args)
            else:
                ax_client = bo_campaign.ax_init_form(bo_args, arg_types)
        for i_progress in range(int(repeat_count)):
            if self.stop_pending_event.is_set():
                logger.info(f'Stopping execution during {run_name}: {i_progress + 1}/{int(repeat_count)}')
                break
            logger.info(f'Executing {run_name} experiment: {i_progress + 1}/{int(repeat_count)}')
            progress = (i_progress + 1) * 100 / int(repeat_count) - 0.1
            self._emit_progress(socketio, progress)
            if bo_args:
                try:
                    parameters, trial_index = ax_client.get_next_trial()
                    logger.info(f'Output value: {parameters}')
                    # fname = f"{run_name}_script"
                    # function = self.globals_dict[fname]
                    output = self.exec_steps(script, "script", logger, socketio, run_id, i_progress, **parameters)

                    _output = {key: value for key, value in output.items() if key in return_list}
                    ax_client.complete_trial(trial_index=trial_index, raw_data=_output)
                    output.update(parameters)
                except Exception as e:
                    logger.info(f'Optimization error: {e}')
                    break
            else:
                # fname = f"{run_name}_script"
                # function = self.globals_dict[fname]
                output = self.exec_steps(script, "script", logger, socketio, run_id, i_progress)

            if output:
                output_list.append(output)
                logger.info(f'Output value: {output}')
        return output_list

    @staticmethod
    def _save_results(run_name, arg_type, return_list, output_list, logger, output_path):
        args = list(arg_type.keys()) if arg_type else []
        args.extend(return_list)
        filename = run_name + "_" + datetime.now().strftime("%Y-%m-%d %H-%M") + ".csv"
        file_path = os.path.join(output_path, filename)
        with open(file_path, "w", newline='') as file:
            writer = csv.DictWriter(file, fieldnames=args)
            writer.writeheader()
            writer.writerows(output_list)
        logger.info(f'Results saved to {file_path}')
        return filename

    @staticmethod
    def _emit_progress(socketio, progress):
        socketio.emit('progress', {'progress': progress})

    def safe_sleep(self, duration: float):
        interval = 1  # check every 1 second
        end_time = time.time() + duration
        while time.time() < end_time:
            if self.stop_current_event.is_set():
                return  # Exit early if stop is requested
            time.sleep(min(interval, end_time - time.time()))

    def get_status(self):
        """Returns current status of the script runner."""
        with self.current_app.app_context():
            return {
                "is_running": self.lock.locked(),
                "paused": self.paused,
                "stop_pending": self.stop_pending_event.is_set(),
                "stop_current": self.stop_current_event.is_set(),
            }