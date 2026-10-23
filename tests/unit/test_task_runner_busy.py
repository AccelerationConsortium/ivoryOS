"""TaskRunner tells open pages when a single step takes and lets go of the runner lock."""
import asyncio
from unittest.mock import MagicMock, patch

import pytest

from ivoryos.runtime.state import global_state
from ivoryos.runtime.task_runner import TaskRunner


class Pump:
    def dose(self, volume: float = 1.0):
        return volume

    def jam(self):
        raise RuntimeError("jammed")


@pytest.fixture
def mock_app():
    app = MagicMock()
    app.app_context.return_value.__enter__.return_value = app
    return app


@pytest.fixture
def pump():
    global_state.defined_variables["pump"] = Pump()
    yield
    global_state.defined_variables.pop("pump", None)


def _run(runner, method, mock_app, **kwargs):
    with patch("ivoryos.runtime.task_runner.db"):
        return asyncio.run(runner.run_single_step("pump", method, {}, current_app=mock_app, **kwargs))


@pytest.mark.parametrize("method, success", [("dose", True), ("jam", False)])
def test_busy_change_on_take_and_release(pump, mock_app, method, success):
    seen = []
    runner = TaskRunner(on_busy_change=lambda: seen.append(runner.lock.locked()))

    assert _run(runner, method, mock_app)["success"] is success
    # running when the step starts, idle once it ends, whether it worked or not
    assert seen == [True, False]
    assert not runner.lock.locked()


def test_no_busy_change_on_override(pump, mock_app):
    seen = []
    runner = TaskRunner(on_busy_change=lambda: seen.append(True))

    _run(runner, "dose", mock_app, override_busy=True)
    # an override never takes the lock, so the platform's state did not change
    assert seen == []
