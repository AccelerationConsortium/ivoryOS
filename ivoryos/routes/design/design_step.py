from flask import Blueprint, request, session, flash, redirect, url_for
from ivoryos.utils import utils
from ivoryos.utils.form import create_form_from_action

steps = Blueprint('design_steps', __name__)

@steps.route("/step/edit/<string:uuid>", methods=['GET', 'POST'])
def edit_action(uuid: str):
    """
    .. :quickref: Workflow Design Steps; edit parameters of an action step on canvas

    .. http:get:: /design/step/edit

    Load parameter form of an action step

    .. http:post:: /design/step/edit

    :param uuid: The step's uuid
    :type uuid: str

    :form dynamic form: workflow step dynamic inputs
    :status 302: save changes and then redirects to :http:get:`/ivoryos/design/script/`
    """

    script = utils.get_script_file()
    action = script.find_by_uuid(uuid)
    session['edit_action'] = action

    if request.method == "POST" and action is not None:
        forms = create_form_from_action(action, script=script)
        if "back" not in request.form:
            kwargs = {field.name: field.data for field in forms if field.name != 'csrf_token'}
            if forms and forms.validate_on_submit():
                save_as = kwargs.pop('return', '')
                kwargs = script.validate_variables(kwargs)
                script.update_by_uuid(uuid=uuid, args=kwargs, output=save_as)
            else:
                flash(forms.errors)
        session.pop('edit_action')
    return redirect(url_for('design.experiment_builder'))

@steps.route("/step/delete/<int:id>")
def delete_action(id: int):
    """
    .. :quickref: Workflow Design Steps; delete an action step on canvas

    .. http:get:: /design/step/delete

    :param id: The step number id
    :type id: int

    :status 302: save changes and then redirects to :http:get:`/ivoryos/design/script/`
    """

    back = request.referrer
    script = utils.get_script_file()
    script.delete_action(id)
    utils.post_script_file(script)
    return redirect(back)

@steps.route("/step/duplicate/<int:id>")
def duplicate_action(id: int):
    """
    .. :quickref: Workflow Design Steps; duplicate an action step on canvas

    .. http:get:: /design/step/duplicate/<int:id>

    :param id: The step number id
    :type id: int

    :status 302: save changes and then redirects to :http:get:`/ivoryos/design/script/`
    """

    back = request.referrer
    script = utils.get_script_file()
    script.duplicate_action(id)
    utils.post_script_file(script)
    return redirect(back) 