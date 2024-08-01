from abc import ABC, abstractmethod

from .arm import Arm
from .chemical import Chemical
from .container import Container
from .abclocation import ABCLocation
from .moveable import Moveable


class Handler(Moveable, ABC):
    @abstractmethod
    def dispense(self, chemical: Chemical, container: Container, location: ABCLocation, arm: Arm):
        pass
