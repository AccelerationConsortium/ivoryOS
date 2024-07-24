import threading
from datetime import datetime
import json
import os
import csv
import pickle
import traceback
import time
from inspect import Signature
from typing import Optional

from flask import Flask, redirect, url_for, flash, jsonify, send_file, request, render_template, session
from flask_socketio import SocketIO
from flask_wtf import FlaskForm
from werkzeug.utils import secure_filename
from flask_login import LoginManager, login_required, login_user, logout_user
import bcrypt

from sdl_webui.utils import utils
from sdl_webui.utils.form import create_form_from_module, create_builtin_form, create_action_button, format_name
from sdl_webui.utils.model import Script, User, db

# import instruments
# from instruments import *
# from config import off_line
# import config
global deck, autofill
deck = None
autofill = False
off_line = False

app = Flask(__name__)
app.config['OUTPUT_FOLDER'] = 'webui_data'
app.config['CSV_FOLDER'] = os.path.join(app.config['OUTPUT_FOLDER'], 'config_csv/')
app.config['SCRIPT_FOLDER'] = os.path.join(app.config['OUTPUT_FOLDER'], 'scripts/')
app.config['DATA_FOLDER'] = os.path.join(app.config['OUTPUT_FOLDER'], 'results/')
app.config["DUMMY_DECK"] = os.path.join(app.config['OUTPUT_FOLDER'], 'pseudo_deck/')
app.config["DECK_HISTORY"] = os.path.join(app.config['OUTPUT_FOLDER'], 'deck_history.txt')
# basedir = os.path.abspath(os.path.dirname(__file__))

app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///project.db"  # local DB
# app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://freedb_heinlab:#2PxSCTVJdrb%x*@sql.freedb.tech:3306/freedb_web_gui'
# app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://sql9620530:bb6vamcmXB@sql9.freesqldatabase.com:3306/sql9620530'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = "key"
socketio = SocketIO(app)

# login helper
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# initialize database
db.init_app(app)
with app.app_context():
    db.create_all()
utils.create_gui_dir(app.config['OUTPUT_FOLDER'])
# deck = None
pseudo_deck = None
defined_variables = set()
api_variables = set()

# if off_line:
#     api_variables = dir(instruments)
#     api_variables = set([i for i in api_variables if not i.startswith("_") and i not in ["sys", "os"]])

logger = utils.start_logger(socketio)


@app.route("/")
@login_required
def index():
    return render_template('home.html')


def get_script_file():
    session_script = session.get("scripts")
    if session_script:
        s = Script()
        s.__dict__.update(**session_script)
        return s
    else:
        return Script(author=session.get('user'))


def post_script_file(script, is_dict=False):
    if is_dict:
        session['scripts'] = script
    else:
        # print(script.as_dict())
        session['scripts'] = script.as_dict()


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # session.query(User, User.name).all()
        user = db.session.query(User).filter(User.username == username).first()
        input_password = password.encode('utf-8')
        # if user and bcrypt.checkpw(input_password, user.hashPassword.encode('utf-8')):
        if user and bcrypt.checkpw(input_password, user.hashPassword):
            # password.encode("utf-8")
            # user = User(username, password.encode("utf-8"))
            login_user(user)
            session['user'] = username
            script_file = Script(author=username)
            session["script"] = script_file.as_dict()
            session['hidden_functions'] = {}
            post_script_file(script_file)
            return redirect(url_for('index'))
        else:
            flash("Incorrect username or password")
    return render_template('login.html')


@app.route('/hide_function/<instrument>/<function>')
def hide_function(instrument, function):
    back = request.referrer
    functions = session.get("hidden_functions")
    if instrument in functions.keys():
        if function not in functions[instrument]:
            functions[instrument].append(function)
    else:
        functions[instrument] = [function]
    session['hidden_functions'] = functions
    return redirect(back)


@app.route('/remove_hidden/<instrument>/<function>')
def remove_hidden(instrument, function):
    back = request.referrer
    functions = session.get("hidden_functions")
    if instrument in functions.keys():
        if function in functions[instrument]:
            functions[instrument].remove(function)
    session['hidden_functions'] = functions
    return redirect(back)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        user = User(username, hashed)
        try:
            db.session.add(user)
            db.session.commit()
            return redirect(url_for('login'))
        except Exception:
            flash("username exists :(")
    return render_template('signup.html')


@app.route("/logout")
@login_required
def logout():
    global pseudo_deck
    pseudo_deck = None
    logout_user()
    session.clear()
    return redirect(url_for('login'))


@login_manager.user_loader
def load_user(username):
    return User(username, password=None)


@app.route("/help")
def help_info():
    sample_deck = """
    import sys,os
    sys.path.append(os.getcwd())
                            
    from new_era.peristaltic_pump_network import PeristalticPumpNetwork, NetworkedPeristalticPump
    from vapourtec.sf10 import SF10
    # --------------------new_era---------------------------
    pump_network = PeristalticPumpNetwork('com5')
    new_era = pump_network.add_pump(address=0, baudrate=9600)
    
    # --------------------  SF10  --------------------------
    sf10 = SF10(device_port="com7")"""
    return render_template('help.html', sample_deck=sample_deck)


@app.route("/controllers")
@login_required
def controllers_home():
    return render_template('controllers_home.html', defined_variables=defined_variables)


@app.route("/experiment/build/", methods=['GET', 'POST'])
@app.route("/experiment/build/<instrument>/", methods=['GET', 'POST'])
@login_required
def experiment_builder(instrument=None):
    global pseudo_deck, deck, autofill
    forms = None
    if pseudo_deck is None:
        pseudo_deck = load_deck(session.get('pseudo_deck'))
    script = get_script_file()
    deck_list = utils.available_pseudo_deck(app.config["DUMMY_DECK"])
    script.sort_actions()

    if deck:
        deck_variables = parse_deck(deck)
    else:
        deck_variables = list(pseudo_deck.keys()) if pseudo_deck else []
        deck_variables.remove("deck_name") if len(deck_variables) > 0 else deck_variables

    functions = []

    if pseudo_deck is None:
        flash("Choose available deck below.")
        # flash(f"Make sure to import {script_dict['deck'] if script_dict['deck'] else 'deck'} for this script")
    if instrument:
        functions = utils.parse_functions(find_instrument_by_name(instrument))
        # inst_object = find_instrument_by_name(instrument)

        if instrument in ['if', 'while', 'variable', 'wait']:
            forms = create_builtin_form(instrument)
        else:
            forms = create_form_from_module(sdl_module=find_instrument_by_name(instrument), autofill=autofill)
        if request.method == 'POST' and "hidden_name" in request.form:
            all_kwargs = request.form.copy()
            method_name = all_kwargs.get("hidden_name", None)
            # if method_name is not None:
            form = forms.get(method_name)
            if form and form.validate_on_submit():
                # print(kwargs)
                function_name = all_kwargs.get("hidden_name")
                save_data = all_kwargs.get('return', '')
                # TODO convert variables in kwargs
                variable_kwargs = {}
                variable_kwargs_types = {}
                kwargs = all_kwargs.copy()

                kwargs.pop("hidden_name", None)
                kwargs.pop("return", None)
                kwargs.pop("csrf_token", None)

                try:
                    variable_kwargs, variable_kwargs_types = utils.find_variable_in_script(script, kwargs)

                    for name in variable_kwargs.keys():
                        del kwargs[name]

                    primitive_arg_types = utils.get_arg_type(kwargs, functions[function_name])

                except:
                    primitive_arg_types = utils.get_arg_type(kwargs, functions[function_name])

                kwargs.update(variable_kwargs)
                arg_types = {}
                arg_types.update(variable_kwargs_types)
                arg_types.update(primitive_arg_types)
                all_kwargs.update(variable_kwargs)

                action = {"instrument": instrument, "action": function_name, "args": kwargs, "return": save_data,
                          'arg_types': arg_types}
                script.add_action(action=action)
            else:
                flash(form.errors)
        # toggle autofill
        elif request.method == 'POST' and "builtin_name" in request.form:
            kwargs = {field.name: field.data for field in forms if field.name != 'csrf_token'}
            if forms.validate_on_submit():
                logic_type = kwargs.pop('builtin_name')
                if 'variable' in kwargs:
                    script.add_variable(**kwargs)
                else:
                    script.add_logic_action(logic_type=logic_type, **kwargs)

        elif request.method == 'POST' and "autofill" in request.form:
            autofill = not autofill
            forms = create_form_from_module(find_instrument_by_name(instrument), autofill=autofill)
        post_script_file(script)
    buttons = [create_action_button(i) for i in script.currently_editing_script]
    return render_template('experiment_builder.html', off_line=off_line, instrument=instrument, history=deck_list,
                           script=script, defined_variables=deck_variables, local_variables=defined_variables,
                           functions=functions, autofill=autofill, forms=forms, buttons=buttons,
                           format_name=format_name)


def process_data(data, config_type):
    rows = {}  # Dictionary to hold webui_data organized by rows

    # Organize webui_data by rows
    for key, value in data.items():
        if value:  # Only process non-empty values
            # Extract the field name and row index
            field_name, row_index = key.split('[')
            row_index = int(row_index.rstrip(']'))

            # If row not in rows, create a new dictionary for that row
            if row_index not in rows:
                rows[row_index] = {}

            # Add or update the field value in the specific row's dictionary
            rows[row_index][field_name] = value

    # Filter out any empty rows and create a list of dictionaries
    filtered_rows = [row for row in rows.values() if len(row) == len(config_type)]

    return filtered_rows


@app.route("/experiment", methods=['GET', 'POST'])
@login_required
def experiment_run():
    config_preview = []
    config_file_list = [i for i in os.listdir(app.config["CSV_FOLDER"]) if not i == ".gitkeep"]
    script = get_script_file()
    exec_string = script.compile(app.config['SCRIPT_FOLDER'])
    config_file = request.args.get("filename")
    config = []
    if config_file:
        session['config_file'] = request.args.get("filename")
    filename = session.get("config_file")
    if filename:
        config_preview = list(csv.DictReader(open(os.path.join(app.config['CSV_FOLDER'], filename))))
        config_preview = config_preview[1:6]
        config = list(csv.DictReader(open(os.path.join(app.config['CSV_FOLDER'], filename))))
        arg_type = config.pop(0)
    try:
        exec(exec_string)
    except Exception:
        flash("Please check syntax!!")
        return redirect(url_for("experiment_builder"))
    run_name = script.name if script.name else "untitled"
    file = open(os.path.join(app.config['SCRIPT_FOLDER'], f"{run_name}.py"), "r")
    script_py = file.read()
    file.close()

    dismiss = session.get("dismiss", None)
    script = get_script_file()
    no_deck_warning = False

    script.sort_actions()
    _, return_list = script.config_return()
    config_list, config_type_list = script.config("script")
    # config = script.config("script")
    data_list = os.listdir(app.config['DATA_FOLDER'])
    data_list.remove(".gitkeep") if ".gitkeep" in data_list else data_list
    if deck is None:
        no_deck_warning = True
        flash(f"No deck is found, import {script.deck}")
    elif script.deck and not script.deck == deck.__name__:
        flash(f"This script is not compatible with current deck, import {script.deck}")
    if request.method == "POST":
        bo_args = None
        if "bo" in request.form:
            bo_args = request.form.to_dict()
            # ax_client = utils.ax_initiation(bo_args)
        if "online-config" in request.form:
            # print("online-config")
            # print(request.form.to_dict())
            config = process_data(request.form.to_dict(), config_list)
        repeat = request.form.get('repeat', None)

        try:

            thread = threading.Thread(target=generate_progress, args=(run_name, config, repeat, script, bo_args))
            thread.start()
        # generate_progress(run_name, filename, repeat)

        except Exception as e:
            flash(e)
    print(config_list, config_type_list)
    return render_template('experiment_run.html', script=script.script_dict, filename=filename, dot_py=script_py,
                           return_list=return_list, config_list=config_list, config_file_list=config_file_list,
                           config_preview=config_preview, data_list=data_list, config_type_list=config_type_list,
                           history=utils.import_history(app.config["DECK_HISTORY"]), no_deck_warning=no_deck_warning,
                           dismiss=dismiss)

    # @app.route('/progress')
    # def progress(run_name, filename, repeat):
    #     return Response(generate_progress(run_name, filename, repeat), mimetype='text/event-stream')

    # @app.route('/progress')


def generate_progress(run_name, config, repeat, script, bo_args):
    time.sleep(1)
    compiled = True
    _, arg_type = script.config("script")
    # script = get_script_file()
    exec_string = script.compile(app.config['SCRIPT_FOLDER'])
    # arg_type = {}
    exec(exec_string)
    output_list = []
    _, return_list = script.config_return()
    exec(f"{run_name}_prep()")
    logger.info('Executing preparation steps')
    if not repeat and not repeat == "":

        for i in config:
            # try to convert types first
            try:
                i = utils.convert_config_type(i, arg_type)
            except Exception as e:
                logger.info(e)
                compiled = False
                # flash(e)
                # return redirect(url_for("experiment_run"))
        if compiled:
            for i, kwargs in enumerate(config):
                # i is in OrderedDict on ur_deck

                kwargs = dict(kwargs)
                logger.info(f'Executing {i + 1} of {len(config)} with kwargs = {kwargs}')
                progress = (i + 1) * 100 / len(config)
                socketio.emit('progress', {'progress': progress})
                output = eval(f"{run_name}_script(**{str(kwargs)})")
                if output:
                    kwargs.update(output)
                    output_list.append(kwargs)
                # yield f"webui_data: {i}/{len(df)} is done"
    if repeat and not repeat == '':
        if bo_args:
            logger.info(f'Initializing optimizer...')
            ax_client = utils.ax_initiation(bo_args)
        for i in range(int(repeat)):
            logger.info(f'Executing {run_name}: {i + 1}/{repeat}')
            progress = (i + 1) * 100 / int(repeat)
            socketio.emit('progress', {'progress': progress})
            if bo_args:

                # ax_client = utils.ax_initiation(bo_args)
                try:
                    parameters, trial_index = ax_client.get_next_trial()
                    logger.info(f'Output value: {parameters}')
                    output = eval(f"{run_name}_script(**{parameters})")
                    # print(output)
                    ax_client.complete_trial(trial_index=trial_index, raw_data=output)
                except Exception as e:
                    logger.info(f'Optimization error: {e}')
                    break
            else:
                output = eval(f"{run_name}_script()")
            if output:
                output_list.append(output)
                logger.info(f'Output value: {output}')
    if compiled:
        exec(run_name + "_cleanup()")
        logger.info('Executing clean up steps')
        # print(output_list)
        if len(output_list) > 0:
            args = list(arg_type.keys())
            args.extend(return_list)
            filename = run_name + "_" + datetime.now().strftime("%Y-%m-%d %H-%M") + ".csv"
            with open(os.path.join(app.config["DATA_FOLDER"], filename), "w", newline='') as file:
                writer = csv.DictWriter(file, fieldnames=args)
                writer.writeheader()
                writer.writerows(output_list)
        logger.info('Finished')
    else:
        logger.info('Task abandoned')
    # session["most_recent_result"] = filename
    # flash("Run finished")
    # return redirect(url_for("experiment_run"))


@app.route("/experiment_preview", methods=['GET', 'POST'])
@login_required
def experiment_preview():
    # current_variables = set(dir())
    script = get_script_file()
    exec_string = script.compile(app.config['SCRIPT_FOLDER'])
    try:
        exec(exec_string)
    except Exception:
        flash("Please check syntax!!")
        return redirect(url_for("experiment_builder"))
    run_name = script.name if script.name else "untitled"
    file = open(os.path.join(app.config["CSV_FOLDER"], f"{run_name}.py"), "r")
    script_py = file.read()
    file.close()
    # _, return_list = script.config_return()

    return render_template('experiment_preview.html', script=script.script_dict, dot_py=script_py, )


@app.route("/my_deck")
@login_required
def deck_controllers():
    global deck
    deck_variables = parse_deck(deck)
    return render_template('controllers_home.html', defined_variables=deck_variables, deck=True,
                           history=utils.import_history(app.config["DECK_HISTORY"]))


@app.route("/new_controller/")
@app.route("/new_controller/<instrument>", methods=['GET', 'POST'])
@login_required
def new_controller(instrument=None):
    device = None
    args = None
    if instrument:

        device = find_instrument_by_name(instrument)
        # print(device)
        args = utils.inspect.signature(device.__init__)

        if request.method == 'POST':
            device_name = request.form.get("device_name", None)
            if device_name and device_name in globals():
                flash("Device name is defined. Try another name, or leave it as blank to auto-configure")
                return render_template('controllers_new.html', instrument=instrument, api_variables=api_variables,
                                       device=device, args=args, defined_variables=defined_variables)
            if not device_name:
                device_name = device.__name__.lower() + "_"
                num = 1
                while device_name + str(num) in globals():
                    num += 1
                device_name = device_name + str(num)
            kwargs = request.form.to_dict()
            kwargs.pop("device_name")
            for i in kwargs:
                if kwargs[i] in globals():
                    kwargs[i] = globals()[kwargs[i]]
            try:
                utils.convert_config_type(kwargs, device.__init__.__annotations__, is_class=True)
            except Exception as e:
                flash(e)
            try:
                globals()[device_name] = device(**kwargs)
                defined_variables.add(device_name)
                return redirect(url_for('controllers_home'))
            except Exception as e:
                flash(e)
    return render_template('controllers_new.html', instrument=instrument, api_variables=api_variables,
                           device=device, args=args, defined_variables=defined_variables)


@app.route("/controllers/<instrument>", methods=['GET', 'POST'])
@login_required
def controllers(instrument):
    inst_object = find_instrument_by_name(instrument)
    functions = utils.parse_functions(inst_object)
    if request.method == 'POST':
        args = request.form.to_dict()
        function_name = args.pop('action')
        function_executable = getattr(inst_object, function_name)
        try:
            args, _ = utils.convert_type(args, functions[function_name])
        except Exception as e:
            flash(e)
            return render_template('controllers.html', instrument=instrument, functions=functions, inst=inst_object)
        if type(functions[function_name]) is dict:
            args = list(args.values())[0]
        # try:
        output = ''
        if callable(function_executable):
            # thread = threading.Thread(target=function_executable, kwargs=args)
            # thread.start()
            if args is not None:
                output = function_executable(**args)
            else:
                output = function_executable()
        else:  # for setter
            function_executable = args
        flash(f"\nRun Success! Output value: {output}.")
        # except Exception as e:
        #     flash(e)
    return render_template('controllers.html', instrument=instrument, functions=functions, inst=inst_object)


# -----------------------handle action editing--------------------------------------------
@app.route("/delete/<id>")
@login_required
def delete_action(id):
    back = request.referrer
    script = get_script_file()
    script.delete_action(id)
    post_script_file(script)
    return redirect(back)


@app.route("/edit/<uuid>", methods=['GET', 'POST'])
@login_required
def edit_action(uuid):
    script = get_script_file()
    action = script.find_by_uuid(uuid)
    session['edit_action'] = action
    if request.method == "POST":
        if "back" not in request.form:
            args = request.form.to_dict()
            save_as = args.pop('return', '')
            try:
                script.update_by_uuid(uuid=uuid, args=args, output=save_as)
            except Exception as e:
                flash(e.__str__())
        session.pop('edit_action')
    return redirect(url_for('experiment_builder'))


@app.route("/edit_workflow/<workflow_name>")
@login_required
def edit_workflow(workflow_name):
    row = Script.query.get(workflow_name)
    script = Script(**row.as_dict())
    post_script_file(script)
    if pseudo_deck and not script.deck == pseudo_deck["deck_name"]:
        flash(f"Choose the deck with name {script.deck}")
    return redirect(url_for('experiment_builder'))


@app.route("/delete_workflow/<workflow_name>")
@login_required
def delete_workflow(workflow_name):
    Script.query.filter(Script.name == workflow_name).delete()
    db.session.commit()
    return redirect(url_for('load_from_database'))


@app.route("/publish")
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
    return redirect(url_for('experiment_builder'))


@app.route("/finalize")
@login_required
def finalize():
    script = get_script_file()
    script.finalize()
    db.session.merge(script)
    db.session.commit()
    post_script_file(script)
    return redirect(url_for('experiment_builder'))


@app.route("/database/", methods=['GET', 'POST'])
@app.route("/database/<deck_name>", methods=['GET', 'POST'])
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


@app.route("/edit_run_name", methods=['GET', 'POST'])
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
        return redirect(url_for("experiment_builder"))


@app.route("/save_as", methods=['GET', 'POST'])
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
        return redirect(url_for("experiment_builder"))


@app.route("/toggle_script_type/<stype>")
@login_required
def toggle_script_type(stype=None):
    script = get_script_file()
    script.editing_type = stype
    post_script_file(script)
    return redirect(url_for('experiment_builder'))


@app.route("/updateList", methods=['GET', 'POST'])
@login_required
def update_list():
    getorder = request.form['order']
    script = get_script_file()
    script.currently_editing_order = getorder.split(",", len(script.currently_editing_script))
    post_script_file(script)
    return jsonify('Successfully Updated')


# --------------------handle all the import/export and download/upload--------------------------
@app.route("/clear")
@login_required
def clear():
    if deck:
        deck_name = deck.__name__
    elif pseudo_deck:
        deck_name = pseudo_deck["deck_name"]
    else:
        deck_name = ''
    script = Script(deck=deck_name, author=session.get('username'))
    post_script_file(script)
    return redirect(url_for("experiment_builder"))


@app.route("/import_api", methods=['GET', 'POST'])
def import_api():
    filepath = request.form.get('filepath')
    # filepath.replace('\\', '/')
    name = os.path.split(filepath)[-1].split('.')[0]
    try:
        spec = utils.importlib.util.spec_from_file_location(name, filepath)
        module = utils.importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        classes = utils.inspect.getmembers(module, utils.inspect.isclass)
        if len(classes) == 0:
            flash("Invalid import: no class found in the path")
            return redirect(url_for("controllers_home"))
        for i in classes:
            globals()[i[0]] = i[1]
            api_variables.add(i[0])
    # should handle path error and file type error
    except Exception as e:
        flash(e.__str__())
    return redirect(url_for("new_controller"))


@app.route("/disconnect", methods=["GET"])
@app.route("/disconnect/<device_name>", methods=["GET"])
def disconnect(device_name=None):
    if device_name:
        try:
            exec(device_name + ".disconnect()")
        except Exception:
            pass
        defined_variables.remove(device_name)
        globals().pop(device_name)
        return redirect(url_for('controllers_home'))

    deck_variables = ["deck." + var for var in set(dir(deck))
                      if not (var.startswith("_") or var[0].isupper() or var.startswith("repackage"))
                      and not type(eval("deck." + var)).__module__ == 'builtins']
    for i in deck_variables:
        try:
            exec(i + ".disconnect()")
        except Exception:
            pass
    globals()["deck"] = None
    return redirect(url_for('deck_controllers'))


@app.route("/import_deck", methods=['POST'])
def import_deck():
    global deck, pseudo_deck
    script = get_script_file()
    filepath = request.form.get('filepath')
    session['dismiss'] = request.form.get('dismiss')
    update = request.form.get('update')
    back = request.referrer
    if session['dismiss']:
        return redirect(back)
    # if filepath == "manage history":

    name = os.path.split(filepath)[-1].split('.')[0]
    try:
        module = utils.import_module_by_filepath(filepath=filepath, name=name)
        # deck format checking
        if not utils.if_deck_valid(module):
            flash("Invalid Deck import")
            return redirect(url_for("deck_controllers"))
        globals()["deck"] = module
        utils.save_to_history(filepath, app.config["DECK_HISTORY"])
        parse_deck(deck, save=update)

        if script.deck is None:
            script.deck = module.__name__
    # file path error exception
    except Exception as e:
        flash(e.__str__())
    return redirect(back)


@app.route("/import_pseudo", methods=['GET', 'POST'])
def import_pseudo():
    global pseudo_deck
    pkl_name = request.form.get('pkl_name')
    script = get_script_file()
    try:
        pseudo_deck = load_deck(pkl_name)
        session['pseudo_deck'] = pkl_name
    except Exception:
        flash(traceback.format_exc())

    if script.deck is None or script.isEmpty():
        script.deck = pkl_name.split('.')[0]
        post_script_file(script)
    elif script.deck and not script.deck == pkl_name.split('.')[0]:
        flash(f"Choose the deck with name {script.deck}")
    return redirect(url_for("experiment_builder"))


def load_deck(pkl_name):
    if not pkl_name:
        return None
    with open(os.path.join(app.config["DUMMY_DECK"], pkl_name), 'rb') as f:
        pseudo_deck = pickle.load(f)
    return pseudo_deck


@app.route('/generate_grid', methods=['get', 'POST'])
def generate_grid():
    grid = None
    if request.method == "POST":
        if "select_tray" in request.form:
            tray_name = request.form.get('select_tray')
            tray_size = utils.tray_size_dict[tray_name]
            grid = utils.make_grid(**tray_size)
        else:
            col = request.form.get('col')
            row = request.form.get('row')
            grid = utils.make_grid(int(row), int(col))

    return render_template("grid.html", grid=grid, grid_dict=utils.tray_size_dict)


@app.route('/vial', methods=['POST'])
def vial():
    if request.method == "POST":
        vials = request.form.to_dict()
        flash(list(vials.keys()))
    return redirect(url_for("generate_grid"))


@app.route('/uploads', methods=['GET', 'POST'])
def upload():
    """
    upload csv configuration file
    :return:
    """
    if request.method == "POST":
        f = request.files['file']
        if 'file' not in request.files:
            flash('No file part')
        if f.filename.split('.')[-1] == "csv":
            filename = secure_filename(f.filename)
            f.save(os.path.join(app.config['CSV_FOLDER'], filename))
            session['config_file'] = filename
            return redirect(url_for("experiment_run"))
        else:
            flash("Config file is in csv format")
            return redirect(url_for("experiment_run"))
    # return send_from_directory(directory=uploads, filename=filename)


@app.route('/load_json', methods=['GET', 'POST'])
def load_json():
    if request.method == "POST":
        f = request.files['file']
        if 'file' not in request.files:
            flash('No file part')
        if f.filename.endswith("json"):
            script_dict = json.load(f)
            post_script_file(script_dict, is_dict=True)
        else:
            flash("Script file need to be JSON file")
    return redirect(url_for("experiment_builder"))


@app.route('/download/<filetype>')
def download(filetype):
    script = get_script_file()
    run_name = script.name if script.name else "untitled"
    if filetype == "configure":
        filepath = f"{run_name}_config.csv"
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            cfg, cfg_types = script.config("script")
            writer.writerow(cfg)
            writer.writerow(list(cfg_types.values()))
    elif filetype == "script":
        script.sort_actions()
        json_object = json.dumps(script.as_dict())
        filepath = os.path.join(app.config['SCRIPT_FOLDER'], f"{run_name}.json")
        # print(filepath)
        with open(filepath, "w") as outfile:
            outfile.write(json_object)
    elif filetype == "python":
        filepath = os.path.join(app.config["SCRIPT_FOLDER"], f"{run_name}.py")

    return send_file(os.path.abspath(filepath), as_attachment=True)
    # elif filetype == "webui_data":
    #     return send_file("results/" + run_name + "_data.csv", as_attachment=True)


@app.route('/download_results/<filename>')
def download_results(filename):
    filepath = os.path.join(app.config["DATA_FOLDER"], filename)
    return send_file(os.path.abspath(filepath), as_attachment=True)


def find_instrument_by_name(name: str):
    if name.startswith("deck"):
        return eval(name)
    elif name in globals():
        return globals()[name]


def parse_deck(deck, save=None):
    # pseudo_deck = session.get('pseudo_deck', None)
    parse_dict = {}
    # TODO
    if "gui_functions" in set(dir(deck)):
        deck_variables = ["deck." + var for var in deck.gui_functions]
    else:
        deck_variables = ["deck." + var for var in set(dir(deck))
                          if not (var.startswith("_") or var[0].isupper() or var.startswith("repackage"))
                          and not type(eval("deck." + var)).__module__ == 'builtins'
                          ]
    for var in deck_variables:
        instrument = eval(var)
        functions = utils.parse_functions(instrument)
        parse_dict[var] = functions

    if deck is not None and save:
        # pseudo_deck = parse_dict
        parse_dict["deck_name"] = deck.__name__
        with open(os.path.join(app.config["DUMMY_DECK"], f"{deck.__name__}.pkl"), 'wb') as file:
            pickle.dump(parse_dict, file)
    return deck_variables


def start_gui(module, host="0.0.0.0", port=8000, debug=True):
    import sys
    global deck, off_line
    deck = sys.modules[module]
    parse_deck(deck, save=True)
    off_line = True
    socketio.run(app, host=host, port=port, debug=debug, use_reloader=False, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    # app.run(host="127.0.0.1", port=8080, debug=False)
    socketio.run(app, host="0.0.0.0", port=8000, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)
