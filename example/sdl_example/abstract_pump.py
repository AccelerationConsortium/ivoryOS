"""
Abstract Hardware API: Pump
This is an example of a hardware Python API.
docstring [optional]:   if given, docstring will be attached to the prompt when using LLM
_helper_function:       function names start with "_" will not be displayed
types and default:      Types (str, float, bool) and default values are recommended
"""


class DummyPump:

    def __init__(self, com_port: str):
        self.com_port = com_port
        self.dictionary = {}

    def dose_liquid(self, amount_in_ml: float, rate_ml_per_minute: float):
        print(f"pretending dosing {amount_in_ml} at {rate_ml_per_minute} ml/min")
        return 1


if __name__ == "__main__":
    balance = DummyPump("com_port")

    # example of using ivoryOS for individual hardware
    from ivoryos.app import ivoryos

    ivoryos(__name__)
