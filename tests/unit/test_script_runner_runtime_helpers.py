from unittest.mock import MagicMock

import pytest

from ivoryos.runtime.script_runner import ScriptRunner
from ivoryos.runtime.script_runner_steps import ScriptRunnerStepMixin


class DummyOptimizer:
    pass


def test_queue_status_includes_display_name_and_execution_details():
    runner = ScriptRunner()
    runner.execution_queue = [{
        "run_name": "internal-run",
        "display_name": "Visible run",
        "repeat_count": 3,
        "config": [{"temperature": 20 + i} for i in range(6)],
        "batch_size": 2,
        "history": "history.csv",
        "optimizer_cls": DummyOptimizer,
        "objectives": [{"name": "yield", "minimize": False}],
        "parameters": [{"name": "temperature"}],
        "constraints": ["temperature >= 20"],
        "additional_params": {"seed": 1},
    }]

    status = runner.get_queue_status()

    assert status[0]["name"] == "Visible run"
    assert status[0]["args"] == "Config: 6 entries"
    details = status[0]["details"]
    assert details["Run Name"] == "internal-run"
    assert details["Mode"] == "Bayesian Optimization"
    assert details["Config Preview (First 5)"] == [{"temperature": 20 + i} for i in range(5)]
    assert details["Optimizer"] == "DummyOptimizer"
    assert details["Additional Params"] == {"seed": 1}


def test_queue_management_mutates_tasks_and_emits_status():
    runner = ScriptRunner()
    runner.execution_queue = [{"run_name": "first"}, {"run_name": "second"}]
    runner._emit_queue_status = MagicMock()

    assert runner.update_task_name("0", "renamed") is True
    assert runner.execution_queue[0]["display_name"] == "renamed"

    assert runner.reorder_tasks(1, "up") is True
    assert runner.execution_queue[0]["run_name"] == "second"

    assert runner.remove_task(1) is True
    assert runner.execution_queue == [{"run_name": "second"}]
    assert runner.update_task_name("99", "missing") is False
    assert runner.reorder_tasks(0, "sideways") is False
    assert runner._emit_queue_status.call_count == 3


def test_pause_and_input_helpers_update_runner_state():
    runner = ScriptRunner()
    runner.logger = MagicMock()
    runner.socketio = MagicMock()
    runner._process_queue = MagicMock()

    assert runner.handle_input_submission("ignored") is False
    runner.waiting_for_input = True
    assert runner.handle_input_submission("user value") is True
    assert runner.input_value == "user value"

    assert runner.toggle_pause() == "Paused"
    assert runner.paused is True
    assert runner.queue_paused is True
    assert not runner.pause_event.is_set()
    runner.socketio.emit.assert_called_with("pause_status", {"paused": True})

    assert runner.toggle_pause() == "Resumed"
    assert runner.paused is False
    assert runner.queue_paused is False
    assert runner.pause_event.is_set()
    runner._process_queue.assert_called_once()

    runner.stop_pending_event.set()
    runner.stop_current_event.set()
    runner.stop_cleanup_event.set()
    runner.pause_event.clear()
    runner.reset_stop_event()

    assert not runner.stop_pending_event.is_set()
    assert not runner.stop_current_event.is_set()
    assert not runner.stop_cleanup_event.is_set()
    assert runner.pause_event.is_set()


def test_substitute_params_replaces_exact_and_embedded_placeholders():
    result = ScriptRunnerStepMixin._substitute_params(
        {"exact": "#sample_id", "message": "Running #sample_id at #temperature", "literal": 5},
        {"sample_id": "A1", "temperature": 37},
    )

    assert result == {
        "exact": "A1",
        "message": "Running A1 at 37",
        "literal": 5,
    }

    with pytest.raises(KeyError):
        ScriptRunnerStepMixin._substitute_params({"message": "Missing #value"}, {})


def test_evaluate_condition_uses_context_and_rejects_invalid_expressions():
    assert ScriptRunnerStepMixin._evaluate_condition("#temperature > 20 and #ready", {
        "temperature": 25,
        "ready": True,
    }) is True
    assert ScriptRunnerStepMixin._evaluate_condition(False, {}) is False

    with pytest.raises(ValueError):
        ScriptRunnerStepMixin._evaluate_condition("#missing > 0", {})

    with pytest.raises(TypeError):
        ScriptRunnerStepMixin._evaluate_condition(None, {})


def test_check_early_stop_requires_all_objectives_on_one_row():
    runner = ScriptRunner()
    objectives = [
        {"name": "loss", "minimize": True, "early_stop": 0.2},
        {"name": "score", "minimize": False, "early_stop": 0.9},
    ]

    assert runner._check_early_stop([
        {"loss": 0.3, "score": 0.95},
        {"loss": 0.1, "score": 0.91},
    ], objectives) is True
    assert runner._check_early_stop([
        {"loss": 0.1, "score": 0.5},
    ], objectives) is False
    assert runner._check_early_stop([
        {"loss": 0.1, "score": 0.95},
    ], [{"name": "loss", "minimize": True}]) is False
