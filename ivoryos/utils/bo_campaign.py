from typing import Dict, Any
import re
from ivoryos.utils.utils import install_and_import


def ax_init_form(data, arg_types, previous_data_len=0):
    """
    create Ax campaign from the web form input
    :param data:
    """
    install_and_import("ax", "ax-platform")
    parameter, objectives = ax_wrapper(data, arg_types)
    from ax.service.ax_client import AxClient
    if previous_data_len > 0:
        gs = exisitng_data_gs(previous_data_len)
        ax_client = AxClient(generation_strategy=gs)
    else:
        ax_client = AxClient()
    ax_client.create_experiment(parameter, objectives=objectives)
    return ax_client


def ax_wrapper(data: dict, arg_types: list):
    """
    Ax platform wrapper function for creating optimization campaign parameters and objective from the web form input
    :param data: e.g.,
    {
        "param_1_type": "range", "param_1_value": [1,2],
        "param_2_type": "range", "param_2_value": [1,2],
        "obj_1_min": True,
        "obj_2_min": True
    }
    :return: the optimization campaign parameters
    parameter=[
        {"name": "param_1", "type": "range", "bounds": [1,2]},
        {"name": "param_1", "type": "range", "bounds": [1,2]}
    ]
    objectives=[
        {"name": "obj_1", "min": True, "threshold": None},
        {"name": "obj_2", "min": True, "threshold": None},
    ]
    """
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
                param = {"name": param_name, "type": param_type, "bounds": values}
            if param_type == "choice":
                param = {"name": param_name, "type": param_type, "values": values}
            if param_type == "fixed":
                param = {"name": param_name, "type": param_type, "value": values[0]}
            _type = arg_types[param_name] if arg_types[param_name] in ["str", "bool", "int"] else "float"
            param.update({"value_type": _type})
            parameter.append(param)
        elif key.endswith("_min"):
            if not value == 'none':
                obj_name = key.split("_min")[0]
                is_min = True if value == "minimize" else False

                threshold = None if f"{obj_name}_threshold" not in data else data[f"{obj_name}_threshold"]
                properties = ObjectiveProperties(minimize=is_min)
                objectives[obj_name] = properties

    return parameter, objectives


def ax_init_opc(bo_args):
    install_and_import("ax", "ax-platform")
    from ax.service.ax_client import AxClient
    from ax.service.utils.instantiation import ObjectiveProperties

    ax_client = AxClient()
    objectives = bo_args.get("objectives")
    objectives_formatted = {}
    for obj in objectives:
        obj_name = obj.get("name")
        minimize = obj.get("minimize")
        objectives_formatted[obj_name] = ObjectiveProperties(minimize=minimize)
    bo_args["objectives"] = objectives_formatted
    ax_client.create_experiment(**bo_args)

    return ax_client


def exisitng_data_gs(data_len):
    """
    temporal generation strategy for existing data
    """
    from ax.generation_strategy.generation_node import GenerationStep
    from ax.generation_strategy.generation_strategy import GenerationStrategy
    from ax.modelbridge.registry import Generators
    if data_len > 4:
        gs = GenerationStrategy(
            steps=[
                GenerationStep(
                    model=Generators.BOTORCH_MODULAR,
                    num_trials=-1,
                    max_parallelism=3,
                ),
            ]
        )
    else:
        gs = GenerationStrategy(
            steps=[
                GenerationStep(
                    model=Generators.SOBOL,
                    num_trials=5-data_len,  # how many sobol trials to perform (rule of thumb: 2 * number of params)
                    max_parallelism=5,
                    model_kwargs={"seed": 999},
                ),
                GenerationStep(
                    model=Generators.BOTORCH_MODULAR,
                    num_trials=-1,
                    max_parallelism=3,
                ),
            ]
        )
    return gs


def parse_optimization_form(form_data: Dict[str, str]):
    """
    Parse dynamic form data into structured optimization configuration.

    Expected form field patterns:
    - Objectives: {name}_min, {name}_weight
    - Parameters: {name}_type, {name}_min, {name}_max, {name}_choices, {name}_value_type
    - Config: step{n}_model, step{n}_num_samples
    """

    objectives = []
    parameters = []
    config = {}

    # Track processed field names to avoid duplicates
    processed_objectives = set()
    processed_parameters = set()

    # Parse objectives
    for field_name, value in form_data.items():
        if field_name.endswith('_min') and value:
            # Extract objective name
            obj_name = field_name.replace('_min', '')
            if obj_name in processed_objectives:
                continue

            # Check if corresponding weight exists
            weight_field = f"{obj_name}_weight"
            if weight_field in form_data and form_data[weight_field]:
                objectives.append({
                    "name": obj_name,
                    "minimize": value == "minimize",
                    "weight": float(form_data[weight_field])
                })
            else:
                objectives.append({
                    "name": obj_name,
                    "minimize": value == "minimize",
                })
            processed_objectives.add(obj_name)

    # Parse parameters
    for field_name, value in form_data.items():
        if field_name.endswith('_type') and value:
            # Extract parameter name
            param_name = field_name.replace('_type', '')
            if param_name in processed_parameters:
                continue

            parameter = {
                "name": param_name,
                "type": value
            }

            # Get value type (default to float)
            value_type_field = f"{param_name}_value_type"
            value_type = form_data.get(value_type_field, "float")
            parameter["value_type"] = value_type

            # Handle different parameter types
            if value == "range":
                min_field = f"{param_name}_min"
                max_field = f"{param_name}_max"

                if min_field in form_data and max_field in form_data:
                    min_val = form_data[min_field]
                    max_val = form_data[max_field]

                    if min_val and max_val:
                        # Convert based on value_type
                        if value_type == "int":
                            bounds = [int(min_val), int(max_val)]
                        elif value_type == "float":
                            bounds = [float(min_val), float(max_val)]
                        else:  # string
                            bounds = [str(min_val), str(max_val)]

                        parameter["bounds"] = bounds

            elif value == "choice":
                choices_field = f"{param_name}_choices"
                if choices_field in form_data and form_data[choices_field]:
                    # Split choices by comma and clean whitespace
                    choices = [choice.strip() for choice in form_data[choices_field].split(',')]

                    # Convert choices based on value_type
                    if value_type == "int":
                        choices = [int(choice) for choice in choices if choice.isdigit()]
                    elif value_type == "float":
                        choices = [float(choice) for choice in choices if
                                   choice.replace('.', '').replace('-', '').isdigit()]
                    # For string, keep as is

                    parameter["bounds"] = choices

            elif value == "fixed":
                fixed_field = f"{param_name}_value"
                if fixed_field in form_data and form_data[fixed_field]:
                    fixed_val = form_data[fixed_field]

                    # Convert based on value_type
                    if value_type == "int":
                        parameter["value"] = int(fixed_val)
                    elif value_type == "float":
                        parameter["value"] = float(fixed_val)
                    else:
                        parameter["value"] = str(fixed_val)

            parameters.append(parameter)
            processed_parameters.add(param_name)

    # Parse configuration steps
    step_pattern = re.compile(r'step(\d+)_(.+)')
    steps = {}

    for field_name, value in form_data.items():
        match = step_pattern.match(field_name)
        if match and value:
            step_num = int(match.group(1))
            step_attr = match.group(2)
            step_key = f"step_{step_num}"

            if step_key not in steps:
                steps[step_key] = {}

            # Convert num_samples to int if it's a number field
            if step_attr == "num_samples":
                steps[step_key][step_attr] = int(value)
            else:
                steps[step_key][step_attr] = value

    return parameters, objectives, steps
