import os
import csv
import io

from flask import Blueprint, redirect, url_for, request, render_template, current_app, jsonify, send_file, Response
from flask_login import login_required

from ivoryos.utils.db_models import db, WorkflowRun, WorkflowStep, WorkflowPhase

data = Blueprint('data', __name__, template_folder='templates')



@data.route('/executions/records')
@login_required
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

    .. http:get:: /executions/records/<int:workflow_id>

    :param workflow_id: workflow id
    :type workflow_id: int
    """
    workflow = db.session.get(WorkflowRun, workflow_id)
    if not workflow:
        return jsonify({"error": "Workflow not found"}), 404

    # Query all phases for this run, ordered by start_time
    phases = WorkflowPhase.query.filter_by(run_id=workflow_id).order_by(WorkflowPhase.start_time).all()

    # Prepare grouped data for template (full objects)
    grouped = {
        "prep": [],
        "script": {},
        "cleanup": [],
    }

    # Prepare grouped data for JSON (dicts)
    grouped_json = {
        "prep": [],
        "script": {},
        "cleanup": [],
    }

    for phase in phases:
        phase_dict = phase.as_dict()

        # Steps sorted by step_index
        steps = sorted(phase.steps, key=lambda s: s.step_index)
        phase_steps_dicts = [s.as_dict() for s in steps]

        if phase.name == "prep":
            grouped["prep"].append(phase)
            grouped_json["prep"].append({
                **phase_dict,
                "steps": phase_steps_dicts
            })

        elif phase.name == "main":
            grouped["script"].setdefault(phase.repeat_index, []).append(phase)
            grouped_json["script"].setdefault(phase.repeat_index, []).append({
                **phase_dict,
                "steps": phase_steps_dicts
            })

        elif phase.name == "cleanup":
            grouped["cleanup"].append(phase)
            grouped_json["cleanup"].append({
                **phase_dict,
                "steps": phase_steps_dicts
            })

    if request.accept_mimetypes.best_match(['application/json', 'text/html']) == 'application/json':
        return jsonify({
            "workflow_info": workflow.as_dict(),
            "phases": grouped_json,
            "csv_file_name": f"{workflow.data_path}"
        })
    else:
        return render_template("workflow_view.html", workflow=workflow, grouped=grouped)


@data.get("/executions/records/<int:workflow_id>/steps_data_csv")
@login_required
def download_workflow_steps_data_csv(workflow_id: int):
    """
    download steps data by workflow id as CSV
    """
    workflow = db.session.get(WorkflowRun, workflow_id)
    if not workflow:
        return jsonify({"error": "Workflow not found"}), 404

    base_data_path = workflow.data_path if workflow.data_path else f"{workflow.name}_{workflow.start_time.strftime('%Y-%m-%d %H-%M')}"

    # Query all phases for this run
    phases = WorkflowPhase.query.filter_by(run_id=workflow_id).order_by(WorkflowPhase.start_time).all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(["Phase Name", "Phase Repeat Index",
                     "Step Index", "Step Start Time", "Step End Time", "Step Run Error", "Step Method Name", "Step Output",
                     ])

    for phase in phases:
        for step in phase.steps:
            step_parameters = step.workflow_phases.parameters[0] if step.workflow_phases.parameters else {}
            step_output = step.output  # at time of writing the output contains full context of action, so both input parameters, variables, and returns
            if set(step_output) - set(step_parameters) == set():
                # there is no difference between the step parameters and the step output -> no set variables/return values in the step
                step_output = {}
            else:
                output_keys = set(step_output) - set(step_parameters)
                step_output = {k: v for k, v in step_output.items() if k in output_keys}

            writer.writerow([
                phase.name,
                phase.repeat_index,
                step.step_index,
                step.start_time,
                step.end_time,
                step.run_error,
                step.method_name,
                step_output,
            ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={base_data_path}_steps.csv"}
    )


@data.get("/executions/data/<int:workflow_id>")
def workflow_phase_data(workflow_id: int):
    """
    .. :quickref: Workflow Data Database; get workflow data for plotting

    get workflow data for plotting by workflow id

    .. http:get:: /executions/data/<int: workflow_id>

    :param workflow_id: workflow id
    """

    workflow = db.session.get(WorkflowRun, workflow_id)
    if not workflow:
        return jsonify({})

    phase_data = {}
    main_phases = WorkflowPhase.query.filter_by(run_id=workflow_id, name='main') \
        .order_by(WorkflowPhase.repeat_index).all()

    for phase in main_phases:
        outputs = phase.outputs or {}
        phase_index = phase.repeat_index
        phase_data[phase_index] = {}

        # Normalize everything to a list of dicts
        if isinstance(outputs, dict):
            outputs = [outputs]
        elif isinstance(outputs, list):
            # flatten if it’s nested like [[{...}, {...}]]
            outputs = [
                item for sublist in outputs
                for item in (sublist if isinstance(sublist, list) else [sublist])
            ]

        # convert each output entry to plotting format
        for out in outputs:
            if not isinstance(out, dict):
                continue
            for k, v in out.items():
                if isinstance(v, (int, float)):
                    phase_data[phase_index].setdefault(k, []).append(
                        {"x": phase_index, "y": v}
                    )
                elif isinstance(v, list) and all(isinstance(i, (int, float)) for i in v):
                    phase_data[phase_index].setdefault(k, []).extend(
                        {"x": phase_index, "y": val} for val in v
                    )

    return jsonify(phase_data)


@data.delete("/executions/records/<int:workflow_id>")
@login_required
def delete_workflow_record(workflow_id: int):
    """
    .. :quickref: Workflow Data Database; delete a workflow execution record

    delete a workflow execution record by workflow id

    .. http:delete:: /executions/records/<int: workflow_id>

    :param workflow_id: workflow id
    :type workflow_id: int
    :status 200: return success message
    """
    run = WorkflowRun.query.get(workflow_id)
    db.session.delete(run)
    db.session.commit()
    return jsonify(success=True)


@data.route('/files/execution-data/<string:filename>')
@login_required
def download_results(filename:str):
    """
    .. :quickref: Workflow data; download a workflow data file (.CSV)

    .. http:get:: /files/execution-data/<string:filename>

    :param filename: workflow data filename
    :type filename: str

    # :status 302: load pseudo deck and then redirects to :http:get:`/ivoryos/executions/records`
    """

    filepath = os.path.join(current_app.config["DATA_FOLDER"], filename)
    return send_file(os.path.abspath(filepath), as_attachment=True)