from abc import ABC, abstractmethod
from typing import Optional

from abstract_robot_classes.chemical import Chemical
from abstract_robot_classes.moveable import Moveable
from kinova_deck.moving.kinova_movable_config import KinovaMoveableConfig


class Container(Moveable, ABC):
    def __init__(self, name: str, config: Optional[KinovaMoveableConfig] = None):
        super().__init__(name, config)

    @abstractmethod
    def update_contents(self, chemical: Chemical, amount_ul: int):
        pass
