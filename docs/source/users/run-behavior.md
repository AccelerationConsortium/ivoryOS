# Run behavior

This page explains what happens when a workflow is executed from the IvoryOS UI.

## Workflow phases

Every workflow has three phases:

1. **Prep** runs once before the main experiment.
2. **Script** runs the main workflow actions. This phase may repeat by repeat count, parameter rows, batches, or optimizer iterations.
3. **Cleanup** runs once after the script phase, unless the run is stopped in a way that skips cleanup.

Use prep for setup that should happen once, such as homing a robot, priming a line, or checking an initial condition. Use cleanup for shutdown steps such as turning off heaters, closing valves, or returning a device to a safe state.

## Repeat, parameter, and optimizer runs

The available run setup depends on the workflow:

| Workflow shape | Run setup |
| --- | --- |
| No configurable parameters | Repeat count |
| Configurable parameters | Parameter table or CSV |
| Configurable parameters and numerical outputs | Optimizer setup |

The script phase is the part that repeats. Prep and cleanup stay once-per-run.

## Saved outputs

Workflow actions can save return values for later steps. When an action returns a fixed-length tuple, each tuple item can be saved under its own name.

Saved outputs are recorded with the workflow run and can be reviewed from the data pages.

## Pause and resume

Pause is cooperative. If a device call is already running, IvoryOS waits for that action to finish before pausing.

Use **Resume** to continue the paused workflow. The execution queue is also paused while the current run is paused.

## Human intervention and errors

A workflow can pause for human intervention, or IvoryOS can pause after an execution error.

When this happens, use the UI to continue, retry, stop, or otherwise resolve the paused run. **Retry** repeats the failed step when the current paused step recorded an error.

## Stop pending

Use **Stop pending** when the current iteration should finish but future iterations should be skipped.

Cleanup still runs by default. If the cleanup checkbox is disabled, the cleanup phase is skipped too.

## Stop current

Use **Stop current** when the current workflow should stop as soon as IvoryOS reaches a cooperative stop check.

This does not force-kill a Python function or hardware call that is already running. IvoryOS waits for the active action to return, then skips the remaining workflow steps and cleanup.

## Execution queue

Only one workflow task runs at a time. Additional submitted runs wait in the execution queue.

The **Continue execution queue** option controls what happens after a stopped workflow winds down:

| Option | Behavior |
| --- | --- |
| Checked | The next queued task can start. |
| Unchecked | The queue stays paused until resumed. |

Normal task completion does not pause the queue. If queued tasks exist and the queue is not paused, the next task starts automatically.
