from abc import ABC
from dataclasses import dataclass

# TODO: replace any
@dataclass
class MoveableSequence(ABC):
    location_A: any
    location_B: any


@dataclass
class MoveableConfig(ABC):
    safe_moves: list[MoveableSequence]
