import inspect
import json
from enum import Enum
from typing import Dict, Optional

import pytest

from ivoryos.forms.dynamic_forms import (
    StructuredField, _action_button, create_form_for_method, create_form_from_action,
)
from ivoryos.parsers.introspection import _inspect_class
from ivoryos.parsers.py_to_json import convert_to_cards
from ivoryos.parsers.structured_types import (
    iter_variables, parse_structured_value, render_python, structured_schema, validate_structured_value,
)
from ivoryos.runtime.script_runner_steps import ScriptRunnerStepMixin
from ivoryos.runtime.state import global_state
from ivoryos.script import Script, ScriptEditor, ScriptRenderer


class Mode(Enum):
    FAST = "fast"
    SLOW = "slow"


class FakeDevice:
    def __init__(self):
        self.received = None

    def configure(self, settings: dict, gains: Optional[Dict[str, float]] = None):
        self.received = (settings, gains)


DICT_TEXT = '{"mode": "fast", "gain": #gain, "limits": [0, 10]}'
DICT_VALUE = {"mode": "fast", "gain": "#gain", "limits": [0, 10]}


def configure_action(settings=None):
    return {"id": 1, "uuid": 1, "instrument": "deck.device", "action": "configure", "return": "",
            "args": {"settings": DICT_VALUE if settings is None else settings}, "arg_types": {"settings": "dict"}}


def test_parse_accepts_json_python_literals_and_variables():
    assert parse_structured_value(DICT_TEXT) == DICT_VALUE
    assert parse_structured_value("{'p': 1.5, 'i': None, 'on': True, 1: -2}") == {"p": 1.5, "i": None, "on": True, 1: -2}
    with pytest.raises(ValueError, match="unsupported expression"):
        parse_structured_value("{'p': f(1)}")


def test_validate_requires_a_dict_at_every_dict_level():
    validate_structured_value({"p": 1}, dict)
    with pytest.raises(ValueError, match="expected a dict"):
        validate_structured_value([1, 2], dict)
    with pytest.raises(ValueError, match=r"\['a'\]: expected a dict"):
        validate_structured_value({"a": [1]}, Dict[str, dict])


def test_schema_describes_keys_and_values():
    assert structured_schema(Optional[Dict[str, float]]) == {
        "kind": "dict", "key": {"kind": "scalar", "type": "str", "optional": False},
        "value": {"kind": "scalar", "type": "float", "optional": False}, "optional": True}
    assert structured_schema(Dict[int, Mode])["value"] == {
        "kind": "enum", "type": "Mode", "choices": ["fast", "slow"], "optional": False}
    assert structured_schema(dict)["value"] == {"kind": "json", "optional": False}


def test_dict_params_use_the_table_editor(app):
    signature = inspect.signature(FakeDevice.configure)

    with app.test_request_context():
        form = create_form_for_method(signature, autofill=False, script=Script(author="tester"), design=True)()
    assert isinstance(form.settings, StructuredField) and isinstance(form.gains, StructuredField)
    assert (form.settings._value(), form.gains._value()) == ("{}", "")  # required: an empty dict; optional: None
    assert json.loads(form.gains.render_kw["data-schema"]) == structured_schema(Optional[Dict[str, float]])

    with app.test_request_context(method="POST", data={"settings": DICT_TEXT, "gains": "{'p': 1.5, 'i': None}"}):
        form = create_form_for_method(signature, autofill=False, script=Script(author="tester"), design=True)()
        assert form.validate(), form.errors
    assert (form.settings.data, form.gains.data) == (DICT_VALUE, {"p": 1.5, "i": None})

    with app.test_request_context(method="POST", data={"settings": "[1, 2]"}):
        form = create_form_for_method(signature, autofill=False, script=Script(author="tester"), design=True)()
        assert not form.validate()
    assert "expected a dict" in form.settings.errors[0]


def test_control_panel_takes_dicts_but_not_variables(app):
    signature = inspect.signature(FakeDevice.configure)

    with app.test_request_context(method="POST", json={"settings": {"mode": "fast", "gain": 2.5}}):
        form = create_form_for_method(signature, autofill=False, design=False)()
        assert form.validate(), form.errors
    assert form.settings.data == {"mode": "fast", "gain": 2.5}

    with app.test_request_context(method="POST", data={"settings": DICT_TEXT}):
        form = create_form_for_method(signature, autofill=False, design=False)()
        assert not form.validate()
    assert form.settings.errors == ["Variables are only supported when designing a workflow"]


def test_dict_variables_become_run_parameters_exported_as_names():
    script = Script(author="tester", script_dict={"prep": [], "script": [configure_action()], "cleanup": []})

    assert ScriptEditor(script).config("script") == (["gain"], {"gain": "any"})
    assert "'settings': {'mode': 'fast', 'gain': gain, 'limits': [0, 10]}" in ScriptRenderer(script).compile()["script"]
    assert ScriptRunnerStepMixin._substitute_params({"settings": DICT_VALUE}, {"gain": 2.0}) == {
        "settings": {"mode": "fast", "gain": 2.0, "limits": [0, 10]}}
    assert list(iter_variables({"p": "#kp"}, Dict[str, float])) == [("kp", float)]
    assert render_python({"p": "#kp", "i": None}) == "{'p': kp, 'i': None}"


def test_plain_dict_exports_as_before():
    action = configure_action({"mode": "fast", "gain": 2.5})
    script = Script(author="tester", script_dict={"prep": [], "script": [action], "cleanup": []})

    assert ScriptEditor(script).config("script") == ([], {})
    assert "'settings': {'mode': 'fast', 'gain': 2.5}" in ScriptRenderer(script).compile()["script"]


def test_stored_dict_shows_whole_in_edit_form_and_canvas(app):
    action = configure_action()
    # an Optional[Dict[str, float]] is recorded as ["Dict", "NoneType"]
    action["args"]["gains"], action["arg_types"]["gains"] = {"p": 1.5}, ["Dict", "NoneType"]

    with app.test_request_context():
        form = create_form_from_action(action, script=Script(author="tester"))

    assert isinstance(form.settings, StructuredField) and isinstance(form.gains, StructuredField)
    assert json.loads(form.settings._value()) == DICT_VALUE
    assert json.loads(form.gains._value()) == {"p": 1.5}
    assert _action_button(configure_action(), variables={})["label"] == (
        "device.configure  (settings = {'mode': 'fast', 'gain': gain, 'limits': [0, 10]})")


def test_dict_naming_an_earlier_output_still_reads_as_that_output(app):
    action = configure_action({"result": "function_output"})

    with app.test_request_context():
        form = create_form_from_action(action, script=Script(author="tester"))

    assert not isinstance(form.settings, StructuredField)
    assert "settings = result" in _action_button(action, variables={"result": "any"})["label"]


def test_python_import_parses_dict_args_with_names(monkeypatch):
    monkeypatch.setattr(global_state, "_interface_schema", {"deck.device": _inspect_class(FakeDevice())})

    cards = convert_to_cards(
        """
def workflow(gain: float):
    deck.device.configure(settings={"mode": "fast", "gain": gain, "limits": [0, 10]})
"""
    )

    assert cards[0]["args"] == {"settings": DICT_VALUE}
    assert cards[0]["arg_types"] == {"settings": "dict"}
