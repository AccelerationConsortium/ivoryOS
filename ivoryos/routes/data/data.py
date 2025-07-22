import os

from flask import Blueprint, redirect, url_for, request, render_template, current_app, jsonify, send_file
from flask_login import login_required

from ivoryos.utils.db_models import db, WorkflowRun, WorkflowStep

data = Blueprint('data', __name__, template_folder='templates')



@data.route('/all')
def list_workflows():
    """
    .. :quickref: Workflow Data Database; list all workflow logs

    list all workflow data logs

    .. http:get:: /data/all/

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


@data.route("/get/<int:workflow_id>")
def get_workflow_steps(workflow_id:int):
    """
    .. :quickref: Workflow Data Database; get workflow data logs

    get workflow data logs by workflow id

    .. http:get:: /data/get/<int:workflow_id>

    :param workflow_id: workflow id
    :type workflow_id: int
    """
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


@data.route("/delete/<int:workflow_id>")
@login_required
def delete_workflow_data(workflow_id: int):
    """
    .. :quickref: Workflow Data Database; delete experiment data from database

    delete workflow data from database

    .. http:get:: /data/delete/<int:workflow_id>

    :param workflow_id: workflow id
    :type workflow_id: int
    :status 302: redirect to :http:get:`/ivoryos/data/all/`

    """
    run = WorkflowRun.query.get(workflow_id)
    db.session.delete(run)
    db.session.commit()
    return redirect(url_for('database.list_workflows'))


@data.route('/download/data/<string:filename>')
def download_results(filename:str):
    """
    .. :quickref: Workflow data; download a workflow data file (.CSV)

    .. http:get:: data/download/data

    :param filename: workflow data filename
    :type filename: str

    # :status 302: load pseudo deck and then redirects to :http:get:`/ivoryos/data/all`
    """

    filepath = os.path.join(current_app.config["DATA_FOLDER"], filename)
    return send_file(os.path.abspath(filepath), as_attachment=True)