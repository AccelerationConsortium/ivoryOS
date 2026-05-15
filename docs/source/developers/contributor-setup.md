# Contributor setup

This page is for contributors working from a local source checkout.

## Python versions

IvoryOS supports Python `>=3.7`. For new development, use Python `>=3.10` when possible because the optional optimizer packages and modern typing syntax are easier to work with there.

Some lab deployments still need older or 32-bit Python environments for vendor drivers. Keep compatibility in mind when changing dependencies or syntax in package code.

## Create an environment

From the repository root:

```console
python -m venv .venv
```

Activate it, then install IvoryOS in editable mode with development and documentation dependencies:

```console
python -m pip install --upgrade pip
python -m pip install -e ".[dev,doc]"
```

Install optional feature groups only when you need them:

```console
python -m pip install -e ".[optimizers]"
python -m pip install -e ".[db]"
python -m pip install -e ".[llm]"
```

The individual optimizer extras are also available:

```console
python -m pip install -e ".[optimizer-ax]"
python -m pip install -e ".[optimizer-baybe]"
python -m pip install -e ".[optimizer-nimo]"
```

## Run the example platform

The abstract SDL example is useful for manual smoke testing:

```console
python community/examples/abstract_sdl_example/abstract_sdl.py
```

Then open:

```text
http://localhost:8000
```

The default local login is:

```text
admin / admin
```

## Local data

IvoryOS writes local runtime data to `ivoryos_data/` in the current working directory. The most important generated paths are:

- `ivoryos_data/ivoryos.db`: local SQLite database.
- `ivoryos_data/scripts/`: saved workflow JSON and generated workflow Python scripts.
- `ivoryos_data/results/`: workflow result CSV files.
- `ivoryos_data/config_csv/`: run configuration CSV files.
- `ivoryos_data/pseudo_deck/`: generated interface schema files.
- `ivoryos_data/logs/` and `ivoryos_data/default.log`: runtime logs.

These files are runtime output, not source. Do not commit newly generated local run data.

## Useful environment variables

| Variable | Purpose |
| --- | --- |
| `URL_PREFIX` | Changes the app prefix from the default `/ivoryos`. |
| `PORT` | Sets the server port when `ivoryos.run(...)` does not receive `port`. |
| `SECRET_KEY` | Flask secret key. |
| `OPENAI_API_KEY` | Enables design-agent features when an LLM server/model is configured. |
| `IVORYOS_DB_URI` | Database URI, preferred over `DATABASE_URL`. |
| `DATABASE_URL` | Fallback database URI. |

PostgreSQL support requires the `db` extra.
