import ast
import re

try:
    from ast import unparse as ast_unparse
except ImportError:
    import astor
    ast_unparse = astor.to_source

from ivoryos.script.models import Script
from ivoryos.script.editor import ScriptEditor
from ivoryos.models.base import db

class ScriptRenderer:
    def __init__(self, script: Script):
        self.script = script
        self.editor = ScriptEditor(script)
        self.needs_call_human = False
        self.blocks_included = False

    def indent(self, unit=0):
        string = "\n"
        for _ in range(unit):
            string += "\t"
        return string

    def convert_to_lines(self, exec_str_collection: dict):
        line_collection = {}
        for stype, func_str in exec_str_collection.items():
            if func_str:
                module = ast.parse(func_str)
                func_def = next(
                    node for node in module.body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                )
                line_collection[stype] = [
                    ast_unparse(node) for node in func_def.body if not isinstance(node, ast.Return)
                ]
        return line_collection

    def render_script_lines(self, script_dict):
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
                instrument = action["instrument"]

                if instrument == "if" and act == "if":
                    stmt = action["args"].get("statement", "")
                    lines.append("    " * indent + f"if {stmt}:")
                    indent += 1
                    stack.append("if")
                elif instrument == "if" and act == "else":
                    indent -= 1
                    lines.append("    " * indent + f"else:")
                    indent += 1
                elif instrument == "if" and act == "endif":
                    if stack:
                        stack.pop()
                    indent = max(indent - 1, 0)
                    lines.append("    " * indent + f"# {act}")
                elif instrument == "while" and act == "endwhile":
                    if stack:
                        stack.pop()
                    indent = max(indent - 1, 0)
                    lines.append("    " * indent + f"# {act}")
                elif instrument == "while" and act == "while":
                    stmt = action["args"].get("statement", "")
                    lines.append("    " * indent + f"while {stmt}:")
                    indent += 1
                    stack.append("while")
                elif instrument == "wait" and act == "wait":
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
                    var_name = act if act and act != "None" else "var"
                    lines.append("    " * indent + f"{var_name} = input({repr(stmt)})")
                elif instrument == "math_variable":
                    stmt = action["args"].get("statement", "")
                    lines.append("    " * indent + f"{act} = {stmt}")
                else:
                    instr = action["instrument"]
                    args = render_args(action.get("args", {}))
                    ret = action.get("return")
                    line = "    " * indent
                    ret_target = self.editor._format_return_target(ret)
                    if ret_target:
                        line += f"{ret_target} = {instr}.{act}({args})"
                    else:
                        line += f"{instr}.{act}({args})"
                    lines.append(line)

            final_lines = []
            for i, line in enumerate(lines):
                final_lines.append(line)
            return final_lines

        return {
            "prep": parse_block(script_dict.get("prep", [])),
            "script": parse_block(script_dict.get("script", [])),
            "cleanup": parse_block(script_dict.get("cleanup", []))
        }

    def render_nested_script_lines(self, script_dict, interface_schema=None):
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

                if instrument == 'workflows':
                    args = render_args(action.get("args", {}))
                    ret = action.get("return")
                    line_code = "    " * indent
                    ret_target = self.editor._format_return_target(ret)
                    if ret_target:
                        line_code += f"{ret_target} = "
                    line_code += f"{act}({args})"
                    
                    children_steps = action.get("workflow", [])
                    if not children_steps:
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
                else: 
                    line_code = ""
                    if instrument == "if" and act == "if":
                        stmt = action["args"].get("statement", "")
                        line_code = "    " * indent + f"if {stmt}:"
                    elif instrument == "if" and act == "else":
                         line_code = "    " * (indent -1) + f"else:" if indent > 0 else "else:"
                    elif instrument == "if" and act == "endif":
                         line_code = "    " * (indent -1) + f"# {act}" if indent > 0 else f"# {act}"
                    elif instrument == "while" and act == "endwhile":
                         line_code = "    " * (indent -1) + f"# {act}" if indent > 0 else f"# {act}"
                    elif instrument == "while" and act == "while":
                        stmt = action["args"].get("statement", "")
                        line_code = "    " * indent + f"while {stmt}:"
                    elif instrument == "wait" and act == "wait":
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
                             line_code = "    " * indent + f"print({repr(stmt)})"
                    elif instrument == "input":
                        stmt = action["args"].get("statement", "")
                        var_name = act if act else "var"
                        line_code = "    " * indent + f"{var_name} = input({repr(stmt)})"
                    else:
                        args_dict = action.get("args", {})
                        args = render_args(args_dict)
                        ret = action.get("return")
                        line_code = "    " * indent
                        
                        is_property_setter = False
                        is_property_getter = False
                        property_name = None
                        
                        if interface_schema and instrument in interface_schema:
                            inst_data = interface_schema[instrument]
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
                             ret_target = self.editor._format_return_target(ret)
                             if ret_target:
                                 line_code += f"{ret_target} = {instrument}.{property_name}"
                             else:
                                 line_code += f"{instrument}.{property_name}"
                        else:
                            ret_target = self.editor._format_return_target(ret)
                            if ret_target:
                                line_code += f"{ret_target} = {instrument}.{act}({args})"
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

    def compile(self, script_path=None, batch=False, mode="sample", interface_schema=None):
        self.needs_call_human = False
        self.blocks_included = False

        self.editor.sort_actions()
        run_name = self.script.name if self.script.name else "untitled"
        run_name = self.editor.validate_function_name(run_name)
        exec_str_collection = {}

        for i in self.script.stypes:
            if self.script.script_dict[i]:
                is_async = any(a.get("coroutine", False) for a in self.script.script_dict[i])
                func_str = self._generate_function_header(run_name, i, is_async, batch) + self._generate_function_body(i, batch, mode, interface_schema)
                exec_str_collection[i] = func_str
        if script_path:
            self._write_to_file(script_path, run_name, exec_str_collection)

        return exec_str_collection

    def _generate_function_header(self, run_name, stype, is_async, batch=False):
        configure, config_type = self.editor.config(stype)
        new_configure = []
        for param, param_type in config_type.items():
            if isinstance(param_type, str) and param_type.startswith("Enum:"):
                 _, full_path = param_type.split(":", 1)
                 class_name = full_path.split(".")[-1]
                 new_configure.append(f"{param}: {class_name}")
            elif isinstance(param_type, str) and param_type.startswith("Literal:"):
                 _, literal_args_str = param_type.split(":", 1)
                 args_list = []
                 for a in literal_args_str.split(","):
                     if a.isdigit() or (a.startswith("-") and a[1:].isdigit()):
                         args_list.append(a)
                     elif a.replace(".", "", 1).isdigit() and a.count(".") < 2:
                         args_list.append(a)
                     else:
                         args_list.append(f"'{a}'")
                 new_configure.append(f"{param}: Literal[{', '.join(args_list)}]")
            elif isinstance(param_type, list):
                 enum_item = next((item for item in param_type if isinstance(item, str) and item.startswith("Enum:")), None)
                 if enum_item:
                      _, full_path = enum_item.split(":", 1)
                      class_name = full_path.split(".")[-1]
                      if "NoneType" in param_type:
                          new_configure.append(f"{param}: Optional[{class_name}]")
                      else:
                          new_configure.append(f"{param}: {class_name}")
                 else:
                      valid_types = [t for t in param_type if t != "NoneType"]
                      if len(valid_types) == 1:
                           if "NoneType" in param_type:
                               new_configure.append(f"{param}: Optional[{valid_types[0]}]")
                           else:
                               new_configure.append(f"{param}: {valid_types[0]}")
                      else:
                           new_configure.append(f"{param}: {param_type}")
            elif not param_type == "any":
                 new_configure.append(f"{param}: {param_type}")
            else:
                 new_configure.append(param)
        configure = new_configure

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

    def _generate_function_body(self, stype, batch=False, mode="sample", interface_schema=None):
        body = ''
        indent_unit = 1
        if batch and stype == "script":
            return_str, return_list = self.editor.config_return()
            configure, config_type = self.editor.config(stype)
            if not configure:
                body += self.indent(indent_unit) + "param_list = [{} for _ in range(n)]"
            for index, action in enumerate(self.script.script_dict[stype]):
                text, indent_unit = self._process_action(indent_unit, action, index, stype, batch, interface_schema=interface_schema)
                body += text
            if return_list:
                body += self.indent(indent_unit) + "return param_list"

        else:
            for index, action in enumerate(self.script.script_dict[stype]):
                text, indent_unit = self._process_action(indent_unit, action, index, stype, interface_schema=interface_schema)
                body += text
            return_str, return_list = self.editor.config_return()
            if return_list and stype == "script":
                body += self.indent(indent_unit) + f"return {return_str}"
        return body

    def _process_action(self, indent_unit, action, index, stype, batch=False, mode="sample", interface_schema=None, action_list=None):
        configure, config_type = self.editor.config(stype)

        instrument = action['instrument']
        statement = action['args'].get('statement')
        args = self._process_args(action['args'])

        save_data = action['return']
        action_name = action['action']
        batch_action = action.get("batch_action", False)

        next_action = self._get_next_action(stype, index, action_list)
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
            var_name = action_name if action_name and action_name != "None" else "var"
            var_type = args.get('variable_type', 'str')
            prompt = statement
            
            if isinstance(prompt, str) and prompt.startswith("#"):
                prompt_expr = prompt[1:]
            else:
                prompt_expr = repr(prompt) if prompt else "''"
                
            input_call = f"input({prompt_expr})"
            
            if var_type == 'int':
                expr = f"int({input_call})"
            elif var_type == 'float':
                expr = f"float({input_call})"
            elif var_type == 'bool':
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
            if batch and not batch_action:
                return f"{self.indent(indent_unit)}for param in param_list:" + f"{self.indent(indent_unit+1)}time.sleep({statement})", indent_unit
            return f"{self.indent(indent_unit)}time.sleep({statement})", indent_unit
        elif instrument == 'repeat':
            return self._process_repeat(indent_unit, action_name, statement, next_action)
        elif instrument == 'comment':
            if isinstance(statement, str) and statement.startswith("#"):
                statement = statement[1:]
                out_stmt = f"print({statement})"
            else:
                out_stmt = f"print({repr(statement)})"

            if batch:
                return f"{self.indent(indent_unit)}for param in param_list:" + f"{self.indent(indent_unit + 1)}{out_stmt}", indent_unit
            return f"{self.indent(indent_unit)}{out_stmt}", indent_unit
        elif instrument == 'pause':
            self.needs_call_human = True
            if isinstance(statement, str) and statement.startswith("#"):
                statement = f"str({statement[1:]})"
            else:
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
        else:
            is_async = action.get("coroutine", False)
            dynamic_arg = len(self.editor.get_variables()) > 0
            workflow_steps = action.get("workflow", None)
        arg_types = action.get('arg_types', {})
        return self._process_instrument_action(indent_unit, instrument, action_name, args, save_data, is_async, dynamic_arg, batch, batch_action, workflow_steps, interface_schema=interface_schema, arg_types=arg_types)

    def _process_args(self, args):
        if isinstance(args, str) and args.startswith("#"):
            return args[1:]
        return args

    def _process_if(self, indent_unit, action, args, next_action):
        exec_string = ""
        if action == 'if':
            if isinstance(args, str) and args.startswith("#"):
                args = args[1:]
            exec_string += self.indent(indent_unit) + f"if {args}:"
            indent_unit += 1
            if next_action and next_action['instrument'] == 'if' and next_action['action'] == 'else':
                exec_string += self.indent(indent_unit) + "pass"
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
        cleaned = re.sub(r"#([A-Za-z_]\w*)", r"\1", expr)
        return cleaned

    def _process_instrument_action(self, indent_unit, instrument, action, args, save_data, is_async=False, dynamic_arg=False,
                                   batch=False, batch_action=False, workflow_steps=None, interface_schema=None, arg_types=None):
        async_str = "await " if is_async else ""

        if instrument == 'workflows':
            if workflow_steps is not None:
                script_actions = workflow_steps
            else:
                 workflow_script = db.session.get(Script, action)
                 if workflow_script:
                     script_actions = workflow_script.script_dict.get('script', [])
                 else:
                     script_actions = []

            if script_actions:
                output_code = self.indent(indent_unit) + f"# Begin Workflow: {action}"
                
                if args and isinstance(args, dict):
                     for key, value in args.items():
                         if isinstance(value, str) and value.startswith("#"):
                             assignment = f"{key} = {value[1:]}"
                         elif isinstance(value, str):
                             assignment = f"{key} = '{value}'"
                         else:
                             assignment = f"{key} = {value}"
                         output_code += self.indent(indent_unit) + assignment

                expanded_body = ""
                for i, inner_action in enumerate(script_actions):
                     text, indent_unit = self._process_action(indent_unit, inner_action, i, 'script', batch, mode="sample", action_list=script_actions)
                     expanded_body += text
                
                output_code += expanded_body
                output_code += self.indent(indent_unit) + f"# End Workflow: {action}"
                return output_code, indent_unit

        function_call = f"{instrument}.{action}"
        if instrument.startswith("blocks"):
            self.blocks_included = True
            function_call = action

        is_property_setter = False
        is_property_getter = False
        property_name = None
        
        if interface_schema and instrument in interface_schema:
            inst_data = interface_schema[instrument]
            if action.endswith("_(setter)"):
                prop_candidate = action[:-9]
                if prop_candidate in inst_data and inst_data[prop_candidate].get('is_property'):
                     is_property_setter = True
                     property_name = prop_candidate
            elif action in inst_data and inst_data[action].get('is_property'):
                is_property_getter = True
                property_name = action

        if is_property_setter:
            arg_str = "None"
            if isinstance(args, dict):
                 val = args.get('value')
                 if val is not None:
                      if isinstance(val, str):
                           if val.startswith("#"):
                                arg_str = val[1:]
                           else:
                                arg_str = f"'{val}'"
                      else:
                           arg_str = str(val)
            single_line = f"{async_str}{instrument}.{property_name} = {arg_str}"
        elif is_property_getter:
            single_line = f"{async_str}{instrument}.{property_name}"
        elif isinstance(args, dict) and args != {}:
            args_str = self._process_dict_args(args, arg_types)
            single_line = f"{async_str}{function_call}(**{args_str})"
        elif isinstance(args, str):
            single_line = f"{function_call} = {args}"
        else:
            single_line = f"{async_str}{function_call}()"

        if batch and not batch_action:
            arg_list = [args[arg][1:] for arg in args if isinstance(args[arg], str) and args[arg].startswith("#")]
            param_str = [f"param['{arg_list}']" for arg_list in arg_list if arg_list]
            args_str = self.indent(indent_unit + 1) +  ", ".join(arg_list) + " = " + ", ".join(param_str) if arg_list else ""
            if dynamic_arg:
                for_string = self.indent(indent_unit) + "for param in param_list:" + args_str
            else:
                for_string = self.indent(indent_unit) + "for i in range(n):"
            if isinstance(save_data, list):
                output_code = for_string + self.indent(indent_unit + 1) + f"__ivoryos_result = {single_line}"
                for index, name in enumerate(save_data):
                    if name:
                        output_code += self.indent(indent_unit + 1) + f"{name} = __ivoryos_result[{index}]"
                        output_code += self.indent(indent_unit + 1) + f"param['{name}'] = {name}"
            else:
                save_data_str = save_data + " = " if save_data else ''
                output_code = for_string + self.indent(indent_unit + 1) + save_data_str + single_line
                if save_data:
                    output_code = output_code + self.indent(indent_unit + 1) + f"param['{save_data}'] = {save_data}"
        else:
            if isinstance(save_data, list):
                if any(save_data):
                    output_code = self.indent(indent_unit) + f"__ivoryos_result = {single_line}"
                    for index, name in enumerate(save_data):
                        if name:
                            output_code += self.indent(indent_unit) + f"{name} = __ivoryos_result[{index}]"
                else:
                    output_code = self.indent(indent_unit) + single_line
            else:
                save_data_str = save_data + " = " if save_data else ''
                output_code = self.indent(indent_unit) + save_data_str + single_line

        return output_code, indent_unit

    def _process_dict_args(self, args, arg_types=None):
        items = []
        for k, v in args.items():
             val_str = repr(v)
             if isinstance(v, str) and v.startswith("#"):
                 val_str = v[1:]
             elif isinstance(v, dict):
                 if v and isinstance(next(iter(v)), str):
                      key = next(iter(v))
                      if v[key] == "function_output":
                           val_str = key
                 else:
                      pass
             elif arg_types and k in arg_types:
                 type_str = arg_types[k]
                 if isinstance(type_str, str) and type_str.startswith("Enum:"):
                     try:
                        _, full_path = type_str.split(":", 1)
                        class_name = full_path.split(".")[-1]
                        val_str = f"{class_name}({repr(v)})"
                     except:
                        pass
             items.append(f"'{k}': {val_str}")
        return "{" + ", ".join(items) + "}"

    def _get_next_action(self, stype, index, action_list=None):
        lst = action_list if action_list is not None else self.script.script_dict[stype]
        if index < (len(lst) - 1):
            return lst[index + 1]
        return None

    def _is_variable(self, arg):
        return arg in self.script.script_dict and self.script.script_dict[arg].get("arg_types") in ("variable", 'math_variable')

    def get_required_imports(self):
        imports = set()
        if self.script.deck:
             imports.add(f"import {self.script.deck} as deck")
        for stype in self.script.stypes:
            for action in self.script.script_dict[stype]:
                arg_types = action.get('arg_types', {})
                if not arg_types: 
                    continue
                if isinstance(arg_types, dict):
                    for key, type_str in arg_types.items():
                        enum_strs = []
                        if isinstance(type_str, str):
                            enum_strs.append(type_str)
                        elif isinstance(type_str, list):
                            enum_strs.extend([t for t in type_str if isinstance(t, str)])
                        
                        for t in enum_strs:
                            if t.startswith("Enum:"):
                                try:
                                    _, full_path = t.split(":", 1)
                                    module_name, class_name = full_path.rsplit(".", 1)
                                    imports.add(f"from {module_name} import {class_name}")
                                except Exception:
                                    pass
                            elif t.startswith("Literal:"):
                                imports.add("from typing import Literal")
                        if isinstance(type_str, list) and "NoneType" in type_str:
                             imports.add("from typing import Optional")
        return "\n".join(sorted(list(imports)))

    def _write_to_file(self, script_path, run_name, exec_string, call_human=False):
        with open(script_path + run_name + ".py", "w") as s:
            if not self.script.deck:
                 s.write("deck = None\n")
            
            s.write("import time")
            s.write("\nfrom typing import Optional")
            if self.blocks_included:
                s.write(f"\n{self._create_block_import()}")
            
            s.write(f"\n{self.get_required_imports()}")

            if self.needs_call_human:
                s.write("""\n\ndef pause(reason="Manual intervention required"):\n\tprint(f"\\nHUMAN INTERVENTION REQUIRED: {reason}")\n\tinput("Press Enter to continue...\\n")""")

            for i in exec_string.values():
                s.write(f"\n\n\n{i}")

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
