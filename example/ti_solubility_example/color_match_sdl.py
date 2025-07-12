"""
Telescope Innovations Solubility Platform.
Platform Developer Ryan Corkery, Veronica Lai, Telescope Innovations Corp. All Rights Reserved
"""
from typing import Optional, Dict
import logging

import ivoryos

# from color_matching import ColorAnalyzer



logging.getLogger('URRTMonitor').setLevel(logging.INFO)
_reference_image_path = r"C:\git_repositories\solubility\data\ivory_colour_matching\blue 1000ul red 500ul.png"
_roi_coords = (1150, 650, 400, 400)  # Adjust these coordinates to match your ROI

class ColourMatchingSDL:
    def __init__(self):
        pass

    # -------------------------------------------------------------------- #
    # ----------------------------- CONTROLLER --------------------------- #
    # -------------------------------------------------------------------- #

    def set_all_vials_clean(self):
        pass

    def update_solvent_information(self, name: str, density: float, valve_position: int):
        pass

    def get_all_solvent_information(self) -> Dict:
        pass

    def update_solid_information(self, name: str, dosing_head_index: str):
        pass

    def get_all_solid_information(self) -> Dict:
        pass

    # -------------------------------------------------------------------- #
    # ------------------------ WORKFLOW/SEQUENCES ------------------------ #
    # -------------------------------------------------------------------- #

    def home_liquid_handler(self):
        pass

    def prime_solvent_line(self, line_number: int, volume_ml: float):
        pass

    def start_heating(self, temperature: Optional[float] = None):
        pass

    def stop_heating(self):
        pass

    def start_stirring(self, rpm: Optional[int] = None):
        pass

    def stop_stirring(self):
        pass

    def auto_recover_arm_position_to_home(self):
        pass

    def create_vial_mixture(self, solvent_1_ul: int):
        pass


colour_matching_sdl = ColourMatchingSDL()

ivoryos.run(__name__)










