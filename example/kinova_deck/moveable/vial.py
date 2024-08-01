from __future__ import annotations

from typing import Union, Optional

from example.abstract_robot_classes.chemical import Chemical
from example.abstract_robot_classes.container import Container
from example.kinova_deck.moving.kinova_movable_config import KinovaMoveableConfig


class Vial(Container):
    def __init__(self, name: str, chemical: Optional[Union[Liquid, Solid]],
                 config: Optional[KinovaMoveableConfig] = None):
        super().__init__(name=name, config=config)
        self.chemical = chemical
        self.amount_ul: int = 0

    def update_contents(self, chemical: Chemical, amount_ul: int):
        self.chemical = chemical
        self.amount_ul += amount_ul
