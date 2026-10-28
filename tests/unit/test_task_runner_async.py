"""Instrument methods that run actions at once work whether the caller waits or runs them in the background."""
import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from ivoryos.runtime.state import global_state
from ivoryos.runtime.task_runner import TaskRunner


async def _action(name):
    await asyncio.sleep(0.05)
    return name


class Mixer:
    def sync_asyncio_run(self):
        # issue #161: a plain method with its own asyncio.run must not land on a running loop
        return asyncio.run(self.async_gather())

    async def async_gather(self):
        return list(await asyncio.gather(_action("a"), _action("b")))


@pytest.fixture
def mock_app():
    app = MagicMock()
    app.app_context.return_value.__enter__.return_value = app
    return app


@pytest.fixture
def mixer():
    global_state.defined_variables["mixer"] = Mixer()
    yield
    global_state.defined_variables.pop("mixer", None)


@pytest.mark.parametrize("method", ["sync_asyncio_run", "async_gather"])
@pytest.mark.parametrize("wait", [True, False])
def test_concurrent_actions_in_a_method(mixer, mock_app, method, wait):
    finished = []
    runner = TaskRunner(on_step_finished=lambda step_id, result: finished.append(result))

    with patch("ivoryos.runtime.task_runner.db"):
        asyncio.run(runner.run_single_step("mixer", method, {}, wait=wait, current_app=mock_app))
        deadline = time.monotonic() + 5
        while not finished:
            assert time.monotonic() < deadline, "timed out"
            time.sleep(0.01)

    assert finished == [{"success": True, "output": ["a", "b"]}]
    assert not runner.lock.locked()
