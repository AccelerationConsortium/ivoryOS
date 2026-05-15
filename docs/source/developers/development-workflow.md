# Development workflow

Use this page as a lightweight checklist for code changes.

## Before changing code

1. Identify the owner package.
2. Check existing tests for the behavior.
3. Decide whether docs or changelog entries are needed.
4. Keep generated files out of the patch unless the source file is meant to be generated.

## Where changes usually belong

| Change type | Start here |
| --- | --- |
| App setup, Flask app, database initialization | `ivoryos/app.py`, `ivoryos/config.py`, `ivoryos/server.py` |
| Runtime state | `ivoryos/runtime/state.py` |
| Direct-control routes | `ivoryos/routes/control/` |
| Workflow design routes | `ivoryos/routes/design/` |
| Execution routes and queue entry points | `ivoryos/routes/execute/` |
| Workflow execution | `ivoryos/runtime/` |
| Workflow models and generated script behavior | `ivoryos/script/` |
| Type conversion and interface schema parsing | `ivoryos/parsers/` |
| Dynamic form behavior | `ivoryos/forms/dynamic_forms.py` |
| Database models | `ivoryos/models/` |
| Optional services | `ivoryos/services/` |
| Optimizer adapters | `ivoryos/optimizer/` |

If a change crosses several rows, document the boundary in the merge request or add a short developer page.

## Changelog and docs

Update `CHANGELOG.md` when a change affects users, integrators, public behavior, dependency requirements, or release-visible bugs.

Update docs when a change affects:

- UI workflows;
- `ivoryos.run(...)` options;
- input type behavior;
- generated proxy behavior;
- route behavior;
- optimizer configuration;
- runtime behavior such as queue, pause, stop, retry, or cleanup.

Use [Docs organization](docs-organization.md) to decide where a page belongs.

## Pull request checklist

- The behavior is covered by a focused unit or integration test where practical.
- Existing tests pass, or any failure is explained.
- The docs build passes when docs changed.
- User-facing behavior is mentioned in `CHANGELOG.md`.
- Generated build output is not committed.
- Runtime data under `ivoryos_data/` is not committed.
- New public behavior has an obvious place in the user, integrator, or developer docs.

## Generated docs pages

The suite README pages under `docs/source/integrators/` are generated during the Sphinx build from upstream repositories:

- `client-api.md`
- `mcp-server.md`
- `plugins.md`

Do not edit those generated files directly. Change their source repositories or update `external_readmes` in `docs/source/conf.py`.
