import pytest

from ivoryos.runtime.control_flow import (
    ConditionalStructureError,
    process_if_block,
    process_repeat_block,
    process_while_block,
    validate_and_nest_control_flow,
)


def step(action, uuid, instrument=None, **extra):
    return {
        "id": uuid,
        "uuid": uuid,
        "action": action,
        "instrument": instrument or action,
        "args": {},
        **extra,
    }


def test_validate_and_nest_control_flow_handles_nested_blocks():
    flat_steps = [
        step("if", 1, args={"statement": True}),
        step("repeat", 2, args={"statement": 2}),
        step("dose", 3, instrument="deck.pump"),
        step("endrepeat", 2),
        step("else", 1),
        step("while", 4, args={"statement": False}),
        step("wait", 5),
        step("endwhile", 4),
        step("endif", 1),
    ]

    nested = validate_and_nest_control_flow(flat_steps)

    assert nested[0]["action"] == "if"
    assert nested[0]["if_block"][0]["action"] == "repeat"
    assert nested[0]["if_block"][0]["repeat_block"][0]["action"] == "dose"
    assert nested[0]["else_block"][0]["action"] == "while"
    assert nested[0]["else_block"][0]["while_block"][0]["action"] == "wait"


def test_validate_and_nest_control_flow_rejects_unmatched_closing_action():
    with pytest.raises(ConditionalStructureError):
        validate_and_nest_control_flow([step("endif", 1)])


def test_validate_and_nest_control_flow_rejects_wrong_nested_closing_action():
    with pytest.raises(ConditionalStructureError):
        validate_and_nest_control_flow([
            step("repeat", 1),
            step("endif", 2),
        ])


def test_validate_and_nest_control_flow_rejects_missing_closing_actions():
    with pytest.raises(ConditionalStructureError, match="Missing 'endif'"):
        validate_and_nest_control_flow([step("if", 1)])

    with pytest.raises(ConditionalStructureError, match="Missing 'endrepeat'"):
        validate_and_nest_control_flow([step("repeat", 2)])

    with pytest.raises(ConditionalStructureError, match="Missing 'endwhile'"):
        validate_and_nest_control_flow([step("while", 3)])


def test_validate_and_nest_control_flow_rejects_mismatched_block_uuid():
    with pytest.raises(ConditionalStructureError, match="expecting else or endif"):
        validate_and_nest_control_flow([
            step("if", 1),
            step("endif", 2),
        ])


def test_process_block_helpers_return_nested_step_and_consumed_count():
    if_step, if_count = process_if_block([
        step("if", 1),
        step("dose", 3),
        step("else", 1),
        step("wait", 4),
        step("endif", 1),
    ], 0)
    repeat_step, repeat_count = process_repeat_block([
        step("repeat", 2),
        step("dose", 3),
        step("endrepeat", 2),
    ], 0)
    while_step, while_count = process_while_block([
        step("while", 5),
        step("wait", 6),
        step("endwhile", 5),
    ], 0)

    assert if_step["if_block"][0]["action"] == "dose"
    assert if_step["else_block"][0]["action"] == "wait"
    assert if_count == 5
    assert repeat_step["repeat_block"][0]["action"] == "dose"
    assert repeat_count == 3
    assert while_step["while_block"][0]["action"] == "wait"
    assert while_count == 3


def test_process_block_helper_rejects_wrong_start_action():
    with pytest.raises(ConditionalStructureError, match="Expected 'if'"):
        process_if_block([step("repeat", 1), step("endrepeat", 1)], 0)
