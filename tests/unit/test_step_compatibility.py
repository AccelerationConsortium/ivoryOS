import inspect
from enum import Enum

import pytest

from ivoryos.parsers.introspection import _inspect_class
from ivoryos.script import Script, ScriptEditor
from ivoryos.script.compatibility import (
    METHOD_MISSING,
    MODULE_MISSING,
    PARAM_MISSING,
    PARAM_REMOVED,
    TYPE_CHANGED,
    WORKFLOW_MISSING,
    DeckReference,
    check_action,
    check_deck_match,
    check_script,
    summarize_issues,
)


class Color(Enum):
    RED = 'r'
    BLUE = 'b'


class Pump:
    """The deck module a saved workflow was built against."""

    def dispense(self, volume: float, speed: int = 5):
        return volume

    def home(self):
        return True

    def tag(self, color: Color, **extras):
        return color

    @property
    def rate(self) -> float:
        return 1.0

    @rate.setter
    def rate(self, value):
        pass

    @property
    def serial(self) -> str:
        return "abc"


class Balance:
    def dispense(self, volume: float):
        return volume


def reference(**kwargs):
    schema = {"deck.pump": _inspect_class(Pump()), "deck.balance": _inspect_class(Balance())}
    kwargs.setdefault("interface_schema", schema)
    return DeckReference(**kwargs)


def step(instrument, action, args=None, arg_types=None, **extra):
    action_dict = {
        "id": 1,
        "uuid": 1,
        "instrument": instrument,
        "action": action,
        "args": {} if args is None else args,
        "arg_types": {} if arg_types is None else arg_types,
        "return": "",
    }
    action_dict.update(extra)
    return action_dict


def codes(issues):
    return [issue["code"] for issue in issues]


def test_step_matching_the_deck_reports_nothing():
    action = step("deck.pump", "dispense", {"volume": 1.0, "speed": 5},
                  {"volume": "float", "speed": "int"})
    assert check_action(action, reference()) == []


def test_flow_control_steps_are_never_checked():
    for instrument in ("if", "while", "repeat", "wait", "pause", "comment", "variable"):
        action = step(instrument, instrument, {"statement": "True"}, {"statement": ""})
        assert check_action(action, reference()) == []


def test_missing_module_names_the_likely_rename():
    action = step("deck.pmp", "dispense", {"volume": 1.0}, {"volume": "float"})
    issues = check_action(action, reference())

    assert codes(issues) == [MODULE_MISSING]
    # module names read the way the canvas labels them, without the deck. prefix
    assert "'pump'" in issues[0]["message"]
    assert "'deck.pump'" not in issues[0]["message"]
    assert "'deck.pmp'" not in issues[0]["message"]


def test_missing_module_without_a_near_name_just_says_it_is_gone():
    action = step("deck.spectrometer", "scan")
    issues = check_action(action, reference())

    assert codes(issues) == [MODULE_MISSING]
    assert "renamed" not in issues[0]["message"]


def test_renamed_method_points_at_the_closest_name():
    action = step("deck.pump", "dispence", {"volume": 1.0}, {"volume": "float"})
    issues = check_action(action, reference())

    assert codes(issues) == [METHOD_MISSING]
    assert "'dispense'" in issues[0]["message"]


def test_method_that_moved_to_another_module_says_where_it_went():
    action = step("deck.pump", "weigh")
    balance = DeckReference(interface_schema={
        "deck.pump": _inspect_class(Pump()),
        "deck.scale": {"weigh": {"signature": None}},
    })
    issues = check_action(action, balance)

    assert codes(issues) == [METHOD_MISSING]
    assert "no longer exists on 'pump'" in issues[0]["message"]
    assert "now on scale" in issues[0]["message"]


def test_argument_the_method_no_longer_takes_is_an_error():
    action = step("deck.pump", "dispense", {"volume": 1.0, "rate": 3},
                  {"volume": "float", "rate": "int"})
    issues = check_action(action, reference())

    assert codes(issues) == [PARAM_REMOVED]
    assert issues[0]["target"] == "rate"


def test_new_required_argument_is_reported_as_missing():
    action = step("deck.pump", "dispense", {"speed": 3}, {"speed": "int"})
    issues = check_action(action, reference())

    assert codes(issues) == [PARAM_MISSING]
    assert issues[0]["target"] == "volume"


def test_new_optional_argument_is_not_reported():
    action = step("deck.pump", "dispense", {"volume": 1.0}, {"volume": "float"})
    assert check_action(action, reference()) == []


def test_changed_argument_type_is_a_warning_naming_both_types():
    action = step("deck.pump", "dispense", {"volume": 1.0}, {"volume": "int"})
    issues = check_action(action, reference())

    assert codes(issues) == [TYPE_CHANGED]
    assert issues[0]["severity"] == "warning"
    assert "was int, now float" in issues[0]["message"]


def test_enum_argument_survives_a_change_of_recorded_module_path():
    """The module recorded for an Enum depends on how the deck was imported."""
    action = step("deck.pump", "tag", {"color": "RED"}, {"color": "Enum:some_other_import.Color"})
    assert check_action(action, reference()) == []


def test_enum_argument_swapped_for_a_different_class_is_reported():
    action = step("deck.pump", "tag", {"color": "RED"}, {"color": "Enum:deck.Colour"})
    assert codes(check_action(action, reference())) == [TYPE_CHANGED]


def test_kwargs_absorb_unrecognised_arguments():
    action = step("deck.pump", "tag", {"color": "RED", "anything": 1}, {"color": "Enum:deck.Color"})
    assert check_action(action, reference()) == []


def test_property_setter_step_matches_a_property_that_still_has_a_setter():
    action = step("deck.pump", "rate_(setter)", {"value": 2.0}, {"value": "float"})
    assert check_action(action, reference()) == []


def test_property_setter_step_on_a_read_only_property_is_an_error():
    action = step("deck.pump", "serial_(setter)", {"value": "x"}, {"value": "str"})
    issues = check_action(action, reference())

    assert codes(issues) == [METHOD_MISSING]
    assert "read-only" in issues[0]["message"]


def test_property_getter_step_takes_no_arguments():
    assert check_action(step("deck.pump", "rate"), reference()) == []


def test_errors_are_listed_before_warnings():
    action = step("deck.pump", "dispense", {"volume": 1.0, "rate": 3},
                  {"volume": "int", "rate": "int"})
    issues = check_action(action, reference())

    assert codes(issues) == [PARAM_REMOVED, TYPE_CHANGED]


def test_nothing_is_reported_when_no_deck_is_loaded():
    """An empty reference means "unknown", not "everything is gone"."""
    action = step("deck.pump", "dispense", {"volume": 1.0}, {"volume": "float"})
    assert check_action(action, DeckReference()) == []


def test_building_blocks_are_not_flagged_when_none_are_registered():
    action = step("blocks.math", "add", {"a": 1}, {"a": "int"})
    assert check_action(action, reference()) == []


def test_building_block_missing_from_a_loaded_category_is_flagged():
    blocks = {"blocks.math": {"add": {"signature": None}}}
    action = step("blocks.math", "subtract", {"a": 1}, {"a": "int"})

    assert codes(check_action(action, reference(building_blocks=blocks))) == [METHOD_MISSING]


def test_legacy_step_storing_a_bare_argument_value_is_skipped():
    action = step("deck.pump", "dispense", args="#volume", arg_types="float")
    assert check_action(action, reference()) == []


def test_deleted_sub_workflow_is_a_warning_not_an_error():
    """The runner executes the copy embedded in the step, so it still runs."""
    action = step("workflows", "rinse", workflow=[])
    issues = check_action(action, reference(workflow_names={"purge"}))

    assert codes(issues) == [WORKFLOW_MISSING]
    assert issues[0]["severity"] == "warning"
    assert "copy saved with it" in issues[0]["message"]


def test_sub_workflow_steps_are_checked_against_the_deck_too():
    embedded = [step("deck.pump", "dispence", {"volume": 1.0}, {"volume": "float"})]
    action = step("workflows", "rinse", workflow=embedded)
    issues = check_action(action, reference(workflow_names={"rinse"}))

    assert codes(issues) == [METHOD_MISSING]
    assert issues[0]["message"].startswith("In 'rinse':")


def test_repeated_problems_inside_a_sub_workflow_are_reported_once():
    broken = step("deck.pump", "dispence", {"volume": 1.0}, {"volume": "float"})
    action = step("workflows", "rinse", workflow=[broken, dict(broken), dict(broken)])
    issues = check_action(action, reference(workflow_names={"rinse"}))

    assert len(issues) == 1


def test_workflow_steps_are_skipped_when_the_registry_is_unavailable():
    action = step("workflows", "rinse", workflow=[])
    assert check_action(action, reference(workflow_names=None)) == []


def test_check_script_keys_findings_by_step_uuid():
    script = Script(author="tester")
    editor = ScriptEditor(script)
    editor.add_action(step("deck.pump", "dispense", {"volume": 1.0}, {"volume": "float"}))
    editor.add_action(step("deck.pump", "dispence", {"volume": 1.0}, {"volume": "float"}))

    findings = check_script(script, reference())

    broken = script.script_dict["script"][1]
    assert set(findings) == {broken["uuid"]}
    assert codes(findings[broken["uuid"]]) == [METHOD_MISSING]


@pytest.mark.parametrize("expected,loaded,flagged", [
    ("sdl_deck", "sdl_deck", False),
    ("sdl_deck", "other_deck", True),
    (None, "sdl_deck", False),
    ("sdl_deck", None, False),
])
def test_deck_mismatch_note(expected, loaded, flagged):
    script = Script(author="tester", deck=expected)
    note = check_deck_match(script, reference(deck_name=loaded))

    assert bool(note) is flagged
    if flagged:
        assert expected in note and loaded in note


def test_deck_mismatch_note_is_silent_without_a_reference():
    script = Script(author="tester", deck="sdl_deck")
    assert check_deck_match(script, DeckReference()) is None


def test_a_renamed_argument_is_reported_once_not_as_both_removed_and_missing():
    """`analyze(param_1, param_2)` called with `param_3` is one edit, not two."""
    action = step("deck.pump", "dispense", {"volume": 1.0, "speeed": 3},
                  {"volume": "float", "speeed": "int"})
    issues = check_action(action, reference())

    assert codes(issues) == [PARAM_REMOVED]
    assert "It now takes 'speed'" in issues[0]["message"]


def test_a_missing_argument_unrelated_to_any_rename_is_still_reported():
    """Two separate findings when the names are nothing like each other."""
    signature = inspect.signature(lambda self, volume: None)
    balance = DeckReference(interface_schema={
        "deck.balance": {"wholly_different": {"signature": signature}},
    })
    action = step("deck.balance", "wholly_different", {"nothing_alike": 1}, {"nothing_alike": "int"})
    issues = check_action(action, balance)

    assert set(codes(issues)) == {PARAM_REMOVED, PARAM_MISSING}


def test_registered_workflows_are_looked_up_only_when_a_step_needs_them():
    """The lookup is a database query; most workflows embed no sub-workflow."""
    calls = []

    def loader():
        calls.append(1)
        return {"rinse"}

    deck_only = DeckReference(interface_schema={"deck.pump": _inspect_class(Pump())},
                              workflow_names_loader=loader)
    check_action(step("deck.pump", "home"), deck_only)
    assert calls == []

    check_action(step("workflows", "rinse", workflow=[]), deck_only)
    assert calls == [1]

    # and only once, however many workflow steps follow
    check_action(step("workflows", "rinse", workflow=[]), deck_only)
    assert calls == [1]


def test_summarize_merges_findings_of_the_same_kind():
    """Four sentences about four missing arguments become one short clause."""
    action = step("deck.pump", "dispense", {}, {})
    signature = inspect.signature(lambda self, a, b, c, d: None)
    strict = DeckReference(interface_schema={"deck.pump": {"dispense": {"signature": signature}}})

    assert summarize_issues(check_action(action, strict)) == "now requires a, b, c, d"


def test_summarize_keeps_different_kinds_apart():
    action = step("deck.pump", "dispense", {"volume": 1.0, "bogus": 2},
                  {"volume": "int", "bogus": "int"})

    assert summarize_issues(check_action(action, reference())) == (
        "no longer takes bogus; changed type of volume")


def test_summarize_drops_the_deck_prefix_from_a_module_name():
    action = step("deck.spectrometer", "scan")

    assert summarize_issues(check_action(action, reference())) == "missing module spectrometer"


def test_summarize_of_nothing_is_empty():
    assert summarize_issues([]) == ""
