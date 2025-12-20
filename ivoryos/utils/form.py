from enum import Enum, EnumMeta
from typing import Union, Any
try:
    from typing import get_origin, get_args
except ImportError:
    # For Python versions = 3.7, use typing_extensions
    from typing_extensions import get_origin, get_args

from wtforms.fields.choices import SelectField
from wtforms.fields.core import Field
from wtforms.validators import InputRequired, ValidationError, Optional
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
        # print("_value", self.data, type(self.data))
        return str(self.data) if self.data else ''


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
        if valuelist[0] == "":
            # print("empty input", valuelist)
            self.data = None
            return
        try:
            self.data = int(valuelist[0])
        except ValueError as exc:
            self.data = None
            raise ValueError(self.gettext("Not a valid integer value.")) from exc


class VariableOrBoolField(Field):
    widget = TextInput()
    false_values = (False, "false", "", "False", "f", "F", "n")

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
        if isinstance(value, str) and value.startswith("#"):
            self.data = value
            return value
        if value in self.false_values:
            self.data = False
        else:
            self.data = True
        return None

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
        return str(self.data)


class FlexibleEnumField(StringField):
    def __init__(self, label=None, validators=None, choices=None, script=None, **kwargs):
        super().__init__(label, validators, **kwargs)
        self.script = script
        self.enum_class = self._resolve_enum(choices)
        self.choices = [e.name for e in self.enum_class]
        # self.value_list = [e.name for e in self.enum_class]

    def _resolve_enum(self, annotation):
        """Extract Enum from Enum or Optional[Enum]"""
        # Case: direct Enum
        if isinstance(annotation, EnumMeta):
            return annotation

        # Case: Optional / Union
        origin = get_origin(annotation)
        if origin is Union:
            for arg in get_args(annotation):
                if isinstance(arg, EnumMeta):
                    return arg

        raise TypeError(f"FlexibleEnumField expected Enum or Optional[Enum], got {annotation!r}")

    def process_formdata(self, valuelist):
        # todo right now enum types will be processed to methods as a str, so the method must convert to the enum type
        if valuelist:
            key = valuelist[0]
            # Treat empty string or "None" as null value
            if key in ("", None, "None"):
                self.data = None
                return

            if key in self.choices:
                # Convert the string key to Enum instance
                self.data = self.enum_class[key].value
            elif key.startswith("#"):
                if not self.script.editing_type == "script":
                    raise ValueError(self.gettext("Variable is not supported in prep/cleanup"))
                self.data = key
            else:
                raise ValidationError(
                    f"Invalid choice: '{key}'. Must match one of {list(self.enum_class.__members__.keys())}")



def parse_annotation(annotation):
    """
    Given a type annotation, return:
    - a list of all valid types (excluding NoneType)
    - a boolean indicating if the value can be None (optional)
    """
    origin = get_origin(annotation)
    args = get_args(annotation)

    if annotation is Any:
        return [str], True  # fallback: accept any string, optional

    if origin is Union:
        types = list(set(args))
        is_optional = type(None) in types
        non_none_types = [t for t in types if t is not type(None)]
        return non_none_types, is_optional

    # Not a Union, just a regular type
    return [annotation], False

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
        # formatted_param_name = format_name(param.name)

        default_value = None
        if autofill:
            default_value = f'#{param.name}'
        else:
            if param.default is not param.empty:
                if isinstance(param.default, Enum):
                    default_value = param.default.name
                else:
                    default_value = param.default

        field_kwargs = {
            "label": param.name,
            "default": default_value,
            "validators": [InputRequired()] if param.default is param.empty else [Optional()],
            **({"script": script} if (autofill or design) else {})
        }
        if _is_enum_type(param.annotation):
            enum_class = _unwrap_enum_type(param.annotation)
            field_class = FlexibleEnumField
            placeholder_text = f"Choose or type a value for {enum_class.__name__} (start with # for custom)"

            extra_kwargs = {"choices": param.annotation}

        else:
            # print(param.annotation)
            annotation, optional = parse_annotation(param.annotation)
            annotation = annotation[0]
            field_class, placeholder_text = annotation_mapping.get(
                annotation,
                (VariableOrStringField if design else StringField, f'Enter {param.annotation} value')
            )
            extra_kwargs = {}
            if optional:
                field_kwargs["filters"] = [lambda x: x if x != '' else None]

            if annotation is bool:
                # Boolean fields should not use InputRequired
                field_kwargs["validators"] = []  # or [Optional()]
            else:
                field_kwargs["validators"] = [InputRequired()] if param.default is param.empty else [Optional()]

        render_kwargs = {"placeholder": placeholder_text}

        # Create the field with additional rendering kwargs for placeholder text
        field = field_class(**field_kwargs, render_kw=render_kwargs, **extra_kwargs)
        setattr(DynamicForm, param.name, field)

    # setattr(DynamicForm, f'add', fname)
    return DynamicForm


def _is_enum_type(tp):
    # Optional[Enum] comes through as Union[Enum, NoneType]
    origin = get_origin(tp)

    # Non-Optional direct enum
    if isinstance(tp, type) and issubclass(tp, Enum):
        return True

    # Optional/Union case → unwrap inner types
    if origin is Union:
        return any(
            isinstance(arg, type) and issubclass(arg, Enum)
            for arg in get_args(tp)
            if arg is not type(None)
        )

    return False

def _unwrap_enum_type(tp):
    from typing import get_origin, get_args, Union
    from enum import Enum

    # Bare Enum
    if isinstance(tp, type) and issubclass(tp, Enum):
        return tp

    # Optional/Union conversion
    origin = get_origin(tp)
    if origin is Union:
        for arg in get_args(tp):
            if arg is not type(None) and isinstance(arg, type) and issubclass(arg, Enum):
                return arg

    return None

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
    return_type = signature.return_annotation
    # print(signature, docstring)
    dynamic_form = create_form_for_method(signature, autofill, script, design)
    if design:
        if return_type is not None:
            return_value = StringField(label='Save value as', render_kw={"placeholder": "Optional"})
            setattr(dynamic_form, 'return', return_value)
        batch_action = BooleanField(label='Batch Action', render_kw={"placeholder": "Optional"})
        setattr(dynamic_form, 'batch_action', batch_action)
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
        try:
            method = getattr(sdl_module, attr_name)
            if inspect.ismethod(method) and not attr_name.startswith('_'):
                signature = inspect.signature(method)
                docstring = inspect.getdoc(method)
                attr = dict(signature=signature, docstring=docstring)
                form_class = create_add_form(attr, attr_name, autofill, script, design)
                method_forms[attr_name] = form_class()
        except Exception as e:
            print(f"Error creating form for {attr_name}: {e}")
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
    for attr_name, info in pseudo.items():
        # Handle properties (getter/setter)
        if isinstance(info, dict) and info.get('is_property'):
            # Getter
            form_class = create_add_form(info, attr_name, autofill, script, design)
            method_forms[attr_name] = form_class()
            
            # Setter
            if info.get('has_setter'):
                setter_name = f"{attr_name}_(setter)"
                sig = info.get('signature')
                # Infer type from getter return annotation if available
                param_type = inspect._empty
                if sig and sig.return_annotation is not inspect._empty:
                    param_type = sig.return_annotation
                
                # Create a synthetic signature for the setter: (value: type)
                setter_sig = inspect.Signature(
                    parameters=[inspect.Parameter('value', inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=param_type)],
                    return_annotation=None
                )
                
                setter_info = {
                    'signature': setter_sig,
                    'docstring': f"Set {attr_name}"
                }
                form_class_setter = create_add_form(setter_info, setter_name, autofill, script, design)
                method_forms[setter_name] = form_class_setter()
        else:
            # Regular method
            # signature = info.get('signature', {})
            form_class = create_add_form(info, attr_name, autofill, script, design)
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
    instrument = action.get("instrument")

    class DynamicForm(FlaskForm):
        pass

    annotation_mapping = {
        "int": (VariableOrIntField if design else IntegerField, 'Enter integer value'),
        "float": (VariableOrFloatField if design else FloatField, 'Enter numeric value'),
        "str": (VariableOrStringField if design else StringField, 'Enter text'),
        "bool": (VariableOrBoolField if design else BooleanField, 'Empty for false')
    }

    for name, param_type in arg_types.items():
        # formatted_param_name = format_name(name)
        value = args.get(name, "")
        if type(value) is dict and value:
            value = next(iter(value))
        if value in (None, "", "None"):
            value = None

        field_kwargs = {
            "label": name,
            "default": value,
            # todo get optional/required from snapshot
            "validators": [],
            "filters": [lambda x: x if x != '' else None],
            **({"script": script})
        }
        if type(param_type) is list:
            none_type = param_type[1]
            if none_type == "NoneType":
                param_type = param_type[0]
        param_type = param_type if type(param_type) is str else f"{param_type}"
        field_class, placeholder_text = annotation_mapping.get(
            param_type,
            (VariableOrStringField if design else StringField, f'Enter {param_type} value')
        )

        if instrument == "math_variable":
            field_class = VariableOrStringField
            placeholder_text = "Enter math expression"
            field_kwargs["validators"] = [InputRequired()]


        render_kwargs = {"placeholder": placeholder_text}

        # Create the field with additional rendering kwargs for placeholder text
        field = field_class(**field_kwargs, render_kw=render_kwargs)
        setattr(DynamicForm, name, field)

    if design:
        if "batch_action" in action:
            batch_action = BooleanField(label='Batch Action', default=bool(action["batch_action"]))
            setattr(DynamicForm, 'batch_action', batch_action)
        return_value = StringField(label='Save value as', default=f"{save_as}", render_kw={"placeholder": "Optional"})
        setattr(DynamicForm, 'return', return_value)
    return DynamicForm()

def create_all_builtin_forms(script):
    all_builtin_forms = {}
    for logic_name in ['if', 'while', 'variable', 'input', 'wait', 'repeat', 'pause', 'math', 'comment']:
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
        'repeat': 'Enter an integer',
        'pause': 'Human Intervention Message',
        'comment': 'Enter comment to log',
        'input': 'Enter prompt message',
        'math': 'Enter math expression, e.g. #x + 5 * (#y - 2)'
    }.get(logic_type, 'Enter statement')
    description_text = {
        'variable': 'Your variable can be numbers, boolean (True or False) or text ("text")',
        'math': "Enter a math expression using #variables, numbers, or returned variables",
    }.get(logic_type, '')
    field_class = {
        'wait': VariableOrFloatField,
        'repeat': VariableOrIntField,
    }.get(logic_type, VariableOrStringField)  # Default to StringField as a fallback
    field_kwargs = {
        "label": f'statement',
        "validators": [InputRequired()] if logic_type in ['wait', "variable", "math"] else [],
        "description": description_text,
        "script": script
    }
    render_kwargs = {"placeholder": placeholder_text}
    field = field_class(**field_kwargs, render_kw=render_kwargs)
    setattr(BuiltinFunctionForm, "statement", field)
    if logic_type == 'variable':
        variable_field = VariableOrStringField(label=f'variable', validators=[InputRequired()],
                                     description="Your variable name cannot include space",
                                     render_kw=render_kwargs, script=script)
        type_field = SelectField(
            'Select Input Type',
            choices=[('int', 'Integer'), ('float', 'Float'), ('str', 'String'), ('bool', 'Boolean')],
            default='str',  # Optional default value
            # coerce = lambda x: None if x == "None" else x
        )
        setattr(BuiltinFunctionForm, "variable", variable_field)
        setattr(BuiltinFunctionForm, "variable_type", type_field)
    elif logic_type == 'input':
        variable_field = VariableOrStringField(label=f'variable', validators=[InputRequired()],
                                     description="Variable to save user input",
                                     render_kw={"placeholder": "Result variable name"}, script=script)
        type_field = SelectField(
            'Select Value Type',
            choices=[('int', 'Integer'), ('float', 'Float'), ('str', 'String'), ('bool', 'Boolean')],
            default='str',
        )
        setattr(BuiltinFunctionForm, "variable", variable_field)
        setattr(BuiltinFunctionForm, "variable_type", type_field)

    elif logic_type == "math":
        math_variable_field = VariableOrStringField(
            label="save_to",
            validators=[InputRequired()],
            description="Variable name to save the result into",
            render_kw={"placeholder": "Result variable name"},
            script=script
        )
        setattr(BuiltinFunctionForm, "math_variable", math_variable_field)

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
        workflow_name = Script.validate_function_name(workflow.name)
        try:
        # if True:
            compiled_strs = workflow.compile().get('script', "")
            if not compiled_strs:
                continue
            method = get_method_from_workflow(compiled_strs)
            functions[workflow_name] = dict(signature=inspect.signature(method), docstring=inspect.getdoc(method))
            setattr(RegisteredWorkflows, workflow_name, method)

            form_class = create_form_for_method(method, autofill, script, design)

            hidden_method_name = HiddenField(name=f'workflow_name', description="",
                                             render_kw={"value": f'{workflow_name}'})
            if design:
                return_value = StringField(label='Save value as', render_kw={"placeholder": "Optional"})
                setattr(form_class, 'return', return_value)
            setattr(form_class, 'workflow_name', hidden_method_name)
            workflow_forms[workflow_name] = form_class()
        except Exception as e:
            # Log error or skip this workflow
            # print(f"Error loading workflow {workflow_name}: {e}")
            pass
    global_config.registered_workflows = RegisteredWorkflows
    return functions, workflow_forms


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
        "if": "background-color: mistyrose",
        "while": "background-color: #a8b5a2",
        "pause": "background-color: palegoldenrod",
        "comment": "background-color: lightgoldenrodyellow",
        "input": "background-color: lightcyan",
    }.get(action['instrument'], "")
    if not style:
        style = "background-color: thistle" if 'batch_action' in action and action["batch_action"] else ""

    if action['instrument'] in ['if', 'while', 'repeat']:
        text = f"{action['action']} {action['args'].get('statement', '')}"
    elif action['instrument'] in ('variable', 'math_variable'):
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
                        if not v:
                            value = v  # Keep the original value if not a dict
                        else:
                            value = next(iter(v))  # Extract the first key if it's a dict
                            # show warning color for variable calling when there is no definition

                            style = "background-color: khaki" if v.get(value) == "function_output" and value not in variables.keys() else ""
                    else:
                        value = v  # Keep the original value if not a dict
                    arg_list.append(f"{k} = {value}")  # Format the key-value pair
                arg_string = "(" + ", ".join(arg_list) + ")"
            else:
                arg_string = f"= {action['args']}"
        text = f"{prefix}{action_text}  {arg_string}"
    return dict(label=text, style=style, uuid=action["uuid"], id=action["id"], instrument=action['instrument'])
