import csv
import json
import os
import pickle
import sys

from flask import Blueprint, redirect, url_for, flash, jsonify, send_file, request, render_template, session, \
    current_app, g
from flask_login import login_required
from flask_socketio import SocketIO
from werkzeug.utils import secure_filename

from ivoryos.utils import utils
from ivoryos.utils.global_config import GlobalConfig
from ivoryos.utils.form import create_builtin_form, create_action_button, format_name, create_form_from_pseudo, \
    create_form_from_action, create_all_builtin_forms
from ivoryos.utils.db_models import Script
from ivoryos.utils.script_runner import ScriptRunner
# from ivoryos.utils.utils import load_workflows

socketio = SocketIO()
design = Blueprint('design', __name__, template_folder='templates/design')

global_config = GlobalConfig()
runner = ScriptRunner()


@socketio.on('abort_pending')
def handle_abort_pending():
    runner.abort_pending()
    socketio.emit('log', {'message': "aborted pending iterations"})


@socketio.on('abort_current')
def handle_abort_current():
    runner.stop_execution()
    socketio.emit('log', {'message': "stopped next task"})


@socketio.on('pause')
def handle_pause():
    msg = runner.toggle_pause()
    socketio.emit('log', {'message': msg})


@socketio.on('connect')
def handle_abort_action():
    # Fetch log messages from local file
    filename = os.path.join(current_app.config["OUTPUT_FOLDER"], current_app.config["LOGGERS_PATH"])
    with open(filename, 'r') as log_file:
        log_history = log_file.readlines()
    for message in log_history[-10:]:
        socketio.emit('log', {'message': message})


@design.route("/experiment/build/", methods=['GET', 'POST'])
@design.route("/experiment/build/<instrument>/", methods=['GET', 'POST'])
@login_required
def experiment_builder(instrument=None):
    """
    .. :quickref: Workflow Design; Build experiment workflow

    **Experiment Builder**

    This route allows users to build and edit experiment workflows. Users can interact with available instruments,
    define variables, and manage experiment scripts.

    .. http:get:: /experiment/build

    Load the experiment builder interface.

    :param instrument: The specific instrument for which to load functions and forms.
    :type instrument: str
    :status 200: Experiment builder loaded successfully.

    .. http:post:: /experiment/build

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
    # load_workflows(script)
    # registered_workflows = global_config.registered_workflows

    if deck and script.deck is None:
        script.deck = os.path.splitext(os.path.basename(deck.__file__))[
            0] if deck.__name__ == "__main__" else deck.__name__
    script.sort_actions()

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
        # deck_variables.insert(0, "registered_workflows")
        deck_variables.insert(0, "flow_control")

    else:
        deck_variables = list(pseudo_deck.keys()) if pseudo_deck else []
        deck_variables.remove("deck_name") if len(deck_variables) > 0 else deck_variables
    edit_action_info = session.get("edit_action")
    if edit_action_info:
        forms = create_form_from_action(edit_action_info, script=script)
    elif instrument:
        # if instrument in ['if', 'while', 'variable', 'wait', 'repeat']:
        #     forms = create_builtin_form(instrument, script=script)
        if instrument == 'flow_control':
            forms = create_all_builtin_forms(script=script)
        # elif instrument == 'registered_workflows':
        #     functions = utils._inspect_class(registered_workflows)
        #     # forms = create_workflow_forms(script=script)
        #     forms = create_form_from_pseudo(pseudo=functions, autofill=autofill, script=script)
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
            # all_kwargs = request.form.copy()
            method_name = request.form.get("hidden_name", None)
            # if method_name is not None:
            form = forms.get(method_name)
            insert_position = request.form.get("drop_target_id", None)
            kwargs = {field.name: field.data for field in form if field.name != 'csrf_token'}
            if form and form.validate_on_submit():
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
            form = forms.get(function_name)
            kwargs = {field.name: field.data for field in form if field.name != 'csrf_token'}
            insert_position = request.form.get("drop_target_id", None)

            if form.validate_on_submit():
                # print(kwargs)
                logic_type = kwargs.pop('builtin_name')
                if 'variable' in kwargs:
                    try:
                        script.add_variable(**kwargs, insert_position=insert_position)
                    except ValueError:
                        flash("Invalid variable type")
                else:
                    script.add_logic_action(logic_type=logic_type, **kwargs, insert_position=insert_position)
            else:
                flash(form.errors)
        elif request.method == 'POST' and "workflow_name" in request.form:
            workflow_name = request.form.get("workflow_name")
            form = forms.get(workflow_name)
            kwargs = {field.name: field.data for field in form if field.name != 'csrf_token'}
            insert_position = request.form.get("drop_target_id", None)

            if form.validate_on_submit():
                # workflow_name = kwargs.pop('workflow_name')
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
    design_buttons = create_action_button(script)
    return render_template('experiment_builder.html', off_line=off_line, instrument=instrument, history=deck_list,
                           script=script, defined_variables=deck_variables,
                           local_variables=global_config.defined_variables,
                           forms=forms, buttons=design_buttons, format_name=format_name,
                           use_llm=enable_llm)


@design.route("/generate_code", methods=['POST'])
@login_required
def generate_code():
    """
    .. :quickref: Text to Code; Generate code from user input and update the design canvas.

    .. http:post:: /generate_code

    :form prompt: user's prompt
    :status 200: and then redirects to :http:get:`/experiment/build`
    :status 400: failed to initialize the AI agent redirects to :http:get:`/experiment/build`

    """
    agent = global_config.agent
    enable_llm = current_app.config["ENABLE_LLM"]
    instrument = request.form.get("instrument")

    if request.method == 'POST' and "clear" in request.form:
        session['prompt'][instrument] = ''
    if request.method == 'POST' and "gen" in request.form:
        prompt = request.form.get("prompt")
        session['prompt'][instrument] = prompt
        # sdl_module = utils.parse_functions(find_instrument_by_name(f'deck.{instrument}'), doc_string=True)
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


@design.route("/experiment", methods=['GET', 'POST'])
@login_required
def experiment_run():
    """
    .. :quickref: Workflow Execution; Execute/iterate the workflow

    .. http:get:: /experiment

    Compile the workflow and load the experiment execution interface.

    .. http:post:: /experiment

    Start workflow execution

    """
    deck = global_config.deck
    script = utils.get_script_file()
    script.sort_actions()
    off_line = current_app.config["OFF_LINE"]
    deck_list = utils.import_history(os.path.join(current_app.config["OUTPUT_FOLDER"], 'deck_history.txt'))
    # if not off_line and deck is None:
    #     # print("loading deck")
    #     module = current_app.config.get('MODULE', '')
    #     deck = sys.modules[module] if module else None
    #     script.deck = os.path.splitext(os.path.basename(deck.__file__))[0]
    design_buttons = {stype: create_action_button(script, stype) for stype in script.stypes}
    config_preview = []
    config_file_list = [i for i in os.listdir(current_app.config["CSV_FOLDER"]) if not i == ".gitkeep"]
    try:
        exec_string = script.compile(current_app.config['SCRIPT_FOLDER'])
    except ValueError as e:
        flash(e.__str__())
        return redirect(url_for("design.experiment_builder"))
    # print(exec_string)
    config_file = request.args.get("filename")
    config = []
    if config_file:
        session['config_file'] = config_file
    filename = session.get("config_file")
    if filename:
        # config_preview = list(csv.DictReader(open(os.path.join(current_app.config['CSV_FOLDER'], filename))))
        config = list(csv.DictReader(open(os.path.join(current_app.config['CSV_FOLDER'], filename))))
        config_preview = config[1:6]
        arg_type = config.pop(0)  # first entry is types
    try:
        for key, func_str in exec_string.items():
            exec(func_str)
        line_collection = script.convert_to_lines(exec_string)
    except Exception:
        flash(f"Please check {key} syntax!!")
        return redirect(url_for("design.experiment_builder"))
    # runner.globals_dict.update(globals())
    run_name = script.name if script.name else "untitled"

    dismiss = session.get("dismiss", None)
    script = utils.get_script_file()
    no_deck_warning = False

    _, return_list = script.config_return()
    config_list, config_type_list = script.config("script")
    # config = script.config("script")
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
        if "bo" in request.form:
            bo_args = request.form.to_dict()
            # ax_client = utils.ax_initiation(bo_args)
        if "online-config" in request.form:
            config = utils.web_config_entry_wrapper(request.form.to_dict(), config_list)
        repeat = request.form.get('repeat', None)

        try:
            datapath = current_app.config["DATA_FOLDER"]
            run_name = script.validate_function_name(run_name)
            runner.run_script(script=script, run_name=run_name, config=config, bo_args=bo_args,
                              logger=g.logger, socketio=g.socketio, repeat_count=repeat,
                              output_path=datapath
                              )
            if utils.check_config_duplicate(config):
                flash(f"WARNING: Duplicate in config entries.")
        except Exception as e:
            flash(e)
    return render_template('experiment_run.html', script=script.script_dict, filename=filename,
                           dot_py=exec_string, line_collection=line_collection,
                           return_list=return_list, config_list=config_list, config_file_list=config_file_list,
                           config_preview=config_preview, data_list=data_list, config_type_list=config_type_list,
                           no_deck_warning=no_deck_warning, dismiss=dismiss, design_buttons=design_buttons,
                           history=deck_list, pause_status=runner.pause_status())


@design.route("/toggle_script_type/<stype>")
@login_required
def toggle_script_type(stype=None):
    """
    .. :quickref: Workflow Design; toggle the experimental phase for design canvas.

    .. http:get:: /toggle_script_type

    :status 200: and then redirects to :http:get:`/experiment/build`

    """
    script = utils.get_script_file()
    script.editing_type = stype
    utils.post_script_file(script)
    return redirect(url_for('design.experiment_builder'))


@design.route("/updateList", methods=['GET', 'POST'])
@login_required
def update_list():
    order = request.form['order']
    script = utils.get_script_file()
    script.currently_editing_order = order.split(",", len(script.currently_editing_script))
    utils.post_script_file(script)
    return jsonify('Successfully Updated')


# --------------------handle all the import/export and download/upload--------------------------
@design.route("/clear")
@login_required
def clear():
    """
    .. :quickref: Workflow Design; clear the design canvas.

    .. http:get:: /clear

    :form prompt: user's prompt
    :status 200: clear canvas and then redirects to :http:get:`/experiment/build`
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


@design.route("/import_pseudo", methods=['POST'])
@login_required
def import_pseudo():
    """
    .. :quickref: Workflow Design; Import pseudo deck from deck history

    .. http:post:: /import_pseudo

    :form pkl_name: pseudo deck name
    :status 302: load pseudo deck and then redirects to :http:get:`/experiment/build`
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


@design.route('/uploads', methods=['POST'])
@login_required
def upload():
    """
    .. :quickref: Workflow Execution; upload a workflow config file (.CSV)

    .. http:post:: /uploads

    :form file: workflow CSV config file
    :status 302: save csv file and then redirects to :http:get:`/experiment`
    """
    if request.method == "POST":
        f = request.files['file']
        if 'file' not in request.files:
            flash('No file part')
        if f.filename.split('.')[-1] == "csv":
            filename = secure_filename(f.filename)
            f.save(os.path.join(current_app.config['CSV_FOLDER'], filename))
            session['config_file'] = filename
            return redirect(url_for("design.experiment_run"))
        else:
            flash("Config file is in csv format")
            return redirect(url_for("design.experiment_run"))


@design.route('/download_results/<filename>')
@login_required
def download_results(filename):
    filepath = os.path.join(current_app.config["DATA_FOLDER"], filename)
    return send_file(os.path.abspath(filepath), as_attachment=True)


@design.route('/load_json', methods=['POST'])
@login_required
def load_json():
    """
    .. :quickref: Workflow Design Ext; upload a workflow design file (.JSON)

    .. http:post:: /load_json

    :form file: workflow design JSON file
    :status 302: load pseudo deck and then redirects to :http:get:`/experiment/build`
    """
    if request.method == "POST":
        f = request.files['file']
        if 'file' not in request.files:
            flash('No file part')
        if f.filename.endswith("json"):
            script_dict = json.load(f)
            utils.post_script_file(script_dict, is_dict=True)
        else:
            flash("Script file need to be JSON file")
    return redirect(url_for("design.experiment_builder"))


@design.route('/download/<filetype>')
@login_required
def download(filetype):
    script = utils.get_script_file()
    run_name = script.name if script.name else "untitled"
    if filetype == "configure":
        filepath = os.path.join(current_app.config['SCRIPT_FOLDER'], f"{run_name}_config.csv")
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            cfg, cfg_types = script.config("script")
            writer.writerow(cfg)
            writer.writerow(list(cfg_types.values()))
    elif filetype == "script":
        script.sort_actions()
        json_object = json.dumps(script.as_dict())
        filepath = os.path.join(current_app.config['SCRIPT_FOLDER'], f"{run_name}.json")
        with open(filepath, "w") as outfile:
            outfile.write(json_object)
    elif filetype == "python":
        filepath = os.path.join(current_app.config["SCRIPT_FOLDER"], f"{run_name}.py")

    return send_file(os.path.abspath(filepath), as_attachment=True)


@design.route("/edit/<uuid>", methods=['GET', 'POST'])
@login_required
def edit_action(uuid: str):
    """
    .. :quickref: Workflow Design; edit parameters of an action step on canvas

    .. http:get:: /edit

    Load parameter form of an action step

    .. http:post:: /edit

    :param uuid: The step's uuid
    :type uuid: str

    :form dynamic form: workflow step dynamic inputs
    :status 302: save changes and then redirects to :http:get:`/experiment/build`
    """
    script = utils.get_script_file()
    action = script.find_by_uuid(uuid)
    session['edit_action'] = action

    if request.method == "POST" and action is not None:
        forms = create_form_from_action(action, script=script)
        if "back" not in request.form:
            kwargs = {field.name: field.data for field in forms if field.name != 'csrf_token'}
            # print(kwargs)
            if forms and forms.validate_on_submit():
                save_as = kwargs.pop('return', '')
                kwargs = script.validate_variables(kwargs)
            # try:
                script.update_by_uuid(uuid=uuid, args=kwargs, output=save_as)
            # except Exception as e:
            else:
                flash(forms.errors)
        session.pop('edit_action')
    return redirect(url_for('design.experiment_builder'))


@design.route("/delete/<id>")
@login_required
def delete_action(id: int):
    """
    .. :quickref: Workflow Design; delete an action step on canvas

    .. http:get:: /delete

    :param id: The step number id
    :type id: int

    :status 302: save changes and then redirects to :http:get:`/experiment/build`
    """
    back = request.referrer
    script = utils.get_script_file()
    script.delete_action(id)
    utils.post_script_file(script)
    return redirect(back)


@design.route("/duplicate/<id>")
@login_required
def duplicate_action(id: int):
    """
    .. :quickref: Workflow Design; duplicate an action step on canvas

    .. http:get:: /duplicate

    :param id: The step number id
    :type id: int

    :status 302: save changes and then redirects to :http:get:`/experiment/build`
    """
    back = request.referrer
    script = utils.get_script_file()
    script.duplicate_action(id)
    utils.post_script_file(script)
    return redirect(back)
