"""The config entries of a running task, editable while the run works through them.

The runner takes entries from here one batch at a time instead of slicing the
whole list when the run starts. That leaves the entries it has not reached open
to editing, adding, removing and reordering, and the entries of the batch that
is running open to edits for the steps it has not run yet. Entries that already
ran are never touched.

An entry is converted from text to its argument types only when its batch
starts, so an entry that cannot be converted fails on its own, with the reason,
instead of keeping every entry from running.

Nothing here is kept once the run ends: the run's iterations are the record of
the table, one per entry it reached, and the edits are kept as run events.
"""

import threading
from datetime import datetime

from ivoryos.parsers.type_conversions import convert_config_type
from ivoryos.runtime.task_conditions import blank_row, config_field_problems, config_row_problem, text_of, type_label

PENDING = "pending"
RUNNING = "running"
DONE = "done"
# cut off by a stop before all its steps ran
STOPPED = "stopped"
# its values could not run, or its steps raised an error the run could not get past
FAILED = "failed"
# entries whose turn has passed; their values are what ran, or why nothing did
FINISHED = (DONE, STOPPED, FAILED)
STATUSES = (PENDING, RUNNING, *FINISHED)


def describe(change):
    """One change as a line for the run log."""
    row = f"Row {change['row']}"
    if change["action"] == "add":
        return f"{row} added: {_pairs(change['values'])}"
    if change["action"] == "remove":
        return f"{row} removed: {_pairs(change['values'])}"
    line = f"{row}: '{change['field']}' changed from {change['from']!r} to {change['to']!r}"
    return f"{line} while it was running" if change.get("while_running") else line


def _pairs(values):
    return ", ".join(f"{key}={value!r}" for key, value in values.items())


def _now():
    return datetime.now().isoformat(timespec="seconds")


class LiveConfig:
    """The entries of one config run, shared between the runner and the editor.

    Every read and change holds ``lock``: the runner takes and finishes batches
    from its own thread while edits arrive from web requests.
    """

    def __init__(self, rows, arg_types, converted=False):
        """``rows`` as the task holds them. ``converted`` means they already carry
        their argument types, as a run submitted through the API does, and are
        used as they are rather than converted from text."""
        self.lock = threading.Lock()
        self.arg_types = dict(arg_types or {})
        self.fields = list(self.arg_types)
        self.entries = []
        self._last_id = 0
        for row in rows or []:
            self.entries.append(self._new_entry(
                {key: text_of(value) for key, value in row.items()},
                values=row if converted else None,
            ))

    def _new_entry(self, text, values=None):
        self._last_id += 1
        return {
            "id": self._last_id,
            "status": PENDING,
            "reason": None,
            # what the editor shows and what an edit replaces
            "text": text,
            # what the steps read once the entry runs; None until converted. While
            # it runs this is the step context itself, so outputs land here too
            "values": values,
            # input names when the entry started, to tell its inputs from its outputs
            "inputs": None,
            # changes saved for a running entry, handed to it between steps
            "pending_edits": {},
            "edited_while_running": False,
            # {input: why its value cannot run}, so a table can mark the cell itself
            "invalid": {} if values is not None else config_field_problems(text, self.fields, self.arg_types),
        }

    def _numbered(self):
        return enumerate(self.entries, start=1)

    # --- the runner's side -------------------------------------------------

    def problems(self):
        """``[(row number, reason)]`` for waiting entries that cannot run as they are."""
        found = []
        with self.lock:
            for number, entry in self._numbered():
                if entry["status"] != PENDING or entry["values"] is not None:
                    continue
                problem = config_row_problem(entry["text"], self.fields, self.arg_types)
                if problem:
                    found.append((number, problem))
        return found

    def start_batch(self, size):
        """Mark up to ``size`` waiting entries as running and return them.

        Also returns ``[(row number, entry)]`` for entries reached on the way that
        cannot be converted; those are marked failed, with the reason.
        """
        batch, failed = [], []
        with self.lock:
            for number, entry in self._numbered():
                if len(batch) >= size:
                    break
                if entry["status"] != PENDING:
                    continue
                if entry["values"] is None:
                    problem = config_row_problem(entry["text"], self.fields, self.arg_types)
                    if problem is None:
                        try:
                            entry["values"] = convert_config_type(dict(entry["text"]), self.arg_types)
                        except Exception as e:
                            problem = str(e)
                    if problem:
                        entry["status"], entry["reason"] = FAILED, problem
                        failed.append((number, entry))
                        continue
                entry["status"] = RUNNING
                entry["inputs"] = list(entry["values"])
                batch.append(entry)
        return batch, failed

    def waiting(self):
        """How many entries the run has not reached yet."""
        with self.lock:
            return sum(1 for entry in self.entries if entry["status"] == PENDING)

    def remaining(self):
        """The entries the run has not reached, as text, for when it ends without them."""
        with self.lock:
            return [dict(entry["text"]) for entry in self.entries if entry["status"] == PENDING]

    def apply_running_edits(self):
        """Hand changes saved for the running entries to the steps still to come.

        The runner calls this between steps, so no step sees a value change under
        it. Returns a log line for each change handed over.
        """
        lines = []
        with self.lock:
            for number, entry in self._numbered():
                if entry["status"] != RUNNING or not entry["pending_edits"]:
                    continue
                for field, edit in entry["pending_edits"].items():
                    entry["values"][field] = edit["value"]
                    entry["text"][field] = edit["text"]
                    lines.append(f"Row {number}: '{field}' is now {edit['text']!r} for the steps still to run.")
                entry["pending_edits"] = {}
                entry["edited_while_running"] = True
        return lines

    def inputs(self, batch):
        """The input values the batch's entries hold now, their outputs left out."""
        with self.lock:
            return [{key: entry["values"].get(key) for key in entry["inputs"]} for entry in batch]

    def edited_while_running(self, batch):
        return any(entry["edited_while_running"] for entry in batch)

    def finish_batch(self, batch, stopped=False):
        """Mark the batch done, or ``stopped`` when a stop cut its steps off.
        Returns a log line for each change that came after its entry's last step
        and so was never used."""
        lines = []
        with self.lock:
            for number, entry in self._numbered():
                if not any(entry is done for done in batch):
                    continue
                for field, edit in entry["pending_edits"].items():
                    lines.append(f"Row {number}: the change of '{field}' to {edit['text']!r} "
                                 f"came after its last step, so it was not used.")
                entry["pending_edits"] = {}
                entry["status"] = STOPPED if stopped else DONE
        return lines

    def close(self):
        """Mark entries still running as failed; only an error leaves any when the run ends."""
        with self.lock:
            for entry in self.entries:
                if entry["status"] == RUNNING:
                    entry["status"] = FAILED
                    entry["pending_edits"] = {}

    # --- the editor's side -------------------------------------------------

    def _columns(self):
        extra = []
        for entry in self.entries:
            extra.extend(key for key in entry["text"] if key not in self.fields and key not in extra)
        return [*self.fields, *extra]

    @staticmethod
    def _shown(entry):
        """An entry's text with any change still waiting to be handed to its steps."""
        text = dict(entry["text"])
        text.update({field: edit["text"] for field, edit in entry["pending_edits"].items()})
        return text

    def view(self):
        """The table as the editor shows it, with each entry's status."""
        with self.lock:
            columns = self._columns()
            counts = {status: 0 for status in STATUSES}
            rows = []
            for entry in self.entries:
                counts[entry["status"]] += 1
                shown = self._shown(entry)
                rows.append({
                    "id": entry["id"],
                    "status": entry["status"],
                    "reason": entry["reason"],
                    "invalid": entry["invalid"],
                    "values": [shown.get(column, "") for column in columns],
                })
            return {
                "fields": columns,
                "types": {field: type_label(self.arg_types.get(field)) for field in self.fields},
                "rows": rows,
                "counts": counts,
            }

    def edit(self, rows):
        """Apply an edited table of the entries that have not finished.

        ``rows`` lists the running and waiting entries in their new order, each as
        ``{"id": entry id, or None for a new one, "values": {input: text},
        "number": the row number the editor showed}``. A value that cannot run
        refuses the whole edit, so nothing changes.

        The run keeps going while the table is edited, so an entry may finish, or
        start, before the edit arrives. A finished entry stays as it ran, and a
        running one cannot be removed; those are reported back rather than refused.

        Returns ``(changes, notes)``: the changes made and what could not be applied.
        """
        if not isinstance(rows, list):
            raise ValueError("Expected the table as a list of rows.")
        with self.lock:
            by_id = {entry["id"]: entry for entry in self.entries}
            planned, notes = [], []
            for position, row in enumerate(rows, start=1):
                if not isinstance(row, dict) or not isinstance(row.get("values"), dict):
                    raise ValueError(f"Row {position} is not a set of input values.")
                number = row.get("number") or position
                text = {str(key): "" if value is None else str(value) for key, value in row["values"].items()}
                entry = by_id.get(row.get("id"))
                if row.get("id") is not None and entry is None:
                    notes.append(f"Row {number} is no longer part of this run, so its changes were not applied.")
                    continue
                if entry is None and blank_row(text):
                    continue
                if entry is not None and entry["status"] in FINISHED:
                    if text != {key: self._shown(entry).get(key, "") for key in text}:
                        notes.append(f"Row {number} finished before the changes were saved, so it ran as it was.")
                    continue
                problem = config_row_problem(text, self.fields, self.arg_types)
                if problem:
                    raise ValueError(f"Row {number}: {problem}")
                planned.append((number, entry, text))

            kept = {id(entry) for _, entry, _ in planned if entry is not None}
            for number, entry in self._numbered():
                if entry["status"] == RUNNING and id(entry) not in kept:
                    notes.append(f"Row {number} is running, so it was not removed.")

            # every value is usable, so from here on nothing can refuse the edit
            changes = []
            for number, entry in self._numbered():
                if entry["status"] == PENDING and id(entry) not in kept:
                    changes.append({"time": _now(), "row": number, "action": "remove", "values": self._shown(entry)})
            waiting = []
            for number, entry, text in planned:
                if entry is None:
                    entry = self._new_entry(text)
                    changes.append({"time": _now(), "row": number, "action": "add", "values": dict(text)})
                elif entry["status"] == RUNNING:
                    changes.extend(self._edit_running(entry, number, text))
                else:
                    changes.extend(self._edit_waiting(entry, number, text))
                if entry["status"] == PENDING:
                    waiting.append(entry)
            # entries that started keep their place; the waiting ones take the new order
            self.entries = [entry for entry in self.entries if entry["status"] != PENDING] + waiting
            return changes, notes

    def _field_changes(self, entry, number, text):
        shown = self._shown(entry)
        return [{"time": _now(), "row": number, "action": "edit", "field": field,
                 "from": shown.get(field, ""), "to": value}
                for field, value in text.items() if shown.get(field, "") != value]

    def _edit_waiting(self, entry, number, text):
        changes = self._field_changes(entry, number, text)
        if changes:
            entry["text"] = text
            # converted again from the new text when the entry starts
            entry["values"] = None
            # an edit is only accepted when every value can run
            entry["invalid"] = {}
        return changes

    def _edit_running(self, entry, number, text):
        changes = self._field_changes(entry, number, text)
        for change in changes:
            field = change["field"]
            change["while_running"] = True
            value = convert_config_type({field: text[field]}, self.arg_types)[field]
            entry["pending_edits"][field] = {"text": text[field], "value": value}
        return changes
