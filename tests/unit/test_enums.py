import json
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pytest

from ivoryos.parsers.type_conversions import convert_config_type
from ivoryos.runtime.task_runner import TaskRunner
from ivoryos.utils.enums import enum_class_of, find_member, to_members
from tests.conftest import MockEnum
from tests.unit.test_runner_missing_method import _execute, _step


class Mode(Enum):
    SLOW = 1
    FAST = 2


@dataclass(frozen=True)
class Plate:
    rows: int
    cols: int


class Plates(Enum):
    WELL_96 = Plate(8, 12)
    WELL_24 = Plate(4, 6)


@pytest.mark.parametrize("key, member", [
    ("FAST", Mode.FAST),       # the key, as the forms send it
    (2, Mode.FAST),            # the value, as JSON sends it
    ("2", Mode.FAST),          # the value as text, as an edit form sends it back
    (Mode.FAST, Mode.FAST),
    ("fast", None),
    ("#mode", None),           # a workflow input, filled in by the run
])
def test_a_member_is_found_by_its_key_or_its_value(key, member):
    assert find_member(Mode, key) is member


def test_any_value_works_since_the_key_is_what_is_kept():
    assert find_member(Plates, "WELL_96") is Plates.WELL_96
    assert find_member(Plates, Plate(8, 12)) is Plates.WELL_96
    # the key is plain text, so a step holding it saves as JSON
    assert json.loads(json.dumps({"plate": find_member(Plates, "WELL_96").name})) == {"plate": "WELL_96"}


def test_the_driver_gets_members_for_its_enum_arguments():
    def load(plate: Plates, mode: Optional[Mode] = None, count: int = 1):
        return plate

    assert enum_class_of(Optional[Mode]) is Mode
    assert to_members(load, {"plate": "WELL_24", "mode": 2, "count": 3}) == {
        "plate": Plates.WELL_24, "mode": Mode.FAST, "count": 3}
    # what names no member is passed as it is, for the driver to refuse
    assert to_members(load, {"plate": "WELL_6"}) == {"plate": "WELL_6"}


def test_a_config_cell_may_hold_the_key_or_the_value_and_the_row_keeps_the_key():
    arg_type = f"Enum:{__name__}.Mode"
    assert convert_config_type({"mode": "FAST"}, {"mode": arg_type}) == {"mode": "FAST"}
    assert convert_config_type({"mode": "2"}, {"mode": arg_type}) == {"mode": "FAST"}
    with pytest.raises(TypeError):
        convert_config_type({"mode": "fast"}, {"mode": arg_type})


def test_the_instruments_page_calls_with_the_member():
    def set_mode(mode: Mode):
        return mode

    for sent in ("FAST", 2, "2"):
        assert TaskRunner._convert_kwargs_type({"mode": sent}, set_mode) == {"mode": Mode.FAST}


def test_a_run_calls_the_driver_with_the_member(app, init_database, test_deck):
    received = []

    def enum_method(arg: MockEnum = MockEnum.OPTION_A):
        received.append(arg)

    test_deck.enum_method = enum_method

    # a step stores the key; one saved when steps stored the value holds 'B'
    for stored in ("OPTION_B", "B"):
        _, row = _execute(app, _step("enum_method", {"arg": stored}, {"arg": "Enum:tests.conftest.MockEnum"}))
        assert row.run_error is False

    assert received == [MockEnum.OPTION_B, MockEnum.OPTION_B]
