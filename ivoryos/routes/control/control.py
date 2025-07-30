from flask import Blueprint, redirect, flash, request, render_template, session, current_app, jsonify
from flask_login import login_required

from ivoryos.routes.control.control_file import control_file
from ivoryos.routes.control.control_new_device import control_temp
from ivoryos.routes.control.utils import post_session_by_instrument, get_session_by_instrument, find_instrument_by_name
from ivoryos.utils.global_config import GlobalConfig
from ivoryos.utils.form import create_form_from_module
from ivoryos.utils.task_runner import TaskRunner

global_config = GlobalConfig()
runner = TaskRunner()

control = Blueprint('control', __name__, template_folder='templates')

control.register_blueprint(control_file)
control.register_blueprint(control_temp)



@control.route("/", strict_slashes=False, methods=["GET", "POST"])
@control.route("/<string:instrument>", strict_slashes=False, methods=["GET", "POST"])
@login_required
def deck_controllers():
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
    deck_variables = global_config.deck_snapshot.keys()
    temp_variables = global_config.defined_variables.keys()
    instrument = request.args.get('instrument')
    forms = None
    if instrument:
        inst_object = find_instrument_by_name(instrument)
        _forms = create_form_from_module(sdl_module=inst_object, autofill=False, design=False)
        order = get_session_by_instrument('card_order', instrument)
        hidden_functions = get_session_by_instrument('hidden_functions', instrument)
        functions = list(_forms.keys())
        for function in functions:
            if function not in hidden_functions and function not in order:
                order.append(function)
        post_session_by_instrument('card_order', instrument, order)
        forms = {name: _forms[name] for name in order if name in _forms}
        # Handle POST for method execution
        if request.method == 'POST':
            all_kwargs = request.form.copy()
            method_name = all_kwargs.pop("hidden_name", None)
            form = forms.get(method_name)
            kwargs = {field.name: field.data for field in form if field.name != 'csrf_token'} if form else {}
            if form and form.validate_on_submit():
                kwargs.pop("hidden_name", None)
                output = runner.run_single_step(instrument, method_name, kwargs, wait=True, current_app=current_app._get_current_object())
                if output["success"]:
                    flash(f"\nRun Success! Output value: {output.get('output', 'None')}.")
                else:
                    flash(f"\nRun Error! {output.get('output', 'Unknown error occurred.')}", "error")
            else:
                if form:
                    flash(form.errors)
                else:
                    flash("Invalid method selected.")
    return render_template(
        'controllers.html',
        defined_variables=deck_variables,
        temp_variables=temp_variables,
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





