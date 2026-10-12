import json

import pytest

from ivoryos.services import draft_history
from ivoryos.services.draft_history import Timeline, describe_change, section_to_show


def steps(*items):
    """Steps as the editor keeps them: ``id`` is the position."""
    return [{**item, "id": position} for position, item in enumerate(items, start=1)]


def step(uid, action="weigh", instrument="deck.balance", **extra):
    return {"uuid": uid, "instrument": instrument, "action": action, "args": {}, "return": "", **extra}


def draft(script=(), prep=(), cleanup=(), **fields):
    data = {"name": None, "uuid": None, "status": "editing", "description": "", "registered": False,
            "python_script": None, "editing_type": "script",
            "script_dict": {"prep": steps(*prep), "script": steps(*script), "cleanup": steps(*cleanup)}}
    data.update(fields)
    return data


def state(data):
    return json.dumps(data)


# ---- the timeline -------------------------------------------------------------------------

def test_a_change_can_be_undone_and_redone():
    timeline = Timeline()
    empty, one = draft(), draft(script=[step(1)])

    assert timeline.record(state(empty), state(one)) is True
    assert timeline.summary()["undo_label"] == "Add balance.weigh"

    restored, message = timeline.move(timeline.index - 1)
    assert json.loads(restored)["script_dict"] == empty["script_dict"]
    assert message == "Undid Add balance.weigh"
    assert timeline.summary()["redo_label"] == "Add balance.weigh"

    restored, message = timeline.move(timeline.index + 1)
    assert json.loads(restored)["script_dict"] == one["script_dict"]
    assert message == "Redid Add balance.weigh"


def test_nothing_to_undo_on_a_new_timeline():
    timeline = Timeline()
    assert not timeline.can_undo and not timeline.can_redo
    assert timeline.move(-1) == (None, None)


def test_a_change_after_an_undo_drops_what_was_undone():
    timeline = Timeline()
    a, b, c = draft(), draft(script=[step(1)]), draft(script=[step(1), step(2, "tare")])
    timeline.record(state(a), state(b))
    timeline.record(state(b), state(c))
    timeline.move(1)

    timeline.record(state(b), state(draft(script=[step(1), step(3, "zero")])))

    assert [entry["label"] for entry in timeline.entries] == ["Start", "Add balance.weigh", "Add balance.zero"]
    assert not timeline.can_redo


def test_switching_tabs_or_saving_again_is_not_a_change_to_undo():
    timeline = Timeline()
    one = draft(script=[step(1)])
    timeline.record(state(draft()), state(one))

    assert timeline.record(state(one), state({**one, "editing_type": "prep"})) is False
    assert timeline.record(state(one), state({**one, "last_modified": "later"})) is False
    assert len(timeline.entries) == 2
    # the current point follows the draft, so undo and redo come back to the tab last used
    assert json.loads(timeline.entries[1]["state"])["editing_type"] == "script"


def test_a_save_that_was_not_recorded_is_part_of_the_current_point():
    timeline = Timeline()
    one = draft(script=[step(1)])
    timeline.record(state(draft()), state(one))
    timeline.amend(state({**one, "deck": "lab_deck"}))

    restored, _ = timeline.move(0)
    restored, _ = timeline.move(1)
    assert json.loads(restored)["deck"] == "lab_deck"


def test_the_oldest_changes_go_once_the_history_is_full(monkeypatch):
    monkeypatch.setattr(draft_history, "MAX_HISTORY", 3)
    timeline = Timeline()
    states = [draft(script=[step(i) for i in range(1, n + 1)]) for n in range(6)]
    for before, after in zip(states, states[1:]):
        timeline.record(state(before), state(after))

    assert len(timeline.entries) == 4
    assert timeline.entries[0]["label"] == "Start"
    assert timeline.summary()["trimmed"] is True
    # the earliest point kept is three changes back
    restored, message = timeline.move(0)
    assert len(json.loads(restored)["script_dict"]["script"]) == 2
    assert message == "Undid 3 changes"


def test_a_restart_begins_a_new_history_with_nothing_to_undo():
    timeline = Timeline()
    timeline.record(state(draft()), state(draft(script=[step(1)])))

    opened = draft(script=[step(7, "tare")], name="flow", uuid="u")
    timeline.restart(state(opened), label="Open “flow”")

    assert not timeline.can_undo and not timeline.can_redo
    assert timeline.summary(entries=True)["entries"][0]["label"] == "Open “flow”"
    timeline.record(state(opened), state(draft(script=[step(7, "tare"), step(8)], name="flow", uuid="u")))
    restored, _ = timeline.move(0)
    assert json.loads(restored)["name"] == "flow"


def test_a_timeline_round_trips_through_its_file_form():
    timeline = Timeline()
    timeline.record(state(draft()), state(draft(script=[step(1)])))

    copy = Timeline.from_dict(json.loads(json.dumps(timeline.as_dict())))

    assert copy.summary(entries=True) == timeline.summary(entries=True)


# ---- what each change is called ---------------------------------------------------------

@pytest.mark.parametrize("before, after, label", [
    (draft(), draft(script=[step(1)]), "Add balance.weigh"),
    (draft(script=[step(1)]), draft(script=[step(1), step(2)]), "Add balance.weigh"),
    (draft(script=[step(1), step(2, "tare")]), draft(script=[step(1)]), "Delete balance.tare"),
    (draft(script=[step(1), step(2, "tare"), step(3, "zero")]),
     draft(script=[step(1), step(3, "zero"), step(2, "tare")]), "Move balance.tare"),
    (draft(script=[step(1)]), draft(script=[step(1, args={"mass": 5})]), "Edit balance.weigh"),
    (draft(script=[step(1)]), draft(script=[step(1, disabled=True)]), "Disable balance.weigh"),
    (draft(script=[step(1, disabled=True)]), draft(script=[step(1, disabled=False)]), "Enable balance.weigh"),
    (draft(), draft(script=[step(1)], name="flow", uuid="u1"), "Open “flow”"),
    (draft(script=[step(1)], name="flow", uuid="u1"), draft(), "Clear workflow"),
    (draft(script=[step(1), step(2, "tare")]), draft(), "Clear all steps"),
    (draft(), draft(script=[step(1), step(2, "tare")]), "Add 2 steps"),
    (draft(script=[step(1)]), draft(script=[step(1)], name="flow", uuid="u2"), "Save as “flow”"),
    (draft(script=[step(1)], name="a", uuid="u"), draft(script=[step(1)], name="b", uuid="u"), "Rename to “b”"),
    (draft(), draft(status="finalized"), "Lock editing"),
    (draft(), draft(description="weighs"), "Edit description"),
    (draft(), draft(python_script={"script": "x = 1"}, script=[step(1)], name="py"), "Import Python code"),
])
def test_a_change_is_named_after_what_it_did(before, after, label):
    assert describe_change(before, after) == label


def test_an_if_and_its_else_and_endif_are_one_step():
    block = [step(9, "if", "if"), step(9, "else", "if"), step(9, "endif", "if")]
    assert describe_change(draft(), draft(script=block)) == "Add If"
    assert describe_change(draft(script=block), draft()) == "Delete If"


def test_flow_control_and_variables_are_named_as_the_canvas_shows_them():
    assert describe_change(draft(), draft(script=[step(1, "x", "variable")])) == "Add variable x"
    assert describe_change(draft(), draft(script=[step(1, "total", "math_variable")])) == "Add math total"
    assert describe_change(draft(), draft(script=[step(1, "wait", "wait")])) == "Add Wait"


def test_a_change_outside_the_experiment_says_where_it_was():
    assert describe_change(draft(), draft(prep=[step(1)])) == "Add balance.weigh (Prep)"
    assert describe_change(draft(), draft(cleanup=[step(1)])) == "Add balance.weigh (Clean up)"


# ---- which tab an undo shows -------------------------------------------------------------

def test_an_undo_shows_the_tab_it_changes():
    current = draft(prep=[step(1)], editing_type="script")
    assert section_to_show(current, draft(editing_type="script")) == "prep"


def test_an_undo_stays_on_the_tab_when_it_changes_it():
    current = draft(prep=[step(1)], script=[step(2)], editing_type="script")
    assert section_to_show(current, draft(prep=[step(1)], editing_type="prep")) == "script"
