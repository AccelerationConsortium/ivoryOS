# Using the UI

The IvoryOS browser UI is organized around operating a platform: call available functions, design reusable workflows, run experiments, and inspect the resulting records.


## Devices

Use **Devices** to inspect the instruments, modules, and functions exposed by the running Python script. Device methods can be called directly for setup, manual checks, calibration, or one-off operations.

When a method has typed arguments, IvoryOS creates matching input controls where possible. Enum arguments appear as dropdown-style choices, while basic values such as numbers and strings appear as editable fields.

```{image} ../_static/control.png
:alt: IvoryOS Devices page
```

## Design

Use **Design** to build workflows from available actions.

1. Add actions from the available devices or workflow functions.
2. Fill constant values directly into action arguments.
3. Use `#parameter_name` when a value should be configured later for a run.
4. Add flow-control actions such as wait, comment, if, or while when the workflow needs structure.
5. Save return values from actions when later steps need to reuse them.
6. Save the workflow so it can be reused from the library or execution page.

If an action returns a fixed-length tuple, the designer can show one save field per returned item so multiple outputs can be named separately.

Every change to the workflow you are editing can be undone: adding, editing, moving,
disabling, duplicating or deleting a step, and renaming it. Undo goes back to when that
workflow was opened from the library, imported, or started with **New**, and no further, so
it never brings back a different workflow. Use the undo and redo buttons beside **Save As**,
or the keyboard:

| Action | Windows and Linux | macOS |
|---|---|---|
| Undo | Ctrl+Z | ⌘Z |
| Redo | Ctrl+Y or Ctrl+Shift+Z | ⇧⌘Z |

The shortcuts leave text fields alone, so Ctrl+Z while typing undoes the typing. The clock
button lists every change with its time; pick one to go straight back, or forward, to it.
The history is kept per browser session and survives a server restart. **Import**,
**Import Python** and **Export** are under **More**.

```{image} ../_static/design.png
:alt: IvoryOS workflow designer
```

## Library

Use **Library** to reopen saved workflows and templates. Integrators can also configure startup template imports so commonly used workflows are available when the app starts.

```{image} ../_static/library.png
:alt: IvoryOS data page
```

## Execute

Use **Execute** to prepare and run a workflow.

IvoryOS chooses the available run configuration based on the workflow shape:

| Workflow shape | Run option |
| --- | --- |
| No configurable parameters | Repeat count |
| Configurable parameters | Parameter table |
| Configurable parameters and numerical outputs | Optimizer configuration |

Queued tasks can be named, paused, resumed, or stopped depending on their current state.

In the parameter table, each row is one run of the workflow. A row left entirely empty is
skipped, so you never have to delete spare rows.

An input is optional when its argument is typed `Optional[...]` or `X | None`. When a
table has both kinds, the required columns are marked with a red asterisk. In a filled row:

- An empty optional cell runs as `None`.
- To give `None` on purpose, type `None` in a text cell, or pick **None** at the end of an
  optional dropdown. It shows in italics. It also counts as filling the row, so a table
  whose only input is optional runs one row for each `None` you enter.
- An empty required cell is marked, and the table does not run until it is filled. A
  required dropdown offers only its choices; a required text cell still accepts `None`.

```{image} ../_static/execute.png
:alt: IvoryOS Execute page
```

See [Run behavior](run-behavior.md) for prep, script, cleanup, pause, stop, and queue behavior.

## Data

Use **Data** to inspect completed workflow records, step records, run outputs, logs, and generated result files.

Each run records who submitted it. The run list has a **Submitted By** column you can sort
by, and the search box finds runs by name or by user. A run's page shows who submitted it
under its title. The queue on the Execute page also shows who submitted each waiting task.
Runs from before this was recorded show `-`.

IvoryOS stores run data under `ivoryos_data/` in the working directory. The most commonly inspected folders are:

- `results/`: workflow result CSV files.
- `scripts/`: generated workflow scripts and JSON workflow definitions.
- `config_csv/`: saved run configuration CSV files.
- `llm_output/`: design-agent prompts and raw responses.

```{image} ../_static/data.png
:alt: IvoryOS Data page
```
