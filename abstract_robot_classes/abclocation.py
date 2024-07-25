from abc import ABC


class ABCLocation(ABC):
    def __init__(self, robot_movement_information):
        self.robot_movement_information = robot_movement_information
