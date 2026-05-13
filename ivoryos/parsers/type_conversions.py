import ast
import importlib
from collections import Counter
from ivoryos.script.editor import ScriptEditor


def _convert_by_str(args, arg_types):
    """
    Converts a value to type through eval(f'{type}("{args}")')
    """
    if not isinstance(arg_types, list):
        arg_types = [arg_types]
    can_be_str = False
    for arg_type in arg_types:
        if arg_type in ["str", "any"]:
            can_be_str = True
            continue
        try:
            if isinstance(arg_type, str) and arg_type.startswith("Enum:"):
                _, full_path = arg_type.split(":", 1)
                module_name, class_name = full_path.rsplit(".", 1)
                try:
                    mod = importlib.import_module(module_name)
                except ImportError:
                    from ivoryos.runtime.state import GlobalState
                    deck = GlobalState().deck
                    if deck and (deck.__name__ == module_name or module_name == "__main__"):
                        mod = deck
                    else:
                        raise
                enum_class = getattr(mod, class_name)
                return enum_class[args].value
            converted_args = eval(f'{arg_type}("{args}")') if type(args) is str else eval(f'{arg_type}({args})')
            return converted_args
        except Exception:
            continue
            
    if can_be_str:
        return args
        
    raise TypeError(f"Input type error: cannot convert '{args}' to any of {arg_types}.")


def _convert_by_class(args, arg_types):
    """
    Converts a value to type through type(arg)
    """
    if arg_types.__module__ == 'builtins':
        args = arg_types(args)
        return args
    elif arg_types.__module__ == "typing":
        for i in arg_types.__args__:
            try:
                args = i(args)
                return args
            except Exception:
                pass
        raise TypeError("Input type error.")
    return args


def convert_config_type(args, arg_types, is_class: bool = False):
    """
    Converts an argument from str to an arg type
    """
    if args:
        ScriptEditor.eval_list(args, arg_types)
        for arg in args:
            if arg not in arg_types.keys():
                raise ValueError("config file format not supported.")
            if args[arg] == '' or args[arg] == "None":
                args[arg] = None
            else:
                arg_type = arg_types[arg]
                try:
                    args[arg] = ast.literal_eval(args[arg])
                except Exception:
                    pass
                
                is_valid_type = False
                if isinstance(arg_type, list):
                    if type(args[arg]).__name__ in arg_type:
                        is_valid_type = True
                else:
                    if type(args[arg]) is arg_type or type(args[arg]).__name__ == arg_type:
                        is_valid_type = True

                if not is_valid_type:
                    if is_class:
                        args[arg] = _convert_by_class(args[arg], arg_type)
                    else:
                        args[arg] = _convert_by_str(args[arg], arg_type)
    return args

def check_config_duplicate(config):
    """
    Checks if the config entry has any duplicate
    """
    hashable_data = [tuple(sorted(d.items())) for d in config]
    return any(count > 1 for count in Counter(hashable_data).values())

def web_config_entry_wrapper(data: dict, config_type: list):
    """
    Wrap the data dictionary from web config entries during execution configuration
    """
    rows = {}
    for key, value in data.items():
        if value:
            field_name, row_index = key.split('[')
            row_index = int(row_index.rstrip(']'))
            if row_index not in rows:
                rows[row_index] = {}
            rows[row_index][field_name] = value

    filtered_rows = [row for row in rows.values() if len(row) == len(config_type)]
    return filtered_rows
