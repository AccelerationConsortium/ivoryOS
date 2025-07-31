import os

from flask import Blueprint, redirect, url_for, request, render_template, current_app, jsonify, send_file
from flask_login import login_required

from ivoryos.utils.db_models import db, WorkflowRun, WorkflowStep

data = Blueprint('data', __name__, template_folder='templates')



@data.route('/executions/records')
def list_workflows():
    """
    .. :quickref: Workflow Execution Database; list all workflow execution records

    list all workflow execution records

    .. http:get:: /executions/records

    """
    query = WorkflowRun.query.order_by(WorkflowRun.id.desc())
    search_term = request.args.get("keyword", None)
    if search_term:
        query = query.filter(WorkflowRun.name.like(f'%{search_term}%'))
    page = request.args.get('page', default=1, type=int)
    per_page = 10

    workflows = query.paginate(page=page, per_page=per_page, error_out=False)
    if request.accept_mimetypes.best_match(['application/json', 'text/html']) == 'application/json':
        workflows = query.all()
        workflow_data = {w.id:{"workflow_name":w.name, "start_time":w.start_time} for w in workflows}
        return jsonify({
            "workflow_data": workflow_data,
        })
    else:
        return render_template('workflow_database.html', workflows=workflows)


@data.get("/executions/records/<int:workflow_id>")
def workflow_logs(workflow_id:int):
    """
    .. :quickref: Workflow Data Database; get workflow data, steps, and logs

    get workflow data logs by workflow id

    .. http:get:: /executions/<int:workflow_id>

    :param workflow_id: workflow id
    :type workflow_id: int
    """

    if request.method == 'GET':
        workflow = db.session.get(WorkflowRun, workflow_id)
        steps = WorkflowStep.query.filter_by(workflow_id=workflow_id).order_by(WorkflowStep.start_time).all()

        # Use full objects for template rendering
        grouped = {
            "prep": [],
            "script": {},
            "cleanup": [],
        }

        # Use dicts for JSON response
        grouped_json = {
            "prep": [],
            "script": {},
            "cleanup": [],
        }

        for step in steps:
            step_dict = step.as_dict()

            if step.phase == "prep":
                grouped["prep"].append(step)
                grouped_json["prep"].append(step_dict)

            elif step.phase == "script":
                grouped["script"].setdefault(step.repeat_index, []).append(step)
                grouped_json["script"].setdefault(step.repeat_index, []).append(step_dict)

            elif step.phase == "cleanup" or step.method_name == "stop":
                grouped["cleanup"].append(step)
                grouped_json["cleanup"].append(step_dict)

        if request.accept_mimetypes.best_match(['application/json', 'text/html']) == 'application/json':
            return jsonify({
                "workflow_info": workflow.as_dict(),
                "steps": grouped_json,
            })
        else:
            return render_template("workflow_view.html", workflow=workflow, grouped=grouped)


@data.delete("/executions/records/<int:workflow_id>")
@login_required
def delete_workflow_record(workflow_id: int):
    """
    .. :quickref: Workflow Data Database; delete a workflow execution record

    delete a workflow execution record by workflow id

    .. http:delete:: /executions/records/<int:workflow_id>

    :param workflow_id: workflow id
    :type workflow_id: int
    :status 200: return success message
    """
    run = WorkflowRun.query.get(workflow_id)
    db.session.delete(run)
    db.session.commit()
    return jsonify(success=True)


@data.route('/files/execution-data/<string:filename>')
def download_results(filename:str):
    """
    .. :quickref: Workflow data; download a workflow data file (.CSV)

    .. http:get:: /files/execution-data/<string:filename>

    :param filename: workflow data filename
    :type filename: str

    # :status 302: load pseudo deck and then redirects to :http:get:`/ivoryos/executions`
    """

    filepath = os.path.join(current_app.config["DATA_FOLDER"], filename)
    return send_file(os.path.abspath(filepath), as_attachment=True)