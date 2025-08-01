from flask import Blueprint, request, session, flash, redirect, url_for, jsonify, render_template, current_app
from flask_login import login_required

from ivoryos.utils import utils
from ivoryos.utils.form import create_form_from_action, create_action_button

steps = Blueprint('design_steps', __name__)


@steps.get("/draft/steps/<int:uuid>")
def get_step(uuid: int):
    """
    .. :quickref: Workflow Design Steps; get an action step editing form

    .. http:get:: /steps/<int:uuid>

    get the editing form for an action step

    :param uuid: The step number id
    :type uuid: int

    :status 200: render template with action step form
    """
    script = utils.get_script_file()
    action = script.find_by_uuid(uuid)
    if request.method == 'GET':
        # forms = create_form_from_action(action, script=script)
        # session['edit_action'] = action
        return render_template("components/edit_action_form.html",
                               action=action,
                               forms=create_form_from_action(action, script=script))


@steps.post("/draft/steps/<int:uuid>")
def save_step(uuid: int):
    """
    .. :quickref: Workflow Design Steps; save an action step on canvas

    .. http:post:: /steps/<int:uuid>

        save the changes of an action step

        :param uuid: The step number id
        :type uuid: int

    :status 200: render template with action step form
    """
    script = utils.get_script_file()
    action = script.find_by_uuid(uuid)
    if action is not None:
        forms = create_form_from_action(action, script=script)
        kwargs = {field.name: field.data for field in forms if field.name != 'csrf_token'}
        if forms and forms.validate_on_submit():
            save_as = kwargs.pop('return', '')
            kwargs = script.validate_variables(kwargs)
            script.update_by_uuid(uuid=uuid, args=kwargs, output=save_as)
        else:
            flash(forms.errors)
    utils.post_script_file(script)
    exec_string = script.compile(current_app.config['SCRIPT_FOLDER'])
    session['python_code'] = exec_string
    design_buttons = {stype: create_action_button(script, stype) for stype in script.stypes}
    return render_template("components/canvas_main.html",
                               script=script,
                               buttons_dict=design_buttons)

@steps.delete("/draft/steps/<int:uuid>")
def delete_step(uuid: int):
    """
    .. :quickref: Workflow Design Steps; delete an action step on canvas

    .. http:delete:: /steps/<int:uuid>

        delete an action step

        :param uuid: The step number id
        :type uuid: int

    :status 200: render template with action step form
    """
    script = utils.get_script_file()
    if request.method == 'DELETE':
        script.delete_action(uuid)
    utils.post_script_file(script)
    exec_string = script.compile(current_app.config['SCRIPT_FOLDER'])
    session['python_code'] = exec_string
    design_buttons = {stype: create_action_button(script, stype) for stype in script.stypes}
    return render_template("components/canvas_main.html",
                               script=script,
                               buttons_dict=design_buttons)


@steps.route("/draft/steps/<int:uuid>/duplicate", methods=["POST"], strict_slashes=False,)
def duplicate_action(uuid: int):
    """
    .. :quickref: Workflow Design Steps; duplicate an action step on canvas

    .. http:post:: /draft/steps/<int:uuid>/duplicate

    :param uuid: The step number uuid
    :type uuid: int

    :status 200: render new design script template
    """

    # back = request.referrer
    script = utils.get_script_file()
    script.duplicate_action(uuid)
    utils.post_script_file(script)
    exec_string = script.compile(current_app.config['SCRIPT_FOLDER'])
    session['python_code'] = exec_string
    design_buttons = {stype: create_action_button(script, stype) for stype in script.stypes}

    return render_template("components/canvas_main.html",
                         script=script,
                         buttons_dict=design_buttons)


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
    script = utils.get_script_file()
    script.currently_editing_order = order.split(",", len(script.currently_editing_script))
    script.sort_actions()

    utils.post_script_file(script)
    exec_string = script.compile(current_app.config['SCRIPT_FOLDER'])
    session['python_code'] = exec_string

    # Return the updated canvas HTML instead of JSON
    design_buttons = {stype: create_action_button(script, stype) for stype in script.stypes}
    return render_template("components/canvas_main.html",
                           script=script,
                           buttons_dict=design_buttons)