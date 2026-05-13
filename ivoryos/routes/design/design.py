import os
import inspect

from flask import Blueprint, flash, jsonify, request, render_template, session, current_app
from flask_login import login_required, current_user

from ivoryos.services.draft_service import get_script_file, post_script_file
from ivoryos.services.connection_history import available_pseudo_deck
from ivoryos.runtime.state import GlobalState
from ivoryos.forms.dynamic_forms import create_action_button, create_form_from_pseudo, create_all_builtin_forms, create_workflow_forms
from ivoryos.models import db
from ivoryos.script import Script, ScriptEditor, ScriptRenderer
from ivoryos.parsers.py_to_json import convert_to_cards, extract_functions_and_convert
from ivoryos.parsers.introspection import load_interface_schema, _inspect_class, get_return_type, get_arg_type
from ivoryos.parsers.returns import extract_return_variables

# Import the new modular components
from ivoryos.routes.design.design_file import files
from ivoryos.routes.design.design_step import steps
from ivoryos.routes.design.design_agent import agent
from ivoryos.routes.library.library import publish

design = Blueprint('design', __name__, template_folder='templates')

# Register sub-blueprints
design.register_blueprint(files)
design.register_blueprint(steps)
design.register_blueprint(agent)

global_state = GlobalState()

# ---- Main Design Routes ----


def _create_forms(instrument, script, autofill, pseudo_deck = None):
    deck = global_state.deck
    functions = {}
    if instrument == 'flow_control':
        forms = create_all_builtin_forms(script=script)
    elif instrument in global_state.defined_variables.keys():
        _object = global_state.defined_variables.get(instrument)
        functions = _inspect_class(_object)
        forms = create_form_from_pseudo(pseudo=functions, autofill=autofill, script=script)
    elif instrument.startswith("blocks"):
        forms = create_form_from_pseudo(pseudo=global_state.building_blocks[instrument], autofill=autofill, script=script)
        functions = global_state.building_blocks[instrument]
    elif instrument.startswith("workflows"):
        _, forms = create_workflow_forms(script, autofill=autofill, design=True)
    else:
        if deck:
            functions = global_state.interface_schema.get(instrument, {})
        elif pseudo_deck:
            functions = pseudo_deck.get(instrument, {})
        forms = create_form_from_pseudo(pseudo=functions, autofill=autofill, script=script)
    return functions, forms

@design.route("/draft")
@login_required
def experiment_builder():
    """
    .. :quickref: Workflow Design; Experiment builder interface

    **Experiment Builder**

    .. http:get:: /draft

    Load the main experiment builder interface where users can design their workflow by adding actions, instruments, and logic.

    :status 200: Experiment builder loaded successfully.
    """
    deck = global_state.deck
    script = get_script_file()

    if deck and script.deck is None:
        script.deck = os.path.splitext(os.path.basename(deck.__file__))[
            0] if deck.__name__ == "__main__" else deck.__name__
        post_script_file(script)
    pseudo_deck_name = session.get('pseudo_deck', '')
    pseudo_deck_path = os.path.join(current_app.config["DUMMY_DECK"], pseudo_deck_name)
    off_line = current_app.config["OFF_LINE"]

    pseudo_deck = load_interface_schema(pseudo_deck_path) if off_line and pseudo_deck_name else None
    if off_line and pseudo_deck is None:
        flash("Choose available deck below.")

    deck_list = available_pseudo_deck(current_app.config["DUMMY_DECK"])

    if deck:
        deck_variables = list(global_state.interface_schema.keys())
        # deck_variables.insert(0, "flow_control")
    else:
        deck_variables = list(pseudo_deck.keys()) if pseudo_deck else []
        deck_variables.remove("deck_name") if len(deck_variables) > 0 else deck_variables

    # edit_action_info = session.get("edit_action")

    try:
        interface_schema = global_state.interface_schema if deck else pseudo_deck
        exec_string = script.python_script if script.python_script else ScriptRenderer(script).compile(current_app.config['SCRIPT_FOLDER'], interface_schema=interface_schema)
    except Exception as e:
        exec_string = {}
        flash(f"Error in Python script: {e}")
    # session['python_code'] = exec_string

    design_buttons = {stype: create_action_button(script, stype) for stype in script.stypes}

    return render_template('experiment_builder.html', off_line=off_line, history=deck_list,
                           script=script, defined_variables=deck_variables, buttons_dict=design_buttons,
                           local_variables=global_state.defined_variables, block_variables=global_state.building_blocks,
                           design_agent_enabled=current_app.config.get("ENABLE_AGENT"))

@design.route("/draft/code_preview", methods=["GET"])
@login_required
def compile_preview():
    """
    .. :quickref: Workflow Design; Preview generated code

    **Compile Preview**

    .. http:get:: /draft/code_preview

    Get a preview of the generated Python code for the current workflow.

    :query mode: The compilation mode ('single' or 'batch').
    :query batch: The batch processing mode ('sample' or others).
    :status 200: Returns the generated code as JSON.
    """
    # Get mode and batch from query parameters
    script = get_script_file()
    mode = request.args.get("mode", "single")   # default to "single"
    batch = request.args.get("batch", "sample") # default to "sample"

    pseudo_deck_name = session.get('pseudo_deck', '')
    pseudo_deck_path = os.path.join(current_app.config["DUMMY_DECK"], pseudo_deck_name)
    off_line = current_app.config["OFF_LINE"]
    pseudo_deck = load_interface_schema(pseudo_deck_path) if off_line and pseudo_deck_name else None
    interface_schema = global_state.interface_schema if not off_line and global_state.deck else pseudo_deck

    try:
        # Example: decide which code to return based on mode/batch
        if mode == "single":
            code = ScriptRenderer(script).compile(current_app.config['SCRIPT_FOLDER'], interface_schema=interface_schema)
        elif mode == "batch":
            code = ScriptRenderer(script).compile(current_app.config['SCRIPT_FOLDER'], batch=True, mode=batch, interface_schema=interface_schema)
        else:
            code = "Invalid mode. Please select 'single' or 'batch'."
    except Exception as e:
        code = f"Error compiling: {e}"

    if isinstance(code, dict):
        imports = ScriptRenderer(script).get_required_imports()
        if imports:
            # Simple approach: prepend to valid code blocks.
            code["imports"] = imports

    return jsonify(code=code)


@design.route("/draft/meta", methods=["PATCH"])
@login_required
def update_script_meta():
    """
    .. :quickref: Workflow Design; Update script metadata

    **Update Meta**

    .. http:patch:: /draft/meta

    Update the script metadata, such as the script name and status. If the script name is provided,
    it saves the script with that name. If the status is "finalized", it finalizes and publishes the script.

    :form name: The name to save the script as.
    :form status: The status of the script (e.g., "finalized").
    :status 200: Successfully updated the script metadata.
    """
    data = request.get_json()
    script = get_script_file()
    if 'name' in data:
        run_name = data.get("name")
        exist_script = Script.query.get(run_name)
        if exist_script is None:
            _, return_list = ScriptEditor(script).config_return()
            script.return_values = list(return_list)
            script.save_as(run_name)
            if 'registered' in data:
                 script.registered = data.get('registered')
            post_script_file(script)
            return jsonify(success=True)
        else:
            flash("Script name is already exist in database")
            return jsonify(success=False)

    if 'status' in data:
        if data['status'] == "finalized":
            _, return_list = ScriptEditor(script).config_return()
            script.return_values = list(return_list)
            script.finalize()
            post_script_file(script)
            publish()
            return jsonify(success=True)
    return jsonify(success=False)


@design.route("/draft/ui-state", methods=["PATCH"])
@login_required
def update_ui_state():
    """
    .. :quickref: Workflow Design; Update design UI state

    **Update UI State**

    .. http:patch:: /draft/ui-state

    Update UI settings for the design canvas, such as showing code overlays, setting the editing mode,
    handling deck selection, or toggling autofill.

    :form show_code: Whether to show the code overlay (bool).
    :form editing_type: The type of editing to set (prep, script, cleanup).
    :form autofill: Whether to enable autofill (bool).
    :form deck_name: The name of the pseudo-deck to select.
    :status 200: Updates the UI state successfully.
    """
    data = request.get_json()

    if "show_code" in data:
        session["show_code"] = bool(data["show_code"])
        return jsonify({"success": True})
    if "editing_type" in data:
        stype = data.get("editing_type")

        script = get_script_file()
        script.editing_type = stype
        post_script_file(script)

        # Re-render only the part of the page you want to update
        design_buttons = {stype: create_action_button(script, stype) for stype in script.stypes}
        rendered_html = render_template("components/canvas.html", script=script, buttons_dict=design_buttons)
        return jsonify({"html": rendered_html})

    if "autofill" in data:
        script = get_script_file()
        instrument = data.get("instrument", '')
        autofill = data.get("autofill", False)
        session['autofill'] = autofill
        _, forms = _create_forms(instrument, script, autofill)
        rendered_html = render_template("components/actions_panel.html", forms=forms, script=script, instrument=instrument)
        return jsonify({"html": rendered_html})

    if "deck_name" in data:
        pkl_name = data.get('deck_name', "")
        script = get_script_file()
        session['pseudo_deck'] = pkl_name
        deck_list = available_pseudo_deck(current_app.config["DUMMY_DECK"])

        if script.deck is None or script.isEmpty():
            script.deck = pkl_name.split('.')[0]
            post_script_file(script)
        elif script.deck and not script.deck == pkl_name.split('.')[0]:
            flash(f"Choose the deck with name {script.deck}")
        pseudo_deck_path = os.path.join(current_app.config["DUMMY_DECK"], pkl_name)
        pseudo_deck = load_interface_schema(pseudo_deck_path)
        deck_variables = list(pseudo_deck.keys()) if pseudo_deck else []
        deck_variables.remove("deck_name") if len(deck_variables) > 0 else deck_variables
        html = render_template("components/sidebar.html", history=deck_list,
                               defined_variables=deck_variables, local_variables = global_state.defined_variables,
                               block_variables=global_state.building_blocks, design_agent_enabled=current_app.config.get("ENABLE_AGENT"))
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
#     script = get_script_file()
#     script.currently_editing_order = order.split(",", len(script.currently_editing_script))
#     ScriptEditor(script).sort_actions()
#     exec_string = ScriptRenderer(script).compile(current_app.config['SCRIPT_FOLDER'])
#     post_script_file(script)
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
    deck = global_state.deck
    if deck:
        deck_name = os.path.splitext(os.path.basename(deck.__file__))[
            0] if deck.__name__ == "__main__" else deck.__name__
    else:
        deck_name = session.get("pseudo_deck", "")
    script = Script(deck=deck_name, author=current_user.get_id())
    post_script_file(script)
    exec_string = ScriptRenderer(script).compile(current_app.config['SCRIPT_FOLDER'])
    # session['python_code'] = exec_string
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
    deck = global_state.deck
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
    post_script_file(script)
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
    script = get_script_file()
    pseudo_deck_name = session.get('pseudo_deck', '')
    pseudo_deck_path = os.path.join(current_app.config["DUMMY_DECK"], pseudo_deck_name)
    off_line = current_app.config["OFF_LINE"]
    pseudo_deck = load_interface_schema(pseudo_deck_path) if off_line and pseudo_deck_name else None
    autofill = session.get('autofill', False)

    if instrument == 'workflows':
        functions, forms = create_workflow_forms(script, autofill=autofill, design=True)
    else:
        functions, forms = _create_forms(instrument, script, autofill, pseudo_deck)

    success = True
    msg = ""
    if "hidden_name" in request.form:
        interface_schema = global_state.interface_schema
        block_interface_schema = global_state.building_blocks
        method_name = request.form.get("hidden_name", None)
        form = forms.get(method_name) if forms else None
        insert_position = request.form.get("drop_target_id", None)

        if form:
            kwargs = {field.name: field.data for field in form if field.name != 'csrf_token'}
            
            # Collect dynamic kwargs
            extra_keys = request.form.getlist('extra_key[]')
            extra_values = request.form.getlist('extra_value[]')
            if extra_keys:
                extra_args = {k.strip(): v for k, v in zip(extra_keys, extra_values) if k and k.strip()}
                kwargs.update(extra_args)

            # print(kwargs)
            if form.validate_on_submit():
                function_name = kwargs.pop("hidden_name")
                batch_action = kwargs.pop("batch_action", False)
                consolidate_batch_args = request.form.getlist("consolidate_batch_args")

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

                return_format = get_return_type(function_data)
                save_data = extract_return_variables(kwargs, ScriptEditor.validate_function_name)

                # Save arg_order from signature to exclude dynamic args
                if function_data and 'signature' in function_data:
                    sig = function_data['signature']
                    arg_order = [k for k in kwargs.keys() if k in sig.parameters]
                else:
                    arg_order = list(kwargs.keys())

                primitive_arg_types = get_arg_type(kwargs, function_data)

                ScriptEditor.eval_list(kwargs, primitive_arg_types)
                kwargs = ScriptEditor(script).validate_variables(kwargs, primitive_arg_types)
                
                # Use function_data to get coroutine status, avoiding KeyError for virtual setters
                coroutine = function_data.get("coroutine", False)

                # print(kwargs)
                action = {"instrument": instrument, "action": function_name,
                          "args": kwargs,
                          "return": save_data,
                          'arg_types': primitive_arg_types,
                          "coroutine": coroutine,
                          "batch_action": batch_action,
                          "consolidate_batch_args": consolidate_batch_args,
                          "arg_order": arg_order,  # Explicitly save order
                          "return_format": return_format,
                          }
                ScriptEditor(script).add_action(action=action, insert_position=insert_position)
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
                    ScriptEditor(script).add_input_action(insert_position=insert_position, **kwargs)
                elif logic_type == 'variable':
                    try:
                        ScriptEditor(script).add_variable(insert_position=insert_position, **kwargs)
                    except ValueError as e:
                        success = False
                        msg = e.__str__()
                elif logic_type == 'math_variable' or logic_type == 'math': # should work with math_variable but doesnt, but does for math because it is the builtin name; should change all instances of using == "math_variable" to math later?
                    try:
                        ScriptEditor(script).add_math_variable(insert_position=insert_position, **kwargs)
                    except ValueError as e:
                        success = False
                        msg = e.__str__()
                else:
                    ScriptEditor(script).add_logic_action(logic_type=logic_type, insert_position=insert_position, **kwargs)
            else:
                success = False
                msg = [f"{field}: {', '.join(messages)}" for field, messages in form.errors.items()]
    elif "workflow_name" in request.form:
        workflow_name = request.form.get("workflow_name")

        # still get workflow by name (name is the primary key)
        target_workflow = Script.query.filter_by(name=workflow_name).first()
        unique_key = None
        if target_workflow and target_workflow.uuid:
            unique_key = target_workflow.uuid
            
        form = forms.get(unique_key) if forms and unique_key else None
        
        insert_position = request.form.get("drop_target_id", None)
        # batch_action = request.form.get("batch_action", False)
        if form:
            kwargs = {field.name: field.data for field in form if field.name != 'csrf_token'}
            if form.validate_on_submit():
                batch_action = kwargs.pop("batch_action", False)
                consolidate_batch_args = request.form.getlist("consolidate_batch_args")
                kwargs.pop('workflow_name')
                save_data = extract_return_variables(kwargs, ScriptEditor.validate_function_name)

                primitive_arg_types = get_arg_type(kwargs, functions[unique_key])
                ScriptEditor.eval_list(kwargs, primitive_arg_types)
                kwargs = ScriptEditor(script).validate_variables(kwargs, primitive_arg_types)
                
                # Fetch the workflow to embed its steps
                target_workflow = Script.query.filter_by(name=workflow_name).first()
                embedded_steps = []
                if target_workflow:
                    embedded_steps = target_workflow.script_dict.get('script', [])

                action = {"instrument": instrument, "action": workflow_name,
                          "args": kwargs,
                          "return": save_data,
                          "batch_action": batch_action,
                          "consolidate_batch_args": consolidate_batch_args,
                          'arg_types': primitive_arg_types,
                          "workflow": embedded_steps} # Embed steps
                # print(action)
                ScriptEditor(script).add_action(action=action, insert_position=insert_position)
            else:
                success = False
                msg = [f"{field}: {', '.join(messages)}" for field, messages in form.errors.items()]
    post_script_file(script)
    #TODO
    pseudo_deck_name = session.get('pseudo_deck', '')
    pseudo_deck_path = os.path.join(current_app.config["DUMMY_DECK"], pseudo_deck_name)
    off_line = current_app.config["OFF_LINE"]
    pseudo_deck = load_interface_schema(pseudo_deck_path) if off_line and pseudo_deck_name else None
    interface_schema = global_state.interface_schema if not off_line and global_state.deck else pseudo_deck
    try:
        exec_string = ScriptRenderer(script).compile(current_app.config['SCRIPT_FOLDER'], interface_schema=interface_schema)
    except Exception as e:
        exec_string = {}
        msg = f"Compilation failed: {str(e)}"
    # exec_string = ScriptRenderer(script).compile(current_app.config['SCRIPT_FOLDER'])
    # session['python_code'] = exec_string
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
    script = get_script_file()
    pseudo_deck_name = session.get('pseudo_deck', '')
    pseudo_deck_path = os.path.join(current_app.config["DUMMY_DECK"], pseudo_deck_name)
    off_line = current_app.config["OFF_LINE"]
    pseudo_deck = load_interface_schema(pseudo_deck_path) if off_line and pseudo_deck_name else None
    autofill = session.get('autofill', False)

    if instrument == 'workflows':
        functions, forms = create_workflow_forms(script, autofill=autofill, design=True)

    elif instrument in global_state.defined_variables.keys() or instrument == 'flow_control' or instrument.startswith("blocks"):
        functions, forms = _create_forms(instrument, script, autofill, pseudo_deck)
    else:
        # Check if it's a deck method
        deck = global_state.deck
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
        pseudo_deck = load_interface_schema(pseudo_deck_path) if off_line and pseudo_deck_name else None
        if off_line and pseudo_deck is None:
            flash("Choose available deck below.")
        deck_list = available_pseudo_deck(current_app.config["DUMMY_DECK"])
        if not off_line:
            deck_variables = list(global_state.interface_schema.keys())
        else:
            deck_variables = list(pseudo_deck.keys()) if pseudo_deck else []
            deck_variables.remove("deck_name") if len(deck_variables) > 0 else deck_variables
        # edit_action_info = session.get("edit_action")
        html = render_template("components/sidebar.html", off_line=off_line, history=deck_list,
                               defined_variables=deck_variables,
                               local_variables=global_state.defined_variables,
                               block_variables=global_state.building_blocks,
                               script=script, 
                               design_agent_enabled=current_app.config.get("ENABLE_AGENT"))
    return jsonify({"html": html})


@design.route("/draft/import_python_file", methods=["POST"])
@login_required
def import_python_file():
    """
    .. :quickref: Workflow Design; Import Python script

    **Import Python File**

    .. http:post:: /draft/import_python_file

    Upload a Python script file and extract workflow functions to be converted into visual cards.

    :form file: The Python (.py) file to import.
    :status 200: Returns extracted workflows and identifies duplicate script names.
    """
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "No file part"})
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "error": "No selected file"})

        source_code = file.read().decode("utf-8")
        workflows = extract_functions_and_convert(source_code)

        if not workflows:
            return jsonify({"success": False, "error": "No functions found in file"})

        duplicates = []
        for name in workflows.keys():
            if Script.query.get(name):
                duplicates.append(name)

        return jsonify({
            "success": True,
            "workflows": workflows,
            "duplicates": duplicates
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@design.route("/draft/confirm_import_python", methods=["POST"])
@login_required
def confirm_import_python():
    """
    .. :quickref: Workflow Design; Confirm Python import

    **Confirm Import**

    .. http:post:: /draft/confirm_import_python

    Finalize the import of extracted workflows, optionally overwriting existing scripts in the database.

    :json workflows: A dictionary of extracted workflows to save.
    :json overwrite: A list of script names that should be overwritten.
    :status 200: Returns success after saving the scripts.
    """
    try:
        data = request.get_json()
        workflows = data.get("workflows", {})
        overwrite = data.get("overwrite", [])

        results = {}

        deck = global_state.deck
        if deck:
             deck_name = os.path.splitext(os.path.basename(deck.__file__))[0] if deck.__name__ == "__main__" else deck.__name__
        else:
             deck_name = "unknown"

        for name, content in workflows.items():
            cards = content.get("cards", [])
            source = content.get("source", "")

            exist_script = Script.query.get(name)

            if exist_script:
                if name in overwrite:
                    # Overwrite
                    # Create a copy of dict to modify to ensure SQLAlchemy detects change
                    new_dict = dict(exist_script.script_dict)
                    new_dict['script'] = cards
                    exist_script.script_dict = new_dict
                    
                    # if isinstance(exist_script.python_script, dict):
                    #      exist_script.python_script['script'] = source
                    # else:
                    #      exist_script.python_script = {'script': source}

                    exist_script.author = current_user.get_id()
                    db.session.merge(exist_script)
                    results[name] = "overwritten"
                else:
                    results[name] = "skipped"
            else:
                # Create
                new_script = Script(name=name, author=current_user.get_id(), deck=deck_name)
                # Initialize script_dict and ensure 'script' key is set
                script_dict = {"prep": [], "script": cards, "cleanup": []}
                new_script.script_dict = script_dict
                # new_script.python_script = {'script': source}
                
                db.session.add(new_script)
                results[name] = "created"
        
        db.session.commit()
        return jsonify({"success": True, "results": results})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)})


@design.get("/draft/variables")
@login_required
def get_available_variables():
    """
    Get available variables for the current script state.
    Optional query param: before_id (int) - filter variables available before this step ID.
    """
    script = get_script_file()
    before_id = request.args.get('before_id')
    if before_id:
        try:
            before_id = int(before_id)
        except ValueError:
            before_id = None

    variable_list = ScriptEditor(script).get_autocomplete_variables(before_id=before_id)
    return jsonify({"variables": variable_list})
