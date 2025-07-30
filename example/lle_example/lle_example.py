
from typing import Union, List
from datetime import datetime

import ivoryos


class DeckSDL7():
    DATA_PATH = r"D:/git_repositories/automated-lle/data/"

    def _initialize_experiment(self, experiment_name: str = None):
        """
        Initializes the workflow by creating directories for data storage
        and creating a log file.
        """
        pass

    def initialize_deck(self, experiment_name: str = None, solvent_file: str = None,
                        method_name: str = None, inj_vol: int = 5):
        """
        Ensures all units are prepped and ready to run a workflow.
        These include homing the robotic arm, zeroing the balance,
        ensuring hplc instrument is on, etc
        """
        pass

    def run_extraction(self, stir_time: Union[int, float] = 1, settle_time: Union[int, float] = 1,
                       rate: int = 1000, reactor: int = 1, time_units: str = "min", output_file: str = None):

        pass

    def extraction_vial_to_reactor(self, vial: str = None):
        """
        Moves the extraction vial to the reactor for extraction & monitoring.
        """

        pass

    def extraction_vial_from_reactor(self, vial: str = None):
        """
        Moves the extraction vial from the reactor to the vial plate at the specified slot.
        """

        pass

    def weigh_container(self, vial: str = None, tray: str = None, sample_name: str = None,
                        to_hplc_inst: bool = False):

        pass

    def sample_aliquot(self, source_tray: str = None, source_vial: str = None,
                       dest_tray: str = 'hplc', dest_vial: str = None,
                       aliquot_volume_ul: Union[float, int] = 100):

        pass

    def volume_iterations(self, volume):

        pass

    def add_solvent(self, vial: str = 'A1', tray: str = 'hplc',
                    solvent: str = "Methanol", solvent_vol: Union[float, int] = 900,
                    clean: bool = False):

        pass

    def run_hplc(self, method: str = None, sample_name: str = None,
                 stall: bool = False, vial: str = None,
                 vial_hplc_location: str = 'P2-B1', inj_vol: int = 5):
        """
        Runs the specified HPLC experiment.
        """

        pass

    # TODO: move update container to Operations level
    def get_hplc_data(self, vial: str, channel: str = None, wavelength: int = 210, peaks: bool = True):
        """
        Loads the HPLC data for the specified vial.

        Available channels:
        channels:{"A": 210,
                  "B": 230,
                  "C": 254,
                  "D": 290,
                  "F": 320}

        """
        pass

    def remove_vial_from_hplc(self):
        self.arm.vial_from_hplc_instrument(slot='A')
        self.arm.to_exchange_horizontal()
        self.arm.container_to_tray(self.hplc.vial)
        self.hplc.has_vial = False
        self.hplc.vial = None

    def _make_experiment_directory(self, experiment_name: str = None):
        """
        Creates a new directory for the experiment data.
        """
        pass

    def hplc_instrument_setup(self, method: str = None, injection_volume: float = 10.0,
                              sequence: str = None):
        """
        sets up hplc for experiment

        """

        pass


deck = DeckSDL7()


if __name__ == "__main__":
    ivoryos.run(__name__)