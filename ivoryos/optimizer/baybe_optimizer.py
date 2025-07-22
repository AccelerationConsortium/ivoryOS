### Directory: ivoryos/optimizers/baybe_optimizer.py
from typing import Dict


from ivoryos.utils.utils import install_and_import
from ivoryos.optimizer.base_optimizer import OptimizerBase

class BaybeOptimizer(OptimizerBase):
    def __init__(self, experiment_name, parameter_space, objective_config, optimizer_config):
        try:
            from baybe import Campaign
        except ImportError:
            install_and_import("baybe")
            print("Please install Baybe with pip install baybe to before register BaybeOptimizer.")

        super().__init__(experiment_name, parameter_space, objective_config, optimizer_config)
        self._trial_id = 0
        self._trials = {}

        self.experiment = Campaign(
            searchspace=self._convert_parameter_to_searchspace(parameter_space),
            objective=self._convert_objective_to_baybe_format(objective_config),
            recommender=self._convert_recommender_to_baybe_format(optimizer_config),
        )


    def suggest(self, n=1):
        self.df = self.experiment.recommend(batch_size=n)
        return self.df.to_dict(orient="records")[0]

    def observe(self, results, index=None):
        """
        Observes the results of a trial and updates the experiment.
        :param results: A dictionary containing the results of the trial.
        :param index: The index of the trial in the DataFrame, if applicable.

        """
        for name, value in results.items():
            self.df[name] = [value]
        self.experiment.add_measurements(self.df)

    def append_existing_data(self, existing_data: Dict):
        """
        Append existing data to the Ax experiment.
        :param existing_data: A dictionary containing existing data.
        """
        import pandas as pd
        if not existing_data:
            return
        # parameter_names = [i.get("name") for i in self.parameter_space]
        # objective_names = [i.get("name") for i in self.objective_config]
        self.experiment.add_measurements(pd.DataFrame(existing_data))
        # for name, value in existing_data.items():
        #     # First attach the trial and note the trial index
        #     parameters = {name: value for name in existing_data if name in parameter_names}
        #     trial_index = self.client.attach_trial(parameters=parameters)
        #     raw_data = {name: value for name in existing_data if name in objective_names}
        #     # Then complete the trial with the existing data
        #     self.client.complete_trial(trial_index=trial_index, raw_data=raw_data)


    def _convert_parameter_to_searchspace(self, parameter_space):
        """
        Converts the parameter space configuration to Baybe format.
        :param parameter_space: The parameter space configuration.
        [
            {"name": "param_1", "type": "range", "bounds": [1.0, 2.0], "value_type": "float"},
            {"name": "param_2", "type": "choice", "bounds": ["a", "b", "c"], "value_type": "str"},
            {"name": "param_3", "type": "range", "bounds": [0 10], "value_type": "int"},
            {"name": "param_4", "type": "substance", "bounds": ["methanol", "water", "toluene"], "value_type": "str"} #TODO
        ]
        :return: A list of Baybe parameters.
        """
        from baybe.parameters.categorical import CategoricalParameter
        from baybe.parameters.numerical import NumericalContinuousParameter, NumericalDiscreteParameter
        from baybe.searchspace import SearchSpace
        parameters = []
        for p in parameter_space:
            if p["type"] == "range":
                if p["value_type"] == "float":
                    parameters.append(NumericalContinuousParameter(name=p["name"], bounds=p["bounds"]))
                elif p["value_type"] == "int":
                    values = tuple([int(v) for v in range(p["bounds"][0], p["bounds"][1] + 1)])
                    parameters.append(NumericalDiscreteParameter(name=p["name"], values=values))

            elif p["type"] == "choice":
                if p["value_type"] == "str":
                    parameters.append(CategoricalParameter(name=p["name"], values=p["bounds"]))
                elif p["value_type"] in ["int", "float"]:
                    parameters.append(NumericalDiscreteParameter(name=p["name"], values=p["bounds"]))
        return SearchSpace.from_product(parameters)

    def _convert_objective_to_baybe_format(self, objective_config):
        """
        Converts the objective configuration to Baybe format.
        :param parameter_space: The parameter space configuration.
        [
            {"name": "obj_1", "minimize": True},
            {"name": "obj_2", "minimize": False}
        ]
        :return: A Baybe objective configuration.
        """
        from baybe.targets import NumericalTarget
        from baybe.objectives import SingleTargetObjective, DesirabilityObjective, ParetoObjective
        targets = []
        weights = []
        for obj in objective_config:
            obj_name = obj.get("name")
            minimize = obj.get("minimize", False)
            weight = obj.get("weight", 1)
            weights.append(weight)
            targets.append(NumericalTarget(name=obj_name, mode="MAX" if minimize else "MIN"))

        if len(targets) == 1:
            return SingleTargetObjective(target=targets[0])
        else:
            # Handle multiple objectives
            return ParetoObjective(targets=targets)


    def _convert_recommender_to_baybe_format(self, recommender_config):
        """
        Converts the recommender configuration to Baybe format.
        :param recommender_config: The recommender configuration.
        :return: A Baybe recommender configuration.
        """
        from baybe.recommenders import (
            BotorchRecommender,
            FPSRecommender,
            TwoPhaseMetaRecommender,
            RandomRecommender,
            NaiveHybridSpaceRecommender
        )
        step_1 = recommender_config.get("step_1", {})
        step_2 = recommender_config.get("step_2", {})
        step_1_recommender = step_1.get("model", "Random")
        step_2_recommender = step_2.get("model", "BOTorch")
        if step_1.get("model") == "Random":
            step_1_recommender = RandomRecommender()
        elif step_1.get("model") == "FPS":
            step_1_recommender = FPSRecommender()
        if step_2.get("model") == "Naive Hybrid Space":
            step_2_recommender = NaiveHybridSpaceRecommender()
        elif step_2.get("model") == "BOTorch":
            step_2_recommender = BotorchRecommender()
        return TwoPhaseMetaRecommender(
            initial_recommender=step_1_recommender,
            recommender=step_2_recommender
        )

    @staticmethod
    def get_schema():
        """
        Returns a template for the optimizer configuration.
        """
        return {
            "parameter_types": ["range", "choice", "substance"],
            "multiple_objectives": True,
            "optimizer_config": {
                "step_1": {"model": ["Random", "FPS"], "num_samples": 10},
                "step_2": {"model": ["BOTorch", "Naive Hybrid Space"]}
            },
        }

if __name__ == "__main__":
    # Example usage
    baybe_optimizer = BaybeOptimizer(
        experiment_name="example_experiment",
        parameter_space=[
            {"name": "param_1", "type": "range", "bounds": [1.0, 2.0], "value_type": "float"},
            {"name": "param_2", "type": "choice", "bounds": ["a", "b", "c"], "value_type": "str"},
            {"name": "param_3", "type": "range", "bounds": [0, 10], "value_type": "int"}
        ],
        objective_config=[
            {"name": "obj_1", "minimize": True},
            {"name": "obj_2", "minimize": False}
        ],
        optimizer_config={
            "step_1": {"model": "Random", "num_samples": 10},
            "step_2": {"model": "BOTorch"}
        }
    )
    print(baybe_optimizer.suggest(5))