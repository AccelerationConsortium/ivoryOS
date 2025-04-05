import ast
import os
import csv
import threading
import time
from datetime import datetime

from ivoryos.utils import utils
from ivoryos.utils.db_models import Script
from ivoryos.utils.global_config import GlobalConfig

global_config = GlobalConfig()
global deck
deck = None

class ScriptRunner:
    def __init__(self, globals_dict=None):
        if globals_dict is None:
            globals_dict = globals()
        self.globals_dict = globals_dict
        self.pause_event = threading.Event()  # A threading event to manage pause/resume
        self.pause_event.set()
        self.stop_pending_event = threading.Event()
        self.stop_current_event = threading.Event()
        self.is_running = False
        self.lock = threading.Lock()
        self.paused = False

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
                   output_path=""):
        global deck
        if deck is None:
            deck = global_config.deck
        time.sleep(1)
        with self.lock:
            if self.is_running:
                logger.info("System is busy. Please wait for it to finish or stop it before starting a new one.")
                return None
            self.is_running = True

        self.reset_stop_event()

        thread = threading.Thread(target=self._run_with_stop_check,
                                  args=(script, repeat_count, run_name, logger, socketio, config, bo_args, output_path))
        thread.start()
        return thread

    def exex_steps(self, script, section_name, logger, socketio, **kwargs):
        """
        Executes a function defined in a string line by line.

        :param func_str: The function as a string
        :param kwargs: Arguments to pass to the function
        :return: The final result of the function execution
        """
        _func_str = script.compile()
        step_list: list = script.convert_to_lines(_func_str).get(section_name, [])
        global deck
        if deck is None:
            deck = global_config.deck
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
                break
            line = step_list[index]
            logger.info(f"Executing: {line}")  # Debugging output
            socketio.emit('execution', {'section': f"{section_name}-{index}"})
            # self._emit_progress(socketio, 100)
            try:
                exec(line, exec_globals, exec_locals)
            except Exception as e:
                logger.error(f"Error during script execution: {e}")
                socketio.emit('error', {'message': e.__str__()})
                self.toggle_pause()
            self.pause_event.wait()

            # todo update script during the run
            # _func_str = script.compile()
            # step_list: list = script.convert_to_lines(_func_str).get(section_name, [])
            index += 1
        return exec_locals  # Return the 'results' variable

    def _run_with_stop_check(self, script: Script, repeat_count: int, run_name: str, logger, socketio, config, bo_args,
                             output_path):
        time.sleep(1)
        # _func_str = script.compile()
        # step_list_dict: dict = script.convert_to_lines(_func_str)
        self._emit_progress(socketio, 1)

        # Run "prep" section once
        script_dict = script.script_dict
        self._run_actions(script, section_name="prep", logger=logger, socketio=socketio)
        output_list = []
        _, arg_type = script.config("script")
        _, return_list = script.config_return()

        # Run "script" section multiple times
        if repeat_count:
            self._run_repeat_section(repeat_count, arg_type, bo_args, output_list, script,
                                     run_name, return_list, logger, socketio)
        elif config:
            self._run_config_section(config, arg_type, output_list, script, run_name, logger,
                                     socketio)

        # Run "cleanup" section once
        self._run_actions(script, section_name="cleanup", logger=logger, socketio=socketio)
        # Reset the running flag when done
        with self.lock:
            self.is_running = False
        # Save results if necessary
        if output_list:
            self._save_results(run_name, arg_type, return_list, output_list, logger, output_path)
        self._emit_progress(socketio, 100)

    def _run_actions(self, script, section_name="", logger=None, socketio=None):
        _func_str = script.compile()
        step_list: list = script.convert_to_lines(_func_str).get(section_name, [])
        logger.info(f'Executing {section_name} steps') if step_list else logger.info(f'No {section_name} steps')
        if self.stop_pending_event.is_set():
            logger.info(f"Stopping execution during {section_name} section.")
            return
        self.exex_steps(script, section_name, logger, socketio)

    def _run_config_section(self, config, arg_type, output_list, script, run_name, logger, socketio):
        compiled = True
        for i in config:
            try:
                i = utils.convert_config_type(i, arg_type)
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
                output = self.exex_steps(script, "script", logger, socketio, **kwargs)
                if output:
                    # kwargs.update(output)
                    output_list.append(output)

    def _run_repeat_section(self, repeat_count, arg_types, bo_args, output_list, script, run_name, return_list,
                            logger, socketio):
        if bo_args:
            logger.info('Initializing optimizer...')
            ax_client = utils.ax_initiation(bo_args, arg_types)
        for i in range(int(repeat_count)):
            if self.stop_pending_event.is_set():
                logger.info(f'Stopping execution during {run_name}: {i + 1}/{int(repeat_count)}')
                break
            logger.info(f'Executing {run_name} experiment: {i + 1}/{int(repeat_count)}')
            progress = (i + 1) * 100 / int(repeat_count) - 0.1
            self._emit_progress(socketio, progress)
            if bo_args:
                try:
                    parameters, trial_index = ax_client.get_next_trial()
                    logger.info(f'Output value: {parameters}')
                    # fname = f"{run_name}_script"
                    # function = self.globals_dict[fname]
                    output = self.exex_steps(script, "script", logger, socketio, **parameters)

                    _output = {key: value for key, value in output.items() if key in return_list}
                    ax_client.complete_trial(trial_index=trial_index, raw_data=_output)
                    output.update(parameters)
                except Exception as e:
                    logger.info(f'Optimization error: {e}')
                    break
            else:
                # fname = f"{run_name}_script"
                # function = self.globals_dict[fname]
                output = self.exex_steps(script, "script", logger, socketio)

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

    @staticmethod
    def _emit_progress(socketio, progress):
        socketio.emit('progress', {'progress': progress})
