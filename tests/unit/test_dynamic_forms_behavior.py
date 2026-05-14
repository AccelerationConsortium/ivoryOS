import inspect
from enum import Enum
from typing import Optional

from ivoryos.forms.dynamic_forms import (
    FlexibleEnumField,
    VariableOrBoolField,
    VariableOrFloatField,
    VariableOrIntField,
    VariableOrStringField,
    create_action_button,
    create_all_builtin_forms,
    create_form_for_method,
    create_form_from_action,
    parse_annotation,
)
from ivoryos.script import Script


class Choice(Enum):
    RED = "red"
    BLUE = "blue"


def typed_method(count: int, amount: float = 1.5, enabled: bool = False, color: Choice = Choice.RED, items: list = None, **extra):
    return count, amount, enabled, color, items, extra


def test_parse_annotation_detects_optional_types():
    types, optional = parse_annotation(Optional[int])

    assert types == [int]
    assert optional is True


def test_create_form_for_method_uses_expected_fields_and_metadata(app):
    script = Script(author="tester")

    with app.app_context():
        form_class = create_form_for_method(
            inspect.signature(typed_method),
            autofill=False,
            script=script,
            design=True,
        )
        form = form_class()

    assert isinstance(form.count, VariableOrIntField)
    assert isinstance(form.amount, VariableOrFloatField)
    assert isinstance(form.enabled, VariableOrBoolField)
    assert isinstance(form.color, FlexibleEnumField)
    assert isinstance(form.items, VariableOrStringField)
    assert form.color.choices == ["RED", "BLUE"]
    assert form_class.has_kwargs is True
    assert form_class.arg_types["items"] == "list"


def test_create_form_from_action_preserves_arg_order_and_return_fields(app):
    action = {
        "id": 7,
        "uuid": 99,
        "instrument": "deck.pump",
        "action": "dose",
        "args": {"second": 2, "first": "alpha"},
        "arg_types": {"first": "str", "second": "int"},
        "arg_order": ["second", "first"],
        "return": ["volume", ""],
        "return_format": {"types": ["float", "str"]},
    }

    with app.app_context():
        form = create_form_from_action(action, script=Script(author="tester"), design=True)

    assert list(form._fields.keys())[:2] == ["second", "first"]
    assert form.second.data == 2
    assert form.first.data == "alpha"
    assert form.return_0.data == "volume"
    assert form.return_1.data == ""
    assert form.return_0.render_kw["placeholder"] == "float"


def test_create_all_builtin_forms_exposes_expected_controls(app):
    script = Script(author="tester")

    with app.app_context():
        forms = create_all_builtin_forms(script)

    assert set(forms) == {"if", "while", "variable", "input", "wait", "repeat", "pause", "math", "comment"}
    assert hasattr(forms["wait"], "batch_action")
    assert hasattr(forms["variable"], "variable_type")
    assert hasattr(forms["input"], "variable_type")
    assert hasattr(forms["math"], "math_variable")


def test_create_action_button_formats_variables_returns_and_missing_outputs():
    script = Script(author="tester")
    script.script_dict["script"] = [
        {
            "id": 1,
            "uuid": 10,
            "instrument": "variable",
            "action": "sample_count",
            "args": {"statement": 3},
            "return": "",
            "arg_types": {"statement": "int"},
        },
        {
            "id": 2,
            "uuid": 11,
            "instrument": "deck.pump",
            "action": "dose",
            "args": {"amount": {"missing_output": "function_output"}},
            "arg_types": {"amount": "float"},
            "arg_order": ["amount"],
            "return": ["measured", ""],
        },
    ]

    buttons = create_action_button(script)

    assert buttons[0]["label"] == "sample_count = 3"
    assert "measured, _ = pump.dose" in buttons[1]["label"]
    assert "amount = missing_output" in buttons[1]["label"]
    assert buttons[1]["style"] == "background-color: khaki"
