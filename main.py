import inspect
from flask import Flask, redirect, url_for, flash, jsonify
from flask import request, render_template
import sample_deck as deck

app = Flask(__name__)
app.secret_key = "key"
bool_dict = {"True": True, "False": False}
script_list = []

libs = set(dir())


# ---------API imports------------
from test import Test
from test_inner import TestInner

api = set(dir())
api_variables = api - libs - set(["libs"])

import_variables = set(dir())

# -----initialize functions here------
ran = Test(TestInner('test'))

user_variables = set(dir())
defined_variables = user_variables - import_variables - set(["import_variables"])


@app.route("/")
def index():
    return render_template('home.html')


@app.route("/controllers")
def controllers_home():
    # current_variables = set(dir())
    return render_template('controllers_home.html', defined_variables=defined_variables)


@app.route("/experiment/build/", methods=['GET', 'POST'])
@app.route("/experiment/build/<instrument>/", methods=['GET', 'POST'])
@app.route("/experiment/build/<instrument>/<action>", methods=['GET', 'POST'])
def experiment_builder(instrument=None, action=None):
    # current_variables = set(dir())
    # inst_object = find_instrument_by_name(instrument)
    # functions = parse_functions(inst_object)
    # script_list.sort(key=sort_by_id)
    # print(script_list)
    deck_variables = ["deck." + var for var in set(dir(deck)) if not var.startswith("_") and not var[0].isupper()]
    if instrument:
        inst_object = find_instrument_by_name(instrument)
        functions = parse_functions(inst_object)
        if action:
            action_parameters = functions[action].parameters
            if request.method == 'POST':
                args = request.form.to_dict()
                selected_function = args.pop('add')
                args = convert_type(args, functions[selected_function].parameters)
                action_dict = {"id":len(script_list)+1, "action": selected_function, "args": args}
                script_list.append(action_dict)
                return render_template('experiment_builder.html', defined_variables=deck_variables,
                                       local_variables=defined_variables,
                                       functions=functions, parameters=action_parameters, instrument=instrument,
                                       action=action, script=script_list)
            return render_template('experiment_builder.html', defined_variables=deck_variables,
                                   local_variables=defined_variables,
                                   functions=functions, parameters=action_parameters, instrument=instrument,
                                   action=action, script=script_list)
        else:
            return render_template('experiment_builder.html', defined_variables=deck_variables,
                                   local_variables=defined_variables,
                                   functions=functions, instrument=instrument, script=script_list)
        return render_template('experiment_builder.html', defined_variables=deck_variables,
                               local_variables=defined_variables)
    return render_template('experiment_builder.html', defined_variables=deck_variables,
                           local_variables=defined_variables, script=script_list)


@app.route("/updateList", methods=['GET', 'POST'])
def update_list():
    getorder = request.form['order']
    order = getorder.split(",", len(script_list))
    print(order)
    for action in script_list:
        for i in range(len(script_list)):
            if action['id']==int(order[i]):
                print(i+1)
                action['id']=i+1
    #     print(script_list[i]['id'])
    # print(script_list)
    # print(script_list)
    return jsonify('Successfully Updated')
    # return render_template('experiment_builder.html',script=script_list)
    # return redirect(url_for('experiment_builder'))


@app.route("/saveList", methods=['GET', 'POST'])
def save_list():
    return ''
@app.route("/experiment")
def experiment_run():
    # current_variables = set(dir())
    script_list.sort(key=sort_by_id)
    print(script_list)

    return render_template('experiment_run.html', script=script_list)


@app.route("/my_deck")
def deck_controllers():
    current_variables = ["deck." + var for var in set(dir(deck)) if not var.startswith("_") and not var[0].isupper()]
    return render_template('controllers_home.html', defined_variables=current_variables)


@app.route("/new_controller", methods=['GET', 'POST'])
def create_controller():
    if request.method == 'POST':
        module_name = request.form['api']
        inst_object = find_instrument_by_name(module_name)
        args = inspect.signature(inst_object.__init__)
        return render_template('create_controller.html', api_variables=api_variables, device=inst_object, args=args)
    return render_template('create_controller.html', api_variables=api_variables, device=None)


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
        return redirect(url_for('controllers', instrument=device_name))
    return render_template('create_controller.html', api_variables=api_variables, device=None)


@app.route("/controllers/<instrument>", methods=['GET', 'POST'])
def controllers(instrument):
    inst_object = find_instrument_by_name(instrument)
    functions = parse_functions(inst_object)

    if request.method == 'POST':
        args = request.form.to_dict()
        selected_function = args.pop('action')
        function = getattr(inst_object, selected_function)
        args = convert_type(args, functions[selected_function].parameters)
        try:
            if args is not None:
                function(**args)
            else:
                function()
        except Exception as e:
            flash(e)
            return render_template('controllers.html', instrument=instrument, functions=functions, inst=inst_object,
                                   err_msg=e)
        flash("Run Success!")
    return render_template('controllers.html', instrument=instrument, functions=functions, inst=inst_object, err_msg='')




def find_instrument_by_name(name: str):
    if name.startswith("deck"):
        return eval(name)
    elif name in globals():
        return globals()[name]


def convert_type(args, parameters):
    if not len(args) == 0:
        for arg in args:
            if args[arg] == '' or args[arg] == "None":
                args[arg] = None
            elif args[arg] == "True" or args[arg] == "False":
                args[arg] = bool_dict[args[arg]]
            elif parameters[arg].annotation is not inspect._empty:
                if not type(args[arg]) == parameters[arg].annotation:
                    args[arg] = parameters[arg].annotation(args[arg])
        return args


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
                functions[function] = function
    return functions


def sort_actions(script_list):
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
