import sys
sys.path.insert(1, r"C:\Users\Public\PycharmProjects\pump_system")

from new_era.peristaltic_pump_network import PeristalticPumpNetwork, NetworkedPeristalticPump
from vapourtec.sf10 import SF10
from ika.thermoshaker import Thermoshaker
from ika.magnetic_stirrer import MagneticStirrer
from north_devices.pumps.tecan_cavro import TecanCavro
from vicim6 import ViciM6
from ftdi_serial import Serial

