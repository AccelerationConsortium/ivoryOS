class ConditionalStructureError(Exception):
    """Raised when control-flow structure is invalid."""


CONTROL_BLOCKS = {
    "if": {
        "end": "endif",
        "body_key": "if_block",
        "else_key": "else_block",
    },
    "repeat": {
        "end": "endrepeat",
        "body_key": "repeat_block",
    },
    "while": {
        "end": "endwhile",
        "body_key": "while_block",
    },
}

CLOSING_ACTIONS = {"else", "endif", "endrepeat", "endwhile"}


def validate_and_nest_control_flow(flat_steps):
    """
    Validate and convert flat control-flow markers into nested blocks.

    Handles:
    - if/else/endif -> if_block/else_block
    - repeat/endrepeat -> repeat_block
    - while/endwhile -> while_block
    """
    nested_steps, next_index = _parse_steps(flat_steps, start_index=0)
    if next_index != len(flat_steps):
        step = flat_steps[next_index]
        raise ConditionalStructureError(
            f"Found '{step['action']}' at position {next_index} without matching opening statement. "
            f"UUID: {step.get('uuid')}"
        )
    return nested_steps


def process_if_block(flat_steps, start_index):
    """Compatibility wrapper for parsing an if block from a flat step list."""
    return _process_block(flat_steps, start_index, "if")


def process_repeat_block(flat_steps, start_index):
    """Compatibility wrapper for parsing a repeat block from a flat step list."""
    return _process_block(flat_steps, start_index, "repeat")


def process_while_block(flat_steps, start_index):
    """Compatibility wrapper for parsing a while block from a flat step list."""
    return _process_block(flat_steps, start_index, "while")


def _process_block(flat_steps, start_index, expected_action):
    action = flat_steps[start_index]["action"]
    if action != expected_action:
        raise ConditionalStructureError(
            f"Expected '{expected_action}' at position {start_index}, found '{action}'. "
            f"UUID: {flat_steps[start_index].get('uuid')}"
        )
    nested_step, next_index = _parse_control_block(flat_steps, start_index)
    return nested_step, next_index - start_index


def _parse_steps(flat_steps, start_index, stop_actions=None, owner_uuid=None):
    stop_actions = set(stop_actions or [])
    nested_steps = []
    index = start_index

    while index < len(flat_steps):
        step = flat_steps[index]
        action = step["action"]

        if action in stop_actions:
            if owner_uuid is not None and step.get("uuid") != owner_uuid:
                expected = " or ".join(sorted(stop_actions))
                raise ConditionalStructureError(
                    f"Found '{action}' with UUID {step.get('uuid')} at position {index}, "
                    f"but expecting {expected} for block with UUID {owner_uuid}"
                )
            return nested_steps, index

        if action in CLOSING_ACTIONS:
            raise ConditionalStructureError(
                f"Found '{action}' at position {index} without matching opening statement. "
                f"UUID: {step.get('uuid')}"
            )

        if action in CONTROL_BLOCKS:
            nested_step, index = _parse_control_block(flat_steps, index)
            nested_steps.append(nested_step)
            continue

        nested_steps.append(step)
        index += 1

    return nested_steps, index


def _parse_control_block(flat_steps, start_index):
    step = flat_steps[start_index].copy()
    action = step["action"]
    block_config = CONTROL_BLOCKS[action]
    block_uuid = step["uuid"]

    if action == "if":
        return _parse_if_block(flat_steps, start_index, step, block_uuid, block_config)

    body, end_index = _parse_steps(
        flat_steps,
        start_index=start_index + 1,
        stop_actions={block_config["end"]},
        owner_uuid=block_uuid,
    )

    if end_index >= len(flat_steps):
        raise ConditionalStructureError(
            f"Missing '{block_config['end']}' for {action} statement with UUID {block_uuid} "
            f"starting at position {start_index}"
        )

    step[block_config["body_key"]] = body
    return step, end_index + 1


def _parse_if_block(flat_steps, start_index, step, block_uuid, block_config):
    if_block, next_index = _parse_steps(
        flat_steps,
        start_index=start_index + 1,
        stop_actions={"else", block_config["end"]},
        owner_uuid=block_uuid,
    )

    else_block = []
    if next_index >= len(flat_steps):
        raise ConditionalStructureError(
            f"Missing '{block_config['end']}' for if statement with UUID {block_uuid} "
            f"starting at position {start_index}"
        )

    stop_step = flat_steps[next_index]
    if stop_step["action"] == "else":
        else_block, next_index = _parse_steps(
            flat_steps,
            start_index=next_index + 1,
            stop_actions={block_config["end"]},
            owner_uuid=block_uuid,
        )

        if next_index >= len(flat_steps):
            raise ConditionalStructureError(
                f"Missing '{block_config['end']}' for if statement with UUID {block_uuid} "
                f"starting at position {start_index}"
            )

    step[block_config["body_key"]] = if_block
    step[block_config["else_key"]] = else_block
    return step, next_index + 1
