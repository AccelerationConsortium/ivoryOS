from flask import Blueprint, request, jsonify, render_template, current_app
from flask_login import login_required

from ivoryos.services.draft_service import get_script_file, post_script_file
from ivoryos.forms.dynamic_forms import create_form_from_action, create_action_button
from ivoryos.parsers.returns import extract_return_variables
from ivoryos.script import ScriptEditor, ScriptRenderer


steps = Blueprint('design_steps', __name__)


@steps.get("/draft/steps/<int:uuid>")
def get_step(uuid: int):
    """
    .. :quickref: Workflow Design; Get step editing form

    **Get Step**

    .. http:get:: /draft/steps/<int:uuid>

    Retrieve the HTML editing form for a specific action step in the design canvas.

    :param uuid: The unique ID of the action step.
    :status 200: Returns the step editing form (HTML).
    :status 404: Step not found.
    """
    script = get_script_file()
    action = script.find_by_uuid(uuid)
    if action is None:
        return jsonify({"warning": "Step not found, please refresh the page."}), 404

    elif request.method == 'GET':
        forms = create_form_from_action(action, script=script)
        # session['edit_action'] = action
        return render_template("components/edit_action_form.html",
                               action=action,
                               forms=forms,
                               script=script)



@steps.post("/draft/steps/<int:uuid>")
def save_step(uuid: int):
    """
    .. :quickref: Workflow Design; Save step changes

    **Save Step**

    .. http:post:: /draft/steps/<int:uuid>

    Save the changes made to an action step, including updated arguments and return variables.

    :param uuid: The step number id
    :type uuid: int

    :status 200: render template with action step form
    """
    script = get_script_file()
    action = script.find_by_uuid(uuid)
    warning = None
    if action is not None:
        forms = create_form_from_action(action, script=script)
        kwargs = {field.name: field.data for field in forms if field.name != 'csrf_token'}
        if forms and forms.validate_on_submit():
            save_data = extract_return_variables(kwargs, ScriptEditor.validate_function_name)

            batch_action = kwargs.pop('batch_action', False)
            consolidate_batch_args = request.form.getlist('consolidate_batch_args')

            # Collect dynamic kwargs
            extra_keys = request.form.getlist('extra_key[]')
            extra_values = request.form.getlist('extra_value[]')
            if extra_keys:
                extra_args = {k.strip(): v for k, v in zip(extra_keys, extra_values) if k and k.strip()}
                kwargs.update(extra_args)

            # literal for args with no typehint
            arg_types = action.get('arg_types', {})
            kwargs = ScriptEditor(script).validate_variables(kwargs, arg_types)

            ScriptEditor(script).update_by_uuid(uuid=uuid, args=kwargs, output=save_data, batch_action=batch_action, consolidate_batch_args=consolidate_batch_args)
        else:
            warning = f"Compilation failed: {str(forms.errors)}"
    post_script_file(script)
    try:
        exec_string = ScriptRenderer(script).compile(current_app.config['SCRIPT_FOLDER'])
    except Exception as e:
        exec_string = {}
        warning = f"Compilation failed: {str(e)}"
    # session['python_code'] = exec_string
    design_buttons = {stype: create_action_button(script, stype) for stype in script.stypes}
    return render_template("components/canvas_main.html",
                           script=script,
                           buttons_dict=design_buttons,
                           warning=warning)

@steps.delete("/draft/steps/<int:uuid>")
def delete_step(uuid: int):
    """
    .. :quickref: Workflow Design; Delete a design step

    **Delete Step**

    .. http:delete:: /draft/steps/<int:uuid>

    Remove a specific action step from the current workflow design.

        :param uuid: The step number id
        :type uuid: int

    :status 200: render template with action step form
    """
    script = get_script_file()
    if request.method == 'DELETE':
        ScriptEditor(script).delete_action(uuid)
    post_script_file(script)
    warning = None
    try:
        exec_string = ScriptRenderer(script).compile(current_app.config['SCRIPT_FOLDER'])
    except Exception as e:
        exec_string = {}
        warning = f"Compilation failed: {str(e)}"
    # session['python_code'] = exec_string
    design_buttons = {stype: create_action_button(script, stype) for stype in script.stypes}
    return render_template("components/canvas_main.html",
                               script=script,
                               buttons_dict=design_buttons, warning=warning)


@steps.route("/draft/steps/<int:uuid>/duplicate", methods=["POST"], strict_slashes=False,)
def duplicate_action(uuid: int):
    """
    .. :quickref: Workflow Design; Duplicate a design step

    **Duplicate Step**

    .. http:post:: /draft/steps/<int:uuid>/duplicate

    :param uuid: The step number uuid
    :type uuid: int

    :status 200: render new design script template
    """

    # back = request.referrer
    script = get_script_file()
    ScriptEditor(script).duplicate_action(uuid)
    post_script_file(script)
    warning = None
    try:
        exec_string = ScriptRenderer(script).compile(current_app.config['SCRIPT_FOLDER'])
    except Exception as e:
        exec_string = {}
        warning = f"Compilation failed: {str(e)}"
    # session['python_code'] = exec_string
    design_buttons = {stype: create_action_button(script, stype) for stype in script.stypes}

    return render_template("components/canvas_main.html",
                         script=script,
                         buttons_dict=design_buttons, warning=warning)


@steps.route("/draft/steps/order", methods=['POST'])
@login_required
def update_list():
    """
    .. :quickref: Workflow Design Steps; update the order of steps in the design canvas when reordering steps.

    .. http:post:: /draft/steps/order

    Update the order of steps in the design canvas when reordering steps.

    :form order: A comma-separated string representing the new order of steps.
    :status 200: Successfully updated the order of steps.
    """
    order = request.form['order']
    script = get_script_file()
    script.currently_editing_order = order.split(",", len(script.currently_editing_script))
    ScriptEditor(script).sort_actions()
    warning = None

    post_script_file(script)
    try:
        exec_string = ScriptRenderer(script).compile(current_app.config['SCRIPT_FOLDER'])
    except Exception as e:
        exec_string = {}
        warning = f"Compilation failed: {str(e)}"
    # session['python_code'] = exec_string

    # Return the updated canvas HTML instead of JSON
    design_buttons = {stype: create_action_button(script, stype) for stype in script.stypes}
    return render_template("components/canvas_main.html",
                           script=script,
                           buttons_dict=design_buttons, warning=warning)