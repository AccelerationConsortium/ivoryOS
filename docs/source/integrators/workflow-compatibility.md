# Keeping saved workflows working

Workflows are saved against the deck as it was at the time. A step stores the
module it calls, the method name, and the arguments it was built with — not a
live reference. Your deck is ordinary Python that you keep editing, so a workflow
saved last month can name something the deck no longer has.

IvoryOS compares every step against the loaded deck and flags the ones that no
longer line up. Operators see those flags in the designer and on the execution
page; see [Workflow step warnings](../users/deck-compatibility.md) for what they
are shown. This page is about which of your edits cause them.

## What a flag means at run time

| Reason | Severity | What happens at run time |
| --- | --- | --- |
| Module is not on the deck | Red | `ValueError: Unknown instrument '<name>'` |
| Method no longer exists on the module | Red | `AttributeError: Method '<name>' no longer exists on '<module>'` |
| Method is passed an argument it no longer accepts | Red | `TypeError: got an unexpected keyword argument` |
| Method requires an argument the step does not set | Red | `TypeError: missing a required argument` |
| Argument type changed | Amber | Nothing at the call itself — see below |
| Sub-workflow is no longer registered | Amber | Nothing — it runs from an embedded copy, see below |

Disabled steps are skipped by the runner, so they are flagged in the designer but
never counted among the steps that will fail.

## When an argument mismatch actually fails

This is the part that is easy to get wrong, because it depends on the method's
signature rather than on the argument alone.

IvoryOS always calls a deck method with keyword arguments — `method(**args)` —
and that single fact decides every case below.

| Situation | Fails? |
| --- | --- |
| Step passes an argument the method does not declare, and the method has **no** `**kwargs` | **Yes** — `TypeError: unexpected keyword argument` |
| Step passes an argument the method does not declare, and the method **has** `**kwargs` | No — it is absorbed |
| Step passes an argument the method does not declare, and the method has `*args` but no `**kwargs` | **Yes** — see below |
| Method has a parameter with no default that the step does not pass | **Yes** — `TypeError: missing a required argument` |
| Method has a parameter **with** a default that the step does not pass | No — the default is used |
| Method gained a keyword-only parameter (after `*`) with no default | **Yes** — `TypeError: missing a required keyword-only argument` |
| Argument value does not match the type annotation | No — see below |

### `*args` does not absorb extra arguments

A common assumption is that either `*args` or `**kwargs` will swallow an argument
the method does not declare. Only `**kwargs` does.

```python
def dispense(self, volume, *rest):
    ...

dispense(volume=1.0, speed=5)
# TypeError: dispense() got an unexpected keyword argument 'speed'
```

Because IvoryOS passes everything by keyword, `*rest` can never receive anything,
so it offers no protection. Add `**kwargs` if you want a method to tolerate
arguments that older saved workflows still pass.

### Type changes do not fail at the call

Python does not enforce type annotations, so changing `volume: float` to
`volume: int` raises nothing when the method is called. This is why a type change
is amber rather than red. It still matters: the stored value may be the wrong
shape for what the method now does with it, so it may fail deeper inside the
method, or quietly produce a wrong result.

The same applies when an `Enum` or `Literal` changes its allowed values. The call
succeeds; whether the stored value is still valid is up to the method.

### A deleted sub-workflow still runs

A step that calls another workflow stores a copy of that workflow's steps inside
itself. The runner executes that copy and never looks the registered workflow up,
so deleting or renaming the original does not break the step.

It is flagged amber because the copy is a snapshot: it no longer tracks the
workflow it came from, and later changes to the original are not in it. The steps
inside the copy are checked against the deck like any other, so if one of them
calls a method the deck has dropped, that shows as a red flag on the parent step.

### Positional-only parameters

A parameter declared before a `/` cannot be passed by keyword:

```python
def dispense(self, volume, /):
    ...
```

Since IvoryOS calls methods with keyword arguments only, such a parameter can
never be supplied and the step fails every time with
`TypeError: got some positional-only arguments passed as keyword arguments`.
This is not compatibility drift — it never worked — so it is not flagged. Avoid
positional-only parameters on deck methods.

## Writing methods that survive an edit

- **Renaming a method or module breaks every saved workflow that uses it.** If a
  rename is worth it, expect to tell operators; the flag suggests the new name
  when it is similar enough, which makes the fix obvious to them.
- **Adding a parameter with a default is safe.** Adding one without a default
  breaks every saved workflow that calls the method.
- **Removing a parameter breaks saved workflows** unless the method also takes
  `**kwargs`.
- **Widening a type is safe; narrowing it is not flagged as fatal but can still
  be wrong.** `float` to `int` will not raise, and the operator keeps whatever
  value was stored.
- **`**kwargs` is the escape hatch** for a method you expect to keep changing.
  IvoryOS stops flagging unrecognised arguments on such methods, which also means
  it will not warn about arguments that silently do nothing.

## What is not checked

The check is deliberately conservative and stays silent rather than guessing:

- If no deck is loaded and no pseudo-deck is selected, nothing is flagged. An
  absent deck means "unknown", not "everything is missing".
- If no building blocks are registered, `blocks.*` steps are not flagged.
- Enum types are compared by class name only. The module path recorded for an
  Enum depends on how the deck was imported, and changes without the signature
  changing.
- Whether a stored value is still *sensible* — only whether the call will be
  accepted.

```{note}
The step edit form is built from what the step saved, not from the deck's current
signature. A parameter the deck has newly added will not appear as a field, and
one the deck has dropped will still be shown. Operators are told to delete and
re-add a flagged step for this reason.
```
