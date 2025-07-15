import os
from flask import Blueprint, jsonify, request, session
from ivoryos.utils import utils
from ivoryos.utils.global_config import GlobalConfig
from ivoryos.utils.db_models import Script, WorkflowRun, SingleStep, WorkflowStep
from ivoryos.utils.py_to_json import convert_to_cards
from ivoryos.routes.database.database import publish
from ivoryos.socket_handlers import abort_pending, abort_current, pause, retry, runner

api = Blueprint('api', __name__)
global_config = GlobalConfig()



@api.route("/api/runner/status", methods=["GET"])
def runner_status():
    """Get the execution status"""
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


@api.route("/api/runner/abort_pending", methods=["POST"])
def api_abort_pending():
    """Abort pending action(s) during execution"""
    abort_pending()
    return jsonify({"status": "ok"}), 200


@api.route("/api/runner/abort_current", methods=["POST"])
def api_abort_current():
    """Abort right after current action during execution"""
    abort_current()
    return jsonify({"status": "ok"}), 200


@api.route("/api/runner/pause", methods=["POST"])
def api_pause():
    """Pause during execution"""
    msg = pause()
    return jsonify({"status": "ok", "pause_status": msg}), 200


@api.route("/api/runner/retry", methods=["POST"])
def api_retry():
    """Retry when error occur during execution"""
    retry()
    return jsonify({"status": "ok, retrying failed step"}), 200


@api.route("/api/design/submit", methods=["POST"])
def submit_script():
    """Submit script"""
    deck = global_config.deck
    deck_name = os.path.splitext(os.path.basename(deck.__file__))[0] if deck.__name__ == "__main__" else deck.__name__
    script = Script(author=session.get('user'), deck=deck_name)
    script_collection = request.get_json()
    workflow_name = script_collection.pop("workflow_name")
    script.python_script = script_collection
    # todo check script format
    script.name = workflow_name
    result = {}
    for stype, py_str in script_collection.items():
        try:
            card = convert_to_cards(py_str)
            script.script_dict[stype] = card
            result[stype] = "success"
        except Exception as e:
            result[
                stype] = f"failed to transcript to ivoryos visualization, but function can still run. error: {str(e)}"
    utils.post_script_file(script)
    try:
        publish()
        db_status = "success"
    except Exception as e:
        db_status = "failed"
    return jsonify({"script": result, "db": db_status}), 200