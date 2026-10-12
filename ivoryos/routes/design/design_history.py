from flask import Blueprint, jsonify, render_template
from flask_login import current_user, login_required

from ivoryos.forms.dynamic_forms import create_action_buttons
from ivoryos.services.draft_service import get_draft_history, redo_draft, restore_draft, undo_draft
from ivoryos.services.draft_history import Timeline


history = Blueprint('design_history', __name__)


@history.app_template_global("draft_history")
def draft_history_state():
    """What undo and redo would do now, for the canvas to show (see canvas_main.html)."""
    if not current_user.is_authenticated:
        return Timeline().summary()
    return get_draft_history()


def _restored(script, message, nothing):
    if script is None:
        return jsonify({"success": False, "message": nothing, "history": get_draft_history()})
    html = render_template("components/canvas.html", script=script,
                           buttons_dict=create_action_buttons(script))
    return jsonify({"success": True, "message": message, "html": html, "history": get_draft_history()})


@history.get("/draft/history")
@login_required
def list_history():
    """
    .. :quickref: Workflow Design; the draft's undo history

    .. http:get:: /draft/history

    Every change to the current draft that can be undone, oldest first, and which one the
    draft is at now.

    :status 200: ``{"index", "can_undo", "can_redo", "undo_label", "redo_label", "entries"}``
    """
    return jsonify(get_draft_history(entries=True))


@history.post("/draft/history/undo")
@login_required
def undo():
    """
    .. :quickref: Workflow Design; undo the last change to the draft

    .. http:post:: /draft/history/undo

    :status 200: ``{"success", "message", "html", "history"}``; ``html`` is the canvas as it is now
    """
    script, message = undo_draft()
    return _restored(script, message, "Nothing to undo")


@history.post("/draft/history/redo")
@login_required
def redo():
    """
    .. :quickref: Workflow Design; redo the change last undone

    .. http:post:: /draft/history/redo

    :status 200: ``{"success", "message", "html", "history"}``; ``html`` is the canvas as it is now
    """
    script, message = redo_draft()
    return _restored(script, message, "Nothing to redo")


@history.post("/draft/history/<int:index>")
@login_required
def restore(index: int):
    """
    .. :quickref: Workflow Design; go to one point of the draft's history

    .. http:post:: /draft/history/<int:index>

    :param index: the point to go to, from :http:get:`/draft/history`
    :status 200: ``{"success", "message", "html", "history"}``; ``html`` is the canvas as it is now
    """
    script, message = restore_draft(index)
    return _restored(script, message, "Already there")
