class ConditionalStructureError(Exception):
    """Raised when conditional structure is invalid"""
    pass


class ConditionalStructureError(Exception):
    """Raised when control flow structure is invalid"""
    pass


class ConditionalStructureError(Exception):
    """Raised when control flow structure is invalid"""
    pass


def validate_and_nest_control_flow(flat_steps):
    """
    Validates and converts flat control flow structures to nested blocks.

    Handles:
    - if/else/endif -> if_block/else_block
    - repeat/endrepeat -> repeat_block
    - while/endwhile -> while_block

    Raises:
        ConditionalStructureError: If the control flow structure is invalid
    """
    nested_steps = []
    i = 0

    while i < len(flat_steps):
        step = flat_steps[i]
        action = step["action"]

        # Check for misplaced closing/middle statements
        if action in ["else", "endif", "endrepeat", "endwhile"]:
            raise ConditionalStructureError(
                f"Found '{action}' at position {i} without matching opening statement. "
                f"UUID: {step.get('uuid')}"
            )

        # Handle IF statements
        if action == "if":
            nested_step, steps_consumed = process_if_block(flat_steps, i)
            nested_steps.append(nested_step)
            i += steps_consumed

        # Handle REPEAT statements
        elif action == "repeat":
            nested_step, steps_consumed = process_repeat_block(flat_steps, i)
            nested_steps.append(nested_step)
            i += steps_consumed

        # Handle WHILE statements
        elif action == "while":
            nested_step, steps_consumed = process_while_block(flat_steps, i)
            nested_steps.append(nested_step)
            i += steps_consumed

        else:
            # Regular step - add as-is
            nested_steps.append(step)
            i += 1

    return nested_steps


def process_if_block(flat_steps, start_index):
    """
    Process an if/else/endif block starting at start_index.

    Returns:
        tuple: (nested_step_with_blocks, total_steps_consumed)
    """
    step = flat_steps[start_index].copy()
    if_uuid = step["uuid"]
    if_block = []
    else_block = []
    current_block = if_block
    found_else = False
    found_endif = False
    i = start_index + 1

    while i < len(flat_steps):
        current_step = flat_steps[i]
        current_action = current_step["action"]

        if current_action == "else":
            if current_step["uuid"] == if_uuid:
                if found_else:
                    raise ConditionalStructureError(
                        f"Multiple 'else' blocks found for if statement with UUID {if_uuid}. "
                        f"Second 'else' at position {i}"
                    )
                current_block = else_block
                found_else = True
                i += 1
                continue
            else:
                raise ConditionalStructureError(
                    f"Found 'else' with UUID {current_step['uuid']} at position {i}, "
                    f"but expecting endif for if with UUID {if_uuid}"
                )

        elif current_action == "endif":
            if current_step["uuid"] == if_uuid:
                found_endif = True
                i += 1
                break
            else:
                raise ConditionalStructureError(
                    f"Found 'endif' with UUID {current_step['uuid']} at position {i}, "
                    f"but expecting endif for if with UUID {if_uuid}"
                )

        elif current_action == "if":
            # Nested if - process it
            try:
                nested_step, steps_consumed = process_if_block(flat_steps, i)
                current_block.append(nested_step)
                i += steps_consumed
            except ConditionalStructureError as e:
                raise ConditionalStructureError(
                    f"Error in nested if starting at position {i}: {str(e)}"
                )

        elif current_action == "repeat":
            # Nested repeat - process it
            try:
                nested_step, steps_consumed = process_repeat_block(flat_steps, i)
                current_block.append(nested_step)
                i += steps_consumed
            except ConditionalStructureError as e:
                raise ConditionalStructureError(
                    f"Error in nested repeat starting at position {i}: {str(e)}"
                )

        elif current_action == "while":
            # Nested while - process it
            try:
                nested_step, steps_consumed = process_while_block(flat_steps, i)
                current_block.append(nested_step)
                i += steps_consumed
            except ConditionalStructureError as e:
                raise ConditionalStructureError(
                    f"Error in nested while starting at position {i}: {str(e)}"
                )

        else:
            # Regular step
            current_block.append(current_step)
            i += 1

    if not found_endif:
        raise ConditionalStructureError(
            f"Missing 'endif' for if statement with UUID {if_uuid} starting at position {start_index}"
        )

    step["if_block"] = if_block
    step["else_block"] = else_block

    return step, i - start_index


def process_repeat_block(flat_steps, start_index):
    """
    Process a repeat/endrepeat block starting at start_index.

    Returns:
        tuple: (nested_step_with_block, total_steps_consumed)
    """
    step = flat_steps[start_index].copy()
    repeat_uuid = step["uuid"]
    repeat_block = []
    found_endrepeat = False
    i = start_index + 1

    while i < len(flat_steps):
        current_step = flat_steps[i]
        current_action = current_step["action"]

        if current_action == "endrepeat":
            if current_step["uuid"] == repeat_uuid:
                found_endrepeat = True
                i += 1
                break
            else:
                raise ConditionalStructureError(
                    f"Found 'endrepeat' with UUID {current_step['uuid']} at position {i}, "
                    f"but expecting endrepeat for repeat with UUID {repeat_uuid}"
                )

        elif current_action == "if":
            # Nested if - process it
            try:
                nested_step, steps_consumed = process_if_block(flat_steps, i)
                repeat_block.append(nested_step)
                i += steps_consumed
            except ConditionalStructureError as e:
                raise ConditionalStructureError(
                    f"Error in nested if starting at position {i}: {str(e)}"
                )

        elif current_action == "repeat":
            # Nested repeat - process it
            try:
                nested_step, steps_consumed = process_repeat_block(flat_steps, i)
                repeat_block.append(nested_step)
                i += steps_consumed
            except ConditionalStructureError as e:
                raise ConditionalStructureError(
                    f"Error in nested repeat starting at position {i}: {str(e)}"
                )

        elif current_action == "while":
            # Nested while - process it
            try:
                nested_step, steps_consumed = process_while_block(flat_steps, i)
                repeat_block.append(nested_step)
                i += steps_consumed
            except ConditionalStructureError as e:
                raise ConditionalStructureError(
                    f"Error in nested while starting at position {i}: {str(e)}"
                )

        else:
            # Regular step
            repeat_block.append(current_step)
            i += 1

    if not found_endrepeat:
        raise ConditionalStructureError(
            f"Missing 'endrepeat' for repeat statement with UUID {repeat_uuid} starting at position {start_index}"
        )

    step["repeat_block"] = repeat_block

    return step, i - start_index


def process_while_block(flat_steps, start_index):
    """
    Process a while/endwhile block starting at start_index.

    Returns:
        tuple: (nested_step_with_block, total_steps_consumed)
    """
    step = flat_steps[start_index].copy()
    while_uuid = step["uuid"]
    while_block = []
    found_endwhile = False
    i = start_index + 1

    while i < len(flat_steps):
        current_step = flat_steps[i]
        current_action = current_step["action"]

        if current_action == "endwhile":
            if current_step["uuid"] == while_uuid:
                found_endwhile = True
                i += 1
                break
            else:
                raise ConditionalStructureError(
                    f"Found 'endwhile' with UUID {current_step['uuid']} at position {i}, "
                    f"but expecting endwhile for while with UUID {while_uuid}"
                )

        elif current_action == "if":
            # Nested if - process it
            try:
                nested_step, steps_consumed = process_if_block(flat_steps, i)
                while_block.append(nested_step)
                i += steps_consumed
            except ConditionalStructureError as e:
                raise ConditionalStructureError(
                    f"Error in nested if starting at position {i}: {str(e)}"
                )

        elif current_action == "repeat":
            # Nested repeat - process it
            try:
                nested_step, steps_consumed = process_repeat_block(flat_steps, i)
                while_block.append(nested_step)
                i += steps_consumed
            except ConditionalStructureError as e:
                raise ConditionalStructureError(
                    f"Error in nested repeat starting at position {i}: {str(e)}"
                )

        elif current_action == "while":
            # Nested while - process it
            try:
                nested_step, steps_consumed = process_while_block(flat_steps, i)
                while_block.append(nested_step)
                i += steps_consumed
            except ConditionalStructureError as e:
                raise ConditionalStructureError(
                    f"Error in nested while starting at position {i}: {str(e)}"
                )

        else:
            # Regular step
            while_block.append(current_step)
            i += 1

    if not found_endwhile:
        raise ConditionalStructureError(
            f"Missing 'endwhile' for while statement with UUID {while_uuid} starting at position {start_index}"
        )

    step["while_block"] = while_block

    return step, i - start_index