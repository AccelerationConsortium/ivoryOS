import inspect
import json
import os
import time
from enum import Enum
from typing import List, Literal, Optional

import pytest

from ivoryos.runtime import safety
from ivoryos.runtime.safety import (Guard, SafetyViolation, check_value, describe, field_kind,
                                    guarded_fields, validate)
from ivoryos.script import Script


class SyringePump:
    def dispense(self, volume: float, rate: float = 50.0):
        return volume


class Heater:
    def __init__(self):
        self._setpoint = 25.0

    def set_temperature(self, setpoint: float, mode: str = "fast"):
        return setpoint

    @property
    def setpoint(self) -> float:
        return self._setpoint

    @setpoint.setter
    def setpoint(self, value: float):
        self._setpoint = value


@pytest.fixture
def deck(monkeypatch):
    objects = {"pump": SyringePump(), "pump2": SyringePump(), "reactor": Heater()}
    monkeypatch.setattr(safety, "_live_object", lambda name: objects.get(name))
    return objects


def write(path, limits):
    path.write_text(json.dumps({"format": "ivoryos-safety/1", "limits": limits}))
    # a fresh mtime, so a guard that already read the file reads it again
    os.utime(path, (time.time() + 1, time.time() + 1))


def guard_with(tmp_path, limits):
    path = tmp_path / "safety.json"
    write(path, limits)
    return Guard(str(path))


# --- values -----------------------------------------------------------------------------------


@pytest.mark.parametrize("value, problem", [
    (5, None),
    (-1, "is below the minimum of 0 mL"),
    (12.5, "is above the maximum of 10 mL"),
    ("abc", "is not a number"),
    (float("nan"), "is not a number"),
    ("#volume", None),  # filled in by the run, checked then
    (None, None),
])
def test_values_against_a_range(value, problem):
    found = check_value({"min": 0, "max": 10, "unit": "mL"}, value)
    assert (found[0][1].startswith(problem) if problem else found == []), found


def test_lists_and_allowed_values():
    assert check_value({"max": 10}, [1, 11, 3]) == [("11", "is above the maximum of 10")]
    assert check_value({"allowed": ["rack", "reactor"]}, "rack") == []
    assert check_value({"allowed": ["rack", "reactor"]}, "floor")[0][1] == "is not allowed here (allowed: rack, reactor)"


def test_a_limit_reads_as_a_short_hint():
    assert describe({"min": 0, "max": 10, "unit": "mL"}) == "mL · 0 to 10"
    assert describe({"min": -50}) == "at least -50"
    assert describe({"allowed": ["a", "b"]}) == "one of a, b"


# --- what can be limited ----------------------------------------------------------------------


class Mode(Enum):
    SLOW = 1
    FAST = 2


@pytest.mark.parametrize("annotation, kind", [
    (float, "number"),
    (Optional[int], "number"),
    (List[float], "number"),
    (str, "text"),
    (inspect.Parameter.empty, "any"),
    (dict, "any"),
    (Mode, "fixed"),
    (Optional[Mode], "fixed"),
    (Literal["a", "b"], "fixed"),
    (bool, "fixed"),
])
def test_what_a_fields_limit_can_say(annotation, kind):
    assert field_kind(annotation) == kind


def test_choices_the_driver_fixes_get_no_shield():
    class Stirrer:
        def stir(self, speed: float, mode: Mode = Mode.SLOW, note=None): ...

        def set_mode(self, mode: Mode): ...

    from ivoryos.parsers.introspection import _inspect_class

    # set_mode has nothing to limit
    assert guarded_fields(_inspect_class(Stirrer())) == {"stir": {"speed": "number", "note": "any"}}


def test_a_property_setter_is_guarded_by_its_value():
    from ivoryos.parsers.introspection import _inspect_class

    assert guarded_fields(_inspect_class(Heater()))["setpoint_(setter)"] == {"value": "number"}


# --- the file ---------------------------------------------------------------------------------


def test_a_valid_file():
    config, errors = validate({
        "format": "ivoryos-safety/1",
        "limits": [{"target": "reactor", "method": "set_temperature", "param": "setpoint", "min": "-50", "max": 250.0}],
    })
    assert errors == []
    assert config["limits"] == [{"target": "reactor", "method": "set_temperature", "param": "setpoint", "min": -50, "max": 250}]


@pytest.mark.parametrize("limit, message", [
    ({"method": "m", "param": "p", "max": 1}, "needs an instrument"),
    ({"target": "t", "method": "m", "param": "p"}, "sets nothing"),
    ({"target": "t", "method": "m", "param": "p", "min": 5, "max": 1}, "minimum (5) is above the maximum (1)"),
    ({"target": "t", "method": "m", "param": "p", "max": "hot"}, "must be a number"),
    ({"target": "t", "method": "m", "param": "p", "allowed": []}, "at least one value"),
])
def test_limits_that_cannot_be_used(limit, message):
    _, errors = validate({"limits": [limit]})
    assert message in errors[0]["message"]


# --- the guard --------------------------------------------------------------------------------


def test_no_file_limits_nothing(tmp_path, deck):
    guard = Guard(str(tmp_path / "safety.json"))
    assert guard.check_call("deck.pump", "dispense", {"volume": 1e9}) == []


def test_a_limit_belongs_to_its_instrument(tmp_path, deck):
    guard = guard_with(tmp_path, [{"target": "pump", "method": "dispense", "param": "volume", "max": 10, "unit": "mL"}])

    assert guard.check_call("deck.pump", "dispense", {"volume": 20}) == [
        "pump.dispense: volume = 20 is above the maximum of 10 mL."]
    # another pump of the same model has limits of its own
    assert guard.check_call("deck.pump2", "dispense", {"volume": 20}) == []


def test_a_left_out_argument_is_checked_at_its_default(tmp_path, deck):
    guard = guard_with(tmp_path, [{"target": "pump", "method": "dispense", "param": "rate", "max": 20}])

    assert guard.check_call("deck.pump", "dispense", {"volume": 1}) == [
        "pump.dispense: rate = 50 is above the maximum of 20."]


def test_a_property_setter_is_limited_on_its_value(tmp_path, deck):
    guard = guard_with(tmp_path, [{"target": "reactor", "method": "setpoint_(setter)", "param": "value", "max": 250}])

    assert guard.check_call("deck.reactor", "setpoint_(setter)", {"value": 300})


def test_a_refused_call_raises(tmp_path, deck):
    guard = guard_with(tmp_path, [{"target": "reactor", "method": "set_temperature", "param": "setpoint", "min": -50, "max": 250}])

    with pytest.raises(SafetyViolation) as refused:
        guard.enforce("deck.reactor", "set_temperature", {"setpoint": 300})

    assert str(refused.value) == "Safety guard: reactor.set_temperature: setpoint = 300 is above the maximum of 250."


def test_a_file_that_cannot_be_read_blocks_every_call(tmp_path, deck):
    path = tmp_path / "safety.json"
    path.write_text("{ not json")
    guard = Guard(str(path))

    [problem] = guard.check_call("deck.pump", "dispense", {"volume": 1})
    assert "cannot be read" in problem and "Every call is blocked" in problem
    assert guard.save_limit("deck.pump", "dispense", "volume", {"max": 1})[0]["message"].endswith(
        "Fix or delete the file before saving here.")


def test_a_hand_edit_applies_without_a_restart(tmp_path, deck):
    guard = guard_with(tmp_path, [{"target": "pump", "method": "dispense", "param": "volume", "max": 10}])
    assert guard.check_call("deck.pump", "dispense", {"volume": 5}) == []

    write(tmp_path / "safety.json", [{"target": "pump", "method": "dispense", "param": "volume", "max": 1}])
    assert guard.check_call("deck.pump", "dispense", {"volume": 5})


def workflow():
    script = Script(author="tester")
    script.script_dict["script"] = [
        {"id": 1, "instrument": "deck.reactor", "action": "set_temperature", "args": {"setpoint": 300}, "arg_types": {}},
        {"id": 2, "instrument": "deck.pump", "action": "dispense", "args": {"volume": "#volume"}, "arg_types": {}},
        {"id": 3, "instrument": "wait", "action": "wait", "args": {"statement": 5}, "arg_types": {}},
    ]
    return script


def test_a_run_is_checked_before_it_starts(tmp_path, deck):
    guard = guard_with(tmp_path, [
        {"target": "reactor", "method": "set_temperature", "param": "setpoint", "max": 250, "unit": "°C"},
        {"target": "pump", "method": "dispense", "param": "volume", "min": 0, "max": 10, "unit": "mL"},
    ])
    script = workflow()

    assert guard.check_steps(script) == ["Step 1, reactor.set_temperature: setpoint = 300 is above the maximum of 250 °C."]
    columns = guard.column_limits(script)
    assert list(columns) == ["volume"] and columns["volume"][0]["source"] == "pump.dispense.volume"
    assert guard.check_rows(script, [{"volume": 5}, {"volume": 20}]) == [
        "Row 2, 'volume': 20 is above the maximum of 10 mL."]
    assert guard.check_search_space(script, [{"name": "volume", "type": "range", "bounds": [0, 50]}]) == [
        "volume: 50 is above the maximum of 10 mL (pump.dispense.volume)."]


# --- saving from a field's shield --------------------------------------------------------------


def test_a_fields_limit_is_set_changed_and_removed(tmp_path, deck):
    guard = guard_with(tmp_path, [{"target": "reactor", "method": "set_temperature", "param": "setpoint", "max": 250}])

    assert guard.save_limit("deck.pump", "dispense", "volume", {"min": 0, "max": 10, "unit": "mL"}) == []
    assert guard.save_limit("deck.pump", "dispense", "volume", {"max": 5, "unit": "mL"}) == []
    assert guard.limits_for("deck.pump") == {"dispense": {"volume": {"max": 5, "unit": "mL"}}}
    # other fields' limits are left as they were
    assert guard.limits_for("deck.reactor") == {"set_temperature": {"setpoint": {"max": 250}}}
    assert json.loads((tmp_path / "safety.json").read_text())["format"] == "ivoryos-safety/1"

    assert guard.save_limit("deck.pump", "dispense", "volume", {}) == []
    assert guard.limits_for("deck.pump") == {}


def test_each_field_says_what_its_shield_shows(tmp_path, deck):
    from ivoryos.parsers.introspection import _inspect_class

    guard = guard_with(tmp_path, [{"target": "pump", "method": "dispense", "param": "volume", "max": 10}])

    assert guard.field_guards("deck.pump", _inspect_class(SyringePump())) == {"dispense": {
        "volume": {"kind": "number", "limit": {"max": 10}},
        "rate": {"kind": "number", "limit": {}},
    }}


def test_an_invalid_limit_changes_nothing_and_says_which_field(tmp_path, deck):
    guard = guard_with(tmp_path, [{"target": "pump", "method": "dispense", "param": "volume", "max": 10}])
    before = (tmp_path / "safety.json").read_text()

    [error] = guard.save_limit("deck.pump", "dispense", "volume", {"min": 5, "max": 1})

    assert (error["method"], error["param"]) == ("dispense", "volume")
    assert (tmp_path / "safety.json").read_text() == before
