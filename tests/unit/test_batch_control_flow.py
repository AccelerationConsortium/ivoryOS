"""Control flow in batch mode must behave like the same steps outside a block.

A repeat is its body written out N times, so shared (batch) steps run once per
iteration and per-sample steps once per sample, with the whole batch moving
through the iterations together (issue #192).
"""
import asyncio
from unittest.mock import MagicMock

from ivoryos.parsers.returns import store_return_value
from ivoryos.runtime.control_flow import validate_and_nest_control_flow
from ivoryos.runtime.script_runner import ScriptRunner
from ivoryos.script import Script, ScriptRenderer


class RecordingRunner(ScriptRunner):
    """Records each action call instead of touching the deck or the database."""

    def __init__(self, results=None):
        super().__init__()
        self.logger = MagicMock()
        self.calls = []
        self.results = iter(results or [])

    async def _execute_action(self, step, context, arg_contexts=None, phase_id=1, step_index=1,
                              section_name=None, override_args=None):
        who = "shared" if step.get("batch_action") else context["sample"]
        self.calls.append((step["action"], who))
        store_return_value(context, arg_contexts, step.get("return", ""), next(self.results, None))
        return context


def step(id, instrument, action, args=None, uuid=None, **extra):
    return {"id": id, "uuid": uuid or id, "instrument": instrument, "action": action,
            "args": args or {}, "return": "", "arg_types": {}, **extra}


def run(runner, flat_steps, contexts):
    nested = validate_and_nest_control_flow(flat_steps)
    asyncio.run(runner._execute_steps_batched(nested, contexts, phase_id=1, section_name="script"))


def test_repeat_runs_shared_steps_once_per_iteration_and_samples_in_lockstep():
    runner = RecordingRunner()
    run(runner, [
        step(1, "repeat", "repeat", {"statement": 3}, uuid="r"),
        step(2, "deck.sdl", "equilibrate", {"temp": 3.0}, batch_action=True),
        step(3, "wait", "wait", {"statement": 1.0}, batch_action=True),
        step(4, "deck.sdl", "dose_solid", {"amount_in_mg": "#amount"}),
        step(5, "repeat", "endrepeat", uuid="r"),
    ], [{"sample": "A", "amount": 1}, {"sample": "B", "amount": 2}])

    iteration = [("equilibrate", "shared"), ("wait", "shared"), ("dose_solid", "A"), ("dose_solid", "B")]
    assert runner.calls == iteration * 3


def test_repeat_count_from_variable_drops_samples_whose_count_is_reached():
    runner = RecordingRunner()
    run(runner, [
        step(1, "repeat", "repeat", {"statement": "#times"}, uuid="r"),
        step(2, "deck.sdl", "stir", batch_action=True),
        step(3, "deck.sdl", "dose", {"amount": 1}),
        step(4, "repeat", "endrepeat", uuid="r"),
    ], [{"sample": "A", "times": 2}, {"sample": "B", "times": 1}])

    assert runner.calls == [
        ("stir", "shared"), ("dose", "A"), ("dose", "B"),
        ("stir", "shared"), ("dose", "A"),
    ]


def test_shared_return_in_repeat_reaches_every_sample_with_latest_value_and_warns():
    runner = RecordingRunner(results=[20.0, 25.0])
    contexts = [{"sample": "A"}, {"sample": "B"}]
    run(runner, [
        step(1, "repeat", "repeat", {"statement": 2}, uuid="r"),
        step(2, "deck.sdl", "read_temp", batch_action=True, **{"return": "temp"}),
        step(3, "repeat", "endrepeat", uuid="r"),
    ], contexts)

    assert [context["temp"] for context in contexts] == [25.0, 25.0]
    runner.logger.warning.assert_called_once()
    assert "temp" in runner.logger.warning.call_args.args[0]


def test_repeat_without_return_values_does_not_warn():
    runner = RecordingRunner()
    run(runner, [
        step(1, "repeat", "repeat", {"statement": 2}, uuid="r"),
        step(2, "deck.sdl", "stir", batch_action=True),
        step(3, "repeat", "endrepeat", uuid="r"),
    ], [{"sample": "A"}, {"sample": "B"}])

    runner.logger.warning.assert_not_called()


def test_if_runs_each_branch_once_for_the_samples_that_took_it():
    runner = RecordingRunner()
    run(runner, [
        step(1, "if", "if", {"statement": "#amount > 1"}, uuid="i"),
        step(2, "deck.sdl", "heat", batch_action=True),
        step(3, "deck.sdl", "dose", {"amount": "#amount"}),
        step(4, "if", "else", uuid="i"),
        step(5, "deck.sdl", "skip"),
        step(6, "if", "endif", uuid="i"),
    ], [{"sample": "A", "amount": 2}, {"sample": "B", "amount": 1}, {"sample": "C", "amount": 3}])

    assert runner.calls == [("heat", "shared"), ("dose", "A"), ("dose", "C"), ("skip", "B")]


def test_compile_batch_mode_loops_over_param_list_without_variables():
    script = Script(name="untitled", author="tester")
    script.script_dict["script"] = [
        step(1, "repeat", "repeat", {"statement": 3}, uuid="r"),
        step(2, "deck.sdl", "equilibrate", {"temp": 3.0}, batch_action=True),
        step(3, "deck.sdl", "dose_solid", {"amount_in_mg": "#sample_index"}, arg_types={"amount_in_mg": "float"}),
        step(4, "repeat", "endrepeat", uuid="r"),
    ]

    compiled = ScriptRenderer(script).compile(batch=True)["script"]

    assert "range(n)" not in compiled
    assert "for param in param_list:" in compiled
    assert "sample_index = param['sample_index']" in compiled
