import ast
import builtins
import re
import uuid
from typing import Dict

class ScriptEditor:
    def __init__(self, script):
        self.script = script

    @property
    def currently_editing_script(self):
        return self.script.script_dict[self.script.editing_type]

    @currently_editing_script.setter
    def currently_editing_script(self, value):
        self.script.script_dict[self.script.editing_type] = value

    @property
    def currently_editing_order(self):
        return self.script.id_order[self.script.editing_type]

    @currently_editing_order.setter
    def currently_editing_order(self, value):
        self.script.id_order[self.script.editing_type] = value

    @staticmethod
    def validate_function_name(name):
        import keyword
        name = re.sub(r'\W|^(?=\d)', '_', name)
        if keyword.iskeyword(name):
            name += '_'
        return name

    def find_by_uuid(self, uuid_val):
        for stype in self.script.script_dict:
            for action in self.script.script_dict[stype]:
                if action['uuid'] == int(uuid_val):
                    return action

    def _convert_type(self, args, arg_types):
        if arg_types in ["list", "tuple", "set"]:
            try:
                args = ast.literal_eval(args)
                return args
            except Exception:
                pass
        if type(arg_types) is not list:
            arg_types = [arg_types]
        for arg_type in arg_types:
            if isinstance(arg_type, str) and arg_type.startswith("Enum:"):
                 continue
            try:
                args = eval(f"{arg_type}('{args}')")
                return
            except Exception:
                pass
        raise TypeError(f"Input type error: cannot convert '{args}' to {arg_type}.")

    def update_by_uuid(self, uuid, args, output, batch_action=False, consolidate_batch_args=False):
        action = self.find_by_uuid(uuid)
        if not action:
            return
        arg_types = action['arg_types']
        if type(action['args']) is dict:
            self.eval_list(args, arg_types)
        action['args'] = args
        action['return'] = output
        action['batch_action'] = batch_action
        action['consolidate_batch_args'] = consolidate_batch_args

    @staticmethod
    def eval_list(args, arg_types):
        for arg in args:
            if arg not in arg_types:
                continue
            arg_type = arg_types[arg]
            if isinstance(arg_type, str) and arg_type.startswith("Enum:"):
                continue
            if arg_type in ["list", "tuple", "set"]:
                if isinstance(args[arg], str) and not args[arg].startswith("#"):
                    convert_type = getattr(builtins, arg_type)
                    try:
                        output = ast.literal_eval(args[arg])
                        if type(output) not in [list, tuple, set]:
                            output = [output]
                        args[arg] = convert_type(output)
                    except ValueError:
                        _list = ''.join(args[arg]).split(',')
                        args[arg] = convert_type([s.strip() for s in _list])
                    except SyntaxError:
                        args[arg] = [item.strip() for item in args[arg].split(",") if item.strip()]

    def _sort(self, script_type):
        if len(self.script.id_order[script_type]) > 0:
            for action in self.script.script_dict[script_type]:
                for i in range(len(self.script.id_order[script_type])):
                    if action['id'] == int(self.script.id_order[script_type][i]):
                        action['id'] = i + 1
                        break
            self.script.id_order[script_type].sort(key=int)
            if not int(self.script.id_order[script_type][-1]) == len(self.script.script_dict[script_type]):
                new_order = list(range(1, len(self.script.script_dict[script_type]) + 1))
                self.script.id_order[script_type] = [str(i) for i in new_order]
            self.script.script_dict[script_type].sort(key=lambda x: int(x['id']))

    def sort_actions(self, script_type=None):
        if script_type:
            self._sort(script_type)
        else:
            for i in self.script.stypes:
                self._sort(i)

    def add_action(self, action: dict, insert_position=None):
        current_len = len(self.currently_editing_script)
        action_to_add = action.copy()
        action_to_add['id'] = current_len + 1
        action_to_add['uuid'] = uuid.uuid4().fields[-1]
        self.currently_editing_script.append(action_to_add)
        self._insert_action(insert_position, current_len)
        self.script.update_time_stamp()

    def add_variable(self, statement, variable, variable_type, insert_position=None):
        variable = self.validate_function_name(variable)
        convert_type = getattr(builtins, variable_type)
        if isinstance(statement, str) and statement.startswith("#"):
            pass
        elif variable_type == "bool":
            statement = True if statement.lower() in ["true", "y", "t", "yes"] else False
        else:
            statement = convert_type(statement)
        current_len = len(self.currently_editing_script)
        uid = uuid.uuid4().fields[-1]
        action = {"id": current_len + 1, "instrument": 'variable', "action": variable,
                        "args": {"statement": 'None' if statement == '' else statement}, "return": '', "uuid": uid,
                        "arg_types": {"statement": variable_type}}
        self.currently_editing_script.append(action)
        self._insert_action(insert_position, current_len)
        self.script.update_time_stamp()

    def add_math_variable(self, statement, math_variable, insert_position=None):
        math_variable = self.validate_function_name(math_variable)
        current_len = len(self.currently_editing_script)
        uid = uuid.uuid4().fields[-1]
        action = {"id": current_len + 1, "instrument": 'math_variable', "action": math_variable,
                        "args": {"statement": 'None' if statement == '' else statement}, "return": '', "uuid": uid,
                        "arg_types": {"statement": 'float'}}
        self.currently_editing_script.append(action)
        self._insert_action(insert_position, current_len)
        self.script.update_time_stamp()

    def add_input_action(self, statement, variable, variable_type, insert_position=None):
        current_len = len(self.currently_editing_script)
        uid = uuid.uuid4().fields[-1]
        action = {"id": current_len + 1, "instrument": 'input', "action": variable,
                  "args": {"statement": statement, "variable": variable}, "return": variable, "uuid": uid,
                  "arg_types": {"statement": variable_type}}
        self.currently_editing_script.append(action)
        self._insert_action(insert_position, current_len)
        self.script.update_time_stamp()

    def _insert_action(self, insert_position, current_len, action_len:int=1):
        if not len(self.currently_editing_order) == current_len:
            self.currently_editing_order = list(range(1, current_len + action_len + 1))
        if insert_position is None:
            self.currently_editing_order.extend([str(current_len + i + 1) for i in range(action_len)])
        else:
            index = int(insert_position) - 1
            self.currently_editing_order[index:index] = [str(current_len + i + 1) for i in range(action_len)]
            self.sort_actions()

    def get_added_variables(self, before_id: int = None):
        script_list = self.currently_editing_script
        if before_id is not None:
            script_list = [a for a in script_list if a['id'] < before_id]
        return self._collect_added_variables(script_list)

    def _collect_added_variables(self, script_list):
        vars_dict = {}
        for action in script_list:
            if action["instrument"] == "variable":
                vars_dict[action["action"]] = action["arg_types"]["statement"]
            elif action["instrument"] == "math_variable":
                vars_dict[action["action"]] = action["arg_types"]["statement"]
            if "workflow" in action and isinstance(action["workflow"], list):
                vars_dict.update(self._collect_added_variables(action["workflow"]))
        return vars_dict

    def get_output_variables(self, before_id: int = None):
        script_list = self.currently_editing_script
        if before_id is not None:
            script_list = [a for a in script_list if a['id'] < before_id]
        return self._collect_output_variables(script_list)

    def _collect_output_variables(self, script_list):
        output_vars = {}
        for action in script_list:
            for output_name in self._return_names(action.get("return")):
                output_vars[output_name] = "function_output"
            if "workflow" in action and isinstance(action["workflow"], list):
                output_vars.update(self._collect_output_variables(action["workflow"]))
        return output_vars

    def get_variables(self, before_id: int = None):
        output_variables: Dict[str, str] = self.get_output_variables(before_id=before_id)
        added_variables = self.get_added_variables(before_id=before_id)
        output_variables.update(added_variables)
        return output_variables

    @staticmethod
    def _return_names(return_value):
        if isinstance(return_value, list):
            return [name for name in return_value if name]
        return [return_value] if return_value else []

    @staticmethod
    def _format_return_target(return_value):
        if isinstance(return_value, list):
            names = [name if name else "_" for name in return_value]
            return ", ".join(names) if any(name != "_" for name in names) else ""
        return return_value or ""

    def get_autocomplete_variables(self, before_id: int = None) -> list:
        variables = self.get_variables(before_id=before_id)
        variable_list = list(variables.keys())
        editing_type = self.script.editing_type or 'script'
        if editing_type in self.script.script_dict:
             config_vars, _ = self.config(editing_type, before_id=before_id)
             for var in config_vars:
                 variable_list.append(f"#{var}")
        return variable_list

    def validate_variables(self, kwargs, arg_types: dict = None):
        output_variables: Dict[str, str] = self.get_variables()
        for key, value in kwargs.items():
            if isinstance(value, str):
                if value in output_variables:
                    var_type = output_variables[value]
                    kwargs[key] = f"#{value}"
                elif value.startswith("#"):
                    kwargs[key] = f"#{self.validate_function_name(value[1:])}"
                else:
                    type_hint = arg_types.get(key, "") if arg_types else ""
                    valid_types = type_hint if isinstance(type_hint, list) else [type_hint] if type_hint else []
                    is_converted = False
                    try:
                        converted = ast.literal_eval(value)
                        if valid_types:
                            if type(converted).__name__ in valid_types:
                                kwargs[key] = converted
                                is_converted = True
                        else:
                            if isinstance(converted, (int, float, bool, list, tuple, dict, set)):
                                kwargs[key] = converted
                                is_converted = True
                    except (ValueError, SyntaxError):
                        pass
                    if not is_converted and valid_types:
                        for t_name in valid_types:
                            if t_name in ['str', 'any', 'NoneType']: continue
                            if t_name in ['bool', 'list', 'tuple', 'dict', 'set']: continue
                            try:
                                converter = getattr(builtins, t_name, None)
                                if converter:
                                    kwargs[key] = converter(value)
                                    break
                            except Exception:
                                pass
        return kwargs

    def add_logic_action(self, logic_type: str, statement, insert_position=None, **kwargs):
        current_len = len(self.currently_editing_script)
        uid = uuid.uuid4().fields[-1]
        logic_dict = {
            "if":
                [
                    {"id": current_len + 1, "instrument": 'if', "action": 'if',
                     "args": {"statement": 'True' if statement == '' else statement},
                     "return": '', "uuid": uid, "arg_types": {"statement": ''}},
                    {"id": current_len + 2, "instrument": 'if', "action": 'else', "args": {}, "return": '',
                     "uuid": uid},
                    {"id": current_len + 3, "instrument": 'if', "action": 'endif', "args": {}, "return": '',
                     "uuid": uid},
                ],
            "while":
                [
                    {"id": current_len + 1, "instrument": 'while', "action": 'while',
                     "args": {"statement": 'False' if statement == '' else statement}, "return": '', "uuid": uid,
                     "arg_types": {"statement": ''}},
                    {"id": current_len + 2, "instrument": 'while', "action": 'endwhile', "args": {}, "return": '',
                     "uuid": uid},
                ],
            "wait":
                [
                    {"id": current_len + 1, "instrument": 'wait', "action": "wait",
                     "args": {"statement": 1 if statement == '' else statement},
                     "return": '', "uuid": uid, "arg_types": {"statement": "float"},
                     "batch_action": kwargs.get("batch_action", False)},
                ],
            "repeat":
                [
                    {"id": current_len + 1, "instrument": 'repeat', "action": "repeat",
                     "args": {"statement": 1 if statement == '' else statement}, "return": '', "uuid": uid,
                     "arg_types": {"statement": "int"}},
                    {"id": current_len + 2, "instrument": 'repeat', "action": 'endrepeat',
                     "args": {}, "return": '', "uuid": uid},
                ],
            "pause":
                [
                    {"id": current_len + 1, "instrument": 'pause', "action": "pause",
                     "args": {"statement": 1 if statement == '' else statement}, "return": '', "uuid": uid,
                     "arg_types": {"statement": "str"}}
                ],
            "comment":
                [
                    {"id": current_len + 1, "instrument": 'comment', "action": "comment",
                     "args": {"statement": statement}, "return": '', "uuid": uid,
                     "arg_types": {"statement": "str"}}
                ],
        }
        action_list = logic_dict[logic_type]
        self.currently_editing_script.extend(action_list)
        self._insert_action(insert_position, current_len, len(action_list))
        self.script.update_time_stamp()

    def delete_action(self, action_id: int):
        uid = next((action['uuid'] for action in self.currently_editing_script if action['id'] == int(action_id)), None)
        id_to_be_removed = [action['id'] for action in self.currently_editing_script if action['uuid'] == uid]
        order = self.currently_editing_order
        script_list = self.currently_editing_script
        self.currently_editing_order = [i for i in order if int(i) not in id_to_be_removed]
        self.currently_editing_script = [action for action in script_list if action['id'] not in id_to_be_removed]
        self.sort_actions()
        self.script.update_time_stamp()

    def duplicate_action(self, action_id: int):
        action_to_duplicate = next((action for action in self.currently_editing_script if action['id'] == int(action_id)),
                                   None)
        if action_to_duplicate is None:
            raise ValueError("Action not found: Unable to duplicate the action with ID", action_id)
        insert_id = action_to_duplicate.get("id")
        self.add_action(action_to_duplicate)
        if action_to_duplicate is not None:
            for action in self.currently_editing_script:
                if action['id'] > insert_id:
                    action['id'] += 1
            self.currently_editing_script[-1]['id'] = insert_id + 1
            self.sort_actions()
            self.script.update_time_stamp()

    def config(self, stype, before_id: int = None):
        configure = []
        variables = self.get_variables(before_id=before_id)
        config_type_dict = {}
        for action in self.script.script_dict[stype]:
            args = action['args']
            if args is not None:
                if type(args) is not dict:
                    if type(args) is str and args.startswith("#"):
                        key = args[1:]
                        if key not in (*variables, *configure):
                            configure.append(key)
                            config_type_dict[key] = action['arg_types']
                else:
                    if action['instrument'] == "math_variable":
                        pattern = r"#([A-Za-z_][A-Za-z0-9_]*)"
                        vars_found = re.findall(pattern, args['statement'])
                        for key in vars_found:
                            if key not in (*variables, *configure):
                                configure.append(key)
                                config_type_dict[key] = action['arg_types']['statement']
                    else:
                        for arg in args:
                            if type(args[arg]) is str and args[arg].startswith("#"):
                                key = args[arg][1:]
                                if key not in (*variables, *configure):
                                    configure.append(key)
                                    if arg in action['arg_types']:
                                        if action['arg_types'][arg] == '':
                                            config_type_dict[key] = "any"
                                        else:
                                            config_type_dict[key] = action['arg_types'][arg]
                                    else:
                                        config_type_dict[key] = "any"
        return configure, config_type_dict

    def config_return(self):
        output_vars = self._collect_output_variables(self.script.script_dict['script'])
        return_list = set(output_vars.keys())
        output_str = "{"
        for i in return_list:
            output_str += "'" + i + "':" + i + ","
        output_str += "}"
        return output_str, list(return_list)

