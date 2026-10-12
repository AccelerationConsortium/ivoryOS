"""Where the running task is, for the progress bar and the live config table.

The runner reports each move here: the task starting, a phase starting, a step starting, an
iteration starting, rows of a config table starting and finishing, and the task ending. Each
move goes to the pages as one ``progress`` event holding the whole picture (:meth:`snapshot`),
so a page that connects, reconnects or is reloaded mid-run is shown exactly what a page that
watched from the start shows (``socket_handlers.handle_connect`` sends it the snapshot).

The pages work out the percentage themselves (``runPercent`` in socket_handler.js): each phase
counts as its number of steps, the experiment phase once per iteration, so the bar moves through
prep and cleanup too, and a config table that grows or shrinks while it runs moves the total.
Progress is reported between steps, not within one.
"""

import math
import threading

from ivoryos.runtime import run_events

IDLE, RUNNING, DONE, STOPPED, FAILED = "idle", "running", "done", "stopped", "failed"
# the sections of a workflow, in the order they run; "script" is the experiment phase
PHASES = ("prep", "script", "cleanup")

_OUTCOMES = {run_events.COMPLETED: DONE, run_events.STOPPED: STOPPED, run_events.FAILED: FAILED}


def state_of(outcome):
    """A run's outcome (``run_events.outcome``) as the state the progress bar shows."""
    return _OUTCOMES.get(outcome, DONE)


class RunProgress:
    """The running task's place, kept by the runner and read by whoever connects.

    The runner thread moves it and a page connecting reads it, so every read and move
    holds ``_lock``. It keeps the last task's end state until the next task starts, so a
    page that reconnects after a run ended still sees how it ended.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._clear()

    def _clear(self):
        self.uid = None
        self.run_name = None
        self.state = IDLE
        self.phase = None
        self.steps = {phase: 0 for phase in PHASES}
        # the furthest step reached in the phase, or this iteration of it: a loop going
        # round again holds the bar where it is rather than moving it back
        self.step = 0
        self.iteration = 0
        self.iterations = None
        # the live table of a config run (``LiveConfig``), whose rows set the iterations
        self.table = None
        self.batch_size = 1
        # the table as it ended (``LiveConfig.final_state``), kept once a config run's table closes
        self.final_table = None

    # --- the runner's side -------------------------------------------------

    def start(self, uid, run_name, script, iterations=None):
        """A task starting: its steps per phase, and the iterations it expects to run."""
        with self._lock:
            self._clear()
            self.uid, self.run_name, self.state = uid, run_name, RUNNING
            script_dict = getattr(script, "script_dict", None) or {}
            self.steps = {phase: len(script_dict.get(phase) or []) for phase in PHASES}
            self.iterations = iterations

    def enter_phase(self, phase):
        with self._lock:
            if phase == "cleanup" and self.iterations is not None:
                # a stop or an early end ran fewer iterations than planned: what ran is the total
                self.iterations = min(self.iterations, self.iteration)
            self.phase, self.step = phase, 0

    def start_iteration(self, iteration, iterations=None):
        """An iteration of the experiment phase starting, the first being 1."""
        with self._lock:
            self.phase, self.step, self.iteration = "script", 0, iteration
            if iterations is not None:
                self.iterations = iterations

    def at_step(self, section, step_number):
        """A step starting; returns whether the run moved on. Only the phase's own steps count,
        not those of a workflow it calls, which run under a section of their own."""
        with self._lock:
            if section != self.phase or step_number <= self.step:
                return False
            self.step = step_number
            return True

    def follow_table(self, live, batch_size=1):
        """A config run's table: its rows, waiting ones included, set the iterations."""
        with self._lock:
            self.table, self.batch_size = live, max(int(batch_size or 1), 1)

    def close_table(self, final_table):
        """The table's run is over: the iterations are the ones that ran."""
        with self._lock:
            self.iterations = self.iteration
            self.table = None
            self.final_table = final_table

    def finish(self, state):
        with self._lock:
            self.state = state
            self.table = None

    # --- the pages' side -----------------------------------------------------

    def snapshot(self, changed_rows=None):
        """The whole picture as the ``progress`` event sends it.

        ``changed_rows`` are config rows whose status just changed, as
        ``LiveConfig.row_states`` gives them, for an open table editor to update in place.
        """
        with self._lock:
            data = {
                "uid": self.uid,
                "run_name": self.run_name,
                "state": self.state,
                "phase": self.phase,
                "steps": dict(self.steps),
                "step": self.step,
                "iteration": self.iteration,
                "iterations": self.iterations,
            }
            if self.table is not None:
                rows = self.table.progress()
                # the batches still to come follow the ones already started
                data["iterations"] = self.iteration + math.ceil(rows["waiting"] / self.batch_size)
                data["table"] = {**rows, "changed": changed_rows or []}
            elif self.final_table is not None:
                # every row as it ended, for a page that was not connected when it did
                data["table"] = {**self.final_table, "closed": True}
            return data
