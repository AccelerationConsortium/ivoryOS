import os
import inspect

from flask import Blueprint, redirect, url_for, flash, jsonify, request, render_template, session, current_app
from flask_login import login_required, current_user

from ivoryos.routes.library.library import publish
from ivoryos.utils import utils
from ivoryos.utils.global_config import GlobalConfig
from ivoryos.utils.form import create_action_button, create_form_from_pseudo, create_all_builtin_forms, create_workflow_forms
from ivoryos.utils.db_models import Script
from ivoryos.utils.py_to_json import convert_to_cards

# Import the new modular components
from ivoryos.routes.design.design_file import files
from ivoryos.routes.design.design_step import steps


design = Blueprint('design', __name__, template_folder='templates')

# Register sub-blueprints
design.register_blueprint(files)
design.register_blueprint(steps)

global_config = GlobalConfig()

# ---- Main Design Routes ----


def _create_forms(instrument, script, autofill, pseudo_deck = None):
    deck = global_config.deck
    functions = {}
    if instrument == 'flow_control':
        forms = create_all_builtin_forms(script=script)
    elif instrument in global_config.defined_variables.keys():
        _object = global_config.defined_variables.get(instrument)
        functions = utils._inspect_class(_object)
        forms = create_form_from_pseudo(pseudo=functions, autofill=autofill, script=script)
    elif instrument.startswith("blocks"):
        forms = create_form_from_pseudo(pseudo=global_config.building_blocks[instrument], autofill=autofill, script=script)
        functions = global_config.building_blocks[instrument]
    else:
        if deck:
            functions = global_config.deck_snapshot.get(instrument, {})
        elif pseudo_deck:
            functions = pseudo_deck.get(instrument, {})
        forms = create_form_from_pseudo(pseudo=functions, autofill=autofill, script=script)
    return functions, forms

@design.route("/draft")
@login_required
def experiment_builder():
    """
    .. :quickref: Workflow Design; Build experiment workflow

    **Experiment Builder**

    .. http:get:: /draft

    Load the experiment builder page where users can design their workflow by adding actions, instruments, and logic.

    :status 200: Experiment builder loaded successfully.

    """
    deck = global_config.deck
    script = utils.get_script_file()

    if deck and script.deck is None:
        script.deck = os.path.splitext(os.path.basename(deck.__file__))[
            0] if deck.__name__ == "__main__" else deck.__name__
        utils.post_script_file(script)
    pseudo_deck_name = session.get('pseudo_deck', '')
    pseudo_deck_path = os.path.join(current_app.config["DUMMY_DECK"], pseudo_deck_name)
    off_line = current_app.config["OFF_LINE"]

    pseudo_deck = utils.load_deck(pseudo_deck_path) if off_line and pseudo_deck_name else None
    if off_line and pseudo_deck is None:
        flash("Choose available deck below.")

    deck_list = utils.available_pseudo_deck(current_app.config["DUMMY_DECK"])

    if deck:
        deck_variables = list(global_config.deck_snapshot.keys())
        # deck_variables.insert(0, "flow_control")
    else:
        deck_variables = list(pseudo_deck.keys()) if pseudo_deck else []
        deck_variables.remove("deck_name") if len(deck_variables) > 0 else deck_variables

    # edit_action_info = session.get("edit_action")

    try:
        snapshot = global_config.deck_snapshot if deck else pseudo_deck
        exec_string = script.python_script if script.python_script else script.compile(current_app.config['SCRIPT_FOLDER'], snapshot=snapshot)
    except Exception as e:
        exec_string = {}
        flash(f"Error in Python script: {e}")
    session['python_code'] = exec_string

    design_buttons = {stype: create_action_button(script, stype) for stype in script.stypes}

    return render_template('experiment_builder.html', off_line=off_line, history=deck_list,
                           script=script, defined_variables=deck_variables, buttons_dict=design_buttons,
                           local_variables=global_config.defined_variables, block_variables=global_config.building_blocks)

@design.route("/draft/code_preview", methods=["GET"])
@login_required
def compile_preview():
    # Get mode and batch from query parameters
    script = utils.get_script_file()
    mode = request.args.get("mode", "single")   # default to "single"
    batch = request.args.get("batch", "sample") # default to "sample"

    pseudo_deck_name = session.get('pseudo_deck', '')
    pseudo_deck_path = os.path.join(current_app.config["DUMMY_DECK"], pseudo_deck_name)
    off_line = current_app.config["OFF_LINE"]
    pseudo_deck = utils.load_deck(pseudo_deck_path) if off_line and pseudo_deck_name else None
    snapshot = global_config.deck_snapshot if not off_line and global_config.deck else pseudo_deck

    try:
        # Example: decide which code to return based on mode/batch
        if mode == "single":
            code = script.compile(current_app.config['SCRIPT_FOLDER'], snapshot=snapshot)
        elif mode == "batch":
            code = script.compile(current_app.config['SCRIPT_FOLDER'], batch=True, mode=batch, snapshot=snapshot)
        else:
            code = "Invalid mode. Please select 'single' or 'batch'."
    except Exception as e:
        code = f"Error compiling: {e}"
    # print(code)
    return jsonify(code=code)


@design.route("/draft/meta", methods=["PATCH"])
@login_required
def update_script_meta():
    """
    .. :quickref: Workflow Design; update the script metadata.

    .. http:patch:: /draft/meta

    Update the script metadata, including the script name and status. If the script name is provided,
    it saves the script with that name. If the status is "finished", it finalizes the script.

    :form name: The name to save the script as.
    :form status: The status of the script (e.g., "finished").

    :status 200: Successfully updated the script metadata.
    """
    data = request.get_json()
    script = utils.get_script_file()
    if 'name' in data:
        run_name = data.get("name")
        exist_script = Script.query.get(run_name)
        if exist_script is None:
            script.save_as(run_name)
            utils.post_script_file(script)
            return jsonify(success=True)
        else:
            flash("Script name is already exist in database")
            return jsonify(success=False)

    if 'status' in data:
        if data['status'] == "finalized":
            script.finalize()
            utils.post_script_file(script)
            publish()
            return jsonify(success=True)
    return jsonify(success=False)


@design.route("/draft/ui-state", methods=["PATCH"])
@login_required
def update_ui_state():
    """
    .. :quickref: Workflow Design; update the UI state for the design canvas.

    .. http:patch:: /draft/ui-state

    Update the UI state for the design canvas, including showing code overlays, setting editing types,
    and handling deck selection.

    :form show_code: Whether to show the code overlay (true/false).
    :form editing_type: The type of editing to set (prep, script, cleanup).
    :form autofill: Whether to enable autofill for the instrument panel (true/false).
    :form deck_name: The name of the deck to select.

    :status 200: Updates the UI state and returns a success message.
    """
    data = request.get_json()

    if "show_code" in data:
        session["show_code"] = bool(data["show_code"])
        return jsonify({"success": True})
    if "editing_type" in data:
        stype = data.get("editing_type")

        script = utils.get_script_file()
        script.editing_type = stype
        utils.post_script_file(script)

        # Re-render only the part of the page you want to update
        design_buttons = {stype: create_action_button(script, stype) for stype in script.stypes}
        rendered_html = render_template("components/canvas.html", script=script, buttons_dict=design_buttons)
        return jsonify({"html": rendered_html})

    if "autofill" in data:
        script = utils.get_script_file()
        instrument = data.get("instrument", '')
        autofill = data.get("autofill", False)
        session['autofill'] = autofill
        _, forms = _create_forms(instrument, script, autofill)
        rendered_html = render_template("components/actions_panel.html", forms=forms, script=script, instrument=instrument)
        return jsonify({"html": rendered_html})

    if "deck_name" in data:
        pkl_name = data.get('deck_name', "")
        script = utils.get_script_file()
        session['pseudo_deck'] = pkl_name
        deck_list = utils.available_pseudo_deck(current_app.config["DUMMY_DECK"])

        if script.deck is None or script.isEmpty():
            script.deck = pkl_name.split('.')[0]
            utils.post_script_file(script)
        elif script.deck and not script.deck == pkl_name.split('.')[0]:
            flash(f"Choose the deck with name {script.deck}")
        pseudo_deck_path = os.path.join(current_app.config["DUMMY_DECK"], pkl_name)
        pseudo_deck = utils.load_deck(pseudo_deck_path)
        deck_variables = list(pseudo_deck.keys()) if pseudo_deck else []
        deck_variables.remove("deck_name") if len(deck_variables) > 0 else deck_variables
        html = render_template("components/sidebar.html", history=deck_list,
                               defined_variables=deck_variables, local_variables = global_config.defined_variables,
                               block_variables=global_config.building_blocks)
        return jsonify({"html": html})
    return jsonify({"error": "Invalid request"}), 400


# @design.route("/draft/steps/order", methods=['POST'])
# @login_required
# def update_list():
#     """
#     .. :quickref: Workflow Design Steps; update the order of steps in the design canvas when reordering steps.
#
#     .. http:post:: /draft/steps/order
#
#     Update the order of steps in the design canvas when reordering steps.
#
#     :form order: A comma-separated string representing the new order of steps.
#     :status 200: Successfully updated the order of steps.
#     """
#     order = request.form['order']
#     script = utils.get_script_file()
#     script.currently_editing_order = order.split(",", len(script.currently_editing_script))
#     script.sort_actions()
#     exec_string = script.compile(current_app.config['SCRIPT_FOLDER'])
#     utils.post_script_file(script)
#     session['python_code'] = exec_string
#
#     return jsonify({'success': True})



@design.route("/draft", methods=['DELETE'])
@login_required
def clear_draft():
    """
    .. :quickref: Workflow Design; clear the design canvas.

    .. http:delete:: /draft

    :status 200: clear canvas
    """
    deck = global_config.deck
    if deck:
        deck_name = os.path.splitext(os.path.basename(deck.__file__))[
            0] if deck.__name__ == "__main__" else deck.__name__
    else:
        deck_name = session.get("pseudo_deck", "")
    script = Script(deck=deck_name, author=current_user.get_id())
    utils.post_script_file(script)
    exec_string = script.compile(current_app.config['SCRIPT_FOLDER'])
    session['python_code'] = exec_string
    return jsonify({'success': True})





@design.route("/draft/submit_python", methods=["POST"])
def submit_script():
    """
    .. :quickref: Workflow Design; convert Python to workflow script

    .. http:post:: /draft/submit_python

    Convert a Python script to a workflow script and save it in the database.

    :form workflow_name: workflow name
    :form script: main script
    :form prep: prep script
    :form cleanup: post script
    :status 200: clear canvas
    """
    deck = global_config.deck
    deck_name = os.path.splitext(os.path.basename(deck.__file__))[0] if deck.__name__ == "__main__" else deck.__name__
    script = Script(author=current_user.get_id(), deck=deck_name)
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
            result[stype] = f"failed to transcript, but function can still run. error: {str(e)}"
    utils.post_script_file(script)
    status = publish()
    return jsonify({"script": result, "db": status}), 200



@design.post("/draft/instruments/<string:instrument>")
@login_required
def methods_handler(instrument: str = ''):
    """
    .. :quickref: Workflow Design; handle methods of a specific instrument

    .. http:post:: /draft/instruments/<string:instrument>

    Add methods for a specific instrument in the workflow design.

    :param instrument: The name of the instrument to handle methods for.
    :type instrument: str
    :status 200: Render the methods for the specified instrument.
    """
    script = utils.get_script_file()
    pseudo_deck_name = session.get('pseudo_deck', '')
    pseudo_deck_path = os.path.join(current_app.config["DUMMY_DECK"], pseudo_deck_name)
    off_line = current_app.config["OFF_LINE"]
    pseudo_deck = utils.load_deck(pseudo_deck_path) if off_line and pseudo_deck_name else None
    autofill = session.get('autofill', False)

    if instrument == 'workflows':
        functions, forms = create_workflow_forms(script, autofill=autofill, design=True)
    else:
        functions, forms = _create_forms(instrument, script, autofill, pseudo_deck)

    success = True
    msg = ""
    request.form
    if "hidden_name" in request.form:
        deck_snapshot = global_config.deck_snapshot
        block_snapshot = global_config.building_blocks
        method_name = request.form.get("hidden_name", None)
        form = forms.get(method_name) if forms else None
        insert_position = request.form.get("drop_target_id", None)

        if form:
            kwargs = {field.name: field.data for field in form if field.name != 'csrf_token'}
            # print(kwargs)
            if form.validate_on_submit():
                function_name = kwargs.pop("hidden_name")
                batch_action = kwargs.pop("batch_action", False)
                save_data = kwargs.pop('return', '')

                # validate return variable name
                save_data = script.validate_function_name(save_data)

                function_data = functions.get(function_name)
                # Handle virtual property setters
                if not function_data and function_name.endswith("_(setter)"):
                    prop_name = function_name[:-9]
                    prop_data = functions.get(prop_name)
                    if prop_data and prop_data.get('is_property'):
                        # Synthesize setter signature: (value: type)
                        sig = prop_data.get('signature')
                        param_type = inspect._empty
                        if sig and sig.return_annotation is not inspect._empty:
                            param_type = sig.return_annotation
                        
                        setter_sig = inspect.Signature(
                            parameters=[inspect.Parameter('value', inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=param_type)],
                            return_annotation=None
                        )
                        # Inherit coroutine status from property (usually False)
                        is_coroutine = prop_data.get('coroutine', False)
                        function_data = {'signature': setter_sig, 'coroutine': is_coroutine}

                if not function_data:
                    # Fallback or error handling
                    function_data = {}

                primitive_arg_types = utils.get_arg_type(kwargs, function_data)

                script.eval_list(kwargs, primitive_arg_types)
                kwargs = script.validate_variables(kwargs, primitive_arg_types)
                
                # Use function_data to get coroutine status, avoiding KeyError for virtual setters
                coroutine = function_data.get("coroutine", False)

                # print(kwargs)
                action = {"instrument": instrument, "action": function_name,
                          "args": kwargs,
                          "return": save_data,
                          'arg_types': primitive_arg_types,
                          "coroutine": coroutine,
                          "batch_action": batch_action,
                          }
                script.add_action(action=action, insert_position=insert_position)
            else:
                msg = [f"{field}: {', '.join(messages)}" for field, messages in form.errors.items()]
                success = False
    elif "builtin_name" in request.form:
        function_name = request.form.get("builtin_name")
        form = forms.get(function_name) if forms else None
        insert_position = request.form.get("drop_target_id", None)
        if form:
            kwargs = {field.name: field.data for field in form if field.name != 'csrf_token'}
            if form.validate_on_submit():
                logic_type = kwargs.pop('builtin_name')
                if logic_type == 'input':
                    script.add_input_action(insert_position=insert_position, **kwargs)
                elif logic_type == 'variable':
                    try:
                        script.add_variable(insert_position=insert_position, **kwargs)
                    except ValueError as e:
                        success = False
                        msg = e.__str__()
                elif logic_type == 'math_variable':
                    try:
                        script.add_math_variable(insert_position=insert_position, **kwargs)
                    except ValueError as e:
                        success = False
                        msg = e.__str__()
                else:
                    script.add_logic_action(logic_type=logic_type, insert_position=insert_position, **kwargs)
            else:
                success = False
                msg = [f"{field}: {', '.join(messages)}" for field, messages in form.errors.items()]
    elif "workflow_name" in request.form:
        workflow_name = request.form.get("workflow_name")
        form = forms.get(workflow_name) if forms else None
        insert_position = request.form.get("drop_target_id", None)
        if form:
            kwargs = {field.name: field.data for field in form if field.name != 'csrf_token'}
            if form.validate_on_submit():
                save_data = kwargs.pop('return', '')
                kwargs.pop('workflow_name')
                # validate return variable name
                save_data = script.validate_function_name(save_data)

                primitive_arg_types = utils.get_arg_type(kwargs, functions[workflow_name])
                script.eval_list(kwargs, primitive_arg_types)
                kwargs = script.validate_variables(kwargs, primitive_arg_types)
                
                # Fetch the workflow to embed its steps
                target_workflow = Script.query.filter_by(name=workflow_name).first()
                embedded_steps = []
                if target_workflow:
                    embedded_steps = target_workflow.script_dict.get('script', [])

                action = {"instrument": instrument, "action": workflow_name,
                          "args": kwargs,
                          "return": save_data,
                          'arg_types': primitive_arg_types,
                          "workflow": embedded_steps} # Embed steps
                # print(action)
                script.add_action(action=action, insert_position=insert_position)
            else:
                success = False
                msg = [f"{field}: {', '.join(messages)}" for field, messages in form.errors.items()]
    utils.post_script_file(script)
    #TODO
    pseudo_deck_name = session.get('pseudo_deck', '')
    pseudo_deck_path = os.path.join(current_app.config["DUMMY_DECK"], pseudo_deck_name)
    off_line = current_app.config["OFF_LINE"]
    pseudo_deck = utils.load_deck(pseudo_deck_path) if off_line and pseudo_deck_name else None
    snapshot = global_config.deck_snapshot if not off_line and global_config.deck else pseudo_deck
    try:
        exec_string = script.compile(current_app.config['SCRIPT_FOLDER'], snapshot=snapshot)
    except Exception as e:
        exec_string = {}
        msg = f"Compilation failed: {str(e)}"
    # exec_string = script.compile(current_app.config['SCRIPT_FOLDER'])
    session['python_code'] = exec_string
    design_buttons = {stype: create_action_button(script, stype) for stype in script.stypes}
    html = render_template("components/canvas_main.html", script=script, buttons_dict=design_buttons)
    return jsonify({"html": html, "success": success, "error": msg})


@design.get("/draft/instruments", strict_slashes=False)
@design.get("/draft/instruments/<string:instrument>")
@login_required
def get_operation_sidebar(instrument: str = ''):
    """
    .. :quickref: Workflow Design; handle methods of a specific instrument

    .. http:get:: /draft/instruments/<string:instrument>

    :param instrument: The name of the instrument to handle methods for.
    :type instrument: str

    :status 200: Render the methods for the specified instrument.
    """
    script = utils.get_script_file()
    pseudo_deck_name = session.get('pseudo_deck', '')
    pseudo_deck_path = os.path.join(current_app.config["DUMMY_DECK"], pseudo_deck_name)
    off_line = current_app.config["OFF_LINE"]
    pseudo_deck = utils.load_deck(pseudo_deck_path) if off_line and pseudo_deck_name else None
    autofill = session.get('autofill', False)

    if instrument == 'workflows':
        functions, forms = create_workflow_forms(script, autofill=autofill, design=True)

    elif instrument in global_config.defined_variables.keys() or instrument == 'flow_control' or instrument.startswith("blocks"):
        functions, forms = _create_forms(instrument, script, autofill, pseudo_deck)
    else:
        # Check if it's a deck method
        deck = global_config.deck
        if deck:
             # This part seems redundant given _create_forms logic but let's stick to existing pattern or just call _create_forms
             pass
        functions, forms = _create_forms(instrument, script, autofill, pseudo_deck)


    if instrument:
        html = render_template("components/sidebar.html", forms=forms, instrument=instrument, script=script)
    else:
        pseudo_deck_name = session.get('pseudo_deck', '')
        pseudo_deck_path = os.path.join(current_app.config["DUMMY_DECK"], pseudo_deck_name)
        off_line = current_app.config["OFF_LINE"]
        pseudo_deck = utils.load_deck(pseudo_deck_path) if off_line and pseudo_deck_name else None
        if off_line and pseudo_deck is None:
            flash("Choose available deck below.")
        deck_list = utils.available_pseudo_deck(current_app.config["DUMMY_DECK"])
        if not off_line:
            deck_variables = list(global_config.deck_snapshot.keys())
        else:
            deck_variables = list(pseudo_deck.keys()) if pseudo_deck else []
            deck_variables.remove("deck_name") if len(deck_variables) > 0 else deck_variables
        # edit_action_info = session.get("edit_action")
        html = render_template("components/sidebar.html", off_line=off_line, history=deck_list,
                               defined_variables=deck_variables,
                               local_variables=global_config.defined_variables,
                               block_variables=global_config.building_blocks,
                               )
    return jsonify({"html": html})
