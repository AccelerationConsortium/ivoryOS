import ast
import json
import inspect
import logging
from typing import get_type_hints, Union, Optional, get_origin, get_args
import sys

import flask

from example.abstract_sdl_example import abstract_sdl as deck



class ScriptAnalyzer:
    def __init__(self):
        self.primitive_types = {
            'int', 'float', 'str', 'bool', 'tuple', 'list'
        }
        self.type_mapping = {
            int: 'int',
            float: 'float',
            str: 'str',
            bool: 'bool',
            tuple: 'tuple',
            list: 'list'
        }

    def extract_type_from_hint(self, type_hint):
        """Extract primitive types from type hints, handling Union and Optional"""
        if type_hint is None:
            return None

        # Handle Union types (including Optional which is Union[T, None])
        origin = get_origin(type_hint)
        if origin is Union:
            args = get_args(type_hint)
            types = []
            for arg in args:
                if arg is type(None):  # Skip None type
                    continue
                if arg in self.type_mapping:
                    types.append(self.type_mapping[arg])
                elif hasattr(arg, '__name__') and arg.__name__ in self.primitive_types:
                    types.append(arg.__name__)
                else:
                    return None  # Non-primitive type found
            return types if types else None

        # Handle direct primitive types
        if type_hint in self.type_mapping:
            return [self.type_mapping[type_hint]]
        elif hasattr(type_hint, '__name__') and type_hint.__name__ in self.primitive_types:
            return [type_hint.__name__]
        else:
            return None  # Non-primitive type


    def analyze_method(self, method):
        """Analyze a single method and extract its signature"""
        try:
            sig = inspect.signature(method)
            type_hints = get_type_hints(method)

            parameters = []
            type_hint_warning = False
            user_input_params = []

            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue

                param_info = {"name": param_name}

                # Get type hint
                if param_name in type_hints:
                    type_list = self.extract_type_from_hint(type_hints[param_name])
                    if type_list is None:
                        type_hint_warning = True
                        user_input_params.append(param_name)
                        param_info["type"] = ""
                    else:
                        param_info["type"] = type_list[0] if len(type_list) == 1 else type_list
                else:
                    type_hint_warning = True
                    user_input_params.append(param_name)
                    param_info["type"] = ""

                # Get default value
                if param.default != inspect.Parameter.empty:
                    param_info["default"] = param.default

                parameters.append(param_info)

            # Get docstring
            docstring = inspect.getdoc(method)

            method_info = {
                "docstring": docstring or "",
                "parameters": parameters
            }

            return method_info, type_hint_warning

        except Exception as e:
            print(f"Error analyzing method {method.__name__}: {e}")
            return None


    def analyze_module(self, module, exclude_names=[]):
        """Analyze module from sys.modules and extract class instances and methods"""
        exclude_classes = (flask.Blueprint, logging.Logger)
        # Get all variables in the module that are class instances
        included = {}
        excluded = {}
        failed = {}
        included_with_warnings = {}
        for name, obj in vars(module).items():
            if (
                    type(obj).__module__ == 'builtins'
                    or name[0].isupper()
                    or name.startswith("_")
                    or isinstance(obj, exclude_classes)
                    or name in exclude_names
                    or not hasattr(obj, '__class__')
            ):
                excluded[name] = type(obj).__name__
                continue

            cls = obj.__class__

            try:
                class_methods, type_hint_warning = self.analyze_class(cls)
                if class_methods:
                    if type_hint_warning:
                        included_with_warnings[name] = class_methods
                    included[name] = class_methods
            except Exception as e:
                failed[name] = str(e)
                continue
        return included, included_with_warnings, failed, excluded

    def save_to_json(self, data, output_path):
        """Save analysis result to JSON file"""
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

    def analyze_class(self, cls):
        class_methods = {}
        type_hint_flag = False
        for method_name, method in inspect.getmembers(cls, predicate=callable):
            if method_name.startswith("_") or method_name.isupper():
                continue
            method_info, type_hint_warning = self.analyze_method(method)
            if type_hint_warning:
                type_hint_flag = True
            if method_info:
                class_methods[method_name] = method_info
        return class_methods, type_hint_flag

    @staticmethod
    def print_deck_snapshot(result, with_warnings, failed):
        print("\nDeck Snapshot:")
        print("Included Classes:")
        for name, methods in result.items():
            print(f"  {name}:")
            for method_name, method_info in methods.items():
                print(f"    {method_name}: {method_info}")

        if with_warnings:
            print("\nClasses with Type Hint Warnings:")
            for name, methods in with_warnings.items():
                print(f"  {name}:")
                for method_name, method_info in methods.items():
                    print(f"    {method_name}: {method_info}")

        if failed:
            print("\nFailed Classes:")
            for name, error in failed.items():
                print(f"  {name}: {error}")

if __name__ == "__main__":

    _analyzer = ScriptAnalyzer()
    # module = sys.modules[deck]
    try:

        result, with_warnings, failed, _ = _analyzer.analyze_module(deck)

        output_path = f"analysis.json"
        _analyzer.save_to_json(result, output_path)

        print(f"\nAnalysis complete! Results saved to: {output_path}")




        _analyzer.print_deck_snapshot(result, with_warnings, failed)

    except Exception as e:
        print(f"Error: {e}")

