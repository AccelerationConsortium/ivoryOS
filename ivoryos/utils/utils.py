import importlib
import inspect
import logging
import os
import pickle
import subprocess
import sys
from typing import Optional, Dict, Tuple

from flask import session
from flask_socketio import SocketIO

from ivoryos.utils.db_models import Script


def get_script_file():
    session_script = session.get("scripts")
    if session_script:
        s = Script()
        s.__dict__.update(**session_script)
        return s
    else:
        return Script(author=session.get('user'))


def post_script_file(script, is_dict=False):
    if is_dict:
        session['scripts'] = script
    else:
        session['scripts'] = script.as_dict()


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


def parse_functions(class_object=None, debug=False):
    functions = {}
    under_score = "_"
    if debug:
        under_score = "__"
    for function, method in inspect.getmembers(type(class_object), predicate=inspect.isfunction):
        if not function.startswith(under_score) and not function.isupper():
            try:
                annotation = inspect.signature(method)
                # if doc_string:
                docstring = inspect.getdoc(method)
                functions[function] = dict(signature=annotation, docstring=docstring)

                # handle getter setters
                # if callable(att):
                #     functions[function] = inspect.signature(att)
                # else:
                #     att = getattr(class_object.__class__, function)
                #     if isinstance(att, property) and att.fset is not None:
                #         setter = att.fset.__annotations__
                #         setter.pop('return', None)
                #         if setter:
                #             functions[function] = setter
            except Exception:
                pass
    return functions


def _get_type_from_parameters(arg, parameters):
    arg_type = ''
    if type(parameters) is inspect.Signature:
        p = parameters.parameters
        # print(p[arg].annotation)
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
            args = eval(f'{i}("{args}")')
            return args
        except Exception:
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
    # print(args, arg_types)
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


def import_module_by_filepath(filepath: str, name: str):
    spec = importlib.util.spec_from_file_location(name, filepath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SocketIOHandler(logging.Handler):
    def __init__(self, socketio: SocketIO):
        super().__init__()
        self.formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        self.socketio = socketio

    def emit(self, record):
        message = self.format(record)
        # session["last_log"] = message
        self.socketio.emit('log', {'message': message})


def start_logger(socketio: SocketIO, logger_name: str, log_filename: str = None):
    # logging.basicConfig( format='%(asctime)s - %(message)s')
    formatter = logging.Formatter(fmt='%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler(filename=log_filename, )
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


def process_data(data, config_type):
    rows = {}  # Dictionary to hold webui_data organized by rows

    # Organize webui_data by rows
    for key, value in data.items():
        if value:  # Only process non-empty values
            # Extract the field name and row index
            field_name, row_index = key.split('[')
            row_index = int(row_index.rstrip(']'))

            # If row not in rows, create a new dictionary for that row
            if row_index not in rows:
                rows[row_index] = {}

            # Add or update the field value in the specific row's dictionary
            rows[row_index][field_name] = value

    # Filter out any empty rows and create a list of dictionaries
    filtered_rows = [row for row in rows.values() if len(row) == len(config_type)]

    return filtered_rows


def parse_deck(deck, save=False, output_path=''):
    deck_variables = {f"deck.{name}": parse_functions(val) for name, val in vars(deck).items()
                      if not type(val).__module__ == 'builtins'
                      and not name[0].isupper()
                      and not name.startswith("_")}
    if deck_variables and save:
        # pseudo_deck = parse_dict
        parse_dict = deck_variables.copy()
        parse_dict["deck_name"] = os.path.splitext(os.path.basename(deck.__file__))[
            0] if deck.__name__ == "__main__" else deck.__name__
        with open(os.path.join(output_path, f"{parse_dict['deck_name']}.pkl"), 'wb') as file:
            pickle.dump(parse_dict, file)
    return deck_variables


def load_deck(pkl_name):
    if not pkl_name:
        return None
    try:
        with open(pkl_name, 'rb') as f:
            pseudo_deck = pickle.load(f)
        return pseudo_deck
    except FileNotFoundError:
        return None
