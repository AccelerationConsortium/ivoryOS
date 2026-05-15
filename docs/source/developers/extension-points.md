# Extension points

This page lists the main places where contributors can extend IvoryOS behavior.

## Optimizers

Optimizer adapters live under `ivoryos/optimizer/`.

To add an optimizer:

1. Implement an adapter that follows `OptimizerBase`.
2. Implement `suggest(...)`, `observe(...)`, `append_existing_data(...)`, `get_plots(...)`, and `get_schema()`.
3. Register the adapter in `ivoryos/optimizer/registry.py`.
4. Add tests for schema availability and execution behavior.
5. Update integrator docs if users need new configuration fields.

The registry only includes adapters whose optional dependencies can be imported. Keep optional optimizer dependencies out of the core dependency list.

## Type conversion and form fields

Use these files when changing how Python signatures become UI controls:

- `ivoryos/parsers/introspection.py`: reads signatures, annotations, and return metadata.
- `ivoryos/forms/dynamic_forms.py`: creates form fields.
- `ivoryos/parsers/type_conversions.py`: converts submitted values before calling Python methods.
- `ivoryos/parsers/returns.py`: extracts and stores scalar or tuple return save names.

Add tests before changing shared conversion behavior. Small changes here can affect direct control, workflow design, generated scripts, remote proxies, and optimizer setup.

## Workflow runtime

Runtime behavior lives under `ivoryos/runtime/`.

Use this area for:

- queue behavior;
- phase execution;
- pause/resume;
- stop pending and stop current;
- retry behavior;
- cleanup handling;
- step output capture.

Keep operator-facing semantics aligned with [Run behavior](../users/run-behavior.md).

## Routes

Routes are organized by product area:

- `ivoryos/routes/main/`
- `ivoryos/routes/auth/`
- `ivoryos/routes/control/`
- `ivoryos/routes/design/`
- `ivoryos/routes/execute/`
- `ivoryos/routes/library/`
- `ivoryos/routes/data/`

The generated route reference is in [IvoryOS routes docs](../routes.rst). Keep route docs in reStructuredText because `sphinxcontrib.autohttp.flask` renders reliably there.

## Generated proxy

Generated proxy behavior lives in `ivoryos/services/client_proxy.py`.

Update this area when changing:

- direct-control route payloads;
- authentication/session behavior;
- Enum serialization;
- type hints in generated proxy code;
- remote instrument method signatures.

Regenerate and manually smoke-test a proxy when changing this contract.

## Plugins

Plugin support is exposed through `ivoryos.run(..., blueprint_plugins=...)`. The plugin template docs are generated into [Plugin for IvoryOS](../integrators/plugins.md).

Core plugin loading happens in `ivoryos/server.py` through `load_plugins(...)`. Keep plugin route prefixes relative to the IvoryOS URL prefix.

## Design agent

Design-agent code lives in:

- `ivoryos/services/llm_agent.py`
- `ivoryos/routes/design/design_agent.py`

The design agent depends on the active interface schema and method docs. If you change introspection output, check design-agent prompts and generated workflow actions.
