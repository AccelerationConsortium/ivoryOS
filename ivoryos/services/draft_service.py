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

# A draft is the unsaved workflow in the designer. There is one per browser/client
# session: only a short ``draft_id`` goes into the (cookie) session, so script size
# is not limited by the cookie, and two sessions of the same user (e.g. a browser
# and the Python client) do not overwrite each other's draft.
#
# Every draft is also written to ``<OUTPUT_FOLDER>/scripts/drafts/``. The signed
# session cookie outlives the server process: after a restart the browser is still
# logged in and still asks for the same ``draft_id``, and the file is what brings
# the designer back exactly as it was. Memory is only a cache in front of the files.
MAX_DRAFTS = 256  # kept in memory and on disk; the least recently saved go first

_drafts = OrderedDict()  # "user_id:draft_id" -> JSON string, least recently used first
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


def _write_draft_file(user_id, draft_id, payload):
    path = get_draft_path(user_id, draft_id)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        is_new = not os.path.exists(path)
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(payload)
        # swap in whole, so a server killed mid-write never leaves a half-written draft behind
        os.replace(tmp_path, path)
        if is_new:
            _prune_draft_files()
    except Exception:
        current_app.logger.exception("Error writing draft file %s", path)


def _remove_draft_file(user_id, draft_id):
    path = get_draft_path(user_id, draft_id)
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except Exception:
        current_app.logger.exception("Error removing draft file %s", path)


def _prune_draft_files():
    """Drop the least recently saved draft files beyond MAX_DRAFTS: sessions that never logged out."""
    try:
        files = [entry for entry in os.scandir(get_drafts_folder())
                 if entry.is_file() and entry.name.endswith(".json")]
    except FileNotFoundError:
        return
    if len(files) <= MAX_DRAFTS:
        return
    files.sort(key=lambda entry: entry.stat().st_mtime)
    for entry in files[:len(files) - MAX_DRAFTS]:
        try:
            os.remove(entry.path)
        except OSError:
            current_app.logger.exception("Error pruning draft file %s", entry.path)


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


def post_script_for_user(user_id, script, is_dict=False, draft_id=None):
    """
    Save a draft script to memory and to its file on disk.

    :param user_id: owner of the draft
    :param script: Script instance or serialized script dictionary
    :param is_dict: set True when ``script`` is already serialized
    :param draft_id: session draft slot; see :func:`current_draft_id`
    """
    data = script if is_dict else script.as_dict()
    try:
        # store serialized so in-place edits never leak into the stored draft
        payload = json.dumps(sanitize_for_json(data))
    except Exception:
        current_app.logger.exception("Error saving draft script for user %s", user_id)
        return

    key = _draft_key(user_id, draft_id)
    with _lock:
        _cache(key, payload)
        _write_draft_file(user_id, draft_id, payload)


def discard_draft(user_id, draft_id=None):
    """Drop a draft from memory and disk (e.g. on logout)."""
    with _lock:
        _drafts.pop(_draft_key(user_id, draft_id), None)
        _remove_draft_file(user_id, draft_id)


def get_script_file():
    """Load the current session's draft."""
    return get_script_for_user(current_user.get_id(), current_draft_id())


def post_script_file(script, is_dict=False):
    """Save the current session's draft."""
    return post_script_for_user(current_user.get_id(), script, is_dict=is_dict, draft_id=current_draft_id())
