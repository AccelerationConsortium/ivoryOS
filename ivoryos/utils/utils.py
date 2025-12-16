import ast
import importlib
import inspect
import json
import logging
import os
import pickle
import socket
import subprocess
import sys
from collections import Counter
from enum import Enum

import flask
from flask import session
from flask_login import current_user
from flask_socketio import SocketIO

from ivoryos.utils.db_models import Script
from ivoryos.utils.decorators import BUILDING_BLOCKS

def get_script_file():
    """Get script from Flask session and returns the script"""
    session_script = session.get("scripts")
    if session_script:
        s = Script()
        s.__dict__.update(**session_script)
        return s
    else:
        return Script(author=current_user.get_id(),)


def post_script_file(script, is_dict=False):
    """
    Post script to Flask. Script will be converted to a dict if it is a Script object
    :param script: Script to post
    :param is_dict: if the script is a dictionary,
    """
    if is_dict:
        session['scripts'] = script
    else:
        session['scripts'] = script.as_dict()


def create_gui_dir(parent_path):
    """
    Creates folders for ivoryos data
    """
    os.makedirs(parent_path, exist_ok=True)
    for path in ["config_csv", "scripts", "results", "pseudo_deck"]:
        os.makedirs(os.path.join(parent_path, path), exist_ok=True)


def save_to_history(filepath, history_path):
    """
    For manual deck connection only
    save deck file path that successfully connected to ivoryos to a history file
    """
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
    """
    For manual deck connection only
    load deck connection history from history file
    """
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
    """
    load pseudo deck (snapshot) from connection history
    """
    return os.listdir(path)


def _inspect_class(class_object=None, debug=False):
    """
    inspect class object: inspect function signature if not name.startswith("_")
    :param class_object: class object
    :param debug: debug mode will inspect function.startswith("_")
    :return: function: Dict[str, Dict[str, Union[Signature, str, None]]]
    """
    functions = {}
    under_score = "_"
    if debug:
        under_score = "__"

    for function, method in inspect.getmembers(type(class_object), predicate=callable):
        if not function.startswith(under_score) and not function.isupper():
            try:
                annotation = inspect.signature(method)
                docstring = inspect.getdoc(method)
                coroutine = inspect.iscoroutinefunction(method)
                functions[function] = dict(signature=annotation, docstring=docstring, coroutine=coroutine,)

            except Exception:
                pass

    for function, prop in inspect.getmembers(type(class_object), lambda x: isinstance(x, property)):
        if not function.startswith(under_score) and not function.isupper():
            try:
                annotation = inspect.signature(prop.fget) if prop.fget else None
                docstring = inspect.getdoc(prop)
                functions[function] = dict(signature=annotation, docstring=docstring, coroutine=False,
                                           is_property=True, has_setter=prop.fset is not None)
            except Exception:
                pass
    return functions


def _get_type_from_parameters(arg, parameters):
    """get argument types from inspection"""
    # TODO
    arg_type = ''
    try:
        if isinstance(parameters, inspect.Signature):
            if arg not in parameters.parameters:
                return arg_type
            annotation = parameters.parameters[arg].annotation
        elif isinstance(parameters, dict):
            annotation = parameters.get(arg, '')
        else:
            annotation = ''
    except Exception:
        return arg_type

    if isinstance(annotation, str):
        arg_type = annotation
    elif annotation is not inspect._empty:
        if annotation.__module__ == 'typing':

            if hasattr(annotation, '__origin__'):
                origin = annotation.__origin__
                if hasattr(origin, '_name') and origin._name in ["Optional", "Union"]:
                    arg_type = [i.__name__ for i in annotation.__args__]
                elif hasattr(origin, '__name__'):
                    arg_type = origin.__name__
                # todo other types
        elif annotation.__module__ == 'types':
            arg_type = [i.__name__ for i in annotation.__args__]

        else:
            arg_type = annotation.__name__
    return arg_type


def _convert_by_str(args, arg_types):
    """
    Converts a value to type through eval(f'{type}("{args}")')
    v1.3.4 TODO try str lastly, otherwise it's always converted to str
    """
    if type(arg_types) is not list:
        arg_types = [arg_types]
    for arg_type in arg_types:
        if not arg_type == "any":
            try:
                args = eval(f'{arg_type}("{args}")') if type(args) is str else eval(f'{arg_type}({args})')
                return args
            except Exception:
                raise TypeError(f"Input type error: cannot convert '{args}' to {arg_type}.")
    return args


def _convert_by_class(args, arg_types):
    """
    Converts a value to type through type(arg)
    """
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
    """
    Converts an argument from str to an arg type
    """
    if args:
        Script.eval_list(args, arg_types)
        for arg in args:
            if arg not in arg_types.keys():
                raise ValueError("config file format not supported.")
            if args[arg] == '' or args[arg] == "None":
                args[arg] = None
            # elif args[arg] == "True" or args[arg] == "False":
            #     args[arg] = bool_dict[args[arg]]
            else:
                arg_type = arg_types[arg]
                try:
                    args[arg] = ast.literal_eval(args[arg])
                except Exception:
                    pass
                if type(args[arg]) is not arg_type and not type(args[arg]).__name__ == arg_type:
                    if is_class:
                        # if arg_type.__module__ == 'builtins':
                        args[arg] = _convert_by_class(args[arg], arg_type)
                    else:
                        args[arg] = _convert_by_str(args[arg], arg_type)
    return args


def import_module_by_filepath(filepath: str, name: str):
    """
    Import module by file path
    :param filepath: full path of module
    :param name: module's name
    """
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
    """
    stream logger to web through web socketIO
    """
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


def get_arg_type(args, parameters):
    """get argument type from signature"""
    arg_types = {}
    # print(args, parameters)
    parameters = parameters.get("signature")
    if args:
        for arg in args:
            arg_types[arg] = _get_type_from_parameters(arg, parameters)
    return arg_types


def install_and_import(package, package_name=None):
    """
    Install the package and import it
    :param package: package to import and install
    :param package_name: pip install package name if different from package
    """
    try:
        # Check if the package is already installed
        importlib.import_module(package)
        # print(f"{package} is already installed.")
    except ImportError:
        # If not installed, install it
        # print(f"{package} is not installed. Installing now...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name or package])
        # print(f"{package} has been installed successfully.")


def web_config_entry_wrapper(data: dict, config_type: list):
    """
    Wrap the data dictionary from web config entries during execution configuration
    :param data: data dictionary
    :param config_type: data entry types ["str", "int", "float", "bool"]
    """
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


def create_deck_snapshot(deck, save: bool = False, output_path: str = '', exclude_names: list = []):
    """
    Create a deck snapshot of the given script
    :param deck: python module name to create the deck snapshot from e.g. __main__
    :param save: save the deck snapshot into pickle file
    :param output_path: path to save the pickle file
    :param exclude_names: module names to exclude from deck snapshot
    """
    exclude_classes = (flask.Blueprint, logging.Logger)

    deck_snapshot = {}
    included = {}
    excluded = {}
    failed = {}

    for name, val in vars(deck).items():
        qualified_name = f"deck.{name}"

        # Exclusion checks
        if (
                type(val).__module__ == 'builtins'
                or name[0].isupper()
                or name.startswith("_")
                or isinstance(val, exclude_classes)
                or name in exclude_names
        ):
            excluded[qualified_name] = type(val).__name__
            continue

        try:
            deck_snapshot[qualified_name] = _inspect_class(val)
            included[qualified_name] = type(val).__name__
        except Exception as e:
            failed[qualified_name] = str(e)

    # Final result
    deck_summary = {
        "included": included,
        # "excluded": excluded,
        "failed": failed
    }

    def print_deck_snapshot(deck_summary):
        def print_section(title, items):
            print(f"\n=== {title} ({len(items)}) ===")
            if not items:
                return
            for name, class_type in items.items():
                print(f"  {name}: {class_type}")

        print_section("✅ INCLUDED MODULES", deck_summary["included"])
        print_section("❌ FAILED MODULES", deck_summary["failed"])
        print("\n")

    print_deck_snapshot(deck_summary)

    if deck_snapshot and save:
        # pseudo_deck = parse_dict
        parse_dict = deck_snapshot.copy()
        parse_dict["deck_name"] = os.path.splitext(os.path.basename(deck.__file__))[
            0] if deck.__name__ == "__main__" else deck.__name__
        with open(os.path.join(output_path, f"{parse_dict['deck_name']}.pkl"), 'wb') as file:
            pickle.dump(parse_dict, file)
    return deck_snapshot


def create_block_snapshot(save: bool = False, output_path: str = ''):
    block_snapshot = {}
    included = {}
    failed = {}
    for category, data in BUILDING_BLOCKS.items():
        key = f"blocks.{category}"
        block_snapshot[key] = {}

        for func_name, meta in data.items():
            func = meta["func"]
            block_snapshot[key][func_name] = {
                "signature": meta["signature"],
                "docstring": meta["docstring"],
                "coroutine": meta["coroutine"],
                "path": f"{func.__module__}.{func.__qualname__}"
            }
    if block_snapshot:
        print(f"\n=== ✅ BUILDING_BLOCKS ({len(block_snapshot)}) ===")
        for category, blocks in block_snapshot.items():
            print(f"  {category}: ", ",".join(blocks.keys()))
    return block_snapshot

def load_deck(pkl_name: str):
    """
    Loads a pickled deck snapshot from disk on offline mode
    :param pkl_name: name of the pickle file
    """
    if not pkl_name:
        return None
    try:
        with open(pkl_name, 'rb') as f:
            pseudo_deck = pickle.load(f)
        return pseudo_deck
    except FileNotFoundError:
        return None


def check_config_duplicate(config):
    """
    Checks if the config entry has any duplicate
    :param config: [{"arg": 1}, {"arg": 1}, {"arg": 1}]
    :return: [True, False]
    """
    hashable_data = [tuple(sorted(d.items())) for d in config]
    return any(count > 1 for count in Counter(hashable_data).values())


def get_method_from_workflow(function_string, func_name="workflow"):
    """Creates a function from a string and assigns it a new name."""

    namespace = {}
    exec(function_string, globals(), namespace)  # Execute the string in a safe namespace
    # func_name = next(iter(namespace))
    # Get the function name dynamically
    return namespace[func_name]

# def load_workflows(script):
#
#     class RegisteredWorkflows:
#         pass
#     deck_name = script.deck
#     workflows = Script.query.filter(Script.deck == deck_name, Script.name != script.name, Script.registered==True).all()
#     for workflow in workflows:
#         compiled_strs = workflow.compile().get('script', "")
#         method = get_method_from_workflow(compiled_strs, func_name=workflow.name)
#         setattr(RegisteredWorkflows, workflow.name, staticmethod(method))
#     global_config.registered_workflows = RegisteredWorkflows()


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))  # Dummy address to get interface IP
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def safe_dump(obj):
    try:
        json.dumps(obj)
        return obj
    except (TypeError, OverflowError):
        if isinstance(obj, Enum):
            return obj.value
        return repr(obj)  # store readable representation


def create_module_snapshot(module):
    classes = inspect.getmembers(module, inspect.isclass)
    api_variables = {}
    for i in classes:
        # globals()[i[0]] = i[1]
        api_variables[i[0]] = i[1]
    return api_variables