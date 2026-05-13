import pytest

from ivoryos.runtime.control_flow import ConditionalStructureError, validate_and_nest_control_flow


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
