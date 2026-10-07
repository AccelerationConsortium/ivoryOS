import copy

from flask import Blueprint, flash, request, render_template, session, current_app, jsonify
from flask_login import login_required

from ivoryos.routes.control.control_file import control_file
from ivoryos.routes.control.control_new_device import control_temp
from ivoryos.routes.control.utils import post_session_by_instrument, get_session_by_instrument, find_instrument_by_name
from ivoryos.forms.dynamic_forms import create_form_from_module, create_form_from_pseudo
from ivoryos.parsers.introspection import _inspect_class
from ivoryos.runtime.safety import UNIT_GROUPS, describe, guard, instrument_name
from ivoryos.runtime.task_runner import TaskRunner
from ivoryos.runtime.state import GlobalState
from ivoryos.models import db, SingleStep

global_state = GlobalState()
runner = TaskRunner()

control = Blueprint('control', __name__, template_folder='templates')

control.register_blueprint(control_file)
control.register_blueprint(control_temp)


def _limitable_functions(instrument):
    """An instrument's methods for its fields' shields; None for what cannot be limited."""
    if instrument_name(instrument) is None:
        return None
    if instrument.startswith("deck."):
        return global_state.interface_schema.get(instrument)
    obj = global_state.defined_variables.get(instrument)
    return _inspect_class(obj) if obj is not None else None


@control.route("/", strict_slashes=False, methods=["GET", "POST"])
@control.route("/<string:instrument>", strict_slashes=False, methods=["GET", "POST"])
@login_required
async def deck_controllers(instrument: str = None):
    """
    .. :quickref: Direct Control; device (instruments) and methods

    device home interface for listing all instruments and methods, selecting an instrument to run its methods

    .. http:get:: /instruments

        Get all available instruments for the control home page.

    .. http:get:: /instruments/<string:instrument>

        Get all methods and their interface schema for the specified <instrument>.

    .. http:post:: /instruments/<string:instrument>

        Execute a specific method on the specified <instrument>.

    :param instrument: instrument name, if not provided, list all instruments
    :type instrument: str
    :status 200: render template with instruments and methods

    """
    instrument = instrument or request.args.get("instrument")
    forms = None
    if instrument:
        inst_object = find_instrument_by_name(instrument)
        if instrument.startswith("blocks"):
            forms = create_form_from_pseudo(pseudo=inst_object, autofill=False, design=False)
        elif instrument.startswith("deck"):
            forms = create_form_from_pseudo(pseudo=global_state.interface_schema[instrument], autofill=False, design=False)
        else:
            #TODO
            forms = create_form_from_module(sdl_module=inst_object, autofill=False, design=False)
        order = get_session_by_instrument('card_order', instrument)
        hidden_functions = get_session_by_instrument('hidden_functions', instrument)
        functions = list(forms.keys())
        for function in functions:
            if function not in hidden_functions and function not in order:
                order.append(function)
        post_session_by_instrument('card_order', instrument, order)
        forms = {name: forms[name] for name in order if name in forms}
    # each field's shield: {method: {param: {"kind", "limit"}}}, empty for building blocks
    limitable = _limitable_functions(instrument) if instrument else None
    guard_fields = guard.field_guards(instrument, limitable) if limitable is not None else {}

    if request.method == "POST":
        if not forms:
            return jsonify({"success": False, "error": "Instrument not found"}), 404

        payload = request.get_json() if request.is_json else request.form.to_dict()
        method_name = payload.pop("hidden_name", None)
        form = forms.get(method_name)

        if not form:
            return jsonify({"success": False, "error": f"Method {method_name} not found"}), 404

        # Extract kwargs
        if request.is_json:
            kwargs = {k: v for k, v in payload.items() if k not in ["csrf_token", "hidden_wait", "override_busy"]}
        else:
            if not form.validate_on_submit():
                flash(f"Run Error! {form.errors}", "error")
                return render_template(
                    "controllers.html",
                    defined_variables=global_state.interface_schema.keys(),
                    block_variables=global_state.building_blocks.keys(),
                    temp_variables=global_state.defined_variables.keys(),
                    instrument=instrument,
                    forms=forms,
                    guard_fields=guard_fields,
                    unit_groups=UNIT_GROUPS,
                    session=session
                )
            else:
                kwargs = {field.name: field.data for field in form if field.name not in ["csrf_token", "hidden_name", "override_busy"]}

        wait = str(payload.get("hidden_wait", "true")).lower() == "true"
        override_busy = str(payload.get("override_busy", "false")).lower() == "true"

        output = await runner.run_single_step(
            component=instrument, method=method_name, kwargs=kwargs, wait=wait,
            current_app=current_app._get_current_object(),
            override_busy=override_busy
        )

        if request.is_json:
            return jsonify(output)
        else:
            if output.get("success"):
                flash(f"Run Success! Output: {output.get('output', 'None')}")
            else:
                flash(f"Run Error! {output.get('output', 'Unknown error occurred.')}", "error")

    # GET request → render web form or return interface_schema for API
    if request.is_json or request.accept_mimetypes.best_match(['application/json', 'text/html']) == 'application/json':
        # 1.3.2 fix interface_schema copy, add building blocks to interface_schemas
        interface_schema = copy.deepcopy(global_state.interface_schema)
        building_blocks = copy.deepcopy(global_state.building_blocks)
        interface_schema.update(building_blocks)
        for instrument_key, instrument_data in interface_schema.items():
            for function_key, function_data in instrument_data.items():
                function_data["signature"] = str(function_data["signature"])
        return jsonify(interface_schema)

    return render_template(
        "controllers.html",
        defined_variables=global_state.interface_schema.keys(),
        block_variables=global_state.building_blocks.keys(),
        temp_variables=global_state.defined_variables.keys(),
        instrument=instrument,
        forms=forms,
        guard_fields=guard_fields,
        unit_groups=UNIT_GROUPS,
        session=session
    )


@control.route("/<string:instrument>/limits", methods=["POST"])
@login_required
def save_limit(instrument: str):
    """
    .. :quickref: Direct Control; set one field's safety limit

    .. http:post:: /instruments/<string:instrument>/limits

        Set the limit on one field of one method, or remove it when the limit sets nothing.

        :json method: the method, ``<name>_(setter)`` for a property setter
        :json param: the field
        :json limit: ``{min, max, unit, allowed}``
        :status 200: ``{"limit": {...}, "hint": "°C · -50 to 250"}``
        :status 400: ``{"errors": [{"message", "method", "param"}]}``, nothing saved
    """
    if _limitable_functions(instrument) is None:
        return jsonify({"errors": [{"message": f"'{instrument}' has no limits to set."}]}), 404
    data = request.get_json(silent=True) or {}
    method, param = str(data.get("method") or ""), str(data.get("param") or "")
    errors = guard.save_limit(instrument, method, param, data.get("limit"))
    if errors:
        return jsonify({"errors": errors}), 400
    limit = guard.constraints(instrument, method).get(param, {})
    return jsonify({"limit": limit, "hint": describe(limit)})


@control.route('/<string:instrument>/actions/order', methods=['POST'])
def save_order(instrument: str):
    """
    .. :quickref: Control Customization; Save method order

    **Save Order**

    .. http:post:: /instruments/<string:instrument>/actions/order

    Save the custom drag-and-drop order for the methods of a specific instrument.

    :param instrument: The name of the instrument.
    :status 204: Order saved successfully.
    """
    # Save the new order for the specified group to session
    data = request.json
    post_session_by_instrument('card_order', instrument, data['order'])
    return '', 204

@control.route('/<string:instrument>/actions/<string:function>', methods=["PATCH"])
def hide_function(instrument: str, function: str):
    """
    .. :quickref: Control Customization; Toggle method visibility

    **Hide Function**

    .. http:patch:: /instruments/<string:instrument>/actions/<string:function>

    Toggle the visibility of a specific method for an instrument in the control UI.

    :param instrument: The name of the instrument.
    :param function: The name of the method to hide/show.
    :json bool hidden: Whether the method should be hidden.
    :status 200: Visibility updated successfully.
    """
    back = request.referrer
    data = request.get_json()
    hidden = data.get('hidden', True)
    functions = get_session_by_instrument("hidden_functions", instrument)
    order = get_session_by_instrument("card_order", instrument)
    if hidden and function not in functions:
        functions.append(function)
        if function in order:
            order.remove(function)
    elif not hidden and function in functions:
        functions.remove(function)
        if function not in order:
            order.append(function)
    post_session_by_instrument('hidden_functions', instrument, functions)
    post_session_by_instrument('card_order', instrument, order)
    return jsonify(success=True, message="Visibility updated")


@control.route("/task/<int:task_id>", methods=["GET"])
def get_task_by_id(task_id):
    """
    .. :quickref: Direct Control; Get task by ID

    .. http:get:: /instruments/task/<int:task_id>

    Retrieve a single task execution step by its ID from the database.

    :status 200: Returns task details.
    :status 404: Task not found.
    """
    step = db.session.get(SingleStep, task_id)
    if step is not None:
        return jsonify(step.as_dict()), 200
    return jsonify({"error": "Task not found"}), 404

@control.post("/console/execute")
@login_required
def console_execute():
    """
    Execute raw python code quickly in the console using the global deck state.
    """
    import io, sys
    
    code = request.json.get("code", "") if request.is_json else ""
    deck = global_state.deck
    local_vars = {"deck": deck}
    if deck:
        for attr in dir(deck):
            if not attr.startswith("_"):
                local_vars[attr] = getattr(deck, attr)
                
    old_stdout = sys.stdout
    redirected_output = io.StringIO()
    sys.stdout = redirected_output
    
    # Restrict execution environment to prevent arbitrary imports (e.g. import os, subprocess)
    safe_builtins = {
        'print': print, 'len': len, 'range': range,
        'str': str, 'int': int, 'float': float, 'bool': bool,
        'list': list, 'dict': dict, 'set': set, 'tuple': tuple,
        'enumerate': enumerate, 'zip': zip, 'sum': sum, 'max': max, 'min': min,
        'abs': abs, 'round': round, 'any': any, 'all': all,
        'isinstance': isinstance, 'type': type, 'hasattr': hasattr, 'getattr': getattr,
        'Exception': Exception, 'ValueError': ValueError, 'TypeError': TypeError
    }
    restricted_globals = {"__builtins__": safe_builtins}
    
    try:
        exec(code, restricted_globals, local_vars)
        output = redirected_output.getvalue()
        return jsonify({"success": True, "output": output})
    except Exception as e:
        output = redirected_output.getvalue()
        return jsonify({"success": False, "error": str(e), "output": output})
    finally:
        sys.stdout = old_stdout
