from __future__ import annotations

import time
from typing import Union

from abstract_robot_classes.chemical import Chemical
from abstract_robot_classes.container import Container
from abstract_robot_classes.handler import Handler
from kinova_deck.components.europa_control import EuropaControlV2
from kinova_deck.kinova_arm import KinovaArm
from kinova_deck.kinova_location import KinovaLocation, KinovaGridLocation
from kinova_deck.moving.kinova_movable_config import KinovaMoveableConfig

EUROPA_PORT = "COM11"


class EuropaHandling(Handler):
    def __init__(self, max_volume_ul, name: str, config: KinovaMoveableConfig):
        super().__init__(name, config, offset_y=-0.02699998021, offset_z=0.19199999421)
        self.max_volume_ul = max_volume_ul
        self.chemical: Chemical = None
        try:
            self.handler = EuropaControlV2(EUROPA_PORT)
            self.handler.needle_home()
        except:
            pass

    def dispense(self, chemical: Chemical, container: Container, location: Union[KinovaLocation, KinovaGridLocation],
                 arm: KinovaArm):
        arm.arm.move_to_locations(location.robot_movement_information)

        # self.handler.dispense_ul(volume_ul=self.max_volume_ul)
        container.update_contents(chemical, self.max_volume_ul)
        time.sleep(1)

    def needle_up(self):
        # i hope this move it back to home
        self.handler.needle_home()

    def needle_down(self):
        # TODO: is negative down?
        self.handler.move_needle_to_absolute_position(absolute_position_mm=-50)

    def draw_liquid(self, container: Container, location: Union[KinovaLocation, KinovaGridLocation], arm: KinovaArm):
        arm.arm.move_to_locations(location.robot_movement_information)

        time.sleep(1)
        # self.handler.aspirate_ul(volume_ul=self.max_volume_ul)
        time.sleep(3)
        self.chemical = container.chemical
