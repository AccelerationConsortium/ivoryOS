import asyncio
from unittest.mock import MagicMock

import pytest

from ivoryos.runtime import live_config as live_module
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


def test_rows_are_converted_and_started_one_batch_at_a_time():
    live = make_live(row("25", "water"), row("40", "ethanol"), row("60", "toluene"))

    batch, skipped = live.start_batch(2)

    assert skipped == []
    assert [entry["values"] for entry in batch] == [row(25.0, "water"), row(40.0, "ethanol")]
    assert live.progress(2) == (1, 2)
    assert [entry["status"] for entry in live.view()["rows"]] == ["running", "running", "pending"]

    live.finish_batch(batch)
    batch, _ = live.start_batch(2)
    assert live.inputs(batch) == [row(60.0, "toluene")]
    assert live.progress(2) == (2, 2)


def test_a_row_that_cannot_run_is_skipped_on_its_own_with_the_reason():
    live = make_live(row("25", "water"), row("hot", "ethanol"), row("60", "toluene"))

    assert [number for number, _ in live.problems()] == [2]

    first, _ = live.start_batch(1)
    live.finish_batch(first)
    second, skipped = live.start_batch(1)

    assert [number for number, _ in skipped] == [2]
    assert "hot" in skipped[0][1]
    assert live.inputs(second) == [row(60.0, "toluene")]
    assert live.view()["counts"] == {"pending": 0, "running": 1, "done": 1, "skipped": 1, "stopped": 0, "error": 0}


def test_converted_rows_from_the_api_are_used_as_they_are():
    original = {"temperature": 25.5, "solvent": "water", "note": "extra keys pass through"}
    live = LiveConfig([original], ARG_TYPES, converted=True)

    batch, skipped = live.start_batch(1)

    assert skipped == [] and batch[0]["values"] is original


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
    # the total moves with the table; the iteration already started stays counted
    assert live.progress(1) == (1, 3)

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

    assert live.view() == before and live.changes == []


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
    assert [change.get("used") for change in live.changes] == [True, False]


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


def test_history_keeps_the_final_and_submitted_tables_and_the_changes():
    live = LiveConfig([row("25", "water"), row("hot", "ethanol"), row("60", "toluene"), row("70", "water")],
                      ARG_TYPES, outputs=["yield_pct"])

    batch, _ = live.start_batch(1)
    batch[0]["values"]["yield_pct"] = 0.9  # what the steps returned
    live.finish_batch(batch)
    batch, skipped = live.start_batch(1)
    live.edit(editable(live, row("65", "toluene")))
    live.apply_running_edits()
    live.finish_batch(batch, stopped=True)

    history = live.history()
    assert history["initial"] == [row("25", "water"), row("hot", "ethanol"), row("60", "toluene"), row("70", "water")]
    assert [(entry["status"], entry["iteration"], entry["values"], entry["outputs"]) for entry in history["final"]] == [
        ("done", 1, row(25.0, "water"), {"yield_pct": 0.9}),
        ("skipped", None, row("hot", "ethanol"), {}),
        ("stopped", 2, row(65.0, "toluene"), {}),
        ("pending", None, row("70", "water"), {}),
    ]
    assert "hot" in history["final"][1]["reason"]
    assert [change["action"] for change in history["changes"]] == ["edit"]


def test_rows_still_running_when_the_run_ends_are_marked_as_failed():
    live = make_live(row("25", "water"), row("40", "ethanol"))
    live.start_batch(1)

    live.close()

    assert [entry["status"] for entry in live.history()["final"]] == ["error", "pending"]


def run_config_section(runner, config, exec_steps):
    runner.exec_steps = exec_steps
    return asyncio.run(runner._run_config_section(
        config, ARG_TYPES, [], MagicMock(), "flow", 1, "flow.csv", [], "", compiled=False, batch_size=1))


@pytest.fixture
def runner(monkeypatch):
    from ivoryos.runtime import script_runner_workflow

    runner = ScriptRunner()
    runner.logger = MagicMock()
    runner.socketio = MagicMock()
    runner._emit_progress = MagicMock()
    phases = []
    monkeypatch.setattr(script_runner_workflow, "WorkflowPhase", lambda **kwargs: phases.append(kwargs) or MagicMock(**kwargs))
    monkeypatch.setattr(script_runner_workflow, "db", MagicMock())
    runner.phases = phases
    return runner


def test_a_bad_row_no_longer_keeps_the_rest_of_the_table_from_running(runner):
    ran = []

    async def exec_steps(script, section, phase_id, kwargs_list=None, batch_size=1):
        ran.extend(dict(kwargs) for kwargs in kwargs_list)
        return kwargs_list

    run_config_section(runner, [row("25", "water"), row("hot", "ethanol"), row("60", "toluene")], exec_steps)

    assert ran == [row(25.0, "water"), row(60.0, "toluene")]
    notices = [call.args[1] for call in runner.socketio.emit.call_args_list if call.args[0] == "notice"]
    # once when the run starts, while it can still be fixed, and once when it is skipped
    assert [notice["title"] for notice in notices] == ["Some rows can't run as entered", "Row skipped"]
    assert all("Row 2" in notice["message"] for notice in notices)
    assert runner.live_config is None


def test_mid_run_edits_are_recorded_with_the_values_the_row_finished_with(runner):
    async def exec_steps(script, section, phase_id, kwargs_list=None, batch_size=1):
        live = runner.live_config
        if kwargs_list[0]["solvent"] == "water":
            live.edit(editable(live, row("30", "water"), row("45", "ethanol")))
            runner._apply_live_row_edits()  # the next step starts
        return kwargs_list

    run_config_section(runner, [row("25", "water"), row("40", "ethanol")], exec_steps)

    assert [phase["parameters"] for phase in runner.phases] == [[row(25.0, "water")], [row(45.0, "ethanol")]]
    from ivoryos.runtime import script_runner_workflow
    run = script_runner_workflow.db.session.get.return_value
    assert [entry["values"] for entry in run.config_history["final"]] == [row(30.0, "water"), row(45.0, "ethanol")]


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


def test_runner_hands_out_the_running_table_only_to_its_own_task():
    runner = ScriptRunner()
    runner.logger = MagicMock()
    assert runner.get_running_config() is None

    runner.current_task = {"uid": "abc", "run_name": "flow", "batch_size": 1}
    runner.live_config = make_live(row("25", "water"))
    table = runner.get_running_config()
    assert (table["uid"], table["name"], table["rows"][0]["values"]) == ("abc", "flow", ["25", "water"])

    assert runner.edit_running_config("other", []) is None
    assert runner.edit_running_config("abc", editable(runner.live_config, row("30", "water"))) == []
    runner.logger.info.assert_called_with("Config table edited: Row 1: 'temperature' changed from '25' to '30'")


def test_a_graceful_stop_leaves_the_rest_of_the_table_not_run(runner):
    async def exec_steps(script, section, phase_id, kwargs_list=None, batch_size=1):
        runner.stop_pending_event.set()  # "stop after this iteration" during row 1
        return kwargs_list

    runner._cut_short = False
    run_config_section(runner, [row("25", "water"), row("40", "ethanol")], exec_steps)

    from ivoryos.runtime import script_runner_workflow
    final = script_runner_workflow.db.session.get.return_value.config_history["final"]
    assert [entry["status"] for entry in final] == ["done", "pending"]
    assert runner._cut_short


def test_a_graceful_stop_during_the_last_row_still_completes(runner):
    async def exec_steps(script, section, phase_id, kwargs_list=None, batch_size=1):
        runner.stop_pending_event.set()
        return kwargs_list

    runner._cut_short = False
    run_config_section(runner, [row("25", "water")], exec_steps)

    assert not runner._cut_short


def test_a_row_is_marked_stopped_only_when_a_stop_cut_off_its_steps(runner):
    from ivoryos.runtime import script_runner_workflow
    run = script_runner_workflow.db.session.get.return_value

    async def stop_during_last_step(script, section, phase_id, kwargs_list=None, batch_size=1):
        runner.stop_current_event.set()  # no step was left to skip
        return kwargs_list

    async def stop_with_steps_left(script, section, phase_id, kwargs_list=None, batch_size=1):
        runner.stop_current_event.set()
        runner._halted()  # the next step sees the stop and is skipped
        return kwargs_list

    run_config_section(runner, [row("25", "water")], stop_during_last_step)
    assert run.config_history["final"][0]["status"] == "done"

    run_config_section(runner, [row("25", "water")], stop_with_steps_left)
    assert run.config_history["final"][0]["status"] == "stopped"


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


def test_open_pages_are_told_while_the_running_table_can_be_edited(runner):
    async def exec_steps(script, section, phase_id, kwargs_list=None, batch_size=1):
        return kwargs_list

    run_config_section(runner, [row("25", "water")], exec_steps)

    told = [call.args[1]["editable"] for call in runner.socketio.emit.call_args_list if call.args[0] == "live_config"]
    assert told == [True, False]


def test_values_that_cannot_run_are_marked_where_they_are():
    live = make_live(row("25", "water"), row("3er", "ethanol"))

    view = live.view()["rows"]
    assert view[0]["invalid"] == {} and list(view[1]["invalid"]) == ["temperature"]

    first, _ = live.start_batch(1)
    live.finish_batch(first)
    live.start_batch(1)
    skipped = live.history()["final"][1]
    assert skipped["status"] == "skipped" and list(skipped["invalid"]) == ["temperature"]
