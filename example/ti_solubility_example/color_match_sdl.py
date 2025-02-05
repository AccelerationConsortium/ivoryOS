"""
Telescope Innovations Solubility Platform.
Platform Developer Ryan Corkery, Veronica Lai, Telescope Innovations Corp. All Rights Reserved
"""
from typing import Optional, Dict
import logging

import ivoryos

from color_matching import ColorAnalyzer
from src.controllers.colour_matching_controller import ColourMatchingController
from src import services


logging.getLogger('URRTMonitor').setLevel(logging.INFO)
_reference_image_path = r"C:\git_repositories\solubility\data\ivory_colour_matching\blue 1000ul red 500ul.png"
_roi_coords = (1150, 650, 400, 400)  # Adjust these coordinates to match your ROI

class ColourMatchingSDL:
    def __init__(self):
        self.controller = services.services.get_controller(ColourMatchingController)
        self.controller.wait_for_init()

        self.analyzer = ColorAnalyzer(_reference_image_path, _roi_coords)
        self.workflow = self.controller.workflow

    # -------------------------------------------------------------------- #
    # ----------------------------- CONTROLLER --------------------------- #
    # -------------------------------------------------------------------- #

    def set_all_vials_clean(self):
        self.controller.set_all_vials_clean()

    def update_solvent_information(self, name: str, density: float, valve_position: int):
        self.controller.update_solvent_information(valve_position=valve_position, name=name, density=density)

    def get_all_solvent_information(self) -> Dict:
        return self.controller.get_all_solvent_information()

    def update_solid_information(self, name: str, dosing_head_index: str):
        self.controller.update_solid_information(name=name, index=dosing_head_index)

    def get_all_solid_information(self) -> Dict:
        return self.controller.get_all_solid_information()

    # -------------------------------------------------------------------- #
    # ------------------------ WORKFLOW/SEQUENCES ------------------------ #
    # -------------------------------------------------------------------- #

    def home_liquid_handler(self):
        self.workflow.home_cartesian_gantry()

    def prime_solvent_line(self, line_number: int, volume_ml: float):
        self.controller.prime_solvent_line(line_number=line_number, volume_ml=volume_ml)

    def start_heating(self, temperature: Optional[float] = None):
        self.workflow.start_heating(temperature=temperature)

    def stop_heating(self):
        self.workflow.stop_heating()

    def start_stirring(self, rpm: Optional[int] = None):
        self.workflow.start_stirring(rpm)

    def stop_stirring(self):
        self.workflow.stop_stirring()

    def auto_recover_arm_position_to_home(self):
        self.controller.auto_recover_arm_position_to_home()

    def create_vial_mixture(self, solvent_1_ul: int):
        solvent_2_ul = 1500 - solvent_1_ul
        frame = self.controller.create_vial_mixture(solvent_1_ul=solvent_1_ul, solvent_2_ul=solvent_2_ul)
        return self.analyzer.analyze_image(frame)


colour_matching_sdl = ColourMatchingSDL()


if __name__ == '__main__':
    print('')
    ivoryos.run(__name__, logger=[colour_matching_sdl.controller.logger.name])









