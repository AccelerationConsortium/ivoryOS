"""TaskRunner tells open pages when a single step takes and lets go of the runner lock."""
import asyncio
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from ivoryos.runtime.state import global_state
from ivoryos.runtime.task_runner import TaskRunner


class Pump:
    def __init__(self):
        self.go = threading.Event()

    def dose(self, volume: float = 1.0):
        return volume

    def jam(self):
        raise RuntimeError("jammed")

    def slow(self):
        # runs until the test lets it finish
        self.go.wait(timeout=5)
        return "done"


@pytest.fixture
def mock_app():
    app = MagicMock()
    app.app_context.return_value.__enter__.return_value = app
    return app


@pytest.fixture
def pump():
    instrument = Pump()
    global_state.defined_variables["pump"] = instrument
    yield instrument
    instrument.go.set()
    global_state.defined_variables.pop("pump", None)


def _run(runner, method, mock_app, **kwargs):
    with patch("ivoryos.runtime.task_runner.db"):
        return asyncio.run(runner.run_single_step("pump", method, {}, current_app=mock_app, **kwargs))


@pytest.mark.parametrize("method, success", [("dose", True), ("jam", False)])
def test_busy_change_on_take_and_release(pump, mock_app, method, success):
    seen = []
    runner = TaskRunner(on_busy_change=lambda: seen.append(
        (runner.lock.locked(), (global_state.running_step or {}).get("method"))))

    assert _run(runner, method, mock_app)["success"] is success
    # running when the step starts, named once it is recorded, idle once it ends, whether it worked or not
    assert seen == [(True, None), (True, method), (False, None)]
    assert not runner.lock.locked()
    assert global_state.running_step is None


def test_busy_status_names_running_step(pump, mock_app):
    # a page on the step's instrument shows it running, even one opened mid-call (overlay.js)
    from ivoryos.socket_handlers import runner as script_runner

    with patch.object(script_runner, "socketio") as socketio:
        _run(TaskRunner(on_busy_change=script_runner._emit_busy_status), "dose", mock_app)

    tasks = [c.args[1]["task"] for c in socketio.emit.call_args_list if c.args[0] == "busy_status"]
    assert tasks == [None, {"id": None, "component": "pump", "method": "dose"}, None]  # no id: the db is patched


def test_no_busy_change_on_override(pump, mock_app):
    seen = []
    runner = TaskRunner(on_busy_change=lambda: seen.append(True))

    _run(runner, "dose", mock_app, override_busy=True)
    # an override never takes the lock, so the platform's state did not change
    assert seen == []


def _wait_for(condition, timeout=5):
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.01)


def test_background_step_holds_lock_until_method_returns(pump, mock_app):
    finished = []
    runner = TaskRunner(on_step_finished=lambda step_id, result: finished.append(result))

    with patch("ivoryos.runtime.task_runner.db"):
        reply = asyncio.run(runner.run_single_step("pump", "slow", {}, wait=False, current_app=mock_app))
        # the reply comes back while the method still runs, and the lock stays taken
        assert reply["status"] == "task started"
        time.sleep(0.2)
        assert runner.lock.locked()
        assert finished == []

        pump.go.set()
        _wait_for(lambda: finished)

    assert finished == [{"success": True, "output": "done"}]
    assert not runner.lock.locked()


def test_busy_reply_while_background_step_runs(pump, mock_app):
    runner = TaskRunner()

    with patch("ivoryos.runtime.task_runner.db"):
        asyncio.run(runner.run_single_step("pump", "slow", {}, wait=False, current_app=mock_app))
        running = dict(global_state.runner_status)

        busy = asyncio.run(runner.run_single_step("pump", "dose", {}, current_app=mock_app))
        assert busy["status"] == "busy"
        assert busy["success"] is False
        # telling a caller it is busy leaves the running step's status alone
        assert global_state.runner_status == running

        pump.go.set()
        _wait_for(lambda: not runner.lock.locked())


def test_background_step_that_cannot_start_lets_go_of_lock(pump, mock_app):
    runner = TaskRunner()

    with patch("ivoryos.runtime.task_runner.db"):
        reply = asyncio.run(runner.run_single_step("pump", "no_such_method", {}, wait=False, current_app=mock_app))

    assert reply["status"] == "error"
    assert not runner.lock.locked()
