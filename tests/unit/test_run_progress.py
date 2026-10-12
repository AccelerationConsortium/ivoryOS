from types import SimpleNamespace

from ivoryos.runtime import run_events
from ivoryos.runtime.live_config import LiveConfig
from ivoryos.runtime.run_progress import RunProgress, state_of

SCRIPT = SimpleNamespace(script_dict={"prep": [{}, {}], "script": [{}, {}, {}], "cleanup": [{}]})


def started(iterations=3):
    progress = RunProgress()
    progress.start("task-1", "flow", SCRIPT, iterations=iterations)
    return progress


def test_a_page_is_told_the_steps_of_each_phase_and_the_iterations_planned():
    snapshot = started().snapshot()

    assert snapshot["uid"] == "task-1" and snapshot["state"] == "running"
    assert snapshot["steps"] == {"prep": 2, "script": 3, "cleanup": 1}
    assert snapshot["iterations"] == 3 and snapshot["phase"] is None


def test_only_the_phases_own_steps_move_it_and_a_loop_never_moves_it_back():
    progress = started()
    progress.start_iteration(1)

    assert progress.at_step("script", 2)
    # a workflow called by step 2 runs under a section of its own
    assert not progress.at_step("script-1", 5)
    # a repeat block going round again
    assert not progress.at_step("script", 1)
    assert progress.snapshot()["step"] == 2
    # the next iteration starts from its first step
    progress.start_iteration(2)
    assert progress.snapshot()["step"] == 0 and progress.at_step("script", 1)


def test_cleanup_counts_only_the_iterations_that_ran():
    progress = started(iterations=10)
    progress.start_iteration(3)  # a stop after the third

    progress.enter_phase("cleanup")

    assert progress.snapshot()["iterations"] == 3


def test_a_config_table_sets_the_iterations_from_its_rows_and_an_edit_moves_them():
    live = LiveConfig([{"x": "1"}, {"x": "2"}, {"x": "3"}], {"x": "int"})
    progress = started(iterations=3)
    progress.follow_table(live, batch_size=2)
    assert progress.snapshot()["iterations"] == 2  # two batches: rows 1-2, then row 3

    batch, _ = live.start_batch(2)
    progress.start_iteration(1)
    snapshot = progress.snapshot()
    assert snapshot["iterations"] == 2 and snapshot["table"]["running"] == [1, 2]

    view = live.view()
    rows = [{"id": entry["id"], "values": {"x": entry["values"][0]}} for entry in view["rows"]]
    live.edit(rows + [{"id": None, "values": {"x": "4"}}, {"id": None, "values": {"x": "5"}}])
    # the running batch, then rows 3-4, then row 5
    assert progress.snapshot()["iterations"] == 3


def test_a_closed_table_keeps_its_rows_as_they_ended_until_the_next_task():
    live = LiveConfig([{"x": "1"}], {"x": "int"})
    progress = started(iterations=1)
    progress.follow_table(live)
    batch, _ = live.start_batch(1)
    progress.start_iteration(1)
    live.finish_batch(batch)

    progress.close_table(live.final_state())
    progress.finish(state_of(run_events.COMPLETED))
    snapshot = progress.snapshot()

    assert snapshot["state"] == "done" and snapshot["iterations"] == 1
    assert snapshot["table"]["closed"] and [row["status"] for row in snapshot["table"]["changed"]] == ["done"]
    # the next task starts clean
    progress.start("task-2", "next", SCRIPT)
    assert "table" not in progress.snapshot() and progress.snapshot()["uid"] == "task-2"


def test_a_run_outcome_reads_as_the_bar_shows_it():
    assert state_of(run_events.COMPLETED) == "done"
    assert state_of(run_events.STOPPED) == "stopped"
    assert state_of(run_events.FAILED) == "failed"
