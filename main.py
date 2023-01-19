import inspect
from flask import Flask, redirect, url_for, flash
from flask import request, render_template

app = Flask(__name__)
bool_dict = {"True": True, "False": False}

libs = set(dir())

# ---------API imports------------
from test import Test
from test_inner import TestInner

api = set(dir())
api_variables = api - libs - set(["libs"])

import_variables = set(dir())

# -----initialize functions here------
ran = Test(5)

user_variables = set(dir())
defined_variables = user_variables - import_variables - set(["import_variables"])


@app.route("/")
def index():
    return render_template('home.html')


@app.route("/controllers")
def controllers_home():
    # defined_variables = parse_globals()
    return render_template('controllers_home.html', defined_variables=defined_variables)


@app.route("/new_controller", methods=['GET', 'POST'])
def create_controller():
    if request.method == 'POST':
        module_name = request.form['api']
        inst_object = find_instrument_by_name(module_name)
        args = inspect.signature(inst_object.__init__)
        return render_template('create_controller.html', api_variables=api_variables, device=inst_object, args=args)
        # global new
        # new = inst_object(9)
        # return redirect(url_for('controllers', instrument='new'))

    return render_template('create_controller.html', api_variables=api_variables, device=None)


@app.route("/new_controller/create", methods=['GET', 'POST'])
def controllers_new():
    if request.method == 'POST':
        device = find_instrument_by_name(request.form["create"])
        device_name = request.form["name"]
        args = inspect.signature(device.__init__)
        if device_name in globals():
            return render_template('create_controller.html', api_variables=api_variables, device=device, args=args,
                                   err_msg="Invalid Name,  change to something else.")
        args = request.form.to_dict()
        args.pop("name")
        args.pop("create")
        for arg in device.__init__.__annotations__:
            if not device.__init__.__annotations__[arg].__module__ == "builtins":
                args[arg] = globals()[args[arg]]
        try:
            globals()[device_name] = device(**args)
        except Exception as e:
            return render_template('create_controller.html', api_variables=api_variables, device=device, args=args, err_msg=e)
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
            return render_template('controllers.html', instrument=instrument, functions=functions, inst=inst_object,
                                   err_msg=e)

    return render_template('controllers.html', instrument=instrument, functions=functions, inst=inst_object, err_msg='')


def find_instrument_by_name(name: str):
    if name in globals():
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
