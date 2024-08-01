from abc import ABC, abstractmethod
from typing import Optional

from example.abstract_robot_classes.abclocation import ABCLocation
from example.abstract_robot_classes.moveable import Moveable


class Arm(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def move(self, from_loc: ABCLocation, to_loc: ABCLocation, moveable: Optional[Moveable] = None):
        pass

    @abstractmethod
    def pick_up(self, moveable: Moveable, location: ABCLocation):
        pass

    @abstractmethod
    def put_down(self, moveable: Moveable, location: ABCLocation):
        pass
