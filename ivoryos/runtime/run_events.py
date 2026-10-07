"""What happened to a run besides its steps, and how the run ended.

Steps are recorded one by one already. What they do not show is why a run went
the way it did: the user pausing it or stopping it, an error that paused it,
rows of its config table skipped or edited. Those are kept on the run as events
with a time, so its page can put them on the timeline next to the iterations.
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
ROW_SKIPPED = "row_skipped"
EARLY_STOP = "early_stop"

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
    ROW_SKIPPED: "Row skipped",
    EARLY_STOP: "Early stop",
}

# how a run ended
COMPLETED = "completed"
STOPPED = "stopped"
FAILED = "error"


def event(kind, detail=None):
    return {"time": datetime.now().isoformat(timespec="seconds"), "kind": kind, "detail": detail}


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
