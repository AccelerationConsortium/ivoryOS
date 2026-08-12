---
name: optimizer_pattern
description: How to add or debug a Bayesian/custom optimizer adapter in IvoryOS
---

# IvoryOS Optimizer Pattern

Read this skill whenever you are adding a new optimizer backend, debugging optimization
campaign behaviour, or modifying how IvoryOS runs Bayesian Optimization (BO) experiments.

---

## 1. Architecture Overview

```
ivoryos/optimizer/
  base_optimizer.py    ← OptimizerBase ABC — all adapters inherit this
  ax_optimizer.py      ← Ax (Meta) adapter
  baybe_optimizer.py   ← BayBE adapter
  nimo_optimizer.py    ← NIMO adapter
  registry.py          ← OPTIMIZER_REGISTRY dict (name → class)
```

The optimizer is selected at run-time and instantiated inside `_run_with_stop_check()` in
`ivoryos/runtime/script_runner_workflow.py`.

---

## 2. The OptimizerBase Interface

Every adapter must implement these four abstract methods:

```python
from ivoryos.optimizer.base_optimizer import OptimizerBase

class MyOptimizer(OptimizerBase):
    def suggest(self, n=1) -> list[dict]:
        """Return n parameter dicts, e.g. [{"param_1": 1.5, "param_2": "a"}]"""
        ...

    def observe(self, results: list[dict]):
        """Feed the list of output dicts back to the optimizer."""
        ...

    def append_existing_data(self, existing_data, file_path: str = None):
        """Pre-load historical data (from CSV) before the first suggest()."""
        ...

    def get_plots(self, plot_type) -> dict:
        """Return plot data for the UI (Plotly-compatible dict or None)."""
        ...
```

The constructor signature is fixed by `OptimizerBase.__init__`:

```python
def __init__(self, experiment_name, parameter_space, objective_config,
             optimizer_config, parameter_constraints=None,
             datapath=None, additional_params=None):
```

---

## 3. Parameter Space Format

`parameter_space` is a list of parameter dicts:

```python
parameter_space = [
    {"name": "temp",    "type": "range",  "bounds": [20.0, 80.0],     "value_type": "float"},
    {"name": "stirrer", "type": "range",  "bounds": [100, 1000],      "value_type": "int"},
    {"name": "solvent", "type": "choice", "bounds": ["EtOH", "MeOH"], "value_type": "str"},
]
```

Types: `"range"` (continuous/integer), `"choice"` (categorical).
`value_type`: `"float"`, `"int"`, `"str"`.

Discrete range steps: use the inherited helper:

```python
values = OptimizerBase._create_discrete_search_space(
    range_with_step=[0.0, 1.0, 0.1], value_type="float"
)
# → [0.0, 0.1, 0.2, ..., 1.0]
```

---

## 4. Objective Config Format

```python
objective_config = [
    {"name": "yield",    "minimize": False, "weight": 1, "early_stop": 0.95},
    {"name": "purity",   "minimize": False, "weight": 1},
]
```

`early_stop` is checked after each iteration in `_run_repeat_section` via
`_check_early_stop(output, objectives)`. If all objectives with a threshold are met for any
row in `output`, the loop terminates early.

---

## 5. Optimizer Config (Step Strategy)

The `optimizer_config` (also called `steps` in the UI) defines the multi-phase strategy:

```python
optimizer_config = {
    "step_1": {"model": "Random", "num_samples": 5},
    "step_2": {"model": "BOTorch"},
}
```

The meaning of each key is adapter-specific — it's passed directly to the adapter's
`__init__`. Use `get_schema()` to expose what your adapter expects:

```python
@staticmethod
def get_schema():
    return {
        "parameter_types": ["range", "choice"],
        "multiple_objectives": True,
        "optimizer_config": {
            "step_1": {"model": ["Random", "GPEI"], "num_samples": 10},
            "step_2": {"model": ["BOTorch"]},
        },
        "additional_field": {}   # extra fields shown in the UI
    }
```

---

## 6. Registering a New Optimizer

**Option A — built-in (add to `registry.py`):**

```python
# ivoryos/optimizer/registry.py
from ivoryos.optimizer.my_optimizer import MyOptimizer

OPTIMIZER_REGISTRY = {
    "Ax": AxOptimizer,
    "BayBE": BayBEOptimizer,
    "NIMO": NIMOOptimizer,
    "My": MyOptimizer,   # ← add here
}
```

**Option B — external (pass at runtime, preferred for user extensions):**

```python
from my_package.my_optimizer import MyOptimizer
import ivoryos

ivoryos.run(
    module=__name__,
    optimizer_registry={"My": MyOptimizer},
)
```

`optimizer_registry` is merged into `global_state.optimizers` in `server.py`.

---

## 7. How the Runner Calls the Optimizer

Inside `_run_repeat_section` in `script_runner_workflow.py`:

```python
# 1. Instantiate
optimizer = optimizer_cls(
    experiment_name=run_name,
    parameter_space=parameters,
    objective_config=objectives,
    parameter_constraints=constraints,
    additional_params=additional_params,
    optimizer_config=steps,
    datapath=output_path,
)

# 2. Pre-load history (if provided)
optimizer.append_existing_data(previous_runs, file_path)

# 3. Suggest → execute → observe loop
for i in range(repeat_count):
    parameters = optimizer.suggest(n=batch_size)   # list of dicts
    output = await self.exec_steps(script, "script", phase_id,
                                   kwargs_list=parameters)
    if output:
        optimizer.observe(output)                   # list of dicts

    # Early stop check
    if self._check_early_stop(output, objectives):
        break
```

`suggest()` must return a list of dicts even when `n=1` (e.g. `[{"param": 1.5}]`).
`observe()` receives the same list of dicts that `exec_steps()` returns (context dicts
with both input parameters and measured output values).

---

## 8. Optional Dependencies

Optimizer dependencies are always **optional extras** — never add them to `requirements.txt`.
Instead, add them to `pyproject.toml` under the correct extra group:

```toml
# pyproject.toml
[project.optional-dependencies]
optimizer-my = ["my-optimizer-package>=1.0"]
optimizers   = [
    "ivoryos[optimizer-ax]",
    "ivoryos[optimizer-baybe]",
    "ivoryos[optimizer-nimo]",
    "ivoryos[optimizer-my]",   # ← add here
]
```

Guard the import in your adapter file:

```python
try:
    from my_optimizer_lib import MyBO
except ImportError as e:
    raise ImportError(
        "MyOptimizer requires 'my-optimizer-package'. "
        "Install with: pip install 'ivoryos[optimizer-my]'"
    ) from e
```

---

## 9. Debugging Checklist

- [ ] `suggest()` returns `None` or `[]`? → Optimizer cannot propose parameters; check constraints vs. bounds.
- [ ] `observe()` receives wrong keys? → The context dict includes *all* script variables, not just objectives; filter by `objective_config` names.
- [ ] History CSV columns mismatch? → `append_existing_data` validates columns against `list(arg_types.keys()) + list(return_list)` — ensure the CSV was generated with the same script.
- [ ] Optimizer not appearing in UI? → Check it is in `global_state.optimizers` (set from `OPTIMIZER_REGISTRY` or passed via `optimizer_registry` kwarg).
- [ ] `get_plots()` returns nothing? → The UI skips the plot tab when `get_plots()` returns `None` — this is expected if the adapter doesn't support plots yet.
