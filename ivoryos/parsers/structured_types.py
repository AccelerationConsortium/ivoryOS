"""
Support for dict-typed method parameters, e.g. ``def configure(self, settings: dict)`` or ``Dict[str, float]``.

Inside a workflow a dict value is kept as a plain, JSON-friendly dict, so it can be stored, shown and edited whole
(as JSON or as a table of keys and values, see ``static/js/structured_editor.js``) and hold ``#variable``
placeholders at any depth. Those variables become run parameters, and are rendered as bare names in exported
Python code.

The arg type string of a dict parameter is ``"dict"``, or ``["Dict", "NoneType"]`` for an ``Optional[Dict[K, V]]``.
"""
import ast
import copy
import json
import re
from enum import Enum
from typing import Any, Union

try:
    from typing import get_args, get_origin
except ImportError:
    from typing_extensions import get_args, get_origin

try:
    from types import UnionType  # PEP 604 ``X | None``, Python 3.10+
except ImportError:
    UnionType = None

_VARIABLE = re.compile(r"#[A-Za-z_]\w*")
_DICT_TYPE = re.compile(r"[Dd]ict(\[.*\])?")
_NAMED_CONSTANTS = {"None": None, "null": None, "True": True, "true": True, "False": False, "false": False}


# ---------------------------------------------------------------------------
# annotations
# ---------------------------------------------------------------------------

def _strip_optional(annotation):
    """``Optional[X]`` -> ``(X, True)``; anything else -> ``(annotation, False)``."""
    origin = get_origin(annotation)
    if origin is Union or (UnionType is not None and origin is UnionType):
        args = get_args(annotation)
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1 and len(non_none) != len(args):
            return non_none[0], True
    return annotation, False


def is_dict_annotation(annotation):
    """``dict``, ``Dict[K, V]`` / ``dict[K, V]``, or an ``Optional`` of one."""
    inner, _ = _strip_optional(annotation)
    return inner is dict or get_origin(inner) is dict


def _dict_value_annotation(annotation):
    """``V`` of ``Dict[K, V]``, or ``None`` for a bare ``dict`` / anything else."""
    if not is_dict_annotation(annotation):
        return None
    args = get_args(_strip_optional(annotation)[0])
    return args[1] if len(args) == 2 else None


# ---------------------------------------------------------------------------
# arg type strings
# ---------------------------------------------------------------------------

def find_structured_type(type_entry):
    """``"dict"`` when an arg type entry (a string, or a list for ``Optional``) is a dict, else ``None``."""
    entries = type_entry if isinstance(type_entry, list) else [type_entry]
    # "dict", or "Dict" for an Optional[Dict[K, V]] (see introspection._get_type_from_parameters)
    if any(isinstance(entry, str) and _DICT_TYPE.fullmatch(entry) for entry in entries):
        return "dict"
    return None


def load_structured_type(type_entry):
    """The annotation for a structured arg type entry (``dict``), or ``None``."""
    return dict if find_structured_type(type_entry) == "dict" else None


# ---------------------------------------------------------------------------
# values
# ---------------------------------------------------------------------------

def is_variable(value):
    return isinstance(value, str) and _VARIABLE.fullmatch(value) is not None


def has_variables(value):
    return any(True for _ in iter_variables(value, None))


def iter_variables(value, annotation):
    """Yield ``(name, annotation)`` for every ``#variable`` leaf inside a structured value."""
    if is_variable(value):
        yield value[1:], annotation
        return
    if isinstance(value, list):
        for item in value:
            for found in iter_variables(item, None):
                yield found
    elif isinstance(value, dict):
        item_type = _dict_value_annotation(annotation)  # the V of a Dict[K, V]
        for item in value.values():
            for found in iter_variables(item, item_type):
                yield found


def substitute_variables(value, context):
    """Replace ``#variable`` leaves nested inside dicts/lists with their values from the context."""
    if is_variable(value):
        return context[value[1:]] if value[1:] in context else value
    if isinstance(value, list):
        return [substitute_variables(item, context) for item in value]
    if isinstance(value, dict):
        return {key: substitute_variables(item, context) for key, item in value.items()}
    return value


def structured_template(annotation):
    """Value used to prefill forms: an empty dict, or ``None`` for an ``Optional`` one."""
    return None if _strip_optional(annotation)[1] else {}


def structured_schema(annotation):
    """
    Layout of a dict annotation for the form editor (``static/js/structured_editor.js``), e.g. for
    ``Optional[Dict[str, float]]``: ``{"kind": "dict", "key": {"kind": "scalar", "type": "str", "optional": False},
    "value": {"kind": "scalar", "type": "float", "optional": False}, "optional": True}``. An Enum value is
    ``{"kind": "enum", "choices": [...]}``; a type the editor has no input for (a union, a list) is ``{"kind": "json"}``.
    """
    inner, optional = _strip_optional(annotation)
    if isinstance(inner, type) and issubclass(inner, Enum) and _json_safe([member.value for member in inner]):
        schema = {"kind": "enum", "type": inner.__name__, "choices": [member.value for member in inner]}
    elif inner in (bool, int, float, str):
        schema = {"kind": "scalar", "type": inner.__name__}
    elif is_dict_annotation(inner):
        args = get_args(inner)
        key, value = args if len(args) == 2 else (str, Any)
        schema = {"kind": "dict", "key": structured_schema(key), "value": structured_schema(value)}
    else:
        schema = {"kind": "json"}
    schema["optional"] = optional
    return schema


def _json_safe(value):
    try:
        json.dumps(value)
        return True
    except (TypeError, ValueError):
        return False


def format_structured_value(value):
    return json.dumps(value, indent=2)


def parse_structured_value(text, annotation=None):
    """
    Parse user text into plain dicts/lists. Accepts JSON and Python literals, e.g. ``{'gain': 1.5, 'mode': None}``.
    Bare ``#variable`` placeholders are allowed anywhere and kept as ``"#variable"`` strings.
    """
    try:
        tree = ast.parse(_quote_variables(text.strip()), mode="eval")
    except SyntaxError as e:
        raise ValueError(f"cannot parse value ({e.msg})") from e
    return _node_to_value(tree.body, annotation)


class _NamesToVariables(ast.NodeTransformer):
    def visit_Name(self, node):
        if node.id in _NAMED_CONSTANTS:
            return node
        return ast.copy_location(ast.Constant(f"#{node.id}"), node)


def structured_value_from_node(node, annotation):
    """Plain value for an expression in an imported Python script, e.g. ``{'gain': g}``; names become #variables."""
    return _node_to_value(_NamesToVariables().visit(copy.deepcopy(node)), annotation)


def _quote_variables(text):
    """Wrap ``#variable`` tokens outside of string literals in quotes."""
    out = []
    quote = None
    i = 0
    while i < len(text):
        char = text[i]
        if quote:
            out.append(char)
            if char == "\\" and i + 1 < len(text):
                out.append(text[i + 1])
                i += 2
                continue
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
            out.append(char)
        elif char == "#" and _VARIABLE.match(text, i):
            match = _VARIABLE.match(text, i)
            out.append(repr(match.group(0)))
            i = match.end()
            continue
        else:
            out.append(char)
        i += 1
    return "".join(out)


def _node_to_value(node, annotation=None):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name) and node.id in _NAMED_CONSTANTS:
        return _NAMED_CONSTANTS[node.id]
    if (isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd))
            and isinstance(node.operand, ast.Constant) and isinstance(node.operand.value, (int, float))):
        return -node.operand.value if isinstance(node.op, ast.USub) else node.operand.value
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_node_to_value(item) for item in node.elts]
    if isinstance(node, ast.Dict):
        if any(key is None for key in node.keys):
            raise ValueError("'**' unpacking is not supported")
        item_type = _dict_value_annotation(annotation)
        return {_node_to_value(key): _node_to_value(value, item_type) for key, value in zip(node.keys, node.values)}
    raise ValueError(f"unsupported expression: {_source(node)}")


def _source(node):
    try:
        return ast.unparse(node)
    except AttributeError:  # Python < 3.9
        return type(node).__name__


def validate_structured_value(value, annotation, path=""):
    """Raise ``ValueError`` when a dict argument (or a dict nested in one) is not a dict. Variables are allowed anywhere."""
    if value is None or is_variable(value) or not is_dict_annotation(annotation):
        return
    if not isinstance(value, dict):
        raise ValueError(f"{path or 'value'}: expected a dict, got {value!r}")
    for key, item in value.items():
        validate_structured_value(item, _dict_value_annotation(annotation), f"{path}[{key!r}]")


def render_python(value, annotation=None):
    """Python source for a structured value, ``#variable`` leaves as bare names."""
    if is_variable(value):
        return value[1:]
    if isinstance(value, list):
        return "[" + ", ".join(render_python(item) for item in value) + "]"
    if isinstance(value, dict):
        item_type = _dict_value_annotation(annotation)
        return "{" + ", ".join(f"{key!r}: {render_python(item, item_type)}" for key, item in value.items()) + "}"
    return repr(value)
