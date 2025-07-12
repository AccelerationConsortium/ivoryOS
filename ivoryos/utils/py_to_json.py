import ast
import json
import uuid

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
            isinstance(node.value, (ast.Constant, ast.Num, ast.Str, ast.NameConstant))
        )

    class CardVisitor(ast.NodeVisitor):
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
            elif isinstance(node.value, ast.Call):
                self.handle_call(node.value, ret_var=node.targets[0].id)

        def visit_Expr(self, node):
            if isinstance(node.value, ast.Call):
                self.handle_call(node.value)

        def handle_call(self, node, ret_var=""):
            func_parts = []
            f = node.func
            while isinstance(f, ast.Attribute):
                func_parts.insert(0, f.attr)
                f = f.value
            if isinstance(f, ast.Name):
                func_parts.insert(0, f.id)
            if not func_parts or not func_parts[0].startswith("deck"):
                return

            instrument = ".".join(func_parts[:-1])
            action = func_parts[-1]

            args = {}
            arg_types = {}

            for kw in node.keywords:
                if kw.arg is None and isinstance(kw.value, ast.Dict):
                    for k_node, v_node in zip(kw.value.keys, kw.value.values):
                        key = k_node.s if isinstance(k_node, ast.Constant) else ast.unparse(k_node)
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

            add_card({
                "action": action,
                "arg_types": arg_types,
                "args": args,
                "id": new_id(),
                "instrument": instrument,
                "return": ret_var,
                "uuid": generate_uuid()
            })

    CardVisitor().visit(tree)
    return cards


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
    deck.sdl.dose_solid(amount_in_mg=solid_amount_mg)
    
    # Step 2: Add methanol solvent
    deck.sdl.dose_solvent(solvent_name='Methanol', amount_in_ml=methanol_amount_ml)
    
    # Step 3: Equilibrate at room temperature (assuming ~23°C) for 20 seconds
    deck.sdl.equilibrate(temp=23.0, duration=20.0)
    
    # Step 4: Analyze the sample
    analysis_results = deck.sdl.analyze(param_1=1, param_2=2)
    
    # Brief pause for system stability
    time.sleep(1.0)
    
    # Return only analysis results
    return {'analysis_results': analysis_results}
    '''
    print(json.dumps(convert_to_cards(test)))