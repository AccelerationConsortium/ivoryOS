import json
import os
import threading
import uuid
from collections import OrderedDict

from flask import current_app, session
from flask_login import current_user
from werkzeug.utils import secure_filename

from ivoryos.parsers.serialize import sanitize_for_json
from ivoryos.script import Script
from ivoryos.services.draft_history import START_LABEL, Timeline

# A draft is the unsaved workflow in the designer. There is one per browser/client
# session: only a short ``draft_id`` goes into the (cookie) session, so script size
# is not limited by the cookie, and two sessions of the same user (e.g. a browser
# and the Python client) do not overwrite each other's draft.
#
# Every draft is also written to ``<OUTPUT_FOLDER>/scripts/drafts/``. The signed
# session cookie outlives the server process: after a restart the browser is still
# logged in and still asks for the same ``draft_id``, and the file is what brings
# the designer back exactly as it was. Memory is only a cache in front of the files.
#
# Each draft also has a history beside it, ``draft_..._<id>.history.json``: the timeline
# undo and redo move along (see ``draft_history``). Every save goes through
# :func:`post_script_for_user`, so every change made in the designer can be undone, and the
# history comes back after a restart with the draft. It covers one workflow: opening,
# importing or starting another begins a new one (``new_history``).
MAX_DRAFTS = 256  # kept in memory and on disk; the least recently saved go first
HISTORY_SUFFIX = ".history.json"

_drafts = OrderedDict()  # "user_id:draft_id" -> JSON string, least recently used first
_histories = OrderedDict()  # "user_id:draft_id" -> Timeline, least recently used first
_lock = threading.Lock()


def _draft_key(user_id, draft_id):
    return f"{user_id or 'anonymous'}:{draft_id or ''}"


def _safe_name(value, default):
    safe = secure_filename(str(value or default))
    return safe or default


def get_drafts_folder():
    """Folder holding the on-disk copy of every session's draft."""
    return os.path.join(current_app.config["OUTPUT_FOLDER"], "scripts", "drafts")


def get_draft_path(user_id, draft_id):
    """Return the JSON path where one session's draft is kept across server restarts."""
    filename = f"draft_{_safe_name(user_id, 'anonymous')}_{_safe_name(draft_id, 'default')}.json"
    return os.path.join(get_drafts_folder(), filename)


def get_history_path(user_id, draft_id):
    """Return the JSON path of a draft's undo history, beside the draft."""
    return _history_path_of(get_draft_path(user_id, draft_id))


def _history_path_of(draft_path):
    return draft_path[:-len(".json")] + HISTORY_SUFFIX


def new_draft_id():
    """Start a fresh draft slot for the current session and return its id."""
    draft_id = uuid.uuid4().hex
    session["draft_id"] = draft_id
    return draft_id


def current_draft_id():
    """Return the current session's draft id, creating one if needed."""
    return session.get("draft_id") or new_draft_id()


def _cache(key, payload):
    """Remember a serialized draft as the most recently used one. Call with ``_lock`` held."""
    _drafts[key] = payload
    _drafts.move_to_end(key)
    while len(_drafts) > MAX_DRAFTS:
        _drafts.popitem(last=False)


def _read_draft_file(user_id, draft_id):
    path = get_draft_path(user_id, draft_id)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None
    except Exception:
        current_app.logger.exception("Error reading draft file %s", path)
        return None


def _write_file(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(payload)
    # swap in whole, so a server killed mid-write never leaves a half-written file behind
    os.replace(tmp_path, path)


def _write_draft_file(user_id, draft_id, payload):
    path = get_draft_path(user_id, draft_id)
    try:
        is_new = not os.path.exists(path)
        _write_file(path, payload)
        if is_new:
            _prune_draft_files()
    except Exception:
        current_app.logger.exception("Error writing draft file %s", path)


def _remove_file(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except Exception:
        current_app.logger.exception("Error removing draft file %s", path)


def _remove_draft_file(user_id, draft_id):
    _remove_file(get_draft_path(user_id, draft_id))
    _remove_file(get_history_path(user_id, draft_id))


def _prune_draft_files():
    """
    Drop the least recently saved drafts beyond MAX_DRAFTS, with their histories: sessions
    that never logged out. A history whose draft is gone goes too.
    """
    try:
        entries = [entry for entry in os.scandir(get_drafts_folder()) if entry.is_file()]
    except FileNotFoundError:
        return
    drafts = [entry for entry in entries
              if entry.name.endswith(".json") and not entry.name.endswith(HISTORY_SUFFIX)]
    drafts.sort(key=lambda entry: entry.stat().st_mtime)
    for entry in drafts[:max(len(drafts) - MAX_DRAFTS, 0)]:
        _remove_file(entry.path)
        _remove_file(_history_path_of(entry.path))
    for entry in entries:
        if entry.name.endswith(HISTORY_SUFFIX):
            draft_path = entry.path[:-len(HISTORY_SUFFIX)] + ".json"
            if not os.path.exists(draft_path):
                _remove_file(entry.path)


def _stored_payload(key, user_id, draft_id):
    """The draft as stored now, serialized, or None. Call with ``_lock`` held."""
    data = _drafts.get(key)
    if data is None:
        data = _read_draft_file(user_id, draft_id)
        if data is not None:
            _cache(key, data)
    return data


def _load_timeline(key, user_id, draft_id):
    """A draft's undo history: from memory, else from its file, else a new one. Call with ``_lock`` held."""
    timeline = _histories.get(key)
    if timeline is None:
        timeline = Timeline()
        path = get_history_path(user_id, draft_id)
        try:
            with open(path, "r", encoding="utf-8") as f:
                timeline = Timeline.from_dict(json.load(f))
        except FileNotFoundError:
            pass
        except Exception:
            current_app.logger.exception("Error reading draft history %s", path)
    _histories[key] = timeline
    _histories.move_to_end(key)
    while len(_histories) > MAX_DRAFTS:
        _histories.popitem(last=False)
    return timeline


def _save_timeline(user_id, draft_id, timeline):
    """Write a draft's undo history beside it. Call with ``_lock`` held."""
    path = get_history_path(user_id, draft_id)
    try:
        _write_file(path, json.dumps(timeline.as_dict()))
    except Exception:
        current_app.logger.exception("Error writing draft history %s", path)


def get_script_for_user(user_id, draft_id=None):
    """Load a draft script, or a new empty Script if the session has none yet."""
    key = _draft_key(user_id, draft_id)
    with _lock:
        data = _drafts.get(key)
        if data is not None:
            _drafts.move_to_end(key)
        else:
            # cold cache, e.g. right after a server restart: the file is the draft of record
            data = _read_draft_file(user_id, draft_id)
            if data is not None:
                _cache(key, data)

    if data is None:
        return Script(author=user_id)

    try:
        return Script.from_dict(json.loads(data))
    except Exception:
        current_app.logger.exception("Error loading draft script for user %s", user_id)
        return Script(author=user_id)


def _serialize(data):
    return json.dumps(sanitize_for_json(data))


def post_script_for_user(user_id, script, is_dict=False, draft_id=None, record=True, label=None,
                         new_history=False):
    """
    Save a draft script to memory and to its file on disk, as a change that can be undone.

    :param user_id: owner of the draft
    :param script: Script instance or serialized script dictionary
    :param is_dict: set True when ``script`` is already serialized
    :param draft_id: session draft slot; see :func:`current_draft_id`
    :param record: False for a save the user did not make (e.g. filling in the deck), which
        is kept in the current point of the history instead of becoming a change to undo
    :param label: how the change is named in the history; worked out from what changed when
        not given (see :func:`ivoryos.services.draft_history.describe_change`)
    :param new_history: True when ``script`` is another workflow (opened, imported or new): its
        history starts here, named ``label``, so undo never goes back to the workflow before
    """
    data = script if is_dict else script.as_dict()
    try:
        # store serialized so in-place edits never leak into the stored draft
        payload = _serialize(data)
    except Exception:
        current_app.logger.exception("Error saving draft script for user %s", user_id)
        return

    key = _draft_key(user_id, draft_id)
    with _lock:
        before = _stored_payload(key, user_id, draft_id)
        _cache(key, payload)
        _write_draft_file(user_id, draft_id, payload)

        timeline = _load_timeline(key, user_id, draft_id)
        if new_history:
            timeline.restart(payload, label=label or START_LABEL)
        elif record:
            # a first save starts the history from what the designer showed: an empty draft
            before = before or _serialize(Script(author=user_id).as_dict())
            timeline.record(before, payload, label=label)
        elif not timeline:
            return
        else:
            timeline.amend(payload)
        _save_timeline(user_id, draft_id, timeline)


def _move_history(user_id, draft_id, target_of):
    key = _draft_key(user_id, draft_id)
    with _lock:
        timeline = _load_timeline(key, user_id, draft_id)
        current = _stored_payload(key, user_id, draft_id)
        if current is not None:
            timeline.amend(current)
        state, message = timeline.move(target_of(timeline), current)
        if state is None:
            return None, None
        _cache(key, state)
        _write_draft_file(user_id, draft_id, state)
        _save_timeline(user_id, draft_id, timeline)
    return Script.from_dict(json.loads(state)), message


def undo_for_user(user_id, draft_id=None):
    """Undo the draft's last change; returns the draft now and what was undone, or ``(None, None)``."""
    return _move_history(user_id, draft_id, lambda timeline: timeline.index - 1)


def redo_for_user(user_id, draft_id=None):
    """Redo the change last undone; returns the draft now and what was redone, or ``(None, None)``."""
    return _move_history(user_id, draft_id, lambda timeline: timeline.index + 1)


def restore_for_user(user_id, draft_id, index):
    """Go back, or forward, to one point of the draft's history (see :func:`draft_history_for_user`)."""
    return _move_history(user_id, draft_id, lambda timeline: int(index))


def draft_history_for_user(user_id, draft_id=None, entries=False):
    """What undo and redo would do now; with ``entries``, every point of the history too."""
    with _lock:
        return _load_timeline(_draft_key(user_id, draft_id), user_id, draft_id).summary(entries=entries)


def discard_draft(user_id, draft_id=None):
    """Drop a draft and its history from memory and disk (e.g. on logout)."""
    key = _draft_key(user_id, draft_id)
    with _lock:
        _drafts.pop(key, None)
        _histories.pop(key, None)
        _remove_draft_file(user_id, draft_id)


def get_script_file():
    """Load the current session's draft."""
    return get_script_for_user(current_user.get_id(), current_draft_id())


def post_script_file(script, is_dict=False, record=True, label=None, new_history=False):
    """Save the current session's draft; see :func:`post_script_for_user`."""
    return post_script_for_user(current_user.get_id(), script, is_dict=is_dict, draft_id=current_draft_id(),
                                record=record, label=label, new_history=new_history)


def undo_draft():
    """Undo the current session's last change to its draft."""
    return undo_for_user(current_user.get_id(), current_draft_id())


def redo_draft():
    """Redo the current session's change last undone."""
    return redo_for_user(current_user.get_id(), current_draft_id())


def restore_draft(index):
    """Take the current session's draft to one point of its history."""
    return restore_for_user(current_user.get_id(), current_draft_id(), index)


def get_draft_history(entries=False):
    """The current session's undo history; see :func:`draft_history_for_user`."""
    return draft_history_for_user(current_user.get_id(), current_draft_id(), entries=entries)
