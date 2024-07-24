from wtforms.fields.simple import SubmitField
from wtforms.validators import InputRequired

from example.dummy_balance import DummyBalance
from example.dummy_deck import DummySDLDeck
from example.dummy_pump import DummyPump

from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, IntegerField, BooleanField, HiddenField
import inspect


def format_name(name):
    """Converts 'example_name' to 'Example Name'."""
    name = name.split(".")[-1]
    text = ' '.join(word for word in name.split('_'))
    return text.capitalize()


def create_form_for_method(method, method_name, autofill):
    class DynamicForm(FlaskForm):
        pass

    sig = inspect.signature(method)

    for param in sig.parameters.values():
        if param.name == 'self':
            continue
        formatted_param_name = format_name(param.name)
        placeholder_text = f'Enter {param.annotation.__name__} value'
        render_kwargs = {"placeholder": placeholder_text}
        if autofill:
            field_class = StringField
            field_kwargs = {
                "label": f'{formatted_param_name}',
                "default": f'#{param.name}',
            }
        else:
            # Decide the field type based on annotation
            field_class = StringField  # Default to StringField as a fallback
            field_kwargs = {
                "label": f'{formatted_param_name}',
                "default": param.default if param.default is not param.empty else "",
            }
            # print(param.name, param.default.__name__, param, type(param.default))

            if param.annotation is int:
                field_class = IntegerField
            elif param.annotation is float:
                field_class = FloatField
            elif param.annotation is str:
                field_class = StringField
            elif param.annotation is bool:
                field_class = BooleanField

        # Create the field with additional rendering kwargs for placeholder text
        field = field_class(**field_kwargs, render_kw=render_kwargs)
        setattr(DynamicForm, param.name, field)

    # setattr(DynamicForm, f'add', fname)
    return DynamicForm


# Create forms for each method in DummySDLDeck
def create_add_form(attr, attr_name, autofill):
    dynamic_form = create_form_for_method(attr, attr_name, autofill)
    return_value = StringField(label='Save value as', render_kw={"placeholder": "Optional"})
    setattr(dynamic_form, 'return', return_value)
    hidden_method_name = HiddenField(name=f'hidden_name', render_kw={"value": f'{attr_name}'})
    setattr(dynamic_form, 'hidden_name', hidden_method_name)
    return dynamic_form


def create_form_from_module(sdl_module, autofill):
    # sdl_deck = DummySDLDeck(DummyPump("COM1"), DummyBalance("COM2"))
    method_forms = {}
    for attr_name in dir(sdl_module):
        attr = getattr(sdl_module, attr_name)
        if callable(attr) and not attr_name.startswith('_'):
            form_class = create_add_form(attr, attr_name, autofill)
            method_forms[attr_name] = form_class()
    return method_forms


def create_builtin_form(logic_type):
    class BuiltinFunctionForm(FlaskForm):
        pass

    placeholder_text = f'Enter numbers' if logic_type == 'wait' else f'Enter statement'
    description_text = f'Your variable can be numbers, boolean (True or False) or text ("text")' if logic_type == 'variable' else ''
    field_class = FloatField if logic_type == 'wait' else StringField  # Default to StringField as a fallback
    field_kwargs = {
        "label": f'statement',
        "validators": [InputRequired()] if logic_type in ['wait', "variable"] else [],
        "description": description_text,
    }
    render_kwargs = {"placeholder": placeholder_text}
    field = field_class(**field_kwargs, render_kw=render_kwargs)
    setattr(BuiltinFunctionForm, "statement", field)
    if logic_type == 'variable':
        variable_field = StringField(label=f'variable', validators=[InputRequired()],
                                     description="Your variable name cannot include space",
                                     render_kw=render_kwargs)
        setattr(BuiltinFunctionForm, "variable", variable_field)
    hidden_field = HiddenField(name=f'builtin_name', render_kw={"value": f'{logic_type}'})
    setattr(BuiltinFunctionForm, "builtin_name", hidden_field)
    return BuiltinFunctionForm()


def create_action_button(s: dict):
    style = ""
    if s['instrument'] in ['if', 'while']:
        text = f"{s['action']} {s['args']}"
        style = "background-color: tomato"
    elif s['instrument'] == 'variable':
        text = f"{s['action']} = {s['args']}"
    else:
        # regular action button
        prefix = f"{s['return']} = " if s['return'] else ""
        action_text = f"{s['instrument'].split('.')[-1] if s['instrument'].startswith('deck') else s['instrument']}.{s['action']}"
        arg_string = ""
        if s['args']:
            if type(s['args']) is dict:
                arg_string = "("+", ".join([f"{k} = {v}" for k, v in s['args'].items()]) + ")"
            else:
                arg_string = f"= {s['args']}"

        text = f"{prefix}{action_text}  {arg_string}"
    return dict(label=text, style=style, uuid=s["uuid"], id=s["id"])


if __name__ == '__main__':
    pump = DummyPump("COM1")
    sdl_deck = DummySDLDeck(DummyPump("COM1"), DummyBalance("COM2"))
    forms = create_form_from_module(pump)
