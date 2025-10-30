import ast
import asyncio
import os
import csv
import threading
import time
from datetime import datetime
from typing import List, Dict, Any

from ivoryos.utils import utils, bo_campaign
from ivoryos.utils.db_models import Script, WorkflowRun, WorkflowStep, db, WorkflowPhase
from ivoryos.utils.global_config import GlobalConfig
from ivoryos.utils.decorators import BUILDING_BLOCKS
from ivoryos.utils.nest_script import validate_and_nest_control_flow

global_config = GlobalConfig()
global deck
deck = None
# global deck, registered_workflows
# deck, registered_workflows = None, None
class HumanInterventionRequired(Exception):
    pass

def pause(reason="Human intervention required"):
    handlers = global_config.notification_handlers
    if handlers:
        for handler in handlers:
            try:
                handler(reason)
            except Exception as e:
                print(f"[notify] handler {handler} failed: {e}")
    # raise error to pause workflow in gui
    raise HumanInterventionRequired(reason)

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
                   output_path="", compiled=False, current_app=None, history=None, optimizer=None, batch_mode=None,
                   n_suggestions=None):
        global deck
        if deck is None:
            deck = global_config.deck
        # print("history", history)
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
            args=(script, repeat_count, run_name, logger, socketio, config, bo_args, output_path, current_app, compiled,
                  history, optimizer, batch_mode, n_suggestions),
        )
        thread.start()
        return thread

    def exec_steps_batch(self, script, section_name, logger, socketio, phase_id,
                         batch_mode="step", batch_action=None, kwargs_list=None):
        """
        Executes a function in batch mode with multiple parameter sets

        :param script: The script object containing the function
        :param section_name: Name of the section to execute
        :param logger: Logger instance
        :param socketio: Socket.io instance for real-time updates
        :param phase_id: Phase identifier
        :param batch_mode: Mode of batch execution:
            - "step": Execute each step once, then repeat for next kwargs
            - "full": Execute all steps for first kwargs, then all steps for next kwargs
            - "parallel_step": Execute same step across all kwargs before moving to next step
        :param batch_action: Optional custom action function(step_index, kwargs_dict) -> modified_kwargs
        :param kwargs_list: List of dictionaries containing arguments for each batch execution
        :return: List of outputs from each batch execution
        """
        if kwargs_list is None:
            kwargs_list = [{}]

        _func_str = script.python_script or script.compile()
        _, return_list = script.config_return()

        step_list: list = script.convert_to_lines(_func_str).get(section_name, [])

        global deck
        if deck is None:
            deck = global_config.deck

        # Prepare base execution environment
        temp_connections = global_config.defined_variables
        base_exec_globals = {"deck": deck, "time": time, "pause": pause}
        base_exec_globals.update(temp_connections)

        # Inject all block categories
        for category, data in BUILDING_BLOCKS.items():
            for method_name, method in data.items():
                base_exec_globals[method_name] = method["func"]

        batch_results = []

        if batch_mode == "step":
            # Execute step 0 for all kwargs, then step 1 for all kwargs, etc.
            exec_locals_list = [kwargs.copy() for kwargs in kwargs_list]

            for step_index in range(len(step_list)):
                if self.stop_current_event.is_set():
                    logger.info(f'Stopping batch execution during {section_name}')
                    break

                line = step_list[step_index]
                method_name = line.strip()

                logger.info(f"Executing step {step_index}/{len(step_list)}: {line} for {len(kwargs_list)} batches")

                for batch_idx, kwargs in enumerate(kwargs_list):
                    if self.stop_current_event.is_set():
                        break

                    # Apply batch action if provided
                    current_kwargs = batch_action(step_index, kwargs.copy()) if batch_action else kwargs

                    exec_globals = base_exec_globals.copy()
                    exec_locals = exec_locals_list[batch_idx].copy()
                    exec_locals.update(current_kwargs)

                    step = WorkflowStep(
                        phase_id=phase_id,
                        step_index=step_index,
                        method_name=f"{method_name}_batch_{batch_idx}",
                        start_time=datetime.now(),
                    )
                    db.session.add(step)
                    db.session.flush()

                    socketio.emit('execution', {
                        'section': f"{section_name}-{step_index}-batch-{batch_idx}"
                    })

                    try:
                        self._execute_line(line, exec_globals, exec_locals)
                        step.run_error = False

                    except HumanInterventionRequired as e:
                        logger.warning(f"Human intervention required: {e}")
                        socketio.emit('human_intervention', {'message': str(e)})
                        step.run_error = False
                        self.toggle_pause()

                    except Exception as e:
                        logger.error(f"Error in batch {batch_idx}, step {step_index}: {e}")
                        socketio.emit('error', {'message': str(e), 'batch': batch_idx})
                        step.run_error = True
                        self.toggle_pause()

                    exec_locals.pop("__async_exec_wrapper", None)
                    step.end_time = datetime.now()
                    step.output = utils.safe_dump(exec_locals)
                    db.session.commit()

                    exec_locals_list[batch_idx] = exec_locals
                    self.pause_event.wait()

            # Extract results
            for exec_locals in exec_locals_list:
                output = {key: value for key, value in exec_locals.items() if key in return_list}
                batch_results.append(output)

        elif batch_mode == "full":
            # Execute all steps for kwargs[0], then all steps for kwargs[1], etc.
            for batch_idx, kwargs in enumerate(kwargs_list):
                if self.stop_current_event.is_set():
                    logger.info(f'Stopping batch execution at batch {batch_idx}')
                    break

                logger.info(f"Executing full workflow for batch {batch_idx}/{len(kwargs_list)}")

                # Use modified kwargs if batch_action provided
                current_kwargs = batch_action(0, kwargs.copy()) if batch_action else kwargs

                # Execute single instance using original logic
                output = self._exec_steps_single(
                    script, section_name, logger, socketio, phase_id,
                    batch_idx=batch_idx, **current_kwargs
                )
                batch_results.append(output)

        elif batch_mode == "parallel_step":
            # Similar to "step" but can be extended for true parallel execution
            # For now, similar to "step" mode but with parallel-ready structure
            return self.exec_steps_batch(
                script, section_name, logger, socketio, phase_id,
                batch_mode="step", batch_action=batch_action, kwargs_list=kwargs_list
            )

        return batch_results

    def _execute_line(self, line, exec_globals, exec_locals):
        """Helper method to execute a single line of code"""
        if line.startswith("time.sleep("):
            duration_str = line.strip()[len("time.sleep("):-1]
            duration = float(duration_str)
            self.safe_sleep(duration)
        else:
            if "await " in line:
                async_code = f"async def __async_exec_wrapper():\n"
                async_code += "\n".join("    " + l for l in line.splitlines())
                async_code += f"\n    return locals()"
                exec(async_code, exec_globals, exec_locals)
                func = exec_locals.get("__async_exec_wrapper") or exec_globals.get("__async_exec_wrapper")
                result_locals = asyncio.run(func())
                exec_locals.update(result_locals)
            else:
                exec(line, exec_globals, exec_locals)
                exec_globals.update(exec_locals)

    def _exec_steps_single(self, script, section_name, logger, socketio, phase_id,
                           batch_idx=None, **kwargs):
        """Helper method to execute all steps for a single set of kwargs"""
        _func_str = script.python_script or script.compile()
        _, return_list = script.config_return()

        step_list: list = script.convert_to_lines(_func_str).get(section_name, [])

        global deck
        if deck is None:
            deck = global_config.deck

        temp_connections = global_config.defined_variables
        exec_globals = {"deck": deck, "time": time, "pause": pause}
        exec_globals.update(temp_connections)

        for category, data in BUILDING_BLOCKS.items():
            for method_name, method in data.items():
                exec_globals[method_name] = method["func"]

        exec_locals = {}
        exec_locals.update(kwargs)
        index = 0

        while index < len(step_list):
            if self.stop_current_event.is_set():
                logger.info(f'Stopping execution during {section_name}')
                break

            line = step_list[index]
            method_name = line.strip()

            step_name = f"{method_name}_batch_{batch_idx}" if batch_idx is not None else method_name

            step = WorkflowStep(
                phase_id=phase_id,
                step_index=index,
                method_name=step_name,
                start_time=datetime.now(),
            )
            db.session.add(step)
            db.session.flush()

            logger.info(f"Executing: {line}")
            socketio.emit('execution', {'section': f"{section_name}-{index}"})

            try:
                self._execute_line(line, exec_globals, exec_locals)

            except HumanInterventionRequired as e:
                logger.warning(f"Human intervention required: {e}")
                socketio.emit('human_intervention', {'message': str(e)})
                self.toggle_pause()

            except Exception as e:
                logger.error(f"Error during script execution: {e}")
                socketio.emit('error', {'message': str(e)})
                step.run_error = True
                self.toggle_pause()

            exec_locals.pop("__async_exec_wrapper", None)
            step.end_time = datetime.now()
            step.output = utils.safe_dump(exec_locals)
            db.session.commit()

            self.pause_event.wait()

            if not step.run_error or not self.retry:
                index += 1

        output = {key: value for key, value in exec_locals.items() if key in return_list}
        return output

    async def exec_steps(self, script, section_name, logger, socketio, phase_id, kwargs_list):
        """
        Executes a function defined in a string line by line
        :param func_str: The function as a string
        :param kwargs: Arguments to pass to the function
        :return: The final result of the function execution
        """
        _func_str = script.python_script or script.compile()
        _, return_list = script.config_return()

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
        exec_globals = {"deck": deck, "time":time, "pause": pause}  # Add required global objects
        # exec_globals = {"deck": deck, "time": time, "registered_workflows":registered_workflows}  # Add required global objects
        exec_globals.update(temp_connections)

        # Inject all block categories
        for category, data in BUILDING_BLOCKS.items():
            for method_name, method in data.items():
                exec_globals[method_name] = method["func"]

        exec_locals = {}  # Local execution scope

        # Define function arguments manually in exec_locals
        # exec_locals.update(kwargs)
        index = 0
        results = kwargs_list.copy()
        nest_script = validate_and_nest_control_flow(script.script_dict.get(section_name, []))

        for step in nest_script:
            action = step["action"]

            if action == "if":
                await self._execute_if_batched(step, results)
            elif action == "repeat":
                await self._execute_repeat_batched(step, results)
            elif action == "while":
                await self._execute_while_batched(step, results)
            else:
                # Regular action - check if batch
                if step.get("batch_action", False):
                    # Execute once for all samples
                    await self._execute_action_once(step, results[0])
                else:
                    # Execute for each sample
                    for context in results:
                        await self._execute_action(step, context)
                        self.pause_event.wait()

        return results  # Return the 'results' variable

    def _run_with_stop_check(self, script: Script, repeat_count: int, run_name: str, logger, socketio, config, bo_args,
                             output_path, current_app, compiled, history=None, optimizer=None, batch_mode=None,
                             n_suggestions=None):
        time.sleep(1)
        # _func_str = script.compile()
        # step_list_dict: dict = script.convert_to_lines(_func_str)
        self._emit_progress(socketio, 1)
        filename = None
        error_flag = False
        # create a new run entry in the database
        repeat_mode = "batch" if config else "optimizer" if bo_args or optimizer else "repeat"
        with current_app.app_context():
            run = WorkflowRun(name=script.name or "untitled", platform=script.deck or "deck", start_time=datetime.now(),
                              repeat_mode=repeat_mode
                              )
            db.session.add(run)
            db.session.flush()
            run_id = run.id  # Save the ID
            db.session.commit()

            # try:
            if True:
                global_config.runner_status = {"id":run_id, "type": "workflow"}
                # Run "prep" section once
                self._run_actions(script, section_name="prep", logger=logger, socketio=socketio, run_id=run_id)
                output_list = []
                _, arg_type = script.config("script")
                _, return_list = script.config_return()
                # Run "script" section multiple times
                if repeat_count:
                    self._run_repeat_section(repeat_count, arg_type, bo_args, output_list, script,
                                             run_name, return_list, compiled, logger, socketio,
                                             history, output_path, run_id=run_id, optimizer=optimizer,
                                             batch_mode=batch_mode, n_suggestions=n_suggestions)
                elif config:
                    asyncio.run(
                        self._run_config_section(
                            config, arg_type, output_list, script, run_name, logger,
                            socketio, run_id=run_id, compiled=compiled
                        )
                    )
                    # self._run_config_section(config, arg_type, output_list, script, run_name, logger,
                    #                          socketio, run_id=run_id, compiled=compiled)
                # Run "cleanup" section once
                self._run_actions(script, section_name="cleanup", logger=logger, socketio=socketio,run_id=run_id)
                # Reset the running flag when done
                # Save results if necessary
                if not script.python_script and return_list:
                    # filename = self._save_results(run_name, arg_type, return_list, output_list, logger, output_path)
                    print(output_list)
                self._emit_progress(socketio, 100)

            # except Exception as e:
            #     logger.error(f"Error during script execution: {e.__str__()}")
            #     error_flag = True
            # finally:
                self.lock.release()
        with current_app.app_context():
            run = db.session.get(WorkflowRun, run_id)
            if run is None:
                logger.info("Error: Run not found in database.")
            else:
                run.end_time = datetime.now()
                run.data_path = filename
                run.run_error = error_flag
                db.session.commit()


    def _run_actions(self, script, section_name="", logger=None, socketio=None, run_id=None):
        _func_str = script.python_script or script.compile()
        step_list: list = script.convert_to_lines(_func_str).get(section_name, [])
        if not step_list:
            logger.info(f'No {section_name} steps')
            return None

        logger.info(f'Executing {section_name} steps')
        if self.stop_pending_event.is_set():
            logger.info(f"Stopping execution during {section_name} section.")
            return None

        phase = WorkflowPhase(
            run_id=run_id,
            name=section_name,
            repeat_index=0,
            start_time=datetime.now()
        )
        db.session.add(phase)
        db.session.flush()
        phase_id = phase.id

        step_outputs = self.exec_steps(script, section_name, logger, socketio, phase_id=phase_id)
        # Save phase-level output
        phase.outputs = step_outputs
        phase.end_time = datetime.now()
        db.session.commit()
        return step_outputs

    async def _run_config_section(self, config, arg_type, output_list, script, run_name, logger, socketio, run_id, compiled=True):
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
                progress = ((i + 1) * 100 / len(config)) - 0.1
                self._emit_progress(socketio, progress)
                # fname = f"{run_name}_script"
                # function = self.globals_dict[fname]

                phase = WorkflowPhase(
                    run_id=run_id,
                    name="main",
                    repeat_index=i,
                    parameters=kwargs,
                    start_time=datetime.now()
                )
                db.session.add(phase)
                db.session.flush()

                phase_id = phase.id
                parameters = [kwargs]
                output = await self.exec_steps(script, "script", logger, socketio, phase_id, kwargs_list=parameters)

                if output:
                    # kwargs.update(output)
                    output_list.append(output)
                    phase.outputs = output
                phase.end_time = datetime.now()
                db.session.commit()
        return output_list

    def _run_repeat_section(self, repeat_count, arg_types, bo_args, output_list, script, run_name, return_list, compiled,
                            logger, socketio, history, output_path, run_id, optimizer=None, batch_mode=None,
                            n_suggestions=None):
        if bo_args:
            logger.info('Initializing optimizer...')
            if compiled:
                ax_client = bo_campaign.ax_init_opc(bo_args)
            else:
                if history:
                    import pandas as pd
                    file_path = os.path.join(output_path, history)
                    previous_runs = pd.read_csv(file_path).to_dict(orient='records')
                    ax_client = bo_campaign.ax_init_form(bo_args, arg_types, len(previous_runs))
                    for row in previous_runs:
                        parameter = {key: value for key, value in row.items() if key in arg_types.keys()}
                        raw_data = {key: value for key, value in row.items() if key in return_list}
                        _, trial_index = ax_client.attach_trial(parameter)
                        ax_client.complete_trial(trial_index=trial_index, raw_data=raw_data)
                        output_list.append(row)
                else:
                    ax_client = bo_campaign.ax_init_form(bo_args, arg_types)
        elif optimizer and history:
            import pandas as pd
            file_path = os.path.join(output_path, history)

            previous_runs = pd.read_csv(file_path)
            optimizer.append_existing_data(previous_runs)
            for row in previous_runs:
                output_list.append(row)



        for i_progress in range(int(repeat_count)):
            if self.stop_pending_event.is_set():
                logger.info(f'Stopping execution during {run_name}: {i_progress + 1}/{int(repeat_count)}')
                break

            phase = WorkflowPhase(
                run_id=run_id,
                name="main",
                repeat_index=i_progress,
                start_time=datetime.now()
            )
            db.session.add(phase)
            db.session.flush()
            phase_id = phase.id

            logger.info(f'Executing {run_name} experiment: {i_progress + 1}/{int(repeat_count)}')
            progress = (i_progress + 1) * 100 / int(repeat_count) - 0.1
            self._emit_progress(socketio, progress)
            if bo_args:
                try:
                    parameters, trial_index = ax_client.get_next_trial()
                    logger.info(f'Output value: {parameters}')
                    # fname = f"{run_name}_script"
                    # function = self.globals_dict[fname]
                    phase.parameters = parameters

                    output = self.exec_steps(script, "script", logger, socketio, phase_id)

                    _output = {key: value for key, value in output.items() if key in return_list}
                    ax_client.complete_trial(trial_index=trial_index, raw_data=_output)
                    output.update(parameters)
                except Exception as e:
                    logger.info(f'Optimization error: {e}')
                    break
            # Optimizer for UI
            elif optimizer:
                try:
                    parameters = optimizer.suggest(n=n_suggestions)
                    logger.info(f'Output value: {parameters}')
                    phase.parameters = parameters

                    if type(parameters) is list and (parameters) == 1:
                        parameters = parameters[0]

                    if not type(parameters) is list:
                        output = self.exec_steps(script, "script", logger, socketio, phase_id)
                        if output:
                            optimizer.observe(output)
                            # output.update(parameters)
                    else:
                        #TODO
                        output = self.exec_steps(script, "script", logger, socketio, phase_id, kwargs_list=parameters)
                        if output:
                            optimizer.observe(output)
                            # output.update(parameters)
                except Exception as e:
                    logger.info(f'Optimization error: {e}')
                    break
            else:
                # fname = f"{run_name}_script"
                # function = self.globals_dict[fname]
                output = self.exec_steps(script, "script", logger, socketio, phase_id)

            if output:
                output_list.append(output)
                logger.info(f'Output value: {output}')
                phase.outputs = output
            phase.end_time = datetime.now()
            db.session.commit()

        if bo_args:
            ax_client.save_to_json_file(os.path.join(output_path, f"{run_name}_ax_client.json"))
            logger.info(
                f'Optimization complete. Results saved to {os.path.join(output_path, f"{run_name}_ax_client.json")}'
            )
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


    async def _execute_steps_by_sample_helper(self, steps: List[Dict], param_sets: List[Dict[str, Any]],
                                              results: List[Dict], start_idx: int,
                                              batch_actions_executed: set):
        """Helper to execute steps for specific samples in by_sample mode."""
        for step_idx, step in enumerate(steps):
            action = step["action"]

            if action == "if":
                await self._execute_if_by_sample_nested(step, param_sets, results, start_idx, batch_actions_executed)
            elif action == "repeat":
                await self._execute_repeat_by_sample_nested(step, param_sets, results, start_idx,
                                                            batch_actions_executed)
            elif action == "while":
                await self._execute_while_by_sample_nested(step, param_sets, results, start_idx, batch_actions_executed)
            else:
                # Regular action
                if step.get("batch_action", False):
                    # Batch action - execute once
                    batch_key = (id(steps), step_idx, step.get("uuid", id(step)))
                    if batch_key not in batch_actions_executed:
                        print(f"Executing batch action: {action}")
                        context = results[start_idx] if start_idx < len(results) else param_sets[0]
                        await self._execute_action(step, context)
                        batch_actions_executed.add(batch_key)
                else:
                    # Non-batch action - execute for this sample
                    for rel_idx, params in enumerate(param_sets):
                        actual_idx = start_idx + rel_idx
                        context = results[actual_idx] if actual_idx < len(results) else {**params}
                        result = await self._execute_action(step, context)
                        if actual_idx < len(results):
                            results[actual_idx].update(result)

    async def _execute_if_by_sample_nested(self, step: Dict, param_sets: List[Dict[str, Any]],
                                           results: List[Dict], start_idx: int,
                                           batch_actions_executed: set):
        """Execute nested if/else in by_sample mode."""
        for rel_idx, params in enumerate(param_sets):
            actual_idx = start_idx + rel_idx
            context = results[actual_idx] if actual_idx < len(results) else params

            condition = self._evaluate_condition(step["args"]["statement"], context)

            if condition:
                await self._execute_steps_by_sample_helper(
                    step["if_block"], [params], results, actual_idx, batch_actions_executed
                )
            else:
                await self._execute_steps_by_sample_helper(
                    step["else_block"], [params], results, actual_idx, batch_actions_executed
                )

    async def _execute_repeat_by_sample_nested(self, step: Dict, param_sets: List[Dict[str, Any]],
                                               results: List[Dict], start_idx: int,
                                               batch_actions_executed: set):
        """Execute nested repeat in by_sample mode."""
        times = step["args"].get("times", 1)

        for i in range(times):
            for rel_idx, params in enumerate(param_sets):
                actual_idx = start_idx + rel_idx
                if actual_idx < len(results):
                    results[actual_idx]["repeat_index"] = i

                await self._execute_steps_by_sample_helper(
                    step["repeat_block"], [params], results, actual_idx, batch_actions_executed
                )

    async def _execute_while_by_sample_nested(self, step: Dict, param_sets: List[Dict[str, Any]],
                                              results: List[Dict], start_idx: int,
                                              batch_actions_executed: set):
        """Execute nested while in by_sample mode."""
        max_iterations = step["args"].get("max_iterations", 1000)

        for rel_idx, params in enumerate(param_sets):
            actual_idx = start_idx + rel_idx
            iteration = 0

            while iteration < max_iterations:
                context = results[actual_idx] if actual_idx < len(results) else {**params}
                context["while_index"] = iteration

                condition = self._evaluate_condition(step["args"]["condition"], context)

                if not condition:
                    break

                await self._execute_steps_by_sample_helper(
                    step["while_block"], [params], results, actual_idx, batch_actions_executed
                )

                iteration += 1

            if iteration >= max_iterations:
                raise RuntimeError(f"While loop exceeded max iterations ({max_iterations}) for sample {actual_idx}")




    async def _execute_steps(self, steps: List[Dict], context: Dict[str, Any], batch_actions_executed: set = None):
        """
        Execute a list of steps for a single sample with its context.

        Args:
            steps: List of workflow steps
            context: Context for this sample
            batch_actions_executed: Set of batch action UUIDs that have already been executed
        """
        if batch_actions_executed is None:
            batch_actions_executed = set()

        result = context.copy()

        for step in steps:
            action = step["action"]

            if action == "if":
                result = await self._execute_if(step, result, batch_actions_executed)
            elif action == "repeat":
                result = await self._execute_repeat(step, result, batch_actions_executed)
            elif action == "while":
                result = await self._execute_while(step, result, batch_actions_executed)
            else:
                # Regular action - check if it's a batch action
                if step.get("batch_action", False):
                    step_uuid = step.get("uuid", id(step))

                    if step_uuid not in batch_actions_executed:
                        # Execute batch action only once
                        print(f"  [BATCH] Executing {step['action']} once for all samples")
                        result = await self._execute_action(step, result)
                        batch_actions_executed.add(step_uuid)
                    else:
                        print(f"  [BATCH] Skipping {step['action']} (already executed)")
                else:
                    # Regular action - execute for this sample
                    result = await self._execute_action(step, result)

        return result

    async def _execute_if(self, step: Dict, context: Dict[str, Any], batch_actions_executed: set):
        """Execute if/else block for single sample."""
        condition = self._evaluate_condition(step["args"]["statement"], context)

        if condition:
            return await self._execute_steps(step["if_block"], context, batch_actions_executed)
        else:
            return await self._execute_steps(step["else_block"], context, batch_actions_executed)

    async def _execute_repeat(self, step: Dict, context: Dict[str, Any], batch_actions_executed: set):
        """Execute repeat block for single sample."""
        times = step["args"].get("times", 1)

        for i in range(times):
            context["repeat_index"] = i
            context = await self._execute_steps(step["repeat_block"], context, batch_actions_executed)

        return context

    async def _execute_while(self, step: Dict, context: Dict[str, Any], batch_actions_executed: set):
        """Execute while block for single sample."""
        max_iterations = step["args"].get("max_iterations", 1000)
        iteration = 0

        while iteration < max_iterations:
            condition = self._evaluate_condition(step["args"]["statement"], context)

            if not condition:
                break

            context["while_index"] = iteration
            context = await self._execute_steps(step["while_block"], context, batch_actions_executed)
            iteration += 1

        if iteration >= max_iterations:
            raise RuntimeError(f"While loop exceeded max iterations ({max_iterations})")

        return context

    async def _batch_by_step(self, nested_list: List[Dict], param_sets: List[Dict[str, Any]]):
        """
        Execute workflow step-by-step for all samples together.
        Batch actions are executed once for all samples.
        Non-batch actions are executed for each sample.
        """
        num_samples = len(param_sets)
        results = param_sets.copy()

        await self._execute_steps_batched(nested_list, results)

        return results


    async def _execute_steps_batched(self, steps: List[Dict], contexts: List[Dict[str, Any]]):
        """
        Execute a list of steps for multiple samples, batching where appropriate.
        """
        for step in steps:
            action = step["action"]

            if action == "if":
                await self._execute_if_batched(step, contexts)
            elif action == "repeat":
                await self._execute_repeat_batched(step, contexts)
            elif action == "while":
                await self._execute_while_batched(step, contexts)
            else:
                # Regular action - check if batch
                if step.get("batch_action", False):
                    # Execute once for all samples
                    await self._execute_action_once(step, contexts[0])
                else:
                    # Execute for each sample
                    for context in contexts:
                        await self._execute_action(step, context)


    async def _execute_if_batched(self, step: Dict, contexts: List[Dict[str, Any]]):
        """Execute if/else block for multiple samples."""
        # Evaluate condition for each sample
        for context in contexts:
            condition = self._evaluate_condition(step["args"]["statement"], context)

            if condition:
                await self._execute_steps_batched(step["if_block"], [context])
            else:
                await self._execute_steps_batched(step["else_block"], [context])


    async def _execute_repeat_batched(self, step: Dict, contexts: List[Dict[str, Any]]):
        """Execute repeat block for multiple samples."""
        times = step["args"].get("times", 1)

        for i in range(times):
            # Add repeat index to all contexts
            for context in contexts:
                context["repeat_index"] = i

            await self._execute_steps_batched(step["repeat_block"], contexts)


    async def _execute_while_batched(self, step: Dict, contexts: List[Dict[str, Any]]):
        """Execute while block for multiple samples."""
        max_iterations = step["args"].get("max_iterations", 1000)
        active_contexts = contexts.copy()
        iteration = 0

        while iteration < max_iterations and active_contexts:
            # Filter contexts that still meet the condition
            still_active = []

            for context in active_contexts:
                condition = self._evaluate_condition(step["args"]["statement"], context)

                if condition:
                    context["while_index"] = iteration
                    still_active.append(context)

            if not still_active:
                break

            # Execute for contexts that are still active
            await self._execute_steps_batched(step["while_block"], still_active)
            active_contexts = still_active
            iteration += 1

        if iteration >= max_iterations:
            raise RuntimeError(f"While loop exceeded max iterations ({max_iterations})")

    async def _execute_action(self, step: Dict, context: Dict[str, Any]):
        """Execute a single action with parameter substitution."""
        # Substitute parameters in args
        substituted_args = self._substitute_params(step["args"], context)

        # Get the component and method
        instrument = step.get("instrument", "")
        action = step["action"]
        if instrument:
            instrument = instrument[5:]
            # print(instrument)
        # Execute the action
        step_db = WorkflowStep(
            phase_id=1,
            step_index=1,
            method_name=action,
            start_time=datetime.now(),
        )
        db.session.add(step_db)
        db.session.flush()

        if action == "wait":
            duration = float(substituted_args["statement"])
            self.safe_sleep(duration)

        elif action == "pause":
            # logger.warning(f"Human intervention required: {e}")
            # socketio.emit('human_intervention', {'message': str(e)})
            # Instead of auto-resume, explicitly stay paused until user action
            # step.run_error = False
            self.toggle_pause()

        elif hasattr(deck, instrument):
            component = getattr(deck, instrument)
            if hasattr(component, action):
                method = getattr(component, action)

                # Execute and handle return value
                if step.get("coroutine", False):
                    result = await method(**substituted_args)
                else:
                    result = method(**substituted_args)

                # Store return value if specified
                return_var = step.get("return", "")
                if return_var:
                    context[return_var] = result

        return context

    async def _execute_action_once(self, step: Dict, context: Dict[str, Any]):
        """Execute a batch action once (not per sample)."""
        print(f"Executing batch action: {step['action']}")
        return await self._execute_action(step, context)

    def _substitute_params(self, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Substitute parameter placeholders like #param_1 with actual values."""
        substituted = {}

        for key, value in args.items():
            if isinstance(value, str) and value.startswith("#"):
                param_name = value[1:]  # Remove '#'
                substituted[key] = context.get(param_name, value)
            else:
                substituted[key] = value

        return substituted

    def _evaluate_condition(self, condition_str: str, context: Dict[str, Any]) -> bool:
        """
        Safely evaluate a condition string with context variables.

        WARNING: This uses eval() which can be dangerous.
        In production, use a proper expression parser.
        """
        # Substitute variables
        for key, value in context.items():
            # Replace variable names in condition
            condition_str = condition_str.replace(f"#{key}", str(value))

        try:
            # Safe evaluation with limited scope
            return bool(eval(condition_str, {"__builtins__": {}}, context))
        except Exception as e:
            print(f"Error evaluating condition '{condition_str}': {e}")
            return False