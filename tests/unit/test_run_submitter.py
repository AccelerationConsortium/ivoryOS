"""Who submitted a run is kept from the request that queued it to the run's record."""
import threading
from unittest.mock import MagicMock

from ivoryos.models import WorkflowRun
from ivoryos.runtime.script_runner import ScriptRunner
from ivoryos.script import Script


def test_a_run_records_who_submitted_it(app, init_database, monkeypatch, tmp_path):
    from ivoryos.runtime import script_runner_workflow

    monkeypatch.setattr(script_runner_workflow.time, "sleep", lambda seconds: None)
    monkeypatch.setitem(app.config, "LOGGERS", None)
    runner = ScriptRunner()
    runner.socketio = MagicMock()
    runner.logger = None
    runner.current_task = {"uid": "task-1"}

    async def nothing(*args, **kwargs):
        return [{}]

    runner._run_actions, runner.exec_steps = nothing, nothing
    # on a thread of its own, as the queue runs it
    thread = threading.Thread(target=runner._run_with_stop_check, kwargs=dict(
        script=Script(author="alice"), repeat_count=1, run_name="heat", config=None, output_path=str(tmp_path),
        current_app=app, compiled=False, batch_size=1, submitted_by="alice"))
    thread.start()
    thread.join(timeout=30)

    with app.app_context():
        [run] = WorkflowRun.query.filter_by(name="heat").all()
        assert run.submitted_by == "alice"


def test_the_queue_says_who_submitted_each_task():
    runner = ScriptRunner()
    runner.execution_queue = [
        {"uid": "a", "run_name": "heat", "repeat_count": 2, "submitted_by": "alice"},
        {"uid": "b", "run_name": "cool", "repeat_count": 1},
    ]

    queue = runner.get_queue_status()

    assert [task["submitted_by"] for task in queue] == ["alice", None]
    assert queue[0]["details"]["Submitted By"] == "alice"
    assert "Submitted By" not in queue[1]["details"]
