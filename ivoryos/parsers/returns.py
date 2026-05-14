from ivoryos.parsers.serialize import safe_dump


def extract_return_variables(form_data, validate_function_name=None):
    """
    Pull scalar or tuple return save names out of submitted form data.

    Scalar/dict returns use "return"; tuple returns use "return_0", "return_1", ...
    Empty tuple slots are preserved so runtime indexing stays aligned with the annotation.
    """
    save_data = form_data.pop("return", "")
    tuple_returns = []

    for key in list(form_data.keys()):
        if key.startswith("return_") and key[7:].isdigit():
            tuple_returns.append((int(key[7:]), form_data.pop(key, "")))

    def clean(name):
        if isinstance(name, str):
            name = name.strip()
        if name and validate_function_name:
            return validate_function_name(name)
        return name or ""

    if tuple_returns:
        return [clean(value) for _, value in sorted(tuple_returns)]

    return clean(save_data)


def store_return_value(context, arg_contexts, return_var, result):
    """Store a function result in the script context, supporting tuple item saves."""
    if not return_var or result is None:
        return

    if isinstance(return_var, list):
        for index, name in enumerate(return_var):
            if not name:
                continue
            try:
                value = result[index]
            except (IndexError, TypeError, KeyError):
                raise ValueError(
                    f"Cannot save return value {index} as '{name}'; result is not indexable at that position."
                )
            value = safe_dump(value)
            context[name] = value
            if arg_contexts is not None:
                arg_contexts[name] = value
        return

    result = safe_dump(result)
    context[return_var] = result
    if arg_contexts is not None:
        arg_contexts[return_var] = result
