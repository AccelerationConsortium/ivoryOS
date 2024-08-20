"""
Abstract Self-driving Lab (SDL) API
This is an example of an SDL API - a collection of multiple hardware
docstring [optional]:   if given, docstring will be attached to the prompt when using LLM
_helper_function:       function names start with "_" will not be displayed
types and default:      Types (str, float, bool) and default values are recommended
"""

import logging
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from example.sdl_example.abstract_balance import DummyBalance
from example.sdl_example.abstract_pump import DummyPump


class DummySDLDeck:
    def __init__(self, pump: DummyPump, balance: DummyBalance):
        self.pump = pump
        self.balance = balance
        self.logger = logging.getLogger(f"logger_name")

    def dose_solvent(self, name: str, amount_in_ml: float = 5, rate_ml_per_minute: float = 1):
        self.pump.dose_liquid(amount_in_ml=amount_in_ml, rate_ml_per_minute=rate_ml_per_minute)
        self.balance.weigh_sample()
        self.logger.info(f"dosing {name} solvent")
        time.sleep(1)
        return 1

    def dose_solid(self, amount_in_mg: float = 5, bring_in: bool = False):
        """dose current chemical"""
        self.balance.dose_solid(amount_in_mg=amount_in_mg)
        self.balance.weigh_sample()
        self.logger.info("Dosing solid")
        time.sleep(1)
        self.logger.info(f"dosing solid {amount_in_mg}, bring in {bring_in}")
        return 1

    def equilibrate(self, temp: float, duration: float):
        self.logger.info(f"equilibrate at {temp} for {duration}")

    def analyze(self):
        self.logger.info("analyze")
        return 3

    def filtration(self):
        self.logger.info("filtration")

    def _send_command(self):
        """helper function"""
        pass


# some constant values, non-module variables are currently not extracted to UI
a = {"a": 1, "b": 3}


if __name__ == "__main__":
    # initializing hardware
    balance = DummyBalance("Fake com port 1")
    pump = DummyPump("Fake com port 2")
    deck = DummySDLDeck(pump, balance)

    from ivoryos import ivoryos
    # ivoryos()
    ivoryos(__name__, logger='logger_name')

    # # LLM using local model with Ollama
    # ivoryos(__name__, model="llama3.1", llm_server='localhost',)

    # # LLM with OpenAI api
    # ivoryos(__name__, model="gpt-3.5-turbo")

    """
    Example prompt when using text-to-code:
    
    add 10 mg of acetaminophen, dose 1 ml of methanol, 
    equilibrate for 10 minute at 50 degrees, 
    filter the sample and analyze with HPLC.
    """
