# Testing and verification

Run the smallest useful check first, then broaden when the change touches shared behavior.

## Unit and integration tests

Run all tests:

```console
pytest
```

Run only unit tests:

```console
pytest tests/unit
```

Run only route and socket integration tests:

```console
pytest tests/integration
```

## Documentation build

Build docs with warnings treated as errors:

```console
python -m sphinx -W -b html docs/source docs/build/html
```

When navigation, file moves, or generated pages changed, force a fresh Sphinx environment:

```console
python -m sphinx -E -a -W -b html docs/source docs/build/html
```

The docs build also downloads suite README pages and generates the recent changelog fragment.

## Manual smoke test

Use the abstract SDL example for a local browser smoke test:

```console
python community/examples/abstract_sdl_example/abstract_sdl.py
```

Open `http://localhost:8000` and log in with `admin / admin`.

Check the flows affected by your change. Common smoke checks:

- Devices page loads exposed objects and methods.
- Enum inputs render as dropdown choices.
- Tuple return annotations render separate save fields.
- A simple workflow can be saved, prepared, run, and reviewed in Data.
- Pause, resume, stop pending, and stop current behave as expected.
- Generated proxy download still imports and calls direct-control routes when proxy behavior changed.

## Test ownership hints

| Area | Tests to inspect first |
| --- | --- |
| Forms, Enum controls, tuple return fields | `tests/unit/test_dynamic_forms_behavior.py` |
| Parser helpers and type conversion | `tests/unit/test_parser_helpers.py`, `tests/unit/test_type_conversion.py` |
| Script rendering and editor behavior | `tests/unit/test_renderer_behavior.py`, `tests/unit/test_script_editor_behavior.py` |
| Runtime helpers and queue behavior | `tests/unit/test_script_runner_runtime_helpers.py`, `tests/unit/test_runtime_and_service_helpers.py` |
| Routes | `tests/integration/test_route_*.py` |
| Socket behavior | `tests/integration/test_sockets.py` |

## When to add tests

Add or update tests when a change affects shared parsing, conversion, route contracts, execution behavior, database records, generated proxy behavior, or optimizer configuration. For narrow docs-only changes, the Sphinx build is usually enough.
