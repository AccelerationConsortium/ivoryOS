from __future__ import annotations

import time
from typing import Optional, Union

from example.abstract_robot_classes.arm import Arm
from example.abstract_robot_classes.container import Container
from example.abstract_robot_classes.moveable import Moveable
from example.kinova_deck.kinova_location import extract_location_from_file, KinovaLocation, KinovaGridLocation
from example.kinova_deck.moving.kinova_movable_config import KinovaMoveableConfig

KINOVA_ADDRESS = "137.82.65.87"
SAFE_VELOCITY = 50
SAFE_GRIPPER_VELOCITY = 0.05
SUPER_SAFE_VELOCITY = 10


class KinovaArm(Arm):
    """
    notes and assumptions
    the arm grippers are by default open wide
    this assumption is not great, it's okay
    the only object in the z plane that might be hit is the liquid handler
    this conflict is dealt with by only moving in the x plane, and then in the y plane (or wise versa)
    """

    def __init__(self, name: str, home_coordinates: str):
        super().__init__(name)
        try:
            print("here")
            # self.arm = KinovaGen3Arm(KINOVA_ADDRESS)
            # self.arm.open_gripper(0)
            # self.arm.move_to_location(self.home)
        except:
            pass

        self.gripping = False
        self.home = extract_location_from_file(home_coordinates)
        self.safe_z = 250

    def move(self, from_loc: Union[KinovaLocation, KinovaGridLocation],
             to_loc: Union[KinovaLocation, KinovaGridLocation],
             moveable: Optional[Moveable] = None):
        # TODO: the joint seems to be moving a bit
        # if changing the dif to arm.location.z - location.z, then to actually move to location.z, we need
        # to reverse the sign of the dif

        destination_z = to_loc.robot_movement_information.z
        curr_arm_z = self.arm.location.z
        destination_z_dif = destination_z - self.arm.location.z
        safe_height_z_dif = self.safe_z - self.arm.location.z
        x_dif = to_loc.robot_movement_information.x - self.arm.location.x
        y_dif = to_loc.robot_movement_information.y - self.arm.location.y

        if self.gripping:
            if curr_arm_z < self.safe_z or curr_arm_z < destination_z:
                if destination_z > self.safe_z:
                    self.arm.move_to_location(self.arm.location.translate(z=destination_z_dif))
                else:
                    self.arm.move_to_location(self.arm.location.translate(z=safe_height_z_dif))
            # else stay at the current height

        if from_loc.name == "home":

            if not self.gripping:
                if destination_z > self.safe_z:
                    self.arm.move_to_location(self.arm.location.translate(z=destination_z_dif))
                elif destination_z < self.safe_z:
                    self.arm.move_to_location(self.arm.location.translate(z=safe_height_z_dif))

            self.arm.move_to_location(self.arm.location.translate(x=x_dif))
            self.arm.move_to_location(self.arm.location.translate(y=y_dif))
            self.arm.move_to_location(to_loc.robot_movement_information)

        elif to_loc.name == "home":

            if not self.gripping:
                if destination_z < self.safe_z:
                    self.arm.move_to_location(self.arm.location.translate(z=safe_height_z_dif))

            self.arm.move_to_location(self.arm.location.translate(y=y_dif))
            self.arm.move_to_location(self.arm.location.translate(x=x_dif))
            self.arm.move_to_location(to_loc.robot_movement_information)

    def pick_up(self, moveable: Moveable, location: Union[KinovaLocation, KinovaGridLocation]):
        # assume arm is ready at safe approach location
        if isinstance(moveable.config, KinovaMoveableConfig) and isinstance(location, KinovaLocation):
            # opens gripper
            self.arm.open_gripper(position=moveable.config.grip_open)
            # moves to base location
            self.arm.move_to_locations(location.robot_movement_information)
            # close gripper
            self.arm.open_gripper(moveable.config.grip_close)
            moveable.gripped = True
            self.gripping = True
        elif isinstance(moveable.config, KinovaMoveableConfig) and isinstance(moveable, Container) and isinstance(
                location, KinovaGridLocation):
            # opens gripper
            self.arm.open_gripper(position=moveable.config.grip_open, velocity=SAFE_GRIPPER_VELOCITY)
            z_dif = self.arm.location.z - location.robot_movement_information.z
            y_dif = location.robot_movement_information.y - self.arm.location.y
            self.arm.move_to_location(self.arm.location.translate(z=z_dif))
            self.arm.move_to_location(self.arm.location.translate(y=y_dif))
            self.arm.move_to_locations(location.robot_movement_information)
            # close gripper
            self.arm.open_gripper(moveable.config.grip_close, velocity=SAFE_GRIPPER_VELOCITY)
            time.sleep(1)
            self.arm.open_gripper(moveable.config.grip_close, velocity=SAFE_GRIPPER_VELOCITY)
            moveable.gripped = True
            self.gripping = True
        else:
            raise NotImplementedError

    def put_down(self, moveable: Moveable, location: Union[KinovaLocation, KinovaGridLocation]):
        if isinstance(moveable.config, KinovaMoveableConfig):
            # move to base
            self.arm.move_to_locations(location.robot_movement_information)
            # open gripper
            self.arm.open_gripper(0)
            moveable.gripped = False
            self.gripping = False
        else:
            raise NotImplementedError
            # need to add grid
