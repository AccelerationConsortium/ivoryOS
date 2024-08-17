"""
Abstract Hardware API: Balance
This is an example of a hardware Python API.
docstring [optional]:   if given, docstring will be attached to the prompt when using LLM
_helper_function:       function names start with "_" will not be displayed
types and default:      Types (str, float, bool) and default values are recommended
"""
import logging
import typing

class DummyBalance:

    def __init__(self, com_port: str):
        self.com_port = com_port
        self._value = None
        self.logger = logging.getLogger("balance")

    @property
    def setter_value(self):
        return self._value

    @setter_value.setter
    def setter_value(self, value):
        self._value = value

    def weigh_sample(self):
        self.logger.info(f"Weighing sample using {self.com_port}")
        return 1

    def dose_solid(self, amount_in_mg: float):
        """this function is used to dose solid"""
        self.logger.info(f"Dosing {amount_in_mg} mg using {self.com_port}")
        return 1

    def _helper(self):
        """helper function will not be extracted and displayed over function panel"""
        pass


if __name__ == "__main__":
    balance = DummyBalance("com_port")

    # example of using ivoryOS for individual hardware
    from ivoryos.app import ivoryos

    ivoryos(__name__)
