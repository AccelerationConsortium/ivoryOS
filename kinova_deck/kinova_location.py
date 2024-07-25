from __future__ import annotations

import json

from hein_robots.grids import Grid
from hein_robots.robotics import Location, Cartesian

from abstract_robot_classes.abclocation import ABCLocation


def extract_location_from_file(sequence_location_name) -> Location:
    # TODO: update with adaptive path
    # /Users/lucyhao/summer/web_controller/kinova_deck/sequences/central_home.json
    pose_file_path = f"/Users/lucyhao/summer/web_controller/kinova_deck/sequences/{sequence_location_name}.json"
    with open(pose_file_path) as pose_file:
        data = json.load(pose_file)
        pose = data["poses"]["pose"][0]
        target_pose = pose['reachPose']['targetPose']
        return Location(target_pose['x'], target_pose['y'], target_pose['z'],
                        target_pose['thetaX'], target_pose['thetaY'], target_pose['thetaZ']).convert_m_to_mm()


class KinovaLocation(ABCLocation):

    def __init__(self, name: str, sequence_location_name: str, moveable_offset_x_y_z: tuple = (0, 0, 0)):
        # TODO need to have grids being update
        # or add to pddl???
        # since every deck in this lab has a grid, makes sense to add to pddl

        super().__init__(extract_location_from_file(sequence_location_name))
        self.name = name
        self.holdable = False
        self.moveable_offset_x_y_z = moveable_offset_x_y_z


class KinovaGridLocation(ABCLocation):
    def __init__(self, name: str, sequence_location_name: str, rows: int, columns: int, spacing_x: float,
                 spacing_y: float, offset_rx: float, offset_ry: float, offset_rz: float, index,
                 moveable_offset_x_y_z: tuple = (0, 0, 0)):
        # TODO need to have grids being update
        # or add to pddl???
        # since every deck in this lab has a grid, makes sense to add to pddl

        super().__init__(
            Grid(location=Location(**extract_location_from_file(sequence_location_name).position.dict),
                 rows=rows,
                 columns=columns,
                 spacing=Cartesian(x=spacing_x, y=spacing_y),
                 offset=Location(rx=offset_rx, ry=offset_ry, rz=offset_rz)).locations[index])
        self.name = name + index
        self.holdable = False
        self.moveable_offset_x_y_z = moveable_offset_x_y_z
