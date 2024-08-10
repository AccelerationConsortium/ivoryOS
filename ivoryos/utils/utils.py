import inspect
import importlib.util
import os
import pickle
import datetime
import logging
import importlib
import subprocess
import sys

from typing import Optional, Dict, Tuple

from flask_socketio import SocketIO

from ivoryos.utils.model import Script

stypes = ['prep', 'script', 'cleanup']


def create_gui_dir(parent_path):
    os.makedirs(parent_path, exist_ok=True)
    for path in ["config_csv", "scripts", "results", "pseudo_deck"]:
        os.makedirs(os.path.join(parent_path, path), exist_ok=True)


def save_to_history(filepath, history_path):
    connections = []
    try:
        with open(history_path, 'r') as file:
            lines = file.read()
            connections = lines.split('\n')
    except FileNotFoundError:
        pass
    if filepath not in connections:
        with open(history_path, 'a') as file:
            file.writelines(f"{filepath}\n")


def import_history(history_path):
    connections = []
    try:
        with open(history_path, 'r') as file:
            lines = file.read()
            connections = lines.split('\n')
    except FileNotFoundError:
        pass
    connections = [i for i in connections if not i == '']
    return connections


def available_pseudo_deck(path):
    import os
    return os.listdir(path)


def new_script(deck_name):
    """
    script dictionary structure
    :param deck:
    :return:
    """
    # .strftime("%Y-%m-%d %H:%M:%S")
    current_time = datetime.datetime.now()
    script_dict = {'name': '',
                   'deck': deck_name,
                   'status': 'editing',
                   'prep': [],
                   'script': [],
                   'cleanup': [],
                   # 'time_created': current_time,
                   # 'time_modified': current_time,
                   # 'author': '',
                   }
    order = {'prep': [],
             'script': [],
             'cleanup': [],
             }
    return script_dict, order


def parse_functions(class_object=None, debug=False):
    functions = {}
    under_score = "_"
    if debug:
        under_score = "__"
    for function in dir(class_object):
        if not function.startswith(under_score) and not function.isupper():
            try:
                att = getattr(class_object, function)

                # handle getter setters
                if callable(att):
                    functions[function] = inspect.signature(att)
                else:
                    att = getattr(class_object.__class__, function)
                    if isinstance(att, property) and att.fset is not None:
                        setter = att.fset.__annotations__
                        setter.pop('return', None)
                        if setter:
                            functions[function] = setter
            except Exception:
                pass
    return functions


def is_compatible(att):
    try:
        obj = inspect.signature(att)
        try:
            pickle.dumps(obj)
        except Exception:
            return False
    except ValueError:
        return False
    return True


def config(script_dict):
    """
    take the global script_dict
    :return: list of variable that require input
    """
    configure = []
    for action in script_dict['script']:
        args = action['args']
        if args is not None:
            if type(args) is not dict:
                if type(args) is str and args.startswith("#") and not args[1:] in configure:
                    configure.append(args[1:])
            else:
                for arg in args:
                    if type(args[arg]) is str \
                            and args[arg].startswith("#") \
                            and not args[arg][1:] in configure:
                        configure.append(args[arg][1:])
    return configure


def config_return(script_dict):
    """
    take the global script_dict
    :return: list of variable that require input
    """
    return_list = [action['return'] for action in script_dict if not action['return'] == '']
    output_str = "return {"
    for i in return_list:
        output_str += "'" + i + "':" + i + ","
    output_str += "}"
    return output_str, return_list


def _get_type_from_parameters(arg, parameters):
    arg_type = ''
    if type(parameters) is inspect.Signature:
        p = parameters.parameters
        print(p[arg].annotation)
        if p[arg].annotation is not inspect._empty:
            # print(p[arg].annotation)
            if p[arg].annotation.__module__ == 'typing':
                # print(p[arg].annotation.__args__)
                arg_type = [i.__name__ for i in p[arg].annotation.__args__]
            else:
                arg_type = p[arg].annotation.__name__
            # print(arg_type)
    elif type(parameters) is dict:
        if parameters[arg]:

            if parameters[arg].__module__ == 'typing':
                arg_type = [i.__name__ for i in parameters[arg].__args__]
            else:
                arg_type = parameters[arg].__name__
    return arg_type


def find_variable_in_script(script: Script, args: Dict[str, str]) -> Optional[Tuple[Dict[str, str], Dict[str, str]]]:
    # TODO: need to search for if the variable exists
    added_variables: list[Dict[str, str]] = [action for action in script.currently_editing_script if
                                             action["instrument"] == "variable"]

    possible_variable_arguments = {}
    possible_variable_types = {}

    for arg_name, arg_val in args.items():
        for added_variable in added_variables:
            if added_variable["action"] == arg_val:
                possible_variable_arguments[arg_name] = added_variable["action"]
                possible_variable_types[arg_name] = "variable"

    return possible_variable_arguments, possible_variable_types


def convert_type(args, parameters):
    bool_dict = {"True": True, "False": False}
    arg_types = {}
    if args:
        for arg in args:
            if args[arg] == '' or args[arg] == "None":
                args[arg] = None
                arg_types[arg] = _get_type_from_parameters(arg, parameters)
            elif args[arg] == "True" or args[arg] == "False":
                args[arg] = bool_dict[args[arg]]
                arg_types[arg] = 'bool'
            elif args[arg].startswith("#"):
                args[arg] = args[arg]
                arg_types[arg] = _get_type_from_parameters(arg, parameters)
            elif type(parameters) is inspect.Signature:
                p = parameters.parameters
                if p[arg].annotation is not inspect._empty:
                    if p[arg].annotation.__module__ == 'typing':
                        arg_types[arg] = p[arg].annotation.__args__

                        for i in p[arg].annotation.__args__:
                            try:
                                args[arg] = eval(f'{i}({args[arg]})')
                                break
                            except Exception:
                                pass

                    else:
                        args[arg] = p[arg].annotation(args[arg])
                        arg_types[arg] = p[arg].annotation.__name__
                else:
                    try:
                        args[arg] = eval(args[arg])
                        arg_types[arg] = ''
                    except Exception:
                        pass
            elif type(parameters) is dict:
                if parameters[arg]:
                    if parameters[arg].__module__ == 'typing':
                        # arg_types[arg] = parameters[arg].__args__
                        for i in parameters[arg].__args__:
                            # print(i)
                            try:
                                # args[arg] = i(args[arg])
                                args[arg] = eval(f'{i}({args[arg]})')
                                arg_types[arg] = i.__name__
                                break
                            except Exception:
                                pass
                    else:
                        args[arg] = parameters[arg](args[arg])
                        arg_types[arg] = parameters[arg].__name__
    return args, arg_types


def _convert_by_str(args, arg_types):
    # print(arg_types)
    if type(arg_types) is not list:
        arg_types = [arg_types]
    for i in arg_types:
        if i == "any":
            try:
                args = eval(args)
            except Exception:
                pass
            return args
        try:
            args = eval(f'{i}({args})')
            return args
        except Exception:
            pass
    raise TypeError(f"Input type error: cannot convert '{args}' to {i}.")


def _convert_by_class(args, arg_types):
    if arg_types.__module__ == 'builtins':
        args = arg_types(args)
        return args
    elif arg_types.__module__ == "typing":
        for i in arg_types.__args__:  # for typing.Union
            try:
                args = i(args)
                return args
            except Exception:
                pass
        raise TypeError("Input type error.")
    # else:
    #     args = globals()[args]
    return args


def convert_config_type(args, arg_types, is_class: bool = False):
    bool_dict = {"True": True, "False": False}
    print(args, arg_types)
    # print(globals())
    if args:
        for arg in args:
            if arg not in arg_types.keys():
                raise ValueError("config file format not supported.")
            if args[arg] == '' or args[arg] == "None":
                args[arg] = None
            elif args[arg] == "True" or args[arg] == "False":
                args[arg] = bool_dict[args[arg]]
            else:
                arg_type = arg_types[arg]

                if is_class:
                    # if arg_type.__module__ == 'builtins':
                    args[arg] = _convert_by_class(args[arg], arg_type)
                else:
                    args[arg] = _convert_by_str(args[arg], arg_type)
    return args


def sort_actions(script_dict, order, script_type=None):
    """
    sort all three types if script_type is None, otherwise sort the specified script type
    :return:
    """
    if script_type:
        sort(script_dict, order, script_type)
    else:
        for i in stypes:
            sort(script_dict, order, i)


def sort(script_dict, order, script_type):
    if len(order[script_type]) > 0:
        for action in script_dict[script_type]:
            for i in range(len(order[script_type])):
                if action['id'] == int(order[script_type][i]):
                    # print(i+1)
                    action['id'] = i + 1
                    break
        order[script_type].sort()
        if not int(order[script_type][-1]) == len(script_dict[script_type]):
            new_order = list(range(1, len(script_dict[script_type]) + 1))
            order[script_type] = [str(i) for i in new_order]
        script_dict[script_type].sort(key=lambda x: x['id'])


def logic_dict(key: str, current_len, args, var_name=None):
    """

    :param key:
    :param current_len:
    :param args:
    :param var_name:
    :return:
    """
    logic_dict = {
        "if":
            [
                {"id": current_len + 1, "instrument": 'if', "action": 'if', "args": args, "return": ''},
                {"id": current_len + 2, "instrument": 'if', "action": 'else', "args": '', "return": ''},
                {"id": current_len + 3, "instrument": 'if', "action": 'endif', "args": '', "return": ''},
            ],
        "while":
            [
                {"id": current_len + 1, "instrument": 'while', "action": 'while', "args": args, "return": ''},
                {"id": current_len + 2, "instrument": 'while', "action": 'endwhile', "args": '', "return": ''},
            ],
        "variable":
            [
                {"id": current_len + 1, "instrument": 'variable', "action": var_name, "args": args, "return": ''},
            ]
    }
    return logic_dict[key]


# def make_grid(row:int=1,col:int=1):
#     """
#     return the tray index str list by defining the size
#     :param row: 1 to 26
#     :param col:
#     :return: return the tray index
#     """
#     letter_list = [chr(i) for i in range(65, 90)]
#     return [i + str(j + 1) for i in letter_list[:col] for j in range(row)]


def make_grid(row: int = 1, col: int = 1):
    """
    return the tray index str list by defining the size
    :param row: 1 to 26
    :param col: 1 to 26
    :return: return the tray index
    """
    letter_list = [chr(i) for i in range(65, 90)]
    return [[i + str(j + 1) for j in range(col)] for i in letter_list[:row]]


tray_size_dict = {
    "metal_4_6": {"row": 4, "col": 6},
    "metal_4_6_landscape": {"row": 6, "col": 4},
    "noah_hplc_tray": {"row": 4, "col": 7},
    "solvent_tray": {"row": 5, "col": 2},
}


def import_module_by_filepath(filepath: str, name: str):
    spec = importlib.util.spec_from_file_location(name, filepath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def if_deck_valid(module):
    count = 0
    for var in set(dir(module)):
        if not var.startswith("_") and not var[0].isupper() and not var.startswith("repackage") \
                and not type(eval("module." + var)).__module__ == 'builtins':
            count += 1
    return False if count == 0 else True


class SocketIOHandler(logging.Handler):
    def __init__(self, socketio: SocketIO):
        super().__init__()
        self.formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        self.socketio = socketio

    def emit(self, record):
        message = self.format(record)
        # session["last_log"] = message
        self.socketio.emit('log', {'message': message})


def start_logger(socketio: SocketIO):
    # logging.basicConfig( format='%(asctime)s - %(message)s')
    formatter = logging.Formatter(fmt='%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    logger = logging.getLogger('gui_logger')
    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler(filename='example.log', )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    # console_logger = logging.StreamHandler()  # stream to console
    # logger.addHandler(console_logger)
    socketio_handler = SocketIOHandler(socketio)
    logger.addHandler(socketio_handler)
    return logger


def ax_wrapper(data):
    from ax.service.utils.instantiation import ObjectiveProperties
    parameter = []
    objectives = {}
    # Iterate through the webui_data dictionary
    for key, value in data.items():
        # Check if the key corresponds to a parameter type
        if "_type" in key:
            param_name = key.split("_type")[0]
            param_type = value
            param_value = data[f"{param_name}_value"].split(",")
            try:
                values = [float(v) for v in param_value]
            except Exception:
                values = param_value
            if param_type == "range":
                parameter.append({"name": param_name, "type": param_type, "bounds": values})
            if param_type == "choice":
                parameter.append({"name": param_name, "type": param_type, "values": values})
            if param_type == "fixed":
                parameter.append({"name": param_name, "type": param_type, "value": values[0]})
        elif key.endswith("_min"):
            if not value == 'none':
                obj_name = key.split("_min")[0]
                is_min = True if value == "minimize" else False

                threshold = None if f"{obj_name}_threshold" not in data else data[f"{obj_name}_threshold"]
                properties = ObjectiveProperties(minimize=is_min, threshold=threshold)
                objectives[obj_name] = properties
    return parameter, objectives


def ax_initiation(data):
    install_and_import("ax", "ax-platform")
    parameter, objectives = ax_wrapper(data)
    from ax.service.ax_client import AxClient
    ax_client = AxClient()
    ax_client.create_experiment(parameter, objectives)
    return ax_client


def get_arg_type(args, parameters):
    arg_types = {}
    # print(args, parameters)
    if args:
        for arg in args:
            arg_types[arg] = _get_type_from_parameters(arg, parameters)
    return arg_types


def install_and_import(package, package_name=None):
    try:
        # Check if the package is already installed
        importlib.import_module(package)
        # print(f"{package} is already installed.")
    except ImportError:
        # If not installed, install it
        # print(f"{package} is not installed. Installing now...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name or package])
        # print(f"{package} has been installed successfully.")
