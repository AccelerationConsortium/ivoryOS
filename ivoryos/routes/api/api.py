import copy
import os
from flask import Blueprint, jsonify, request, current_app

from ivoryos.routes.control.control import find_instrument_by_name
from ivoryos.utils.form import create_form_from_module
from ivoryos.utils.global_config import GlobalConfig
from ivoryos.utils.db_models import Script, WorkflowRun, SingleStep, WorkflowStep

from ivoryos.socket_handlers import abort_pending, abort_current, pause, retry, runner
from ivoryos.utils.task_runner import TaskRunner

api = Blueprint('api', __name__)
global_config = GlobalConfig()
task_runner = TaskRunner()

#TODO: add authentication and authorization to the API endpoints


@api.route("/control/", strict_slashes=False, methods=['GET'])
@api.route("/control/<string:instrument>", methods=['POST'])
def backend_control(instrument: str=None):
    """
    .. :quickref: Backend Control; backend control

    backend control through http requests

    .. http:get:: /api/control/

    :param instrument: instrument name
    :type instrument: str

    .. http:post:: /api/control/

    """
    if instrument:
        inst_object = find_instrument_by_name(instrument)
        forms = create_form_from_module(sdl_module=inst_object, autofill=False, design=False)

    if request.method == 'POST':
        method_name = request.json.get("hidden_name", None)
        form = forms.get(method_name, None)
        if form:
            kwargs = {field.name: field.data for field in form if field.name not in ['csrf_token', 'hidden_name']}
            wait = request.form.get("hidden_wait", "true") == "true"
            output = task_runner.run_single_step(component=instrument, method=method_name, kwargs=kwargs, wait=wait,
                                            current_app=current_app._get_current_object())
            return jsonify(output), 200

    snapshot = copy.deepcopy(global_config.deck_snapshot)
    # Iterate through each instrument in the snapshot
    for instrument_key, instrument_data in snapshot.items():
        # Iterate through each function associated with the current instrument
        for function_key, function_data in instrument_data.items():
            # Convert the function signature to a string representation
            function_data['signature'] = str(function_data['signature'])
    return jsonify(snapshot), 200