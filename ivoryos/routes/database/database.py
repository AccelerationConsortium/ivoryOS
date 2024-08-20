from flask import Blueprint, redirect, url_for, flash, request, render_template, session
from flask_login import login_required

from ivoryos.utils.db_models import Script, User, db
from ivoryos.utils.utils import get_script_file, post_script_file
global deck

database = Blueprint('database', __name__, template_folder='templates/database')


@database.route("/delete/<id>")
@login_required
def delete_action(id):
    back = request.referrer
    script = get_script_file()
    script.delete_action(id)
    post_script_file(script)
    return redirect(back)


@database.route("/edit_workflow/<workflow_name>")
@login_required
def edit_workflow(workflow_name):
    row = Script.query.get(workflow_name)
    script = Script(**row.as_dict())
    post_script_file(script)
    pseudo_name = session.get("pseudo_deck", "")
    if not deck and pseudo_name and not script.deck == pseudo_name:
        flash(f"Choose the deck with name {script.deck}")
    return redirect(url_for('design.experiment_builder'))


@database.route("/delete_workflow/<workflow_name>")
@login_required
def delete_workflow(workflow_name):
    Script.query.filter(Script.name == workflow_name).delete()
    db.session.commit()
    return redirect(url_for('database.load_from_database'))


@database.route("/publish")
@login_required
def publish():
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


@database.route("/finalize")
@login_required
def finalize():
    script = get_script_file()
    script.finalize()
    db.session.merge(script)
    db.session.commit()
    post_script_file(script)
    return redirect(url_for('design.experiment_builder'))


@database.route("/database/", methods=['GET', 'POST'])
@database.route("/database/<deck_name>", methods=['GET', 'POST'])
@login_required
def load_from_database(deck_name=None):
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

    workflows = query.paginate(page=page, per_page=per_page, error_out=False)
    return render_template("experiment_database.html", workflows=workflows, deck_list=deck_list, deck_name=deck_name)


@database.route("/edit_run_name", methods=['GET', 'POST'])
@login_required
def edit_run_name():
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


@database.route("/save_as", methods=['GET', 'POST'])
@login_required
def save_as():
    # script = get_script_file()
    if request.method == "POST":
        run_name = request.form.get("run_name")
        exist_script = Script.query.get(run_name)
        if not exist_script:
            script = get_script_file()
            script.save_as(run_name)
            script.author = session.get('user')
            post_script_file(script)
            publish()
        else:
            flash("Script name is already exist in database")
        return redirect(url_for("design.experiment_builder"))
