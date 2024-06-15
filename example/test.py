import requests
from flask import app, redirect, render_template, url_for, Flask, request
from wtforms.fields.simple import BooleanField, HiddenField

from example.dummy_balance import DummyBalance
from example.dummy_deck import DummySDLDeck
from example.dummy_pump import DummyPump

app = Flask(__name__)
app.secret_key = "key"
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, IntegerField, SubmitField, RadioField
import inspect


def format_name(name):
    """Converts 'example_name' to 'Example Name'."""
    text = ' '.join(word for word in name.split('_'))
    return text.capitalize()


def create_form_for_method(method, method_name):
    class DynamicForm(FlaskForm):
        pass

    sig = inspect.signature(method)

    for param in sig.parameters.values():
        if param.name == 'self':
            continue

        # Decide the field type based on annotation
        field_class = StringField  # Default to StringField as a fallback
        formatted_param_name = format_name(param.name)
        field_kwargs = {
            "label": f'{formatted_param_name}',
            "default": param.default
        }
        placeholder_text = f'Enter {param.annotation.__name__} value'
        render_kwargs = {"placeholder": placeholder_text}

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
    fname = HiddenField(name='method_name', default=f'{method_name}', label='')
    setattr(DynamicForm, 'method_name', fname)
    return DynamicForm


# Create forms for each method in DummySDLDeck
sdl_deck = DummySDLDeck(DummyPump("COM1"), DummyBalance("COM2"))
method_forms = {}
for attr_name in dir(sdl_deck):
    attr = getattr(sdl_deck, attr_name)
    if callable(attr) and not attr_name.startswith('_'):
        form_class = create_form_for_method(attr, attr_name)
        method_forms[attr_name] = form_class


@app.route('/', methods=['GET', 'POST'])
def index():
    forms = {name: form() for name, form in method_forms.items() if issubclass(form, FlaskForm)}
    # print(forms)
    if request.method == 'POST':
        all_kwargs = request.form.copy()

        method_name = all_kwargs.pop("method_name", None)
        print(method_name)
        form = forms.get(method_name, None)
        if form.validate_on_submit():
            kwargs = {field.name: field.data for field in form if field.name != 'csrf_token'}
            kwargs.pop("method_name")
            func = getattr(sdl_deck, method_name)
            result = func(**kwargs)
        else:
            result = form.errors
        return redirect(url_for('index', result=result))
    return render_template('index.html', forms=forms, format_name=format_name)


if __name__ == '__main__':
    app.run(debug=True, port=3000)
