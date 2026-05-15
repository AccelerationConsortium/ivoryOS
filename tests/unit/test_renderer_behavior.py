import os
from enum import Enum

from ivoryos.script import Script, ScriptRenderer


class RenderChoice(Enum):
    A = "a"


def action(instrument, name, args=None, return_value="", **extra):
    data = {
        "id": extra.pop("id", 1),
        "uuid": extra.pop("uuid", 1),
        "instrument": instrument,
        "action": name,
        "args": args or {},
        "return": return_value,
        "arg_types": extra.pop("arg_types", {}),
    }
    data.update(extra)
    return data


def test_render_script_lines_formats_common_action_types():
    script = Script(author="tester")
    renderer = ScriptRenderer(script)
    script_dict = {
        "prep": [],
        "script": [
            action("variable", "count", {"statement": 1}, id=1, arg_types={"statement": "int"}),
            action("if", "if", {"statement": "count > 0"}, id=2),
            action("wait", "wait", {"statement": "#delay"}, id=3),
            action("if", "else", {}, id=4),
            action("input", "sample", {"statement": "Sample?", "variable": "sample"}, id=5),
            action("if", "endif", {}, id=6),
            action("math_variable", "total", {"statement": "#count + 1"}, id=7),
            action("deck.pump", "dose", {"amount": 1}, "result", id=8),
        ],
        "cleanup": [],
    }

    lines = renderer.render_script_lines(script_dict)["script"]

    assert lines == [
        "count = 1",
        "if count > 0:",
        "    time.sleep(delay)",
        "else:",
        "    sample = input('Sample?')",
        "# endif",
        "total = #count + 1",
        "result = deck.pump.dose(amount=1)",
    ]


def test_render_nested_script_lines_handles_workflows_properties_and_comments():
    script = Script(author="tester")
    renderer = ScriptRenderer(script)
    script_dict = {
        "prep": [],
        "script": [
            action(
                "workflows",
                "child_workflow",
                {"sample": "#sample", "label": "A"},
                "child_result",
                workflow=[action("comment", "comment", {"statement": "nested"}, id=1)],
                id=1,
            ),
            action("deck.heater", "temperature_(setter)", {"value": "#target"}, id=2),
            action("deck.heater", "temperature", {}, "actual", id=3),
            action("comment", "comment", {"statement": "#actual"}, id=4),
        ],
        "cleanup": [],
    }
    interface_schema = {
        "deck.heater": {
            "temperature": {"is_property": True}
        }
    }

    nodes = renderer.render_nested_script_lines(script_dict, interface_schema=interface_schema)["script"]

    assert nodes[0]["type"] == "workflow"
    assert nodes[0]["code"] == "child_result = child_workflow(sample=#sample, label=A)"
    assert nodes[0]["children"][0]["code"] == "    print('nested')"
    assert nodes[1]["code"] == "deck.heater.temperature = target"
    assert nodes[2]["code"] == "actual = deck.heater.temperature"
    assert nodes[3]["code"] == "print(actual)"


def test_compile_generates_headers_builtins_returns_and_required_imports(tmp_path):
    script = Script(name="My Workflow", author="tester", deck="my_deck")
    script.script_dict["script"] = [
        action("variable", "count", {"statement": 1}, id=1, arg_types={"statement": "int"}),
        action("input", "sample", {"statement": "Sample?", "variable": "sample", "variable_type": "str"}, "sample", id=2),
        action("wait", "wait", {"statement": 0.1}, id=3),
        action("pause", "pause", {"statement": "Check"}, id=4),
        action("math_variable", "total", {"statement": "#count + 2"}, id=5, arg_types={"statement": "float"}),
        action(
            "deck.pump",
            "dose",
            {"amount": "#total", "choice": "a"},
            ["first", "second"],
            id=6,
            arg_types={"amount": "float", "choice": "Enum:tests.unit.test_renderer_behavior.RenderChoice"},
        ),
    ]

    renderer = ScriptRenderer(script)
    compiled = renderer.compile(script_path=str(tmp_path) + os.sep)

    assert "def My_Workflow():" in compiled["script"]
    assert "sample = input('Sample?')" in compiled["script"]
    assert "time.sleep(0.1)" in compiled["script"]
    assert "pause('''Check''')" in compiled["script"]
    assert "total = count + 2" in compiled["script"]
    assert "__ivoryos_result = deck.pump.dose(**{'amount': total, 'choice': RenderChoice('a')})" in compiled["script"]
    assert "return {" in compiled["script"]
    assert "'sample':sample" in compiled["script"]
    assert "'first':first" in compiled["script"]
    assert "'second':second" in compiled["script"]

    imports = renderer.get_required_imports()
    assert "import my_deck as deck" in imports
    assert "from tests.unit.test_renderer_behavior import RenderChoice" in imports

    written = tmp_path / "My_Workflow.py"
    assert written.exists()
    file_text = written.read_text()
    assert "deck = None" not in file_text
    assert "def pause(reason=\"Manual intervention required\")" in file_text


def test_compile_batch_mode_uses_param_list_and_result_storage():
    script = Script(name="Batch Run", author="tester")
    script.script_dict["script"] = [
        action("variable", "seed", {"statement": 1}, id=1, arg_types={"statement": "int"}),
        action("deck.pump", "dose", {"amount": "#configured_amount"}, "reading", id=2, arg_types={"amount": "float"}),
    ]

    compiled = ScriptRenderer(script).compile(batch=True)["script"]

    assert "def Batch_Run(param_list):" in compiled
    assert '"""Batch mode is experimental and may have bugs."""' in compiled
    assert "for param in param_list:" in compiled
    assert "configured_amount = param['configured_amount']" in compiled
    assert "param['reading'] = reading" in compiled
    assert "return param_list" in compiled
