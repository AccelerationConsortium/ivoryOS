from dataclasses import dataclass
from typing import Callable, Optional, Union

from example.abstract_robot_classes.moveableconfig import MoveableSequence, MoveableConfig


@dataclass
class KinovaMoveableSequence(MoveableSequence):
    location_A: Union[str, list[str]]
    location_B: Union[str, list[str]]
    sequence_from_A_to_B: Optional[Callable] = None
    sequence_from_B_to_A: Optional[Callable] = None


# TODO: define on a type or specific object
@dataclass
class KinovaMoveableConfig(MoveableConfig):
    name: Union[str, type]
    safe_moves: list[KinovaMoveableSequence]
    grip_open: float
    grip_close: float
