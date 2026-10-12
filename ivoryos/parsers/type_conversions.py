import ast
from collections import Counter
from ivoryos.script.editor import ScriptEditor
from ivoryos.utils.enums import enum_class_from_type, find_member


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
                # a config cell may hold the key or the value; the row keeps the key, and the
                # runner calls the driver with the member (ivoryos.utils.enums)
                enum_class = enum_class_from_type(arg_type)
                member = find_member(enum_class, args) if enum_class else None
                if member is None:
                    raise ValueError(f"'{args}' is not one of {arg_type}")
                return member.name
            elif isinstance(arg_type, str) and arg_type.startswith("Literal:"):
                _, options_str = arg_type.split(":", 1)
                options = options_str.split(",")
                if str(args) in options:
                    return args
                raise ValueError(f"Value '{args}' not in Literal choices: {options}")
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
    The rows of the execution page's config table, ``{input: text}`` each, in table order.

    ``data`` holds the cells as ``input[row]`` keys. A row left entirely empty is skipped. An
    empty cell in a filled row is kept as ``""``: an input that takes None runs as None, and
    any other is reported before the run starts (``task_conditions.config_form_problems``),
    rather than its row being dropped without a word.
    """
    rows = {}
    for key, value in data.items():
        field_name, bracket, row_index = key.partition('[')
        if not bracket:
            continue
        try:
            index = int(row_index.rstrip(']'))
        except ValueError:
            continue
        rows.setdefault(index, {})[field_name] = value
    return [{field: row.get(field, "") for field in config_type}
            for row in rows.values() if any(str(value).strip() for value in row.values())]
