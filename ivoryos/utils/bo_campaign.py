import ast
from typing import Dict
import re


def normalize_value(v: str):
    """
    TODO centralize type conversion
    Convert HTML form string values to Python types.
    """

    if v in ("", None, "Default"):
        return None

    # -------- Boolean --------
    if v == "True":
        return True
    if v == "False":
        return False

    # -------- List detection --------
    # Case 1: looks like a Python literal list, e.g., "[1,2,3]"
    if isinstance(v, str) and v.strip().startswith("[") and v.strip().endswith("]"):
        try:
            parsed = ast.literal_eval(v)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass

    # Case 2: comma-separated values "1,2,3" or "a,b,c"
    if "," in v:
        parts = [p.strip() for p in v.split(",") if p.strip()]
        normalized_list = [normalize_value(p) for p in parts]
        return normalized_list

    # -------- Int --------
    try:
        return int(v)
    except ValueError:
        pass

    # -------- Float --------
    try:
        return float(v)
    except ValueError:
        pass

    # -------- Fallback: string --------
    return v



def parse_optimization_form(form_data: Dict[str, str]):
    """
    Parse dynamic form data into structured optimization configuration.

    Expected form field patterns:
    - Objectives: {name}_obj_min, {name}_weight
    - Parameters: {name}_type, {name}_min, {name}_max, {name}_choices, {name}_value_type
    - Config: step{n}_model, step{n}_num_samples
    """

    objectives = []
    parameters = []

    # Track processed field names to avoid duplicates
    processed_objectives = set()
    processed_parameters = set()

    # Parse objectives
    for field_name, value in form_data.items():
        if field_name.endswith('_obj_min') and value:
            # Extract objective name
            obj_name = field_name.replace('_obj_min', '')
            if obj_name in processed_objectives:
                continue

            # Check if corresponding weight exists
            weight_field = f"{obj_name}_weight"
            early_stop_field = f"{obj_name}_obj_threshold"

            config = {
                    "name": obj_name,
                    "minimize": value == "minimize",
                }
            if weight_field in form_data and form_data[weight_field]:
                config["weight"] = float(form_data[weight_field])
            if early_stop_field in form_data and form_data[early_stop_field]:
                config["early_stop"] = float(form_data[early_stop_field])
            objectives.append(config)
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
                step_field = f"{param_name}_step"
                if min_field in form_data and max_field in form_data:
                    min_val = form_data[min_field]
                    max_val = form_data[max_field]
                    step_val = form_data[step_field] if step_field in form_data else None
                    if min_val and max_val:
                        # Convert based on value_type
                        if value_type == "int":
                            bounds = [int(min_val), int(max_val)]
                        elif value_type == "float":
                            bounds = [float(min_val), float(max_val)]
                        else:  # string
                            bounds = [float(min_val), float(max_val)]
                        if step_val:
                            bounds.append(float(step_val))
                        parameter["bounds"] = bounds

            elif value == "choice":
                choices_field = f"{param_name}_value"
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

    # Parse additional parameters
    additional_params = {}
    for key, value in form_data.items():
        if key.startswith("adv_") and value not in ("Default", "", None):
            cleaned_key = key.replace("adv_", "")
            normalized = normalize_value(value)
            if normalized is not None:  # Still skip "Default", empty, None
                additional_params[cleaned_key] = normalized
    return parameters, objectives, steps, additional_params
