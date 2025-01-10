"""
Telescope Innovations Solubility Platform.
Platform Developer Ryan Corkery, Veronica Lai, Telescope Innovations Corp. All Rights Reserved
"""
from typing import Optional, Dict
import logging

import ivoryos

from src.controllers.solubility_controller import SolubilityController
from src import services

logging.getLogger('URRTMonitor').setLevel(logging.INFO)


class SolubilitySDL:
    def __init__(self):
        self.controller = services.services.get_controller(SolubilityController)
        self.controller.wait_for_init()

        self.workflow = self.controller.workflow

    # -------------------------------------------------------------------- #
    # ----------------------------- CONTROLLER --------------------------- #
    # -------------------------------------------------------------------- #

    def run_campaign(self,
                     solid_name: str,
                     solid_mass_mg: float,
                     solvent_names: list,
                     campaign_name: str = None,
                     ):
        solvent_names = ''.join(solvent_names).split(',')
        solvent_names = [s.strip() for s in solvent_names]
        self.controller.run_campaign(solid_name, solid_mass_mg, solvent_names, campaign_name)

    def run_workflow(self,
                     solid_name: str,
                     solid_mass_mg: float,
                     solvent_name: str,
                     ):
        self.controller.run_workflow(solid_name, solid_mass_mg, solvent_name)

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

    def capping_station_test_decapping_and_capping(self):
        self.controller.workflow.capping_station_test_decapping_and_capping()


solubility_sdl = SolubilitySDL()

if __name__ == '__main__':
    ivoryos.run(__name__, logger=[solubility_sdl.controller.logger.name])