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
import random
from enum import Enum
from typing import List, Union

# from ivoryos.config import get_config
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))


from abstract_balance import AbstractBalance
from abstract_pump import AbstractPump
# import prefect

class Solvent(Enum):
    Methanol = "Methanol"
    Ethanol = "Ethanol"
    Acetone = "Acetone"


class AbstractSDL(ABC):
    def __init__(self, pump: AbstractPump, balance: AbstractBalance):
        self.pump = pump
        self.balance = balance
        self.logger = logging.getLogger(f"logger_name")

    # @prefect.task
    def analyze(self, param_1:int, param_2:int):
        """analyze current chemical"""
        self.logger.info("analyze")
        print("analyzing")
        time.sleep(1)
        return random.random()

    # @prefect.task
    def dose_solid(self, amount_in_mg: float = 5,
                   solid_name: str = "acetaminophen",):
        """dose current chemical"""
        print("dosing solid")
        self.balance.dose_solid(amount_in_mg=amount_in_mg)
        self.balance.weigh_sample()
        self.logger.info("Dosing solid")
        time.sleep(1)
        self.logger.info(f"dosing solid {amount_in_mg}")
        return 1

    # @prefect.task
    def dose_solvent(self,
                     solvent_name: str = "Methanol",
                     amount_in_ml: float = 5,
                     rate_ml_per_minute: float = 1
                     ):
        print("dosing liquid")
        self.pump.dose_liquid(amount_in_ml=amount_in_ml, rate_ml_per_minute=rate_ml_per_minute)
        self.balance.weigh_sample()
        self.logger.info(f"dosing {solvent_name} solvent")
        time.sleep(1)
        return 1

    # @prefect.task
    def equilibrate(self, temp: float, duration: float):
        print("equilibrate")
        time.sleep(1)
        self.logger.info(f"equilibrate at {temp} for {duration}")

    # @prefect.task
    def simulate_error(self):
        raise ValueError("some error")

    def _send_command(self):
        """helper function"""
        pass


# some constant values, non-module variables are currently not extracted to UI
a = {"a": 1, "b": 3}
b = 1

# initializing hardware
balance = AbstractBalance("Fake com port 1")
pump = AbstractPump("Fake com port 2")
sdl = AbstractSDL(pump, balance)
# pump_2 = AbstractPump("3")

if __name__ == "__main__":
    
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
    import ivoryos
    # USE CASE 1 - start OS using current module
    ivoryos.run(__name__)




    # # USE CASE 2 - start OS using current module and enable LLM with Ollama
    # ivoryos.run(__name__, model="llama3.1", llm_server='localhost')

    # USE CASE 3 - start OS using current module and enable LLM with OpenAI api key in .env
    # ivoryos.run(__name__, )

    # # USE CASE 4 - start OS without using current module
    # ivoryos.run()

    # # LOGGER EXAMPLE - start OS using current module and include logger
    # ivoryos.run(__name__, logger='logger_name')

    """
    Example prompt when using text-to-code:

    add 10 mg of acetaminophen, dose 1 ml of methanol, 
    equilibrate for 10 minute at 50 degrees, 
    filter the sample and analyze with HPLC.
    """
