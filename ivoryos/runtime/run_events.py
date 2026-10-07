"""What happened to a run besides its steps, and how the run ended.

Steps are recorded one by one already. What they do not show is why a run went
the way it did: the user pausing it or stopping it, an error that paused it,
its config table being edited, rows of the table it never reached. Those are
kept on the run as events with a time, so its page can put them on the timeline
next to the iterations.
"""

from datetime import datetime

# the user's actions
PAUSED = "paused"
RESUMED = "resumed"
RETRIED = "retried"
STOP_AFTER_ITERATION = "stop_after_iteration"
STOP_NOW = "stop_now"
CLEANUP_SKIPPED = "cleanup_skipped"
TABLE_EDITED = "table_edited"
# what the run ran into
ERROR = "error"
INTERVENTION = "intervention"
EARLY_STOP = "early_stop"
# config rows left when the run ended, kept with the event as "rows"
ROWS_NOT_RUN = "rows_not_run"

LABELS = {
    PAUSED: "Paused",
    RESUMED: "Resumed",
    RETRIED: "Retried step",
    STOP_AFTER_ITERATION: "Stop after this iteration",
    STOP_NOW: "Stopped",
    CLEANUP_SKIPPED: "Cleanup skipped",
    TABLE_EDITED: "Table edited",
    ERROR: "Error",
    INTERVENTION: "Intervention needed",
    EARLY_STOP: "Early stop",
    ROWS_NOT_RUN: "Rows not run",
}

# how a run ended
COMPLETED = "completed"
STOPPED = "stopped"
FAILED = "error"


def event(kind, detail=None, **data):
    """An event as kept on the run; ``data`` adds whatever else it needs to keep,
    such as the changes of a table edit."""
    return {"time": datetime.now().isoformat(timespec="seconds"), "kind": kind, "detail": detail, **data}


def outcome(error, cut_short, stopped):
    """How a run ended: an error, a stop that left work undone, or neither.

    ``cut_short`` is a stop after an iteration that left iterations or rows not
    run; one that came during the last iteration changes nothing, so the run
    still completed. ``stopped`` is a stop that cut steps off where they were.
    """
    if error:
        return FAILED
    if cut_short or stopped:
        return STOPPED
    return COMPLETED
