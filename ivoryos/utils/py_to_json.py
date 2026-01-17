import ast
import json
import uuid


from ivoryos.utils.global_config import GlobalConfig

global_config = GlobalConfig()

if global_config.building_blocks:
    building_blocks = {
        inner_key: f"{block_key}.{inner_key}"
        for block_key, block_value in global_config.building_blocks.items()
        for inner_key in block_value.keys()
    }
else:
    building_blocks = {}

def generate_uuid():
    return int(str(uuid.uuid4().int)[:15])

def infer_type(value):
    if isinstance(value, bool):
        return "bool"
    elif isinstance(value, int):
        return "int"
    elif isinstance(value, float):
        return "float"
    elif isinstance(value, str):
        return "str"
    elif isinstance(value, (ast.Name, str)) and str(value).startswith("#"):
        return "float"  # default fallback for variables
    else:
        return "unknown"

def convert_to_cards(source_code: str):
    tree = ast.parse(source_code)
    cards = []
    card_id = 1
    block_stack = []  # to track control flow UUIDs

    def new_id():
        nonlocal card_id
        val = card_id
        card_id += 1
        return val

    def add_card(card):
        cards.append(card)

    def is_supported_assignment(node):
        return (
            isinstance(node.targets[0], ast.Name) and
            isinstance(node.value, ast.Constant)
        )

    class CardVisitor(ast.NodeVisitor):
        def __init__(self):
            self.defined_types = {}  # <-- always exists


        def visit_FunctionDef(self, node):
            self.defined_types = {
                arg.arg: ast.unparse(arg.annotation) if arg.annotation else "float"
                for arg in node.args.args
            }
            for stmt in node.body:
                self.visit(stmt)

        def visit_If(self, node):
            uuid_ = generate_uuid()
            block_stack.append(("if", uuid_))

            add_card({
                "action": "if",
                "arg_types": {"statement": ""},
                "args": {"statement": ast.unparse(node.test)},
                "id": new_id(),
                "instrument": "if",
                "return": "",
                "uuid": uuid_
            })

            for stmt in node.body:
                self.visit(stmt)

            if node.orelse:
                add_card({
                    "action": "else",
                    "args": {},
                    "id": new_id(),
                    "instrument": "if",
                    "return": "",
                    "uuid": uuid_
                })
                for stmt in node.orelse:
                    self.visit(stmt)

            _, block_uuid = block_stack.pop()
            add_card({
                "action": "endif",
                "args": {},
                "id": new_id(),
                "instrument": "if",
                "return": "",
                "uuid": block_uuid
            })

        def visit_While(self, node):
            uuid_ = generate_uuid()
            block_stack.append(("while", uuid_))

            add_card({
                "action": "while",
                "arg_types": {"statement": ""},
                "args": {"statement": ast.unparse(node.test)},
                "id": new_id(),
                "instrument": "while",
                "return": "",
                "uuid": uuid_
            })

            for stmt in node.body:
                self.visit(stmt)

            _, block_uuid = block_stack.pop()
            add_card({
                "action": "endwhile",
                "args": {},
                "id": new_id(),
                "instrument": "while",
                "return": "",
                "uuid": block_uuid
            })

        def visit_Assign(self, node):
            if is_supported_assignment(node):
                var_name = node.targets[0].id
                value = node.value.value
                add_card({
                    "action": var_name,
                    "arg_types": {"statement": infer_type(value)},
                    "args": {"statement": value},
                    "id": new_id(),
                    "instrument": "variable",
                    "return": "",
                    "uuid": generate_uuid()
                })
            elif isinstance(node.value, ast.Await):
                self.handle_call(node.value.value, ret_var=node.targets[0].id, awaited=True)

            elif isinstance(node.value, ast.Call):
                self.handle_call(node.value, ret_var=node.targets[0].id)

        def visit_Expr(self, node):
            if isinstance(node.value, ast.Await):
                # node.value is ast.Await
                self.handle_call(node.value.value, awaited=True)
            elif isinstance(node.value, ast.Call):
                self.handle_call(node.value)

        def handle_call(self, node, ret_var="", awaited=False):
            func_parts = []
            f = node.func
            while isinstance(f, ast.Attribute):
                func_parts.insert(0, f.attr)
                f = f.value
            if isinstance(f, ast.Name):
                func_parts.insert(0, f.id)

            full_func_name = ".".join(func_parts)

            # Check if it starts with 'deck.' and strip it
            if full_func_name.startswith("deck."):
                remaining_parts = full_func_name.split(".")[1:]
                # Must have at least instrument.action
                if len(remaining_parts) >= 2:
                    instrument = f"deck.{'.'.join(remaining_parts[:-1])}"
                    action = remaining_parts[-1]
                else:
                    return # invalid format like deck.something
            elif full_func_name.startswith("blocks."):
                instrument = ".".join(func_parts[:-1])
                action = func_parts[-1]
            elif func_parts[-1] in building_blocks.keys():
                instrument = building_blocks.get(func_parts[-1])
                action = func_parts[-1]
            else:
                # Try to see if the first part is a known instrument in deck_snapshot
                # This covers cases like 'sdl.dose' where 'sdl' is the instrument
                if len(func_parts) >= 2:
                    possible_instrument = ".".join(func_parts[:-1])
                    possible_action = func_parts[-1]
                    if f"deck.{possible_instrument}" in global_config.deck_snapshot:
                        instrument = f"deck.{possible_instrument}"
                        action = possible_action
                    else:
                        return
                else:
                    return

            # # Validate that the instrument (if not a block or time) exists in deck_snapshot
            # if not instrument.startswith("blocks.") and instrument != "time":
            #      if instrument not in global_config.deck_snapshot:
            #          return # Not a valid instrument call for this deck
            #


            # --- special case for time.sleep ---
            if instrument == "time" and action == "sleep":
                wait_value = None
                if node.args:
                    arg_node = node.args[0]
                    if isinstance(arg_node, ast.Constant):
                        wait_value = arg_node.value
                    elif isinstance(arg_node, ast.Name):
                        wait_value = f"#{arg_node.id}"
                    else:
                        wait_value = ast.unparse(arg_node)

                add_card({
                    "action": "wait",
                    "arg_types": {"statement": infer_type(wait_value)},
                    "args": {"statement": wait_value},
                    "id": new_id(),
                    "instrument": "wait",
                    "return": ret_var,
                    "uuid": generate_uuid()
                })
                return
            # -----------------------------------


            args = {}
            arg_types = {}

            # Resolve function signature
            sig_params = []
            func_def = None

            # 1. Check in deck_snapshot
            if instrument in global_config.deck_snapshot:
                func_info = global_config.deck_snapshot[instrument].get(action)
                if func_info and 'signature' in func_info:
                    sig_params = list(func_info['signature'].parameters.keys())
                    sig_params.remove("self")
                    print(sig_params)

            # 2. Check in building_blocks
            # instrument might be mapped name or actual block name
            # building_blocks keys are short names, values are mapped names (e.g. 'test' -> 'blocks.general.test')
            if not sig_params:
                # Check if instrument is a block name e.g. "blocks.general"
                if instrument.startswith("blocks."):
                    if instrument in global_config.building_blocks:
                        func_info = global_config.building_blocks[instrument].get(action)
                        if func_info and 'signature' in func_info:
                            sig_params = list(func_info['signature'].parameters.keys())

            # Handle positional arguments
            for i, arg_node in enumerate(node.args):
                if i < len(sig_params):
                    arg_name = sig_params[i]
                else:
                    # Fallback if we have more args than parameters or no signature found
                    arg_name = f"arg_{i}"

                if isinstance(arg_node, ast.Constant):
                    value = arg_node.value
                elif isinstance(arg_node, ast.Name):
                    value = f"#{arg_node.id}"
                else:
                    value = ast.unparse(arg_node)

                args[arg_name] = value
                arg_types[arg_name] = infer_type(value)


            for kw in node.keywords:
                if kw.arg is None and isinstance(kw.value, ast.Dict):
                    for k_node, v_node in zip(kw.value.keys, kw.value.values):
                        key = k_node.value if isinstance(k_node, ast.Constant) else ast.unparse(k_node)
                        if isinstance(v_node, ast.Constant):
                            value = v_node.value
                        elif isinstance(v_node, ast.Name):
                            value = f"#{v_node.id}"
                        else:
                            value = ast.unparse(v_node)
                        args[key] = value
                        arg_types[key] = infer_type(value)
                else:
                    if isinstance(kw.value, ast.Constant):
                        value = kw.value.value
                    elif isinstance(kw.value, ast.Name):
                        value = f"#{kw.value.id}"
                    else:
                        value = ast.unparse(kw.value)
                    args[kw.arg] = value
                    arg_types[kw.arg] = (
                        self.defined_types.get(kw.value.id, "float")
                        if isinstance(kw.value, ast.Name)
                        else infer_type(value)
                    )

            card = {
                "action": action,
                "arg_types": arg_types,
                "args": args,
                "id": new_id(),
                "instrument": instrument,
                "return": ret_var,
                "uuid": generate_uuid()
            }

            if awaited:
                card["coroutine"] = True  # mark as coroutine if awaited

            add_card(card)

    CardVisitor().visit(tree)
    return cards

def extract_functions_and_convert(source_code: str):
    """
    Parses source code, extracts each top-level function definition,
    and converts its body to cards.
    Returns a dict {func_name: cards_list}.
    """
    tree = ast.parse(source_code)
    results = {}
    
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
             # Extract the source code for this function
             # ast.get_source_segment is available in 3.8+
             func_source = ast.get_source_segment(source_code, node)
             if func_source:
                 cards = convert_to_cards(func_source)
                 results[node.name] = {"cards": cards, "source": func_source}
    return results


if __name__ == "__main__":
    test = '''def workflow_dynamic(solid_amount_mg, methanol_amount_ml):
    """
    SDL workflow: dose solid, add methanol, equilibrate, and analyze
    
    Args:
        solid_amount_mg (float): Amount of solid to dose in mg
        methanol_amount_ml (float): Amount of methanol to dose in ml
    
    Returns:
        dict: Results containing analysis data
    """
    # Step 1: Dose solid material
    deck.sdl.dose_solid(solid_amount_mg)
    
    # Step 2: Add methanol solvent
    deck.sdl.dose_solvent(solvent_name='Methanol', amount_in_ml=methanol_amount_ml)
    
    # Step 3: Equilibrate at room temperature (assuming ~23°C) for 20 seconds
    deck.sdl.equilibrate(temp=23.0, duration=20.0)
    
    # Step 4: Analyze the sample
    analysis_results = deck.sdl.analyze(param_1=1, param_2=2)
    
    # test block 
    result = blocks.general.test(**{'a': 1, 'b': 2})
    
    # Brief pause for system stability
    time.sleep(1.0)
    
    # Return only analysis results
    return {'analysis_results': analysis_results}
    '''
    from pprint import pprint
    pprint(json.dumps(convert_to_cards(test)))