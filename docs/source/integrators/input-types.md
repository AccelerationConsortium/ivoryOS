# Input types and UI controls

IvoryOS builds UI controls from Python method signatures. Good type hints make direct control, workflow design, CSV configuration, generated proxy clients, and optimizer setup more predictable.

## Basic pattern

Expose a normal Python object or function, then launch IvoryOS from the script where it is initialized.

```python
class Pump:
    def dispense(self, volume_ml: float, rate_ml_min: float = 1.0) -> float:
        return self.driver.dispense(volume_ml=volume_ml, rate_ml_min=rate_ml_min)


pump = Pump()

import ivoryos

ivoryos.run(__name__)
```

IvoryOS sees `pump.dispense(...)`, builds form fields for `volume_ml` and `rate_ml_min`, and converts submitted UI values using the annotations.

## Primitive types

| Annotation | UI input | Converted value |
| --- | --- | --- |
| `int` | `42` | `42` |
| `float` | `3.14` | `3.14` |
| `str` | `hello` | `"hello"` |
| `bool` | `True` / `False` | `True` / `False` |

Use primitive annotations for most scalar hardware settings such as volumes, temperatures, durations, speeds, and names.

## Container types

| Annotation | UI input | Converted value |
| --- | --- | --- |
| `list` | `[1, 2, 3]` | `[1, 2, 3]` |
| `tuple` | `(1, "a")` | `(1, "a")` |
| `set` | `{1, 2, 3}` | `{1, 2, 3}` |

Container inputs use Python literal syntax. Keep them for compact configuration values; if users need to edit many rows, prefer a CSV parameter table.

## Optional and Union types

```python
from typing import Optional, Union


def heat(target_c: Optional[float] = None):
    ...


def set_position(position: Union[int, str]):
    ...
```

`Optional[...]` allows blank or `None` values. `Union[...]` lets IvoryOS try more than one supported conversion.

## Enum dropdowns

Use Python `Enum` classes when a parameter should be selected from a fixed list. IvoryOS turns Enum annotations into dropdown-style choices in the UI.

```python
from enum import Enum
from typing import Optional


class Solvent(Enum):
    Methanol = "Methanol"
    Ethanol = "Ethanol"
    Acetone = "Acetone"


class AbstractSDL:
    def dose_solvent(
        self,
        solvent_name: Optional[Solvent] = None,
        amount_in_ml: float = 5,
        rate_ml_per_minute: float = 1,
    ):
        if solvent_name is None:
            solvent_name = Solvent.Methanol
        else:
            solvent_name = Solvent(solvent_name)

        self.pump.dose_liquid(
            amount_in_ml=amount_in_ml,
            rate_ml_per_minute=rate_ml_per_minute,
        )
```

This pattern is used in `community/examples/abstract_sdl_example/abstract_sdl.py`.

The UI shows the Enum member names as choices. The submitted value is commonly the Enum value, so convert it back inside the method with `Solvent(solvent_name)` if the rest of your code expects an Enum instance.

For a required dropdown, remove `Optional` and the `None` default:

```python
def dose_solvent(solvent_name: Solvent, amount_in_ml: float = 5):
    solvent_name = Solvent(solvent_name)
    ...
```

## Configurable workflow parameters

In the workflow designer, prefix an argument with `#` to make it configurable at run time.

```text
#wash_solvent
#target_temperature
#residence_time
```

Configurable parameters appear during run preparation. If the original method annotation is an Enum, the configurable parameter keeps the same set of allowed choices.

## Return values

Return type hints help workflow outputs and optimization setup.

```python
def measure_absorbance(wavelength_nm: float) -> float:
    return spectrometer.measure(wavelength_nm)
```

Numerical outputs can be used for optimizer-based runs.

## Tuple outputs

Use a fixed-length tuple return annotation when one method returns multiple values that users may want to save separately.

```python
def measure_sample(sample_id: str) -> tuple[float, float]:
    absorbance = spectrometer.measure_absorbance(sample_id)
    retention_time = hplc.measure_retention_time(sample_id)
    return absorbance, retention_time
```

In the workflow designer, IvoryOS shows one save field per tuple item, such as **Save item 1 as** and **Save item 2 as**. The saved names can then be used by later workflow steps.

For older Python typing style, `Tuple[float, float]` is also supported:

```python
from typing import Tuple


def measure_sample(sample_id: str) -> Tuple[float, float]:
    ...
```

Use scalar return annotations for single values, fixed-length tuple annotations for multiple named outputs, and `dict` returns when the result is best handled as a structured object.

## Practical rules

- Add type hints to every public method you want users to call from IvoryOS.
- Use `Enum` for settings with a fixed set of valid choices, and convert the submitted value back to the Enum inside the method when needed.
- Use fixed-length tuple return annotations when users should save multiple outputs from one workflow action.
- Use defaults for common values so the generated UI opens in a useful state.
- Keep hardware-only driver objects inside your wrapper class; expose small, stable methods to IvoryOS.
- Regenerate remote proxy clients after changing method names, argument names, annotations, or return types.
