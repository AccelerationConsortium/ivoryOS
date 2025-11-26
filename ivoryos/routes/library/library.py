from flask import Blueprint, redirect, url_for, flash, request, render_template, session, current_app, jsonify
from flask_login import login_required, current_user

from ivoryos.utils.db_models import Script, db, WorkflowRun, WorkflowStep
from ivoryos.utils.utils import get_script_file, post_script_file

library = Blueprint('library', __name__, template_folder='templates')



@library.route("/<string:script_name>", methods=["GET", "POST", "DELETE"])
@login_required
def workflow_script(script_name:str):
    # todo: split this into two routes, one for GET and POST, another for DELETE
    """
    .. :quickref: Workflow Script Database; get, post, delete a workflow script

    .. http:get:: /library/<string: script_name>

    :param script_name: script name
    :type script_name: str
    :status 302: redirect to :http:get:`/ivoryos/draft`

    .. http:post:: /library/<string: script_name>

    :param script_name: script name
    :type script_name: str
    :status 200: json response with success status

    .. http:delete:: /library/<string: script_name>

    :param script_name: script name
    :type script_name: str
    :status 302: redirect to :http:get:`/ivoryos/draft`

    """
    row = Script.query.get(script_name)
    if request.method == "DELETE":
        if not row:
            return jsonify(success=False)
        db.session.delete(row)
        db.session.commit()
        return jsonify(success=True)
    if request.method == "GET":
        if not row:
            return jsonify(success=False)
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
    if request.method == "POST":
        status = publish()
        return jsonify(status)
    return None


def publish():
    script = get_script_file()

    if script.author is None:
        script.author = current_user.get_id()
    if not script.name or not script.deck:
        return {"success": False, "error": "Deck cannot be empty, try to re-submit deck configuration on the left panel"}
    row = Script.query.get(script.name)
    if row and row.status == "finalized":
        return {"success": False, "error": "This is a protected script, use save as to rename."}

    elif row and current_user.get_id() != row.author:
        return {"success": False, "error": "You are not the author, use save as to rename."}
    else:
        db.session.merge(script)
        db.session.commit()
        return {"success": True, "message": "Script published successfully"}


@library.get("/", strict_slashes=False)
@login_required
def load_from_database():
    """
    .. :quickref: Script Database; database page

    backend control through http requests

    .. http:get:: /library


    """
    session.pop('edit_action', None)  # reset cache
    query = Script.query
    search_term = request.args.get("keyword", None)
    deck_name = request.args.get("deck", None)
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
        return render_template("library.html", scripts=scripts, deck_list=deck_list, deck_name=deck_name)




@library.post("/", strict_slashes=False)
@login_required
def save_as():
    """
    .. :quickref: Script Database; save the script as

    save the current workflow script as

    .. http:post:: /library

    : form run_name: new workflow name
    :status 302: redirect to :http:get:`/ivoryos/draft`

    """
    if request.method == "POST":
        run_name = request.form.get("run_name")
        description = request.form.get("description")
        ## TODO: check if run_name is valid
        register_workflow = request.form.get("register_workflow")
        script = get_script_file()
        script.save_as(run_name)
        script.registered = register_workflow == "on"
        script.author = current_user.get_id()
        script.description = description
        post_script_file(script)
        status = publish()
        if request.accept_mimetypes.best_match(['application/json', 'text/html']) == 'application/json':
            return jsonify(status)
        else:
            if status["success"]:
                flash("Script saved successfully")
            else:
                flash(status["error"], "error")
            return redirect(url_for('design.experiment_builder'))

