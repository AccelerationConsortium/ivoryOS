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

        self.stop_event = threading.Event()
        self.is_running = False
        self.lock = threading.Lock()

    def reset_stop_event(self):
        self.stop_event.clear()

    def stop_execution(self):
        self.stop_event.set()
        # print("Stop pending tasks")

    def run_script(self, script, repeat_count=1, run_name=None, logger=None, socketio=None, config=None, bo_args=None,
                   output_path=""):
        global deck
        if deck is None:
            deck = global_config.deck
        exec_string = script.compile()
        exec(exec_string)
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

    def _run_with_stop_check(self, script: Script, repeat_count, run_name, logger, socketio, config, bo_args,
                             output_path):
        time.sleep(1)
        self._emit_progress(socketio, 1)
        try:
            # Run "prep" section once
            script_dict = script.script_dict
            self._run_actions(script_dict.get("prep", []), section_name="prep", run_name=run_name, logger=logger)
            output_list = []
            _, arg_type = script.config("script")
            _, return_list = script.config_return()
            # Run "script" section multiple times
            if repeat_count:
                self._run_repeat_section(repeat_count, arg_type, bo_args, output_list, return_list, run_name, logger, socketio)
            elif config:
                self._run_config_section(config, arg_type, output_list, return_list, run_name, logger, socketio)
            # Run "cleanup" section once
            self._run_actions(script_dict.get("cleanup", []), section_name="cleanup", run_name=run_name, logger=logger)
            # Save results if necessary
            if output_list:
                self._save_results(run_name, arg_type, return_list, output_list, logger, output_path)
        except Exception as e:
            logger.error(f"Error during script execution: {e}")
        finally:
            with self.lock:
                self.is_running = False  # Reset the running flag when done
            self._emit_progress(socketio, 100)

    def _run_actions(self, actions, section_name="", run_name=None, logger=None):
        logger.info(f'Executing {section_name} steps') if actions else logger.info(f'No {section_name} steps')
        if self.stop_event.is_set():
            logger.info(f"Stopping execution during {section_name} section.")
            return
            # for action in actions:
            #     if self.stop_event.is_set():
            #         logger.info(f"Stopping execution during {section_name} section.")
            #         break
            #     logger.info(f'Executing {action.get("action", "")} action')
        fname = f"{run_name}_{section_name}"
        function = self.globals_dict[fname]
        function()

    def _run_config_section(self, config, arg_type, output_list, return_list, run_name, logger, socketio):
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
                if self.stop_event.is_set():
                    logger.info(f'Stopping execution during {run_name}: {i + 1}/{len(config)}')
                    break
                logger.info(f'Executing {i + 1} of {len(config)} with kwargs = {kwargs}')
                progress = (i + 1) * 100 / len(config)
                self._emit_progress(socketio, progress)
                fname = f"{run_name}_script"
                function = self.globals_dict[fname]
                output = function(**kwargs)
                if output:
                    kwargs.update(output)
                    output_list.append(kwargs)

    def _run_repeat_section(self, repeat_count, arg_types, bo_args, output_list, return_list, run_name, logger, socketio):
        if bo_args:
            logger.info('Initializing optimizer...')
            ax_client = utils.ax_initiation(bo_args, arg_types)
        for i in range(int(repeat_count)):
            if self.stop_event.is_set():
                logger.info(f'Stopping execution during {run_name}: {i + 1}/{int(repeat_count)}')
                break
            logger.info(f'Executing {run_name} experiment: {i + 1}/{int(repeat_count)}')
            progress = (i + 1) * 100 / int(repeat_count) - 0.1
            self._emit_progress(socketio, progress)
            if bo_args:
                try:
                    parameters, trial_index = ax_client.get_next_trial()
                    logger.info(f'Output value: {parameters}')
                    fname = f"{run_name}_script"
                    function = self.globals_dict[fname]
                    output = function(**parameters)
                    # output = eval(f"{run_name}_script(**{parameters})")
                    _output = output.copy()
                    ax_client.complete_trial(trial_index=trial_index, raw_data=_output)
                    output.update(parameters)
                except Exception as e:
                    logger.info(f'Optimization error: {e}')
                    break
            else:
                fname = f"{run_name}_script"
                function = self.globals_dict[fname]
                output = function()

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
