"""
Telescope Innovations Derivatization sampling example.
Platform Developer Junliang Liu, Yusuke Sato, Telescope Innovations Corp. All Rights Reserved
"""

import os
from sielc_dompser.autosampler.autosampler import Autosampler
from directinject import *
import ivoryos


class SimpleAutosampler:
    def __init__(self):
        self.autosampler = Autosampler('COM12')

    def home_autosampler(self):
        self.autosampler.home_tray_arm()

    def move_needle_to_injection_port(self):
        self.autosampler.needle_to_bottom_of_injection_port()

    def move_needle_to_waste_port(self):
        self.autosampler.needle_to_bottom_of_waste_port()

    def move_needle_to_bottom_of_vial(self, vial_number: int):
        self.autosampler.needle_to_bottom_of_vial(vial_number)


# todo set this
os.environ['DI_HOST'] = '192.168.254.199'  # '192.168.2.98' # kepler
os.environ['LABSOLUTIONS_BASE_ADDRESS'] = 'http://localhost:8000'

sielc = SimpleAutosampler()

if __name__ == "__main__":
    ivoryos.run(__name__, port=8001)
