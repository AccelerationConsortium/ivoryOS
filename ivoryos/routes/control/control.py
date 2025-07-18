from flask import Blueprint, redirect, flash, request, render_template, session, current_app
from flask_login import login_required

from ivoryos.routes.control.control_file import control_file
from ivoryos.routes.control.control_new_device import control_temp
from ivoryos.routes.control.utils import post_session_by_instrument, get_session_by_instrument, find_instrument_by_name
from ivoryos.utils.global_config import GlobalConfig
from ivoryos.utils.form import create_form_from_module, format_name
from ivoryos.utils.task_runner import TaskRunner

global_config = GlobalConfig()
runner = TaskRunner()

control = Blueprint('control', __name__, template_folder='templates')

control.register_blueprint(control_file)
control.register_blueprint(control_temp)



@control.route("/home", strict_slashes=False, methods=["GET", "POST"])
@login_required
def deck_controllers():
    """
    Combined controllers page: sidebar with all instruments, main area with method cards for selected instrument.
    """
    deck_variables = global_config.deck_snapshot.keys()
    temp_variables = global_config.defined_variables.keys()
    instrument = request.args.get('instrument')
    forms = None
    # format_name_fn = format_name
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
                try:
                    kwargs.pop("hidden_name", None)
                    output = runner.run_single_step(instrument, method_name, kwargs, wait=True, current_app=current_app._get_current_object())
                    flash(f"\nRun Success! Output value: {output}.")
                except Exception as e:
                    flash(str(e))
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
        format_name=format_name,
        session=session
    )

@control.route('/<instrument>/save-order', methods=['POST'])
def save_order(instrument: str):
    """
    .. :quickref: Control Customization; Save functions' order

    .. http:post:: /control/save-order

    save function drag and drop order for the given <instrument>

    """
    # Save the new order for the specified group to session
    data = request.json
    post_session_by_instrument('card_order', instrument, data['order'])
    return '', 204


@control.route('/<instrument>/<function>/hide')
def hide_function(instrument, function):
    """
    .. :quickref: Control Customization; Hide function

    .. http:get:: //control/<instrument>/<function>/hide

    Hide the given <instrument> and <function>

    """
    back = request.referrer
    functions = get_session_by_instrument("hidden_functions", instrument)
    order = get_session_by_instrument("card_order", instrument)
    if function not in functions:
        functions.append(function)
        order.remove(function)
    post_session_by_instrument('hidden_functions', instrument, functions)
    post_session_by_instrument('card_order', instrument, order)
    return redirect(back)


@control.route('/<instrument>/<function>/unhide')
def remove_hidden(instrument: str, function: str):
    """
    .. :quickref: Control Customization; Remove a hidden function

    .. http:get:: /control/<instrument>/<function>/unhide

    Un-hide the given <instrument> and <function>

    """
    back = request.referrer
    functions = get_session_by_instrument("hidden_functions", instrument)
    order = get_session_by_instrument("card_order", instrument)
    if function in functions:
        functions.remove(function)
        order.append(function)
    post_session_by_instrument('hidden_functions', instrument, functions)
    post_session_by_instrument('card_order', instrument, order)
    return redirect(back)





