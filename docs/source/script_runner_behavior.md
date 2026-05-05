# Script Runner Behavior

This document summarizes how `ScriptRunner` currently handles workflow execution, pause/resume, stop controls, cleanup, and the execution queue.

## Main Model

`ScriptRunner` runs workflow tasks through a single shared runner lock. Only one workflow task runs at a time.

When a new workflow is submitted through the execution page, `run_script(...)` creates a task object and appends it to `execution_queue`.

- If the runner is idle, `_process_queue()` starts the next task immediately.
- If another workflow is running, `_process_queue()` returns `"queued"` and the task stays in `execution_queue`.
- When a running workflow finishes, the runner releases the lock and calls `_process_queue()` again to start the next queued task if the queue is not paused.

Submitting a new task explicitly clears `paused` and `queue_paused`, then emits `pause_status: false`. In other words, adding a new run currently unpauses the queue.

## Workflow Phases

A workflow runs in this order:

1. `prep`
2. `script`, repeated by repeat count, optimizer iterations, or config batches
3. `cleanup`

The `script` phase may run multiple iterations. For config mode, iterations are grouped by `batch_size`.

## Pause / Resume

Pause is cooperative. It does not interrupt an instrument call that is already running.

When the user clicks pause/resume, the frontend emits `pause`, which calls `runner.toggle_pause()`.

When pausing:

- `paused = True`
- `queue_paused = True`
- `pause_event.clear()`
- frontend receives `pause_status: true`

When resuming:

- `paused = False`
- `queue_paused = False`
- `pause_event.set()`
- frontend receives `pause_status: false`
- `_process_queue()` is called, so queued tasks may start if the runner is idle

Execution checks `pause_event.wait()` after actions and between some batched contexts. This means pause usually takes effect after the current action completes, not in the middle of that action.

## Human Intervention And Errors

A workflow step can call the runner-level `pause(...)` helper. That raises `HumanInterventionRequired`.

When human intervention happens:

- frontend receives `human_intervention`
- the active step is paused through `toggle_pause()`
- the queue is also paused
- the user must continue, retry, stop, or otherwise resume from the UI

When a normal exception happens during a step:

- frontend receives `error`
- the step is marked as failed in the database
- `toggle_pause()` is called
- the queue is paused

`Retry` sets `runner.retry = True` and toggles pause. If the failed step had `run_error = True`, `_execute_action(...)` repeats that same step once.

## Stop Pending

The "stop pending" control emits `abort_pending`.

Backend behavior:

- `stop_pending_event.set()`
- the current running action is allowed to finish
- the current iteration is allowed to finish
- future repeat/config iterations stop at the next iteration boundary
- cleanup still runs by default

The UI also has a cleanup checkbox:

- If cleanup is enabled, only pending script iterations are skipped.
- If cleanup is disabled, `abort_cleanup()` is also called and the cleanup phase is skipped.

The "continue execution queue" checkbox controls what happens after the current workflow finishes winding down:

- Checked / `continue_queue = true`: queue is not paused, so the next queued task can start.
- Unchecked / `continue_queue = false`: `queue_paused = True`, so queued tasks remain queued until the user resumes.

## Stop Current

The "stop current" control emits `abort_current`.

Backend behavior:

- `stop_current_event.set()`
- `abort_pending()` is called, so future iterations are skipped
- `abort_cleanup()` is called, so cleanup is skipped
- current action is not force-killed

This is still cooperative. The runner checks `stop_current_event` before starting an action. If a device call or Python function is already running, the runner waits for it to return. The special `wait` action uses `safe_sleep(...)`, so it can exit early when stop-current is requested.

After stop-current is requested, the remaining steps in the current workflow are skipped as the runner reaches stop checks.

The "continue execution queue" checkbox controls the queue after the current workflow stops:

- Checked / `continue_queue = true`: the runner may continue with the next queued task.
- Unchecked / `continue_queue = false`: the queue is paused after the current workflow stops.

## Queue Behavior

The queue is stored in memory as `execution_queue`.

Queued tasks can be:

- viewed through `/executions/queue`
- deleted through `/executions/queue/delete`
- reordered through `/executions/queue/reorder`
- renamed through `/executions/queue/task/rename`

`queue_paused` controls whether `_process_queue()` is allowed to start the next queued task.

Important cases:

- Manual pause sets `queue_paused = True`.
- Resume sets `queue_paused = False`.
- Stop pending/current with `continue_queue = false` sets `queue_paused = True`.
- Stop pending/current with `continue_queue = true` sets `queue_paused = False`.
- Submitting a new workflow currently sets `queue_paused = False`.

## Auto-Pause Summary

The runner auto-pauses on:

- human intervention
- execution error
- manual pause
- stop pending/current when `continue_queue = false`

The runner does not auto-pause on normal task completion. If the queue has pending tasks and `queue_paused` is false, the next task starts automatically.

## Practical Meaning Of UI Controls

| Control | Meaning |
| --- | --- |
| Pause | Finish the current action, then wait before continuing. Also prevents queued tasks from starting. |
| Resume | Continue the paused workflow or queue. |
| Retry | Resume and retry the failed step if the current paused step recorded an error. |
| Stop pending | Finish the current iteration, skip remaining iterations, optionally run cleanup. |
| Stop current | Stop the current workflow as soon as cooperative stop checks are reached; skip cleanup. |
| Continue execution queue | If checked, start the next queued task after the current workflow winds down. If unchecked, leave the queue paused. |

