# Quick start

## Install

```console
pip install ivoryos
```

Install optional feature groups only when needed:

```console
pip install "ivoryos[optimizers]"
pip install "ivoryos[db]"
pip install "ivoryos[llm]"
```

## Launch IvoryOS

Create or open the Python script where your devices, modules, or workflow functions are initialized.

```python
my_robot = Robot()

import ivoryos

ivoryos.run(__name__)
```

Run the script, then open `http://localhost:8000` in a browser. The default local login is `admin` / `admin`.

## First workflow check

1. Open the **Devices** tab to confirm your exposed functions appear.
2. Open the **Design** tab to drag functions into a workflow.
3. Use `#parameter_name` inside workflow arguments to make a parameter configurable at run time.
4. Click **Prepare Run** to configure repeats, parameter batches, or optimization.
5. Run the workflow from the execution page and review records in the **Data** tab.

## Output files

IvoryOS creates `ivoryos_data/` in the working directory on first run. It stores local configuration CSVs, workflow records, generated scripts, logs, and the local SQLite database.

See [Using the UI](../users/using-the-ui.md) for the no-code browser workflow. Runtime settings such as logging, notification handlers, and design-agent configuration are covered in the [Runtime API reference](usage.rst).
