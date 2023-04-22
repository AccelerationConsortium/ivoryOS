# import inspect
import json
import os
import csv
import pickle
import sqlite3
import sys
import traceback

from flask import Flask, redirect, url_for, flash, jsonify, send_file, request, render_template, session
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException
from utils import utils
from utils.script import Script
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user

login_manager = LoginManager()

# import sample_deck as deck
deck = None
pseudo_deck = None
# import ur_deck as deck

app = Flask(__name__)
app.config['CSV_FOLDER'] = 'config_csv/'
app.config['SCRIPT_FOLDER'] = 'scripts/'
app.secret_key = "key"
login_manager.init_app(app)
login_manager.login_view = "login"
class User(UserMixin):
    def __init__(self, id):
        self.username = 'admin'
        self.id = id
        self.passward = "admin"


sqlite3.register_adapter(list, json.dumps)
sqlite3.register_adapter(dict, json.dumps)
con = sqlite3.connect("webapp.db", check_same_thread=False)
cursor = con.cursor()
cursor.row_factory = sqlite3.Row
# cursor.execute("""create table IF NOT EXISTS workflow (name TEXT PRIMARY KEY NOT NULL,
#                     deck TEXT NOT NULL, status TEXT NOT NULL, script NOT NULL, prep NOT NULL, cleanup NOT NULL)""")
cursor.execute("""create table IF NOT EXISTS script_library (name TEXT PRIMARY KEY NOT NULL,
                    deck TEXT NOT NULL, status TEXT NOT NULL, script_dict NOT NULL, time_created NOT NULL,
                    last_modified NOT NULL, id_order NOT NULL, editing_type NOT NULL)""")
# def get_db_connection():
#     connect = sqlite3.connect("webapp.db")
#     connect.row_factory = sqlite3.Row
#     return connect


script_type = 'script'  # set default type to be 'script'
# stypes = ['prep', 'script', 'cleanup']
script_dict, order = utils.new_script(deck.__name__ if deck else '')
dismiss = None
libs = set(dir())

# ---------API imports------------
# from test import Test
# from test_inner import TestInner

api = set(dir())
api_variables = api - libs - set(["libs"])

import_variables = set(dir())

# -----initialize functions here------
# ran = Test(TestInner('test'))

user_variables = set(dir())
defined_variables = user_variables - import_variables - set(["import_variables"])



@app.route("/")
@login_required
def index():
    return render_template('home.html')

def get_script_file():
    session_script = session.get("scripts")
    print(session_script)
    if session_script:
        return Script(**session_script)
    else:
        return Script()

def post_script_file(script):
    session['scripts'] = script.__dict__

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if password == "admin":
            user = User(username)
            login_user(user)
            session['user'] = username
            script_file = Script()
            session["script"] = script_file.__dict__

            return redirect(url_for('index'))
    return render_template('login.html')

@app.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop("scripts", None)
    return redirect(url_for('login'))

@login_manager.user_loader
def load_user(userid):
    return User(userid)


@app.route("/help")
def help_info():
    return render_template('help.html')


@app.route("/controllers")
def controllers_home():
    return render_template('controllers_home.html', defined_variables=defined_variables, deck='')


@app.route("/experiment/build/", methods=['GET', 'POST'])
@app.route("/experiment/build/<instrument>/", methods=['GET', 'POST'])
# @app.route("/experiment/build/<instrument>/<action>", methods=['GET', 'POST'])
def experiment_builder(instrument=None):
    global script_dict, order, script_type, pseudo_deck

    script_object = get_script_file()
    deck_list = utils.available_pseudo_deck()
    # utils.sort_actions(script_dict, order, script_type)
    script_object.sort_actions()
    deck_variables = list(pseudo_deck.keys()) if pseudo_deck else []

    functions = []
    if pseudo_deck is None:
        flash("Choose available deck below.")
        # flash(f"Make sure to import {script_dict['deck'] if script_dict['deck'] else 'deck'} for this script")
    if instrument:
        # inst_object = find_instrument_by_name(instrument)
        if instrument not in ['if', 'while', 'variable']:
            functions = pseudo_deck[instrument]
        # current_len = len(script_dict[script_type])
        if request.method == 'POST' and "add" in request.form:

            args = request.form.to_dict()
            function_name = args.pop('add')
            script_type = args.pop('script_type')
            save_data = args.pop('return') if 'return' in request.form else ''
            # try:
            args = utils.convert_type(args, functions[function_name])
            # except Exception:
                # flash(traceback.format_exc())
                # return redirect(url_for("experiment_builder", instrument=instrument))
            if type(functions[function_name]) is dict:
                args = list(args.values())[0]
            # action_dict = {"id": current_len + 1, "instrument": instrument, "action": function_name,
            #                "args": args, "return": save_data}
            # order[script_type].append(str(current_len + 1))
            # script_dict[script_type].append(action_dict)

            script_object.editing_type = script_type
            action = {"instrument": instrument, "action": function_name, "args": args, "return": save_data}
            script_object.add_action(action=action)

        elif request.method == 'POST':
            # handle while, if and define variables
            script_type = request.form.get('script_type')
            statement = request.form.get('statement')

            if "if" in request.form:
                args = 'True' if statement == '' else statement
                script_object.add_logic_action(logic_type='if', args=args)
            if "while" in request.form:
                args = 'False' if statement == '' else statement
                script_object.add_logic_action(logic_type='while', args=args)
            if "variable" in request.form:
                var_name = request.form.get('variable')
                args = 'None' if statement == '' else statement
                script_object.add_logic_action(logic_type='variable', args=args, var_name=var_name)

    deck_variables.remove("deck_name") if len(deck_variables) > 0 else deck_variables
    post_script_file(script_object)
    return render_template('experiment_builder.html', instrument=instrument, history=deck_list,
                           script=script_object, defined_variables=deck_variables, local_variables=defined_variables,
                           functions=functions)


@app.route("/experiment", methods=['GET', 'POST'])
@app.route("/experiment/<path:filename>", methods=['GET', 'POST'])
def experiment_run(filename=None):
    # current_variables = set(dir())
    script_object = get_script_file()
    global order, script_dict
    prompt = False
    run_name = script_object.name if script_object.name else "untitled"
    file = open("scripts/" + run_name + ".py", "r")
    script_py = file.read()
    file.close()
    _, return_list = utils.config_return(script_dict['script'])
    utils.sort_actions(script_dict, order)
    if deck is None:
        prompt = True
    elif not script_dict['deck'] == '' and not script_dict['deck'] == deck.__name__:
        flash("This script is not compatible with current deck, import ", script_dict['deck'])
    if request.method == "POST":
        repeat = request.form.get('repeat')
        output_list = []
        try:
            # flash("Running!")
            exec(run_name + "_prep()")
            if filename is not None and not filename == 'None':
                df = csv.DictReader(open(os.path.join(app.config['CSV_FOLDER'], filename)))
                for i in df:
                    # todo
                    # arg = convert_type(i,)
                    output = eval(run_name + "_script(**" + str(i) + ")")
                    output_list.append(output)
            if not repeat == '' and repeat is not None:
                for i in range(int(repeat)):
                    output = eval(run_name + "_script()")
                    output_list.append(output)
            exec(run_name + "_cleanup()")
            if len(return_list) > 0:
                with open("results/" + run_name + "_data.csv", "w", newline='') as file:
                    writer = csv.DictWriter(file, fieldnames=return_list)
                    writer.writeheader()
                    writer.writerows(output_list)
            flash("Run finished")
        except Exception as e:
            flash(e)
    return render_template('experiment_run.html', script=script_dict, filename=filename, dot_py=script_py,
                           # return_list=return_list,
                           history=utils.import_history(), prompt=prompt, dismiss=dismiss)


@app.route("/my_deck")
def deck_controllers():
    global deck
    deck_variables = parse_deck(deck)
    return render_template('controllers_home.html', defined_variables=deck_variables, deck="Deck",
                           history=utils.import_history())


@app.route("/new_controller/")
@app.route("/new_controller/<instrument>", methods=['GET', 'POST'])
def new_controller(instrument=None):
    device = None
    args = None
    if instrument:
        device = find_instrument_by_name(instrument)
        # print(inst_object)
        args = utils.inspect.signature(device.__init__)

        if request.method == 'POST':
            device_name = request.form["name"]
            if device_name == '' or device_name in globals():
                flash("Device name is NOT valid")
                return render_template('create_controller.html', instrument=instrument, api_variables=api_variables,
                                       device=device, args=args, defined_variables=defined_variables)
            kwargs = request.form.to_dict()
            kwargs.pop("name")
            for arg in device.__init__.__annotations__:
                if not device.__init__.__annotations__[arg].__module__ == "builtins":
                    kwargs[arg] = globals()[kwargs[arg]]
            try:
                globals()[device_name] = device(**kwargs)
                defined_variables.add(device_name)
                return redirect(url_for('controllers_home'))
            except Exception as e:
                flash(e)
    return render_template('create_controller.html', instrument=instrument, api_variables=api_variables,
                           device=device, args=args, defined_variables=defined_variables)


@app.route("/controllers/<instrument>", methods=['GET', 'POST'])
def controllers(instrument):
    inst_object = find_instrument_by_name(instrument)
    functions = utils.parse_functions(inst_object)

    if request.method == 'POST':
        args = request.form.to_dict()
        function_name = args.pop('action')
        function_executable = getattr(inst_object, function_name)
        args = utils.convert_type(args, functions[function_name])
        # try:
        #     args = convert_type(args, functions[function_name])
        # except Exception as e:
        #     flash(e)
        # return render_template('controllers.html', instrument=instrument, functions=functions, inst=inst_object)
        if type(functions[function_name]) is dict:
            args = list(args.values())[0]
        try:

            if callable(function_executable):
                if args is not None:
                    # print(args)
                    function_executable(**args)
                else:
                    function_executable()
            else:  # for setter
                function_executable = args
            flash("Run Success!")
        except Exception as e:
            flash(e)
    return render_template('controllers.html', instrument=instrument, functions=functions, inst=inst_object)


# -----------------------handle action editing--------------------------------------------
@app.route("/delete/<id>")
def delete_action(id):
    back = request.referrer
    script_object = get_script_file()
    script_object.delete_action(id)
    post_script_file(script_object)
    # for action in script_dict[script_type]:
    #     if action['id'] == int(id):
    #         script_dict[script_type].remove(action)
    # for i in order[script_type]:
    #     if int(i) == int(id):
    #         order[script_type].remove(i)
    # print(script_object.__dict__)
    return redirect(back)


# TODO
@app.route("/edit/<id>")
def edit_action(id):
    for action in script_dict['script']:
        if action['id'] == int(id):
            return ""
            # return redirect(url_for('experiment_builder', edit_action=action))


@app.route("/edit_workflow/<workflow_name>")
def edit_workflow(workflow_name):
    global script_dict
    global order
    row = cursor.execute(f"SELECT * FROM script_library WHERE name = '{workflow_name}'").fetchone()

    script = dict(zip(row.keys(), row))
    session['script'] = script
    return redirect(url_for('experiment_builder'))


@app.route("/delete_workflow/<workflow_name>")
def delete_workflow(workflow_name):
    global script_dict
    cursor.execute(f"Delete FROM script_library WHERE name = '{workflow_name}'")
    con.commit()
    return redirect(url_for('load_from_database'))


@app.route("/publish")
def publish():
    # cursor = con.cursor()
    global script_dict, order
    utils.sort_actions(script_dict, order)

    script =get_script_file()

    # if script_dict['name'] == "" or script_dict['deck'] == "":
    #     flash("Deck cannot be empty, try to re-submit deck configuration on the left panel")

    if not script.name or not script.deck:
        flash("Deck cannot be empty, try to re-submit deck configuration on the left panel")
    row = cursor.execute(f"SELECT * FROM script_library WHERE name = '{script_dict['name']}'").fetchone()
    # if row is not None and row["status"] == "finalized":
    if row and row["status"] == "finalized":
        flash("This is a protected script, use save as to rename.")
    else:
        # cursor.execute("""INSERT OR REPLACE INTO workflow(name, deck, status, script, prep, cleanup)
        #                             VALUES (:name,:deck, :status,:script, :prep, :cleanup);""", script_dict)
        cursor.execute('''INSERT OR REPLACE INTO script_library(name, deck, status, script_dict, time_created, last_modified, id_order, editing_type) 
                            VALUES(:name,:deck, :status,:script_dict, :time_created, :last_modified, :id_order, :editing_type);''', script.__dict__)
        con.commit()
        flash("Saved!")
    return redirect(url_for('experiment_builder'))


@app.route("/finalize")
def finalize():
    # cursor = con.cursor()
    global script_dict
    script_dict['status'] = "finalized"

    script = get_script_file()
    script.finalize()
    post_script_file(script)

    return redirect(url_for('experiment_builder'))


@app.route("/database", methods=['GET', 'POST'])
@app.route("/database/<deck_name>", methods=['GET', 'POST'])
def load_from_database(deck_name=None):
    # cursor = con.cursor()]
    # deck_list = []
    if deck_name is None:
        workflows = cursor.execute("""SELECT * FROM script_library""").fetchall()
        temp = cursor.execute("""SELECT DISTINCT deck FROM script_library""")
        deck_list = [i['deck'] for i in temp]
        # workflows = cursor.execute("""SELECT * FROM workflow""").fetchall()
        # temp = cursor.execute("""SELECT DISTINCT deck FROM workflow""")
        # deck_list = [i['deck'] for i in temp]
    else:
        workflows = cursor.execute(f"""SELECT * FROM script_library WHERE deck = '{deck_name}'""").fetchall()
        deck_list = ["ALL"]
    # con.commit()
    return render_template("experiment_database.html", workflows=workflows, deck_list=deck_list)


@app.route("/edit_run_name", methods=['GET', 'POST'])
def edit_run_name():
    if request.method == "POST":
        run_name = request.form.get("run_name")
        exist_script = cursor.execute(f"""SELECT * FROM script_library WHERE name ='{run_name}'""").fetchall()

        if len(exist_script) == 0:
            script = get_script_file()
            script.save_as(run_name)
            post_script_file(script)

            script_dict['name'] = run_name
            script_dict['status'] = 'editing'
        else:
            flash("Script name is already exist in database")
        return redirect(url_for("experiment_builder"))


@app.route("/save_as", methods=['GET', 'POST'])
def save_as():
    if request.method == "POST":
        run_name = request.form.get("run_name")
        exist_script = cursor.execute(f"""SELECT * FROM script_library WHERE name ='{run_name}'""").fetchall()
        if len(exist_script) == 0:
            script_dict['name'] = run_name
            script_dict['status'] = 'editing'

            script = get_script_file()
            script.save_as(run_name)
            post_script_file(script)

            publish()
        else:
            flash("Script name is already exist in database")
        return redirect(url_for("experiment_builder"))


@app.route("/toggle_script_type/<stype>")
def toggle_script_type(stype=None):
    # session['stype'] = stype

    script = get_script_file()
    script.editing_type = stype
    post_script_file(script)
    return redirect(url_for('experiment_builder', script=script))


@app.route("/updateList", methods=['GET', 'POST'])
def update_list():
    getorder = request.form['order']
    script = get_script_file()
    script.currently_editing_order = getorder.split(",", len(script.currently_editing_script))
    post_script_file(script)
    return jsonify('Successfully Updated')


@app.route("/configure", methods=['GET', 'POST'])
def build_run_block():
    """

    :param run_name:
    :return:
    """
    global script_dict
    global order
    utils.sort_actions(script_dict, order)
    run_name = script_dict['name'] if script_dict['name'] else "untitled"

    # flash("Define deck first")
    # return redirect(url_for("experiment_builder"))
    with open("scripts/" + run_name + ".py", "w") as s:
        if not script_dict['deck'] == '':
            s.write("import " + script_dict['deck'] + " as deck")
        else:
            s.write("deck = None")
        for i in utils.stypes:
            indent_unit = 1
            exec_string = "\n\ndef " + run_name + "_" + i + "("
            configure = utils.config(script_dict)
            if i == "script":
                for j in configure:
                    exec_string = exec_string + j + ","
            exec_string = exec_string + "):"
            exec_string = exec_string + utils.indent(indent_unit) + "global " + run_name + "_" + i

            for index, action in enumerate(script_dict[i]):
                instrument = action['instrument']
                args = action['args']
                save_data = action['return']
                action = action['action']
                next_ = None
                if instrument == 'if':

                    if index < (len(script_dict[i]) - 1):
                        next_ = script_dict[i][index + 1]
                    if action == 'if':
                        exec_string = exec_string + utils.indent(indent_unit) + "if " + args + ":"
                        indent_unit += 1
                        if next_ and next_['instrument'] == 'if':
                            exec_string = exec_string + utils.indent(indent_unit) + "pass"
                    elif action == 'else':
                        exec_string = exec_string + utils.indent(indent_unit - 1) + "else:"
                        if next_['instrument'] == 'if' and next_['action'] == 'endif':
                            exec_string = exec_string + utils.indent(indent_unit) + "pass"
                    else:
                        indent_unit -= 1
                elif instrument == 'while':

                    if index < (len(script_dict[i]) - 1):
                        next_ = script_dict[i][index + 1]
                    if action == 'while':
                        exec_string = exec_string + utils.indent(indent_unit) + "while " + args + ":"
                        indent_unit += 1
                        if next_ and next_['instrument'] == 'while':
                            exec_string = exec_string + utils.indent(indent_unit) + "pass"
                        # else:
                        #     indent = "\t"
                    elif action == 'endwhile':
                        indent_unit -= 1
                elif instrument == 'variable':
                    # args = "False" if args == '' else args
                    exec_string = exec_string + utils.indent(indent_unit) + action + " = " + args
                else:
                    if args is not None:
                        if type(args) is dict:
                            temp = args.__str__()
                            for arg in args:
                                if type(args[arg]) is str and args[arg].startswith("#"):
                                    temp = temp.replace("'#" + args[arg][1:] + "'", args[arg][1:])
                            single_line = instrument + "." + action + "(**" + temp + ")"
                        else:
                            if type(args) is str and args.startswith("#"):
                                args = args.replace("'#" + args[1:] + "'", args[1:])
                            single_line = instrument + "." + action + " = " + str(args)
                    else:
                        single_line = instrument + "." + action + "()"
                    if save_data == '':
                        exec_string = exec_string + utils.indent(indent_unit) + single_line
                    else:
                        exec_string = exec_string + utils.indent(indent_unit) + save_data + " = " + single_line
            return_str, return_list = utils.config_return(script_dict[i])
            if len(return_list) > 0:
                exec_string += utils.indent(indent_unit) + return_str
            try:
                exec(exec_string)
            except Exception as e:
                # flash(e.__str__())
                flash("Please check syntax!!")
                return redirect(url_for("experiment_builder"))
            s.write(exec_string)
    # create config_csv file
    with open("empty_configure.csv", 'w') as f:
        writer = csv.writer(f)
        writer.writerow(configure)

    return redirect(url_for("experiment_run"))


# --------------------handle all the import/export and download/upload--------------------------
@app.route("/clear")
def clear():
    if deck:
        deck_name = deck.__name__
    elif pseudo_deck:
        deck_name = pseudo_deck["deck_name"]
    else:
        deck_name = ''
    script = Script(deck=deck_name)
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


@app.route("/import_deck", methods=['POST'])
def import_deck():
    global script_dict, deck, dismiss, pseudo_deck
    filepath = request.form.get('filepath')
    dismiss = request.form.get('dismiss')
    update = request.form.get('update')
    back = request.referrer
    if dismiss:
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

        if script_dict['deck'] == "" or script_dict['deck'] is None:
            script_dict['deck'] = module.__name__
    # file path error exception
    except Exception as e:
        flash(e.__str__())
    # return redirect(url_for("experiment_builder"))
    return redirect(back)


@app.route("/import_pseudo", methods=['POST'])
def import_pseudo():
    global pseudo_deck
    pkl_name = request.form.get('pkl_name')
    script = get_script_file()
    try:
        with open('static/pseudo_deck/' + pkl_name, 'rb') as f:
            pseudo_deck = pickle.load(f)
        # if script_dict['deck'] == "" or script_dict['deck'] is None or \
        #         not (script_dict['script'] and script_dict['prep'] and script_dict['cleanup']):
        if script.deck is None or script.isEmpty():
            script.deck = pkl_name.split('.')[0]
        elif script.deck and not script.deck == pkl_name.split('.')[0]:
            flash(f"Choose the deck with name {script.deck}")
    # file path error exception
    except Exception:
        flash(traceback.format_exc())
    post_script_file(script)
    return redirect(url_for("experiment_builder"))


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
            global script_dict
            script_dict = json.load(f)
        else:
            flash("Script file need to be JSON file")
    return redirect(url_for("experiment_builder"))


@app.route('/download/<filetype>')
def download(filetype):
    run_name = script_dict['name'] if script_dict['name'] else "untitled"
    if filetype == "configure":
        return send_file("empty_configure.csv", as_attachment=True)
    elif filetype == "script":
        utils.sort_actions(script_dict, order)
        json_object = json.dumps(script_dict)
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
    global pseudo_deck
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
    app.run(host="127.0.0.1", port=8080, debug=False)
