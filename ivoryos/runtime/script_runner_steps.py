import re
from datetime import datetime
from typing import Any, Dict, List

from ivoryos.runtime.control_flow import validate_and_nest_control_flow
from ivoryos.runtime.runner_runtime import HumanInterventionRequired, ensure_deck, global_state, pause
from ivoryos.models import WorkflowStep, db
from ivoryos.parsers.returns import store_return_value
from ivoryos.parsers.serialize import sanitize_for_json
from ivoryos.utils.decorators import BUILDING_BLOCKS


class ScriptRunnerStepMixin:
    async def _execute_steps_batched(self, steps: List[Dict], contexts: List[Dict[str, Any]], phase_id, section_name, arg_contexts:List[Dict[str, Any]] = None):
        """
        Execute a list of steps for multiple samples, batching where appropriate.
        """
        for step in steps:
            action = step["action"]
            instrument = step["instrument"]
            action_id = step["id"]
            if action == "if":
                await self._execute_if_batched(step, contexts, phase_id=phase_id, step_index=action_id,
                                               section_name=section_name)
            elif action == "repeat":
                await self._execute_repeat_batched(step, contexts, phase_id=phase_id, step_index=action_id,
                                                   section_name=section_name)
            elif action == "while":
                await self._execute_while_batched(step, contexts, phase_id=phase_id, step_index=action_id,
                                                  section_name=section_name)
            elif instrument == "variable":
                await self._execute_variable_batched(step, contexts, phase_id=phase_id, step_index=action_id,
                                                     section_name=section_name)
                # print("Variable executed", "current context", contexts)
            elif instrument == "math_variable":
                await self._execute_variable_batched(step, contexts, phase_id=phase_id, step_index=action_id,
                                                     section_name=section_name)
            elif instrument == "input":
                await self._execute_variable_batched(step, contexts, phase_id=phase_id, step_index=action_id,
                                                     section_name=section_name)
            elif instrument == "workflows":
                # Recursively logic for nested workflows
                # print(step.get("workflow", []))
                workflow_steps = validate_and_nest_control_flow(step.get("workflow", []))
                if workflow_steps:
                    if self.socketio:
                        self.socketio.emit('log', {'message': f"Entering workflow: {action} with args: {step.get('args', {})}"})
                    
                    # Inject parameters into context
                    
                    # For batched contexts:
                    workflow_contexts = []
                    for context in contexts:
                        substituted_args =  self._substitute_params( step.get("args", {}), context)
                        # args = step.get("args", {})
                        # for key, value in args.items():
                        #      if isinstance(value, str) and value.startswith("#"):
                        #          context[key] = context.get(value[1:])
                        #      else:
                        #          context[key] = value
                        workflow_contexts.append(substituted_args)
                        # print("context", context)
                        # print("substituted_args", substituted_args)
                    if step.get("batch_action", False):
                        await self._execute_steps_batched(workflow_steps, [contexts[0]], arg_contexts=[workflow_contexts[0]], phase_id=phase_id, section_name=f"{section_name}-{action_id-1}")
                        if len(contexts) > 1:
                            # Propagate any new values from first context to others
                            for key, value in contexts[0].items():
                                for context in contexts[1:]:
                                    if key not in context:
                                        context[key] = value

                    else:
                        for context, workflow_context in zip(contexts, workflow_contexts):
                            # sequentially execute workflow steps
                            await self._execute_steps_batched(workflow_steps, [context], arg_contexts=[workflow_context], phase_id=phase_id,
                                                              section_name=f"{section_name}-{action_id - 1}")

            else:
                # Regular action - check if batch
                if step.get("batch_action", False):
                    # Execute once for all samples
                    consolidate_keys = step.get("consolidate_batch_args", [])
                    if consolidate_keys:
                        # Normalize to list if boolean (backward compat)
                        if isinstance(consolidate_keys, bool):
                            consolidate_keys = [k for k, v in step.get("arg_types", {}).items() if v == "list"]
                        
                        # Aggregate arguments
                        aggregated_args = {}
                        
                        # Initialize based on first context substitution to get keys
                        first_args = self._substitute_params(step["args"], contexts[0])
                        
                        # Identify keys to consolidate
                        # Must be in consolidate_keys AND be a list type (user requirement)
                        target_keys = []
                        arg_types = step.get("arg_types", {})
                        for key in consolidate_keys:
                            if arg_types.get(key) == "list" or key in first_args: # weak check if arg_types invalid
                                target_keys.append(key)
                        
                        # Initialize aggregated args
                        for key, val in first_args.items():
                             if key in target_keys:
                                 aggregated_args[key] = []
                             else:
                                 aggregated_args[key] = val # For non-consolidated args, keep first value

                        # Iterate all contexts to collect lists
                        for ctx in contexts:
                            sub_args = self._substitute_params(step["args"], ctx)
                            for key in target_keys:
                                if key in sub_args:
                                    val = sub_args[key]
                                    if isinstance(val, (list, tuple)):
                                        aggregated_args[key].extend(val)
                                    else:
                                        aggregated_args[key].append(val)
                        
                        await self._execute_action_once(step, contexts[0], arg_contexts=arg_contexts, phase_id=phase_id, step_index=action_id,
                                                            section_name=section_name, override_args=aggregated_args)

                    else:
                        await self._execute_action_once(step, contexts[0], arg_contexts=arg_contexts, phase_id=phase_id, step_index=action_id,
                                                            section_name=section_name)

                else:
                    # Execute for each sample
                    if arg_contexts:
                        for context, arg_context in zip(contexts, arg_contexts):
                            await self._execute_action(step, context, arg_contexts=arg_context, phase_id=phase_id, step_index=action_id,
                                                       section_name=section_name)
                    else:
                        for context in contexts:
                            await self._execute_action(step, context, phase_id=phase_id, step_index=action_id,
                                                       section_name=section_name)
                            self.pause_event.wait()



    async def _execute_if_batched(self, step: Dict, contexts: List[Dict[str, Any]], phase_id, step_index, section_name):
        """Execute if/else block for multiple samples."""
        # Evaluate condition for each sample
        for context in contexts:
            condition = self._evaluate_condition(step["args"]["statement"], context)
            if self.logger:
                self.logger.info(f"Evaluating if {step['args']['statement']}: {condition}")
            if condition:
                await self._execute_steps_batched(step["if_block"], [context], phase_id=phase_id, section_name=section_name)
            else:
                await self._execute_steps_batched(step["else_block"], [context], phase_id=phase_id, section_name=section_name)


    async def _execute_repeat_batched(self, step: Dict, contexts: List[Dict[str, Any]], phase_id, step_index, section_name):
        """Execute repeat block for multiple samples."""
        for context in contexts:
            times = step["args"].get("statement", 1)

            if isinstance(times, str) and times.startswith("#"):
                times = context.get(times[1:])
            # print("repeat times", times, type(times))
            for i in range(times):
                # Add repeat index to all contexts
                # for context in contexts:
                #     context["repeat_index"] = i

                await self._execute_steps_batched(step["repeat_block"], [context], phase_id=phase_id, section_name=section_name)


    async def _execute_while_batched(self, step: Dict, contexts: List[Dict[str, Any]], phase_id, step_index, section_name):
        """Execute while block for multiple samples."""
        max_iterations = step["args"].get("max_iterations", 1000)
        active_contexts = contexts.copy()
        iteration = 0

        while active_contexts and self.stop_current_event.is_set() is False:
            # Filter contexts that still meet the condition
            still_active = []

            for context in active_contexts:
                condition = self._evaluate_condition(step["args"]["statement"], context)
                if self.logger:
                    self.logger.info(f"Evaluating while {step['args']['statement']}: {condition}")
                if condition:
                    context["while_index"] = iteration
                    still_active.append(context)

            if not still_active:
                break

            # Execute for contexts that are still active
            await self._execute_steps_batched(step["while_block"], still_active, phase_id=phase_id, section_name=section_name)
            active_contexts = still_active
            iteration += 1

        # if iteration >= max_iterations:
        #     raise RuntimeError(f"While loop exceeded max iterations ({max_iterations})")

    async def _execute_action(self, step: Dict, context: Dict[str, Any], arg_contexts: Dict[str, Any]=None, phase_id=1, step_index=1, section_name=None, override_args=None):
        """Execute a single action with parameter substitution."""
        # Substitute parameters in args
        result = None
        if self.stop_current_event.is_set():
            return context
        
        if override_args is not None:
            substituted_args = override_args
        elif arg_contexts:
            substituted_args = self._substitute_params(step["args"], arg_contexts)
        else:
            substituted_args = self._substitute_params(step["args"], context)

        # Get the component and method
        instrument = step.get("instrument", "")
        action = step["action"]
        if instrument and "." in instrument:
            instrument_type, instrument = instrument.split(".")
        else:
            instrument_type = ""
        current_deck = ensure_deck(required=instrument_type == "deck")
        # Execute the action
        while True:
            step_db = WorkflowStep(
                phase_id=phase_id,
                step_index=step_index,
                method_name=action,
                start_time=datetime.now(),
            )
            db.session.add(step_db)
            db.session.flush()
            step_id = step_db.id # Save ID
            db.session.commit() # Commit early to release lock
            
            try:

                if self.logger:
                    self.logger.info(f"Executing '{instrument}.{action}' with args {substituted_args}")
                
                section_id = f"{section_name}-{step_index-1}"
                self.last_execution_section = section_id
                self.socketio.emit('execution', {'section': section_id})
                if action == "wait":
                    duration = float(substituted_args["statement"])
                    self.safe_sleep(duration)

                elif action == "pause":
                    msg = substituted_args.get("statement", "")
                    pause(msg)

                elif action == "comment":
                    msg = substituted_args.get("statement", "")
                    if self.logger:
                        self.logger.info(f"Comment: {msg}")

                elif instrument_type == "deck" and hasattr(current_deck, instrument):
                    component = getattr(current_deck, instrument)
                    if "_(setter)" in action:
                        action = action.replace("_(setter)", "")
                    if hasattr(component, action):
                        attr = getattr(component, action)

                        if callable(attr):
                            # Execute and handle return value
                            if step.get("coroutine", False):
                                result = await attr(**substituted_args)
                            else:
                                result = attr(**substituted_args)
                        else:
                            # Handle property setter/getter
                            if "value" in substituted_args:
                                setattr(component, action, substituted_args["value"])
                                result = substituted_args["value"]
                            else:
                                result = attr
                        # Store return value if specified
                        # return_var = step.get("return", "")
                        # if return_var:
                        #     context[return_var] = result

                elif instrument_type == "blocks" and instrument in BUILDING_BLOCKS.keys():
                    # Inject all block categories
                    method_collection = BUILDING_BLOCKS[instrument]
                    if action in method_collection.keys():
                        method = method_collection[action]["func"]

                        # Execute and handle return value
                        # print(step.get("coroutine", False))
                        if step.get("coroutine", False):
                            result = await method(**substituted_args)
                        else:
                            result = method(**substituted_args)

                        # # Store return value if specified
                        # return_var = step.get("return", "")
                        # if return_var:
                        #     context[return_var] = result
                else:
                    module = global_state.defined_variables.get(instrument, None)
                    if module is None:
                        raise ValueError(f"Unknown instrument '{instrument}'")
                    method = getattr(module, action)
                    if step.get("coroutine", False):
                        result = await method(**substituted_args)
                    else:
                        result = method(**substituted_args)
                        # Store return value if specified
                return_var = step.get("return", "")
                if return_var and result is not None:
                    store_return_value(context, arg_contexts, return_var, result)

            except HumanInterventionRequired as e:
                self.logger.warning(f"Human intervention required: {e}")
                self.socketio.emit('human_intervention', {'message': str(e)})
                # Instead of auto-resume, explicitly stay paused until user action
                # step.run_error = False
                self.toggle_pause()

            except Exception as e:
                self.logger.error(f"Error during script execution: {e}")
                self.socketio.emit('error', {'message': str(e)})
                
                # Update error status in a fresh transaction
                step_db = db.session.get(WorkflowStep, step_id)
                step_db.run_error = True
                db.session.commit()
                
                self.toggle_pause()
            finally:
                step_db = db.session.get(WorkflowStep, step_id)
                step_db.end_time = datetime.now()
                step_db.output = sanitize_for_json(context) # todo if change so output doesnt include all input values as well then need to update ivoryos.routes.data.data.download_workflow_steps_data_csv
                db.session.commit()

                self.pause_event.wait()
            
            if self.retry:
                # only retry if it errored out
                if step_db.run_error:
                    self.retry = False
                    continue
                if self.socketio:
                    self.socketio.emit('error_resolved')
                self.retry = False
            
            break

        return context

    async def _execute_action_once(self, step: Dict, context: Dict[str, Any], arg_contexts, phase_id, step_index, section_name, override_args=None):
        """Execute a batch action once (not per sample)."""
        # print(f"Executing batch action: {step['action']}")
        return await self._execute_action(step, context, arg_contexts=arg_contexts, phase_id=phase_id, step_index=step_index, section_name=section_name, override_args=override_args)

    @staticmethod
    def _substitute_params(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Substitute parameter placeholders like #param_1 with actual values."""
        substituted = {}

        def substitute_vars(value: str, context: Dict[str, Any]) -> Any:
            # Replace placeholders of the form `#var` in a string with values from a context.
            def replacer(match):
                var_name = match.group(1)
                if var_name not in context:
                    raise KeyError(f"Missing context value for '{var_name}'")
                return str(context[var_name])

            return re.sub(r"#(\w+)", replacer, value)

        for key, value in args.items():
            if isinstance(value, str) and value.startswith("#"):
                param_name = value[1:]  # Remove '#'
                substituted[key] = context.get(param_name)
            elif isinstance(value, str):
                # for comment need to substitue #args in the arg with the actual values
                substituted[key] = substitute_vars(value, context)
            else:
                substituted[key] = value

        return substituted

    @staticmethod
    def _evaluate_condition(condition_str: str, context: Dict[str, Any]) -> bool:
        """
        Safely evaluate a condition string with context variables.
        """
        # Create evaluation context with all variables
        eval_context = {}

        # Substitute variables in the condition string
        if isinstance(condition_str, str):
            substituted = condition_str
            for key, value in context.items():
                # Replace #variable with actual variable name for eval
                substituted = substituted.replace(f"#{key}", key)
                # Add variable to eval context
                eval_context[key] = value

            try:
                # Safe evaluation with variables in scope
                result = eval(substituted, {"__builtins__": {}}, eval_context)
                return bool(result)
            except Exception as e:
                raise ValueError(f"Error evaluating condition '{condition_str}': {e}")
        elif isinstance(condition_str, bool):
            return condition_str
        else:
            raise condition_str

    def _check_early_stop(self, output, objectives):
        for row in output:
            all_met = True
            for obj in objectives:
                name = obj['name']
                minimize = obj.get('minimize', True)
                threshold = obj.get('early_stop', None)

                if threshold is None:
                    all_met = False
                    break# Skip if no early stop defined

                value = row[name]
                if minimize and value > threshold:
                    all_met = False
                    break
                elif not minimize and value < threshold:
                    all_met = False
                    break

            if all_met:
                return True  # At least one row meets all early stop thresholds

        return False  # No row met all thresholds

    def prompt_user(self, prompt: str, var_type) -> str:
        result = None
        if self.socketio:
            self.waiting_for_input = True
            self.input_value = None
            self.socketio.emit('request_input', {
                'prompt': prompt,
                'type': var_type
            })
            if self.logger:
                self.logger.info(f"Requesting input: {prompt} ({var_type})")

            # Pause and wait for input
            self.pause_event.clear()
            self.pause_event.wait()

            # Process result
            result = self.input_value
            self.waiting_for_input = False

            # Log result
            if self.logger:
                self.logger.info(f"Input received: {result}")
        else:
            if self.logger:
                self.logger.warning("No socketio connection, skipping input")
        return result

    async def _execute_variable_batched(self, step: Dict, contexts: List[Dict[str, Any]], phase_id, step_index,
                                        section_name):
        """Execute variable assignment for multiple samples."""
        var_name = step["action"]  # "vial" in your example
        var_value = step["args"]["statement"]
        arg_type = step["arg_types"]["statement"]

        for context in contexts:
            if step["instrument"] == "input":
                value = self.prompt_user(var_value, arg_type)
                context[var_name] = value
                continue

            # Substitute any variable references in the value
            if isinstance(var_value, str):
                substituted_value = var_value

                # Replace all variable references (with or without #) with their values
                for key, val in context.items():
                    # Handle both #variable and variable (without #)
                    substituted_value = substituted_value.replace(f"#{key}", str(val))
                    # For expressions like "vial+10", replace variable name directly
                    # Use word boundaries to avoid partial matches
                    import re
                    substituted_value = re.sub(r'\b' + re.escape(key) + r'\b', str(val), substituted_value)

                # Handle based on type
                if arg_type == "float":
                    try:
                        # Evaluate as expression (e.g., "10.0+10" becomes 20.0)
                        result = eval(substituted_value, {"__builtins__": {}}, {})
                        context[var_name] = float(result)
                    except:
                        # If eval fails, try direct conversion
                        context[var_name] = float(substituted_value)

                elif arg_type == "int":
                    try:
                        result = eval(substituted_value, {"__builtins__": {}}, {})
                        context[var_name] = int(result)
                    except:
                        context[var_name] = int(substituted_value)

                elif arg_type == "bool":
                    try:
                        # Evaluate boolean expressions
                        result = eval(substituted_value, {"__builtins__": {}}, {})
                        context[var_name] = bool(result)
                    except:
                        context[var_name] = substituted_value.lower() in ['true', '1', 'yes']

                else:  # "str"
                    # For strings, check if it looks like an expression (including f-strings)
                    # todo add to the list '{', '}' if want those to show up in the string, but then fstring logic might not work? needs testing
                    if any(char in substituted_value for char in ['+', '-', '*', '/', '>', '<', '=', '(', ')']) \
                            or substituted_value.startswith('f"') or substituted_value.startswith("f'") \
                            or substituted_value.startswith('"') or substituted_value.startswith("'"):
                        try:
                            # Try to evaluate as expression
                            result = eval(substituted_value, {"__builtins__": {}}, context)
                            context[var_name] = result
                        except:
                            # If eval fails, store as string
                            context[var_name] = substituted_value
                    else:
                        context[var_name] = substituted_value
            else:
                # Direct numeric or boolean value
                context[var_name] = var_value
