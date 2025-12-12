import copy

from flask import Blueprint, redirect, flash, request, render_template, session, current_app, jsonify
from flask_login import login_required

from ivoryos.routes.control.control_file import control_file
from ivoryos.routes.control.control_new_device import control_temp
from ivoryos.routes.control.utils import post_session_by_instrument, get_session_by_instrument, find_instrument_by_name
from ivoryos.utils.global_config import GlobalConfig
from ivoryos.utils.form import create_form_from_module, create_form_from_pseudo
from ivoryos.utils.task_runner import TaskRunner

global_config = GlobalConfig()
runner = TaskRunner()

control = Blueprint('control', __name__, template_folder='templates')

control.register_blueprint(control_file)
control.register_blueprint(control_temp)



@control.route("/", strict_slashes=False, methods=["GET", "POST"])
@control.route("/<string:instrument>", strict_slashes=False, methods=["GET", "POST"])
@login_required
async def deck_controllers(instrument: str = None):
    """
    .. :quickref: Direct Control; device (instruments) and methods

    device home interface for listing all instruments and methods, selecting an instrument to run its methods

    .. http:get:: /instruments

        get all instruments for home page

    .. http:get:: /instruments/<string:instrument>

        get all methods of the given <instrument>

    .. http:post:: /instruments/<string:instrument>

        send POST request to run a method of the given <instrument>

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
            forms = create_form_from_pseudo(pseudo=global_config.deck_snapshot[instrument], autofill=False, design=False)
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
            kwargs = {k: v for k, v in payload.items() if k not in ["csrf_token", "hidden_wait"]}
        else:
            if not form.validate_on_submit():
                flash(f"Run Error! {form.errors}", "error")
                return render_template(
                    "controllers.html",
                    defined_variables=global_config.deck_snapshot.keys(),
                    block_variables=global_config.building_blocks.keys(),
                    temp_variables=global_config.defined_variables.keys(),
                    instrument=instrument,
                    forms=forms,
                    session=session
                )
            else:
                kwargs = {field.name: field.data for field in form if field.name not in ["csrf_token", "hidden_name"]}

        wait = str(payload.get("hidden_wait", "true")).lower() == "true"

        output = await runner.run_single_step(
            component=instrument, method=method_name, kwargs=kwargs, wait=wait,
            current_app=current_app._get_current_object()
        )

        if request.is_json:
            return jsonify(output)
        else:
            if output.get("success"):
                flash(f"Run Success! Output: {output.get('output', 'None')}")
            else:
                flash(f"Run Error! {output.get('output', 'Unknown error occurred.')}", "error")

    # GET request → render web form or return snapshot for API
    if request.is_json or request.accept_mimetypes.best_match(['application/json', 'text/html']) == 'application/json':
        # 1.3.2 fix snapshot copy, add building blocks to snapshots
        snapshot = copy.deepcopy(global_config.deck_snapshot)
        building_blocks = copy.deepcopy(global_config.building_blocks)
        snapshot.update(building_blocks)
        for instrument_key, instrument_data in snapshot.items():
            for function_key, function_data in instrument_data.items():
                function_data["signature"] = str(function_data["signature"])
        return jsonify(snapshot)

    return render_template(
        "controllers.html",
        defined_variables=global_config.deck_snapshot.keys(),
        block_variables=global_config.building_blocks.keys(),
        temp_variables=global_config.defined_variables.keys(),
        instrument=instrument,
        forms=forms,
        session=session
    )

@control.route('/<string:instrument>/actions/order', methods=['POST'])
def save_order(instrument: str):
    """
    .. :quickref: Control Customization; Save functions' order

    .. http:post:: instruments/<string:instrument>/actions/order

    save function drag and drop order for the given <instrument>

    """
    # Save the new order for the specified group to session
    data = request.json
    post_session_by_instrument('card_order', instrument, data['order'])
    return '', 204

@control.route('/<string:instrument>/actions/<string:function>', methods=["PATCH"])
def hide_function(instrument: str, function: str):
    """
    .. :quickref: Control Customization; Toggle function visibility

    .. http:patch:: /instruments/<instrument>/actions/<function>

    Toggle visibility for the given <instrument> and <function>

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





