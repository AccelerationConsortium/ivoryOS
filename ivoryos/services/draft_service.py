import json
import os

from flask import current_app
from flask_login import current_user
from werkzeug.utils import secure_filename

from ivoryos.parsers.serialize import sanitize_for_json
from ivoryos.script import Script


def _safe_user_id(user_id):
    safe_id = secure_filename(str(user_id or "anonymous"))
    return safe_id or "anonymous"


def get_draft_path(user_id):
    """Return the draft JSON path for a user id."""
    filename = f"draft_{_safe_user_id(user_id)}.json"
    return os.path.join(current_app.config["OUTPUT_FOLDER"], "scripts", "drafts", filename)


def get_script_for_user(user_id):
    """Load a user's draft script from server-side JSON storage."""
    draft_path = get_draft_path(user_id)

    if not os.path.exists(draft_path):
        return Script(author=user_id)

    try:
        with open(draft_path, "r", encoding="utf-8") as f:
            return Script.from_dict(json.load(f))
    except Exception:
        current_app.logger.exception("Error loading draft script for user %s", user_id)
        return Script(author=user_id)


def post_script_for_user(user_id, script, is_dict=False):
    """
    Save a user's draft script to server-side JSON storage.

    :param user_id: owner of the draft
    :param script: Script instance or serialized script dictionary
    :param is_dict: set True when ``script`` is already serialized
    """
    draft_path = get_draft_path(user_id)
    data = script if is_dict else script.as_dict()

    os.makedirs(os.path.dirname(draft_path), exist_ok=True)

    try:
        with open(draft_path, "w", encoding="utf-8") as f:
            json.dump(sanitize_for_json(data), f)
    except Exception:
        current_app.logger.exception("Error saving draft script for user %s", user_id)


def get_script_file():
    """Compatibility wrapper for current-user draft loading."""
    return get_script_for_user(current_user.get_id())


def post_script_file(script, is_dict=False):
    """Compatibility wrapper for current-user draft saving."""
    return post_script_for_user(current_user.get_id(), script, is_dict=is_dict)
