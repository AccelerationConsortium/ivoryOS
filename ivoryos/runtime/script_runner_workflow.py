import asyncio
import logging
import math
import os
import time
from datetime import datetime

import pandas as pd

from ivoryos.runtime.control_flow import validate_and_nest_control_flow
from ivoryos.runtime.live_config import DONE, FAILED, STOPPED, LiveConfig
from ivoryos.runtime.run_events import EARLY_STOP, ROWS_NOT_RUN, outcome as run_outcome
from ivoryos.runtime.runner_runtime import ensure_deck, global_state, pause
from ivoryos.models import WorkflowRun, WorkflowPhase, db
from ivoryos.script import Script, ScriptEditor, ScriptRenderer
from ivoryos.parsers.serialize import sanitize_for_json


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
        # batch progress is reported against this list; left empty outside batch mode
        self.current_batch = results if int(batch_size or 1) > 1 else []
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
            run = WorkflowRun(name=run_name, platform=script.deck or "deck", start_time=datetime.now(),
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

            # set before anything can fail, since the run's record is closed with it below
            output_list = []
            # what happens besides the steps, and whether a stop leaves work undone
            self.run_events = []
            self.run_id = run_id
            self._cut_short = False
            try:
            # if True:
                global_state.runner_status = {"id":run_id, "type": "workflow"}
                # Run "prep" section once
                asyncio.run(self._run_actions(script, section_name="prep", run_id=run_id))
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
                error_msg = f"Error during script execution: {e.__str__()}"
                if self.logger:
                    self.logger.error(error_msg)
                if self.socketio:
                    self.socketio.emit('error', {'message': error_msg})
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

                # taken before the next task starts, which resets both
                status = run_outcome(error_flag, self._cut_short, self.stop_current_event.is_set())
                with self._events_lock:
                    # nothing recorded after this point belongs to this run
                    events, self.run_events, self.run_id = self.run_events, None, None

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
                run.status = status
                run.events = sanitize_for_json(events) or None

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
        # a stop without skipping cleanup: lift the stop so the cleanup steps can run
        if section_name == "cleanup" and self.stop_current_event.is_set():
            if self.logger:
                self.logger.info("Proceeding to cleanup after stop.")
            self.stop_current_event.clear()

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
        # Entries are taken a batch at a time, so the ones not reached yet can still
        # be edited while the run goes on; see ivoryos.runtime.live_config. Every
        # entry the run reaches becomes an iteration in table order, a failed one
        # included, so the iterations are the record of the table as it ran.
        live = LiveConfig(config, arg_type, converted=compiled)
        batch_size = int(batch_size)
        iteration = 0
        self.live_config = live
        self._emit_live_config(True)
        try:
            self._report_unrunnable_rows(live.problems(), ahead=True)
            while True:
                if self.stop_pending_event.is_set():
                    waiting = live.waiting()
                    if waiting:
                        # rows were left; a stop during the last one changes nothing
                        self._cut_short = True
                        if self.logger:
                            total = iteration + math.ceil(waiting / batch_size)
                            self.logger.info(f'Stopping execution during {run_name}: {iteration + 1}/{total}')
                    break
                batch, failed = live.start_batch(batch_size)
                for _, entry in failed:
                    iteration += 1
                    self._record_failed_row(run_id, iteration, entry)
                self._report_unrunnable_rows([(number, entry["reason"]) for number, entry in failed])
                if not batch:
                    break
                kwargs_list = [entry["values"] for entry in batch]
                iteration += 1
                total = iteration + math.ceil(live.waiting() / batch_size)
                if self.logger:
                    self.logger.info(f'Executing {iteration} of {total} with kwargs = {live.inputs(batch)}')
                progress = (iteration * 100 / total) - 0.1
                self._emit_progress(progress, iteration=iteration, total=total)

                phase = WorkflowPhase(
                    run_id=run_id,
                    name="main",
                    repeat_index=iteration,
                    parameters=sanitize_for_json(live.inputs(batch)),
                    start_time=datetime.now()
                )
                db.session.add(phase)
                db.session.flush()

                phase_id = phase.id
                db.session.commit()

                self.steps_cut_off = False
                try:
                    output = await self.exec_steps(script, "script", phase_id, kwargs_list=kwargs_list, batch_size=batch_size)
                except Exception as e:
                    self._close_failed_phase(phase_id, e)
                    raise
                # print(output)
                phase = db.session.get(WorkflowPhase, phase_id)
                if output:
                    # kwargs.update(output)
                    for output_dict in output:
                        output_list.append(output_dict)
                    phase.outputs = sanitize_for_json(output)
                if live.edited_while_running(batch):
                    # the values the last steps used are the ground truth
                    phase.parameters = sanitize_for_json(live.inputs(batch))
                phase.status = STOPPED if self.steps_cut_off else DONE
                phase.end_time = datetime.now()
                db.session.commit()
                for line in live.finish_batch(batch, stopped=self.steps_cut_off):
                    if self.logger:
                        self.logger.warning(line)

                # save results
            # if not script.python_script and any(output_list):
            #     if i == 0:
            #         self._save_results(filename, arg_type, return_list, output_list, output_path)
            #     else:
            #         self._save_results_last_row(filename, arg_type, return_list, output_list, output_path)
        finally:
            self.live_config = None
            self._emit_live_config(False)
            live.close()
            left = live.remaining()
            if left:
                # rows the run never reached have no iteration; this is their only record
                self.record_event(ROWS_NOT_RUN, f"{len(left)} row(s) of the table were not run.",
                                  rows=sanitize_for_json(left))

        return output_list

    def _record_failed_row(self, run_id, iteration, entry):
        """Keep a row whose values cannot run as a failed iteration in its place,
        with the values as entered and what is wrong with them."""
        now = datetime.now()
        db.session.add(WorkflowPhase(
            run_id=run_id, name="main", repeat_index=iteration,
            parameters=sanitize_for_json([dict(entry["text"])]),
            status=FAILED, error={"message": entry["reason"], "fields": entry["invalid"]},
            start_time=now, end_time=now,
        ))
        db.session.commit()

    def _close_failed_phase(self, phase_id, error):
        """Mark an iteration whose steps raised as failed, before the error ends the run."""
        try:
            db.session.rollback()
            phase = db.session.get(WorkflowPhase, phase_id)
            phase.status, phase.error, phase.end_time = FAILED, {"message": str(error)}, datetime.now()
            db.session.commit()
        except Exception:
            db.session.rollback()

    def _emit_live_config(self, editable):
        """Tell open pages whether the running task has a config table they can edit."""
        if self.socketio:
            self.socketio.emit('live_config', {'editable': editable})

    def _report_unrunnable_rows(self, rows, ahead=False):
        """Tell the user which config rows cannot run, and why.

        ``ahead`` is the check when the run starts, while the rows can still be
        fixed in the run's table; otherwise the rows were just reached and failed.
        """
        if not rows:
            return
        lines = [f"Row {number}: {reason}" for number, reason in rows]
        if ahead:
            title = "Some rows can't run as entered"
            intro = ("Fix them in the current run's table before the run reaches them, "
                     "or they will fail.")
        else:
            title = "Row failed" if len(rows) == 1 else "Rows failed"
            intro = "These rows could not run:"
        if self.logger:
            for line in lines:
                self.logger.warning(f"{title}. {line}")
        if self.socketio:
            self.socketio.emit('notice', {'title': title, 'message': "\n".join([intro, *lines])})

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
                self._cut_short = True
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
            self.steps_cut_off = False

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

                    output = await self.exec_steps(script, "script",  phase_id, kwargs_list=parameters, batch_size=batch_size)
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

            phase.status = STOPPED if self.steps_cut_off else DONE
            phase.end_time = datetime.now()
            db.session.commit()

            # save results
            # if not script.python_script and any(output_list):
            #     if i_progress == 0:
            #         self._save_results(filename, arg_types, return_list, output_list, output_path)
            #     else:
            #         self._save_results_last_row(filename, arg_types, return_list, output_list, output_path)

            if optimizer and self._check_early_stop(output, objectives):
                if self.logger:
                    self.logger.info('Early stopping')
                self.record_event(EARLY_STOP, "Every objective reached its threshold.")
                break

        if optimizer:
            try:
                plots = optimizer.get_plots('all')
                if isinstance(plots, dict) and "error" in plots:
                    # Don't save the error as plots: the data panel would render it as a plot card
                    if self.logger:
                        self.logger.warning(f'Could not generate optimizer plots: {plots["error"]}')
                elif plots:
                    plots_file_path = os.path.join(output_path, f"{filename.replace('.csv', '')}_plots.json")
                    import json
                    with open(plots_file_path, 'w') as f:
                        json.dump(plots, f)
                    if self.logger:
                        self.logger.info(f'Optimizer plots saved to {plots_file_path}')
            except Exception as e:
                if self.logger:
                    self.logger.warning(f'Could not save optimizer plots: {e}')

        return output_list

    # def _save_results(self, filename, arg_type, return_list, output_list, output_path):
    #     """Save the results to the filename"""
    #     file_path = os.path.join(output_path, filename)
    #     df = pd.DataFrame(output_list)
    #     # output_columns = list(arg_type.keys()) + list(return_list)
    #     # df = df.reindex(columns=output_columns)
    #
    #     # print(f'save df {df} to {file_path}')
    #     df.to_csv(file_path, index=False)
    #
    #     if self.logger:
    #         self.logger.info(f'Results saved to {file_path}')

    # def _save_results_last_row(self, filename, arg_type, return_list, output_list, output_path):
    #     """
    #     Save the last row to the filename. If the file does not exist, create it with header.
    #     """
    #     file_path = os.path.join(output_path, filename)
    #     df = pd.DataFrame([output_list[-1]])
    #
    #     df.to_csv(file_path,
    #               mode="a",
    #               header=not os.path.exists(file_path),
    #               index=False,
    #               )
    #
    #     if self.logger:
    #         self.logger.info(f'Append to results saved to {file_path}')

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
