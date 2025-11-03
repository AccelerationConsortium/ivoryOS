import inspect
import os

BUILDING_BLOCKS = {}

def block(_func=None, *, category="general"):
    def decorator(func):
        if category not in BUILDING_BLOCKS:
            BUILDING_BLOCKS[category] = {}
        if func.__module__ == "__main__":
            file_path = inspect.getfile(func)  # e.g. /path/to/math_blocks.py
            module = os.path.splitext(os.path.basename(file_path))[0]
        else:
            module = func.__module__
        BUILDING_BLOCKS[category][func.__name__] = {
            "func": func,
            "signature": inspect.signature(func),
            "docstring": inspect.getdoc(func),
            "coroutine": inspect.iscoroutinefunction(func),
            "path": module
        }
        return func
    if _func is None:
        return decorator
    else:
        return decorator(_func)


class BlockNamespace:
    """[not in use] Expose methods for one block category as attributes."""

    def __init__(self, methods):
        for name, meta in methods.items():
            setattr(self, name, meta["func"])