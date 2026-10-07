import asyncio
from unittest.mock import MagicMock

import pytest

from ivoryos.runtime.live_config import LiveConfig, describe
from ivoryos.runtime.script_runner import ScriptRunner

ARG_TYPES = {"temperature": "float", "solvent": "str"}


def make_live(*rows, converted=False):
    return LiveConfig([dict(row) for row in rows], ARG_TYPES, converted=converted)


def row(temperature, solvent):
    return {"temperature": temperature, "solvent": solvent}


def editable(live, *values):
    """The running and pending rows as the editor sends them.

    ``values`` replace theirs in order; ``None`` leaves a row out, which removes
    it, and rows past the end of ``values`` are sent as they are.
    """
    view = live.view()
    rows = [entry for entry in view["rows"] if entry["status"] in ("running", "pending")]
    sent = []
    for position, entry in enumerate(rows, start=1):
        new = values[position - 1] if position <= len(values) else dict(zip(view["fields"], entry["values"]))
        if new is not None:
            sent.append({"id": entry["id"], "values": new, "number": position})
    return sent


# --- the live table ----------------------------------------------------------


def test_rows_are_converted_and_started_one_batch_at_a_time():
    live = make_live(row("25", "water"), row("40", "ethanol"), row("60", "toluene"))

    batch, failed = live.start_batch(2)

    assert failed == []
    assert [entry["values"] for entry in batch] == [row(25.0, "water"), row(40.0, "ethanol")]
    assert live.waiting() == 1
    assert [entry["status"] for entry in live.view()["rows"]] == ["running", "running", "pending"]

    live.finish_batch(batch)
    batch, _ = live.start_batch(2)
    assert live.inputs(batch) == [row(60.0, "toluene")]
    assert live.waiting() == 0


def test_a_row_that_cannot_run_fails_on_its_own_with_the_reason():
    live = make_live(row("25", "water"), row("hot", "ethanol"), row("60", "toluene"))

    assert [number for number, _ in live.problems()] == [2]

    first, _ = live.start_batch(1)
    live.finish_batch(first)
    second, failed = live.start_batch(1)

    [(number, entry)] = failed
    assert number == 2 and "hot" in entry["reason"] and list(entry["invalid"]) == ["temperature"]
    assert entry["text"] == row("hot", "ethanol")
    assert live.inputs(second) == [row(60.0, "toluene")]
    assert live.view()["counts"] == {"pending": 0, "running": 1, "done": 1, "stopped": 0, "failed": 1}


def test_converted_rows_from_the_api_are_used_as_they_are():
    original = {"temperature": 25.5, "solvent": "water", "note": "extra keys pass through"}
    live = LiveConfig([original], ARG_TYPES, converted=True)

    batch, failed = live.start_batch(1)

    assert failed == [] and batch[0]["values"] is original


def test_waiting_rows_can_be_edited_added_removed_and_reordered():
    live = make_live(row("25", "water"), row("40", "ethanol"), row("60", "toluene"))
    first, _ = live.start_batch(1)
    running, ethanol, toluene = [entry["id"] for entry in live.view()["rows"]]

    changes, notes = live.edit([
        {"id": running, "values": row("25", "water"), "number": 1},
        {"id": toluene, "values": row("65", "toluene"), "number": 2},
        {"id": None, "values": row("80", "hexane"), "number": 3},
        {"id": None, "values": row("", ""), "number": 4},  # added and never filled in
    ])

    assert notes == []
    assert [describe(change) for change in changes] == [
        "Row 2 removed: temperature='40', solvent='ethanol'",
        "Row 2: 'temperature' changed from '60' to '65'",
        "Row 3 added: temperature='80', solvent='hexane'",
    ]
    assert [entry["values"] for entry in live.view()["rows"]] == [
        ["25", "water"], ["65", "toluene"], ["80", "hexane"],
    ]
    assert live.waiting() == 2

    live.finish_batch(first)
    assert live.inputs(live.start_batch(1)[0]) == [row(65.0, "toluene")]


def test_an_edit_with_a_value_that_cannot_run_changes_nothing():
    live = make_live(row("25", "water"), row("40", "ethanol"))
    before = live.view()

    with pytest.raises(ValueError, match="Row 2"):
        live.edit([
            {"id": 1, "values": row("30", "water"), "number": 1},
            {"id": 2, "values": row("warm", "ethanol"), "number": 2},
        ])

    assert live.view() == before


def test_edits_to_the_running_row_reach_only_the_steps_still_to_run():
    live = make_live(row("25", "water"), row("40", "ethanol"))
    batch, _ = live.start_batch(1)
    context = batch[0]["values"]

    live.edit(editable(live, row("30", "water")))
    # saved, shown in the editor, but not handed to the steps until the next one starts
    assert context["temperature"] == 25.0
    assert live.view()["rows"][0]["values"] == ["30", "water"]

    assert live.apply_running_edits() == ["Row 1: 'temperature' is now '30' for the steps still to run."]
    assert context["temperature"] == 30.0
    assert live.edited_while_running(batch)

    live.edit(editable(live, row("35", "water")))
    # a change after the last step is reported and the row keeps what it ran with
    assert live.finish_batch(batch) == [
        "Row 1: the change of 'temperature' to '35' came after its last step, so it was not used."]
    assert live.inputs(batch) == [row(30.0, "water")]


def test_rows_that_finished_meanwhile_are_left_as_they_ran():
    live = make_live(row("25", "water"), row("40", "ethanol"))
    first, _ = live.start_batch(1)
    stale = editable(live, row("26", "water"), row("40", "ethanol"))
    live.finish_batch(first)
    second, _ = live.start_batch(1)

    # the editor still holds row 1 as running and drops row 2, which is running now
    changes, notes = live.edit([stale[0]])

    assert changes == []
    assert notes == ["Row 1 finished before the changes were saved, so it ran as it was.",
                     "Row 2 is running, so it was not removed."]
    assert live.inputs(first) == [row(25.0, "water")]


def test_values_that_cannot_run_are_marked_where_they_are():
    live = make_live(row("25", "water"), row("3er", "ethanol"))

    view = live.view()["rows"]
    assert view[0]["invalid"] == {} and list(view[1]["invalid"]) == ["temperature"]


def test_rows_still_running_when_the_run_ends_are_marked_failed_and_the_rest_left():
    live = make_live(row("25", "water"), row("40", "ethanol"))
    live.start_batch(1)

    live.close()

    assert [entry["status"] for entry in live.view()["rows"]] == ["failed", "pending"]
    assert live.remaining() == [row("40", "ethanol")]


# --- the runner: the iterations are the record of the table -----------------


class FakePhase:
    def __init__(self, **fields):
        self.status = self.error = self.outputs = self.end_time = None
        self.__dict__.update(fields)


class FakeSession:
    """Just enough of a session for the config loop: phases kept in order."""

    def __init__(self):
        self.phases = []

    def add(self, phase):
        self.phases.append(phase)
        phase.id = len(self.phases)

    def get(self, model, phase_id):
        return self.phases[phase_id - 1]

    def flush(self):
        pass

    commit = rollback = flush


def run_config_section(runner, config, exec_steps):
    runner.exec_steps = exec_steps
    return asyncio.run(runner._run_config_section(
        config, ARG_TYPES, [], MagicMock(), "flow", 1, "flow.csv", [], "", compiled=False, batch_size=1))


@pytest.fixture
def runner(monkeypatch):
    from types import SimpleNamespace
    from ivoryos.runtime import script_runner_workflow

    runner = ScriptRunner()
    runner.logger = MagicMock()
    runner.socketio = MagicMock()
    runner._emit_progress = MagicMock()
    runner.run_events = []  # a run in progress, not saved anywhere
    session = FakeSession()
    monkeypatch.setattr(script_runner_workflow, "WorkflowPhase", FakePhase)
    monkeypatch.setattr(script_runner_workflow, "db", SimpleNamespace(session=session))
    runner.phases = session.phases
    return runner


def finished():
    async def steps(script, section, phase_id, kwargs_list=None, batch_size=1):
        return kwargs_list
    return steps


def test_every_row_reached_becomes_an_iteration_in_order_a_failed_one_included(runner):
    ran = []

    async def exec_steps(script, section, phase_id, kwargs_list=None, batch_size=1):
        ran.extend(dict(kwargs) for kwargs in kwargs_list)
        return kwargs_list

    run_config_section(runner, [row("25", "water"), row("hot", "ethanol"), row("60", "toluene")], exec_steps)

    assert ran == [row(25.0, "water"), row(60.0, "toluene")]
    assert [(phase.repeat_index, phase.status) for phase in runner.phases] == [(1, "done"), (2, "failed"), (3, "done")]
    failed = runner.phases[1]
    assert failed.parameters == [row("hot", "ethanol")]
    assert "hot" in failed.error["message"] and list(failed.error["fields"]) == ["temperature"]
    notices = [call.args[1] for call in runner.socketio.emit.call_args_list if call.args[0] == "notice"]
    # once when the run starts, while it can still be fixed, and once when it fails
    assert [notice["title"] for notice in notices] == ["Some rows can't run as entered", "Row failed"]
    assert runner.live_config is None


def test_an_iteration_keeps_the_values_its_last_steps_used(runner):
    async def exec_steps(script, section, phase_id, kwargs_list=None, batch_size=1):
        live = runner.live_config
        if kwargs_list[0]["solvent"] == "water":
            live.edit(editable(live, row("30", "water"), row("45", "ethanol")))
            runner._apply_live_row_edits()  # the next step starts
        return kwargs_list

    run_config_section(runner, [row("25", "water"), row("40", "ethanol")], exec_steps)

    assert [phase.parameters for phase in runner.phases] == [[row(30.0, "water")], [row(45.0, "ethanol")]]


def test_rows_left_by_a_graceful_stop_are_kept_with_an_event(runner):
    async def exec_steps(script, section, phase_id, kwargs_list=None, batch_size=1):
        runner.stop_pending_event.set()  # "stop after this iteration" during row 1
        return kwargs_list

    runner._cut_short = False
    run_config_section(runner, [row("25", "water"), row("40", "ethanol")], exec_steps)

    assert [phase.status for phase in runner.phases] == ["done"]
    assert runner._cut_short
    [left] = runner.run_events
    assert (left["kind"], left["rows"]) == ("rows_not_run", [row("40", "ethanol")])


def test_a_graceful_stop_during_the_last_row_still_completes(runner):
    async def exec_steps(script, section, phase_id, kwargs_list=None, batch_size=1):
        runner.stop_pending_event.set()
        return kwargs_list

    runner._cut_short = False
    run_config_section(runner, [row("25", "water")], exec_steps)

    assert not runner._cut_short and runner.run_events == []


def test_an_iteration_is_stopped_only_when_a_stop_cut_off_its_steps(runner):
    async def stop_during_last_step(script, section, phase_id, kwargs_list=None, batch_size=1):
        runner.stop_current_event.set()  # no step was left to skip
        return kwargs_list

    async def stop_with_steps_left(script, section, phase_id, kwargs_list=None, batch_size=1):
        runner.stop_current_event.set()
        runner._halted()  # the next step sees the stop and is skipped
        return kwargs_list

    run_config_section(runner, [row("25", "water")], stop_during_last_step)
    run_config_section(runner, [row("25", "water")], stop_with_steps_left)

    assert [phase.status for phase in runner.phases] == ["done", "stopped"]


def test_an_iteration_whose_steps_raise_is_kept_as_failed(runner):
    async def exec_steps(script, section, phase_id, kwargs_list=None, batch_size=1):
        raise RuntimeError("pump jammed")

    with pytest.raises(RuntimeError):
        run_config_section(runner, [row("25", "water"), row("40", "ethanol")], exec_steps)

    [phase] = runner.phases
    assert (phase.status, phase.error) == ("failed", {"message": "pump jammed"})
    assert runner.run_events[0]["rows"] == [row("40", "ethanol")]


def test_open_pages_are_told_while_the_running_table_can_be_edited(runner):
    run_config_section(runner, [row("25", "water")], finished())

    told = [call.args[1]["editable"] for call in runner.socketio.emit.call_args_list if call.args[0] == "live_config"]
    assert told == [True, False]


def test_row_edits_wait_while_a_shared_step_runs_nested_steps():
    runner = ScriptRunner()
    runner.logger = None
    live = make_live(row("25", "water"))
    batch, _ = live.start_batch(1)
    runner.live_config = live
    live.edit(editable(live, row("30", "water")))

    runner._shared_step_depth = 1
    runner._apply_live_row_edits()
    assert batch[0]["values"]["temperature"] == 25.0

    runner._shared_step_depth = 0
    runner._apply_live_row_edits()
    assert batch[0]["values"]["temperature"] == 30.0


def test_runner_hands_out_the_running_table_only_to_its_own_task_and_keeps_its_edits():
    runner = ScriptRunner()
    runner.logger = MagicMock()
    assert runner.get_running_config() is None

    runner.current_task = {"uid": "abc", "run_name": "flow", "batch_size": 1}
    runner.live_config = make_live(row("25", "water"))
    runner.run_events = []
    table = runner.get_running_config()
    assert (table["uid"], table["name"], table["rows"][0]["values"]) == ("abc", "flow", ["25", "water"])

    assert runner.edit_running_config("other", []) is None
    assert runner.edit_running_config("abc", editable(runner.live_config, row("30", "water"))) == []
    runner.logger.info.assert_called_with("Config table edited: Row 1: 'temperature' changed from '25' to '30'")
    [edited] = runner.run_events
    assert edited["kind"] == "table_edited"
    assert edited["detail"] == "Row 1: 'temperature' changed from '25' to '30'"
    assert [(change["field"], change["from"], change["to"]) for change in edited["changes"]] == [("temperature", "25", "30")]


# --- run outcomes and the user's actions --------------------------------------


def test_run_outcomes():
    from ivoryos.runtime.run_events import outcome
    assert outcome(error=False, cut_short=False, stopped=False) == "completed"
    assert outcome(error=False, cut_short=True, stopped=False) == "stopped"
    assert outcome(error=False, cut_short=False, stopped=True) == "stopped"
    assert outcome(error=True, cut_short=True, stopped=True) == "error"


def test_the_users_actions_are_recorded_only_while_a_run_is_in_progress(monkeypatch):
    from ivoryos import socket_handlers

    monkeypatch.setattr(socket_handlers, "socketio", MagicMock())
    for name in ("abort_pending", "abort_cleanup", "stop_execution", "toggle_pause"):
        monkeypatch.setattr(socket_handlers.runner, name, MagicMock(return_value="Paused"))

    monkeypatch.setattr(socket_handlers.runner, "run_events", None)
    socket_handlers.pause()
    assert socket_handlers.runner.run_events is None

    monkeypatch.setattr(socket_handlers.runner, "run_events", [])
    socket_handlers.pause()
    socket_handlers.abort_pending()
    socket_handlers.abort_cleanup()
    socket_handlers.abort_current(cleanup=True)
    assert [(event["kind"], event["detail"]) for event in socket_handlers.runner.run_events] == [
        ("paused", None), ("stop_after_iteration", None), ("cleanup_skipped", None), ("stop_now", "Cleanup will run."),
    ]
