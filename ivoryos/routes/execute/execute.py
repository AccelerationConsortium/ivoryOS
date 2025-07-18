import csv
import os
import time

from flask import Blueprint, redirect, url_for, flash, jsonify, request, render_template, session, \
    current_app, g
from flask_login import login_required

from ivoryos.routes.execute.execute_file import files
from ivoryos.utils import utils
from ivoryos.utils.global_config import GlobalConfig
from ivoryos.utils.form import create_action_button, format_name, create_form_from_pseudo, \
    create_form_from_action, create_all_builtin_forms

from werkzeug.utils import secure_filename

from ivoryos.socket_handlers import runner

execute = Blueprint('execute', __name__, template_folder='templates')

execute.register_blueprint(files)
# Register sub-blueprints
global_config = GlobalConfig()


@execute.route("/campaign", methods=['GET', 'POST'])
@login_required
def experiment_run():
    """
    .. :quickref: Workflow Execution; Execute/iterate the workflow

    .. http:get:: /design/campaign

    Compile the workflow and load the experiment execution interface.

    .. http:post:: /design/campaign

    Start workflow execution

    """
    deck = global_config.deck
    script = utils.get_script_file()
    # runner = global_config.runner
    existing_data = None
    # script.sort_actions() # handled in update list
    off_line = current_app.config["OFF_LINE"]
    deck_list = utils.import_history(os.path.join(current_app.config["OUTPUT_FOLDER"], 'deck_history.txt'))

    design_buttons = {stype: create_action_button(script, stype) for stype in script.stypes}
    config_preview = []
    config_file_list = [i for i in os.listdir(current_app.config["CSV_FOLDER"]) if not i == ".gitkeep"]

    try:
        exec_string = script.python_script if script.python_script else script.compile(
            current_app.config['SCRIPT_FOLDER'])
    except Exception as e:
        flash(e.__str__())
        if request.accept_mimetypes.best_match(['application/json', 'text/html']) == 'application/json':
            return jsonify({"error": e.__str__()})
        else:
            return redirect(url_for("design.experiment_builder"))

    config_file = request.args.get("filename")
    config = []
    if config_file:
        session['config_file'] = config_file
    filename = session.get("config_file")
    if filename:
        config = list(csv.DictReader(open(os.path.join(current_app.config['CSV_FOLDER'], filename))))
        config_preview = config[1:]
        arg_type = config.pop(0)  # first entry is types

    try:
        # Handle both string and dict exec_string
        if isinstance(exec_string, dict):
            for key, func_str in exec_string.items():
                exec(func_str)
            line_collection = script.convert_to_lines(exec_string)
        else:
            # Handle string case - you might need to adjust this based on your needs
            line_collection = []
    except Exception:
        flash(f"Please check syntax!!")
        return redirect(url_for("design.experiment_builder"))

    run_name = script.name if script.name else "untitled"

    dismiss = session.get("dismiss", None)
    script = utils.get_script_file()
    no_deck_warning = False

    _, return_list = script.config_return()
    config_list, config_type_list = script.config("script")
    data_list = os.listdir(current_app.config['DATA_FOLDER'])
    data_list.remove(".gitkeep") if ".gitkeep" in data_list else data_list

    if deck is None:
        no_deck_warning = True
        flash(f"No deck is found, import {script.deck}")
    elif script.deck:
        is_deck_match = script.deck == deck.__name__ or script.deck == \
                        os.path.splitext(os.path.basename(deck.__file__))[0]
        if not is_deck_match:
            flash(f"This script is not compatible with current deck, import {script.deck}")

    if request.method == "POST":
        bo_args = None
        compiled = False
        if request.accept_mimetypes.best_match(['application/json', 'text/html']) == 'application/json':
            payload_json = request.get_json()
            compiled = True
            if "kwargs" in payload_json:
                config = payload_json["kwargs"]
            elif "parameters" in payload_json:
                bo_args = payload_json
            repeat = payload_json.pop("repeat", None)
        else:
            if "bo" in request.form:
                bo_args = request.form.to_dict()
                existing_data = bo_args.pop("existing_data")
            if "online-config" in request.form:
                config = utils.web_config_entry_wrapper(request.form.to_dict(), config_list)
            repeat = request.form.get('repeat', None)

        try:
            datapath = current_app.config["DATA_FOLDER"]
            run_name = script.validate_function_name(run_name)
            runner.run_script(script=script, run_name=run_name, config=config, bo_args=bo_args,
                              logger=g.logger, socketio=g.socketio, repeat_count=repeat,
                              output_path=datapath, compiled=compiled, history=existing_data,
                              current_app=current_app._get_current_object()
                              )
            if utils.check_config_duplicate(config):
                flash(f"WARNING: Duplicate in config entries.")
        except Exception as e:
            if request.accept_mimetypes.best_match(['application/json', 'text/html']) == 'application/json':
                return jsonify({"error": e.__str__()})
            else:
                flash(e)

    if request.accept_mimetypes.best_match(['application/json', 'text/html']) == 'application/json':
        # wait to get a workflow ID
        while not global_config.runner_status:
            time.sleep(1)
        return jsonify({"status": "task started", "task_id": global_config.runner_status.get("id")})
    else:
        return render_template('experiment_run.html', script=script.script_dict, filename=filename,
                               dot_py=exec_string, line_collection=line_collection,
                               return_list=return_list, config_list=config_list, config_file_list=config_file_list,
                               config_preview=config_preview, data_list=data_list, config_type_list=config_type_list,
                               no_deck_warning=no_deck_warning, dismiss=dismiss, design_buttons=design_buttons,
                               history=deck_list, pause_status=runner.pause_status())


@execute.route('/data_preview/<filename>')
@login_required
def data_preview(filename):
    """Serve a preview of the selected data file (CSV) as JSON."""
    import csv
    import os
    from flask import abort

    data_folder = current_app.config['DATA_FOLDER']
    file_path = os.path.join(data_folder, filename)
    if not os.path.exists(file_path):
        abort(404)
    with open(file_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        rows = list(reader)
    # Limit preview to first 10 rows
    return jsonify({"columns": reader.fieldnames, "rows": rows})


