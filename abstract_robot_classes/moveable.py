from abc import ABC
from typing import Optional

from abstract_robot_classes.moveableconfig import MoveableConfig


class Moveable(ABC):
    def __init__(self, name: str,
                 config: Optional[MoveableConfig] = None,
                 offset_x: float = 0,
                 offset_y: float = 0,
                 offset_z: float = 0):
        self.name = name
        self.gripped = False
        self.config: Optional[MoveableConfig] = config
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.offset_z = offset_z
