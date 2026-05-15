# ADR 001: Runtime Design

## Status

Accepted.

## Context

IvoryOS needs to expose Python objects, workflow scripts, direct-control calls, queue state, pause/resume controls, and generated UI forms through one running Flask application.

The runtime must support:

- one active deck per running process;
- direct-control calls from the UI, API clients, and generated proxies;
- workflow execution with preparation, main script, and cleanup phases;
- cooperative pause, retry, stop-pending, and stop-current controls;
- serialized access to instruments that are not safe for concurrent calls.

## Decision

IvoryOS keeps runtime state in a process-wide `GlobalState` singleton. The active deck, interface schema, building blocks, optimizer registry, runner status, notification handlers, and shared runner lock live there.

Direct-control calls and workflow runners use that shared state instead of copying the deck into local module-level caches. The active deck is configured when `ivoryos.run(__name__)` starts the server.

Workflow control is cooperative. IvoryOS does not kill a running Python method or hardware driver call mid-call. Stop and pause controls take effect at action boundaries or explicit safe wait points.

## Consequences

- A running IvoryOS process has one active deck.
- Instrument calls can be serialized through the shared runner lock.
- Routes, parsers, and runners can resolve the active deck consistently.
- Long-running or blocking driver calls must return before pause or stop controls can fully take effect.
- Integrations that need multiple physical servers should run multiple IvoryOS processes and connect them through client/proxy APIs.
