# ADR 002: Optimizer Schema

## Status

Accepted.

## Context

IvoryOS supports multiple optimizer backends, including optional packages such as Ax, BayBE, and NIMO. Not every deployment installs every optimizer, and each optimizer has different configuration fields and parameter support.

The workflow execution UI needs a stable way to discover:

- which optimizers are available in the current environment;
- supported parameter types;
- whether multiple objectives are supported;
- optimizer-specific configuration fields;
- additional advanced settings.

## Decision

Optimizer adapters implement a shared `get_schema()` contract. The optimizer registry only includes adapters whose optional package dependencies can be imported.

The execution route exposes optimizer schemas through:

```text
POST /ivoryos/executions/optimizer_schema
```

If no `optimizer_type` is provided, the route returns all available optimizer schemas. If `optimizer_type` is provided, it returns that optimizer's schema.

The UI renders optimizer configuration from the schema instead of hard-coding every optimizer's controls into the page.

## Consequences

- Installing or removing optional optimizer packages changes which optimizers appear.
- New optimizers can be added by implementing the optimizer base behavior and `get_schema()`, then registering the adapter.
- The UI can hide unsupported parameter types or advanced sections based on schema fields.
- Schema changes are user-facing API changes and should be documented in release notes.
