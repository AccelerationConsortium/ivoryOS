"""A step the last server left running is marked interrupted at startup, so nothing waits on it."""
from datetime import datetime

from ivoryos.models import db, SingleStep
from ivoryos.runtime.task_runner import INTERRUPTED, mark_interrupted_steps


def test_unfinished_steps_marked_interrupted(app, init_database):
    with app.app_context():
        finished = SingleStep(method_name="deck.pump.dose", kwargs={}, start_time=datetime.now(),
                              end_time=datetime.now(), output=1)
        left_running = SingleStep(method_name="deck.pump.slow", kwargs={}, start_time=datetime.now())
        db.session.add_all([finished, left_running])
        db.session.commit()

        assert mark_interrupted_steps() == 1

        assert left_running.run_error == INTERRUPTED
        # when it stopped is not known, and a made-up end time would give it a false duration
        assert left_running.end_time is None
        assert finished.run_error is None
        assert finished.output == 1
        # a later restart does not count it again
        assert mark_interrupted_steps() == 0
