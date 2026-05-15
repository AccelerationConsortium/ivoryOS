# Data model

This page summarizes the main runtime data structures contributors usually touch.

## Runtime directories

IvoryOS creates `ivoryos_data/` in the current working directory.

```text
ivoryos_data/
|-- config_csv/
|-- llm_output/
|-- logs/
|-- pseudo_deck/
|-- results/
|-- scripts/
|   `-- drafts/
|-- default.log
`-- ivoryos.db
```

These directories are runtime output. Do not commit newly generated local run data.

## Database location

By default, IvoryOS uses SQLite:

```text
ivoryos_data/ivoryos.db
```

Set `IVORYOS_DB_URI` or `DATABASE_URL` to use another database. PostgreSQL support requires the `db` extra.

## Workflow definition model

Saved workflow definitions use the `Script` model in `ivoryos/script/models.py`.

Important fields:

| Field | Meaning |
| --- | --- |
| `name` | Workflow name and primary key. |
| `deck` | Platform/deck name associated with the workflow. |
| `script_dict` | Workflow actions grouped into `prep`, `script`, and `cleanup`. |
| `id_order` | UI ordering metadata for workflow actions. |
| `status` | Editing/finalized state. |
| `registered` | Whether a workflow should appear as a registered workflow action. |
| `return_values` | Declared output names. |
| `uuid` | Stable identifier for saved scripts. |

## Execution records

Workflow run records live in `ivoryos/models/workflow.py`.

```text
WorkflowRun
    |
    +-- WorkflowPhase
            |
            +-- WorkflowStep
```

`WorkflowRun` represents one submitted run. It stores the run name, platform, timing, data path, repeat mode, and related phases.

`WorkflowPhase` represents one phase execution, such as `prep`, a repeated `script` iteration, or `cleanup`. It stores iteration parameters, outputs, timing, and related steps.

`WorkflowStep` represents one action call inside a phase. It stores method name, timing, error state, and output.

## Direct-control records

Direct-control calls use `SingleStep` in `ivoryos/models/execution.py`.

`SingleStep` stores:

- method name;
- submitted kwargs;
- start and end time;
- error text;
- output.

Generated proxy calls use the same direct-control route behavior and are recorded as single-step calls.

## Interface schemas

When IvoryOS starts with `ivoryos.run(__name__)`, it inspects the active module and writes a pseudo-deck schema under:

```text
ivoryos_data/pseudo_deck/
```

The schema records exposed functions, methods, parameter types, docstrings, and generated UI metadata used by the browser session and workflow designer.

## Result files

Workflow outputs are written under:

```text
ivoryos_data/results/
```

Generated workflow scripts and workflow JSON files are written under:

```text
ivoryos_data/scripts/
```

Run configuration CSV files are written under:

```text
ivoryos_data/config_csv/
```
