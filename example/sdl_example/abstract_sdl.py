"""
Abstract Self-driving Lab (SDL) API
This is an example of an SDL API - a collection of multiple hardware
docstring [optional]:   if given, docstring will be attached to the prompt when using LLM
_helper_function:       function names start with "_" will not be displayed
types and default:      Types (str, float, bool) and default values are recommended
"""

from example.sdl_example.abstract_balance import DummyBalance
from example.sdl_example.abstract_pump import DummyPump


class DummySDLDeck:
    def __init__(self, pump: DummyPump, balance: DummyBalance):
        self.pump = pump
        self.balance = balance

    def dose_solvent(self, name: str, amount_in_ml: float = 5, rate_ml_per_minute: float = 1):
        self.pump.dose_liquid(amount_in_ml=amount_in_ml, rate_ml_per_minute=rate_ml_per_minute)
        self.balance.weigh_sample()
        print("dosing solvent")

    def dose_solid(self, amount_in_mg: float = 5, bring_in: bool = False):
        """dose current chemical"""
        self.balance.dose_solid(amount_in_mg=amount_in_mg)
        self.balance.weigh_sample()
        print("dosing solid")

    def equilibrate(self, temp: float, duration: float):
        print("equilibrate")

    def sample(self, sample_volume: float = 10):
        print("sample")

    def dilute(self, solvent: str, factor: float):
        print("dilute")

    def analyze(self):
        print("analyze")

    def filtration(self):
        print("filtration")

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

    from ivoryos.app import ivoryos

    ivoryos(__name__)

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
