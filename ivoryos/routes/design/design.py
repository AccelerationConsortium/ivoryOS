import csv
import json
import os
import pickle
import sys
import time

from flask import Blueprint, redirect, url_for, flash, jsonify, send_file, request, render_template, session, \
    current_app, g
from flask_login import login_required
from werkzeug.utils import secure_filename

from ivoryos.routes.database.database import publish
from ivoryos.utils import utils
from ivoryos.utils.global_config import GlobalConfig
from ivoryos.utils.form import create_builtin_form, create_action_button, format_name, create_form_from_pseudo, \
    create_form_from_action, create_all_builtin_forms
from ivoryos.utils.db_models import Script, WorkflowRun, SingleStep, WorkflowStep
from ivoryos.utils.py_to_json import convert_to_cards
from ivoryos.utils.script_runner import ScriptRunner

# Import the new modular components
from .socket_handlers import socketio
from .api_routes import api
from .file_operations import files
from .step_management import steps

design = Blueprint('design', __name__, template_folder='templates/design')

# Register sub-blueprints
design.register_blueprint(api)
design.register_blueprint(files)
design.register_blueprint(steps)

global_config = GlobalConfig()
runner = ScriptRunner()

# ---- Main Design Routes ----

@design.route("/design/script/", methods=['GET', 'POST'])
@design.route("/design/script/<instrument>/", methods=['GET', 'POST'])
@login_required
def experiment_builder(instrument=None):
    """
    .. :quickref: Workflow Design; Build experiment workflow

    **Experiment Builder**

    This route allows users to build and edit experiment workflows. Users can interact with available instruments,
    define variables, and manage experiment scripts.

    .. http:get:: /design/script

    Load the experiment builder interface.

    :param instrument: The specific instrument for which to load functions and forms.
    :type instrument: str
    :status 200: Experiment builder loaded successfully.

    .. http:post:: /design/script

    Submit form data to add or modify actions in the experiment script.

    **Adding action to canvas**

    :form return: (optional) The name of the function or method to add to the script.
    :form dynamic: depend on the selected instrument and its metadata.

    :status 200: Action added or modified successfully.
    :status 400: Validation errors in submitted form data.
    :status 302: Toggles autofill or redirects to refresh the page.

    **Toggle auto parameter name fill**:

    :status 200: autofill toggled successfully

    """
    deck = global_config.deck
    script = utils.get_script_file()

    if deck and script.deck is None:
        script.deck = os.path.splitext(os.path.basename(deck.__file__))[
            0] if deck.__name__ == "__main__" else deck.__name__

    pseudo_deck_name = session.get('pseudo_deck', '')
    pseudo_deck_path = os.path.join(current_app.config["DUMMY_DECK"], pseudo_deck_name)
    off_line = current_app.config["OFF_LINE"]
    enable_llm = current_app.config["ENABLE_LLM"]
    autofill = session.get('autofill')

    # autofill is not allowed for prep and cleanup
    autofill = autofill if script.editing_type == "script" else False
    forms = None
    pseudo_deck = utils.load_deck(pseudo_deck_path) if off_line and pseudo_deck_name else None
    if off_line and pseudo_deck is None:
        flash("Choose available deck below.")

    deck_list = utils.available_pseudo_deck(current_app.config["DUMMY_DECK"])

    functions = {}
    if deck:
        deck_variables = list(global_config.deck_snapshot.keys())
        deck_variables.insert(0, "flow_control")
    else:
        deck_variables = list(pseudo_deck.keys()) if pseudo_deck else []
        deck_variables.remove("deck_name") if len(deck_variables) > 0 else deck_variables
    
    edit_action_info = session.get("edit_action")
    if edit_action_info:
        forms = create_form_from_action(edit_action_info, script=script)
    elif instrument:
        if instrument == 'flow_control':
            forms = create_all_builtin_forms(script=script)
        elif instrument in global_config.defined_variables.keys():
            _object = global_config.defined_variables.get(instrument)
            functions = utils._inspect_class(_object)
            forms = create_form_from_pseudo(pseudo=functions, autofill=autofill, script=script)
        else:
            if deck:
                functions = global_config.deck_snapshot.get(instrument, {})
            elif pseudo_deck:
                functions = pseudo_deck.get(instrument, {})
            forms = create_form_from_pseudo(pseudo=functions, autofill=autofill, script=script)
        
        if request.method == 'POST' and "hidden_name" in request.form:
            method_name = request.form.get("hidden_name", None)
            form = forms.get(method_name) if forms else None
            insert_position = request.form.get("drop_target_id", None)
            
            if form:
                kwargs = {field.name: field.data for field in form if field.name != 'csrf_token'}
                if form.validate_on_submit():
                    function_name = kwargs.pop("hidden_name")
                    save_data = kwargs.pop('return', '')

                    primitive_arg_types = utils.get_arg_type(kwargs, functions[function_name])

                    script.eval_list(kwargs, primitive_arg_types)
                    kwargs = script.validate_variables(kwargs)
                    action = {"instrument": instrument, "action": function_name,
                              "args": kwargs,
                              "return": save_data,
                              'arg_types': primitive_arg_types}
                    script.add_action(action=action, insert_position=insert_position)
                else:
                    flash(form.errors)

        elif request.method == 'POST' and "builtin_name" in request.form:
            function_name = request.form.get("builtin_name")
            form = forms.get(function_name) if forms else None
            insert_position = request.form.get("drop_target_id", None)

            if form:
                kwargs = {field.name: field.data for field in form if field.name != 'csrf_token'}
                if form.validate_on_submit():
                    logic_type = kwargs.pop('builtin_name')
                    if 'variable' in kwargs:
                        try:
                            script.add_variable(insert_position=insert_position, **kwargs)
                        except ValueError:
                            flash("Invalid variable type")
                    else:
                        script.add_logic_action(logic_type=logic_type, insert_position=insert_position, **kwargs)
                else:
                    flash(form.errors)
                    
        elif request.method == 'POST' and "workflow_name" in request.form:
            workflow_name = request.form.get("workflow_name")
            form = forms.get(workflow_name) if forms else None
            insert_position = request.form.get("drop_target_id", None)

            if form:
                kwargs = {field.name: field.data for field in form if field.name != 'csrf_token'}
                if form.validate_on_submit():
                    save_data = kwargs.pop('return', '')

                    primitive_arg_types = utils.get_arg_type(kwargs, functions[workflow_name])

                    script.eval_list(kwargs, primitive_arg_types)
                    kwargs = script.validate_variables(kwargs)
                    action = {"instrument": instrument, "action": workflow_name,
                              "args": kwargs,
                              "return": save_data,
                              'arg_types': primitive_arg_types}
                    script.add_action(action=action, insert_position=insert_position)
                    script.add_workflow(**kwargs, insert_position=insert_position)
                else:
                    flash(form.errors)

        # toggle autofill, autofill doesn't apply to control flow ops
        elif request.method == 'POST' and "autofill" in request.form:
            autofill = not autofill
            session['autofill'] = autofill
            if not instrument == 'flow_control':
                forms = create_form_from_pseudo(functions, autofill=autofill, script=script)

    utils.post_script_file(script)

    exec_string = script.python_script if script.python_script else script.compile(current_app.config['SCRIPT_FOLDER'])
    session['python_code'] = exec_string

    design_buttons = create_action_button(script)
    return render_template('experiment_builder.html', off_line=off_line, instrument=instrument, history=deck_list,
                           script=script, defined_variables=deck_variables,
                           local_variables=global_config.defined_variables,
                           forms=forms, buttons=design_buttons, format_name=format_name,
                           use_llm=enable_llm)


@design.route("/design/generate_code", methods=['POST'])
@login_required
def generate_code():
    """
    .. :quickref: Text to Code; Generate code from user input and update the design canvas.

    .. http:post:: /design/generate_code

    :form prompt: user's prompt
    :status 200: and then redirects to :http:get:`/experiment/build`
    :status 400: failed to initialize the AI agent redirects to :http:get:`/design/script`

    """
    agent = global_config.agent
    enable_llm = current_app.config["ENABLE_LLM"]
    instrument = request.form.get("instrument")

    if request.method == 'POST' and "clear" in request.form:
        session['prompt'][instrument] = ''
    if request.method == 'POST' and "gen" in request.form:
        prompt = request.form.get("prompt")
        session['prompt'][instrument] = prompt
        sdl_module = global_config.deck_snapshot.get(instrument, {})
        empty_script = Script(author=session.get('user'))
        if enable_llm and agent is None:
            try:
                model = current_app.config["LLM_MODEL"]
                server = current_app.config["LLM_SERVER"]
                module = current_app.config["MODULE"]
                from ivoryos.utils.llm_agent import LlmAgent
                agent = LlmAgent(host=server, model=model, output_path=os.path.dirname(os.path.abspath(module)))
            except Exception as e:
                flash(e.__str__())
                return redirect(url_for("design.experiment_builder", instrument=instrument, use_llm=True)), 400
        action_list = agent.generate_code(sdl_module, prompt)
        for action in action_list:
            action['instrument'] = instrument
            action['return'] = ''
            if "args" not in action:
                action['args'] = {}
            if "arg_types" not in action:
                action['arg_types'] = {}
            empty_script.add_action(action)
        utils.post_script_file(empty_script)
    return redirect(url_for("design.experiment_builder", instrument=instrument, use_llm=True))


@design.route("/design/campaign", methods=['GET', 'POST'])
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

    existing_data = None
    # script.sort_actions() # handled in update list
    off_line = current_app.config["OFF_LINE"]
    deck_list = utils.import_history(os.path.join(current_app.config["OUTPUT_FOLDER"], 'deck_history.txt'))
    
    design_buttons = {stype: create_action_button(script, stype) for stype in script.stypes}
    config_preview = []
    config_file_list = [i for i in os.listdir(current_app.config["CSV_FOLDER"]) if not i == ".gitkeep"]
    
    try:
        exec_string = script.python_script if script.python_script else script.compile(current_app.config['SCRIPT_FOLDER'])
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


@design.route("/design/script/toggle/<stype>")
@login_required
def toggle_script_type(stype=None):
    """
    .. :quickref: Workflow Design; toggle the experimental phase for design canvas.

    .. http:get:: /design/script/toggle/<stype>

    :status 200: and then redirects to :http:get:`/design/script`

    """
    script = utils.get_script_file()
    script.editing_type = stype
    utils.post_script_file(script)
    return redirect(url_for('design.experiment_builder'))


@design.route("/updateList", methods=['POST'])
@login_required
def update_list():
    order = request.form['order']
    script = utils.get_script_file()
    script.currently_editing_order = order.split(",", len(script.currently_editing_script))
    script.sort_actions()
    exec_string = script.compile(current_app.config['SCRIPT_FOLDER'])
    utils.post_script_file(script)
    session['python_code'] = exec_string

    return jsonify({'success': True})


@design.route("/toggle_show_code", methods=["POST"])
def toggle_show_code():
    session["show_code"] = not session.get("show_code", False)
    return redirect(request.referrer or url_for("design.experiment_builder"))


# --------------------handle all the import/export and download/upload--------------------------
@design.route("/design/clear")
@login_required
def clear():
    """
    .. :quickref: Workflow Design; clear the design canvas.

    .. http:get:: /design/clear

    :form prompt: user's prompt
    :status 200: clear canvas and then redirects to :http:get:`/design/script`
    """
    deck = global_config.deck
    pseudo_name = session.get("pseudo_deck", "")
    if deck:
        deck_name = os.path.splitext(os.path.basename(deck.__file__))[
            0] if deck.__name__ == "__main__" else deck.__name__
    elif pseudo_name:
        deck_name = pseudo_name
    else:
        deck_name = ''
    script = Script(deck=deck_name, author=session.get('username'))
    utils.post_script_file(script)
    return redirect(url_for("design.experiment_builder"))


@design.route("/design/import/pseudo", methods=['POST'])
@login_required
def import_pseudo():
    """
    .. :quickref: Workflow Design; Import pseudo deck from deck history

    .. http:post:: /design/import/pseudo

    :form pkl_name: pseudo deck name
    :status 302: load pseudo deck and then redirects to :http:get:`/design/script`
    """
    pkl_name = request.form.get('pkl_name')
    script = utils.get_script_file()
    session['pseudo_deck'] = pkl_name

    if script.deck is None or script.isEmpty():
        script.deck = pkl_name.split('.')[0]
        utils.post_script_file(script)
    elif script.deck and not script.deck == pkl_name.split('.')[0]:
        flash(f"Choose the deck with name {script.deck}")
    return redirect(url_for("design.experiment_builder"))






