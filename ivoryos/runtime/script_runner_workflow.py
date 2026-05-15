import asyncio
import logging
import os
import time
from datetime import datetime

import pandas as pd

from ivoryos.runtime.control_flow import validate_and_nest_control_flow
from ivoryos.runtime.runner_runtime import ensure_deck, global_state, pause
from ivoryos.models import WorkflowRun, WorkflowPhase, db
from ivoryos.script import Script, ScriptEditor, ScriptRenderer
from ivoryos.parsers.serialize import sanitize_for_json
from ivoryos.parsers.type_conversions import convert_config_type


class ScriptRunnerWorkflowMixin:
    async def exec_steps(self, script, section_name, phase_id, kwargs_list=None, batch_size=1):
        """
        Executes a function defined in a string line by line
        :param func_str: The function as a string
        :param kwargs: Arguments to pass to the function
        :return: The final result of the function execution
        """
        _func_str = script.python_script or ScriptRenderer(script).compile()
        _, return_list = ScriptEditor(script).config_return()

        # global deck, registered_workflows
        current_deck = ensure_deck()
        # if registered_workflows is None:
        #     registered_workflows = global_state.registered_workflows

        # for i, line in enumerate(step_list):
        #     if line.startswith("registered_workflows"):
        #
        # func_str = ScriptRenderer(script).compile()
        # Parse function body from string
        temp_connections = global_state.defined_variables
        # Prepare execution environment
        exec_globals = {"deck": current_deck, "time": time, "pause": pause}  # Add required global objects
        # exec_globals = {"deck": deck, "time": time, "registered_workflows":registered_workflows}  # Add required global objects
        exec_globals.update(temp_connections)

        exec_locals = {}  # Local execution scope

        # Define function arguments manually in exec_locals
        # exec_locals.update(kwargs)
        index = 0
        if kwargs_list:
            results = kwargs_list.copy()
        else:
            results = [{} for _ in range(batch_size)]
        nested_steps = validate_and_nest_control_flow(script.script_dict.get(section_name, []))

        await self._execute_steps_batched(nested_steps, results, phase_id=phase_id, section_name=section_name)

        return results  # Return the 'results' variable

    def _run_with_stop_check(self, script: Script, repeat_count: int, run_name: str, config,
                             output_path, current_app, compiled, history=None, optimizer=None, batch_mode=None,
                             batch_size=None, objectives=None, parameters=None, constraints=None, steps=None,
                             optimizer_cls=None, additional_params=None, on_start=None, display_name=None):
        if current_app:
            ctx = current_app.app_context()
            ctx.push()

        time.sleep(1)
        
        if on_start:
            try:
                on_start()
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error in on_start callback: {e}")
        elif self.socketio:
             # Fallback if no callback provided? Or just minimal emit?
             self.socketio.emit('start_task', {'run_name': run_name})

        # _func_str = ScriptRenderer(script).compile()
        # step_list_dict: dict = ScriptRenderer(script).convert_to_lines(_func_str)
        self._emit_progress(1)
        filename = f"{run_name}_{datetime.now().strftime('%Y-%m-%d %H-%M')}.csv"
        error_flag = False
        # create a new run entry in the database
        repeat_mode = "batch" if config else "optimizer" if optimizer else "repeat"
        if optimizer_cls is not None:
            # try:
            if self.logger:
                self.logger.info(f"Initializing optimizer {optimizer_cls.__name__}")
            try:
                optimizer = optimizer_cls(experiment_name=run_name, parameter_space=parameters, objective_config=objectives,
                                      parameter_constraints=constraints, additional_params=additional_params,
                                      optimizer_config=steps, datapath=output_path)
                current_app.config["LAST_OPTIMIZER"] = optimizer
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error during optimizer initialization: {e.__str__()}")
                self._emit_progress(100)
                if self.lock.locked():
                    self.lock.release()
                return None

        with current_app.app_context():
            run = WorkflowRun(name=script.name or "untitled", platform=script.deck or "deck", start_time=datetime.now(),
                              repeat_mode=repeat_mode
                              )
            db.session.add(run)
            db.session.flush()
            run_id = run.id  # Save the ID
            # overwrite filename with the run specific start time
            filename = f"{run_name}_{run.start_time.strftime('%Y-%m-%d %H-%M-%S')}.csv"
            run.data_path = filename
            db.session.commit()

            # setup run-specific logging to a file using run_id
            log_filename = f"{run_name}_{run.start_time.strftime('%Y-%m-%d %H-%M-%S')}.log"
            log_path = os.path.join(current_app.config["LOG_FOLDER"], log_filename)
            run_file_handler = logging.FileHandler(log_path)
            run_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
            gui_logger = self.logger
            app_loggers = current_app.config["LOGGERS"]
            app_loggers = app_loggers if isinstance(app_loggers, list) else [app_loggers]
            gui_and_app_loggers = [gui_logger, *app_loggers]
            for logger in gui_and_app_loggers:
                if not logger:
                    continue
                if isinstance(logger, str):
                    logger = logging.getLogger(logger)
                try:
                    logger.addHandler(run_file_handler)
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Failed to setup logger {logger}: {e}")

            try:
            # if True:
                global_state.runner_status = {"id":run_id, "type": "workflow"}
                # Run "prep" section once
                asyncio.run(self._run_actions(script, section_name="prep", run_id=run_id))
                output_list = []
                _, arg_type = ScriptEditor(script).config("script")
                _, return_list = ScriptEditor(script).config_return()
                # Run "script" section multiple times
                if repeat_count:
                    asyncio.run(
                        self._run_repeat_section(repeat_count, arg_type, output_list, script,
                                             run_name, return_list, compiled,
                                             history, output_path, run_id, filename, optimizer=optimizer,
                                             batch_mode=batch_mode, batch_size=batch_size, objectives=objectives)
                    )
                elif config:
                    asyncio.run(
                        self._run_config_section(
                            config, arg_type, output_list, script, run_name, run_id, filename, return_list, output_path,
                            compiled=compiled, batch_mode=batch_mode, batch_size=batch_size
                        )
                    )

                # Run "cleanup" section once
                asyncio.run(self._run_actions(script, section_name="cleanup", run_id=run_id))
                # Reset the running flag when done

            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error during script execution: {e.__str__()}")
                error_flag = True
            finally:
                self._emit_progress(100)
                if self.lock.locked():
                    self.lock.release()
                self._emit_busy_status()
                
                self.current_task = None # Clear current task
                
                # Close run-specific log handler
                for logger in gui_and_app_loggers:
                    if not logger:
                        continue
                    if isinstance(logger, str):
                        logger = logging.getLogger(logger)
                    try:
                        logger.removeHandler(run_file_handler)
                    except Exception:
                        pass
                    run_file_handler.close()

                # Check for next task in queue
                self._process_queue()


        with current_app.app_context():
            run = db.session.get(WorkflowRun, run_id)
            if run is None:
                if self.logger:
                    self.logger.info("Error: Run not found in database.")
            else:
                run.end_time = datetime.now()
                run.run_error = error_flag

                # remove data_path from db record
                if not any(output_list):
                    run.data_path = None
                db.session.commit()


    async def _run_actions(self, script, section_name="", run_id=None):

        if self.logger:
            self.logger.info(f'Executing {section_name} steps')

        # V1.4.8 stop cleanup is optional, credit @Veronica
        # Only skip cleanup section when explicitly requested via stop_cleanup_event
        if section_name == "cleanup" and self.stop_cleanup_event.is_set():
            if self.logger:
                self.logger.info(f"Skipping cleanup section due to stop signal.")
            return None

        phase = WorkflowPhase(
            run_id=run_id,
            name=section_name,
            repeat_index=1,
            start_time=datetime.now()
        )
        db.session.add(phase)
        db.session.flush()
        phase_id = phase.id
        db.session.commit()

        step_outputs = await self.exec_steps(script, section_name, phase_id=phase_id)
        # Save phase-level output
        phase = db.session.get(WorkflowPhase, phase_id)
        phase.outputs = sanitize_for_json(step_outputs)
        phase.end_time = datetime.now()
        db.session.commit()
        return step_outputs

    async def _run_config_section(self, config, arg_type, output_list, script, run_name, run_id, filename, return_list, output_path,
                                  compiled=True, batch_mode=False, batch_size=1):
        if not compiled:
            for i in config:
                try:
                    i = convert_config_type(i, arg_type)
                    compiled = True
                except Exception as e:
                    if self.logger:
                        if isinstance(e, SyntaxError):
                            self.logger.error(f"Error in configuration data: {e.args}")
                            self.logger.error(
                                f"{e.msg} at line {e.lineno}, column {e.offset}: {e.text.strip()}"
                            )
                        else:
                            self.logger.error(e)
                    compiled = False
                    break
        if compiled:
            batch_size = int(batch_size)
            nested_list = [config[i:i + batch_size] for i in range(0, len(config), batch_size)]

            for i, kwargs_list in enumerate(nested_list):
                # kwargs = dict(kwargs)
                if self.stop_pending_event.is_set():
                    if self.logger:
                        self.logger.info(f'Stopping execution during {run_name}: {i + 1}/{len(config)}')
                    break
                if self.logger:
                    self.logger.info(f'Executing {i + 1} of {len(nested_list)} with kwargs = {kwargs_list}')
                progress = ((i + 1) * 100 / len(nested_list)) - 0.1
                self._emit_progress(progress, iteration=i + 1, total=len(nested_list))

                phase = WorkflowPhase(
                    run_id=run_id,
                    name="main",
                    repeat_index=i + 1,
                    parameters=sanitize_for_json(kwargs_list),
                    start_time=datetime.now()
                )
                db.session.add(phase)
                db.session.flush()

                phase_id = phase.id
                db.session.commit()

                output = await self.exec_steps(script, "script", phase_id, kwargs_list=kwargs_list, )
                # print(output)
                phase = db.session.get(WorkflowPhase, phase_id)
                if output:
                    # kwargs.update(output)
                    for output_dict in output:
                        output_list.append(output_dict)
                    phase.outputs = sanitize_for_json(output)
                phase.end_time = datetime.now()
                db.session.commit()

                # save results
                if not script.python_script and any(output_list):
                    if i == 0:
                        self._save_results(filename, arg_type, return_list, output_list, output_path)
                    else:
                        self._save_results_last_row(filename, arg_type, return_list, output_list, output_path)

        return output_list

    async def _run_repeat_section(self, repeat_count, arg_types, output_list, script, run_name, return_list, compiled,
                                  history, output_path, run_id, filename,
                                  optimizer=None, batch_mode=None, batch_size=None, objectives=None):

        if optimizer and history:
            file_path = os.path.join(output_path, history)

            previous_runs = pd.read_csv(file_path)

            expected_cols = list(arg_types.keys()) + list(return_list)

            actual_cols = previous_runs.columns.tolist()

            # NOT okay if it misses columns
            if set(expected_cols) - set(actual_cols):
                if self.logger:
                    self.logger.warning(f"Missing columns from history .csv file. Expecting {expected_cols} but got {actual_cols}")
                raise ValueError("Missing columns from history .csv file.")

            # okay if there is extra columns
            if set(actual_cols) - set(expected_cols):
                if self.logger:
                    self.logger.warning(f"Extra columns from history .csv file. Expecting {expected_cols} but got {actual_cols}")

            optimizer.append_existing_data(previous_runs, file_path)

            for row in previous_runs.to_dict(orient='records'):
                output_list.append(row)



        for i_progress in range(int(repeat_count)):
            if self.stop_pending_event.is_set():
                if self.logger:
                    self.logger.info(f'Stopping execution during {run_name}: {i_progress + 1}/{int(repeat_count)}')
                break

            phase = WorkflowPhase(
                run_id=run_id,
                name="main",
                repeat_index=i_progress + 1,
                start_time=datetime.now()
            )
            db.session.add(phase)
            db.session.flush()
            phase_id = phase.id
            db.session.commit()

            if self.logger:
                self.logger.info(f'Executing {run_name} experiment: {i_progress + 1}/{int(repeat_count)}')
            progress = (i_progress + 1) * 100 / int(repeat_count) - 0.1
            self._emit_progress(progress, iteration=i_progress + 1, total=int(repeat_count))

            # Optimizer for UI
            if optimizer:
                try:
                    parameters = optimizer.suggest(n=batch_size)

                    if parameters is None or len(parameters) == 0:
                        self.logger.info("No parameters suggested by optimizer.")
                        raise ValueError("No parameters suggested by optimizer.")

                    if self.logger:
                        self.logger.info(f'Parameters: {parameters}')
                    # Re-fetch phase to update
                    phase = db.session.get(WorkflowPhase, phase_id)
                    phase.parameters = sanitize_for_json(parameters)
                    db.session.commit() # Commit parameters early? Or wait? Let's commit to be safe if exec_steps crashes

                    output = await self.exec_steps(script, "script",  phase_id, kwargs_list=parameters)
                    if output:
                        optimizer.observe(output)
                        
                    else:
                        if self.logger:
                            self.logger.info('No output from script')


                except Exception as e:
                    if self.logger:
                        self.logger.info(f'Optimization error: {e}')
                    break
            else:

                output = await self.exec_steps(script, "script", phase_id, batch_size=batch_size)

            phase = db.session.get(WorkflowPhase, phase_id)
            if output:
                # print("output: ", output)
                output_list.extend(output)
                if self.logger:
                    self.logger.info(f'Output value: {output}')
                phase.outputs = sanitize_for_json(output)

            phase.end_time = datetime.now()
            db.session.commit()

            # save results
            if not script.python_script and any(output_list):
                if i_progress == 0:
                    self._save_results(filename, arg_types, return_list, output_list, output_path)
                else:
                    self._save_results_last_row(filename, arg_types, return_list, output_list, output_path)

            if optimizer and self._check_early_stop(output, objectives):
                if self.logger:
                    self.logger.info('Early stopping')
                break
                

        return output_list

    def _save_results(self, filename, arg_type, return_list, output_list, output_path):
        """Save the results to the filename"""
        file_path = os.path.join(output_path, filename)
        df = pd.DataFrame(output_list)
        # output_columns = list(arg_type.keys()) + list(return_list)
        # df = df.reindex(columns=output_columns)

        # print(f'save df {df} to {file_path}')
        df.to_csv(file_path, index=False)

        if self.logger:
            self.logger.info(f'Results saved to {file_path}')

    def _save_results_last_row(self, filename, arg_type, return_list, output_list, output_path):
        """
        Save the last row to the filename. If the file does not exist, create it with header.
        """
        file_path = os.path.join(output_path, filename)
        df = pd.DataFrame([output_list[-1]])

        df.to_csv(file_path,
                  mode="a",
                  header=not os.path.exists(file_path),
                  index=False,
                  )

        if self.logger:
            self.logger.info(f'Append to results saved to {file_path}')

    def _emit_progress(self, progress, **kwargs):
        self.last_progress = progress
        if 'iteration' in kwargs:
            self.last_iteration = kwargs['iteration']
        if 'total' in kwargs:
            self.last_total = kwargs['total']
            
        if progress == 100 or progress == 0:
            self.last_iteration = None
            self.last_total = None
            
        payload = {'progress': progress}
        payload.update(kwargs)
        self.socketio.emit('progress', payload)

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
