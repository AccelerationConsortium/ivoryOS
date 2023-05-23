# import inspect
import json
import os
import csv
import pickle
import traceback
import time
from flask import Flask, redirect, url_for, flash, jsonify, send_file, request, render_template, session, Response
from werkzeug.utils import secure_filename

import instruments
from utils import utils
from model import Script, User, db
from flask_login import LoginManager, login_required, login_user, logout_user
import bcrypt
from instruments import *

off_line = True
# if off_line:

app = Flask(__name__)
app.config['CSV_FOLDER'] = 'config_csv/'
app.config['SCRIPT_FOLDER'] = 'scripts/'
# basedir = os.path.abspath(os.path.dirname(__file__))

app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///project.db"

app.secret_key = "key"
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# initialize database
db.init_app(app)

with app.app_context():
    db.create_all()

deck = None
pseudo_deck = None
defined_variables = set()
api_variables = set()
if off_line:
    api_variables = dir(instruments)
    api_variables = set([i for i in api_variables if not i.startswith("_") and not i == "sys"])


@app.route("/")
@login_required
def index():
    return render_template('home.html')


def get_script_file():
    session_script = session.get("scripts")
    if session_script:
        return Script(**session_script)
    else:
        return Script(author=session.get('user'))


def post_script_file(script, is_dict=False):
    if is_dict:
        session['scripts'] = script
    else:
        session['scripts'] = script.as_dict()


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # session.query(User, User.name).all()
        user = db.session.query(User).filter(User.username == username).first()
        if user and bcrypt.checkpw(password.encode("utf-8"), user.hashPassword):
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
    return render_template('controllers_home.html', defined_variables=defined_variables, deck='')


@app.route("/experiment/build/", methods=['GET', 'POST'])
@app.route("/experiment/build/<instrument>/", methods=['GET', 'POST'])
@login_required
def experiment_builder(instrument=None):
    global pseudo_deck
    if not pseudo_deck:
        pseudo_deck = load_deck(session.get('pseudo_deck'))
    script = get_script_file()
    deck_list = utils.available_pseudo_deck()
    script.sort_actions()
    deck_variables = list(pseudo_deck.keys()) if pseudo_deck else []
    deck_variables.remove("deck_name") if len(deck_variables) > 0 else deck_variables

    functions = []
    if pseudo_deck is None:
        flash("Choose available deck below.")
        # flash(f"Make sure to import {script_dict['deck'] if script_dict['deck'] else 'deck'} for this script")
    if instrument:
        # inst_object = find_instrument_by_name(instrument)
        if instrument not in ['if', 'while', 'variable', 'wait']:
            functions = pseudo_deck[instrument]
        # current_len = len(script_dict[script_type])
        if request.method == 'POST' and "add" in request.form:

            args = request.form.to_dict()
            function_name = args.pop('add')
            script_type = args.pop('script_type', None)
            save_data = args.pop('return') if 'return' in request.form else ''
            try:
                args, arg_types = utils.convert_type(args, functions[function_name])
            except Exception:
                flash(traceback.format_exc())
                return redirect(url_for("experiment_builder", instrument=instrument))
            if type(functions[function_name]) is dict:
                args = list(args.values())[0]
                arg_types = list(arg_types.values())[0]
            if script_type:
                script.editing_type = script_type
            action = {"instrument": instrument, "action": function_name, "args": args, "return": save_data,
                      'arg_types': arg_types}
            script.add_action(action=action)

        elif request.method == 'POST':
            # handle while, if and define variables
            script_type = request.form.get('script_type', None)
            if script_type:
                script.editing_type = script_type

            statement = request.form.get('statement')

            if "if" in request.form:
                script.add_logic_action(logic_type='if', args=statement)
            if "while" in request.form:
                script.add_logic_action(logic_type='while', args=statement)
            if "variable" in request.form:
                var_name = request.form.get('variable')
                script.add_logic_action(logic_type='variable', args=statement, var_name=var_name)
            if "wait" in request.form:
                script.add_logic_action(logic_type="wait", args=statement)
        post_script_file(script)

    return render_template('experiment_builder.html', instrument=instrument, history=deck_list,
                           script=script, defined_variables=deck_variables, local_variables=defined_variables,
                           functions=functions)


@app.route("/experiment", methods=['GET', 'POST'])
@app.route("/experiment/<path:filename>", methods=['GET', 'POST'])
@login_required
def experiment_run(filename=None):
    # current_variables = set(dir())
    script = get_script_file()
    exec_string = script.compile()
    try:
        exec(exec_string)
    except Exception:
        flash("Please check syntax!!")
        return redirect(url_for("experiment_builder"))
    run_name = script.name if script.name else "untitled"
    file = open("scripts/" + run_name + ".py", "r")
    script_py = file.read()
    file.close()

    dismiss = session.get("dismiss", None)
    script = get_script_file()
    prompt = False

    script.sort_actions()

    if deck is None:
        prompt = True
    elif script.deck and not script.deck == deck.__name__:
        flash(f"This script is not compatible with current deck, import {script.deck}")
    if request.method == "POST":
        repeat = request.form.get('repeat')

        try:
            # flash("Running!")
            generate_progress(run_name, filename, repeat)
            flash("Run finished")
        except Exception as e:
            flash(e)
    return render_template('experiment_run.html', script=script.script_dict, filename=filename, dot_py=script_py,
                           # return_list=return_list,
                           history=utils.import_history(), prompt=prompt, dismiss=dismiss)


@app.route('/progress')
def progress(run_name, filename, repeat):
    return Response(generate_progress(run_name, filename, repeat), mimetype='text/event-stream')


def generate_progress(run_name, filename, repeat):
    script = get_script_file()
    exec_string = script.compile()
    # print(exec_string)
    exec(exec_string)
    output_list = []
    _, return_list = script.config_return()
    exec(run_name + "_prep()")
    if filename is not None and not filename == 'None':
        df = csv.DictReader(open(os.path.join(app.config['CSV_FOLDER'], filename)))
        for i in df:
            # todo
            # arg = convert_type(i,)
            # print(i)
            output = eval(run_name + "_script(**" + str(i) + ")")
            output_list.append(output)
            # yield f"data: {i}/{len(df)} is done"
    if not repeat == '' and repeat is not None:
        for i in range(int(repeat)):
            output = eval(run_name + "_script()")
            output_list.append(output)
            # yield f"data: {i}/{repeat} is done"
    exec(run_name + "_cleanup()")
    if len(return_list) > 0:
        with open("results/" + run_name + "_data.csv", "w", newline='') as file:
            writer = csv.DictWriter(file, fieldnames=return_list)
            writer.writeheader()
            writer.writerows(output_list)


@app.route("/experiment_preview", methods=['GET', 'POST'])
@login_required
def experiment_preview():
    # current_variables = set(dir())
    script = get_script_file()
    exec_string = script.compile()
    try:
        exec(exec_string)
    except Exception:
        flash("Please check syntax!!")
        return redirect(url_for("experiment_builder"))
    run_name = script.name if script.name else "untitled"
    file = open("scripts/" + run_name + ".py", "r")
    script_py = file.read()
    file.close()
    # _, return_list = script.config_return()

    return render_template('experiment_preview.html', script=script.script_dict, dot_py=script_py, )


@app.route("/my_deck")
@login_required
def deck_controllers():
    global deck
    deck_variables = parse_deck(deck)
    return render_template('controllers_home.html', defined_variables=deck_variables, deck="Deck",
                           history=utils.import_history())


@app.route("/new_controller/")
@app.route("/new_controller/<instrument>", methods=['GET', 'POST'])
@login_required
def new_controller(instrument=None):
    device = None
    args = None
    if instrument:
        device = find_instrument_by_name(instrument)
        # print(inst_object)
        args = utils.inspect.signature(device.__init__)

        if request.method == 'POST':
            device_name = request.form.get("device_name", None)
            if device_name and device_name in globals():
                flash("Device name is defined. Try another name, or leave it as blank to auto-configure")
                return render_template('create_controller.html', instrument=instrument, api_variables=api_variables,
                                       device=device, args=args, defined_variables=defined_variables)
            if device_name == '' or device_name in None:
                device_name = device.__name__.lower() + "_"
                num = 1
                while device_name + str(num) in globals():
                    num += 1
                device_name = device_name + str(num)
            kwargs = request.form.to_dict()
            kwargs.pop("device_name")

            for i in kwargs:
                if kwargs[i] == '' or kwargs[i] == 'None':
                    kwargs[i] = None
                else:
                    kwargs[i] = eval(kwargs[i])
            # for arg in device.__init__.__annotations__:
            #     if not device.__init__.__annotations__[arg].__module__ == "builtins":
            #         if kwargs[arg]:
            #             kwargs[arg] = globals()[kwargs[arg]]
            try:
                globals()[device_name] = device(**kwargs)
                defined_variables.add(device_name)
                return redirect(url_for('controllers_home'))
            except Exception as e:
                flash(e)
    return render_template('create_controller.html', instrument=instrument, api_variables=api_variables,
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
        # try:
        #     args = convert_type(args, functions[function_name])
        except Exception as e:
            flash(e)
            return render_template('controllers.html', instrument=instrument, functions=functions, inst=inst_object)
        if type(functions[function_name]) is dict:
            args = list(args.values())[0]
        try:
            output = ''
            if callable(function_executable):
                if args is not None:
                    output = function_executable(**args)
                else:
                    output = function_executable()
            else:  # for setter
                function_executable = args
            flash(f"{output}\nRun Success!")
        except Exception as e:
            flash(e)
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


# TODO
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
            script.update_by_uuid(uuid=uuid, args=args, output=save_as)
        session.pop('edit_action')
    return redirect(url_for('experiment_builder'))


@app.route("/edit_workflow/<workflow_name>")
@login_required
def edit_workflow(workflow_name):
    row = Script.query.get(workflow_name)
    script = Script(**row.as_dict())
    post_script_file(script)
    if not script.deck == pseudo_deck["deck_name"]:
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
    post_script_file(script)

    db.session.merge(script)
    db.session.commit()
    return redirect(url_for('experiment_builder'))


@app.route("/database/", methods=['GET', 'POST'])
@app.route("/database/<deck_name>", methods=['GET', 'POST'])
@login_required
def load_from_database(deck_name=None):
    session.pop('edit_action', None)  # reset cache
    query = Script.query
    search_term = request.args.get("keyword", None)
    print(search_term)
    # search_term = request.form.get("keyword", None)
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
    name = os.path.split(filepath)[-1].split('.')[0]
    try:
        module = utils.import_module_by_filepath(filepath=filepath, name=name)
        # deck format checking
        if not utils.if_deck_valid(module):
            flash("Invalid Deck import")
            return redirect(url_for("deck_controllers"))
        globals()["deck"] = module
        utils.save_to_history(filepath)
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
    with open('static/pseudo_deck/' + pkl_name, 'rb') as f:
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
            return redirect(url_for("experiment_run", filename=filename))
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
        if f.filename.split('.')[-1] == "json":
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
        with open("empty_configure.csv", 'w', newline='') as f:
            writer = csv.writer(f)
            cfg, cfg_types = script.config("script")

            writer.writerow(cfg)
            writer.writerow(list(cfg_types.values()))
        return send_file("empty_configure.csv", as_attachment=True)
    elif filetype == "script":
        script.sort_actions()
        json_object = json.dumps(script.as_dict())
        with open(run_name + ".json", "w") as outfile:
            outfile.write(json_object)
        return send_file(run_name + ".json", as_attachment=True)
    elif filetype == "python":
        return send_file("scripts/" + run_name + ".py", as_attachment=True)
    elif filetype == "data":
        return send_file("results/" + run_name + "_data.csv", as_attachment=True)


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
                          and not type(eval("deck." + var)).__module__ == 'builtins']
    for var in deck_variables:
        instrument = eval(var)
        functions = utils.parse_functions(instrument)
        parse_dict[var] = functions

    if deck is not None and save:
        # pseudo_deck = parse_dict
        parse_dict["deck_name"] = deck.__name__
        with open("static/pseudo_deck/" + deck.__name__ + ".pkl", 'wb') as file:
            pickle.dump(parse_dict, file)

    return deck_variables


if __name__ == "__main__":
    # app.run(host="127.0.0.1", port=8080, debug=False)
    app.run(host="0.0.0.0", port=5000)
