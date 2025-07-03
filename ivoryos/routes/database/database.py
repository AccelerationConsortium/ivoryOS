from flask import Blueprint, redirect, url_for, flash, request, render_template, session, current_app, jsonify
from flask_login import login_required

from ivoryos.utils.db_models import Script, db, WorkflowRun, WorkflowStep
from ivoryos.utils.utils import get_script_file, post_script_file

database = Blueprint('database', __name__, template_folder='templates/database')



@database.route("/database/scripts/edit/<script_name>")
@login_required
def edit_workflow(script_name:str):
    """
    .. :quickref: Database; load workflow script to canvas

    load the selected workflow to the design canvas

    .. http:get:: /database/scripts/edit/<script_name>

    :param script_name: script name
    :type script_name: str
    :status 302: redirect to :http:get:`/ivoryos/design/script/`
    """
    row = Script.query.get(script_name)
    script = Script(**row.as_dict())
    post_script_file(script)
    pseudo_name = session.get("pseudo_deck", "")
    off_line = current_app.config["OFF_LINE"]
    if off_line and pseudo_name and not script.deck == pseudo_name:
        flash(f"Choose the deck with name {script.deck}")
    if request.accept_mimetypes.best_match(['application/json', 'text/html']) == 'application/json':
        return jsonify({
            "script": script.as_dict(),
            "python_script": script.compile(),
        })
    return redirect(url_for('design.experiment_builder'))


@database.route("/database/scripts/delete/<script_name>")
@login_required
def delete_workflow(script_name: str):
    """
    .. :quickref: Database; delete workflow

    delete workflow from database

    .. http:get:: /database/scripts/delete/<script_name>

    :param script_name: workflow name
    :type script_name: str
    :status 302: redirect to :http:get:`/ivoryos/database/scripts/`

    """
    Script.query.filter(Script.name == script_name).delete()
    db.session.commit()
    return redirect(url_for('database.load_from_database'))


@database.route("/database/scripts/save")
@login_required
def publish():
    """
    .. :quickref: Database; save workflow to database

    save workflow to database

    .. http:get:: /database/scripts/save

    :status 302: redirect to :http:get:`/ivoryos/experiment/build/`
    """
    script = get_script_file()
    if not script.name or not script.deck:
        flash("Deck cannot be empty, try to re-submit deck configuration on the left panel")
    row = Script.query.get(script.name)
    if row and row.status == "finalized":
        flash("This is a protected script, use save as to rename.")
    elif row and not session['user'] == row.author:
        flash("You are not the author, use save as to rename.")
    else:
        db.session.merge(script)
        db.session.commit()
        flash("Saved!")
    return redirect(url_for('design.experiment_builder'))


@database.route("/database/scripts/finalize")
@login_required
def finalize():
    """
    .. :quickref: Database; finalize the workflow

    [protected workflow] prevent saving edited workflow to the same workflow name

    .. http:get:: /finalize

    :status 302: redirect to :http:get:`/ivoryos/experiment/build/`

    """
    script = get_script_file()
    script.finalize()
    if script.name:
        db.session.merge(script)
        db.session.commit()
    post_script_file(script)
    return redirect(url_for('design.experiment_builder'))


@database.route("/database/scripts/", strict_slashes=False)
@database.route("/database/scripts/<deck_name>")
@login_required
def load_from_database(deck_name=None):
    """
    .. :quickref: Database; database page

    backend control through http requests

    .. http:get:: /database/scripts/<deck_name>

    :param deck_name: filter for deck name
    :type deck_name: str

    """
    session.pop('edit_action', None)  # reset cache
    query = Script.query
    search_term = request.args.get("keyword", None)
    if search_term:
        query = query.filter(Script.name.like(f'%{search_term}%'))
    if deck_name is None:
        temp = Script.query.with_entities(Script.deck).distinct().all()
        deck_list = [i[0] for i in temp]
    else:
        query = query.filter(Script.deck == deck_name)
        deck_list = ["ALL"]
    page = request.args.get('page', default=1, type=int)
    per_page = 10

    scripts = query.paginate(page=page, per_page=per_page, error_out=False)
    if request.accept_mimetypes.best_match(['application/json', 'text/html']) == 'application/json':
        scripts = query.all()
        script_names = [script.name for script in scripts]
        return jsonify({
            "workflows": script_names,
        })
    else:
        # return HTML
        return render_template("scripts_database.html", scripts=scripts, deck_list=deck_list, deck_name=deck_name)


@database.route("/database/scripts/rename", methods=['POST'])
@login_required
def edit_run_name():
    """
    .. :quickref: Database; edit workflow name

    edit the name of the current workflow, won't save to the database

    .. http:post:: database/scripts/rename

    : form run_name: new workflow name
    :status 302: redirect to :http:get:`/ivoryos/experiment/build/`

    """
    if request.method == "POST":
        run_name = request.form.get("run_name")
        exist_script = Script.query.get(run_name)
        if not exist_script:
            script = get_script_file()
            script.save_as(run_name)
            post_script_file(script)
        else:
            flash("Script name is already exist in database")
        return redirect(url_for("design.experiment_builder"))


@database.route("/database/scripts/save_as", methods=['POST'])
@login_required
def save_as():
    """
    .. :quickref: Database; save the run name as

    save the current workflow script as

    .. http:post:: /database/scripts/save_as

    : form run_name: new workflow name
    :status 302: redirect to :http:get:`/ivoryos/experiment/build/`

    """
    if request.method == "POST":
        run_name = request.form.get("run_name")
        register_workflow = request.form.get("register_workflow")
        exist_script = Script.query.get(run_name)
        if not exist_script:
            script = get_script_file()
            script.save_as(run_name)
            script.registered = register_workflow == "on"
            script.author = session.get('user')
            post_script_file(script)
            publish()
        else:
            flash("Script name is already exist in database")
        return redirect(url_for("design.experiment_builder"))


# -----------------------------------------------------------
# ------------------  Workflow logs   -----------------------
# -----------------------------------------------------------
@database.route('/database/workflows/')
def list_workflows():
    """
    .. :quickref: Database; list all workflow logs

    list all workflow logs

    .. http:get:: /database/workflows/

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


@database.route("/database/workflows/<int:workflow_id>")
def get_workflow_steps(workflow_id:int):
    """
    .. :quickref: Database; list all workflow logs

    list all workflow logs

    .. http:get:: /database/workflows/<int:workflow_id>

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


@database.route("/database/workflows/delete/<int:workflow_id>")
@login_required
def delete_workflow_data(workflow_id: int):
    """
    .. :quickref: Database; delete experiment data from database

    delete workflow data from database

    .. http:get:: /database/workflows/delete/<int:workflow_id>

    :param workflow_id: workflow id
    :type workflow_id: int
    :status 302: redirect to :http:get:`/ivoryos/database/workflows/`

    """
    run = WorkflowRun.query.get(workflow_id)
    db.session.delete(run)
    db.session.commit()
    return redirect(url_for('database.list_workflows'))