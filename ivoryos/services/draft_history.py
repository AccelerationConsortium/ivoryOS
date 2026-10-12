"""
Undo and redo for the designer's draft.

A draft keeps a timeline of its own states: every change saved from the designer adds the new
state to the end, and undo and redo move along it. A state is the whole draft, serialized, so
going back restores exactly what was there, whatever the change was: a step added, edited,
moved or deleted, a rename.

The history belongs to one workflow. Opening a workflow from the library, importing one or
starting a new one begins a new history (:meth:`Timeline.restart`), so undo never goes back
into the workflow that was there before.

Each point on the timeline is labelled with the change that led to it ("Add balance.weigh",
"Move pump.dose_liquid (Prep)"), worked out by comparing the two states, so every route that
saves the draft gets a readable history without saying what it did. A route can still name a
change itself where the comparison cannot know the intent, e.g. "Import ..." for a JSON file.

This module only holds the timeline and its labels; ``draft_service`` stores it beside the
draft, in memory and on disk, so the history survives a server restart like the draft does.
"""
import json
import time

# changes kept per draft; undo reaches back this far, which in practice is the whole session
MAX_HISTORY = 100

# what only changes the view: switching tabs or saving again is not a change to undo
VIEW_FIELDS = ("editing_type", "last_modified")

SECTIONS = ("prep", "script", "cleanup")
SECTION_NAMES = {"prep": "Prep", "script": "Experiment", "cleanup": "Clean up"}

START_LABEL = "Start"

_FLOW_CONTROL = ("if", "while", "repeat", "wait", "pause", "comment")


def _content(state):
    """A draft state without the fields that only change the view."""
    return {key: value for key, value in (state or {}).items() if key not in VIEW_FIELDS}


def same_content(before, after):
    return _content(before) == _content(after)


def _section(state, section):
    return ((state or {}).get("script_dict") or {}).get(section) or []


def _without_position(step):
    # a step's ``id`` is its position, renumbered on every change; the order shows moves
    return {key: value for key, value in step.items() if key != "id"}


def _logical_steps(steps):
    """The steps of a section by uuid, in order: an if, its else and its endif are one step."""
    grouped = {}
    for step in steps:
        grouped.setdefault(step.get("uuid"), []).append(_without_position(step))
    return grouped


def step_name(step):
    """How a step is named in a history label, close to how the canvas shows it."""
    instrument = str(step.get("instrument") or "")
    action = str(step.get("action") or "")
    if instrument in _FLOW_CONTROL:
        return instrument.capitalize()
    if instrument == "variable":
        return f"variable {action}"
    if instrument == "math_variable":
        return f"math {action}"
    if instrument == "input":
        return f"input {action}"
    if instrument == "workflows":
        return f"workflow {action}"
    if instrument:
        return f"{instrument.split('.')[-1]}.{action}"
    return action or "step"


def _count(n, noun="step"):
    return f"{n} {noun}{'' if n == 1 else 's'}"


def changed_sections(before, after):
    return [section for section in SECTIONS
            if [_without_position(step) for step in _section(before, section)]
            != [_without_position(step) for step in _section(after, section)]]


def _moved_step(before_order, after_order):
    """The one step whose move turns one order into the other, if a single drag explains it."""
    for uid in before_order:
        if [u for u in before_order if u != uid] == [u for u in after_order if u != uid]:
            return uid
    return None


def _describe_section(before, after, section):
    old = _logical_steps(_section(before, section))
    new = _logical_steps(_section(after, section))
    old_order, new_order = list(old), list(new)
    added = [uid for uid in new_order if uid not in old]
    removed = [uid for uid in old_order if uid not in new]

    if added and not removed:
        # a copy and a second add of the same action look alike: the duplicate route says which
        if len(added) == 1:
            return f"Add {step_name(new[added[0]][0])}"
        return f"Add {_count(len(added))}"
    if removed and not added:
        if len(removed) == 1:
            return f"Delete {step_name(old[removed[0]][0])}"
        if not new_order:
            return "Clear all steps"
        return f"Delete {_count(len(removed))}"
    if not added and not removed:
        if old_order != new_order:
            moved = _moved_step(old_order, new_order)
            return f"Move {step_name(old[moved][0])}" if moved is not None else "Reorder steps"
        edited = [uid for uid in new_order if old[uid] != new[uid]]
        if len(edited) == 1:
            uid = edited[0]
            name = step_name(new[uid][0])
            toggled = [{**s, "disabled": False} for s in old[uid]] == [{**s, "disabled": False} for s in new[uid]]
            if toggled:
                return f"{'Disable' if new[uid][0].get('disabled') else 'Enable'} {name}"
            return f"Edit {name}"
        return f"Edit {_count(len(edited))}"
    return f"Edit {SECTION_NAMES.get(section, section)} steps"


def step_change(verb, step, section="script"):
    """A label for a change to one step, as :func:`describe_change` names it: "Duplicate balance.weigh (Prep)"."""
    label = f"{verb} {step_name(step)}"
    return label if section == "script" else f"{label} ({SECTION_NAMES.get(section, section)})"


def describe_change(before, after):
    """A short label for the change from one draft state to the next."""
    before, after = before or {}, after or {}
    sections = changed_sections(before, after)
    renamed = before.get("name") != after.get("name")
    new_identity = before.get("uuid") != after.get("uuid")
    name = after.get("name")

    if after.get("python_script") and after.get("python_script") != before.get("python_script"):
        return "Import Python code"
    if sections and (renamed or new_identity):
        if not any(_section(after, section) for section in SECTIONS):
            return "Clear workflow"
        return f"Open “{name}”" if name else "Open a workflow"
    if not sections:
        if renamed:
            if not name:
                return "Remove name"
            return f"Save as “{name}”" if new_identity else f"Rename to “{name}”"
        if before.get("status") != after.get("status"):
            return "Lock editing" if after.get("status") == "finalized" else "Unlock editing"
        if before.get("description") != after.get("description"):
            return "Edit description"
        if before.get("registered") != after.get("registered"):
            return "Register workflow" if after.get("registered") else "Unregister workflow"
        return "Edit workflow"
    if len(sections) == 1:
        section = sections[0]
        label = _describe_section(before, after, section)
        return label if section == "script" else f"{label} ({SECTION_NAMES[section]})"
    return "Edit workflow"


def section_to_show(current, target):
    """
    The tab to show once ``target`` is restored: the one the user is on, unless the restore
    changes nothing there, then the tab that does change, so an undo is never invisible.
    """
    showing = (current or {}).get("editing_type") or "script"
    changed = changed_sections(current, target)
    if not changed or showing in changed:
        return showing
    return changed[0]


class Timeline:
    """
    A draft's states, oldest first, and which one is the draft now.

    Every state is a serialized draft (a JSON string), so the stored draft and its point on the
    timeline can be compared and copied as they are. Entry 0 is where the history starts;
    every later entry is labelled with the change that led to it.
    """

    def __init__(self, entries=None, index=0, trimmed=False):
        self.entries = list(entries or [])
        self.index = min(max(int(index or 0), 0), max(len(self.entries) - 1, 0))
        self.trimmed = bool(trimmed)

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        return cls(data.get("entries"), data.get("index", 0), data.get("trimmed", False))

    def as_dict(self):
        return {"index": self.index, "trimmed": self.trimmed, "entries": self.entries}

    def __bool__(self):
        return bool(self.entries)

    @property
    def can_undo(self):
        return self.index > 0

    @property
    def can_redo(self):
        return self.index < len(self.entries) - 1

    def restart(self, state, label=START_LABEL, now=None):
        """Begin a new history at ``state``, e.g. a workflow just opened: nothing before it can be undone."""
        self.entries = [{"label": label, "time": now or time.time(), "state": state}]
        self.index = 0
        self.trimmed = False

    def amend(self, state):
        """The draft changed without a change to undo (a tab switch, a setting): follow it."""
        if self.entries:
            self.entries[self.index]["state"] = state

    def record(self, before, after, label=None, now=None):
        """
        Add ``after`` as the next state, unless it only changes the view; returns whether a
        change was added. ``before`` is the draft as stored until now: the current point takes
        it, so a save that was not recorded is part of what the next undo returns to.
        """
        before_data, after_data = json.loads(before), json.loads(after)
        if not self.entries:
            self.entries = [{"label": START_LABEL, "time": now or time.time(), "state": before}]
            self.index = 0
        else:
            self.entries[self.index]["state"] = before
        if same_content(before_data, after_data):
            self.entries[self.index]["state"] = after
            return False
        # a change after an undo starts a new branch: what was undone cannot be redone any more
        del self.entries[self.index + 1:]
        self.entries.append({"label": label or describe_change(before_data, after_data),
                             "time": now or time.time(), "state": after})
        overflow = len(self.entries) - (MAX_HISTORY + 1)
        if overflow > 0:
            del self.entries[:overflow]
            self.entries[0]["label"] = START_LABEL
            self.trimmed = True
        self.index = len(self.entries) - 1
        return True

    def move(self, target, current=None):
        """
        Make entry ``target`` the draft; returns its state and a message saying what was undone
        or redone, or ``(None, None)`` when there is no such entry. ``current`` is the stored
        draft, which decides the tab shown (see :func:`section_to_show`).
        """
        if not 0 <= target < len(self.entries) or target == self.index:
            return None, None
        current_data = json.loads(current or self.entries[self.index]["state"])
        target_data = json.loads(self.entries[target]["state"])
        target_data["editing_type"] = section_to_show(current_data, target_data)
        state = json.dumps(target_data)
        self.entries[target]["state"] = state

        steps = abs(target - self.index)
        if target < self.index:
            what = self.entries[self.index]["label"] if steps == 1 else _count(steps, "change")
            message = f"Undid {what}"
        else:
            what = self.entries[target]["label"] if steps == 1 else _count(steps, "change")
            message = f"Redid {what}"
        self.index = target
        return state, message

    def summary(self, entries=False):
        """What the designer shows: whether undo and redo can run, and what they would do."""
        data = {
            "index": self.index,
            "can_undo": self.can_undo,
            "can_redo": self.can_redo,
            "undo_label": self.entries[self.index]["label"] if self.can_undo else None,
            "redo_label": self.entries[self.index + 1]["label"] if self.can_redo else None,
            "trimmed": self.trimmed,
        }
        if entries:
            data["entries"] = [{"index": i, "label": entry["label"], "time": entry["time"]}
                               for i, entry in enumerate(self.entries)]
        return data
