"""Compare saved workflow steps against the deck that is loaded right now.

A step stores the module it calls, the method name, and the arguments it was
built with. The deck is ordinary Python that people keep editing, so a workflow
saved last month can name a module that was renamed, a method that no longer
exists, or a parameter whose type changed. Nothing catches that today until the
run fails halfway through, so the designer asks this module which steps no
longer line up with the deck and flags them on the canvas.

The check is deliberately conservative: a source that is simply not loaded (no
deck in offline mode, no building blocks registered) reports nothing rather than
declaring everything it used to hold missing.
"""

import difflib
import inspect
import os

from ivoryos.parsers.introspection import _inspect_class, get_arg_type, load_interface_schema

# Steps whose instrument is control flow rather than something on the deck.
# They have no signature to compare against.
FLOW_CONTROL_INSTRUMENTS = frozenset({
    "if", "while", "repeat", "wait", "pause", "comment",
    "variable", "math_variable", "input",
})

WORKFLOW_INSTRUMENT = "workflows"
PROPERTY_SETTER_SUFFIX = "_(setter)"

# How far to follow workflow steps that embed other workflows.
MAX_WORKFLOW_DEPTH = 3

# Issue codes. The message is what the user reads; the code is what tests and
# any future filtering match on.
MODULE_MISSING = "module_missing"
METHOD_MISSING = "method_missing"
PARAM_REMOVED = "param_removed"
PARAM_MISSING = "param_missing"
TYPE_CHANGED = "type_changed"
WORKFLOW_MISSING = "workflow_missing"

# An error will raise when the step runs; a warning may still run, but with a
# value the deck no longer expects.
ERROR = "error"
WARNING = "warning"


def _issue(code, severity, message, target=None):
    return {"code": code, "severity": severity, "message": message, "target": target}


def _display(instrument):
    """A module name as the canvas writes it: ``deck.pump`` reads as ``pump``.

    Deck modules are always stored fully qualified, but the step labels drop the
    ``deck.`` prefix, so messages about them should read the same way. Building
    blocks keep their ``blocks.`` prefix, which is how they are labelled too.
    """
    return instrument[len("deck."):] if instrument.startswith("deck.") else instrument


def _closest(name, candidates):
    """The one candidate close enough to ``name`` to be a plausible rename."""
    others = [candidate for candidate in candidates if candidate != name]
    matches = difflib.get_close_matches(name, others, n=1, cutoff=0.6)
    return matches[0] if matches else None


def _normalize_type(value):
    """A comparable form of one argument type.

    Both sides of a comparison come from :func:`get_arg_type`, so they already
    share a vocabulary. Two things still need normalizing: the members of a
    union carry no meaningful order, and an Enum is compared by class name only,
    because the module path recorded for it depends on how the deck happened to
    be imported (``__main__`` when the deck is run as a script) and can change
    without the signature changing at all.
    """
    if isinstance(value, (list, tuple)):
        return tuple(sorted(_normalize_type(item) for item in value))
    text = "" if value is None else str(value)
    if text.startswith("Enum:"):
        return "Enum:" + text.rsplit(".", 1)[-1]
    return text


def _format_type(value):
    """One argument type as it should read in a warning."""
    if isinstance(value, (list, tuple)):
        return " | ".join(_format_type(item) for item in value) or "untyped"
    text = "" if value is None else str(value)
    if text.startswith("Enum:"):
        return text.rsplit(".", 1)[-1]
    if text.startswith("Literal:"):
        return "one of " + text[len("Literal:"):]
    return text or "untyped"


def _signature_of(function_data):
    signature = function_data.get("signature") if isinstance(function_data, dict) else function_data
    return signature if isinstance(signature, inspect.Signature) else None


def _callable_parameters(signature):
    """``({name: Parameter}, accepts_extra)`` for what a step may pass.

    Mirrors the fields the designer builds from a signature: ``self`` and
    ``*args`` never become form fields, and ``**kwargs`` means unrecognised
    argument names are still legal.
    """
    parameters = {}
    accepts_extra = False
    for parameter in signature.parameters.values():
        if parameter.name == "self":
            continue
        if parameter.kind == inspect.Parameter.VAR_POSITIONAL:
            continue
        if parameter.kind == inspect.Parameter.VAR_KEYWORD:
            accepts_extra = True
            continue
        parameters[parameter.name] = parameter
    return parameters, accepts_extra


def _setter_signature(property_data):
    """The ``(value)`` signature a property setter step was built against.

    The schema stores a property once, under the getter. The designer
    synthesizes a setter from the getter's return annotation when it builds the
    form, so the check has to synthesize the same thing to compare against.
    """
    getter = _signature_of(property_data)
    annotation = inspect.Parameter.empty
    if getter is not None and getter.return_annotation is not inspect.Signature.empty:
        annotation = getter.return_annotation
    value = inspect.Parameter("value", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=annotation)
    return inspect.Signature(parameters=[value])


class DeckReference:
    """What the process currently offers, keyed the way steps name it.

    Three separate sources can back a step: the deck's interface schema
    (``deck.*``), registered building blocks (``blocks.*``), and objects created
    at runtime on the instruments page (a bare name). Each of them can be
    absent, and an absent source yields no findings at all.
    """

    def __init__(self, interface_schema=None, building_blocks=None, local_variables=None,
                 workflow_names=None, workflow_names_loader=None, deck_name=None):
        self.interface_schema = dict(interface_schema or {})
        # a pickled schema carries the deck's name alongside the modules
        self.interface_schema.pop("deck_name", None)
        self.building_blocks = dict(building_blocks or {})
        self.local_variables = dict(local_variables or {})
        self._workflow_names = None if workflow_names is None else set(workflow_names)
        self._workflow_names_loader = workflow_names_loader
        self._workflow_names_loaded = workflow_names_loader is None
        self.deck_name = deck_name
        self._inspected = {}

    @property
    def enabled(self):
        """Whether anything is loaded to check steps against."""
        return bool(self.interface_schema or self.building_blocks or self.local_variables)

    @property
    def workflow_names(self):
        """Workflows still usable as a step, or ``None`` if that is unknown.

        Resolved on first use rather than up front: it costs a database query,
        and most workflows embed no sub-workflow at all, so asking eagerly would
        put a query on every canvas render to answer a question nothing asks.
        """
        if not self._workflow_names_loaded:
            self._workflow_names_loaded = True
            names = self._workflow_names_loader()
            self._workflow_names = None if names is None else set(names)
        return self._workflow_names

    def catalogue(self, instrument):
        """The mapping a step's instrument should be found in, or ``None``.

        ``None`` means that kind of source is not loaded, which is not the same
        as the module being gone.
        """
        if instrument.startswith("deck."):
            return self.interface_schema or None
        if instrument.startswith("blocks."):
            return self.building_blocks or None
        return self.local_variables or None

    def siblings(self, instrument):
        """Names in the same catalogue, for spotting a rename."""
        catalogue = self.catalogue(instrument)
        return sorted(catalogue) if catalogue else []

    def functions_for(self, instrument):
        """``{method name: metadata}`` for a module, or ``None`` if it is gone."""
        catalogue = self.catalogue(instrument)
        if catalogue is None or instrument not in catalogue:
            return None
        module = catalogue[instrument]
        if catalogue is self.local_variables:
            # runtime objects are live instances, not an already-inspected schema
            if instrument not in self._inspected:
                try:
                    self._inspected[instrument] = _inspect_class(module)
                except Exception:
                    self._inspected[instrument] = {}
            return self._inspected[instrument]
        return module if isinstance(module, dict) else {}

    def modules_with(self, method_name):
        """Modules that still offer ``method_name``, for a method that moved."""
        found = []
        for catalogue in (self.interface_schema, self.building_blocks):
            for name, functions in catalogue.items():
                if isinstance(functions, dict) and method_name in functions:
                    found.append(name)
        return sorted(found)


def deck_name_of(deck):
    """The name a script records for a deck module."""
    name = getattr(deck, "__name__", None)
    if not name:
        return None
    if name == "__main__" and getattr(deck, "__file__", None):
        return os.path.splitext(os.path.basename(deck.__file__))[0]
    return name


# Where the per-request reference is cached; building it can read a pickle from
# disk and query the database, and several places want it during one render.
_REQUEST_CACHE_KEY = "_ivoryos_deck_reference"


def current_reference():
    """A :class:`DeckReference` for whatever this process has loaded right now.

    Cached for the duration of a request, since a deck cannot be swapped in the
    middle of one.
    """
    from flask import current_app, g, has_app_context, has_request_context, session

    from ivoryos.runtime.state import GlobalState

    if has_app_context() and hasattr(g, _REQUEST_CACHE_KEY):
        return getattr(g, _REQUEST_CACHE_KEY)

    state = GlobalState()
    deck = state.deck
    interface_schema = state.interface_schema if deck else None
    deck_name = deck_name_of(deck)

    if not interface_schema and has_request_context():
        # offline: the designer works against a pickled snapshot of a past deck
        pseudo_deck_name = session.get("pseudo_deck", "")
        if pseudo_deck_name:
            path = os.path.join(current_app.config["DUMMY_DECK"], pseudo_deck_name)
            snapshot = load_interface_schema(path) or {}
            if snapshot:
                interface_schema = snapshot
                deck_name = snapshot.get("deck_name") or os.path.splitext(pseudo_deck_name)[0]

    reference = DeckReference(
        interface_schema=interface_schema,
        building_blocks=state.building_blocks,
        local_variables=state.defined_variables,
        workflow_names_loader=_registered_workflow_names,
        deck_name=deck_name,
    )
    if has_app_context():
        setattr(g, _REQUEST_CACHE_KEY, reference)
    return reference


def _registered_workflow_names():
    """Names of workflows that can still be used as a step, or ``None``.

    ``None`` means the lookup did not happen (no database bound, for instance),
    so workflow steps go unchecked rather than all being reported as deleted.
    """
    try:
        from ivoryos.models import db
        from ivoryos.script.models import Script

        rows = db.session.query(Script.name).filter(Script.registered.is_(True)).all()
    except Exception:
        return None
    return {row[0] for row in rows}


def check_action(action, reference, _depth=0):
    """Reasons ``action`` no longer lines up with ``reference``, errors first."""
    if not isinstance(action, dict) or reference is None or not reference.enabled:
        return []
    instrument = action.get("instrument") or ""
    if not instrument or instrument in FLOW_CONTROL_INSTRUMENTS:
        return []
    if instrument == WORKFLOW_INSTRUMENT:
        issues = _check_workflow_action(action, reference, _depth)
    else:
        issues = _check_call_action(action, reference)
    return sorted(issues, key=lambda issue: 0 if issue["severity"] == ERROR else 1)


def check_script(script, reference):
    """``{step uuid: [issue, ...]}`` for every step of ``script`` that has one."""
    found = {}
    if reference is None or not reference.enabled:
        return found
    for stype in script.script_dict or {}:
        for action in script.script_dict.get(stype) or []:
            issues = check_action(action, reference)
            if issues:
                found[action.get("uuid")] = issues
    return found


# Compact stand-ins for the full messages, for places that list many steps at once.
SHORT_FORMS = {
    MODULE_MISSING: "missing module",
    METHOD_MISSING: "missing method",
    PARAM_REMOVED: "no longer takes",
    PARAM_MISSING: "now requires",
    TYPE_CHANGED: "changed type of",
    WORKFLOW_MISSING: "workflow not registered",
}


def summarize_issues(issues):
    """One short phrase covering a step's findings.

    The full sentences belong where there is room to read them - the canvas
    tooltip and the step edit panel. A list of steps needs something that fits on
    one line, so findings of the same kind are merged and named by what they are
    about: four sentences about four missing arguments become one clause.
    """
    grouped = {}
    for issue in issues:
        grouped.setdefault(issue["code"], []).append(issue.get("target"))

    parts = []
    for code, targets in grouped.items():
        label = SHORT_FORMS.get(code, code.replace("_", " "))
        named = list(dict.fromkeys(_display(target) for target in targets if target))
        parts.append(f"{label} {', '.join(named)}" if named else label)
    return "; ".join(parts)


def script_issue_summary(script, reference, include_disabled=False):
    """Flagged steps in run order, as a flat list.

    The design canvas hangs findings on the step button it draws; the execution
    page has no step buttons, so it needs them as a list it can just print.

    Disabled steps are left out by default: the runner skips them, so they
    cannot fail and must not be counted among the steps that will.
    """
    summary = []
    if reference is None or not reference.enabled:
        return summary
    for stype in script.script_dict or {}:
        for action in script.script_dict.get(stype) or []:
            if action.get("disabled", False) and not include_disabled:
                continue
            issues = check_action(action, reference)
            if not issues:
                continue
            summary.append({
                "phase": stype,
                "id": action.get("id"),
                "label": f"{_display(action.get('instrument') or '')}.{action.get('action')}",
                "issues": issues,
                "summary": summarize_issues(issues),
                "blocking": any(issue["severity"] == ERROR for issue in issues),
            })
    return summary


def check_deck_match(script, reference):
    """A warning when the workflow was built against another deck, else ``None``.

    Steps are still checked in that case; this just explains up front why so
    many of them are suddenly flagged.
    """
    if reference is None or not reference.enabled:
        return None
    expected = getattr(script, "deck", None)
    if not expected or not reference.deck_name or expected == reference.deck_name:
        return None
    return (f"This workflow was designed for deck '{expected}', but '{reference.deck_name}' "
            f"is loaded. Steps are checked against the loaded deck.")


def _check_call_action(action, reference):
    instrument = action["instrument"]
    functions = reference.functions_for(instrument)
    if functions is None:
        if reference.catalogue(instrument) is None:
            # nothing of this kind is loaded; we cannot tell gone from unknown
            return []
        return [_module_missing_issue(instrument, reference)]

    method_name = action.get("action") or ""
    function_data, resolved = _resolve_member(functions, method_name)
    if function_data is None:
        return [_method_missing_issue(instrument, method_name, functions, reference)]

    signature = resolved["signature"]
    if signature is None:
        # no signature was recorded; the module and method are there, so stop here
        return []
    return _check_arguments(action, signature, f"{_display(instrument)}.{resolved['label']}")


def _resolve_member(functions, method_name):
    """``(metadata, {'signature', 'label'})`` for the member a step calls."""
    if method_name in functions:
        data = functions[method_name]
        return data, {"signature": _signature_of(data), "label": method_name}

    if method_name.endswith(PROPERTY_SETTER_SUFFIX):
        property_name = method_name[: -len(PROPERTY_SETTER_SUFFIX)]
        data = functions.get(property_name)
        if data and data.get("is_property") and data.get("has_setter"):
            return data, {"signature": _setter_signature(data), "label": property_name}

    return None, None


def _module_missing_issue(instrument, reference):
    bare = _display(instrument)
    candidates = {_display(name): name for name in reference.siblings(instrument)}
    renamed = _closest(bare, candidates)
    if renamed:
        message = (f"Module '{bare}' is not on the current deck. "
                   f"A similarly named '{renamed}' exists - was it renamed?")
    else:
        message = f"Module '{bare}' is not on the current deck."
    return _issue(MODULE_MISSING, ERROR, message, target=instrument)


def _method_missing_issue(instrument, method_name, functions, reference):
    module = _display(instrument)
    shown = method_name
    if method_name.endswith(PROPERTY_SETTER_SUFFIX):
        property_name = method_name[: -len(PROPERTY_SETTER_SUFFIX)]
        existing = functions.get(property_name)
        if existing is not None:
            if existing.get("is_property"):
                message = f"Property '{property_name}' on '{module}' is now read-only."
            else:
                message = f"'{property_name}' on '{module}' is no longer a property and cannot be set."
            return _issue(METHOD_MISSING, ERROR, message, target=property_name)
        shown = property_name

    gone = f"Method '{shown}' no longer exists on '{module}'."

    renamed = _closest(shown, functions.keys())
    if renamed:
        return _issue(METHOD_MISSING, ERROR, f"{gone} It now has '{renamed}' - was it renamed?", target=shown)

    moved_to = [_display(name) for name in reference.modules_with(shown) if name != instrument]
    if moved_to:
        return _issue(METHOD_MISSING, ERROR,
                      f"{gone} It is now on {', '.join(moved_to)} - was it moved?", target=shown)

    return _issue(METHOD_MISSING, ERROR, gone, target=shown)


def _check_arguments(action, signature, label):
    """What the step saved against what the method now accepts."""
    arguments = action.get("args")
    if not isinstance(arguments, dict):
        # a legacy step that stored a bare value; there is nothing to match by name
        return []

    parameters, accepts_extra = _callable_parameters(signature)
    issues = []
    renamed_to = set()

    if not accepts_extra:
        for name in arguments:
            if name in parameters:
                continue
            renamed = _closest(name, parameters.keys())
            if renamed and renamed not in arguments:
                renamed_to.add(renamed)
                message = (f"'{label}' no longer takes '{name}'. "
                           f"It now takes '{renamed}' - was it renamed?")
            else:
                message = f"'{label}' no longer takes '{name}'."
            issues.append(_issue(PARAM_REMOVED, ERROR, message, target=name))

    for name, parameter in parameters.items():
        if name in arguments or parameter.default is not inspect.Parameter.empty:
            continue
        if name in renamed_to:
            # already covered, as the new name of an argument this step still passes
            continue
        issues.append(_issue(
            PARAM_MISSING, ERROR,
            f"'{label}' now requires '{name}', which this step does not set.",
            target=name,
        ))

    issues.extend(_check_argument_types(action, arguments, parameters, signature, label))
    return issues


def _check_argument_types(action, arguments, parameters, signature, label):
    """The argument types the step recorded against the ones in force today."""
    recorded = action.get("arg_types")
    if not isinstance(recorded, dict):
        return []

    # only arguments the step still passes to a parameter that still exists, and
    # whose type was recorded at all, can be compared
    comparable = [name for name in arguments if name in parameters and name in recorded]
    if not comparable:
        return []

    current = get_arg_type(comparable, {"signature": signature})
    issues = []
    for name in comparable:
        before, after = recorded.get(name), current.get(name)
        if _normalize_type(before) == _normalize_type(after):
            continue
        issues.append(_issue(
            TYPE_CHANGED, WARNING,
            f"'{label}' takes a different type for '{name}' now: "
            f"was {_format_type(before)}, now {_format_type(after)}.",
            target=name,
        ))
    return issues


def _check_workflow_action(action, reference, depth):
    """A step that calls another workflow, plus the deck calls it embeds."""
    issues = []
    name = action.get("action") or ""
    if reference.workflow_names is not None and name not in reference.workflow_names:
        # Not an error: the runner executes the copy of the sub-workflow embedded
        # in this step rather than looking the registered one up, so the step
        # still runs. What it runs is a snapshot that can no longer be compared
        # against an original, which is worth saying but will not raise.
        suffix = ("This step runs from the copy saved with it, which may be out of date.")
        renamed = _closest(name, reference.workflow_names)
        if renamed:
            message = (f"Workflow '{name}' is no longer registered, though a similarly "
                       f"named '{renamed}' exists. {suffix}")
        else:
            message = f"Workflow '{name}' is no longer registered. {suffix}"
        issues.append(_issue(WORKFLOW_MISSING, WARNING, message, target=name))

    if depth >= MAX_WORKFLOW_DEPTH:
        return issues

    # the embedded copy of the sub-workflow calls the deck too, so it rots the
    # same way; report each distinct reason once rather than once per step
    seen = set()
    for step in action.get("workflow") or []:
        for issue in check_action(step, reference, depth + 1):
            nested = dict(issue, message=f"In '{name}': {issue['message']}")
            key = (nested["code"], nested["message"])
            if key not in seen:
                seen.add(key)
                issues.append(nested)
    return issues
