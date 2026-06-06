import logging
import time
from enum import Enum
from typing import Optional, Union, List, Literal

class Color(Enum):
    RED = "Red"
    GREEN = "Green"
    BLUE = "Blue"

class InputTypeShowcase:
    """
    A showcase of all the input types supported by IvoryOS's dynamic forms.
    This class can be used as a 'deck' or an instrument to see how the frontend renders different type hints.
    """

    def __init__(self):
        self.logger = logging.getLogger("showcase_logger")
        self.logger.setLevel(logging.INFO)

    def basic_types(self, string_input: str, int_input: int, float_input: float, bool_input: bool):
        """
        Showcases basic primitive types: str, int, float, bool.
        """
        self.logger.info(f"Received string: {string_input}")
        self.logger.info(f"Received int: {int_input}")
        self.logger.info(f"Received float: {float_input}")
        self.logger.info(f"Received bool: {bool_input}")
        return True

    def optional_types(self, optional_int: Optional[int] = None, optional_str: Union[str, None] = None):
        """
        Showcases optional types which do not enforce the InputRequired validator.
        """
        self.logger.info(f"Received optional int: {optional_int}")
        self.logger.info(f"Received optional str: {optional_str}")
        return True

    def default_values(self, standard_timeout: int = 60, default_name: str = "IvoryOS"):
        """
        Showcases how default values are pre-filled in the frontend.
        """
        self.logger.info(f"Timeout: {standard_timeout}, Name: {default_name}")
        return True

    def enum_choices(self, primary_color: Color, optional_color: Optional[Color] = None):
        """
        Showcases dropdown selections using an Enum.
        """
        self.logger.info(f"Primary Color: {primary_color}")
        self.logger.info(f"Optional Color: {optional_color}")
        return True

    def literal_choices(self, mode: Literal["Fast", "Standard", "Slow"], retry: Literal[1, 3, 5] = 3):
        """
        Showcases dropdown selections using typing.Literal.
        """
        self.logger.info(f"Mode: {mode}")
        self.logger.info(f"Retries: {retry}")
        return True

    def list_types(self, sample_ids: List[str], temperatures: list):
        """
        Showcases how lists are handled.
        """
        self.logger.info(f"Sample IDs: {sample_ids}")
        self.logger.info(f"Temperatures: {temperatures}")
        return True

    def multiple_returns(self) -> tuple[int, float, str]:
        """
        Showcases how a function returning a tuple generates multiple 'Save item X as' fields.
        """
        return 1, 3.14, "Success"


if __name__ == "__main__":
    # Example usage / testing
    input_type = InputTypeShowcase()
    import ivoryos
    ivoryos.run(__name__, logger=input_type.logger.name)