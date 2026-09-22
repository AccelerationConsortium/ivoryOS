"""A step whose deck method has been deleted must not pass as a success.

The designer flags such a step, but the runner has to fail on it too: a silent
no-op mid-run is worse than an error, because the workflow reports success
having skipped a step.
"""
import asyncio
from unittest.mock import MagicMock

from ivoryos.models import WorkflowPhase, WorkflowRun, WorkflowStep, db
from ivoryos.runtime.script_runner import ScriptRunner


def _execute(app, step):
    """Run one step; return the emitted socket events and the row written for it."""
    with app.app_context():
        db.create_all()
        run = WorkflowRun(name="r", platform="p")
        db.session.add(run)
        db.session.flush()
        phase = WorkflowPhase(run_id=run.id, name="script")
        db.session.add(phase)
        db.session.commit()
        phase_id = phase.id

        runner = ScriptRunner()
        runner.logger = MagicMock()
        runner.socketio = MagicMock()
        # on error the runner pauses for the operator to retry, and the `finally`
        # block then waits on that event; nothing would release it in a test
        runner.toggle_pause = MagicMock()

        asyncio.run(runner._execute_action(step, {}, phase_id=phase_id, step_index=1))

        row = db.session.query(WorkflowStep).filter_by(phase_id=phase_id).one()
        events = [call.args for call in runner.socketio.emit.call_args_list]
        return events, row


def _step(action, args=None, arg_types=None):
    return {
        "instrument": "deck.dummy",
        "action": action,
        "args": args or {},
        "arg_types": arg_types or {},
        "return": "",
    }


def test_deleted_method_is_recorded_as_an_error(app, init_database, test_deck):
    events, row = _execute(app, _step("method_that_was_deleted"))

    assert row.run_error is True
    errors = [payload for name, payload in events if name == "error"]
    assert errors and "method_that_was_deleted" in errors[0]["message"]


def test_removed_argument_is_recorded_as_an_error(app, init_database, test_deck):
    """This path already failed loudly - the call itself raises TypeError."""
    _, row = _execute(app, _step("int_method", {"arg": 1, "gone": 2},
                                 {"arg": "int", "gone": "int"}))

    assert row.run_error is True


def test_a_step_that_still_matches_the_deck_succeeds(app, init_database, test_deck):
    _, row = _execute(app, _step("int_method", {"arg": 3}, {"arg": "int"}))

    assert row.run_error is False
