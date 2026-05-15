# IvoryOS major refactoring summary

This document summarizes the major architectural changes and refactorings implemented.

## Dissolving the monolithic `utils/` directory

The `ivoryos/utils/` directory has been broken apart into logical, domain-specific packages to enforce a cleaner separation of concerns:

- `ivoryos/core/`: system-level abstractions such as `module_loader.py` and `return_handlers.py`.
- `ivoryos/forms/`: UI form generation and WTForms logic such as `dynamic_forms.py`.
- `ivoryos/models/`: database models such as `base.py`, `execution.py`, `script.py`, `user.py`, and `workflow.py`.
- `ivoryos/parsers/`: data serialization, JSON parsing, and type conversions.
- `ivoryos/runtime/`: execution orchestration, control flows, and queue management such as `script_runner.py` and `task_runner.py`.
- `ivoryos/services/`: standalone backend services such as `llm_agent.py`, `draft_service.py`, and `client_proxy.py`.

## Real-time Socket.IO synchronization

Legacy HTTP polling through `GET /status` and `GET /queue` has been replaced with an event-driven Socket.IO architecture.

- Real-time events such as `busy_status`, `queue_status`, and `pause_status` are managed centrally in `ivoryos/socket_handlers.py`.
- Frontend synchronization is handled through `window.platformState` in `socket_handler.js`, reducing server overhead and UI latency.

## Codebase cleanup

- Community examples were removed from the core package area because they were primarily publication-oriented and not intended for core reproducibility.
- Integration and unit tests in `tests/` were updated to reflect the package-based import structure.
