import inspect
import os

from flask import Flask, redirect, url_for, flash, jsonify, send_from_directory, current_app, send_file
from flask import request, render_template
from werkzeug.utils import secure_filename

# import sample_deck as deck
deck = None
import csv

# import ur_deck

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'csv/'
app.secret_key = "key"

script_list = []
order = []
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


@app.route("/controllers")
def controllers_home():
    # current_variables = set(dir())
    return render_template('controllers_home.html', defined_variables=defined_variables, deck='')


@app.route('/uploads/', methods=['GET', 'POST'])
def upload():
    if request.method == "POST":
        f = request.files['file']
        if f.filename.split('.')[-1] == "csv":

            filename = secure_filename(f.filename)
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return redirect(url_for("experiment_run", filename=filename))
    # return send_from_directory(directory=uploads, filename=filename)


@app.route('/download')
def download():
    return send_file("empty_configure.csv", as_attachment=True)


@app.route("/delete/<id>")
def delete_action(id):
    for action in script_list:
        if action['id'] == int(id):
            script_list.remove(action)
    for i in order:
        if int(i) == int(id):
            order.remove(i)
    return redirect(url_for('experiment_builder'))


@app.route("/experiment/build/", methods=['GET', 'POST'])
@app.route("/experiment/build/<instrument>/", methods=['GET', 'POST'])
@app.route("/experiment/build/<instrument>/<action>", methods=['GET', 'POST'])
def experiment_builder(instrument=None, action=None):
    # current_variables = set(dir())
    # inst_object = find_instrument_by_name(instrument)
    # functions = parse_functions(inst_object)
    global script_list
    global order
    sort_actions()
    # print(script_list)
    deck_variables = ["deck." + var for var in set(dir(deck)) if not var.startswith("_") and not var[0].isupper()]
    if instrument:
        inst_object = find_instrument_by_name(instrument)
        functions = parse_functions(inst_object)
        if action:
            if type(functions[action]) is dict:
                action_parameters = functions[action]
            else:
                action_parameters = functions[action].parameters
            if request.method == 'POST':
                # sort_actions(script_list, order)

                args = request.form.to_dict()
                function_name = args.pop('add')
                try:
                    args = convert_type(args, functions[function_name])
                except Exception as e:
                    flash(e)
                    return render_template('experiment_builder.html', defined_variables=deck_variables,
                                       local_variables=defined_variables,
                                       functions=functions, parameters=action_parameters, instrument=instrument,
                                       action=action, script=script_list, config=config())
                if type(functions[function_name]) is dict:
                    args = list(args.values())[0]
                action_dict = {"id": len(script_list) + 1, "instrument": instrument, "action": function_name,
                               "args": args}
                order.append(str(len(script_list) + 1))
                script_list.append(action_dict)
                # configure = config()
                return render_template('experiment_builder.html', defined_variables=deck_variables,
                                       local_variables=defined_variables,
                                       functions=functions, parameters=action_parameters, instrument=instrument,
                                       action=action, script=script_list, config=config())
            return render_template('experiment_builder.html', defined_variables=deck_variables,
                                   local_variables=defined_variables,
                                   functions=functions, parameters=action_parameters, instrument=instrument,
                                   action=action, script=script_list, config=config())
        else:
            return render_template('experiment_builder.html', defined_variables=deck_variables,
                                   local_variables=defined_variables,
                                   functions=functions, instrument=instrument, script=script_list, config=config())
        return render_template('experiment_builder.html', defined_variables=deck_variables,
                               local_variables=defined_variables)
    return render_template('experiment_builder.html', defined_variables=deck_variables,
                           local_variables=defined_variables, script=script_list, config=config())


@app.route("/updateList", methods=['GET', 'POST'])
def update_list():
    getorder = request.form['order']
    global order
    order = getorder.split(",", len(script_list))
    # print(script_list)
    return jsonify('Successfully Updated')
    # return render_template('experiment_builder.html',script=script_list)
    # return redirect(url_for('experiment_builder'))

@app.route("/import_api/<filepath>", methods=['GET', 'POST'])
def import_api(filepath):
    import importlib.util
    filepath = request.form.get('filepath')
    name = request.form.get('name')
    if name == '':
        name = filepath.split('/')[-1].split('.')[0]
    spec = importlib.util.spec_from_file_location(name, filepath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    globals()[name] = module


@app.route("/import_deck", methods=['GET', 'POST'])
def import_deck():
    import importlib.util
    filepath = request.form.get('filepath')
    filepath.replace('\\', '/')
    print(filepath)
    # name = request.form.get('name')
    # if name == '':
    #     name = filepath.split('/')[-1].split('.')[0]
    spec = importlib.util.spec_from_file_location("deck", filepath, )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    globals()["deck"] = module
    # spec.loader.exec_module(module)

    return redirect(url_for("deck_controllers"))


@app.route("/configure", methods=['GET', 'POST'])
def build_run_block(run_name=None):
    if run_name is None:
        run_name = "random_for_now"
    exec_string = "def " + run_name + "("
    configure = config()
    for i in configure:
        exec_string = exec_string + i + ","
    exec_string = exec_string + "):"
    exec_string = exec_string + "\n\tglobal " + run_name
    for action in script_list:
        instrument = action['instrument']
        # inst_object = find_instrument_by_name(instrument)
        args = action['args']
        # args = convert_type(args, functions[selected_function].parameters)
        action = action['action']
        # function = getattr(inst_object, action)
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
                exec_string = exec_string + "\n\t" + instrument + "." + action + "=" + args
        else:
            exec_string = exec_string + "\n\t" + instrument + "." + action + "()"
    # print(script_list)
    exec(exec_string)
    with open("empty_configure.csv", 'w') as f:
        writer = csv.writer(f)
        writer.writerow(configure)
    return redirect(url_for("experiment_run"))


@app.route("/experiment", methods=['GET', 'POST'])
@app.route("/experiment/<path:filename>", methods=['GET', 'POST'])
def experiment_run(filename=None):
    # current_variables = set(dir())
    if len(order) > 0:
        sort_actions()
    if request.method == "POST":
        run_name = "random_for_now"
        repeat = request.form.get('repeat')
        if filename is not None and not filename == 'None':
            df = csv.DictReader(open(os.path.join(app.config['UPLOAD_FOLDER'], filename)))
            for i in df:
                exec(run_name + "(**i)")
        if not repeat == '' and repeat is not None:
            for i in range(int(repeat)):
                try:
                    exec(run_name + "()")
                except Exception as e:
                    flash(e)
                    break
        # print(exec_string)

        return render_template('experiment_run.html', script=script_list, filename=filename)
    return render_template('experiment_run.html', script=script_list, filename=filename)


@app.route("/my_deck")
def deck_controllers():
    current_variables = ["deck." + var for var in set(dir(deck)) if not var.startswith("_") and not var[0].isupper()]
    return render_template('controllers_home.html', defined_variables=current_variables, deck="Deck")


@app.route("/new_controller", methods=['GET', 'POST'])
def create_controller():
    if request.method == 'POST':
        module_name = request.form['api']
        inst_object = find_instrument_by_name(module_name)
        args = inspect.signature(inst_object.__init__)
        return render_template('create_controller.html', api_variables=api_variables,
                               device=inst_object, args=args, defined_variables=defined_variables)
    return render_template('create_controller.html', api_variables=api_variables,
                           device=None, defined_variables=defined_variables)


@app.route("/new_controller/create", methods=['GET', 'POST'])
def controllers_new():
    if request.method == 'POST':
        device = find_instrument_by_name(request.form["create"])
        device_name = request.form["name"]
        args = inspect.signature(device.__init__)
        if device_name == '' or device_name in globals():
            flash("Device name is NOT valid")
            return render_template('create_controller.html', api_variables=api_variables, device=device, args=args)
        args = request.form.to_dict()
        args.pop("name")
        args.pop("create")
        for arg in device.__init__.__annotations__:
            if not device.__init__.__annotations__[arg].__module__ == "builtins":
                args[arg] = globals()[args[arg]]
        try:
            globals()[device_name] = device(**args)
            defined_variables.add(device_name)
        except Exception as e:
            return render_template('create_controller.html', api_variables=api_variables, device=device, args=args,
                                   err_msg=e)
        return redirect(url_for('controllers_home', defined_variables=defined_variables, deck=''))
    return render_template('create_controller.html', api_variables=api_variables, device=None)


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
            return render_template('controllers.html', instrument=instrument, functions=functions, inst=inst_object)
        if type(functions[function_name]) is dict:
            args = list(args.values())[0]
        try:
            if callable(function_executable):
                if args is not None:
                    function_executable(**args)
                else:
                    function_executable()
            else:   # for setter
                function_executable = args
            flash("Run Success!")
        except Exception as e:
            flash(e)
            # return render_template('controllers.html', instrument=instrument, functions=functions, inst=inst_object)
    return render_template('controllers.html', instrument=instrument, functions=functions, inst=inst_object)


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
            elif type(parameters) is not dict:
                parameters = parameters.paramenters
                if parameters[arg].annotation is not inspect._empty:
                    if not type(args[arg]) == parameters[arg].annotation:
                        args[arg] = parameters[arg].annotation(args[arg])
            elif type(parameters) is dict:
                if parameters[arg] is not None:
                    if not type(args[arg]) == parameters[arg]:
                        args[arg] = parameters[arg](args[arg])
        return args


def config():
    configure = []
    for action in script_list:
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
            if call:
                att = getattr(class_object, function)

                # handle getter setters
                if callable(att):
                    functions[function] = inspect.signature(att)
                else:
                    try:
                        att = getattr(class_object.__class__, function)
                        if isinstance(att, property) and att.fset is not None:
                            functions[function] = att.fset.__annotations__
                    except:
                        pass
            else:
                functions[function] = function
    return functions


def sort_actions():
    global script_list
    global order
    if len(order) > 0:
        for action in script_list:
            for i in range(len(order)):
                if action['id'] == int(order[i]):
                    # print(i+1)
                    action['id'] = i + 1
                    break
        order.sort()
        if not int(order[-1]) == len(script_list):
            new_order = list(range(1, len(script_list) + 1))
            order = [str(i) for i in new_order]
        script_list.sort(key=sort_by_id)


def sort_by_id(dict):
    return dict['id']


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
    app.run(host="127.0.0.1", port=8080, debug=True)
