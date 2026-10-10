import json
import threading
import uuid
from collections import OrderedDict

from flask import current_app, session
from flask_login import current_user

from ivoryos.parsers.serialize import sanitize_for_json
from ivoryos.script import Script

# Drafts live in server memory, one per browser/client session. Only a short
# ``draft_id`` goes into the (cookie) session, so script size is not limited by
# the cookie, and two sessions of the same user (e.g. a browser and the Python
# client) no longer overwrite each other's draft.
MAX_DRAFTS = 256

_drafts = OrderedDict()  # "user_id:draft_id" -> JSON string, least recently used first
_lock = threading.Lock()


def _draft_key(user_id, draft_id):
    return f"{user_id or 'anonymous'}:{draft_id or ''}"


def new_draft_id():
    """Start a fresh draft slot for the current session and return its id."""
    draft_id = uuid.uuid4().hex
    session["draft_id"] = draft_id
    return draft_id


def current_draft_id():
    """Return the current session's draft id, creating one if needed."""
    return session.get("draft_id") or new_draft_id()


def get_script_for_user(user_id, draft_id=None):
    """Load a draft script from memory, or a new empty Script if none exists."""
    key = _draft_key(user_id, draft_id)
    with _lock:
        data = _drafts.get(key)
        if data is not None:
            _drafts.move_to_end(key)

    if data is None:
        return Script(author=user_id)

    try:
        return Script.from_dict(json.loads(data))
    except Exception:
        current_app.logger.exception("Error loading draft script for user %s", user_id)
        return Script(author=user_id)


def post_script_for_user(user_id, script, is_dict=False, draft_id=None):
    """
    Save a draft script to memory.

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
        _drafts[key] = payload
        _drafts.move_to_end(key)
        while len(_drafts) > MAX_DRAFTS:
            _drafts.popitem(last=False)


def discard_draft(user_id, draft_id=None):
    """Drop a draft from memory (e.g. on logout)."""
    with _lock:
        _drafts.pop(_draft_key(user_id, draft_id), None)


def get_script_file():
    """Load the current session's draft."""
    return get_script_for_user(current_user.get_id(), current_draft_id())


def post_script_file(script, is_dict=False):
    """Save the current session's draft."""
    return post_script_for_user(current_user.get_id(), script, is_dict=is_dict, draft_id=current_draft_id())
