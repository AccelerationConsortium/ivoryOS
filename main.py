import inspect
import json
import os
import csv
import sqlite3

from flask import Flask, redirect, url_for, flash, jsonify, send_file, request, render_template
from werkzeug.utils import secure_filename

# import sample_deck as deck
deck = None

# import ur_deck as deck

app = Flask(__name__)
app.config['CSV_FOLDER'] = 'config_csv/'
app.config['SCRIPT_FOLDER'] = 'scripts/'
app.secret_key = "key"

sqlite3.register_adapter(list, json.dumps)
sqlite3.register_adapter(dict, json.dumps)
con = sqlite3.connect("webapp.db", check_same_thread=False)
cursor = con.cursor()
cursor.row_factory = sqlite3.Row
cursor.execute("""create table IF NOT EXISTS workflow (name TEXT PRIMARY KEY NOT NULL, 
                    deck TEXT NOT NULL, status TEXT NOT NULL, script NOT NULL, prep NOT NULL, cleanup NOT NULL)""")


def get_db_connection():
    connect = sqlite3.connect("webapp.db")
    connect.row_factory = sqlite3.Row
    return connect


script_list = []
script_type = 'script'
stypes = ['prep', 'script', 'cleanup']
order = {'prep': [],
         'script': [],
         'cleanup': [],
         }
script_dict = {'name': '',
               'deck': '',
               'status': 'editing',
               'prep': [],
               'script': [],
               'cleanup': [],
               }
# save action to block
# in run

# script_dict = {'name': None,
#                'deck': None,
#                'status': 'editing',
#                'script': {"prep": [], "main": [], "cleanup": []}}

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
def index():
    return render_template('home.html')


@app.route("/help")
def help_info():
    return render_template('help.html')


@app.route("/controllers")
def controllers_home():
    # current_variables = set(dir())
    return render_template('controllers_home.html', defined_variables=defined_variables, deck='')


@app.route("/experiment/build/", methods=['GET', 'POST'])
@app.route("/experiment/build/<instrument>/", methods=['GET', 'POST'])
@app.route("/experiment/build/<instrument>/<action>", methods=['GET', 'POST'])
# @app.route("/experiment/build/<instrument>/<action>/<script_type>", methods=['GET', 'POST'])
def experiment_builder(instrument=None, action=None):
    global script_dict
    global order
    global script_type
    # print(script_type)
    sort_actions(script_type)
    action_parameters = None
    functions = []
    if "gui_functions" in set(dir(deck)):
        deck_variables = ["deck." + var for var in deck.gui_functions]
    else:
        deck_variables = ["deck." + var for var in set(dir(deck)) if not var.startswith("_") and not var[0].isupper()
                          and not var.startswith("repackage") and not type(eval("deck." + var)).__module__ == 'builtins']

    if instrument:
        inst_object = find_instrument_by_name(instrument)
        functions = parse_functions(inst_object)
        if action:
            if type(functions[action]) is dict:
                action_parameters = functions[action]
            else:
                action_parameters = functions[action].parameters
            if request.method == 'POST':
                args = request.form.to_dict()
                function_name = args.pop('add')
                script_type = args.pop('script_type')
                try:
                    args = convert_type(args, functions[function_name])
                except ValueError as e:
                    flash(e.__str__())
                    return redirect(url_for("experiment_builder", instrument=instrument, action=action))
                if type(functions[function_name]) is dict:
                    args = list(args.values())[0]

                # action_dict = {"id": len(script_dict['script']) + 1, "instrument": instrument, "action": function_name,
                #                "args": args}
                # order.append(str(len(script_dict['script']) + 1))
                # script_dict['script'].append(action_dict)
                action_dict = {"id": len(script_dict[script_type]) + 1, "instrument": instrument, "action": function_name,
                               "args": args}
                order[script_type].append(str(len(script_dict[script_type]) + 1))
                script_dict[script_type].append(action_dict)

    return render_template('experiment_builder.html', instrument=instrument, action=action, script_type=script_type,
                           script=script_dict, defined_variables=deck_variables, local_variables=defined_variables,
                           functions=functions, parameters=action_parameters, config=config())


@app.route("/experiment", methods=['GET', 'POST'])
@app.route("/experiment/<path:filename>", methods=['GET', 'POST'])
def experiment_run(filename=None):
    # current_variables = set(dir())
    global order
    for i in stypes:
        if len(order[i]) > 0:
            sort_actions(i)
    if deck is None and len(defined_variables) == 0:
        flash('Warning: import deck or connect instruments, go to Build Experiment tab')
        # flash('Warning: import deck or connect instruments, go to <a class="alert-link" href="/experiment/build">Build Experiment</a>')
    if request.method == "POST":
        run_name = script_dict['name']
        # if run_name is None or run_name == "None":
        #     run_name =
        repeat = request.form.get('repeat')
        try:
            exec(run_name + "_prep()")
            if filename is not None and not filename == 'None':
                df = csv.DictReader(open(os.path.join(app.config['CSV_FOLDER'], filename)))
                for _ in df:
                    exec(run_name + "_script(**i)")
            if not repeat == '' and repeat is not None:
                for i in range(int(repeat)):
                    exec(run_name + "_script()")
            exec(run_name + "_cleanup()")
            flash("Run finished")
        except Exception as e:
            flash(e)
            # break
        # return render_template('experiment_run.html', script=script_dict['script'], filename=filename)
    return render_template('experiment_run.html', script=script_dict, filename=filename)


@app.route("/my_deck")
def deck_controllers():
    global deck
    if "gui_functions" in set(dir(deck)):
        deck_variables = ["deck." + var for var in deck.gui_functions]
    else:
        deck_variables = ["deck." + var for var in set(dir(deck)) if not var.startswith("_") and not var[0].isupper()
                          and not var.startswith("repackage") and not type(eval("deck." + var)).__module__ == 'builtins']
    return render_template('controllers_home.html', defined_variables=deck_variables, deck="Deck")


@app.route("/new_controller/")
@app.route("/new_controller/<instrument>", methods=['GET', 'POST'])
def new_controller(instrument=None):
    device = None
    args = None
    if instrument:
        device = find_instrument_by_name(instrument)
        # print(inst_object)
        args = inspect.signature(device.__init__)

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
    functions = parse_functions(inst_object)

    if request.method == 'POST':
        args = request.form.to_dict()
        function_name = args.pop('action')
        function_executable = getattr(inst_object, function_name)
        try:
            args = convert_type(args, functions[function_name])
        except Exception as e:
            flash(e)
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
#todo
def delete_action(id):
    for action in script_dict[script_type]:
        if action['id'] == int(id):
            script_dict[script_type].remove(action)
    for i in order[script_type]:
        if int(i) == int(id):
            order[script_type].remove(i)
    return redirect(url_for('experiment_builder'))


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
    row = cursor.execute(f"SELECT * FROM workflow WHERE name = '{workflow_name}'").fetchone()
    script_dict = dict(zip(row.keys(), row))
    for i in stypes:
        script_dict[i] = json.loads(script_dict[i])
    return redirect(url_for('experiment_builder'))


@app.route("/delete_workflow/<workflow_name>")
def delete_workflow(workflow_name):
    global script_dict
    cursor.execute(f"Delete FROM workflow WHERE name = '{workflow_name}'")
    con.commit()
    return redirect(url_for('load_from_database'))


@app.route("/publish")
def publish():
    # cursor = con.cursor()
    global script_dict
    if script_dict['name'] == '':
        flash("Name cannot be blank")
        return redirect(url_for("experiment_builder"))
    row = cursor.execute(f"SELECT * FROM workflow WHERE name = '{script_dict['name']}'").fetchone()
    if row is not None and row["status"] == "finalized":
        flash("This is a finalized script, edit name to create a new entry")
        return redirect(url_for('experiment_builder'))
    else:
        cursor.execute("""INSERT OR REPLACE INTO workflow(name, deck, status, script, prep, cleanup)
                                    VALUES (:name,:deck, :status,:script, :prep, :cleanup);""", script_dict)
        con.commit()
    return redirect(url_for('load_from_database'))


@app.route("/finalize")
def finalize():
    # cursor = con.cursor()
    global script_dict
    script_dict['status'] = "finalized"
    return redirect(url_for('experiment_builder'))


@app.route("/database", methods=['GET', 'POST'])
@app.route("/database/<deck_name>", methods=['GET', 'POST'])
def load_from_database(deck_name=None):
    # cursor = con.cursor()]
    # deck_list = []
    if deck_name is None:
        workflows = cursor.execute("""SELECT * FROM workflow""").fetchall()
        temp = cursor.execute("""SELECT DISTINCT deck FROM workflow""")
        deck_list = [i['deck'] for i in temp]
    else:
        workflows = cursor.execute(f"""SELECT * FROM workflow WHERE deck = '{deck_name}'""").fetchall()
        deck_list = ["ALL"]
    # con.commit()
    return render_template("experiment_database.html", workflows=workflows, deck_list=deck_list)


@app.route("/edit_run_name", methods=['GET', 'POST'])
def edit_run_name():
    if request.method == "POST":
        run_name = request.form.get("run_name")
        exist_script = cursor.execute(f"""SELECT * FROM workflow WHERE name ='{run_name}'""").fetchall()
        if len(exist_script) == 0:
            script_dict['name'] = run_name
            script_dict['status'] = 'editing'
        else:
            flash("Script name is already exist in database")
        return redirect(url_for("experiment_builder"))

@app.route("/toggle_script_type/<stype>")
def toggle_script_type(stype=None):
    global script_type
    script_type = stype
    return redirect(url_for('experiment_builder'))

@app.route("/updateList", methods=['GET', 'POST'])
def update_list():
    getorder = request.form['order']
    global order
    order[script_type] = getorder.split(",", len(script_dict[script_type]))
    # print(script_list)
    return jsonify('Successfully Updated')
    # return render_template('experiment_builder.html',script=script_list)
    # return redirect(url_for('experiment_builder'))


@app.route("/configure", methods=['GET', 'POST'])
def build_run_block():
    """

    :param run_name:
    :return:
    """
    run_name = script_dict['name']
    if run_name is None or run_name == "":
        run_name = "random_for_now"
    for i in stypes:
        exec_string = "def " + run_name + "_" + i + "("
        configure = config()
        for i in configure:
            exec_string = exec_string + i + ","
        exec_string = exec_string + "):"
        exec_string = exec_string + "\n\tglobal " + run_name + "_" + i
        for action in script_dict[i]:
            instrument = action['instrument']
            args = action['args']
            action = action['action']
            if args is not None:
                if type(args) is dict:
                    temp = args.__str__()
                    for arg in args:
                        if type(args[arg]) is str and args[arg].startswith("#"):
                            temp = temp.replace("'#" + args[arg][1:] + "'", args[arg][1:])
                    exec_string = exec_string + "\n\t" + instrument + "." + action + "(**" + temp + ")"
                else:
                    if type(args) is str and args.startswith("#"):
                        args = args.replace("'#" + args[1:] + "'", args[1:])
                    exec_string = exec_string + "\n\t" + instrument + "." + action + "=" + str(args)
            else:
                exec_string = exec_string + "\n\t" + instrument + "." + action + "()"
        exec(exec_string)
    # create config_csv file
    with open("empty_configure.csv", 'w') as f:
        writer = csv.writer(f)
        writer.writerow(configure)
    with open("scripts/script.py", "w") as s:
        # TODO:
        s.write("import " + script_dict['deck'] + " as deck\n" + exec_string)
    return redirect(url_for("experiment_run"))


# --------------------handle all the import/export and download/upload--------------------------

@app.route("/import_api", methods=['GET', 'POST'])
def import_api():
    import importlib.util
    filepath = request.form.get('filepath')
    # filepath.replace('\\', '/')
    # name = request.form.get('name')
    # if name == '':
    # print(filepath)
    name = os.path.split(filepath)[-1].split('.')[0]
    # print(name)
    try:
        spec = importlib.util.spec_from_file_location(name, filepath)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        classes = inspect.getmembers(module, inspect.isclass)
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


@app.route("/import_deck", methods=['GET', 'POST'])
def import_deck():
    import importlib.util
    global script_dict
    filepath = request.form.get('filepath')
    # print(filepath)
    name = os.path.split(filepath)[-1].split('.')[0]
    # filepath.replace('\\', '/')
    try:
        spec = importlib.util.spec_from_file_location(name, filepath, )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # deck format checking
        if len([var for var in set(dir(module)) if not var.startswith("_") and not var[0].isupper() \
                                                   and not var.startswith("repackage")]) == 0:
            flash("Invalid Deck import")
            return redirect(url_for("deck_controllers"))
        globals()["deck"] = module
        if script_dict['deck'] == "" or script_dict['deck'] is None:
            script_dict['deck'] = module.__name__
    # file path error exception
    except Exception as e:
        flash(e.__str__())
    return redirect(url_for("experiment_builder"))


@app.route('/uploads/', methods=['GET', 'POST'])
def upload():
    if request.method == "POST":
        f = request.files['file']
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
        if f.filename.split('.')[-1] == "json":
            global script_dict
            script_dict = json.load(f)
        else:
            flash("Script file need to be JSON file")
    return redirect(url_for("experiment_builder"))


@app.route('/download/<filetype>')
def download(filetype):
    if filetype == "configure":
        return send_file("empty_configure.csv", as_attachment=True)
    if filetype == "script":
        sort_actions()

        json_object = json.dumps(script_dict)
        # with open(run_name + ".json", "w") as outfile:
        with open("untitled.json", "w") as outfile:
            outfile.write(json_object)
        return send_file("untitled.json", as_attachment=True)


def find_instrument_by_name(name: str):
    if name.startswith("deck"):
        return eval(name)
    elif name in globals():
        return globals()[name]


def convert_type(args, parameters, configure=[]):
    bool_dict = {"True": True, "False": False}

    if not len(args) == 0:
        for arg in args:
            if args[arg] == '' or args[arg] == "None":
                args[arg] = None
            elif args[arg] == "True" or args[arg] == "False":
                args[arg] = bool_dict[args[arg]]
            # configure parameter
            elif args[arg].startswith("#"):
                # configure_variables.append(args[arg][1:])
                # exec(args[arg][1:]+"=None")
                configure.append(args[arg][1:])
                # args[arg] = args[arg][1:]
            elif type(parameters) is inspect.Signature:
                p = parameters.parameters
                if p[arg].annotation is not inspect._empty:
                    if not type(args[arg]) == p[arg].annotation:
                        args[arg] = p[arg].annotation(args[arg])
            elif type(parameters) is dict:
                if parameters[arg] is not None:
                    if not type(args[arg]) == parameters[arg]:
                        args[arg] = parameters[arg](args[arg])
        return args


def config():
    """
    take the global script_dict
    :return: list of variable that require input
    """
    configure = []
    for action in script_dict['script']:
        args = action['args']
        if args is not None:
            if type(args) is not dict:
                if type(args) is str and args.startswith("#") and not args[1:] in configure:
                    configure.append(args[1:])
            else:
                for arg in args:
                    if type(args[arg]) is str \
                            and args[arg].startswith("#") \
                            and not args[arg][1:] in configure:
                        configure.append(args[arg][1:])
    return configure


def parse_functions(class_object=None, call=True):
    functions = {}
    for function in dir(class_object):
        if not function.startswith("_") and not function.isupper():
            # if call:
            att = getattr(class_object, function)

            # handle getter setters
            if callable(att):
                functions[function] = inspect.signature(att)
            else:
                try:
                    att = getattr(class_object.__class__, function)
                    if isinstance(att, property) and att.fset is not None:
                        functions[function] = att.fset.__annotations__
                except AttributeError:
                    pass
        # else:
        #     functions[function] = function
    return functions


def sort_actions(script_type):
    global script_dict
    global order
    if len(order[script_type]) > 0:
        for action in script_dict[script_type]:
            for i in range(len(order[script_type])):
                if action['id'] == int(order[script_type][i]):
                    # print(i+1)
                    action['id'] = i + 1
                    break
        order[script_type].sort()
        if not int(order[script_type][-1]) == len(script_dict[script_type]):
            new_order = list(range(1, len(script_dict[script_type]) + 1))
            order[script_type] = [str(i) for i in new_order]
        script_dict[script_type].sort(key=lambda x: x['id'])


# def parse_globals():
#     functions = []
#     for function in all_variables:
#         if not function.startswith("_") and not function.isupper():
#             functions.append(function)
#     return functions

# def creat_device(device, args):
#     for arg in device.__init__.__annotations__:
#         if not device.__init__.__annotations__[arg].__module__ == "builtins":
#             args[arg] = globals()[args[arg]]


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=False)
