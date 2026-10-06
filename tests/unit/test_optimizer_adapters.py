"""The optimizer adapters, as the runner drives them (script_runner_workflow._run_repeat_section):
suggest(n) returns a list of n parameter dicts; observe() gets one dict per trial, the trial's
parameters with its outputs, a failed trial carrying no objective value.

The adapters are shared with ivoryos-nextgen (edge_server/ivoryos_edge/optimizer/) and kept the
same by hand; these pin the behaviour both repos rely on. Ax and BayBE are optional extras, so
each test skips when its backend is not installed.
"""
import logging

import pytest

SPACE = [
    {"name": "x", "type": "range", "bounds": [0.0, 1.0], "value_type": "float"},
    {"name": "n", "type": "range", "bounds": [0, 5], "value_type": "int"},
]
OBJECTIVE = [{"name": "y", "minimize": False}]


def _measure(trial):
    return 1 - (trial["x"] - 0.6) ** 2 - 0.05 * (trial["n"] - 3) ** 2


def _baybe(step_1):
    from ivoryos.optimizer.baybe_optimizer import BaybeOptimizer

    return BaybeOptimizer(
        experiment_name="adapters",
        parameter_space=[{"name": "x", "type": "range", "bounds": [1, 4], "value_type": "int"}],
        objective_config=OBJECTIVE,
        optimizer_config={"step_1": step_1, "step_2": {"model": "BOTorch"}},
    )


def test_baybe_random_start_lasts_num_samples_measurements():
    """BayBE's own default switches to the model after one measurement, whatever was configured."""
    pytest.importorskip("baybe")
    from baybe.recommenders import BotorchRecommender, RandomRecommender

    opt = _baybe({"model": "Random", "num_samples": 3})
    recommender = opt.experiment.recommender
    assert recommender.switch_after == 3

    def chosen():
        return recommender.select_recommender(measurements=opt.experiment.measurements)

    for _ in range(3):
        assert isinstance(chosen(), RandomRecommender)
        (trial,) = opt.suggest(1)
        opt.observe([{**trial, "y": float(trial["x"])}])
    assert isinstance(chosen(), BotorchRecommender)


@pytest.mark.parametrize("step_1, switch_after", [
    ({"model": "Random", "num_samples": 0}, 1),    # an emptied field
    ({"model": "Random"}, 1),                      # not named: BayBE's own default
    ({"model": "Random", "num_samples": "6"}, 6),  # BayBE refuses anything but a real int
])
def test_baybe_initial_samples_are_a_whole_number_of_at_least_one(step_1, switch_after):
    pytest.importorskip("baybe")
    assert _baybe(step_1).experiment.recommender.switch_after == switch_after


def test_baybe_records_the_round_without_the_failed_trial(capsys):
    """BayBE has no failed status and refuses a measurement with its target missing; one failed
    experiment used to raise here and end the whole optimization (the runner breaks on an error)."""
    pytest.importorskip("baybe")
    opt = _baybe({"model": "Random", "num_samples": 2})
    failed, *fine = opt.suggest(3)
    opt.observe([{**failed}] + [{**t, "y": float(t["x"])} for t in fine])

    recorded = opt.experiment.measurements
    assert len(recorded) == 2
    assert sorted(recorded["x"].tolist()) == sorted(t["x"] for t in fine)
    assert "gave no result" in capsys.readouterr().out


@pytest.mark.parametrize("optimizer_config", [
    pytest.param(None, id="default strategy"),
    pytest.param({"step_1": {"model": "Sobol", "num_samples": 5}, "step_2": {"model": "BoTorch"}}, id="Sobol x5 then BoTorch"),
])
def test_ax_fills_the_batch_across_a_node_change(optimizer_config):
    """Ax caps a batch by the trial limit of the node it is leaving, so asking for 3 with Sobol at
    4 of 5 trials gave 1; suggest asks again for the rest."""
    pytest.importorskip("ax")
    logging.disable(logging.CRITICAL)
    from ivoryos.optimizer.ax_optimizer import AxOptimizer

    opt = AxOptimizer("adapters", SPACE, OBJECTIVE, optimizer_config)
    nodes = []
    for _ in range(3):
        trials = opt.suggest(3)
        assert len(trials) == 3
        trials_on_record = opt.client._experiment.trials
        nodes += [trials_on_record[i].generator_run._generation_node_name for i in opt.trial_index_list]
        opt.observe([{**t, "y": _measure(t)} for t in trials])
    assert len(set(nodes)) > 1, "the model never took over"
    assert nodes[-1] == nodes[-2] == nodes[-3], "the last round should be the model's alone"
