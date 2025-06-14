from ivoryos.utils.utils import install_and_import


def ax_init_form(data, arg_types):
    """
    create Ax campaign from the web form input
    :param data:
    """
    install_and_import("ax", "ax-platform")
    parameter, objectives = ax_wrapper(data, arg_types)
    from ax.service.ax_client import AxClient
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