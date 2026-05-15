import inspect
from datetime import date
from enum import Enum

import pytest

from ivoryos.parsers.py_to_json import convert_to_cards, extract_functions_and_convert, infer_type
from ivoryos.parsers.returns import extract_return_variables, store_return_value
from ivoryos.parsers.serialize import sanitize_for_json
from ivoryos.runtime.state import global_state


class Status(Enum):
    OK = "ok"


class NotJsonSerializable:
    def __repr__(self):
        return "<not-json>"


def test_infer_type_handles_supported_literal_values():
    assert infer_type(True) == "bool"
    assert infer_type(1) == "int"
    assert infer_type(1.5) == "float"
    assert infer_type("value") == "str"
    assert infer_type("#value") == "any"
    assert infer_type(object()) == "unknown"


def test_convert_to_cards_handles_variables_calls_and_control_flow():
    global_state.interface_schema = {
        "deck.pump": {
            "dose": {
                "signature": inspect.Signature(parameters=[
                    inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD),
                    inspect.Parameter("amount", inspect.Parameter.POSITIONAL_OR_KEYWORD),
                    inspect.Parameter("label", inspect.Parameter.POSITIONAL_OR_KEYWORD),
                ])
            }
        }
    }

    cards = convert_to_cards(
        """
def workflow(amount: float):
    count = 2
    if count > 1:
        reading = deck.pump.dose(amount, label="sample")
    else:
        deck.pump.dose(**{"amount": 3})
    while count < 5:
        deck.pump.dose(amount=count)
"""
    )

    assert [card["action"] for card in cards] == [
        "count",
        "if",
        "dose",
        "else",
        "dose",
        "endif",
        "while",
        "dose",
        "endwhile",
    ]
    assert cards[0]["instrument"] == "variable"
    assert cards[2]["instrument"] == "deck.pump"
    assert cards[2]["args"] == {"amount": "#amount", "label": "sample"}
    assert cards[2]["arg_types"] == {"amount": "float", "label": "str"}
    assert cards[2]["return"] == "reading"
    assert cards[4]["args"] == {"amount": 3}
    assert cards[7]["args"] == {"amount": "#count"}
    assert cards[7]["arg_types"] == {"amount": "int"}


def test_extract_functions_and_convert_returns_each_function_source():
    result = extract_functions_and_convert(
        """
def first():
    x = 1

def second():
    y = "done"
"""
    )

    assert set(result) == {"first", "second"}
    assert result["first"]["cards"][0]["action"] == "x"
    assert "def second" in result["second"]["source"]


def test_extract_return_variables_cleans_scalar_and_tuple_returns():
    form_data = {"return_1": " second value ", "return_0": "first-value", "other": "kept"}

    result = extract_return_variables(form_data, lambda value: value.replace(" ", "_").replace("-", "_"))

    assert result == ["first_value", "second_value"]
    assert form_data == {"other": "kept"}

    scalar = {"return": " total value "}
    assert extract_return_variables(scalar, lambda value: value.strip().replace(" ", "_")) == "total_value"
    assert scalar == {}


def test_store_return_value_saves_scalar_and_tuple_results():
    context = {}
    arg_contexts = {}

    store_return_value(context, arg_contexts, "status", Status.OK)
    store_return_value(context, arg_contexts, ["first", "", "third"], (1, 2, {"values": {3, 4}}))

    assert context["status"] == "ok"
    assert context["first"] == 1
    assert sorted(context["third"]["values"]) == [3, 4]
    assert arg_contexts == context

    with pytest.raises(ValueError, match="Cannot save return value"):
        store_return_value({}, {}, ["missing"], object())


def test_sanitize_for_json_recursively_converts_non_json_types():
    payload = {
        "when": date(2026, 5, 14),
        "status": Status.OK,
        "items": (1, {3, 2}),
        "unknown": NotJsonSerializable(),
    }

    result = sanitize_for_json(payload)
    assert result == {
        "when": "2026-05-14",
        "status": "ok",
        "items": [1, result["items"][1]],
        "unknown": "<not-json>",
    }
    assert sorted(result["items"][1]) == [2, 3]
