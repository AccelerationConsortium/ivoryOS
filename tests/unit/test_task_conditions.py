import threading
from unittest.mock import MagicMock

import pytest

from ivoryos.runtime import task_conditions
from ivoryos.runtime.script_runner import ScriptRunner
from ivoryos.script import Script


class FakeOptimizer:
    @staticmethod
    def get_schema():
        return {
            "parameter_types": ["range", "choice"],
            "multiple_objectives": True,
            "supports_continuous": True,
            "supports_constraints": True,
            "optimizer_config": {
                "step_1": {"model": ["Sobol", "Uniform"], "num_samples": 5},
                "step_2": {"model": ["BoTorch", "SAASBO"]},
            },
            "additional_field": {"seed": {"type": "int", "required": False}},
        }


class DiscreteOptimizer(FakeOptimizer):
    @staticmethod
    def get_schema():
        return dict(FakeOptimizer.get_schema(), supports_continuous=False, multiple_objectives=False)


def make_script():
    script = Script(author="tester")
    script.script_dict["script"] = [
        {
            "id": 1, "uuid": 1, "instrument": "deck.reactor", "action": "run",
            "args": {"temperature": "#temperature", "solvent": "#solvent"},
            "return": "yield_pct", "arg_types": {"temperature": "float", "solvent": "str"},
        },
        {
            "id": 2, "uuid": 2, "instrument": "deck.reactor", "action": "measure",
            "args": {}, "return": "purity", "arg_types": {},
        },
    ]
    return script


def config_task(**extra):
    return {
        "script": make_script(), "repeat_count": None, "batch_size": 1, "compiled": False,
        "config": [{"temperature": "25", "solvent": "water"}, {"temperature": "30", "solvent": "ethanol"}],
        **extra,
    }


def optimizer_task(optimizer_cls=FakeOptimizer):
    return {
        "script": make_script(), "repeat_count": 10, "batch_size": 1, "config": None,
        "optimizer_cls": optimizer_cls,
        "parameters": [
            {"name": "temperature", "type": "range", "value_type": "float", "bounds": [20.0, 80.0]},
            {"name": "solvent", "type": "choice", "value_type": "str", "bounds": ["water", "ethanol"]},
        ],
        "objectives": [{"name": "yield_pct", "minimize": False}],
        "constraints": [],
        "steps": {"step_1": {"model": "Sobol", "num_samples": 5}, "step_2": {"model": "BoTorch"}},
        "additional_params": {},
    }


def test_task_mode_follows_what_the_runner_will_do():
    assert task_conditions.task_mode(config_task()) == task_conditions.CONFIG
    assert task_conditions.task_mode(optimizer_task()) == task_conditions.OPTIMIZER
    assert task_conditions.task_mode({"repeat_count": 3, "config": None}) == task_conditions.REPEAT


def test_config_view_lists_entries_as_text_under_the_workflow_inputs():
    task = config_task(config=[{"temperature": 25.5, "solvent": "water"}], compiled=True)

    view = task_conditions.editable_conditions(task)

    assert view["mode"] == "config"
    assert view["fields"] == ["temperature", "solvent"]
    assert view["types"] == {"temperature": "float", "solvent": "str"}
    assert view["rows"] == [["25.5", "water"]]


def test_config_edits_are_stored_as_text_for_the_runner_to_convert():
    task = config_task(compiled=True)

    updates = task_conditions.parse_changes(task, {
        "batch_size": "2",
        "config": [
            {"temperature": "40", "solvent": "toluene"},
            {"temperature": "", "solvent": ""},  # an entry added and never filled in
        ],
    })

    assert updates == {
        "batch_size": 2,
        "config": [{"temperature": "40", "solvent": "toluene"}],
        "compiled": False,
    }


@pytest.mark.parametrize("entries, message", [
    ([{"temperature": "hot", "solvent": "water"}], "Entry 1"),
    ([{"temperature": "25", "solvent": "water"}, {"temperature": "25", "solvent": ""}], "Entry 2 has no value for 'solvent'"),
    ([{"temperature": "25", "solvent": "water", "pressure": "1"}], "'pressure' is not an input"),
    ([{"temperature": "", "solvent": ""}], "at least one config entry"),
])
def test_config_edits_that_would_fail_the_run_are_refused(entries, message):
    with pytest.raises(ValueError, match=message):
        task_conditions.parse_changes(config_task(), {"config": entries})


@pytest.mark.parametrize("value", ["0", "-1", "two", "1.5"])
def test_repeat_count_and_batch_size_must_be_positive_whole_numbers(value):
    task = {"repeat_count": 3, "batch_size": 1, "config": None}
    with pytest.raises(ValueError, match="Repeat count"):
        task_conditions.parse_changes(task, {"repeat_count": value})
    with pytest.raises(ValueError, match="Batch size"):
        task_conditions.parse_changes(task, {"batch_size": value})


def test_optimizer_view_offers_every_output_and_the_schema_choices():
    view = task_conditions.editable_conditions(optimizer_task())

    assert view["mode"] == "optimizer"
    assert view["repeat_count"] == 10
    temperature, solvent = view["parameters"]
    assert (temperature["min"], temperature["max"], temperature["step"]) == ("20.0", "80.0", "")
    assert solvent["choices"] == "water, ethanol"
    assert temperature["types"] == ["range", "choice"]
    assert view["objectives"] == [
        {"name": "yield_pct", "goal": "maximize", "early_stop": ""},
        {"name": "purity", "goal": "none", "early_stop": ""},
    ]
    assert [(step["key"], step["model"], step["has_num_samples"]) for step in view["steps"]] == [
        ("step_1", "Sobol", True), ("step_2", "BoTorch", False),
    ]
    assert view["additional_params"] == [{"name": "seed", "type": "int", "options": [], "value": ""}]


def test_optimizer_edits_replace_the_campaign_settings():
    task = optimizer_task()

    updates = task_conditions.parse_changes(task, {
        "repeat_count": "20",
        "parameters": [
            {"name": "temperature", "type": "range", "min": "30", "max": "60", "step": "5"},
            {"name": "solvent", "type": "choice", "choices": "water, toluene, hexane"},
        ],
        "objectives": [
            {"name": "yield_pct", "goal": "none", "early_stop": ""},
            {"name": "purity", "goal": "maximize", "early_stop": "99.5"},
        ],
        "constraints": ["temperature <= 50", "  "],
        "steps": {"step_1": {"model": "Uniform", "num_samples": "8"}, "step_2": {"model": "SAASBO"}},
        "additional_params": {"seed": "7"},
    })

    assert updates["repeat_count"] == 20
    assert updates["parameters"] == [
        {"name": "temperature", "type": "range", "value_type": "float", "bounds": [30.0, 60.0, 5.0]},
        {"name": "solvent", "type": "choice", "value_type": "str", "bounds": ["water", "toluene", "hexane"]},
    ]
    assert updates["objectives"] == [{"name": "purity", "minimize": False, "early_stop": 99.5}]
    assert updates["constraints"] == ["temperature <= 50"]
    assert updates["steps"] == {"step_1": {"model": "Uniform", "num_samples": 8}, "step_2": {"model": "SAASBO"}}
    assert updates["additional_params"] == {"seed": 7}
    # nothing is applied to the task by checking the changes
    assert task["repeat_count"] == 10


@pytest.mark.parametrize("changes, message", [
    ({"parameters": [{"name": "temperature", "type": "range", "min": "60", "max": "30"}]}, "below its maximum"),
    ({"parameters": [{"name": "temperature", "type": "range", "min": "a", "max": "30"}]}, "must be a number"),
    ({"parameters": [{"name": "temperature", "type": "fixed", "value": "30"}]}, "does not take 'fixed'"),
    ({"parameters": [{"name": "pressure", "type": "range", "min": "1", "max": "2"}]}, "not a parameter"),
    ({"objectives": [{"name": "yield_pct", "goal": "none"}]}, "at least one objective"),
    ({"steps": {"step_1": {"model": "Magic"}}}, "not a model"),
    ({"additional_params": {"verbose": "True"}}, "not a setting"),
])
def test_optimizer_edits_the_optimizer_cannot_take_are_refused(changes, message):
    with pytest.raises(ValueError, match=message):
        task_conditions.parse_changes(optimizer_task(), changes)


def test_discrete_single_objective_optimizer_rules_are_enforced():
    task = optimizer_task(DiscreteOptimizer)
    with pytest.raises(ValueError, match="needs a step"):
        task_conditions.parse_changes(task, {
            "parameters": [{"name": "temperature", "type": "range", "min": "20", "max": "80", "step": ""}],
        })
    with pytest.raises(ValueError, match="single objective"):
        task_conditions.parse_changes(task, {"objectives": [
            {"name": "yield_pct", "goal": "maximize"}, {"name": "purity", "goal": "maximize"},
        ]})


def test_runner_edits_only_tasks_still_in_the_queue():
    runner = ScriptRunner()
    runner._emit_queue_status = MagicMock()
    task = config_task(uid="abc")
    runner.execution_queue = [task]

    assert runner.get_task_conditions("abc")["rows"] == [["25", "water"], ["30", "ethanol"]]
    assert runner.update_task_conditions("abc", {"batch_size": "3"}) is True
    assert task["batch_size"] == 3
    runner._emit_queue_status.assert_called_once()

    with pytest.raises(ValueError):
        runner.update_task_conditions("abc", {"batch_size": "3", "config": [{"temperature": "hot", "solvent": "x"}]})
    # a refused edit changes nothing, not even the fields that were fine
    assert task["config"][0] == {"temperature": "25", "solvent": "water"}

    assert runner.get_task_conditions("gone") is None
    assert runner.update_task_conditions("gone", {"batch_size": "2"}) is False


def test_queued_tasks_get_an_id_that_is_not_passed_on_to_the_run():
    runner = ScriptRunner()
    runner.lock = threading.Lock()
    runner.queue_paused = True  # keep the task waiting
    runner._emit_queue_status = MagicMock()
    runner._emit_busy_status = MagicMock()
    runner.run_script(script=make_script(), repeat_count=2, run_name="flow")

    uid = runner.execution_queue[0]["uid"]
    assert runner.get_queue_status()[0]["uid"] == uid

    runner._run_with_stop_check = MagicMock()
    runner.queue_paused = False
    runner._process_queue().join()

    kwargs = runner._run_with_stop_check.call_args.kwargs
    assert "uid" not in kwargs
    assert kwargs["run_name"] == "flow"


def test_renaming_changes_the_name_the_run_is_saved_under():
    task = config_task(run_name="screen", display_name="Screen")

    assert task_conditions.editable_conditions(task)["name"] == "screen"
    assert task_conditions.parse_changes(task, {"name": "High temp screen"}) == {
        "run_name": "High_temp_screen", "display_name": None,
    }
    # the same name is no change, so it is not made unique against itself
    assert task_conditions.parse_changes(task, {"name": " screen "}) == {}
    with pytest.raises(ValueError, match="name"):
        task_conditions.parse_changes(task, {"name": "  "})

    calls = []
    unique = lambda name, keep: calls.append((name, keep)) or "taken_1"
    assert task_conditions.parse_changes(task, {"name": "taken"}, unique_name=unique)["run_name"] == "taken_1"
    assert calls == [("taken", "screen")]
