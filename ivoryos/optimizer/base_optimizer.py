### ivoryos/optimizers/base.py

from abc import ABC, abstractmethod

from pandas.core.interchange.dataframe_protocol import DataFrame


class OptimizerBase(ABC):
    def __init__(self, experiment_name:str, parameter_space: list, objective_config: dict, optimizer_config: dict):
        self.experiment_name = experiment_name
        self.parameter_space = parameter_space
        self.objective_config = objective_config
        self.optimizer_config = optimizer_config

    @abstractmethod
    def suggest(self, n=1):
        pass

    @abstractmethod
    def observe(self, results: dict):
        pass

    @abstractmethod
    def append_existing_data(self, existing_data: DataFrame):
        pass

    @staticmethod
    def get_schema():
        """
        Returns a template for the optimizer configuration.
        """
        return {
            "parameter_types": ["range", "choice"],
            "multiple_objectives": True,
            # "objective_weights": True,
            "optimizer_config": {},
        }



