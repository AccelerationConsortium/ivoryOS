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


@api.route("/runner/status", methods=["GET"])
def runner_status():
    """
    .. :quickref: Runner Status; backend runner status

    get is system is busy and current task

    .. http:get:: /api/runner/status


    """
    # runner = global_config.runner
    runner_busy = global_config.runner_lock.locked()
    status = {"busy": runner_busy}
    task_status = global_config.runner_status
    current_step = {}

    if task_status is not None:
        task_type = task_status["type"]
        task_id = task_status["id"]
        if task_type == "task":
            step = SingleStep.query.get(task_id)
            current_step = step.as_dict()
        if task_type == "workflow":
            workflow = WorkflowRun.query.get(task_id)
            if workflow is not None:
                latest_step = WorkflowStep.query.filter_by(workflow_id=workflow.id).order_by(
                    WorkflowStep.start_time.desc()).first()
                if latest_step is not None:
                    current_step = latest_step.as_dict()
                status["workflow_status"] = {"workflow_info": workflow.as_dict(), "runner_status": runner.get_status()}
    status["current_task"] = current_step
    return jsonify(status), 200


@api.route("/runner/abort_pending", methods=["POST"])
def api_abort_pending():
    """
    .. :quickref: Workflow Control; abort pending workflow

    finish current iteration, and stop pending workflow iterations

    .. http:get:: /api/runner/abort_pending

    """
    abort_pending()
    return jsonify({"status": "ok"}), 200


@api.route("/runner/abort_current", methods=["POST"])
def api_abort_current():
    """
    .. :quickref: Workflow Control; abort starting from next task

    finish current task, and stop all pending tasks or iterations

    .. http:get:: /api/runner/abort_current

    """
    abort_current()
    return jsonify({"status": "ok"}), 200


@api.route("/runner/pause", methods=["POST"])
def api_pause():
    """
    .. :quickref: Workflow Control; pause and resume

    pause workflow iterations or resume workflow iterations

    .. http:get:: /api/runner/pause

    """
    msg = pause()
    return jsonify({"status": "ok", "pause_status": msg}), 200


@api.route("/runner/retry", methods=["POST"])
def api_retry():
    """
    .. :quickref: Workflow Control; retry the failed workflow step.

    retry workflow step

    .. http:get:: /api/runner/retry

    """
    retry()
    return jsonify({"status": "ok, retrying failed step"}), 200



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
        method_name = request.form.get("hidden_name", None)
        form = forms.get(method_name, None)
        if form:
            kwargs = {field.name: field.data for field in form if field.name not in ['csrf_token', 'hidden_name']}
            wait = request.form.get("hidden_wait", "true") == "true"
            output = task_runner.run_single_step(component=instrument, method=method_name, kwargs=kwargs, wait=wait,
                                            current_app=current_app._get_current_object())
            return jsonify(output), 200

    snapshot = global_config.deck_snapshot.copy()
    # Iterate through each instrument in the snapshot
    for instrument_key, instrument_data in snapshot.items():
        # Iterate through each function associated with the current instrument
        for function_key, function_data in instrument_data.items():
            # Convert the function signature to a string representation
            function_data['signature'] = str(function_data['signature'])
    return jsonify(snapshot), 200