from wtforms.fields.choices import SelectField
from wtforms.fields.core import Field
from wtforms.validators import InputRequired
from wtforms.widgets.core import TextInput

from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, HiddenField, BooleanField, IntegerField
import inspect

from ivoryos.utils.db_models import Script
from ivoryos.utils.global_config import GlobalConfig

global_config = GlobalConfig()

def find_variable(data, script):
    """
    find user defined variables and return values in the script:Script
    :param data: string of input variable name
    :param script:Script object
    """
    variables: dict[str, str] = script.get_variables()
    for variable_name, variable_type in variables.items():
        if variable_name == data:
            return data, variable_type  # variable_type int float str or "function_output"
    return None, None


class VariableOrStringField(Field):
    widget = TextInput()

    def __init__(self, label='', validators=None, script=None, **kwargs):
        super(VariableOrStringField, self).__init__(label, validators, **kwargs)
        self.script = script

    def process_formdata(self, valuelist):
        if valuelist:
            if not self.script.editing_type == "script" and valuelist[0].startswith("#"):
                raise ValueError(self.gettext("Variable is not supported in prep/cleanup"))
            self.data = valuelist[0]

    def _value(self):
        if self.script:
            variable, variable_type = find_variable(self.data, self.script)
            if variable:
                return variable

        return str(self.data) if self.data is not None else ""


class VariableOrFloatField(Field):
    widget = TextInput()

    def __init__(self, label='', validators=None, script=None, **kwargs):
        super(VariableOrFloatField, self).__init__(label, validators, **kwargs)
        self.script = script

    def _value(self):
        if self.script:
            variable, variable_type = find_variable(self.data, self.script)
            if variable:
                return variable

        if self.raw_data:
            return self.raw_data[0]
        if self.data is not None:
            return str(self.data)
        return ""

    def process_formdata(self, valuelist):
        if not valuelist:
            return
        elif valuelist[0].startswith("#"):
            if not self.script.editing_type == "script":
                raise ValueError(self.gettext("Variable is not supported in prep/cleanup"))
            self.data = valuelist[0]
            return
        try:
            if self.script:
                try:
                    variable, variable_type = find_variable(valuelist[0], self.script)
                    if variable:
                        if not variable_type == "function_output":
                            if variable_type not in ["float", "int"]:
                                raise ValueError("Variable is not a valid float")
                        self.data = variable
                        return
                except ValueError:
                    pass
            self.data = float(valuelist[0])
        except ValueError as exc:
            self.data = None
            raise ValueError(self.gettext("Not a valid float value.")) from exc


# unset_value = UnsetValue()


class VariableOrIntField(Field):
    widget = TextInput()

    def __init__(self, label='', validators=None, script=None, **kwargs):
        super(VariableOrIntField, self).__init__(label, validators, **kwargs)
        self.script = script

    def _value(self):
        if self.script:
            variable, variable_type = find_variable(self.data, self.script)
            if variable:
                return variable

        if self.raw_data:
            return self.raw_data[0]
        if self.data is not None:
            return str(self.data)
        return ""

    def process_formdata(self, valuelist):
        if not valuelist:
            return
        if self.script:
            variable, variable_type = find_variable(valuelist[0], self.script)
            if variable:
                try:
                    if not variable_type == "function_output":
                        if not variable_type == "int":
                            raise ValueError("Not a valid integer value")
                    self.data = str(variable)
                    return
                except ValueError:
                    pass
        if valuelist[0].startswith("#"):
            if not self.script.editing_type == "script":
                raise ValueError(self.gettext("Variable is not supported in prep/cleanup"))
            self.data = valuelist[0]
            return
        try:
            self.data = int(valuelist[0])
        except ValueError as exc:
            self.data = None
            raise ValueError(self.gettext("Not a valid integer value.")) from exc


class VariableOrBoolField(BooleanField):
    widget = TextInput()
    false_values = (False, "false", "", "False", "f", "F")

    def __init__(self, label='', validators=None, script=None, **kwargs):
        super(VariableOrBoolField, self).__init__(label, validators, **kwargs)
        self.script = script

    def process_data(self, value):

        if self.script:
            variable, variable_type = find_variable(value, self.script)
            if variable:
                if not variable_type == "function_output":
                    raise ValueError("Not accepting boolean variables")
                return variable

        self.data = bool(value)

    def process_formdata(self, valuelist):
        # todo
        # print(valuelist)
        if not valuelist or not type(valuelist) is list:
            self.data = False
        else:
            value = valuelist[0] if type(valuelist) is list else valuelist
            if value.startswith("#"):
                if not self.script.editing_type == "script":
                    raise ValueError(self.gettext("Variable is not supported in prep/cleanup"))
                self.data = valuelist[0]
            elif value in self.false_values:
                self.data = False
            else:
                self.data = True

    def _value(self):

        if self.script:
            variable, variable_type = find_variable(self.raw_data, self.script)
            if variable:
                return variable

        if self.raw_data:
            return str(self.raw_data[0])
        return "y"


def format_name(name):
    """Converts 'example_name' to 'Example Name'."""
    name = name.split(".")[-1]
    text = ' '.join(word for word in name.split('_'))
    return text.capitalize()


def create_form_for_method(method, autofill, script=None, design=True):
    """
    Create forms for each method or signature
    :param method: dict(docstring, signature)
    :param autofill:bool if autofill is enabled
    :param script:Script object
    :param design: if design is enabled
    """

    class DynamicForm(FlaskForm):
        pass

    annotation_mapping = {
        int: (VariableOrIntField if design else IntegerField, 'Enter integer value'),
        float: (VariableOrFloatField if design else FloatField, 'Enter numeric value'),
        str: (VariableOrStringField if design else StringField, 'Enter text'),
        bool: (VariableOrBoolField if design else BooleanField, 'Empty for false')
    }
    sig = method if type(method) is inspect.Signature else inspect.signature(method)

    for param in sig.parameters.values():
        if param.name == 'self':
            continue
        formatted_param_name = format_name(param.name)
        field_kwargs = {
            "label": formatted_param_name,
            "default": f'#{param.name}' if autofill else (param.default if param.default is not param.empty else None),
            "validators": [InputRequired()] if param.default is param.empty else None,
            **({"script": script} if (autofill or design) else {})
        }
        field_class, placeholder_text = annotation_mapping.get(
            param.annotation,
            (VariableOrStringField if design else StringField, f'Enter {param.annotation} value')
        )
        render_kwargs = {"placeholder": placeholder_text}

        # Create the field with additional rendering kwargs for placeholder text
        field = field_class(**field_kwargs, render_kw=render_kwargs)
        setattr(DynamicForm, param.name, field)

    # setattr(DynamicForm, f'add', fname)
    return DynamicForm


def create_add_form(attr, attr_name, autofill: bool, script=None, design: bool = True):
    """
    Create forms for each method or signature
    :param attr: dict(docstring, signature)
    :param attr_name: method name
    :param autofill:bool if autofill is enabled
    :param script:Script object
    :param design: if design is enabled. Design allows string input for parameter names ("#param") for all fields
    """
    signature = attr.get('signature', {})
    docstring = attr.get('docstring', "")
    dynamic_form = create_form_for_method(signature, autofill, script, design)
    if design:
        return_value = StringField(label='Save value as', render_kw={"placeholder": "Optional"})
        setattr(dynamic_form, 'return', return_value)
    hidden_method_name = HiddenField(name=f'hidden_name', description=docstring, render_kw={"value": f'{attr_name}'})
    setattr(dynamic_form, 'hidden_name', hidden_method_name)
    return dynamic_form


def create_form_from_module(sdl_module, autofill: bool = False, script=None, design: bool = False):
    """
    Create forms for each method, used for control routes
    :param sdl_module: method module
    :param autofill:bool if autofill is enabled
    :param script:Script object
    :param design: if design is enabled
    """
    method_forms = {}
    for attr_name in dir(sdl_module):
        method = getattr(sdl_module, attr_name)
        if inspect.ismethod(method) and not attr_name.startswith('_'):
            signature = inspect.signature(method)
            docstring = inspect.getdoc(method)
            attr = dict(signature=signature, docstring=docstring)
            form_class = create_add_form(attr, attr_name, autofill, script, design)
            method_forms[attr_name] = form_class()
    return method_forms


def create_form_from_pseudo(pseudo: dict, autofill: bool, script=None, design=True):
    """
    Create forms for pseudo method, used for design routes
    :param pseudo:{'dose_liquid': {
                        "docstring": "some docstring",
                        "signature": Signature(amount_in_ml: float, rate_ml_per_minute: float) }
                    }
    :param autofill:bool if autofill is enabled
    :param script:Script object
    :param design: if design is enabled
    """
    method_forms = {}
    for attr_name, signature in pseudo.items():
        # signature = info.get('signature', {})
        form_class = create_add_form(signature, attr_name, autofill, script, design)
        method_forms[attr_name] = form_class()
    return method_forms


def create_form_from_action(action: dict, script=None, design=True):
    '''
    Create forms for single action, used for design routes
    :param action: {'action': 'dose_solid', 'arg_types': {'amount_in_mg': 'float', 'bring_in': 'bool'},
                    'args': {'amount_in_mg': 5.0, 'bring_in': False}, 'id': 9,
                    'instrument': 'deck.sdl', 'return': '', 'uuid': 266929188668995}
    :param script:Script object
    :param design: if design is enabled

    '''

    arg_types = action.get("arg_types", {})
    args = action.get("args", {})
    save_as = action.get("return")

    class DynamicForm(FlaskForm):
        pass

    annotation_mapping = {
        "int": (VariableOrIntField if design else IntegerField, 'Enter integer value'),
        "float": (VariableOrFloatField if design else FloatField, 'Enter numeric value'),
        "str": (VariableOrStringField if design else StringField, 'Enter text'),
        "bool": (VariableOrBoolField if design else BooleanField, 'Empty for false')
    }

    for name, param_type in arg_types.items():
        formatted_param_name = format_name(name)
        value = args.get(name, "")
        if type(value) is dict:
            value = next(iter(value))
        field_kwargs = {
            "label": formatted_param_name,
            "default": f'{value}',
            "validators": [InputRequired()],
            **({"script": script})
        }
        param_type = param_type if type(param_type) is str else f"{param_type}"
        field_class, placeholder_text = annotation_mapping.get(
            param_type,
            (VariableOrStringField if design else StringField, f'Enter {param_type} value')
        )
        render_kwargs = {"placeholder": placeholder_text}

        # Create the field with additional rendering kwargs for placeholder text
        field = field_class(**field_kwargs, render_kw=render_kwargs)
        setattr(DynamicForm, name, field)

    if design:
        return_value = StringField(label='Save value as', default=f"{save_as}", render_kw={"placeholder": "Optional"})
        setattr(DynamicForm, 'return', return_value)
    return DynamicForm()

def create_all_builtin_forms(script):
    all_builtin_forms = {}
    for logic_name in ['if', 'while', 'variable', 'wait', 'repeat']:
        # signature = info.get('signature', {})
        form_class = create_builtin_form(logic_name, script)
        all_builtin_forms[logic_name] = form_class()
    return all_builtin_forms

def create_builtin_form(logic_type, script):
    """
    Create a builtin form {if, while, variable, repeat, wait}
    """
    class BuiltinFunctionForm(FlaskForm):
        pass

    placeholder_text = {
        'wait': 'Enter second',
        'repeat': 'Enter an integer'
    }.get(logic_type, 'Enter statement')
    description_text = {
        'variable': 'Your variable can be numbers, boolean (True or False) or text ("text")',
    }.get(logic_type, '')
    field_class = {
        'wait': VariableOrFloatField,
        'repeat': VariableOrIntField
    }.get(logic_type, VariableOrStringField)  # Default to StringField as a fallback
    field_kwargs = {
        "label": f'statement',
        "validators": [InputRequired()] if logic_type in ['wait', "variable"] else [],
        "description": description_text,
        "script": script
    }
    render_kwargs = {"placeholder": placeholder_text}
    field = field_class(**field_kwargs, render_kw=render_kwargs)
    setattr(BuiltinFunctionForm, "statement", field)
    if logic_type == 'variable':
        variable_field = StringField(label=f'variable', validators=[InputRequired()],
                                     description="Your variable name cannot include space",
                                     render_kw=render_kwargs)
        type_field = SelectField(
            'Select Input Type',
            choices=[('int', 'Integer'), ('float', 'Float'), ('str', 'String'), ('bool', 'Boolean')],
            default='str'  # Optional default value
        )
        setattr(BuiltinFunctionForm, "variable", variable_field)
        setattr(BuiltinFunctionForm, "type", type_field)
    hidden_field = HiddenField(name=f'builtin_name', render_kw={"value": f'{logic_type}'})
    setattr(BuiltinFunctionForm, "builtin_name", hidden_field)
    return BuiltinFunctionForm


def get_method_from_workflow(function_string):
    """Creates a function from a string and assigns it a new name."""

    namespace = {}
    exec(function_string, globals(), namespace)  # Execute the string in a safe namespace
    func_name = next(iter(namespace))
    # Get the function name dynamically
    return namespace[func_name]


def create_workflow_forms(script, autofill: bool = False, design: bool = False):
    workflow_forms = {}
    functions = {}
    class RegisteredWorkflows:
        pass

    deck_name = script.deck
    workflows = Script.query.filter(Script.deck==deck_name, Script.name != script.name).all()
    for workflow in workflows:
        compiled_strs = workflow.compile().get('script', "")
        method = get_method_from_workflow(compiled_strs)
        functions[workflow.name] = dict(signature=inspect.signature(method), docstring=inspect.getdoc(method))
        setattr(RegisteredWorkflows, workflow.name, method)

        form_class = create_form_for_method(method, autofill, script, design)

        hidden_method_name = HiddenField(name=f'hidden_name', description="",
                                         render_kw={"value": f'{workflow.name}'})
        if design:
            return_value = StringField(label='Save value as', render_kw={"placeholder": "Optional"})
            setattr(form_class, 'return', return_value)
        setattr(form_class, 'workflow_name', hidden_method_name)
        workflow_forms[workflow.name] = form_class()
    global_config.registered_workflows = RegisteredWorkflows
    return workflow_forms, functions


def create_action_button(script, stype=None):
    """
    Creates action buttons for design route (design canvas)
    :param script: Script object
    :param stype: script type (script, prep, cleanup)
    """
    stype = stype or script.editing_type
    variables = script.get_variables()
    return [_action_button(i, variables) for i in script.get_script(stype)]


def _action_button(action: dict, variables: dict):
    """
    Creates action button for one action
    :param action: Action dict
    :param variables: created variable dict
    """
    style = {
        "repeat": "background-color: lightsteelblue",
        "if": "background-color: salmon",
        "while": "background-color: salmon",
    }.get(action['instrument'], "")

    if action['instrument'] in ['if', 'while', 'repeat']:
        text = f"{action['action']} {action['args'].get('statement', '')}"
    elif action['instrument'] == 'variable':
        text = f"{action['action']} = {action['args'].get('statement')}"
    else:
        # regular action button
        prefix = f"{action['return']} = " if action['return'] else ""
        action_text = f"{action['instrument'].split('.')[-1] if action['instrument'].startswith('deck') else action['instrument']}.{action['action']}"
        arg_string = ""
        if action['args']:
            if type(action['args']) is dict:
                arg_list = []
                for k, v in action['args'].items():
                    if isinstance(v, dict):
                        value = next(iter(v))  # Extract the first key if it's a dict
                        # show warning color for variable calling when there is no definition
                        style = "background-color: khaki" if value not in variables.keys() else ""
                    else:
                        value = v  # Keep the original value if not a dict
                    arg_list.append(f"{k} = {value}")  # Format the key-value pair
                arg_string = "(" + ", ".join(arg_list) + ")"
            else:
                arg_string = f"= {action['args']}"
        text = f"{prefix}{action_text}  {arg_string}"
    return dict(label=text, style=style, uuid=action["uuid"], id=action["id"], instrument=action['instrument'])
