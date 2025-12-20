import ast
try:
    from ast import unparse as ast_unparse
except ImportError:
    import astor
    ast_unparse = astor.to_source

import builtins
import json
import keyword
import re
import uuid
from datetime import datetime
from typing import Dict

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy_utils import JSONType

db = SQLAlchemy()


class User(db.Model, UserMixin):
    __tablename__ = 'user'
    # id = db.Column(db.Integer)
    username = db.Column(db.String(50), primary_key=True, unique=True, nullable=False)
    # email = db.Column(db.String)
    hashPassword = db.Column(db.String(255))

    # New columns for logo customization
    settings = db.Column(JSONType, nullable=True)

    # password = db.Column()
    def __init__(self, username, password):
        # self.id = id
        self.username = username
        # self.email = email
        self.hashPassword = password

    def get_id(self):
        return self.username


class Script(db.Model):
    __tablename__ = 'script'
    # id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), primary_key=True, unique=True)
    deck = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(50), nullable=True)
    script_dict = db.Column(JSONType, nullable=True)
    time_created = db.Column(db.String(50), nullable=True)
    last_modified = db.Column(db.String(50), nullable=True)
    id_order = db.Column(JSONType, nullable=True)
    editing_type = db.Column(db.String(50), nullable=True)
    author = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    # registered = db.Column(db.Boolean, nullable=True, default=False)

    def __init__(self, name=None, deck=None, status=None, script_dict: dict = None, id_order: dict = None,
                 time_created=None, last_modified=None, editing_type=None, author: str = None,
                 # registered:bool=False,
                 description: str = None,
                 python_script: str = None
                 ):
        if script_dict is None:
            script_dict = {"prep": [], "script": [], "cleanup": []}
        elif type(script_dict) is not dict:
            script_dict = json.loads(script_dict)
        if id_order is None:
            id_order = {"prep": [], "script": [], "cleanup": []}
        elif type(id_order) is not dict:
            id_order = json.loads(id_order)
        if status is None:
            status = 'editing'
        if time_created is None:
            time_created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if last_modified is None:
            last_modified = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if editing_type is None:
            editing_type = "script"
        if description is None:
            description = ""
        self.name = name
        self.deck = deck
        self.status = status
        self.script_dict = script_dict
        self.time_created = time_created
        self.last_modified = last_modified
        self.id_order = id_order
        self.editing_type = editing_type
        self.author = author
        self.python_script = python_script
        self.description = description
        # self.r = registered

    def as_dict(self):
        dict = self.__dict__
        dict.pop('_sa_instance_state', None)
        return dict

    def get(self):
        workflows = db.session.query(Script).all()
        # result = script_schema.dump(workflows)
        return workflows

    def find_by_uuid(self, uuid):
        for stype in self.script_dict:
            for action in self.script_dict[stype]:

                if action['uuid'] == int(uuid):
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
            try:
                # print(arg_type)
                args = eval(f"{arg_type}('{args}')")
                return
            except Exception:

                pass
        raise TypeError(f"Input type error: cannot convert '{args}' to {arg_type}.")

    def update_by_uuid(self, uuid, args, output, batch_action=False):
        action = self.find_by_uuid(uuid)
        if not action:
            return
        arg_types = action['arg_types']
        if type(action['args']) is dict:
            # pass
            self.eval_list(args, arg_types)
        else:
            pass
        action['args'] = args
        action['return'] = output
        action['batch_action'] = batch_action

    @staticmethod
    def eval_list(args, arg_types):
        for arg in args:
            arg_type = arg_types[arg]
            if arg_type in ["list", "tuple", "set"]:

                if type(arg) is str and not args[arg].startswith("#"):
                    # arg_types = arg_types[arg]
                    # if arg_types in ["list", "tuple", "set"]:
                    convert_type = getattr(builtins, arg_type)  # Handle unknown types s
                    try:
                        output = ast.literal_eval(args[arg])
                        if type(output) not in [list, tuple, set]:
                            output = [output]
                        args[arg] = convert_type(output)
                        # return args
                    except ValueError:
                        _list = ''.join(args[arg]).split(',')
                        # convert_type = getattr(builtins, arg_types)  # Handle unknown types s
                        args[arg] = convert_type([s.strip() for s in _list])

    @property
    def stypes(self):
        return list(self.script_dict.keys())

    @property
    def currently_editing_script(self):
        return self.script_dict[self.editing_type]

    @currently_editing_script.setter
    def currently_editing_script(self, script):
        self.script_dict[self.editing_type] = script

    @property
    def currently_editing_order(self):
        return self.id_order[self.editing_type]

    @currently_editing_order.setter
    def currently_editing_order(self, script):
        self.id_order[self.editing_type] = script

    def update_time_stamp(self):
        self.last_modified = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def get_script(self, stype: str):
        return self.script_dict[stype]

    def isEmpty(self) -> bool:
        if not (self.script_dict['script'] or self.script_dict['prep'] or self.script_dict['cleanup']):
            return True
        return False

    def _sort(self, script_type):
        if len(self.id_order[script_type]) > 0:
            for action in self.script_dict[script_type]:
                for i in range(len(self.id_order[script_type])):
                    if action['id'] == int(self.id_order[script_type][i]):
                        # print(i+1)
                        action['id'] = i + 1
                        break
            self.id_order[script_type].sort(key=int)
            if not int(self.id_order[script_type][-1]) == len(self.script_dict[script_type]):
                new_order = list(range(1, len(self.script_dict[script_type]) + 1))
                self.id_order[script_type] = [str(i) for i in new_order]
            self.script_dict[script_type].sort(key=lambda x: int(x['id']))

    def sort_actions(self, script_type=None):
        if script_type:
            self._sort(script_type)
        else:
            for i in self.stypes:
                self._sort(i)

    def add_action(self, action: dict, insert_position=None):
        current_len = len(self.currently_editing_script)
        action_to_add = action.copy()
        action_to_add['id'] = current_len + 1
        action_to_add['uuid'] = uuid.uuid4().fields[-1]
        self.currently_editing_script.append(action_to_add)
        self._insert_action(insert_position, current_len)
        self.update_time_stamp()

    def add_variable(self, statement, variable, variable_type, insert_position=None):
        variable = self.validate_function_name(variable)
        convert_type = getattr(builtins, variable_type)
        if isinstance(statement, str) and statement.startswith("#"):
            pass
        # boolean values
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
        self.update_time_stamp()

    def add_math_variable(self, statement, math_variable, insert_position=None):
        math_variable = self.validate_function_name(math_variable)

        current_len = len(self.currently_editing_script)
        uid = uuid.uuid4().fields[-1]
        action = {"id": current_len + 1, "instrument": 'math_variable', "action": math_variable,
                        "args": {"statement": 'None' if statement == '' else statement}, "return": '', "uuid": uid,
                        "arg_types": {"statement": 'float'}}
        self.currently_editing_script.append(action)
        self._insert_action(insert_position, current_len)
        self.update_time_stamp()

    def add_input_action(self, statement, variable, variable_type, insert_position=None):
        current_len = len(self.currently_editing_script)
        uid = uuid.uuid4().fields[-1]
        action = {"id": current_len + 1, "instrument": 'input', "action": variable,
                  "args": {"statement": statement, "variable": variable}, "return": variable, "uuid": uid,
                  "arg_types": {"statement": variable_type}}
        self.currently_editing_script.append(action)
        self._insert_action(insert_position, current_len)
        self.update_time_stamp()

    def _insert_action(self, insert_position, current_len, action_len:int=1):

        if insert_position is None:
            self.currently_editing_order.extend([str(current_len + i + 1) for i in range(action_len)])
        else:
            index = int(insert_position) - 1
            self.currently_editing_order[index:index] = [str(current_len + i + 1) for i in range(action_len)]
            self.sort_actions()

    def get_added_variables(self):
        added_variables: Dict[str, str] = {action["action"]: action["arg_types"]["statement"] for action in
                                           self.currently_editing_script if action["instrument"] == "variable"}
        added_math_variables: Dict[str, str] = {action["action"]: action["arg_types"]["statement"] for action in
                                                self.currently_editing_script if action["instrument"] == "math_variable"}
        all_added_variables = {**added_variables, **added_math_variables}
        return all_added_variables

    def get_output_variables(self):
        output_variables: Dict[str, str] = {action["return"]: "function_output" for action in
                                            self.currently_editing_script if action["return"]}

        return output_variables

    def get_variables(self):
        output_variables: Dict[str, str] = self.get_output_variables()
        added_variables = self.get_added_variables()
        output_variables.update(added_variables)

        return output_variables

    def validate_variables(self, kwargs, arg_types: dict = None):
        """
        Validates the kwargs passed to the Script
        """
        output_variables: Dict[str, str] = self.get_variables()
        # print(output_variables)
        for key, value in kwargs.items():
            if isinstance(value, str):
                if value in output_variables:
                    var_type = output_variables[value]
                    kwargs[key] = f"#{value}"
                elif value.startswith("#"):
                    kwargs[key] = f"#{self.validate_function_name(value[1:])}"
                else:
                    # attempt to convert to numerical or bool value for args with no type hint
                    type_hint = arg_types.get(key, "") if arg_types else ""
                    if not type_hint:
                        try:
                            converted = ast.literal_eval(value)
                            if isinstance(converted, (int, float, bool)):
                                kwargs[key] = converted
                        except (ValueError, SyntaxError):
                            pass
        return kwargs

    def add_logic_action(self, logic_type: str, statement, insert_position=None):
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
                     "return": '', "uuid": uid, "arg_types": {"statement": "float"}},
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
        self.update_time_stamp()

    def delete_action(self, id: int):
        """
        Delete the action by id (step number)
        """
        uid = next((action['uuid'] for action in self.currently_editing_script if action['id'] == int(id)), None)
        id_to_be_removed = [action['id'] for action in self.currently_editing_script if action['uuid'] == uid]
        order = self.currently_editing_order
        script = self.currently_editing_script
        self.currently_editing_order = [i for i in order if int(i) not in id_to_be_removed]
        self.currently_editing_script = [action for action in script if action['id'] not in id_to_be_removed]
        self.sort_actions()
        self.update_time_stamp()

    def duplicate_action(self, id: int):
        """
        duplicate action by id (step number), available only for non logic actions
        """
        action_to_duplicate = next((action for action in self.currently_editing_script if action['id'] == int(id)),
                                   None)
        insert_id = action_to_duplicate.get("id")
        self.add_action(action_to_duplicate)
        # print(self.currently_editing_script)
        if action_to_duplicate is not None:
            # Update IDs for all subsequent actions
            for action in self.currently_editing_script:
                if action['id'] > insert_id:
                    action['id'] += 1
            self.currently_editing_script[-1]['id'] = insert_id + 1
            # Sort actions if necessary and update the time stamp
            self.sort_actions()
            self.update_time_stamp()
        else:
            raise ValueError("Action not found: Unable to duplicate the action with ID", id)

    def config(self, stype):
        """
        take the global script_dict
        :return: list of variable that require input
        """
        configure = []
        variables = self.get_variables()
        # print(variables)
        config_type_dict = {}
        for action in self.script_dict[stype]:
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
                        # assume any kind of math variable will be evaluated to float even if it might be an int
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
        # todo
        return configure, config_type_dict

    def config_return(self):
        """
        take the global script_dict
        :return: list of variable that require input
        """

        return_list = set([action['return'] for action in self.script_dict['script'] if not action['return'] == ''])
        output_str = "{"
        for i in return_list:
            output_str += "'" + i + "':" + i + ","
        output_str += "}"
        return output_str, return_list

    def finalize(self):
        """finalize script, disable editing"""
        self.status = "finalized"
        self.update_time_stamp()

    def save_as(self, name):
        """resave script, enable editing"""
        self.name = name
        self.status = "editing"
        self.update_time_stamp()

    def indent(self, unit=0):
        """helper: create _ unit of indent in code string"""
        string = "\n"
        for _ in range(unit):
            string += "\t"
        return string

    def convert_to_lines(self, exec_str_collection: dict):
        """
        Parse a dictionary of script functions and extract function body lines.

        :param exec_str_collection: Dictionary containing script types and corresponding function strings.
        :return: A dict containing script types as keys and lists of function body lines as values.
        """
        line_collection = {}

        for stype, func_str in exec_str_collection.items():
            if func_str:
                module = ast.parse(func_str)

                # Find the first function (regular or async)
                func_def = next(
                    node for node in module.body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                )

                # Extract function body as source lines, skipping 'return' nodes
                line_collection[stype] = [
                    ast_unparse(node) for node in func_def.body if not isinstance(node, ast.Return)
                ]
        return line_collection

    def render_script_lines(self, script_dict):
        """
        Convert the script_dict structure into a dict of displayable Python-like lines,
        keeping ID consistency for highlighting.
        """

        def render_args(args):
            if not args:
                return ""
            return ", ".join(f"{k}={v}" for k, v in args.items())

        def parse_block(block):
            lines = []
            indent = 0
            stack = []

            for action in block:
                act = action["action"]
                _id = action["id"]
                instrument = action["instrument"]

                # Handle control structures
                if act == "if":
                    stmt = action["args"].get("statement", "")
                    lines.append("    " * indent + f"if {stmt}:")
                    indent += 1
                    stack.append("if")

                elif act == "else":
                    indent -= 1
                    lines.append("    " * indent + f"else:")
                    indent += 1

                elif act in ("endif", "endwhile"):
                    if stack:
                        stack.pop()
                    indent = max(indent - 1, 0)
                    lines.append("    " * indent + f"# {act}")

                elif act == "while":
                    stmt = action["args"].get("statement", "")
                    lines.append("    " * indent + f"while {stmt}:")
                    indent += 1
                    stack.append("while")

                elif act == "wait":
                    stmt = action["args"].get("statement", "")
                    if isinstance(stmt, str) and stmt.startswith("#"):
                        stmt = stmt[1:]
                    lines.append("    " * indent + f"time.sleep({stmt})")

                elif instrument == "variable":
                    stmt = action["args"].get("statement", "")
                    if isinstance(stmt, str) and stmt.startswith("#"):
                        stmt = stmt[1:]
                    lines.append("    " * indent + f"{act} = {stmt}")

                elif instrument == "input":
                    stmt = action["args"].get("statement", "")
                    var_name = action["args"].get("variable", "")
                    lines.append("    " * indent + f"{var_name} = input({repr(stmt)})")

                elif instrument == "math_variable":
                    stmt = action["args"].get("statement", "")
                    lines.append("    " * indent + f"{act} = {stmt}")


                else:
                    # Regular function call
                    instr = action["instrument"]
                    args = render_args(action.get("args", {}))
                    ret = action.get("return")
                    line = "    " * indent
                    if ret:
                        line += f"{ret} = {instr}.{act}({args})"
                    else:
                        line += f"{instr}.{act}({args})"
                    lines.append(line)

            # Ensure empty control blocks get "pass"
            final_lines = []
            for i, line in enumerate(lines):
                final_lines.append(line)
                # if line.strip().startswith("else") and (
                #         i == len(lines) - 1 or lines[i + 1].startswith("#") or "endif" in lines[i + 1]
                # ):
                    # final_lines.append("    " * (indent) + "pass")

            return final_lines

        return {
            "prep": parse_block(script_dict.get("prep", [])),
            "script": parse_block(script_dict.get("script", [])),
            "cleanup": parse_block(script_dict.get("cleanup", []))
        }

    def render_nested_script_lines(self, script_dict, snapshot=None):
        """
        Convert script_dict into a nested structure for collapsible UI.
        Returns check dict: { 'script': [ {type: 'line', code: '...', id: 'script-0'}, ... ] }
        """
        def render_args(args):
            if not args:
                return ""
            return ", ".join(f"{k}={v}" for k, v in args.items())

        def parse_block(block, parent_id_prefix, indent=0):
            nodes = []
            
            for i, action in enumerate(block):
                act = action["action"]
                instrument = action["instrument"]
                current_id = f"{parent_id_prefix}-{i}"
                
                # Handle nested workflows
                if instrument == 'workflows':
                    args = render_args(action.get("args", {}))
                    ret = action.get("return")
                    line_code = "    " * indent
                    if ret:
                        line_code += f"{ret} = "
                    line_code += f"{act}({args})"
                    
                    category = "workflow" # collapsible
                    
                    # Recursively parse children
                    # Prioritize embedded workflow steps
                    children_steps = action.get("workflow", [])
                    if not children_steps:
                        # Fallback to DB lookup if needed, though likely compilation ensures it's there
                        # but safe to check
                        wf_script = Script.query.filter_by(name=act).first()
                        if wf_script:
                            children_steps = wf_script.script_dict.get('script', [])

                    children_nodes = parse_block(children_steps, current_id, indent + 1)
                    
                    nodes.append({
                        "type": "workflow",
                        "code": line_code,
                        "id": current_id,
                        "children": children_nodes
                    })
                    
                # Handle control structures (simplified for now, treated as lines or blocks if we want collapse)
                # For now, let's treat control structures as flat or just lines, 
                # unless we want to collapse 'if' blocks too. 
                # User specifically asked for workflow collapse. Let's stick to that for now to avoid complexity.
                else: 
                     # Re-use the existing logic to generate the line string
                    line_code = ""
                    # ... [Logic to generate line string similar to render_script_lines] ...
                    # To avoid code duplication, I'll copy the logic briefly or helper
                    
                    if act == "if":
                        stmt = action["args"].get("statement", "")
                        line_code = "    " * indent + f"if {stmt}:"
                    elif act == "else":
                        # else is tricky because it belongs to previous if, but structurally it's a sibling in the list? 
                        # actually in the JSON list, else is likely a sibling.
                         line_code = "    " * (indent -1) + f"else:" if indent > 0 else "else:"
                    elif act in ("endif", "endwhile"):
                         line_code = "    " * (indent -1) + f"# {act}" if indent > 0 else f"# {act}"
                    elif act == "while":
                        stmt = action["args"].get("statement", "")
                        line_code = "    " * indent + f"while {stmt}:"
                    elif act == "wait":
                        stmt = action["args"].get("statement", "")
                        if isinstance(stmt, str) and stmt.startswith("#"):
                            stmt = stmt[1:]
                        line_code = "    " * indent + f"time.sleep({stmt})"
                    elif instrument == "variable":
                        stmt = action["args"].get("statement", "")
                        if isinstance(stmt, str) and stmt.startswith("#"):
                             stmt = stmt[1:]
                        line_code = "    " * indent + f"{act} = {stmt}"
                    elif instrument == "math_variable":
                        stmt = action["args"].get("statement", "")
                        line_code = "    " * indent + f"{act} = {stmt}"
                    elif instrument == "comment":
                        stmt = action["args"].get("statement", "")
                        if isinstance(stmt, str) and stmt.startswith("#"):
                             stmt = stmt[1:]
                             line_code = "    " * indent + f"print({stmt})"
                        else:
                             # Use repr to handle quotes safely
                             line_code = "    " * indent + f"print({repr(stmt)})"
                    elif instrument == "input":
                        stmt = action["args"].get("statement", "")
                        var_name = action["args"].get("variable", "var")
                        line_code = "    " * indent + f"{var_name} = input({repr(stmt)})"
                    else:
                        args_dict = action.get("args", {})
                        args = render_args(args_dict)
                        ret = action.get("return")
                        line_code = "    " * indent
                        
                        # Check metadata for properties
                        is_property_setter = False
                        is_property_getter = False
                        property_name = None
                        
                        if snapshot and instrument in snapshot:
                            inst_data = snapshot[instrument]
                            if act.endswith("_(setter)"):
                                prop_candidate = act[:-9]
                                if prop_candidate in inst_data and inst_data[prop_candidate].get('is_property'):
                                    is_property_setter = True
                                    property_name = prop_candidate
                            elif act in inst_data and inst_data[act].get('is_property'):
                                is_property_getter = True
                                property_name = act
                        
                        if is_property_setter:
                             arg_val = args_dict.get('value')
                             if isinstance(arg_val, str) and not arg_val.startswith("#"):
                                 arg_val = f"'{arg_val}'"
                             elif isinstance(arg_val, str) and arg_val.startswith("#"):
                                 arg_val = arg_val[1:]
                             line_code += f"{instrument}.{property_name} = {arg_val}"
                        elif is_property_getter:
                             if ret:
                                 line_code += f"{ret} = {instrument}.{property_name}"
                             else:
                                 line_code += f"{instrument}.{property_name}"
                        else:
                            if ret:
                                line_code += f"{ret} = {instrument}.{act}({args})"
                            else:
                                line_code += f"{instrument}.{act}({args})"
                    
                    nodes.append({
                        "type": "line",
                        "code": line_code,
                        "id": current_id
                    })
                    
            return nodes

        return {
            "prep": parse_block(script_dict.get("prep", []), "prep"),
            "script": parse_block(script_dict.get("script", []), "script"),
            "cleanup": parse_block(script_dict.get("cleanup", []), "cleanup")
        }

    def compile(self, script_path=None, batch=False, mode="sample", snapshot=None):
        """
        Compile the current script to a Python file.
        :return: String to write to a Python file.
        """
        self.needs_call_human = False
        self.blocks_included = False

        self.sort_actions()
        run_name = self.name if self.name else "untitled"
        run_name = self.validate_function_name(run_name)
        exec_str_collection = {}

        for i in self.stypes:
            if self.script_dict[i]:
                is_async = any(a.get("coroutine", False) for a in self.script_dict[i])
                func_str = self._generate_function_header(run_name, i, is_async, batch) + self._generate_function_body(i, batch, mode, snapshot)
                exec_str_collection[i] = func_str
        if script_path:
            self._write_to_file(script_path, run_name, exec_str_collection)

        return exec_str_collection



    @staticmethod
    def validate_function_name(name):
        """Replace invalid characters with underscores"""
        name = re.sub(r'\W|^(?=\d)', '_', name)
        # Check if it's a Python keyword and adjust if necessary
        if keyword.iskeyword(name):
            name += '_'
        return name

    def _generate_function_header(self, run_name, stype, is_async, batch=False):
        """
        Generate the function header.
        """
        configure, config_type = self.config(stype)
        configure = [param + f":{param_type}" if not param_type == "any" else param for param, param_type in
                     config_type.items()]

        script_type = f"_{stype}" if stype != "script" else ""
        async_str = "async " if is_async else ""
        function_header = f"{async_str}def {run_name}{script_type}("

        if stype == "script":
            if batch:
                function_header += "param_list" if configure else "n: int"
            else:
                function_header += ", ".join(configure)
        function_header += "):"

        if stype == "script" and batch:
            function_header += self.indent(1) + f'"""Batch mode is experimental and may have bugs."""'
        return function_header

    def _generate_function_body(self, stype, batch=False, mode="sample", snapshot=None):
        """
        Generate the function body for each type in stypes.
        """
        body = ''
        indent_unit = 1
        if batch and stype == "script":
            return_str, return_list = self.config_return()
            configure, config_type = self.config(stype)
            if not configure:
                body += self.indent(indent_unit) + "param_list = [{} for _ in range(n)]"
            for index, action in enumerate(self.script_dict[stype]):
                text, indent_unit = self._process_action(indent_unit, action, index, stype, batch, snapshot=snapshot)
                body += text
            if return_list:
                # body += self.indent(indent_unit) + f"result_list.append({return_str})"
                body += self.indent(indent_unit) + "return param_list"

        else:
            for index, action in enumerate(self.script_dict[stype]):
                text, indent_unit = self._process_action(indent_unit, action, index, stype, snapshot=snapshot)
                body += text
            return_str, return_list = self.config_return()
            if return_list and stype == "script":
                body += self.indent(indent_unit) + f"return {return_str}"
        return body

    def _process_action(self, indent_unit, action, index, stype, batch=False, mode="sample", snapshot=None):
        """
        Process each action within the script dictionary.
        """
        configure, config_type = self.config(stype)

        instrument = action['instrument']
        statement = action['args'].get('statement')
        args = self._process_args(action['args'])

        save_data = action['return']
        action_name = action['action']
        batch_action = action.get("batch_action", False)

        next_action = self._get_next_action(stype, index)
        # print(args)
        if instrument == 'if':
            return self._process_if(indent_unit, action_name, statement, next_action)
        elif instrument == 'while':
            return self._process_while(indent_unit, action_name, statement, next_action)
        elif instrument == 'variable':
            if batch:
                if isinstance(statement, str) and statement.startswith("#"):
                    return '', indent_unit
                return self.indent(indent_unit) + "for param in param_list:" + self.indent(
                    indent_unit + 1) + f"param['{action_name}'] = {statement}", indent_unit
            else:
                if isinstance(statement, str) and statement.startswith("#"):
                    statement = statement[1:]
                return self.indent(indent_unit) + f"{action_name} = {statement}", indent_unit
        elif instrument == 'input':
            var_name = args.get('variable')
            var_type = args.get('variable_type', 'str')
            prompt = statement
            
            # Construct input call
            if isinstance(prompt, str) and prompt.startswith("#"):
                prompt_expr = prompt[1:]
            else:
                prompt_expr = repr(prompt) if prompt else "''"
                
            input_call = f"input({prompt_expr})"
            
            # Apply type casting
            if var_type == 'int':
                expr = f"int({input_call})"
            elif var_type == 'float':
                expr = f"float({input_call})"
            elif var_type == 'bool':
            # Simplified bool conversion (non-empty string is True) or specific 'true' check?
            # Standard bool("False") is True. 
            # Let's simple use bool() for now or specific parsing if needed. 
            # Python input() returns string. 
                expr = f"bool({input_call})"
            else:
                expr = input_call
                
            if batch:
                return self.indent(indent_unit) + "for param in param_list:" + \
                       self.indent(indent_unit + 1) + f"param['{var_name}'] = {expr}", indent_unit
            else:
                return self.indent(indent_unit) + f"{var_name} = {expr}", indent_unit

        elif instrument == 'wait':
            if isinstance(statement, str) and statement.startswith("#"):
                statement = statement[1:]
            if batch:
                return f"{self.indent(indent_unit)}for param in param_list:" + f"{self.indent(indent_unit+1)}time.sleep({statement})", indent_unit
            return f"{self.indent(indent_unit)}time.sleep({statement})", indent_unit
        elif instrument == 'repeat':
            return self._process_repeat(indent_unit, action_name, statement, next_action)
        elif instrument == 'comment':
            if isinstance(statement, str) and statement.startswith("#"):
                statement = statement[1:]
                out_stmt = f"print({statement})"
            else:
                # Use repr to safely escape string with quotes
                out_stmt = f"print({repr(statement)})"

            if batch:
                return f"{self.indent(indent_unit)}for param in param_list:" + f"{self.indent(indent_unit + 1)}{out_stmt}", indent_unit
            return f"{self.indent(indent_unit)}{out_stmt}", indent_unit
        elif instrument == 'pause':
            self.needs_call_human = True
            if isinstance(statement, str) and statement.startswith("#"):
                statement = f"str({statement[1:]})"
            else:
                # cases like "text with a backslash \"
                statement = statement.encode('unicode_escape').decode()
            if batch:
                return f"{self.indent(indent_unit)}for param in param_list:" + f"{self.indent(indent_unit+1)}pause('''{statement}''')", indent_unit
            return f"{self.indent(indent_unit)}pause('''{statement}''')", indent_unit
        elif instrument == "math_variable":
            math_expression = self._process_math(statement)
            if batch:
                return f"{self.indent(indent_unit)}for param in param_list:" + f"{self.indent(indent_unit + 1)}param['{action_name}'] = {math_expression}", indent_unit
            else:
                return f"{self.indent(indent_unit)}{action_name} = {math_expression}", indent_unit
        # todo
        # elif instrument == 'registered_workflows':
        #     return inspect.getsource(my_function)
        else:
            is_async = action.get("coroutine", False)
            dynamic_arg = len(self.get_variables()) > 0
            workflow_steps = action.get("workflow", None)
        return self._process_instrument_action(indent_unit, instrument, action_name, args, save_data, is_async, dynamic_arg, batch, batch_action, workflow_steps, snapshot=snapshot)

    def _process_args(self, args):
        """
        Process arguments, handling any specific formatting needs.
        """
        if isinstance(args, str) and args.startswith("#"):
            return args[1:]
        return args

    def _process_if(self, indent_unit, action, args, next_action):
        """
        Process 'if' and 'else' actions.
        """
        exec_string = ""
        if action == 'if':
            if isinstance(args, str) and args.startswith("#"):
                args = args[1:]
            exec_string += self.indent(indent_unit) + f"if {args}:"
            indent_unit += 1
            if next_action and next_action['instrument'] == 'if' and next_action['action'] == 'else':
                exec_string += self.indent(indent_unit) + "pass"
            # else:

        elif action == 'else':
            indent_unit -= 1
            exec_string += self.indent(indent_unit) + "else:"
            indent_unit += 1
            if next_action and next_action['instrument'] == 'if' and next_action['action'] == 'endif':
                exec_string += self.indent(indent_unit) + "pass"
        else:
            indent_unit -= 1
        return exec_string, indent_unit

    def _process_while(self, indent_unit, action, args, next_action):
        """
        Process 'while' and 'endwhile' actions.
        """
        exec_string = ""
        if action == 'while':
            if isinstance(args, str) and args.startswith("#"):
                args = args[1:]
            exec_string += self.indent(indent_unit) + f"while {args}:"
            indent_unit += 1
            if next_action and next_action['instrument'] == 'while':
                exec_string += self.indent(indent_unit) + "pass"
        elif action == 'endwhile':
            indent_unit -= 1
        return exec_string, indent_unit

    def _process_repeat(self, indent_unit, action, args, next_action):
        """
        Process 'while' and 'endwhile' actions.
        """
        exec_string = ""
        if isinstance(args, str) and args.startswith("#"):
            args = args[1:]
        if action == 'repeat':
            exec_string += self.indent(indent_unit) + f"for _ in range({args}):"
            indent_unit += 1
            if next_action and next_action['instrument'] == 'repeat':
                exec_string += self.indent(indent_unit) + "pass"
        elif action == 'endrepeat':
            indent_unit -= 1
        return exec_string, indent_unit

    def _process_math(self, expr: str) -> str:
        """
        Return the math expression as a string but remove '#' prefix from variable names
        """
        # remove leading "#" for variable tokens
        cleaned = re.sub(r"#([A-Za-z_]\w*)", r"\1", expr)
        return cleaned

    def _process_instrument_action(self, indent_unit, instrument, action, args, save_data, is_async=False, dynamic_arg=False,
                                   batch=False, batch_action=False, workflow_steps=None, snapshot=None):
        """
        Process actions related to instruments.
        """
        async_str = "await " if is_async else ""

        if instrument == 'workflows':
            # This is a call to another registered workflow
            # Check for embedded steps first, otherwise fetch
            if workflow_steps is not None:
                # Use embedded steps (already a list of dicts)
                script_actions = workflow_steps
                # Create a temporary Script object just to use its context/methods if needed? 
                # Actually we can use 'self' but we need to ensure the methods called inside are generic.
                # _process_action uses self.script_dict etc. 
                # Wait, if we recurse, we need to be careful.
                # Let's inspect logic below.
                
                # We need a context for the inner workflow?
                # Using 'self' is fine for _process_action as long as it doesn't depend on self.script_dict for the *current* action being processed (it's passed in).
                # But _process_action requires 'stype' which is usually 'script'.
                pass # placeholder for logic logic
            else:
                 workflow_script = Script.query.get(action)
                 if workflow_script:
                     script_actions = workflow_script.script_dict.get('script', [])
                 else:
                     script_actions = []

            if script_actions:
                output_code = self.indent(indent_unit) + f"# Begin Workflow: {action}"
                
                # Inject argument assignments
                if args and isinstance(args, dict):
                     for key, value in args.items():
                         if isinstance(value, str) and value.startswith("#"):
                             # Passing a variable: inner_var = outer_var
                             assignment = f"{key} = {value[1:]}"
                         elif isinstance(value, str):
                             # String literal
                             assignment = f"{key} = '{value}'"
                         else:
                             # Other literals (int, float, bool)
                             assignment = f"{key} = {value}"
                         output_code += self.indent(indent_unit) + assignment

                expanded_body = ""
                # Use 'self' to process the inner actions. 
                # Prerequisite: _process_action is stateless regarding the script content list.
                # It seems so.
                for i, inner_action in enumerate(script_actions):
                     text, _ = self._process_action(indent_unit, inner_action, i, 'script', batch, mode="sample") 
                     expanded_body += text
                
                output_code += expanded_body
                output_code += self.indent(indent_unit) + f"# End Workflow: {action}"
                return output_code, indent_unit

        function_call = f"{instrument}.{action}"
        if instrument.startswith("blocks"):
            self.blocks_included = True
            function_call = action

        # Check if this is a property getter/setter
        is_property_setter = False
        is_property_getter = False
        property_name = None
        
        if snapshot and instrument in snapshot:
            inst_data = snapshot[instrument]
            if action.endswith("_(setter)"):
                prop_candidate = action[:-9]
                if prop_candidate in inst_data and inst_data[prop_candidate].get('is_property'):
                     is_property_setter = True
                     property_name = prop_candidate
            elif action in inst_data and inst_data[action].get('is_property'):
                is_property_getter = True
                property_name = action

        if is_property_setter:
            # Generate assignment: inst.prop = value
            arg_str = "None"
            if isinstance(args, dict):
                 val = args.get('value')
                 if val is not None:
                      # If it is a string starting with # or text, handle quoting
                      if isinstance(val, str):
                           if val.startswith("#"):
                                arg_str = val[1:]
                           else:
                                arg_str = f"'{val}'"
                      else:
                           arg_str = str(val)
            single_line = f"{async_str}{instrument}.{property_name} = {arg_str}"

        elif is_property_getter:
            # Generate access: inst.prop (no parentheses)
            single_line = f"{async_str}{instrument}.{property_name}"

        elif isinstance(args, dict) and args != {}:
            args_str = self._process_dict_args(args)
            single_line = f"{async_str}{function_call}(**{args_str})"
        elif isinstance(args, str):
            single_line = f"{function_call} = {args}"
        else:
            single_line = f"{async_str}{function_call}()"


        save_data_str = save_data + " = " if save_data else ''

        if batch and not batch_action:
            arg_list = [args[arg][1:] for arg in args if isinstance(args[arg], str) and args[arg].startswith("#")]
            param_str = [f"param['{arg_list}']" for arg_list in arg_list if arg_list]
            args_str = self.indent(indent_unit + 1) +  ", ".join(arg_list) + " = " + ", ".join(param_str) if arg_list else ""
            if dynamic_arg:
                for_string = self.indent(indent_unit) + "for param in param_list:" + args_str
            else:
                for_string = self.indent(indent_unit) + "for i in range(n):"
            output_code = for_string + self.indent(indent_unit + 1) + save_data_str + single_line
            if save_data:
                output_code = output_code + self.indent(indent_unit + 1) + f"param['{save_data}'] = {save_data}"
        else:
            output_code = self.indent(indent_unit) + save_data_str + single_line

        return output_code, indent_unit

    def _process_dict_args(self, args):
        """
        Process dictionary arguments, handling special cases like variables.
        """
        args_str = args.__str__()
        for arg in args:
            if isinstance(args[arg], str) and args[arg].startswith("#"):
                args_str = args_str.replace(f"'#{args[arg][1:]}'", args[arg][1:])
            elif isinstance(args[arg], dict):
                # print(args[arg])
                if not args[arg]:
                    continue
                # Extract the variable name (first key in the dict)
                value = next(iter(args[arg]))
                var_type = args[arg].get(value)

                # Only process if it's a function_output variable reference
                if var_type == "function_output":
                    variables = self.get_variables()
                    if value not in variables:
                        raise ValueError(f"Variable ({value}) is not defined.")
                    # Replace the dict string representation with just the variable name
                    args_str = args_str.replace(f"{args[arg]}", value)

        # elif self._is_variable(arg):
            #     print("is variable")
            #     args_str = args_str.replace(f"'{args[arg]}'", args[arg])
        return args_str

    def _get_next_action(self, stype, index):
        """
        Get the next action in the sequence if it exists.
        """
        if index < (len(self.script_dict[stype]) - 1):
            return self.script_dict[stype][index + 1]
        return None

    def _is_variable(self, arg):
        """
        Check if the argument is of type 'variable'.
        """
        return arg in self.script_dict and self.script_dict[arg].get("arg_types") in ("variable", 'math_variable')

    def _write_to_file(self, script_path, run_name, exec_string, call_human=False):
        """
        Write the compiled script to a file.
        """
        with open(script_path + run_name + ".py", "w") as s:
            if self.deck:
                s.write(f"import {self.deck} as deck")
            else:
                s.write("deck = None")
            s.write("\nimport time")
            if self.blocks_included:
                s.write(f"\n{self._create_block_import()}")
            if self.needs_call_human:
                s.write("""\n\ndef pause(reason="Manual intervention required"):\n\tprint(f"\\nHUMAN INTERVENTION REQUIRED: {reason}")\n\tinput("Press Enter to continue...\\n")""")

            for i in exec_string.values():
                s.write(f"\n\n\n{i}")

    def add_workflow(self, workflow_name, insert_position=None, **kwargs):
        current_len = len(self.currently_editing_script)
        uid = uuid.uuid4().fields[-1]
        action = {"id": current_len + 1, "instrument": "deck_name", "action": workflow_name,
                  "args": kwargs, "return": '', "uuid": uid,
                  "arg_types": {}}
        self.currently_editing_script.append(action)
        self._insert_action(insert_position, current_len)
        self.update_time_stamp()

    def group_actions(self, ids: list, name: str, author: str):
        """
        Group selected actions into a new registered workflow script.

        :param ids: List of action IDs (step numbers) to group.
        :param name: Name of the new workflow.
        :param author: Author of the new workflow.
        """
        # 1. Validate inputs
        if not ids:
            return
        
        # Sort ids to ensure we process them in order
        ids = sorted([int(id) for id in ids])
        
        # 2. Extract actions to be grouped
        actions_to_group = []
        for action in self.currently_editing_script:
            if action['id'] in ids:
                actions_to_group.append(action)
        
        # Sort actions by their ID to maintain order
        actions_to_group.sort(key=lambda x: x['id'])

        if not actions_to_group:
            return

        # 3. Create new Script for the grouped workflow
        # We assume the new script should have the same deck as the current one
        new_script_dict = {"prep": [], "cleanup": [], "script": []}
        
        # Deep copy actions to avoid reference issues, and reset their IDs
        import copy
        new_actions = copy.deepcopy(actions_to_group)
        for i, action in enumerate(new_actions):
            action['id'] = i + 1
            # Keep UUIDs or generate new ones? 
            # Generating new ones is safer to avoid duplicates across scripts if that matters
            action['uuid'] = uuid.uuid4().fields[-1] 
        
        new_script_dict["script"] = new_actions
        
        new_script = Script(
            name=name,
            deck=self.deck,
            status="finalized", # Or "editing"? Maybe finalized so it's immediately usable?
            script_dict=new_script_dict,
            author=author,
            # registered=True,
            description=f"Grouped from {len(ids)} steps"
        )
        
        # Save the new script to DB - THIS NEEDS DB SESSION ACCESS usually.
        # But Script object methods here seem to only modify self state usually.
        # We need to return this new script object so the caller can save it to DB.
        
        # 4. Remove original actions from current script
        # We need to insert the new workflow action at the position of the *first* removed action
        first_id = ids[0]
        insert_index = -1
        
        # Find index in currently_editing_script
        for i, action in enumerate(self.currently_editing_script):
            if action['id'] == first_id:
                insert_index = i
                break
        
        # Filter out grouped actions
        self.currently_editing_script = [a for a in self.currently_editing_script if a['id'] not in ids]
        
        # 5. Insert new workflow call
        # We need to construct arguments for the workflow if any internal variables are used?
        # For now, let's assume no arguments or let user configure later.
        # But wait, if the grouped steps used variables, those variables might need to be passed in.
        # Complex variable analysis is hard. For v1, let's assume empty args.
        
        # uuid for the new action
        uid = uuid.uuid4().fields[-1]
        
        workflow_action = {
            "id": 0, # Will be fixed by sort/insert logic or we set it now? self.add_workflow handles appending.
            "instrument": "deck_name", # This seems to be the convention for workflows?
            "action": name,
            "args": {},
            "return": "",
            "uuid": uid,
            "arg_types": {}
        }
        
        # We can't use self.add_workflow directly easily because we want to insert at specific index 
        # NOT just append and then invalidly insert. 
        # Actually `add_workflow` logic: append then `_insert_action`.
        # `_insert_action` logic: manipulation of `currently_editing_order`.
        
        # Let's direct modify `currently_editing_script` and `currently_editing_order`.
        
        self.currently_editing_script.insert(insert_index, workflow_action)
        
        # 6. Fix IDs
        # We simply re-assign IDs based on position
        for i, action in enumerate(self.currently_editing_script):
            action['id'] = i + 1
            
        # 7. Update Order
        # Reset order to match current script list
        self.currently_editing_order = [str(a['id']) for a in self.currently_editing_script]
        
        self.update_time_stamp()
        
        return new_script

    def _create_block_import(self):
        imports = {}
        from ivoryos.utils.decorators import BUILDING_BLOCKS
        for category, methods in BUILDING_BLOCKS.items():
            for method_name, meta in methods.items():
                func = meta["func"]
                module = meta["path"]
                name = func.__name__
                imports.setdefault(module, set()).add(name)
        lines = []
        for module, funcs in imports.items():
            lines.append(f"from {module} import {', '.join(sorted(funcs))}")
        return "\n".join(lines)

class WorkflowRun(db.Model):
    """Represents the entire experiment"""
    __tablename__ = 'workflow_runs'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    platform = db.Column(db.String(128), nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.now())
    end_time = db.Column(db.DateTime)
    data_path = db.Column(db.String(256))
    repeat_mode = db.Column(db.String(64), default="none")  # static_repeat, sweep, optimizer

    # A run contains multiple iterations
    phases = db.relationship(
        'WorkflowPhase',
        backref='workflow_runs', # Clearer back-reference name
        cascade='all, delete-orphan',
        lazy='dynamic' # Good for handling many iterations
    )
    def as_dict(self):
        dict = self.__dict__
        dict.pop('_sa_instance_state', None)
        return dict

class WorkflowPhase(db.Model):
    """Represents a single function call within a WorkflowRun."""
    __tablename__ = 'workflow_phases'

    id = db.Column(db.Integer, primary_key=True)
    # Foreign key to link this iteration to its parent run
    run_id = db.Column(db.Integer, db.ForeignKey('workflow_runs.id', ondelete='CASCADE'), nullable=False)

    # NEW: Store iteration-specific parameters here
    name = db.Column(db.String(64), nullable=False)  # 'prep', 'main', 'cleanup'
    repeat_index = db.Column(db.Integer, default=0)

    parameters = db.Column(JSONType)  # Use db.JSON for general support
    outputs = db.Column(JSONType)
    start_time = db.Column(db.DateTime, default=datetime.now)
    end_time = db.Column(db.DateTime)

    # An iteration contains multiple steps
    steps = db.relationship(
        'WorkflowStep',
        backref='workflow_phases',  # Clearer back-reference name
        cascade='all, delete-orphan'
    )

    def as_dict(self):
        dict = self.__dict__.copy()
        dict.pop('_sa_instance_state', None)
        return dict

class WorkflowStep(db.Model):
    __tablename__ = 'workflow_steps'

    id = db.Column(db.Integer, primary_key=True)
    # workflow_id = db.Column(db.Integer, db.ForeignKey('workflow_runs.id', ondelete='CASCADE'), nullable=True)
    phase_id = db.Column(db.Integer, db.ForeignKey('workflow_phases.id', ondelete='CASCADE'), nullable=True)

    # phase = db.Column(db.String(64), nullable=False)  # 'prep', 'main', 'cleanup'
    # repeat_index = db.Column(db.Integer, default=0)   # Only applies to 'main' phase
    step_index = db.Column(db.Integer, default=0)
    method_name = db.Column(db.String(128), nullable=False)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    run_error = db.Column(db.Boolean, default=False)
    output = db.Column(JSONType, default={})
    # Using as_dict method from ModelBase

    def as_dict(self):
        dict = self.__dict__.copy()
        dict.pop('_sa_instance_state', None)
        return dict


class SingleStep(db.Model):
    __tablename__ = 'single_steps'

    id = db.Column(db.Integer, primary_key=True)
    method_name = db.Column(db.String(128), nullable=False)
    kwargs = db.Column(JSONType, nullable=False)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    run_error = db.Column(db.String(128))
    output = db.Column(JSONType, nullable=True)

    def as_dict(self):
        dict = self.__dict__.copy()
        dict.pop('_sa_instance_state', None)
        return dict

if __name__ == "__main__":
    a = Script()

    print("")
