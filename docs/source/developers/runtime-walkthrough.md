# Runtime walkthrough

This page follows the main path from a platform script to a completed workflow run.

## Startup path

```text
User platform script
        |
        v
ivoryos.run(__name__)
        |
        v
create_app(...)
        |
        v
register Flask routes, SocketIO, database, auth
        |
        v
inspect active Python module
        |
        v
store deck and interface schema in global_state
        |
        v
start SocketIO Flask server
```

`ivoryos.run(...)` lives in `ivoryos/server.py`. It creates the Flask app, imports workflow templates, loads plugins, registers loggers and notification handlers, configures optimizers, and starts the server.

When `module` is provided, IvoryOS starts from the active Python module:

- `global_state.deck` stores the active Python module.
- `generate_interface_schema(...)` inspects the deck and writes a pseudo-deck schema.
- `generate_block_schema(...)` registers built-in flow-control blocks.
- `create_module_interface_schema(...)` builds the API variable view.

## Interface generation

```text
Python function or method
        |
        v
inspect.Signature
        |
        v
argument types, defaults, docstring, return annotation
        |
        v
dynamic WTForms fields
        |
        v
direct-control form and workflow action form
```

Key files:

- `ivoryos/parsers/introspection.py`
- `ivoryos/forms/dynamic_forms.py`
- `ivoryos/parsers/type_conversions.py`
- `ivoryos/parsers/returns.py`

Return annotations matter. Scalar returns show one save field. Fixed-length tuple returns show one save field per tuple item.

## Workflow design path

```text
Design UI
   |
   v
design routes
   |
   v
Script model + ScriptEditor
   |
   v
workflow JSON in database
   |
   v
generated workflow Python script
```

Key files:

- `ivoryos/routes/design/`
- `ivoryos/script/models.py`
- `ivoryos/script/editor.py`
- `ivoryos/script/renderer.py`

Workflows are stored as structured data with three phases: `prep`, `script`, and `cleanup`.

## Execution path

```text
Execute UI
   |
   v
execute routes
   |
   v
ScriptRunner queue
   |
   v
prep phase
   |
   v
script phase repeated by run mode
   |
   v
cleanup phase
   |
   v
WorkflowRun, WorkflowPhase, WorkflowStep records
```

Key files:

- `ivoryos/routes/execute/`
- `ivoryos/runtime/script_runner.py`
- `ivoryos/runtime/script_runner_queue.py`
- `ivoryos/runtime/script_runner_workflow.py`
- `ivoryos/runtime/script_runner_steps.py`
- `ivoryos/parsers/returns.py`

Only one workflow task runs at a time through the shared runner lock. Queue behavior, pause/resume, stop pending, stop current, and cleanup behavior are user-facing runtime behavior; see [Run behavior](../users/run-behavior.md).

## Direct-control path

```text
Devices UI or generated proxy
        |
        v
POST /ivoryos/instruments/<instrument>
        |
        v
control route resolves object and method
        |
        v
argument conversion
        |
        v
method call on live deck object
        |
        v
SingleStep record and JSON response
```

Key files:

- `ivoryos/routes/control/`
- `ivoryos/services/client_proxy.py`
- `ivoryos/models/execution.py`

Direct-control calls are logged as `SingleStep` records. Remote proxy clients use the same route contract.
