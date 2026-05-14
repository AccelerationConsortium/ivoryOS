import pytest

from ivoryos.script import Script, ScriptEditor


def test_add_variable_math_and_input_actions_update_variables():
    script = Script(author="tester")
    editor = ScriptEditor(script)

    editor.add_variable("true", "flag value", "bool")
    editor.add_math_variable("#flag_value + 2", "score total")
    editor.add_input_action("Enter sample", "sample_name", "str")

    actions = script.script_dict["script"]
    assert [action["action"] for action in actions] == ["flag_value", "score_total", "sample_name"]
    assert actions[0]["args"]["statement"] is True
    assert actions[1]["instrument"] == "math_variable"
    assert actions[2]["return"] == "sample_name"
    assert editor.get_variables() == {
        "sample_name": "function_output",
        "flag_value": "bool",
        "score_total": "float",
    }


def test_insert_sort_duplicate_and_delete_actions_by_uuid():
    script = Script(author="tester")
    editor = ScriptEditor(script)
    editor.add_action({"instrument": "deck.pump", "action": "prime", "args": {}, "return": "", "arg_types": {}})
    editor.add_action(
        {"instrument": "deck.pump", "action": "dose", "args": {"amount": 1}, "return": "", "arg_types": {"amount": "int"}},
        insert_position="1",
    )

    assert [action["action"] for action in script.script_dict["script"]] == ["dose", "prime"]

    editor.duplicate_action(1)
    assert [action["id"] for action in script.script_dict["script"]] == [1, 2, 3]
    assert script.script_dict["script"][1]["action"] == "dose"

    editor.add_logic_action("if", "#ready")
    logic_uuid = script.script_dict["script"][-3]["uuid"]
    editor.delete_action(script.script_dict["script"][-3]["id"])

    assert all(action["uuid"] != logic_uuid for action in script.script_dict["script"])


def test_config_and_validate_variables_resolve_inputs_and_outputs():
    script = Script(author="tester")
    script.script_dict["script"] = [
        {
            "id": 1,
            "uuid": 1,
            "instrument": "deck.sensor",
            "action": "read",
            "args": {},
            "return": "reading",
            "arg_types": {},
        },
        {
            "id": 2,
            "uuid": 2,
            "instrument": "deck.pump",
            "action": "dose",
            "args": {"amount": "#configured_amount", "label": "literal"},
            "return": "",
            "arg_types": {"amount": "float", "label": "str"},
        },
        {
            "id": 3,
            "uuid": 3,
            "instrument": "math_variable",
            "action": "scaled",
            "args": {"statement": "#configured_amount * 2"},
            "return": "",
            "arg_types": {"statement": "float"},
        },
    ]

    editor = ScriptEditor(script)

    config, config_types = editor.config("script")
    assert config == ["configured_amount"]
    assert config_types == {"configured_amount": "float"}

    kwargs = editor.validate_variables(
        {"amount": "reading", "count": "42", "new variable": "#bad name"},
        {"amount": "float", "count": "int", "new variable": "str"},
    )
    assert kwargs == {
        "amount": "#reading",
        "count": 42,
        "new variable": "#bad_name",
    }


def test_duplicate_missing_action_raises_value_error():
    script = Script(author="tester")
    editor = ScriptEditor(script)

    with pytest.raises(ValueError):
        editor.duplicate_action(404)
