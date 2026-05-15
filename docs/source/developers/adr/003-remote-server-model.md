# ADR 003: Remote Server Model

## Status

Accepted.

## Context

Self-driving laboratory platforms often need to share instruments, APIs, or licensed drivers across machines. A platform may need to call an instrument it does not physically host, or two workflows may need serialized access to the same instrument.

The integration should preserve normal Python ergonomics for workflow authors while keeping real hardware ownership in one process.

## Decision

IvoryOS can act as an instrument server. The server process owns the real Python driver object and exposes direct-control routes under:

```text
/ivoryos/instruments/<instrument>
```

For deck instruments, the instrument name is usually `deck.<object_name>`, such as:

```text
/ivoryos/instruments/deck.balance
```

IvoryOS can generate a Python proxy file from the server's interface schema:

```text
/ivoryos/instruments/files/proxy
```

Remote platforms import the generated proxy and call methods such as `balance.read_mass_mg()` or `balance.dose_solid(...)`. The generated proxy sends authenticated HTTP POST requests to the instrument server.

## Consequences

- The instrument server is the source of truth for the real driver object.
- Remote workflows can use normal-looking Python method calls without importing the real hardware SDK.
- Direct-control calls are logged as single-step execution records.
- The shared runner lock serializes normal direct-control calls and helps prevent concurrent access to the same hardware.
- The proxy should be regenerated when exposed method signatures change.
- Authentication, network access, and deployment boundaries become part of the instrument integration design.

See [Remote instrument proxy](../../integrators/remote-instrument-proxy.md) for the integrator-facing guide.
