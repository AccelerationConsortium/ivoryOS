"""Enum arguments: a step stores the member's key, and the driver is called with the member.

The key is plain text, so a workflow saves whatever the Enum's values are: numbers, text, or
objects such as a plate. A value is accepted wherever one is typed or sent (``"methanol"``,
``2``, or ``"2"`` as a form sends it back) and finds its member the same way a key does, so
workflows saved when steps stored the value keep working.
"""

import importlib
import inspect
from enum import EnumMeta
from typing import Union

try:
    from typing import get_args, get_origin
except ImportError:  # Python 3.7
    from typing_extensions import get_args, get_origin

try:
    from types import UnionType  # `Mode | None`, Python 3.10+
    _UNIONS = (Union, UnionType)
except ImportError:
    _UNIONS = (Union,)


def enum_class_of(annotation):
    """The Enum class an annotation names, also inside ``Optional``; None otherwise."""
    if isinstance(annotation, EnumMeta):
        return annotation
    if get_origin(annotation) in _UNIONS:
        for arg in get_args(annotation):
            if isinstance(arg, EnumMeta):
                return arg
    return None


def enum_class_from_type(type_str):
    """The Enum class a recorded ``Enum:module.Class`` type names, or None if it cannot be found."""
    try:
        _, full_path = type_str.split(":", 1)
        module_name, class_name = full_path.rsplit(".", 1)
    except (AttributeError, ValueError):
        return None
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        from ivoryos.runtime.state import GlobalState

        deck = GlobalState().deck
        if not (deck and (deck.__name__ == module_name or module_name == "__main__")):
            return None
        module = deck
    except Exception:
        return None
    return enum_class_of(getattr(module, class_name, None))


def find_member(enum_class, key):
    """The member ``key`` stands for, or None: the member itself, its key, its value, or its
    value as text (``"1"`` for ``SLOW = 1``)."""
    if isinstance(key, enum_class):
        return key
    if isinstance(key, str) and key in enum_class.__members__:
        return enum_class[key]
    for member in enum_class:
        try:
            if member.value == key or (isinstance(key, str) and str(member.value) == key):
                return member
        except Exception:  # a value whose comparison fails is simply not a match
            continue
    return None


def to_members(function, kwargs):
    """``kwargs`` for calling ``function``, each Enum-typed argument as its member. An
    argument that names no member is passed as it is."""
    try:
        parameters = inspect.signature(function).parameters
    except (TypeError, ValueError):
        return kwargs
    converted = dict(kwargs)
    for name, value in kwargs.items():
        param = parameters.get(name)
        enum_class = enum_class_of(param.annotation) if param is not None else None
        if enum_class is not None:
            member = find_member(enum_class, value)
            if member is not None:
                converted[name] = member
    return converted
