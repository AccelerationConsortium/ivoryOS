"""
Abstract Self-driving Lab (SDL) API
This is an example of an SDL API - a collection of multiple hardware
docstring [optional]:   if given, docstring will be attached to the prompt when using LLM
_helper_function:       function names start with "_" will not be displayed
types and default:      Types (str, float, bool) and default values are recommended
"""
# from __future__ import annotations

import logging
import os
import sys
import time
from abc import ABC
from typing import List, Union

from example.abstract_sdl_example.abstract_balance import AbstractBalance
from example.abstract_sdl_example.abstract_pump import AbstractPump


class AbstractSDL(ABC):
    def __init__(self, pump: AbstractPump, balance: AbstractBalance):
        self.pump = pump
        self.balance = balance
        self.logger = logging.getLogger(f"logger_name")

    def dose_solvent(self, solvent_name: str, amount_in_ml: float = 5, rate_ml_per_minute: float = 1):
        self.pump.dose_liquid(amount_in_ml=amount_in_ml, rate_ml_per_minute=rate_ml_per_minute)
        self.balance.weigh_sample()
        self.logger.info(f"dosing {solvent_name} solvent")
        time.sleep(1)
        return 1

    def dose_solid(self, amount_in_mg: float = 5, bring_in: bool = False):
        """dose current chemical"""
        self.balance.dose_solid(amount_in_mg=amount_in_mg)
        self.balance.weigh_sample()
        self.logger.info("Dosing solid")
        time.sleep(10)
        self.logger.info(f"dosing solid {amount_in_mg}, bring in {bring_in}")
        return 1

    def equilibrate(self, temp: float, duration: float):
        self.logger.info(f"equilibrate at {temp} for {duration}")

    def analyze(self):
        self.logger.info("analyze")
        return 3

    def filtration(self, test):
        for i in test:
            print(i)
        self.logger.info("filtration")

    def _send_command(self):
        """helper function"""
        pass

    def example_function(self,
                         a: int,
                         b: str,
                         # c: float | None,  # Optional[float]
                         # d: str | int,  # Union[str, int]
                         e: list[str],  # List[str]
                         f: dict[str, int],  # Dict[str, int]
                         g: tuple[int, str, float]  # Tuple[int, str, float]
                         ):

        pass


    def prepare_extraction_vial(self,
                                 crude_plate: str = 'extraction', crude_volume: Union[float, int] = 3000,
                                 org_solvent: str = "dichloromethane", org_volume: Union[float, int] = 2000,
                                 aq_solvent: str = "water", aq_volume: int = 2000):

        print(type(aq_volume))


# some constant values, non-module variables are currently not extracted to UI
a = {"a": 1, "b": 3}
b = 1

# initializing hardware
balance = AbstractBalance("Fake com port 1")
pump = AbstractPump("Fake com port 2")
sdl = AbstractSDL(pump, balance)
# pump_2 = AbstractPump("3")

if __name__ == "__main__":
    import ivoryos

    # USE CASE 1 - start OS using current module
    # ivoryos.run(__name__)

    # # USE CASE 2 - start OS using current module and enable LLM with Ollama
    # ivoryos.run(__name__, model="llama3.1", llm_server='localhost')

    # USE CASE 3 - start OS using current module and enable LLM with OpenAI api key in .env
    # ivoryos.run(__name__, )

    # # USE CASE 4 - start OS without using current module
    # ivoryos.run()

    # # LOGGER EXAMPLE - start OS using current module and include logger
    ivoryos.run(__name__, logger='logger_name')

    """
    Example prompt when using text-to-code:

    add 10 mg of acetaminophen, dose 1 ml of methanol, 
    equilibrate for 10 minute at 50 degrees, 
    filter the sample and analyze with HPLC.
    """
