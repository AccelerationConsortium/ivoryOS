# optimizers/ax_optimizer.py
from typing import Dict



from ivoryos.optimizer.base_optimizer import OptimizerBase
from ivoryos.utils.utils import install_and_import

class AxOptimizer(OptimizerBase):
    def __init__(self, experiment_name, parameter_space, objective_config, optimizer_config=None):
        try:
            from ax.api.client import Client
        except ImportError as e:
            install_and_import("ax", "ax-platform")
            raise ImportError("Please install Ax with pip install ax-platform to use AxOptimizer. Attempting to install Ax...")
        super().__init__(experiment_name, parameter_space, objective_config, optimizer_config)

        self.client = Client()
        # 2. Configure where Ax will search.
        self.client.configure_experiment(
            name=experiment_name,
            parameters=self._convert_parameter_to_ax_format(parameter_space)
        )
        # 3. Configure the objective function.
        self.client.configure_optimization(objective=self._convert_objective_to_ax_format(objective_config))
        if optimizer_config:
            self.client.set_generation_strategy(self._convert_generator_to_ax_format(optimizer_config))
        self.generators = self._create_generator_mapping()

    @staticmethod
    def _create_generator_mapping():
        """Create a mapping from string values to Generator enum members."""
        from ax.modelbridge import Generators
        return {member.value: member for member in Generators}

    def _convert_parameter_to_ax_format(self, parameter_space):
        """
        Converts the parameter space configuration to Baybe format.
        :param parameter_space: The parameter space configuration.
        [
            {"name": "param_1", "type": "range", "bounds": [1.0, 2.0], "value_type": "float"},
            {"name": "param_2", "type": "choice", "bounds": ["a", "b", "c"], "value_type": "str"},
            {"name": "param_3", "type": "range", "bounds": [0 10], "value_type": "int"},
        ]
        :return: A list of Baybe parameters.
        """
        from ax import RangeParameterConfig, ChoiceParameterConfig
        ax_params = []
        for p in parameter_space:
            if p["type"] == "range":
                ax_params.append(
                    RangeParameterConfig(
                        name=p["name"],
                        bounds=tuple(p["bounds"]),
                        parameter_type=p["value_type"]
                    ))
            elif p["type"] == "choice":
                ax_params.append(
                    ChoiceParameterConfig(
                        name=p["name"],
                        values=p["bounds"],
                        parameter_type=p["value_type"],
                    )
                )
        return ax_params

    def _convert_objective_to_ax_format(self, objective_config: list):
        """
        Converts the objective configuration to Baybe format.
        :param parameter_space: The parameter space configuration.
        [
            {"name": "obj_1", "minimize": True, "weight": 1},
            {"name": "obj_2", "minimize": False, "weight": 2}
        ]
        :return: Ax objective configuration. "-cost, utility"
        """
        objectives = []
        for obj in objective_config:
            obj_name = obj.get("name")
            minimize = obj.get("minimize", True)
            weight = obj.get("weight", 1)
            sign = "-" if minimize else ""
            objectives.append(f"{sign}{weight} * {obj_name}")
        return ", ".join(objectives)

    def _convert_generator_to_ax_format(self, optimizer_config):
        """
        Converts the optimizer configuration to Ax format.
        :param optimizer_config: The optimizer configuration.
        :return: Ax generator configuration.
        """
        from ax.generation_strategy.generation_node import GenerationStep
        from ax.generation_strategy.generation_strategy import GenerationStrategy
        generators = self._create_generator_mapping()
        step_1 = optimizer_config.get("step_1", {})
        step_2 = optimizer_config.get("step_2", {})
        step_1_generator = step_1.get("model", "Sobol")
        step_2_generator = step_2.get("model", "BOTorch")
        generator_1 = GenerationStep(model=generators.get(step_1_generator), num_trials=step_1.get("num_samples", 5))
        generator_2 = GenerationStep(model=generators.get(step_2_generator), num_trials=step_2.get("num_samples", -1))
        return GenerationStrategy(steps=[generator_1, generator_2])

    def suggest(self, n=1):
        trial_index, params = self.client.get_next_trials(1).popitem()
        self.trial_index = trial_index
        return params

    def observe(self, results):
        self.client.complete_trial(
            trial_index=self.trial_index,
            raw_data=results
        )

    @staticmethod
    def get_schema():
        return {
            "parameter_types": ["range", "choice"],
            "multiple_objectives": True,
            # "objective_weights": True,
            "optimizer_config": {
                "step_1": {"model": ["Sobol", "Uniform", "Factorial", "Thompson"], "num_samples": 5},
                "step_2": {"model": ["BoTorch", "SAASBO", "SAAS_MTGP", "Legacy_GPEI", "EB", "EB_Ashr", "ST_MTGP", "BO_MIXED", "Contextual_SACBO"]}
            },
        }

    def append_existing_data(self, existing_data):
        """
        Append existing data to the Ax experiment.
        :param existing_data: A dictionary containing existing data.
        """
        from pandas import DataFrame
        if not existing_data:
            return
        if isinstance(existing_data, DataFrame):
            existing_data = existing_data.to_dict(orient="records")
        parameter_names = [i.get("name") for i in self.parameter_space]
        objective_names = [i.get("name") for i in self.objective_config]
        for name, value in existing_data.items():
            # First attach the trial and note the trial index
            parameters = {name: value for name in existing_data if name in parameter_names}
            trial_index = self.client.attach_trial(parameters=parameters)
            raw_data = {name: value for name in existing_data if name in objective_names}
            # Then complete the trial with the existing data
            self.client.complete_trial(trial_index=trial_index, raw_data=raw_data)


if __name__ == "__main__":
    # Example usage
    optimizer = AxOptimizer(
        experiment_name="example_experiment",
        parameter_space=[
            {"name": "param_1", "type": "range", "bounds": [0.0, 1.0], "value_type": "float"},
            {"name": "param_2", "type": "choice", "bounds": ["a", "b", "c"], "value_type": "str"}
        ],
        objective_config=[
            {"name": "objective_1", "minimize": True},
            {"name": "objective_2", "minimize": False}
        ],
        optimizer_config={
            "step_1": {"model": "Sobol", "num_samples": 5},
            "step_2": {"model": "BoTorch"}
        }
    )
    print(optimizer._create_generator_mapping())